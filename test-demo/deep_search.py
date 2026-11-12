"""Deep Search - find a company's email / phone / website when the first search result doesn't show them.

Waterfall (stops adding steps once an email is found, except the free website crawl):
  1. Website   - use the result's own website; for a listing (LinkedIn, IndiaMART...) look the
                 company up on the search engine and pick the result whose domain matches the name.
  2. Crawl     - homepage + up to 3 Contact / About pages: emails (mailto + text), Indian phones,
                 address, social links. Uses the HTML cache (html_cache_manager), so a page is
                 downloaded at most once per HTML_CACHE_MAX_AGE_DAYS.
  3. JSON-LD   - schema.org Organization / LocalBusiness data: email, telephone, sameAs, address.
  4. Zaubacorp - for registered companies (Pvt Ltd / Limited / LLP): MCA record email + CIN.
  5. Hunter    - optional, uses Hunter.io credits (HUNTER_API_KEY): emails on the domain.
  6. Guess     - info@domain when the domain accepts mail. Marked "guess", never saved as the email.

Safety: only public http(s) websites on ports 80/443 are fetched; every redirect is re-checked, so the
server can't be pointed at localhost or a private network. Pages are capped at 3 MB.
"""
import ipaddress
import json
import os
import re
import socket
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

import html_cache_manager as hcm
import search_engine as se

MAX_ITEMS_PER_CALL = 10
MAX_SUBPAGES = 3
WORKERS = 4
PAGE_TIMEOUT = 10
REGISTERED_RE = re.compile(r"\b(pvt|private|limited|ltd|llp)\b\.?", re.I)
CIN_RE = re.compile(r"\b[LU]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6}\b")
SOCIAL_PATTERNS = {
    "linkedin": re.compile(r"https?://(?:[a-z]{2,3}\.)?linkedin\.com/(?:company|in)/[^\s\"'<>?#]+", re.I),
    "instagram": re.compile(r"https?://(?:www\.)?instagram\.com/[A-Za-z0-9_.]+/?", re.I),
    "facebook": re.compile(r"https?://(?:www\.|m\.)?facebook\.com/[^\s\"'<>?#]+", re.I),
    "twitter": re.compile(r"https?://(?:www\.)?(?:twitter|x)\.com/[A-Za-z0-9_]+/?", re.I),
    "youtube": re.compile(r"https?://(?:www\.)?youtube\.com/(?:@|c/|channel/|user/)[^\s\"'<>?#]+", re.I),
    "whatsapp": re.compile(r"https?://(?:wa\.me|api\.whatsapp\.com/send)[^\s\"'<>]*", re.I),
}
SOCIAL_SKIP = ("/sharer", "/share", "/intent/", "/plugins/", "/dialog/", "/tr?", "/hashtag/")
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; LeadsGenAI-DeepSearch/1.0)", "Accept-Language": "en-IN,en;q=0.9"}


def _scraper():
    """scraper.py holds the tested email / phone / address extractors. Imported lazily (it pulls pandas)."""
    import scraper
    return scraper


# ---------------------------------------------------------------------------
# Safety
# ---------------------------------------------------------------------------

def public_url_guard(url: str) -> None:
    """Raises hcm.BlockedUrl unless url is http(s) on a public IP address and a normal port."""
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.hostname:
        raise hcm.BlockedUrl(f"not a web address: {url[:80]}")
    if p.port not in (None, 80, 443):
        raise hcm.BlockedUrl(f"port {p.port} not allowed")
    try:
        infos = socket.getaddrinfo(p.hostname, p.port or (443 if p.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except socket.gaierror:
        raise hcm.BlockedUrl(f"domain not found: {p.hostname}")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0].split("%")[0])
        if not ip.is_global:
            raise hcm.BlockedUrl(f"{p.hostname} points to a private address")


def fetch(url: str) -> str:
    try:
        public_url_guard(url)
    except hcm.BlockedUrl:
        return ""
    html, ok = hcm.fetch_or_get_cached_html(url, headers=HEADERS, timeout=PAGE_TIMEOUT, guard=public_url_guard)
    return html if ok else ""


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

def site_root(url: str) -> str:
    p = urlparse(url if "://" in url else "https://" + url)
    return f"{p.scheme}://{p.netloc}/" if p.netloc else ""


def extract_socials(html: str) -> Dict[str, str]:
    out = {}
    for name, pat in SOCIAL_PATTERNS.items():
        for m in pat.findall(html or ""):
            if not any(s in m.lower() for s in SOCIAL_SKIP):
                out[name] = m.rstrip("/\\")
                break
    return out


def extract_jsonld(soup: BeautifulSoup) -> Dict[str, Any]:
    found: Dict[str, Any] = {"emails": [], "phones": [], "same_as": [], "address": "", "name": ""}

    def walk(node):
        if isinstance(node, list):
            for n in node:
                walk(n)
            return
        if not isinstance(node, dict):
            return
        if "@graph" in node:
            walk(node["@graph"])
        types = node.get("@type")
        types = types if isinstance(types, list) else [types]
        if any(t in ("Organization", "Corporation", "LocalBusiness", "ProfessionalService", "Store") or
               (isinstance(t, str) and t.endswith("Business")) for t in types):
            if node.get("name") and not found["name"]:
                found["name"] = str(node["name"]).strip()[:90]
            if node.get("email"):
                found["emails"].append(str(node["email"]).replace("mailto:", "").strip().lower())
            if node.get("telephone"):
                found["phones"].append(str(node["telephone"]))
            same = node.get("sameAs") or []
            found["same_as"] += same if isinstance(same, list) else [same]
            addr = node.get("address")
            if isinstance(addr, dict) and not found["address"]:
                found["address"] = ", ".join(str(addr.get(k)) for k in
                                             ("streetAddress", "addressLocality", "addressRegion", "postalCode")
                                             if addr.get(k))
            elif isinstance(addr, str) and not found["address"]:
                found["address"] = addr
        for v in node.values():
            if isinstance(v, (dict, list)):
                walk(v)

    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            walk(json.loads(tag.string or tag.get_text() or ""))
        except (ValueError, TypeError):
            continue
    return found


def _rank_emails(emails: List[str], domain: str) -> List[str]:
    uniq = []
    for e in emails:
        e = e.strip().lower()
        if e and se.EMAIL_RE.fullmatch(e) and e not in uniq:
            uniq.append(e)
    on_domain = [e for e in uniq if domain and e.split("@")[1].endswith(domain)]
    return (on_domain + [e for e in uniq if e not in on_domain])[:3]


def crawl_site(website: str) -> Dict[str, Any]:
    """Homepage + up to MAX_SUBPAGES contact/about pages."""
    sc = _scraper()
    root = site_root(website)
    out = {"emails": [], "phones": [], "address": "", "socials": {}, "name": "", "pages": [], "error": ""}
    if not root:
        out["error"] = "no website"
        return out
    home_url = root
    home = fetch(root)
    if not home and website.rstrip("/") != root.rstrip("/"):
        home_url, home = website, fetch(website)
    if not home:
        out["error"] = "website could not be opened"
        return out
    pages = [(home_url, home)]
    soup = BeautifulSoup(home, "html.parser")
    jl_home = extract_jsonld(soup)
    og = soup.find("meta", property="og:site_name")
    title = se.clean_title(soup.title.get_text()) if soup.title else ""
    # JSON-LD / og:site_name / cleaned <title> first: scraper.extract_company_name splits titles on spaces
    out["name"] = jl_home["name"] or (og.get("content", "").strip()[:90] if og else "") or title or sc.extract_company_name(soup, root)
    links = sc.discover_contact_links(soup, root)
    for path in ("contact", "contact-us"):
        if len(links) < MAX_SUBPAGES and not any(path in l.lower() for l in links):
            links.append(root + path)
    for link in links[:MAX_SUBPAGES]:
        html = fetch(link)
        if html:
            pages.append((link, html))
    emails, phones, socials, jl_all = [], [], {}, {"emails": [], "phones": [], "same_as": [], "address": ""}
    for url, html in pages:
        s = BeautifulSoup(html, "html.parser")
        emails += sc.extract_clean_emails(html, s)
        phones += sc.extract_clean_indian_phones(html, s)
        for k, v in extract_socials(html).items():
            socials.setdefault(k, v)
        jl = extract_jsonld(s)
        for k in ("emails", "phones", "same_as"):
            jl_all[k] += jl[k]
        jl_all["address"] = jl_all["address"] or jl["address"]
        if not out["address"]:
            addr = sc.extract_address(s, html)
            out["address"] = "" if addr in ("N/A", None) else addr
        out["pages"].append(url)
    for p in jl_all["phones"]:
        norm = sc.validate_and_normalize_indian_phone(p)
        if norm:
            phones.insert(0, norm)
    for link in jl_all["same_as"]:
        for k, v in extract_socials(str(link)).items():
            socials.setdefault(k, v)
    out["emails"] = _rank_emails(jl_all["emails"] + emails, se.domain_of(root))
    out["phones"] = list(dict.fromkeys(phones))[:2]
    out["address"] = (jl_all["address"] or out["address"])[:200]
    out["socials"] = socials
    out["jsonld"] = bool(jl_all["emails"] or jl_all["phones"] or jl_all["same_as"] or jl_all["address"])
    return out


# ---------------------------------------------------------------------------
# Waterfall steps that use the search engine / APIs
# ---------------------------------------------------------------------------

def _name_tokens(name: str) -> List[str]:
    stop = {"pvt", "private", "ltd", "limited", "llp", "the", "and", "india", "company", "co", "inc",
            "solutions", "services", "technologies", "technology", "infotech", "group"}
    return [t for t in re.findall(r"[a-z0-9]{3,}", (name or "").lower()) if t not in stop]


def find_website(company: str, place: str, engine: str) -> Optional[str]:
    tokens = _name_tokens(company)
    if not tokens or not se.engine_available(engine):
        return None
    try:
        hits = se.ENGINE_FUNCS[engine](f'"{company}" {place} official website', 6, "any", requests.Session())
    except (se.EngineError, requests.RequestException):
        return None
    for h in hits:
        url = h.get("url", "")
        dom = se.domain_of(url)
        if not dom or se.is_platform(url) or se._matches(dom, se.JUNK_DOMAINS):
            continue
        label = re.sub(r"[^a-z0-9]", "", dom.split(".")[0])
        if any(t in label or label in t for t in tokens):
            return site_root(url)
    return None


def zauba_lookup(company: str, engine: str) -> Dict[str, str]:
    if not REGISTERED_RE.search(company or "") or not se.engine_available(engine):
        return {}
    try:
        hits = se.ENGINE_FUNCS[engine](f'site:zaubacorp.com "{company}"', 5, "any", requests.Session())
    except (se.EngineError, requests.RequestException):
        return {}
    page = next((h["url"] for h in hits if "zaubacorp.com/company/" in h.get("url", "")), "")
    if not page:
        return {}
    html = fetch(page)
    if not html:
        return {}
    text = BeautifulSoup(html, "html.parser").get_text(" ")
    emails = [e.lower() for e in se.EMAIL_RE.findall(text) if "zaubacorp" not in e.lower()]
    cin = CIN_RE.search(text)
    return {"email": emails[0] if emails else "", "cin": cin.group(0) if cin else "", "url": page}


def hunter_lookup(domain: str) -> List[Dict[str, str]]:
    key = os.getenv("HUNTER_API_KEY", "").strip()
    if not key or not domain:
        return []
    r = requests.get("https://api.hunter.io/v2/domain-search", timeout=20,
                     params={"domain": domain, "limit": 5, "api_key": key})
    if r.status_code in (401, 403):
        raise se.EngineError(f"Hunter rejected the API key (HTTP {r.status_code})")
    if r.status_code == 429:
        raise se.EngineError("Hunter: rate limit or monthly quota reached")
    r.raise_for_status()
    out = []
    for e in ((r.json() or {}).get("data") or {}).get("emails") or []:
        name = " ".join(x for x in (e.get("first_name"), e.get("last_name")) if x)
        out.append({"email": (e.get("value") or "").lower(), "name": name, "position": e.get("position") or "",
                    "confidence": e.get("confidence") or 0})
    return [x for x in out if x["email"]]


def guess_email(domain: str) -> str:
    if not domain:
        return ""
    try:
        import email_checks
        return f"info@{domain}" if email_checks.domain_accepts_mail(domain) else ""
    except Exception:  # noqa: BLE001 - a guess is optional
        return ""


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def enrich(item: Dict[str, Any], engine: str, use_hunter: bool, place: str = "") -> Dict[str, Any]:
    steps: List[str] = []
    company = (item.get("company") or "").strip()
    if item.get("kind") == "article":
        return {"key": item.get("key") or item.get("url") or company, "website": "", "emails": [], "phones": [],
                "address": "", "socials": {}, "contacts": [], "email_guess": "", "cin": "", "company": "",
                "pages_checked": 0, "status": "none",
                "steps": ["skipped: this is a list article (e.g. 'Top 10 companies') - open it and search the companies by name"]}
    website = (item.get("website") or "").strip()
    url = (item.get("url") or "").strip()
    if not website and url and not se.is_platform(url):
        website = url
    out = {"key": item.get("key") or url or website or company, "website": "", "emails": [], "phones": [],
           "address": "", "socials": {}, "contacts": [], "email_guess": "", "cin": "", "company": "",
           "pages_checked": 0, "steps": steps, "status": "none"}

    # 1. Website
    if website:
        steps.append("website: from result")
    else:
        found = find_website(company, place, engine)
        if found:
            website = found
            steps.append(f"website: found via {se.ENGINES[engine]['name']}")
        else:
            steps.append("website: not found")
    if website:
        try:
            public_url_guard(site_root(website))
        except hcm.BlockedUrl as e:
            steps.append(f"website blocked: {e}")
            website = ""
    out["website"] = site_root(website) if website else ""

    # 2 + 3. Crawl + JSON-LD
    if out["website"]:
        crawl = crawl_site(website)
        out["pages_checked"] = len(crawl["pages"])
        if crawl["error"]:
            steps.append(f"crawl: {crawl['error']}")
        else:
            steps.append(f"crawl: {len(crawl['pages'])} page(s), {len(crawl['emails'])} email(s), {len(crawl['phones'])} phone(s)")
            if crawl.get("jsonld"):
                steps.append("json-ld: company data found")
            out.update(emails=crawl["emails"], phones=crawl["phones"], address=crawl["address"],
                       socials=crawl["socials"], company=crawl["name"])

    # 4. Zaubacorp (registered companies only)
    if not out["emails"] and REGISTERED_RE.search(company):
        z = zauba_lookup(company, engine)
        if z.get("email"):
            out["emails"] = [z["email"]]
        if z.get("cin"):
            out["cin"] = z["cin"]
        steps.append("zaubacorp: " + ("email found" if z.get("email") else ("record found" if z else "nothing found")))

    # 5. Hunter (credits)
    domain = se.domain_of(out["website"])
    if use_hunter and not out["emails"] and domain:
        try:
            people = hunter_lookup(domain)
            out["contacts"] = people
            if people:
                out["emails"] = [p["email"] for p in people[:3]]
            steps.append(f"hunter: {len(people)} email(s)")
        except (se.EngineError, requests.RequestException) as e:
            steps.append(f"hunter: {str(e)[:100]}")

    # 6. Guess (never saved as the real email)
    if not out["emails"] and domain:
        out["email_guess"] = guess_email(domain)
        if out["email_guess"]:
            steps.append("guess: info@ (not verified)")

    if out["emails"] or out["phones"]:
        out["status"] = "found"
    elif out["website"] or out["socials"]:
        out["status"] = "partial"
    return out


def deep_search(items: Any, engine: str = "auto", use_hunter: bool = False, place: str = "") -> Dict[str, Any]:
    if not isinstance(items, list) or not items:
        raise ValueError("Select at least one result")
    if len(items) > MAX_ITEMS_PER_CALL:
        raise ValueError(f"Deep search at most {MAX_ITEMS_PER_CALL} results at a time")
    clean = []
    for it in items:
        if not isinstance(it, dict) or not (it.get("url") or it.get("website") or it.get("company")):
            raise ValueError("Each result needs a link, website or company name")
        clean.append({k: str(it.get(k) or "")[:300] for k in ("key", "url", "website", "company", "kind")})
    if engine != "auto" and engine not in se.ENGINES:
        raise ValueError("Unknown search engine")
    engine = se.resolve_engine(engine)
    if use_hunter and not os.getenv("HUNTER_API_KEY", "").strip():
        raise ValueError("Hunter needs HUNTER_API_KEY in .env")
    place = re.sub(r"[^A-Za-z .'-]", "", place or "")[:60]
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        results = list(pool.map(lambda it: _safe_enrich(it, engine, use_hunter, place), clean))
    return {"results": results, "engine": engine,
            "found": sum(r["status"] == "found" for r in results)}


def _safe_enrich(item, engine, use_hunter, place):
    try:
        return enrich(item, engine, use_hunter, place)
    except Exception as e:  # noqa: BLE001 - one bad site must not fail the batch
        return {"key": item.get("key") or item.get("url") or item.get("company"), "website": "", "emails": [],
                "phones": [], "address": "", "socials": {}, "contacts": [], "email_guess": "", "cin": "",
                "company": "", "pages_checked": 0, "steps": [f"error: {e.__class__.__name__}"], "status": "error"}

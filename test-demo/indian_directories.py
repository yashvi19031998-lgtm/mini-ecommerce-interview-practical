"""Data Extraction -> Indian Directories: supplier / business listings from Indian directory portals.

Each portal has its own menu item; all share this module. Pages are read the polite way:
  - only public listing pages that the site's robots.txt allows (never search pages or APIs it disallows)
  - an honest User-Agent, the URL guard (public addresses only), the HTML cache, and a pause between requests
  - nothing hidden behind a click / login is collected (masked phone numbers stay masked)

Sources (checked live on 2026-11-12):
  indiamart       dir.indiamart.com/<city>/<category>.html or /impcat/<category>.html (search.mp is robots-disallowed)
                  -> company, IndiaMART call-forwarding phone, city, product, rating, GST verified, member since
  justdial        unavailable: returns an empty page to automated requests (bot protection we do not bypass)
  sulekha         www.sulekha.com/<category>/<city> (city required) -> JSON-LD LocalBusiness: name, locality, phone
  tradeindia      www.tradeindia.com/manufacturers/<category>.html (+ city page when listed) -> company, city, state,
                  business type, established year, certificates, product (phones are masked by TradeIndia)
  exportersindia  www.exportersindia.com/<city>/<category>.htm or /indian-suppliers/<category>.htm
                  -> company, profile, locality, years on the site, product, price (phones are behind a click)
  mlmdiary        mlmdiary.com/directory (the site's own listing feed; robots allows it; crawl-delay 5 s)
                  -> MLM COMPANIES only, aggregated from member cards. Member names / phones are personal data
                  (DPDP Act 2023) and are never collected.
"""
import json
import re
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote, urljoin

import requests
from bs4 import BeautifulSoup

import deep_search
import html_cache_manager as hcm
import maps_sources
import search_engine as se
from job_portals import ALL_INDIA, INDIAN_STATES

MAX_KEYWORDS = 5
MAX_RESULTS_PER_SOURCE = 150
CITY_RE = re.compile(r"^[A-Za-z .'-]{1,60}$")
HEADERS = dict(deep_search.HEADERS)
TIMEOUT = 30

SOURCES: Dict[str, Dict[str, Any]] = {
    "indiamart": {"name": "IndiaMART", "domain": "indiamart.com", "gap": 2.0, "needs_keyword": True,
                  "note": "Category pages (city or all India). Phones are IndiaMART call-forwarding numbers."},
    "justdial": {"name": "Justdial", "domain": "justdial.com",
                 "unavailable": "Justdial returns an empty page to automated requests (bot protection). "
                                "Getting past it would mean bypassing that protection, which this app does not do."},
    "sulekha": {"name": "Sulekha", "domain": "sulekha.com", "gap": 2.0, "needs_keyword": True, "needs_city": True,
                "pages": 2, "note": "Service providers per city, with phone numbers. Needs a city."},
    "tradeindia": {"name": "TradeIndia", "domain": "tradeindia.com", "gap": 2.0, "needs_keyword": True,
                   "note": "Manufacturer / supplier category pages. Phone numbers are hidden by TradeIndia."},
    "exportersindia": {"name": "ExportersIndia", "domain": "exportersindia.com", "gap": 2.0, "needs_keyword": True,
                       "note": "Supplier category pages (city or all India). Phones are behind a click and not collected."},
    "mlmdiary": {"name": "MLMDiary", "domain": "mlmdiary.com", "gap": 5.0, "needs_keyword": False, "pages": 3,
                 "note": "MLM companies from the MLMDiary directory (member names and phones are not collected)."},
}


class NotFound(Exception):
    """The portal has no page for this category / city."""


# ---------------------------------------------------------------------------
# Catalog + validation
# ---------------------------------------------------------------------------

def source_status(sid: str) -> str:
    return "unavailable" if SOURCES[sid].get("unavailable") else "available"


def list_sources() -> List[Dict[str, Any]]:
    return [{"id": sid, "name": s["name"], "kind": "directory", "status": source_status(sid),
             "note": s.get("note", ""), "reason": s.get("unavailable", ""), "keys": [],
             "needsKeyword": s.get("needs_keyword", True), "needsCity": s.get("needs_city", False)}
            for sid, s in SOURCES.items()]


def validate_request(data: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("Invalid request")
    sources = data.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("Select at least one source")
    for sid in sources:
        if sid not in SOURCES:
            raise ValueError(f"Unknown source: {str(sid)[:30]}")
        if source_status(sid) == "unavailable":
            raise ValueError(f"{SOURCES[sid]['name']} is not available: {SOURCES[sid]['unavailable']}")
    sources = list(dict.fromkeys(sources))
    need_kw = any(SOURCES[s].get("needs_keyword", True) for s in sources)
    keywords = maps_sources._clean_list(data.get("keywords"), "Category / product", MAX_KEYWORDS, 80, need_kw)
    audience = maps_sources._clean_list(data.get("audience"), "Target audience", 5, 60, False)
    state = data.get("state") or ALL_INDIA
    if state != ALL_INDIA and state not in INDIAN_STATES:
        raise ValueError("Unknown state")
    city = " ".join(str(data.get("city") or "").split())
    if city and not CITY_RE.match(city):
        raise ValueError("City must be letters only (max 60 characters)")
    for sid in sources:
        if SOURCES[sid].get("needs_city") and not city:
            raise ValueError(f"{SOURCES[sid]['name']} lists businesses per city - enter a city")
    return {"keywords": keywords, "audience": audience, "state": state, "city": city, "sources": sources}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def slugify(text: str) -> str:
    t = (text or "").lower().replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


def slug_variants(keyword: str) -> List[str]:
    """The portals name categories in their own way; try the obvious spellings (at most 3 requests)."""
    base = slugify(keyword)
    out = [base]
    out.append(base[:-1] if base.endswith("s") else base + "s")
    if "-" not in base:
        out.append(base + "-services")
    return [s for s in dict.fromkeys(out) if s][:3]


def _clean(text: Any, limit: int = 300) -> str:
    return " ".join(str(text or "").split())[:limit]


def make_result(source_id: str, **f: Any) -> Dict[str, Any]:
    row = {"source_id": source_id, "source": SOURCES[source_id]["name"], "company": "", "url": "", "email": "",
           "phone": "", "phone_ext": "", "phone_note": "", "website": "", "location": "", "category": "", "product": "",
           "details": "", "rating": "", "verified": "", "since": "", "kind": "listing"}
    row.update({k: (_clean(v, 600) if isinstance(v, str) else v) for k, v in f.items()})
    return row


class Fetcher:
    """One per source run: pauses between live requests to the same portal (cache hits need no pause)."""

    def __init__(self, sid: str, sleep=time.sleep, gap: Optional[float] = None):
        self.gap = gap if gap is not None else SOURCES.get(sid, {}).get("gap", 2.0)
        self.sleep = sleep
        self.last = 0.0
        self.requests = 0

    def get(self, url: str, headers: Optional[Dict[str, str]] = None) -> Tuple[int, str, str]:
        wait = self.last + self.gap - time.time()
        if self.last and wait > 0:
            self.sleep(wait)
        status, text, final_url, cached = hcm.fetch_page(url, headers or HEADERS, deep_search.public_url_guard,
                                                         timeout=TIMEOUT)
        if not cached:
            self.last = time.time()
            self.requests += 1
        return status, text, final_url


def _first_page(fetcher: Fetcher, urls: List[str], is_redirect_ok=None) -> Tuple[str, str]:
    """The first URL that is a real page (200, not redirected to a generic page). Returns (html, url)."""
    for url in urls:
        status, html, final_url = fetcher.get(url)
        moved = final_url.split("?")[0].rstrip("/") != url.split("?")[0].rstrip("/")
        if status == 200 and html and not (moved and not (is_redirect_ok and is_redirect_ok(final_url))):
            return html, url
        if status not in (200, 301, 302, 404, 410):
            raise requests.HTTPError(f"HTTP {status}")
    raise NotFound()


def _ld_items(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    out = []
    for s in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(s.string or "")
        except (ValueError, TypeError):
            continue
        for node in (data if isinstance(data, list) else data.get("@graph", [data])):
            if isinstance(node, dict):
                out.append(node)
    return out


def _embedded_json(html: str, marker: str) -> Optional[Any]:
    i = html.find(marker)
    if i < 0:
        return None
    start = html.find("{", i)
    try:
        obj, _ = json.JSONDecoder().raw_decode(html[start:])
        return obj
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Parsers (pure functions - unit tested with saved pages)
# ---------------------------------------------------------------------------

def parse_indiamart(html: str, keyword: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    state = _embedded_json(html, "window.__INITIAL_STATE__") or {}
    rows = []
    for d in state.get("data") or []:
        if not isinstance(d, dict) or not d.get("CMP"):
            continue
        # c_ct is "8047625603" or "8047625603,5093" (number, extension)
        number, _, ext = str(d.get("c_ct") or "").partition(",")
        phone, ext = re.sub(r"\D", "", number), re.sub(r"\D", "", ext)
        pns = "PNS" in str(d.get("g_cn") or "")       # IndiaMART call-forwarding (Bengaluru 080 numbers)
        if pns and len(phone) == 10 and phone.startswith("80"):
            phone = "0" + phone
        rows.append(make_result(
            "indiamart", company=d["CMP"], url=d.get("s_url") or "", phone=phone,
            phone_ext=ext if phone else "",
            phone_note=("IndiaMART call-forwarding number" + (f" - dial extension {ext}" if ext else "")) if phone and pns
            else (f"Extension {ext}" if phone and ext else ""),
            location=", ".join(x for x in OrderedDict.fromkeys([d.get("ad") or "", d.get("city") or ""]) if x),
            category=keyword, product=d.get("p_nm") or d.get("f_nm") or "",
            rating=f"{d['wt_avg']} ({d.get('tr_c') or 0} ratings)" if d.get("wt_avg") else "",
            verified="GST verified" if d.get("gst_v") else "", since=d.get("m_sn") or "",
            details=d.get("ds") or ""))
    related = [c.get("GLCAT_MCAT_NAME") for c in state.get("relCat") or [] if isinstance(c, dict) and c.get("GLCAT_MCAT_NAME")]
    return rows, related


def parse_sulekha(html: str, keyword: str) -> List[Dict[str, Any]]:
    rows = []
    for node in _ld_items(BeautifulSoup(html, "html.parser")):
        if node.get("@type") != "ItemList":
            continue
        for el in node.get("itemListElement") or []:
            b = (el or {}).get("item") or {}
            if not isinstance(b, dict) or not b.get("name"):
                continue
            a = b.get("address") or {}
            loc = ", ".join(x for x in (a.get("addressLocality"), a.get("addressRegion"), a.get("postalCode")) if x)
            rows.append(make_result("sulekha", company=b["name"], url=urljoin("https://www.sulekha.com/", b.get("url") or ""),
                                    phone=re.sub(r"[^\d+]", "", str(b.get("telephone") or "")), location=loc,
                                    category=keyword, details=(b.get("description") or "").strip('"')))
    return rows


def _tradeindia_data(html: str) -> Dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")
    tag = soup.find("script", id="__NEXT_DATA__")
    try:
        nd = json.loads(tag.string) if tag else {}
        return nd["props"]["pageProps"]["initialState"]["manufacturer"]["manufacturer_page"][
            "manufacturer_page_res"]["mcatData"] or {}
    except (ValueError, KeyError, TypeError):
        return {}


def parse_tradeindia(html: str, keyword: str) -> Tuple[List[Dict[str, Any]], List[str], Dict[str, str]]:
    m = _tradeindia_data(html)
    rows = []
    for d in (m.get("listing_data") or {}).get("listing_data") or []:
        if not isinstance(d, dict) or not d.get("co_name"):
            continue
        rows.append(make_result(
            "tradeindia", company=d["co_name"], url=urljoin("https://www.tradeindia.com/", d.get("profile_url") or ""),
            phone_note="Hidden by TradeIndia" if d.get("number_mask") else "",
            location=", ".join(x for x in (d.get("city"), d.get("state")) if x), category=keyword,
            product=d.get("product_name") or "", details=" · ".join(x for x in (
                d.get("business_type") or "", f"Est. {d['estd']}" if d.get("estd") else "", d.get("std_cert") or "",
                d.get("price") or "") if x),
            verified="TrustSEAL" if d.get("has_trust_stamp") else "",
            since=f"{d['member_since']} yrs" if d.get("member_since") else "", state=d.get("state") or ""))
    related = [r.get("keyword") for r in m.get("related_search_data") or [] if isinstance(r, dict) and r.get("keyword")]
    cities = {str(c.get("city_name", "")).lower(): urljoin("https://www.tradeindia.com/", c.get("url") or "")
              for c in m.get("list_city_data") or [] if isinstance(c, dict) and c.get("url")}
    return rows, related, cities


def parse_exportersindia(html: str, keyword: str) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for li in soup.select("ul.l3ClasFlistNew > li"):
        a = li.select_one("a.com_nam")
        if not a or not a.get_text(strip=True):
            continue
        addr = li.select_one("div._address") or li.select_one("div.gst_address")
        box = li.select_one("div.com_address")
        years = re.search(r"(\d+)\s+Years?", box.get_text(" ", strip=True)) if box else None
        prod = li.select_one("div.inDataH h2 a") or li.select_one("h2 a")
        price = li.select_one("div._price")
        rows.append(make_result(
            "exportersindia", company=a.get_text(" ", strip=True), url=urljoin("https://www.exportersindia.com/", a.get("href", "")),
            phone_note="Behind 'View Mobile' on ExportersIndia", location=addr.get_text(" ", strip=True) if addr else "",
            category=keyword, product=prod.get_text(" ", strip=True) if prod else "",
            details=(price.get("data-tooltip") or "") if price else "", since=f"{years.group(1)} yrs" if years else ""))
    return rows


def parse_mlmdiary(payload: str) -> Tuple[List[Dict[str, str]], bool]:
    """Member cards -> [{company, location, plan}] (the member's own name is dropped here). Returns (cards, has_more)."""
    try:
        data = json.loads(payload or "")
    except ValueError:
        return [], False
    soup = BeautifulSoup(data.get("html") or "", "html.parser")
    cards = []
    for card in soup.select("div.bg-white.rounded-xl.border"):
        company = loc = plan = ""
        for p in card.find_all("p"):
            icon = " ".join(p.i.get("class", [])) if p.i else ""
            text = _clean(p.get_text(" ", strip=True), 120)
            if "fa-building" in icon:
                company = text
            elif "fa-location-dot" in icon:
                loc = text
            elif "fa-diagram-project" in icon:
                plan = text
        if company and company.strip(".-").strip():
            cards.append({"company": company.strip(), "location": loc, "plan": plan})
    return cards, bool(data.get("has_more"))


def aggregate_mlm(cards: List[Dict[str, str]], keyword: str = "") -> List[Dict[str, Any]]:
    groups: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
    for c in cards:
        key = re.sub(r"[^a-z0-9]", "", c["company"].lower())
        if not key:
            continue
        g = groups.setdefault(key, {"company": c["company"], "members": 0, "cities": OrderedDict(), "plans": OrderedDict()})
        g["members"] += 1
        if c["location"]:
            g["cities"][c["location"].split(",")[0].strip()] = 1
        for p in re.split(r",\s*", c["plan"]):
            if p.strip():
                g["plans"][p.strip()] = 1
    rows = []
    for g in groups.values():
        cities, plans = list(g["cities"])[:5], list(g["plans"])[:4]
        rows.append(make_result(
            "mlmdiary", company=g["company"], url=f"https://mlmdiary.com/directory?country=India&company={quote(g['company'])}",
            location=", ".join(cities), category=keyword or "MLM company", product=", ".join(plans),
            details=f"{g['members']} member{'s' if g['members'] != 1 else ''} listed on MLMDiary"
                    + (f" in {', '.join(cities)}" if cities else "") + (f". Plans: {', '.join(plans)}" if plans else ""),
            members=g["members"]))
    rows.sort(key=lambda r: -r["members"])
    return rows


# ---------------------------------------------------------------------------
# Source runs
# ---------------------------------------------------------------------------

def _city_slug(city: str) -> str:
    return slugify(city)


def run_indiamart(f: Fetcher, kw: str, req: Dict[str, Any], notes: List[str]) -> List[Dict[str, Any]]:
    city = _city_slug(req["city"])
    urls = []
    for s in slug_variants(kw):
        urls.append(f"https://dir.indiamart.com/{city}/{s}.html" if city else f"https://dir.indiamart.com/impcat/{s}.html")
    html, _ = _first_page(f, urls)
    rows, related = parse_indiamart(html, kw)
    if not rows and related:
        notes.append(f"{kw}: IndiaMART has no listings here - related categories: {', '.join(related[:6])}")
    return rows


def run_sulekha(f: Fetcher, kw: str, req: Dict[str, Any], notes: List[str]) -> List[Dict[str, Any]]:
    city = _city_slug(req["city"])
    html, url = _first_page(f, [f"https://www.sulekha.com/{s}/{city}" for s in slug_variants(kw)])
    rows = parse_sulekha(html, kw)
    for page in range(2, SOURCES["sulekha"]["pages"] + 1):
        if len(rows) < 20 * (page - 1):
            break
        status, more, _ = f.get(f"{url}?page={page}")
        new = parse_sulekha(more, kw) if status == 200 else []
        seen = {r["url"] for r in rows}
        new = [r for r in new if r["url"] not in seen]
        if not new:
            break
        rows += new
    return rows


def run_tradeindia(f: Fetcher, kw: str, req: Dict[str, Any], notes: List[str]) -> List[Dict[str, Any]]:
    urls = [f"https://www.tradeindia.com/manufacturers/{s}.html" for s in slug_variants(kw)]
    html, _ = _first_page(f, urls)
    rows, related, cities = parse_tradeindia(html, kw)
    if req["city"]:
        city = req["city"].lower()
        city_rows = []
        if cities.get(city):                      # TradeIndia has a page for this city
            status, chtml, _ = f.get(cities[city])
            if status == 200:
                city_rows, _, _ = parse_tradeindia(chtml, kw)
        rows = city_rows or [r for r in rows if city in r["location"].lower()]
        if not rows:
            notes.append(f"{kw}: TradeIndia lists no {kw} supplier in {req['city']} on its category page")
    elif req["state"] != ALL_INDIA:
        rows = [r for r in rows if r.get("state", "").lower() == req["state"].lower()]
    if not rows and related:
        notes.append(f"{kw}: related TradeIndia categories: {', '.join(related[:6])}")
    return rows


def run_exportersindia(f: Fetcher, kw: str, req: Dict[str, Any], notes: List[str]) -> List[Dict[str, Any]]:
    city = _city_slug(req["city"])
    urls = [f"https://www.exportersindia.com/{city}/{s}.htm" if city else f"https://www.exportersindia.com/indian-suppliers/{s}.htm"
            for s in slug_variants(kw)]
    html, _ = _first_page(f, urls)
    rows = parse_exportersindia(html, kw)
    if not city and req["state"] != ALL_INDIA:
        rows = [r for r in rows if req["state"].lower() in r["location"].lower()]
    return rows


def run_mlmdiary(f: Fetcher, kw: str, req: Dict[str, Any], notes: List[str]) -> List[Dict[str, Any]]:
    params = "country=India"
    if req["state"] != ALL_INDIA:
        params += f"&state={quote(req['state'])}"
    if req["city"]:
        params += f"&city={quote(req['city'])}"
    headers = dict(HEADERS, Accept="application/json", **{"X-Requested-With": "XMLHttpRequest"})
    cards = []
    for page in range(1, SOURCES["mlmdiary"]["pages"] + 1):
        status, payload, _ = f.get(f"https://mlmdiary.com/directory?{params}&page={page}", headers)
        if status != 200:
            if page == 1:
                raise requests.HTTPError(f"HTTP {status}")
            break
        got, more = parse_mlmdiary(payload)
        cards += got
        if not more:
            break
    rows = aggregate_mlm(cards, kw)
    if kw:
        rows = [r for r in rows if kw.lower() in f"{r['company']} {r['product']}".lower()]
    return rows


RUNNERS = {"indiamart": run_indiamart, "sulekha": run_sulekha, "tradeindia": run_tradeindia,
           "exportersindia": run_exportersindia, "mlmdiary": run_mlmdiary}


def _run_source(sid: str, req: Dict[str, Any], sleep=time.sleep) -> Dict[str, Any]:
    t0, rows, errors, notes = time.time(), [], [], []
    f = Fetcher(sid, sleep)
    keywords = req["keywords"] or ([""] if not SOURCES[sid].get("needs_keyword", True) else [])
    for kw in keywords:
        try:
            rows += RUNNERS[sid](f, kw, req, notes)
        except NotFound:
            errors.append(f"{kw}: {SOURCES[sid]['name']} has no category page named '{kw}'"
                          + (f" in {req['city']}" if req["city"] and sid != "tradeindia" else "")
                          + " - try the name the site uses (e.g. 'bakery products', 'interior designers decorators')")
        except hcm.BlockedUrl as e:
            errors.append(f"{kw}: blocked URL ({e})")
        except requests.Timeout:
            errors.append(f"{kw}: {SOURCES[sid]['name']} did not answer in time - try again later")
        except requests.ConnectionError:
            errors.append(f"{kw}: could not reach {SOURCES[sid]['name']} - check the internet connection")
        except Exception as e:  # noqa: BLE001 - one source must never fail the whole search
            errors.append(f"{kw}: {e.__class__.__name__}: {str(e)[:120]}")
    if req["audience"] and rows:
        words = [w for a in req["audience"] for w in re.findall(r"[a-z0-9]{3,}", a.lower())]
        kept = [r for r in rows if any(w in f"{r['company']} {r['product']} {r['details']} {r['category']}".lower() for w in words)]
        if kept:
            rows = kept
        else:
            notes.append("No listing mentions the target audience - showing all")
    status = "error" if errors and not rows and len(errors) >= max(1, len(keywords)) else "ok"
    return {"rows": rows, "status": status, "errors": errors + notes, "seconds": round(time.time() - t0, 1),
            "requests": f.requests}


def search(data: Dict[str, Any], sleep=time.sleep) -> Dict[str, Any]:
    req = validate_request(data)
    with ThreadPoolExecutor(max_workers=len(req["sources"])) as pool:   # different portals in parallel
        runs = dict(zip(req["sources"], pool.map(lambda sid: _run_source(sid, req, sleep), req["sources"])))
    results, statuses, seen = [], {}, {}
    for sid in req["sources"]:
        count = 0
        for r in runs[sid]["rows"]:
            key = (sid, re.sub(r"[^a-z0-9]", "", r["company"].lower()), r["location"].split(",")[0].lower())
            if key in seen:                               # same company under two keywords: merge the product
                kept = seen[key]
                if r["product"] and r["product"] not in kept["product"]:
                    kept["product"] = _clean(f"{kept['product']}; {r['product']}", 300)
                for fld in ("phone", "url", "rating", "verified", "since"):
                    if not kept.get(fld) and r.get(fld):
                        kept[fld] = r[fld]
                continue
            if count >= MAX_RESULTS_PER_SOURCE:
                continue
            seen[key] = r
            results.append(r)
            count += 1
        statuses[sid] = {"name": SOURCES[sid]["name"], "status": runs[sid]["status"], "count": count,
                         "seconds": runs[sid]["seconds"], "errors": runs[sid]["errors"]}
    results.sort(key=lambda r: (not r["phone"], r["company"].lower()))
    return {"query": {k: req[k] for k in ("keywords", "audience", "state", "city")},
            "results": results, "total": len(results), "sources": statuses}


def result_to_raw_lead(r: Dict[str, Any]) -> Dict[str, str]:
    sid = r.get("source_id", "")
    name = SOURCES.get(sid, {}).get("name", "Indian Directory")
    details = [f"Listed on {name}: {r.get('url', '')}"]
    for label, key in (("Product", "product"), ("Category", "category"), ("Rating", "rating"),
                       ("Verified", "verified"), ("On the site for", "since"), ("Details", "details")):
        if r.get(key):
            details.append(f"{label}: {r[key]}")
    if r.get("phone_note") and r.get("phone"):
        details.append(f"Phone: {r['phone_note']}")
    website = r.get("website", "")
    if website and se.is_platform(website):
        website = ""
    return {
        "company_name": r.get("company", ""),
        "email": r.get("email", ""),
        "mobile_number": r.get("phone", ""),
        "website": website,
        "location": r.get("location", ""),
        "description": ". ".join(details)[:800],
        "source": f"Indian Directories ({name})",
        "source_url": r.get("url", ""),
        "lead_type": "MLM Company" if sid == "mlmdiary" else "Directory Listing (B2B / services)",
    }

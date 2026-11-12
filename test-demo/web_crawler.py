"""Web Crawler: four tools that read websites the user names.

  site_crawl     crawl one or more websites (same site only, depth + page limit) -> contacts per page and per site
  harvest_links  read list pages (member lists, exhibitor lists, "top companies" articles) -> the outside company
                 websites they link to (then Bulk Website Contacts finds their contacts)
  find_keywords  crawl a site and report the pages that mention given words, with a snippet
  sitemap        read a site's sitemap(s) -> every listed page with its last-modified date

Rules for every request: robots.txt is obeyed (robots_policy), robots crawl-delay is honoured (at least 1 s between
pages of the same site), the URL guard allows public addresses only, pages go through the HTML cache, an honest
User-Agent is sent, and each request is limited in pages and time.
"""
import re
import time
from collections import Counter, OrderedDict, deque
from html import unescape
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import urldefrag, urljoin, urlparse

from bs4 import BeautifulSoup

import deep_search
import html_cache_manager as hcm
import robots_policy
import search_engine as se

MAX_SEEDS = 5
PAGE_CHOICES = (10, 25, 50)
DEPTH_CHOICES = (1, 2, 3)
MAX_KEYWORDS = 10
TIME_BUDGET = 90.0                      # seconds per request (the web proxy allows 120)
MAX_SITEMAP_URLS = 5000
MAX_CHILD_SITEMAPS = 10
SKIP_EXT = re.compile(r"\.(jpe?g|png|gif|webp|svg|ico|bmp|pdf|zip|rar|7z|gz|tar|mp4|mp3|avi|mov|wmv|webm|css|js|json|xml|"
                      r"woff2?|ttf|eot|docx?|xlsx?|pptx?|csv|apk|exe|dmg)$", re.I)
NOISE_HOSTS = {"w3.org", "schema.org", "wordpress.org", "wordpress.com", "wp.com", "gravatar.com", "googleapis.com",
               "gstatic.com", "google-analytics.com", "googletagmanager.com", "doubleclick.net", "cloudflare.com",
               "jsdelivr.net", "cdnjs.com", "bootstrapcdn.com", "jquery.com", "fontawesome.com", "bit.ly", "goo.gl",
               "t.co", "tinyurl.com", "wa.me", "whatsapp.com", "addthis.com", "sharethis.com", "creativecommons.org",
               "apple.com", "play.google.com", "maps.google.com", "goo.gle", "g.page", "youtu.be"}
GENERIC_ANCHORS = {"", "click here", "here", "website", "visit website", "visit", "read more", "more", "link", "view",
                   "view website", "www", "home", "learn more", "know more", "details", "view details"}
NEXT_RE = re.compile(r"^\s*(next|next page|›|»|>|older posts?)\s*$", re.I)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _urls(values: Any, label: str = "website", max_items: int = MAX_SEEDS) -> List[str]:
    if isinstance(values, str):
        values = re.split(r"[\s,]+", values)
    if not isinstance(values, list):
        raise ValueError(f"Enter at least one {label}")
    out = []
    for v in values:
        v = str(v or "").strip()
        if not v:
            continue
        if not v.startswith(("http://", "https://")):
            v = "https://" + v
        host = se.domain_of(v)
        if len(v) > 500 or not host or "." not in host:
            raise ValueError(f"Not a web address: {v[:60]}")
        out.append(urldefrag(v)[0])
    out = list(dict.fromkeys(out))
    if not out:
        raise ValueError(f"Enter at least one {label}")
    if len(out) > max_items:
        raise ValueError(f"At most {max_items} {label}s per run")
    return out


def _choice(v: Any, choices: Tuple[int, ...], label: str) -> int:
    if v not in choices:
        raise ValueError(f"Unknown {label}")
    return v


def _keywords(values: Any) -> List[str]:
    if isinstance(values, str):
        values = values.split(",")
    if not isinstance(values, list):
        raise ValueError("Enter at least one keyword")
    out = list(dict.fromkeys(" ".join(str(v).split()).lower() for v in values if str(v).strip()))
    if not out:
        raise ValueError("Enter at least one keyword")
    if len(out) > MAX_KEYWORDS:
        raise ValueError(f"At most {MAX_KEYWORDS} keywords")
    if any(len(k) > 60 or len(k) < 2 for k in out):
        raise ValueError("Each keyword must be 2-60 characters")
    return out


# ---------------------------------------------------------------------------
# Fetching (robots + guard + cache + per-site pause)
# ---------------------------------------------------------------------------

class Session:
    def __init__(self, sleep: Callable[[float], None] = time.sleep, clock: Callable[[], float] = time.time,
                 budget: float = TIME_BUDGET):
        self.sleep, self.clock = sleep, clock
        self.start, self.budget = clock(), budget
        self.last: Dict[str, float] = {}
        self.blocked = 0          # robots.txt said no
        self.failed = 0
        self.fetched = 0

    def out_of_time(self) -> bool:
        return self.clock() - self.start > self.budget

    def get(self, url: str) -> Tuple[int, str, str]:
        """-> (status, html, final_url); status 0 = not fetched (robots / blocked / error)."""
        if not robots_policy.allowed(url):
            self.blocked += 1
            return 0, "", url
        host = se.domain_of(url)
        gap = robots_policy.crawl_delay(url)
        wait = self.last.get(host, 0) + gap - self.clock()
        if host in self.last and wait > 0:
            self.sleep(wait)
        try:
            status, html, final, cached = hcm.fetch_page(url, deep_search.HEADERS, deep_search.public_url_guard,
                                                         timeout=deep_search.PAGE_TIMEOUT)
        except Exception:  # noqa: BLE001 - guard / network / bad response: counted, never fatal
            self.failed += 1
            return 0, "", url
        if not cached:
            self.last[host] = self.clock()
            self.fetched += 1
        if status != 200:
            self.failed += 1
        return status, html if status == 200 else "", final


def page_key(url: str) -> str:
    """www / no-www, http / https and a trailing slash are the same page."""
    p = urlparse(url)
    host = (p.hostname or "").lower()
    host = host[4:] if host.startswith("www.") else host
    return f"{host}{p.path.rstrip('/') or '/'}{'?' + p.query if p.query else ''}"


def same_site(url: str, root_host: str) -> bool:
    h = se.domain_of(url)
    return h == root_host or h.endswith("." + root_host)


def page_links(html: str, base: str) -> List[Tuple[str, str]]:
    """-> [(absolute url without #fragment, anchor text)] for http(s) links to pages (no files / mailto / js)."""
    soup = BeautifulSoup(html or "", "html.parser")
    out, seen = [], set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith(("mailto:", "tel:", "javascript:", "#", "data:")):
            continue
        url = urldefrag(urljoin(base, href))[0]
        p = urlparse(url)
        if p.scheme not in ("http", "https") or not p.netloc or SKIP_EXT.search(p.path):
            continue
        if url not in seen:
            seen.add(url)
            out.append((url, " ".join(a.get_text(" ", strip=True).split())[:120]))
    return out


def page_contacts(html: str) -> Dict[str, Any]:
    """Emails / phones (visible text + tel: links only) / socials / title of one page."""
    sc = deep_search._scraper()
    soup = BeautifulSoup(html or "", "html.parser")
    jl = deep_search.extract_jsonld(soup)
    emails = list(dict.fromkeys(jl["emails"] + sc.extract_clean_emails(html, soup)))
    phones = [sc.validate_and_normalize_indian_phone(p) for p in jl["phones"]]
    phones = list(dict.fromkeys([p for p in phones if p] + sc.extract_clean_indian_phones(deep_search.visible_text(soup), soup)))
    title = se.clean_title(soup.title.get_text()) if soup.title else ""
    og = soup.find("meta", property="og:site_name")
    name = jl.get("name") or (og.get("content", "").strip() if og else "")
    return {"title": title[:150], "name": name[:90], "emails": emails[:10], "phones": phones[:10],
            "socials": deep_search.extract_socials(html)}


def _crawl(seeds: List[str], max_pages: int, depth: int, s: Session,
           priority: Optional[Callable[[str, str], bool]] = None) -> List[Dict[str, Any]]:
    """Breadth-first over each seed's own site. priority(url, anchor) puts matching links first."""
    pages: List[Dict[str, Any]] = []
    per_site = max(1, max_pages // len(seeds))
    for seed in seeds:
        host = se.domain_of(seed)
        queue, seen, count = deque([(seed, 0)]), {page_key(seed)}, 0
        while queue and count < per_site and not s.out_of_time():
            url, d = queue.popleft()
            status, html, final = s.get(url)
            count += 1
            seen.add(page_key(final or url))                     # redirect target counts as seen too
            pages.append({"url": url, "final": final, "depth": d, "status": status, "html": html, "site": host})
            if not html or d >= depth:
                continue
            links, batch = [], set()
            for u, t in page_links(html, final or url):
                k = page_key(u)
                if same_site(u, host) and k not in seen and k not in batch:
                    batch.add(k)
                    links.append((u, t))
            if priority:
                links.sort(key=lambda x: not priority(*x))
                urgent = [(u, d + 1) for u, t in links if priority(u, t)]
                rest = [(u, d + 1) for u, t in links if not priority(u, t)]
                queue = deque(urgent + list(queue) + rest)
            else:
                queue.extend((u, d + 1) for u, _ in links)
            seen.update(batch)
    return pages


def _summary(s: Session, pages: int) -> Dict[str, Any]:
    notes = []
    if s.blocked:
        notes.append(f"{s.blocked} page(s) skipped: the site's robots.txt does not allow them")
    if s.failed:
        notes.append(f"{s.failed} page(s) could not be opened")
    if s.out_of_time():
        notes.append(f"Stopped after {int(s.budget)} s to keep the request short - run again for more (pages are cached)")
    return {"pages": pages, "fetched": s.fetched, "blocked": s.blocked, "failed": s.failed, "notes": notes}


# ---------------------------------------------------------------------------
# 1. Site crawler
# ---------------------------------------------------------------------------

def site_crawl(data: Dict[str, Any], session: Optional[Session] = None) -> Dict[str, Any]:
    seeds = _urls(data.get("urls"))
    max_pages = _choice(data.get("max_pages", 25), PAGE_CHOICES, "page limit")
    depth = _choice(data.get("depth", 2), DEPTH_CHOICES, "depth")
    s = session or Session()
    crawled = _crawl(seeds, max_pages, depth, s)
    rows, sites = [], OrderedDict()
    for p in crawled:
        c = page_contacts(p["html"]) if p["html"] else {"title": "", "name": "", "emails": [], "phones": [], "socials": {}}
        rows.append({"site": p["site"], "url": p["url"], "depth": p["depth"],
                     "status": "ok" if p["html"] else ("robots" if p["status"] == 0 else f"HTTP {p['status']}"), **c})
        agg = sites.setdefault(p["site"], {"site": p["site"], "website": deep_search.site_root(p["url"]), "company": "",
                                           "emails": [], "phones": [], "socials": {}, "pages": 0, "address": ""})
        agg["pages"] += 1
        agg["company"] = agg["company"] or c["name"]                  # the site's own name (JSON-LD / og:site_name)
        agg.setdefault("title", c["title"])
        agg["emails"] = list(dict.fromkeys(agg["emails"] + c["emails"]))[:10]
        agg["phones"] = list(dict.fromkeys(agg["phones"] + c["phones"]))[:10]
        for k, v in c["socials"].items():
            agg["socials"].setdefault(k, v)
    for a in sites.values():
        a.update(domain=a["site"], status="found" if a["emails"] or a["phones"] else "none",
                 company=a["company"] or a.pop("title", "") or a["site"])
        a.pop("title", None)
    return {"results": rows, "sites": list(sites.values()), **_summary(s, len(rows))}


# ---------------------------------------------------------------------------
# 2. Link harvester
# ---------------------------------------------------------------------------

def _good_anchor(text: str) -> bool:
    t = text.strip().lower()
    return bool(t) and t not in GENERIC_ANCHORS and not t.startswith(("http", "www.")) and len(t) <= 80


def harvest_links(data: Dict[str, Any], session: Optional[Session] = None) -> Dict[str, Any]:
    seeds = _urls(data.get("urls"), "list page")
    follow = _choice(data.get("follow_pages", 1), (1, 2, 3, 5), "number of pages to follow")
    s = session or Session()
    found: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
    read = 0
    for seed in seeds:
        host, url = se.domain_of(seed), seed
        for _ in range(follow):
            if not url or s.out_of_time():
                break
            status, html, final = s.get(url)
            read += 1
            if not html:
                break
            nxt = None
            for link, text in page_links(html, final or url):
                d = se.domain_of(link)
                if same_site(link, host):
                    if not nxt and NEXT_RE.match(text):
                        nxt = link
                    continue
                if not d or se._matches(d, se.JUNK_DOMAINS) or se._matches(d, NOISE_HOSTS) or se.is_platform(link):
                    continue
                row = found.setdefault(d, {"domain": d, "website": deep_search.site_root(link), "company": "",
                                           "anchors": [], "found_on": url, "links": 0, "government": deep_search.is_government(link)})
                row["links"] += 1
                if _good_anchor(text) and text not in row["anchors"]:
                    row["anchors"].append(text)
                    row["company"] = row["company"] or text
            url = nxt
    rows = list(found.values())
    for r in rows:
        r["anchors"] = r["anchors"][:3]
        r["company"] = r["company"] or r["domain"]
    return {"results": rows, **_summary(s, read)}


# ---------------------------------------------------------------------------
# 3. Keyword page finder
# ---------------------------------------------------------------------------

def snippets(text: str, kw: str, limit: int = 2, width: int = 80) -> Tuple[int, List[str]]:
    pat = re.compile(rf"(?<![a-z0-9]){re.escape(kw)}(?![a-z0-9])", re.I)
    hits = list(pat.finditer(text))
    out = []
    for m in hits[:limit]:
        a, b = max(0, m.start() - width), min(len(text), m.end() + width)
        out.append(("…" if a else "") + text[a:b].strip() + ("…" if b < len(text) else ""))
    return len(hits), out


def find_keywords(data: Dict[str, Any], session: Optional[Session] = None) -> Dict[str, Any]:
    seeds = _urls(data.get("urls"), "website", 3)
    kws = _keywords(data.get("keywords"))
    max_pages = _choice(data.get("max_pages", 25), PAGE_CHOICES, "page limit")
    depth = _choice(data.get("depth", 2), DEPTH_CHOICES, "depth")
    s = session or Session()
    slugs = [re.sub(r"[^a-z0-9]+", "-", k).strip("-") for k in kws]
    prio = lambda url, text: any(k in text.lower() for k in kws) or any(sl and sl in url.lower() for sl in slugs)  # noqa: E731
    crawled = _crawl(seeds, max_pages, depth, s, priority=prio)
    rows, pages_with = [], set()
    for p in crawled:
        if not p["html"]:
            continue
        soup = BeautifulSoup(p["html"], "html.parser")
        text = " ".join(deep_search.visible_text(soup).split())
        title = se.clean_title(soup.title.get_text()) if soup.title else ""
        for k, sl in zip(kws, slugs):
            n, snips = snippets(text, k)
            in_url = bool(sl) and sl in p["url"].lower()
            if n or in_url:
                pages_with.add(p["url"])
                rows.append({"site": p["site"], "url": p["url"], "title": title[:150], "keyword": k, "count": n,
                             "snippets": snips, "in_url": in_url})
    rows.sort(key=lambda r: (-r["count"], r["url"]))
    per_kw = Counter(r["keyword"] for r in rows)
    return {"results": rows, "keywords": {k: per_kw.get(k, 0) for k in kws}, "matched_pages": len(pages_with),
            **_summary(s, len(crawled))}


# ---------------------------------------------------------------------------
# 4. Sitemap explorer
# ---------------------------------------------------------------------------

LOC_RE = re.compile(r"<loc>\s*(.*?)\s*</loc>", re.I | re.S)
URL_BLOCK_RE = re.compile(r"<url>(.*?)</url>", re.I | re.S)
TAG_RE = {t: re.compile(rf"<{t}>\s*(.*?)\s*</{t}>", re.I | re.S) for t in ("lastmod", "changefreq", "priority")}


def parse_sitemap(xml: str) -> Tuple[str, List[Dict[str, str]]]:
    """-> ("index", [{"loc"}]) | ("urlset", [{"loc", "lastmod", "changefreq", "priority"}]) | ("", []).
    Regex, not an XML parser: no entity expansion, tolerant of sloppy files."""
    head = (xml or "")[:2000].lower()
    if "<sitemapindex" in head:
        return "index", [{"loc": unescape(m)} for m in LOC_RE.findall(xml)]
    if "<urlset" in head:
        out = []
        for block in URL_BLOCK_RE.findall(xml):
            loc = LOC_RE.search(block)
            if not loc:
                continue
            row = {"loc": unescape(loc.group(1))}
            for t, rx in TAG_RE.items():
                m = rx.search(block)
                row[t] = m.group(1).strip() if m else ""
            out.append(row)
            if len(out) >= MAX_SITEMAP_URLS:
                break
        return "urlset", out
    return "", []


def sitemap(data: Dict[str, Any], session: Optional[Session] = None) -> Dict[str, Any]:
    site = _urls(data.get("urls"), "website", 1)[0]
    root = deep_search.site_root(site).rstrip("/")
    s = session or Session()
    defaults = [f"{root}/sitemap.xml", f"{root}/sitemap_index.xml", f"{root}/wp-sitemap.xml"]
    candidates = list(dict.fromkeys(robots_policy.sitemaps(root) + defaults))
    rows: List[Dict[str, str]] = []
    read, notes, queue, seen = [], [], deque(candidates), set()
    children = 0
    while queue and len(rows) < MAX_SITEMAP_URLS and not s.out_of_time():
        sm = queue.popleft()
        if sm in seen:
            continue
        seen.add(sm)
        if sm.lower().endswith(".gz"):
            notes.append(f"Skipped compressed sitemap {sm} (open it in a browser to read)")
            continue
        failed_before = s.failed
        status, xml, _ = s.get(sm)
        if status == 404 and sm in defaults:
            s.failed = failed_before                               # a missing default name is not an error
        kind, items = parse_sitemap(xml)
        if not kind:
            continue
        read.append(sm)
        queue = deque(x for x in queue if x not in defaults)    # found one: the other default names are not needed
        if kind == "index":
            for it in items:
                if children < MAX_CHILD_SITEMAPS and same_site(it["loc"], se.domain_of(root)):
                    queue.append(it["loc"])
                    children += 1
            if len(items) > MAX_CHILD_SITEMAPS:
                notes.append(f"Read the first {MAX_CHILD_SITEMAPS} of {len(items)} sitemaps in the index")
            continue
        for it in items:
            p = urlparse(it["loc"])
            section = (p.path.strip("/").split("/") or [""])[0] or "(home)"
            rows.append({**it, "url": it.pop("loc"), "section": section[:60]})
    rows = list({r["url"]: r for r in rows}.values())[:MAX_SITEMAP_URLS]
    if not read:
        notes.append("No sitemap found (robots.txt, /sitemap.xml, /sitemap_index.xml and /wp-sitemap.xml were tried)")
    sections = Counter(r["section"] for r in rows).most_common(15)
    dated = sorted((r for r in rows if r.get("lastmod")), key=lambda r: r["lastmod"], reverse=True)
    summary = _summary(s, len(read))
    summary["notes"] = notes + summary["notes"]
    return {"results": rows, "sitemaps": read, "sections": [{"section": k, "pages": v} for k, v in sections],
            "newest": dated[0]["lastmod"] if dated else "", "oldest": dated[-1]["lastmod"] if dated else "", **summary}

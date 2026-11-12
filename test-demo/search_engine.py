"""Scraping / Mining -> Search Engines.

Builds ready-made search queries ("dorks") from a keyword + place, runs them on a search engine and
returns company / listing results that can be deep-searched (deep_search.py) and saved as leads.

Engines:
  brave       Brave Search API      BRAVE_SEARCH_API_KEY  ($5 free credit/month ~ 1,000 searches; card required)
  serper      Serper.dev (Google)   SERPER_API_KEY        (free starter credits)
  searxng     your own SearXNG      SEARXNG_URL           (no key: open-source metasearch you run yourself, e.g. Docker)
  duckduckgo  DuckDuckGo            no key - best effort: often returns nothing for site: / quoted queries
  auto        Brave, Serper, SearXNG - the first one that is set up - else DuckDuckGo

Fallback: a query that fails on one engine (rate limit, no credits, bad key, not running) is retried on the next
engine that is set up, in the order Brave -> Serper -> SearXNG -> DuckDuckGo (see run_with_fallback).
Rate limits: queries run one after another with a gap; when every engine is rate limited the search stops and
returns what it already found, with a message. We never rotate identities or bypass bot checks.
"""
import os
import functools
import re
import threading
import time
import warnings
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests

from job_portals import ALL_INDIA, INDIAN_STATES

warnings.filterwarnings("ignore", message=".*renamed to `ddgs`.*")
try:
    from duckduckgo_search import DDGS
    from duckduckgo_search.exceptions import DuckDuckGoSearchException, RatelimitException
except ImportError:  # pragma: no cover - optional dependency
    DDGS = None
    DuckDuckGoSearchException = RatelimitException = Exception

MAX_KEYWORDS = 5
MAX_AUDIENCE = 5
MAX_AUDIENCE_LEN = 60
MAX_LEN = 80
MAX_RESULTS_CHOICES = (10, 25, 50, 100)
MAX_EXCLUDES = 10
MAX_CUSTOM_LEN = 300
TIMEOUT = 20
GAP_SECONDS = {"brave": 1.1, "serper": 0.3, "searxng": 1.5, "duckduckgo": 2.0}
TIME_FILTERS = {"any": None, "day": "d", "week": "w", "month": "m", "year": "y"}
CITY_RE = re.compile(r"^[A-Za-z .'-]{1,60}$")
SITE_RE = re.compile(r"^[a-z0-9.-]+\.[a-z]{2,}(/[\w./-]*)?$")

ENGINES = {
    "brave": {"name": "Brave Search", "short": "Brave Search", "key": "BRAVE_SEARCH_API_KEY", "url": "https://api-dashboard.search.brave.com/app/keys",
              "note": "$5 free credit every month (about 1,000 searches); a payment card is required; supports site: and quotes"},
    "serper": {"name": "Serper.dev (Google results)", "short": "Serper - Google", "key": "SERPER_API_KEY", "url": "https://serper.dev/api-key",
               "note": "Google results; free starter credits, then paid"},
    "searxng": {"name": "SearXNG (self-hosted, no key)", "short": "SearXNG", "key": "SEARXNG_URL",
                "url": "https://docs.searxng.org/admin/installation-docker.html",
                "note": "Free, no key: your own SearXNG server (Docker); set SEARXNG_URL, e.g. http://localhost:8888"},
    "duckduckgo": {"name": "DuckDuckGo (no key)", "short": "DuckDuckGo", "key": None, "url": "https://duckduckgo.com",
                   "note": "Free, best effort - site: and quoted queries often return nothing"},
}

# {kw} = keyword, {loc} = city / state / India
MODES = {
    "companies": {"name": "Companies & websites",
                  "help": "Business websites for the keyword in the place.",
                  "queries": ['"{kw}" company {loc}', '{kw} services {loc} "contact us"']},
    "contacts": {"name": "Contact pages (email / phone)",
                 "help": "Pages that show an email address or phone number.",
                 "queries": ['"{kw}" {loc} "contact us" email', '"{kw}" {loc} "@gmail.com" OR "+91"']},
    "b2b": {"name": "B2B portals (IndiaMART, TradeIndia, ExportersIndia)",
            "help": "Supplier listings from B2B portals, found through the search engine.",
            "queries": ['site:indiamart.com "{kw}" {loc}', 'site:tradeindia.com "{kw}" {loc}',
                        'site:exportersindia.com "{kw}" {loc}']},
    "linkedin": {"name": "LinkedIn company pages",
                 "help": "Company pages on LinkedIn (name + link; use Deep Search to find the website).",
                 "queries": ['site:linkedin.com/company "{kw}" {loc}']},
    "intent": {"name": "Buyer intent (looking for / hiring)",
               "help": "Posts from people or companies looking for this service.",
               "queries": ['"looking for" "{kw}" {loc}', '"need a" "{kw}" {loc}',
                           'site:reddit.com/r/forhire "hiring" "{kw}"', 'site:upwork.com/freelance-jobs "{kw}"']},
    "tenders": {"name": "Tenders & RFPs (government)",
                "help": "Government tenders / requests for proposal.",
                "queries": ['"{kw}" tender {loc} site:gov.in', '"request for proposal" "{kw}" {loc}']},
    "custom": {"name": "Custom query",
               "help": "Write your own query. {keyword} and {city} are replaced for each keyword.",
               "queries": []},
}

# Result domains that are listings on a platform, not the company's own website.
PLATFORM_DOMAINS = {
    "linkedin.com", "indiamart.com", "tradeindia.com", "exportersindia.com", "justdial.com", "sulekha.com",
    "facebook.com", "instagram.com", "twitter.com", "x.com", "youtube.com", "reddit.com", "upwork.com",
    "fiverr.com", "freelancer.com", "clutch.co", "goodfirms.co", "ambitionbox.com", "glassdoor.com",
    "glassdoor.co.in", "naukri.com", "indeed.com", "zaubacorp.com", "tofler.in", "crunchbase.com",
    "yellowpages.in", "quora.com", "medium.com", "github.com", "eprocure.gov.in", "gem.gov.in",
    "mlmdiary.com",
}
# Never useful as a lead.
JUNK_DOMAINS = {
    "wikipedia.org", "merriam-webster.com", "cambridge.org", "dictionary.com", "thesaurus.com",
    "collinsdictionary.com", "britannica.com", "imdb.com", "netflix.com", "pinterest.com", "google.com",
    "bing.com", "duckduckgo.com", "search.brave.com", "play.google.com", "apps.apple.com", "msn.com",
    "w3schools.com", "geeksforgeeks.org", "tutorialspoint.com", "vocabulary.com", "microsoft.com", "apple.com",
    "amazon.com", "softonic.com", "igetintopc.com", "computerhope.com", "simplilearn.com", "stackoverflow.com",
    "openai.com", "chatgpt.com", "investopedia.com", "techtarget.com", "ibm.com", "javatpoint.com",
}
# "Top 10 IT companies in Ahmedabad" pages list many companies - they are not one company's website.
ARTICLE_RE = re.compile(r"^\s*(top|best)\s+\d+\b|\b(top|best)\s+\d+\s+\w+|\blist of\b|\branking\b|\bcompanies in\b", re.I)
TITLE_SUFFIX_RE = re.compile(
    r"\s*[\|\-–—:]\s*(LinkedIn|IndiaMART|Indiamart|TradeIndia|Tradeindia|ExportersIndia|Facebook|Instagram|"
    r"Justdial|Reddit|Upwork|YouTube|Home|Official Website|Contact Us|About Us)\b.*$", re.I)
EMAIL_RE = re.compile(r"\b[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)*\.[a-zA-Z]{2,}\b")
PHONE_RE = re.compile(r"(?:\+91[\s-]?|\b0)?[6-9]\d{4}[\s-]?\d{5}\b")


class EngineError(Exception):
    """An engine could not answer (missing key, rejected, network)."""


class RateLimited(EngineError):
    """The engine asked us to slow down."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def domain_of(url: str) -> str:
    host = (urlparse(url or "").hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def _matches(domain: str, domains) -> bool:
    return any(domain == d or domain.endswith("." + d) for d in domains)


def is_platform(url: str) -> bool:
    return _matches(domain_of(url), PLATFORM_DOMAINS)


def _key(name: Optional[str]) -> str:
    return os.getenv(name, "").strip() if name else ""


def engine_available(engine_id: str) -> bool:
    e = ENGINES.get(engine_id)
    if not e:
        return False
    return bool(DDGS) if e["key"] is None else bool(_key(e["key"]))


def resolve_engine(engine_id: str) -> str:
    if engine_id == "auto":
        for eid in ("brave", "serper", "searxng"):
            if engine_available(eid):
                return eid
        return "duckduckgo"
    return engine_id


def list_engines() -> List[Dict[str, Any]]:
    out = [{"id": "auto", "name": "Auto (best available)", "status": "available",
            "note": f"Uses {ENGINES[resolve_engine('auto')]['name']} right now; if it runs out or fails, the next "
                    f"set-up engine (Brave, Serper, SearXNG, then DuckDuckGo) answers"}]
    for eid, e in ENGINES.items():
        status = "available" if engine_available(eid) else ("needs_key" if e["key"] else "unavailable")
        out.append({"id": eid, "name": e["name"], "status": status, "note": e["note"], "url": e["url"],
                    "key": e["key"] or ""})
    return out


def list_modes() -> List[Dict[str, str]]:
    return [{"id": k, "name": v["name"], "help": v["help"], "examples": v["queries"][:2]} for k, v in MODES.items()]


def place_text(state: str, city: str) -> str:
    if city:
        return city
    if state and state != ALL_INDIA:
        return state
    return "India"


def clean_title(title: str) -> str:
    t = TITLE_SUFFIX_RE.sub("", title or "").strip()
    for sep in (" | ", " - ", " – ", " — "):
        if sep in t:
            t = t.split(sep)[0].strip()
    return t[:90]


def snippet_contacts(text: str) -> Tuple[List[str], List[str]]:
    emails = sorted({e.lower() for e in EMAIL_RE.findall(text or "")
                     if not e.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"))})
    phones = []
    for m in PHONE_RE.findall(text or ""):
        digits = re.sub(r"\D", "", m)[-10:]
        if len(digits) == 10 and len(set(digits)) > 3:
            p = f"+91 {digits[:5]} {digits[5:]}"
            if p not in phones:
                phones.append(p)
    return emails[:3], phones[:2]


# ---------------------------------------------------------------------------
# Validation + query building
# ---------------------------------------------------------------------------

def validate_request(data: Dict[str, Any]) -> Dict[str, Any]:
    """Returns a clean request or raises ValueError with a user-friendly message."""
    if not isinstance(data, dict):
        raise ValueError("Invalid request")
    kws = data.get("keywords")
    if not isinstance(kws, list):
        raise ValueError("Enter at least one keyword")
    keywords, seen = [], set()
    for k in kws:
        if not isinstance(k, str):
            raise ValueError("Keywords must be text")
        k = " ".join(k.split())
        if not k or k.lower() in seen:
            continue
        if len(k) > MAX_LEN:
            raise ValueError(f"Keyword longer than {MAX_LEN} characters")
        if '"' in k:
            raise ValueError("Keywords cannot contain double quotes")
        seen.add(k.lower())
        keywords.append(k)
    if not keywords:
        raise ValueError("Enter at least one keyword")
    if len(keywords) > MAX_KEYWORDS:
        raise ValueError(f"Use at most {MAX_KEYWORDS} keywords")

    audience_in = data.get("audience") or []
    if not isinstance(audience_in, list):
        raise ValueError("Target audience must be a list")
    audience, seen_a = [], set()
    for a in audience_in:
        a = " ".join(str(a).split())
        if not a or a.lower() in seen_a:
            continue
        if len(a) > MAX_AUDIENCE_LEN:
            raise ValueError(f"Target audience longer than {MAX_AUDIENCE_LEN} characters")
        if '"' in a:
            raise ValueError("Target audience cannot contain double quotes")
        seen_a.add(a.lower())
        audience.append(a)
    if len(audience) > MAX_AUDIENCE:
        raise ValueError(f"Use at most {MAX_AUDIENCE} target audiences")

    mode = data.get("mode") or "companies"
    if mode not in MODES:
        raise ValueError("Unknown search mode")
    custom = ""
    if mode == "custom":
        custom = " ".join(str(data.get("custom_query") or "").split())
        if not custom:
            raise ValueError("Write a custom query")
        if len(custom) > MAX_CUSTOM_LEN:
            raise ValueError(f"Custom query longer than {MAX_CUSTOM_LEN} characters")

    state = data.get("state") or ALL_INDIA
    if state != ALL_INDIA and state not in INDIAN_STATES:
        raise ValueError("Unknown state")
    city = " ".join(str(data.get("city") or "").split())
    if city and not CITY_RE.match(city):
        raise ValueError("City must be letters only (max 60 characters)")

    engine = data.get("engine") or "auto"
    if engine != "auto" and engine not in ENGINES:
        raise ValueError("Unknown search engine")
    resolved = resolve_engine(engine)
    if not engine_available(resolved):
        e = ENGINES[resolved]
        raise ValueError(f"{e['name']} needs {e['key']} in .env" if e["key"] else f"{e['name']} is not installed")

    time_filter = data.get("time") or "any"
    if time_filter not in TIME_FILTERS:
        raise ValueError("Unknown time filter")
    try:
        max_results = int(data.get("max_results") or 25)
    except (TypeError, ValueError):
        raise ValueError("Max results must be a number")
    if max_results not in MAX_RESULTS_CHOICES:
        raise ValueError(f"Max results must be one of {', '.join(map(str, MAX_RESULTS_CHOICES))}")

    excludes = data.get("exclude_sites") or []
    if not isinstance(excludes, list) or len(excludes) > MAX_EXCLUDES:
        raise ValueError(f"Exclude at most {MAX_EXCLUDES} sites")
    clean_ex = []
    for s in excludes:
        s = str(s).strip().lower()
        s = re.sub(r"^https?://", "", s).removeprefix("www.").rstrip("/")
        if not s:
            continue
        if not SITE_RE.match(s):
            raise ValueError(f"'{s[:30]}' is not a website (e.g. justdial.com)")
        clean_ex.append(s)

    return {"keywords": keywords, "audience": audience, "mode": mode, "custom_query": custom, "state": state, "city": city,
            "engine": engine, "engine_used": resolved, "time": time_filter, "max_results": max_results,
            "exclude_sites": clean_ex}


def audience_clause(audience: List[str]) -> str:
    """Target audience terms as one OR group: ("real estate" OR manufacturing)."""
    terms = []
    for a in audience:
        a = re.sub(r"[/|]", " ", a).strip()
        a = " ".join(a.split())
        if a:
            terms.append(f'"{a}"' if " " in a else a)
    if not terms:
        return ""
    return terms[0] if len(terms) == 1 else "(" + " OR ".join(terms) + ")"


def build_queries(req: Dict[str, Any]) -> List[Dict[str, str]]:
    loc = place_text(req["state"], req["city"])
    out = []
    for kw in req["keywords"]:
        templates = MODES[req["mode"]]["queries"]
        if req["mode"] == "custom":
            q = req["custom_query"].replace("{keyword}", kw).replace("{city}", loc)
            if "{keyword}" not in req["custom_query"] and len(req["keywords"]) > 1:
                q = f"{q} {kw}"
            qs = [q]
        else:
            qs = [t.format(kw=kw, loc=loc) for t in templates]
        for q in qs:
            q = " ".join(q.split())
            if req.get("audience"):
                q += " " + audience_clause(req["audience"])
            if req["exclude_sites"]:
                q += " " + " ".join(f"-site:{s}" for s in req["exclude_sites"])
            out.append({"keyword": kw, "query": q})
    return out


# ---------------------------------------------------------------------------
# Engines: each returns [{"title", "url", "snippet"}]
# ---------------------------------------------------------------------------

def _http_error(r: requests.Response, name: str) -> None:
    if r.status_code == 429:
        raise RateLimited(f"{name}: rate limit reached (HTTP 429)")
    if r.status_code in (401, 403):
        raise EngineError(f"{name} rejected the API key (HTTP {r.status_code})")
    if r.status_code == 402:
        raise EngineError(f"{name}: no credits left (HTTP 402)")
    if r.status_code >= 400:
        raise EngineError(f"{name}: HTTP {r.status_code}")


def search_brave(query: str, count: int, time_filter: str, session: requests.Session) -> List[Dict[str, str]]:
    out, offset = [], 0
    fresh = {"d": "pd", "w": "pw", "m": "pm", "y": "py"}.get(TIME_FILTERS[time_filter] or "")
    while len(out) < count and offset <= 4:
        params = {"q": query, "count": min(20, count - len(out)), "offset": offset, "country": "IN", "search_lang": "en"}
        if fresh:
            params["freshness"] = fresh
        r = session.get("https://api.search.brave.com/res/v1/web/search", params=params, timeout=TIMEOUT,
                        headers={"Accept": "application/json", "X-Subscription-Token": _key("BRAVE_SEARCH_API_KEY")})
        _http_error(r, "Brave Search")
        items = ((r.json() or {}).get("web") or {}).get("results") or []
        out += [{"title": i.get("title", ""), "url": i.get("url", ""), "snippet": re.sub(r"<[^>]+>", "", i.get("description", ""))}
                for i in items]
        if len(items) < params["count"]:
            break
        offset += 1
        time.sleep(GAP_SECONDS["brave"])
    return out[:count]


def search_serper(query: str, count: int, time_filter: str, session: requests.Session) -> List[Dict[str, str]]:
    out, page = [], 1
    while len(out) < count and page <= 10:
        body = {"q": query, "gl": "in", "hl": "en", "num": 10, "page": page}
        if TIME_FILTERS[time_filter]:
            body["tbs"] = f"qdr:{TIME_FILTERS[time_filter]}"
        r = session.post("https://google.serper.dev/search", json=body, timeout=TIMEOUT,
                         headers={"X-API-KEY": _key("SERPER_API_KEY"), "Content-Type": "application/json"})
        _http_error(r, "Serper")
        items = (r.json() or {}).get("organic") or []
        out += [{"title": i.get("title", ""), "url": i.get("link", ""), "snippet": i.get("snippet", "")} for i in items]
        if len(items) < 10:
            break
        page += 1
        time.sleep(GAP_SECONDS["serper"])
    return out[:count]


def search_duckduckgo(query: str, count: int, time_filter: str, session=None) -> List[Dict[str, str]]:
    if not DDGS:
        raise EngineError("DuckDuckGo search library is not installed")
    try:
        items = DDGS().text(query, region="in-en", timelimit=TIME_FILTERS[time_filter], backend="html",
                            max_results=count) or []
    except RatelimitException as e:
        raise RateLimited(f"DuckDuckGo: rate limit reached ({e})")
    except DuckDuckGoSearchException as e:
        raise EngineError(f"DuckDuckGo: {str(e)[:120]}")
    return [{"title": i.get("title", ""), "url": i.get("href", ""), "snippet": i.get("body", "")} for i in items]


def searxng_base() -> str:
    """SEARXNG_URL without a trailing slash; only http(s) URLs are accepted."""
    url = _key("SEARXNG_URL").rstrip("/")
    if url and urlparse(url).scheme not in ("http", "https"):
        raise EngineError("SEARXNG_URL must start with http:// or https://")
    return url


def search_searxng(query: str, count: int, time_filter: str, session: requests.Session) -> List[Dict[str, str]]:
    """Your own SearXNG instance (JSON output must be enabled in its settings.yml: search.formats: [html, json])."""
    base = searxng_base()
    if not base:
        raise EngineError("SearXNG needs SEARXNG_URL in .env")
    out, seen, page = [], set(), 1
    time_range = {"d": "day", "w": "week", "m": "month", "y": "year"}.get(TIME_FILTERS[time_filter] or "")
    while len(out) < count and page <= 5:
        params = {"q": query, "format": "json", "pageno": page, "language": "en-IN", "safesearch": 0}
        if time_range:
            params["time_range"] = time_range
        try:
            r = session.get(f"{base}/search", params=params, timeout=TIMEOUT, headers={"Accept": "application/json"})
        except requests.ConnectionError:
            raise EngineError(f"SearXNG is not running at {base} - start it (see docs/searxng-setup.md)")
        if r.status_code == 403:
            raise EngineError("SearXNG refused JSON output - add 'json' to search.formats in its settings.yml")
        _http_error(r, "SearXNG")
        try:
            items = (r.json() or {}).get("results") or []
        except ValueError:
            raise EngineError("SearXNG did not return JSON - check SEARXNG_URL")
        new = [i for i in items if i.get("url") and i["url"] not in seen]
        for i in new:
            seen.add(i["url"])
            out.append({"title": i.get("title", ""), "url": i["url"], "snippet": i.get("content", "") or ""})
        if not new:
            break
        page += 1
        time.sleep(GAP_SECONDS["searxng"])
    return out[:count]


RAW_ENGINE_FUNCS: Dict[str, Callable] = {"brave": search_brave, "serper": search_serper, "searxng": search_searxng,
                                         "duckduckgo": search_duckduckgo}

# Fallback: Brave -> Serper -> SearXNG -> DuckDuckGo. When an engine is rate limited, out of credits, rejects its key
# or is not running, the same query goes to the next engine that is set up, and the failed engine is skipped for
# COOLDOWN_SECONDS so later queries do not waste a request on it. This lets a Brave key and SearXNG work together.
FALLBACK_ORDER = ("brave", "serper", "searxng", "duckduckgo")
COOLDOWN_SECONDS = 600
_cooldown: Dict[str, float] = {}
_cooldown_lock = threading.Lock()


def cooling(engine_id: str) -> bool:
    with _cooldown_lock:
        return _cooldown.get(engine_id, 0) > time.time()


def _cool(engine_id: str) -> None:
    with _cooldown_lock:
        _cooldown[engine_id] = time.time() + COOLDOWN_SECONDS


def reset_cooldown() -> None:
    with _cooldown_lock:
        _cooldown.clear()


def fallback_chain(engine_id: str) -> List[str]:
    """The engine itself, then the engines after it in FALLBACK_ORDER that are set up; cooling ones go last."""
    later = list(FALLBACK_ORDER[FALLBACK_ORDER.index(engine_id) + 1:]) if engine_id in FALLBACK_ORDER else []
    chain = [engine_id] + [e for e in later if engine_available(e)]
    return [e for e in chain if not cooling(e)] + [e for e in chain if cooling(e)]


def run_with_fallback(engine_id: str, query: str, count: int, time_filter: str, session=None) -> List[Dict[str, str]]:
    errors: List[Exception] = []
    for eid in fallback_chain(engine_id):
        try:
            hits = RAW_ENGINE_FUNCS[eid](query, count, time_filter, session or requests.Session())
        except EngineError as e:               # RateLimited is an EngineError too
            _cool(eid)
            errors.append(e)
            continue
        except requests.RequestException as e:  # timeout / network: try the next engine, no cooldown
            errors.append(EngineError(f"{ENGINES[eid]['short']}: {e.__class__.__name__}"))
            continue
        if eid != engine_id:
            print(f"[search] {ENGINES[engine_id]['short']} unavailable - used {ENGINES[eid]['short']} instead")
        return hits
    limited = [e for e in errors if isinstance(e, RateLimited)]
    if limited:
        raise RateLimited("; ".join(str(e) for e in limited))
    raise EngineError("; ".join(str(e) for e in errors) or "No search engine available")


ENGINE_FUNCS: Dict[str, Callable] = {eid: functools.partial(run_with_fallback, eid) for eid in RAW_ENGINE_FUNCS}


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

SITE_OP_RE = re.compile(r"(?<![-\w])site:([a-z0-9.-]+\.[a-z]{2,})((?:/[\w./-]*)?)", re.I)


def required_sites(query: str) -> List[Tuple[str, str]]:
    """(domain, path) pairs from positive site: operators - results must come from one of them."""
    return [(d.lower().removeprefix("www."), p.lower().rstrip("/")) for d, p in SITE_OP_RE.findall(query)]


def matches_required(url: str, sites: List[Tuple[str, str]]) -> bool:
    if not sites:
        return True
    dom, path = domain_of(url), urlparse(url).path.lower()
    return any((dom == d or dom.endswith("." + d)) and path.startswith(p) for d, p in sites)


def make_result(raw: Dict[str, str], keyword: str, query: str, engine: str, mode: str) -> Dict[str, Any]:
    url = raw.get("url", "")
    emails, phones = snippet_contacts(f"{raw.get('title', '')} {raw.get('snippet', '')}")
    platform = is_platform(url)
    article = not platform and bool(ARTICLE_RE.search(raw.get("title") or ""))
    return {
        "company": clean_title(raw.get("title", "")) or domain_of(url),
        "title": (raw.get("title") or "")[:140],
        "url": url,
        "domain": domain_of(url),
        "website": "" if (platform or article) else url,
        "kind": "listing" if platform else ("article" if article else "website"),
        "snippet": (raw.get("snippet") or "")[:300],
        "email": ", ".join(emails),
        "phone": phones[0] if phones else "",
        "keyword": keyword, "query": query, "engine": engine, "mode": mode,
        "in_leads": False, "match": "",
    }


def mark_existing(results: List[Dict[str, Any]], master_path: str) -> None:
    """Flags results that already exist in the leads database (by email, phone, website or link)."""
    if not results or not os.path.exists(master_path):
        return
    from lead_normalizer import MasterLeadRegistry
    reg = MasterLeadRegistry(master_path)
    for r in results:
        idx = reg.find_match(result_to_raw_lead(r))
        if idx is not None:
            r["in_leads"] = True
            r["match"] = reg.leads[idx].get("company_name", "") or reg.leads[idx].get("lead_id", "")


def search(data: Dict[str, Any], master_path: str = "", sleep: Callable[[float], None] = time.sleep) -> Dict[str, Any]:
    req = validate_request(data)
    engine = req["engine_used"]
    queries = build_queries(req)
    per_query = max(5, -(-req["max_results"] // len(queries)))
    session = requests.Session()
    results, seen_urls, seen_domains = [], set(), set()
    errors, stopped, t0, done, ignored = [], "", time.time(), 0, 0
    for i, q in enumerate(queries):
        if len(results) >= req["max_results"]:
            break
        if i:
            sleep(GAP_SECONDS[engine])
        try:
            raw = ENGINE_FUNCS[engine](q["query"], per_query, req["time"], session)
        except RateLimited as e:
            stopped = str(e)
            break
        except (EngineError, requests.RequestException, ValueError) as e:
            errors.append(f"{q['query'][:60]}: {str(e)[:140]}")
            continue
        done += 1
        sites = required_sites(q["query"])
        for item in raw:
            url = (item.get("url") or "").strip()
            dom = domain_of(url)
            if not url.startswith(("http://", "https://")) or not dom or url in seen_urls:
                continue
            if not matches_required(url, sites):  # some engines ignore site: - drop off-target results
                ignored += 1
                continue
            if _matches(dom, JUNK_DOMAINS) or _matches(dom, req["exclude_sites"]):
                continue
            r = make_result(item, q["keyword"], q["query"], engine, req["mode"])
            # one row per company website; listings are kept per page
            if r["kind"] == "website":
                if dom in seen_domains:
                    continue
                seen_domains.add(dom)
            seen_urls.add(url)
            results.append(r)
            if len(results) >= req["max_results"]:
                break
    if master_path:
        mark_existing(results, master_path)
    order = {"website": 0, "listing": 1, "article": 2}
    results.sort(key=lambda r: (r["in_leads"], order[r["kind"]], not (r["email"] or r["phone"])))
    status = "error" if (not done and (errors or stopped)) else ("partial" if (errors or stopped) else "ok")
    hint = ""
    if not results and engine == "duckduckgo":
        hint = ("DuckDuckGo returned nothing useful for these queries (it often ignores site: and quoted searches "
                "from apps). Add a free BRAVE_SEARCH_API_KEY / SERPER_API_KEY, or run your own SearXNG (SEARXNG_URL, no key), for reliable results.")
    return {
        "query": {k: req[k] for k in ("keywords", "audience", "mode", "state", "city", "engine", "time", "max_results", "exclude_sites")},
        "queries": [q["query"] for q in queries],
        "engines": {engine: {"name": ENGINES[engine]["name"], "status": status, "count": len(results),
                             "queries_run": done, "queries_total": len(queries),
                             "seconds": round(time.time() - t0, 1),
                             "errors": errors + ([stopped] if stopped else [])}},
        "rate_limited": bool(stopped),
        "ignored_off_target": ignored,
        "hint": hint,
        "results": results,
        "total": len(results),
    }


def result_to_raw_lead(r: Dict[str, Any]) -> Dict[str, str]:
    details = [r.get("snippet", "")]
    if r.get("address"):
        details.append(f"Address: {r['address']}")
    socials = r.get("socials") or {}
    if socials:
        details.append("Social: " + ", ".join(f"{k}: {v}" for k, v in socials.items()))
    mode = MODES.get(r.get("mode", ""), {}).get("name", "")
    return {
        "company_name": r.get("company", ""),
        "full_name": r.get("contact_name", ""),
        "email": r.get("email", ""),
        "mobile_number": r.get("phone", ""),
        "website": r.get("website", ""),
        "location": r.get("location", ""),
        "description": ". ".join(x for x in details if x)[:600],
        "source": f"Search Engine ({ENGINES.get(r.get('engine', ''), {}).get('short', r.get('engine', ''))})",
        "source_url": r.get("url", ""),
        "lead_type": f"Search Engine - {mode}" if mode else "Search Engine",
    }

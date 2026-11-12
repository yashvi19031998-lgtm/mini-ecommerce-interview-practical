"""Scraping / Mining -> Social Media: business pages on Instagram, Facebook, LinkedIn, X and YouTube.

All data comes from search-engine results only (title, URL, snippet). This module never requests
instagram.com / facebook.com / linkedin.com / x.com / youtube.com itself: those sites need a login or block
bots, and scraping them breaks their terms.

Privacy (India DPDP Act 2023): only business / brand pages are kept. A result that looks like a private
person's profile (no business word, no contact, not a company page / channel) is dropped and counted.
"""
import re
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

import requests

import maps_sources
import search_engine as se
from job_portals import ALL_INDIA, INDIAN_STATES

MAX_KEYWORDS = 5
MAX_RESULTS_PER_SOURCE = 50
CITY_RE = re.compile(r"^[A-Za-z .'-]{1,60}$")

SOURCES = {
    "instagram": {"name": "Instagram business pages", "network": "Instagram",
                  "queries": ['site:instagram.com "{kw}" {place}',
                              'site:instagram.com "{kw}" {place} ("DM" OR "order" OR "booking" OR "enquiry")']},
    "facebook": {"name": "Facebook business pages", "network": "Facebook",
                 "queries": ['site:facebook.com "{kw}" {place}']},
    "linkedin": {"name": "LinkedIn company pages", "network": "LinkedIn",
                 "queries": ['site:linkedin.com/company "{kw}" {place}']},
    "x": {"name": "X (Twitter) business accounts", "network": "X",
          "queries": ['site:x.com "{kw}" {place}', 'site:twitter.com "{kw}" {place}']},
    "youtube": {"name": "YouTube channels", "network": "YouTube",
                "queries": ['site:youtube.com "{kw}" {place} channel']},
    "whatsapp_business": {"name": "WhatsApp Business catalogs", "network": "WhatsApp",
                          "unavailable": "Business catalogs are only visible inside the WhatsApp app"},
}

INSTAGRAM_SKIP = {"p", "reel", "reels", "explore", "stories", "tv", "accounts", "about", "developer", "legal",
                  "directory", "web", "challenge"}
FACEBOOK_SKIP = {"groups", "events", "posts", "photos", "videos", "watch", "marketplace", "sharer", "sharer.php",
                 "login", "login.php", "help", "pages", "gaming", "hashtag", "story.php", "permalink.php", "reel",
                 "share", "public", "people", "search", "dialog", "plugins", "policies", "privacy"}
X_SKIP = {"status", "hashtag", "search", "i", "intent", "home", "explore", "login", "share", "settings", "tos", "privacy"}
NOT_A_WEBSITE = ("instagram.com", "facebook.com", "fb.com", "linkedin.com", "x.com", "twitter.com", "youtube.com",
                 "youtu.be", "bit.ly", "linktr.ee", "linkin.bio", "wa.me", "whatsapp.com", "t.me", "google.com",
                 "bing.com", "duckduckgo.com", "goo.gl", "tinyurl.com")
BUSINESS_WORDS = ("shop", "store", "studio", "salon", "cafe", "café", "bakery", "boutique", "clinic", "academy",
                  "classes", "services", "solutions", "agency", "official", "pvt", "ltd", "llp", "co.", "enterprises",
                  "traders", "restaurant", "hotel", "interiors", "designs", "photography", "events", "real estate",
                  "builders", "company", "brand", "store", "kitchen", "foods", "fashion", "boutique", "institute",
                  "consultancy", "hospital", "dental", "fitness", "gym", "jewellers", "jewellery", "furniture", "decor")
TITLE_NOISE = re.compile(
    r"\s*(?:[•|\-–—:]\s*)?(?:Instagram photos and videos|Instagram|Facebook|LinkedIn|on LinkedIn|X|Twitter|YouTube)\s*$"
    r"|\s*\(@[\w.]+\)\s*|\s*@[\w.]+\s*$|\s*\|\s*$", re.I)
FOLLOWERS_RE = re.compile(r"([\d][\d,.]*\s*[KkMm]?)\s+(?:followers|subscribers)\b", re.I)
URL_IN_TEXT = re.compile(r"(?:https?://|www\.)[^\s\"'<>()]+", re.I)


# ---------------------------------------------------------------------------
# Catalog + validation
# ---------------------------------------------------------------------------

def source_status(sid: str) -> str:
    return "unavailable" if SOURCES[sid].get("unavailable") else "available"


def list_sources() -> List[Dict[str, Any]]:
    return [{"id": sid, "name": s["name"], "kind": "social", "status": source_status(sid),
             "note": f"{s['network']} pages found through the search engine" if not s.get("unavailable") else "",
             "reason": s.get("unavailable", ""), "keys": []} for sid, s in SOURCES.items()]


def validate_request(data: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("Invalid request")
    try:
        keywords = maps_sources._clean_list(data.get("keywords"), "Keyword", MAX_KEYWORDS, 80, True)
    except ValueError as e:
        if "at least one" in str(e):
            raise ValueError("Enter at least one business type or keyword")
        raise
    audience = maps_sources._clean_list(data.get("audience"), "Target audience", 5, 60, False)
    state = data.get("state") or ""
    if not state:
        raise ValueError("Select a state")
    if state != ALL_INDIA and state not in INDIAN_STATES:
        raise ValueError("Unknown state")
    city = " ".join(str(data.get("city") or "").split())
    if city and not CITY_RE.match(city):
        raise ValueError("City must be letters only (max 60 characters)")
    sources = data.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("Select at least one source")
    for sid in sources:
        if sid not in SOURCES:
            raise ValueError(f"Unknown source: {str(sid)[:30]}")
        if source_status(sid) == "unavailable":
            raise ValueError(f"{SOURCES[sid]['name']} is not available: {SOURCES[sid]['unavailable']}")
    engine = data.get("engine") or "auto"
    if engine != "auto" and engine not in se.ENGINES:
        raise ValueError("Unknown search engine")
    engine_used = se.resolve_engine(engine)
    if not se.engine_available(engine_used):
        e = se.ENGINES[engine_used]
        raise ValueError(f"{e['name']} needs {e['key']} in .env")
    return {"keywords": keywords, "audience": audience, "state": state, "city": city,
            "sources": list(dict.fromkeys(sources)), "engine": engine, "engine_used": engine_used}


# ---------------------------------------------------------------------------
# URL / field parsing (title, URL, snippet only)
# ---------------------------------------------------------------------------

def profile_of(sid: str, url: str) -> Optional[Tuple[str, str]]:
    """(handle, normalised profile URL) for a business profile URL of this network, else None."""
    p = urlparse((url or "").strip())
    host = (p.hostname or "").lower()
    host = host[4:] if host.startswith("www.") else host
    host = host[2:] if host.startswith("m.") else host
    parts = [x for x in p.path.split("/") if x]
    if sid == "instagram" and host == "instagram.com" and len(parts) == 1 and parts[0].lower() not in INSTAGRAM_SKIP \
            and re.fullmatch(r"[A-Za-z0-9_.]{2,30}", parts[0]):
        return parts[0].lower(), f"https://www.instagram.com/{parts[0].lower()}/"
    if sid == "facebook" and host in ("facebook.com", "web.facebook.com"):
        if parts and parts[0].lower() == "profile.php":
            pid = (parse_qs(p.query).get("id") or [""])[0]
            return (f"id{pid}", f"https://www.facebook.com/profile.php?id={pid}") if pid.isdigit() else None
        if len(parts) == 1 and parts[0].lower() not in FACEBOOK_SKIP and re.fullmatch(r"[A-Za-z0-9.\-]{2,80}", parts[0]):
            return parts[0].lower(), f"https://www.facebook.com/{parts[0]}"
        return None
    if sid == "linkedin" and host.endswith("linkedin.com") and len(parts) >= 2 and parts[0].lower() == "company":
        return parts[1].lower(), f"https://www.linkedin.com/company/{parts[1]}"
    if sid == "x" and host in ("x.com", "twitter.com") and len(parts) == 1 and parts[0].lower() not in X_SKIP \
            and re.fullmatch(r"[A-Za-z0-9_]{1,15}", parts[0]):
        return parts[0].lower(), f"https://x.com/{parts[0]}"
    if sid == "youtube" and host == "youtube.com" and parts:
        first = parts[0]
        if first.startswith("@") and len(parts) == 1:
            return first.lower(), f"https://www.youtube.com/{first}"
        if first.lower() in ("c", "channel", "user") and len(parts) == 2:
            return f"{first.lower()}/{parts[1]}".lower(), f"https://www.youtube.com/{first}/{parts[1]}"
    return None


def clean_name(title: str, handle: str) -> str:
    t = se.clean_title(title or "") if title else ""
    for _ in range(3):
        t = TITLE_NOISE.sub("", t).strip(" -|•:")
    return t or handle.lstrip("@")


def followers_of(text: str) -> str:
    m = FOLLOWERS_RE.search(text or "")
    return m.group(1).replace(" ", "") if m else ""


def followers_number(text: str) -> float:
    t = (text or "").replace(",", "").strip().upper()
    try:
        if t.endswith("K"):
            return float(t[:-1]) * 1_000
        if t.endswith("M"):
            return float(t[:-1]) * 1_000_000
        return float(t) if t else 0.0
    except ValueError:
        return 0.0


def website_in(text: str) -> str:
    for raw in URL_IN_TEXT.findall(text or ""):
        url = raw.rstrip(".,;)") if raw.lower().startswith("http") else "https://" + raw.rstrip(".,;)")
        dom = se.domain_of(url)
        if dom and "." in dom and not any(dom == d or dom.endswith("." + d) for d in NOT_A_WEBSITE):
            return url
    return ""


def looks_like_business(sid: str, keyword: str, text: str, has_contact: bool) -> bool:
    if sid in ("linkedin", "youtube") or has_contact:
        return True
    low = (text or "").lower()
    return any(w in low for w in BUSINESS_WORDS) or (keyword.lower() in low)


def make_result(source_id: str, **fields) -> Dict[str, str]:
    keys = ("source", "company", "handle", "network", "profile_url", "email", "phone", "website", "location",
            "category", "followers", "url", "details", "keyword")
    out = {"source_id": source_id}
    out.update({k: str(fields.get(k) or "") for k in keys})
    out["kind"] = "website" if out["website"] else "listing"
    return out


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

def search_network(sid: str, keyword: str, req: Dict[str, Any], counters: Dict[str, int]) -> List[Dict[str, Any]]:
    place = se.place_text(req["state"], req["city"])
    engine = req["engine_used"]
    out = []
    for i, tpl in enumerate(SOURCES[sid]["queries"]):
        if i:
            time.sleep(se.GAP_SECONDS[engine])
        q = tpl.format(kw=keyword, place=place)
        sites = se.required_sites(q)
        try:
            hits = se.ENGINE_FUNCS[engine](q, 25, "any", requests.Session())
        except se.RateLimited as e:
            if not out:
                raise
            counters["rate_limited"] = str(e)     # keep what this keyword already found
            return out
        for h in hits:
            url = h.get("url") or ""
            if sites and not se.matches_required(url, sites):
                continue
            prof = profile_of(sid, url)
            if not prof:
                continue
            handle, profile_url = prof
            title, snippet = h.get("title") or "", h.get("snippet") or ""
            emails, phones = se.snippet_contacts(f"{title} {snippet}")
            website = website_in(snippet)
            if not looks_like_business(sid, keyword, f"{title} {snippet}", bool(emails or phones or website)):
                counters["personal"] += 1
                continue
            out.append(make_result(sid, source=SOURCES[sid]["name"], company=clean_name(title, handle), handle=handle,
                                   network=SOURCES[sid]["network"], profile_url=profile_url, url=profile_url,
                                   email=", ".join(emails), phone=phones[0] if phones else "", website=website,
                                   location=place if place != "India" else "", category=keyword,
                                   followers=followers_of(snippet), details=snippet[:200], keyword=keyword))
    return out


def _run_source(sid: str, req: Dict[str, Any]) -> Dict[str, Any]:
    t0, rows, errors, counters = time.time(), [], [], {"personal": 0, "rate_limited": ""}
    for i, kw in enumerate(req["keywords"]):
        if counters["rate_limited"]:
            errors.append(f"{kw}: {counters['rate_limited']}")
            break
        if i:
            time.sleep(se.GAP_SECONDS.get(req["engine_used"], 1.0))
        try:
            rows += search_network(sid, kw, req, counters)
        except se.RateLimited as e:
            errors.append(f"{kw}: {e}")
            break
        except requests.Timeout:
            errors.append(f"{kw}: {SOURCES[sid]['name']} did not answer in time (server busy) - try again later")
        except requests.ConnectionError:
            errors.append(f"{kw}: could not reach the search engine - check the internet connection")
        except Exception as e:  # noqa: BLE001 - one source must never fail the whole search
            errors.append(f"{kw}: {e.__class__.__name__}: {str(e)[:120]}")
    if counters["rate_limited"] and not any(counters["rate_limited"] in e for e in errors):
        errors.append(counters["rate_limited"])
    notes = []
    if counters["personal"]:
        notes.append(f"{counters['personal']} personal-looking profile(s) skipped (privacy)")
    if req["audience"] and rows:
        words = [w for a in req["audience"] for w in re.findall(r"[a-z0-9]{3,}", a.lower())]
        kept = [r for r in rows if any(w in f"{r['company']} {r['details']} {r['category']}".lower() for w in words)]
        if kept:
            rows = kept
        else:
            notes.append("No result mentions the target audience - showing all results")
    status = "error" if errors and not rows else "ok"
    return {"rows": rows, "status": status, "errors": errors + notes, "seconds": round(time.time() - t0, 1)}


MERGE_FIELDS = ("email", "phone", "website", "followers", "details", "location")


def search(data: Dict[str, Any]) -> Dict[str, Any]:
    req = validate_request(data)
    with ThreadPoolExecutor(max_workers=min(3, len(req["sources"]))) as pool:
        runs = dict(zip(req["sources"], pool.map(lambda sid: _run_source(sid, req), req["sources"])))
    index: Dict[str, Dict[str, Any]] = {}
    results, statuses = [], {}
    for sid in req["sources"]:
        count = 0
        for r in runs[sid]["rows"]:
            key = f"{r['network']}|{r['handle']}".lower()
            kept = index.get(key)
            if kept:
                for f in MERGE_FIELDS:
                    if not kept.get(f) and r.get(f):
                        kept[f] = r[f]
                if kept["website"]:
                    kept["kind"] = "website"
                continue
            if count >= MAX_RESULTS_PER_SOURCE:
                continue
            index[key] = r
            results.append(r)
            count += 1
        statuses[sid] = {"name": SOURCES[sid]["name"], "status": runs[sid]["status"], "count": count,
                         "seconds": runs[sid]["seconds"], "errors": runs[sid]["errors"]}
    results.sort(key=lambda r: (not (r["phone"] or r["email"]), not r["website"], -followers_number(r["followers"])))
    hint = ""
    if not results and req["engine_used"] == "duckduckgo":
        hint = ("DuckDuckGo returned nothing useful for these queries (it often ignores site: and quoted searches "
                "from apps). Add a free BRAVE_SEARCH_API_KEY / SERPER_API_KEY, or run your own SearXNG (SEARXNG_URL, no key), for reliable results.")
    return {"query": {k: req[k] for k in ("keywords", "audience", "state", "city", "engine")},
            "results": results, "total": len(results), "sources": statuses, "engine": req["engine_used"], "hint": hint}


def result_to_raw_lead(r: Dict[str, Any]) -> Dict[str, str]:
    details = [r.get("network") and f"{r['network']}: {r.get('profile_url', '')}", r.get("category"),
               r.get("followers") and f"{r['followers']} followers", r.get("details")]
    return {
        "company_name": r.get("company", "") or r.get("handle", ""),
        "email": r.get("email", ""),
        "mobile_number": r.get("phone", ""),
        "website": r.get("website", ""),
        "location": r.get("location", ""),
        "description": ". ".join(x for x in details if x)[:600],
        "source": f"Social Media ({r.get('network') or r.get('source', '')})",
        "source_url": r.get("profile_url") or r.get("url", ""),
        "lead_type": "Social Media Business",
    }

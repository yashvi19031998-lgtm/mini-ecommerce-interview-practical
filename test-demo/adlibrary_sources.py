"""Scraping / Mining -> Ad Library: businesses that are spending money on ads right now (= hot leads).

Sources:
  ad_pixels           free. The search engine finds business websites for the keyword + place, then each home
                      page (guarded fetch, HTML cache) is checked for advertising tags: Meta Pixel, Google Ads,
                      Google Tag Manager, LinkedIn Insight, Microsoft Ads (UET). A site with an ad tag is
                      investing in ads. At most AD_PIXEL_SITES sites are opened per search.
  meta_ad_library     official Meta Ad Library API (META_AD_LIBRARY_TOKEN). Note: outside the EU / UK the
                      API only returns political & social-issue ads, so for India it finds advertisers on
                      those topics, not shops.
  google_transparency Google Ads Transparency Center advertiser pages found through the search engine.
  Unavailable: scraping the Meta Ad Library website (needs a browser; against Meta's terms) and the Google Ads
  Transparency website (JavaScript-only).
"""
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List

import requests

import deep_search
import maps_sources
import search_engine as se
from job_portals import ALL_INDIA, INDIAN_STATES, PortalError, _session

MAX_KEYWORDS = 5
MAX_RESULTS_PER_SOURCE = 50
AD_PIXEL_SITES = 15
META_API = "https://graph.facebook.com/v21.0/ads_archive"
CITY_RE = re.compile(r"^[A-Za-z .'-]{1,60}$")

AD_TAGS = {
    "Meta Pixel": re.compile(r"connect\.facebook\.net/[^\"'\s]*/fbevents\.js|fbq\(\s*['\"]init", re.I),
    "Google Ads": re.compile(r"\bAW-\d{6,}\b|googleadservices\.com|googleads\.g\.doubleclick\.net", re.I),
    "Google Tag Manager": re.compile(r"\bGTM-[A-Z0-9]{4,}\b"),
    "LinkedIn Insight": re.compile(r"snap\.licdn\.com|_linkedin_partner_id", re.I),
    "Microsoft Ads": re.compile(r"bat\.bing\.com", re.I),
}
# GTM alone only means "has a tag manager"; real ad tags are the strong signal
STRONG_TAGS = {"Meta Pixel", "Google Ads", "LinkedIn Insight", "Microsoft Ads"}

SOURCES = {
    "ad_pixels": {"name": "Ad tags on websites", "kind": "signals", "key": None,
                  "note": "Finds business websites and checks them for Meta Pixel / Google Ads / LinkedIn / Microsoft ad tags."},
    "meta_ad_library": {"name": "Meta Ad Library API", "kind": "official", "key": "META_AD_LIBRARY_TOKEN",
                        "note": "Official API. India: political & social-issue ads only (Meta's rule outside the EU / UK)."},
    "google_transparency": {"name": "Google Ads Transparency (via search engine)", "kind": "search", "key": None,
                            "note": "Advertiser pages found through the search engine (needs Brave / Serper for good results)."},
    "meta_ad_library_web": {"name": "Meta Ad Library website", "kind": "official",
                            "unavailable": "Needs a browser; automated access is against Meta's terms - use the API"},
    "google_transparency_web": {"name": "Google Ads Transparency website", "kind": "official",
                                "unavailable": "The site is JavaScript-only; there is no public API"},
}


def source_status(sid: str) -> str:
    s = SOURCES[sid]
    if s.get("unavailable"):
        return "unavailable"
    if s.get("key") and not maps_sources._key_set(s["key"]):
        return "needs_key"
    return "available"


def list_sources() -> List[Dict[str, Any]]:
    out = []
    for sid, s in SOURCES.items():
        st = source_status(sid)
        reason = s.get("unavailable") or (f"Add {s['key']} in .env (Settings > API Keys)" if st == "needs_key" else "")
        out.append({"id": sid, "name": s["name"], "kind": s["kind"], "status": st, "note": s.get("note", ""),
                    "reason": reason, "keys": [s["key"]] if s.get("key") else []})
    return out


def validate_request(data: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("Invalid request")
    keywords = maps_sources._clean_list(data.get("keywords"), "Keyword", MAX_KEYWORDS, 80, True)
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
        st = source_status(sid)
        if st == "needs_key":
            raise ValueError(f"{SOURCES[sid]['name']} needs {SOURCES[sid]['key']} in .env")
        if st == "unavailable":
            raise ValueError(f"{SOURCES[sid]['name']} is not available: {SOURCES[sid]['unavailable']}")
    engine = data.get("engine") or "auto"
    if engine != "auto" and engine not in se.ENGINES:
        raise ValueError("Unknown search engine")
    engine_used = se.resolve_engine(engine)
    if {"ad_pixels", "google_transparency"} & set(sources) and not se.engine_available(engine_used):
        e = se.ENGINES[engine_used]
        raise ValueError(f"{e['name']} needs {e['key']} in .env")
    return {"keywords": keywords, "audience": audience, "state": state, "city": city,
            "sources": list(dict.fromkeys(sources)), "engine": engine, "engine_used": engine_used}


def make_result(source_id: str, **f) -> Dict[str, Any]:
    out = {"source_id": source_id, "source": SOURCES[source_id]["name"]}
    for k in ("company", "email", "phone", "website", "location", "category", "url", "details", "keyword",
              "ad_tags", "ad_since", "ad_link"):
        v = f.get(k)
        out[k] = str(v or "").strip() if k in ("url", "ad_link") else " ".join(str(v or "").split())[:600]
    out["kind"] = "website" if out["website"] else "listing"
    return out


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------

def detect_ad_tags(html: str) -> List[str]:
    return [name for name, pat in AD_TAGS.items() if pat.search(html or "")]


def search_ad_pixels(keyword: str, req: Dict[str, Any], budget: List[int]) -> Dict[str, Any]:
    """Returns {"rows": [...], "checked": n, "no_tags": n}."""
    engine = req["engine_used"]
    place = se.place_text(req["state"], req["city"])
    hits = se.ENGINE_FUNCS[engine](f'"{keyword}" {place}', 25, "any", requests.Session())
    rows, checked, no_tags, seen = [], 0, 0, set()
    for h in hits:
        url = (h.get("url") or "").strip()
        dom = se.domain_of(url)
        if not dom or dom in seen or se.is_platform(url) or se._matches(dom, se.JUNK_DOMAINS) \
                or se.ARTICLE_RE.search(h.get("title") or "") or deep_search.is_government(url):
            continue
        seen.add(dom)
        if budget[0] >= AD_PIXEL_SITES:
            break
        budget[0] += 1
        root = deep_search.site_root(url)
        html = deep_search.fetch(root)       # guarded (public addresses only, every redirect), cached, honest UA
        checked += 1
        tags = detect_ad_tags(html)
        if not (set(tags) & STRONG_TAGS):
            no_tags += 1
            continue
        emails, phones = se.snippet_contacts(f"{h.get('title', '')} {h.get('snippet', '')}")
        rows.append(make_result("ad_pixels", company=se.clean_title(h.get("title", "")) or dom, website=root,
                                url=root, location=place if place != "India" else "", category=keyword,
                                email=", ".join(emails), phone=phones[0] if phones else "",
                                ad_tags=", ".join(tags), keyword=keyword,
                                details=f"Ad tags on website: {', '.join(tags)}"))
    return {"rows": rows, "checked": checked, "no_tags": no_tags}


def search_meta(keyword: str, req: Dict[str, Any]) -> List[Dict[str, Any]]:
    token = os.getenv("META_AD_LIBRARY_TOKEN", "").strip()
    if not token:
        raise PortalError("META_AD_LIBRARY_TOKEN not set in .env")
    params = {"access_token": token, "search_terms": keyword, "ad_reached_countries": '["IN"]',
              "ad_active_status": "ACTIVE", "ad_type": "POLITICAL_AND_ISSUE_ADS", "limit": 50,
              "fields": "page_id,page_name,ad_delivery_start_time,ad_snapshot_url,bylines,publisher_platforms"}
    r = requests.get(META_API, params=params, timeout=25)
    if r.status_code in (400, 401, 403):
        try:
            msg = (r.json().get("error") or {}).get("message", "")
        except ValueError:
            msg = ""
        raise PortalError(f"Meta rejected the request (HTTP {r.status_code}){': ' + msg[:120] if msg else ''}")
    if r.status_code == 429:
        raise PortalError("Meta Ad Library: rate limit reached - try again later")
    r.raise_for_status()
    pages: Dict[str, Dict[str, Any]] = {}
    for ad in (r.json() or {}).get("data") or []:
        pid = str(ad.get("page_id") or "")
        name = ad.get("page_name") or ""
        if not pid or not name:
            continue
        p = pages.setdefault(pid, {"name": name, "count": 0, "since": ad.get("ad_delivery_start_time", ""),
                                   "link": ad.get("ad_snapshot_url", ""), "by": ad.get("bylines", ""),
                                   "where": ", ".join(ad.get("publisher_platforms") or [])})
        p["count"] += 1
        if ad.get("ad_delivery_start_time", "") < p["since"]:
            p["since"] = ad["ad_delivery_start_time"]
    out = []
    for pid, p in pages.items():
        out.append(make_result("meta_ad_library", company=p["name"], url=f"https://www.facebook.com/{pid}",
                               ad_link=f"https://www.facebook.com/ads/library/?view_all_page_id={pid}",
                               ad_since=p["since"][:10], category=keyword, keyword=keyword,
                               details=f"{p['count']} active ad(s) on {p['where'] or 'Meta'}"
                                       + (f" · paid for by {p['by']}" if p["by"] else "")))
    return out


def search_transparency(keyword: str, req: Dict[str, Any]) -> List[Dict[str, Any]]:
    engine = req["engine_used"]
    q = f'site:adstransparency.google.com "{keyword}"'
    sites = se.required_sites(q)
    out = []
    for h in se.ENGINE_FUNCS[engine](q, 25, "any", requests.Session()):
        url = h.get("url", "")
        if not se.matches_required(url, sites) or "/advertiser/" not in url:
            continue
        name = re.sub(r"\s*[-|]\s*Google Ads Transparency.*$", "", h.get("title") or "", flags=re.I).strip()
        out.append(make_result("google_transparency", company=name or "Google advertiser", url=url, ad_link=url,
                               category=keyword, keyword=keyword, details=(h.get("snippet") or "")[:200]))
    return out


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

def _run_source(sid: str, req: Dict[str, Any]) -> Dict[str, Any]:
    t0, rows, errors = time.time(), [], []
    budget, checked, no_tags = [0], 0, 0
    for i, kw in enumerate(req["keywords"]):
        if i:
            time.sleep(se.GAP_SECONDS.get(req["engine_used"], 1.0))
        try:
            if sid == "ad_pixels":
                res = search_ad_pixels(kw, req, budget)
                rows += res["rows"]
                checked += res["checked"]
                no_tags += res["no_tags"]
            elif sid == "meta_ad_library":
                rows += search_meta(kw, req)
            elif sid == "google_transparency":
                rows += search_transparency(kw, req)
        except se.RateLimited as e:
            errors.append(f"{kw}: {e}")
            break
        except PortalError as e:
            errors.append(f"{kw}: {e}")
        except requests.Timeout:
            errors.append(f"{kw}: {SOURCES[sid]['name']} did not answer in time (server busy) - try again later")
        except requests.ConnectionError:
            errors.append(f"{kw}: could not reach {SOURCES[sid]['name']} - check the internet connection")
        except Exception as e:  # noqa: BLE001 - one source must never fail the whole search
            errors.append(f"{kw}: {e.__class__.__name__}: {str(e)[:120]}")
    if sid == "ad_pixels" and checked:
        errors.append(f"{checked} website(s) checked, {no_tags} without ad tags (not shown)")
    if req["audience"] and rows:
        words = [w for a in req["audience"] for w in re.findall(r"[a-z0-9]{3,}", a.lower())]
        kept = [r for r in rows if any(w in f"{r['company']} {r['category']} {r['details']}".lower() for w in words)]
        if kept:
            rows = kept
        else:
            errors.append("No result mentions the target audience - showing all results")
    real_errors = [e for e in errors if "website(s) checked" not in e]
    status = "error" if real_errors and not rows and len(real_errors) >= len(req["keywords"]) else "ok"
    return {"rows": rows[:MAX_RESULTS_PER_SOURCE], "status": status, "errors": errors,
            "seconds": round(time.time() - t0, 1)}


def _dedupe(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    index, out = {}, []
    for r in rows:
        keys = [("w", se.domain_of(r["website"]))] if r.get("website") else []
        keys.append(("n", re.sub(r"[^a-z0-9]", "", r["company"].lower())))
        kept = next((index[k] for k in keys if k in index), None)
        if kept is not None:
            for f in ("email", "phone", "website", "ad_tags", "ad_link", "ad_since"):
                if not kept.get(f) and r.get(f):
                    kept[f] = r[f]
            if r.get("details") and r["details"] not in kept["details"]:
                kept["details"] = f"{kept['details']} · {r['details']}"[:600]
            continue
        for k in keys:
            index[k] = r
        out.append(r)
    return out


def search(data: Dict[str, Any]) -> Dict[str, Any]:
    req = validate_request(data)
    with ThreadPoolExecutor(max_workers=min(3, len(req["sources"]))) as pool:
        runs = dict(zip(req["sources"], pool.map(lambda sid: _run_source(sid, req), req["sources"])))
    rows, statuses = [], {}
    for sid in req["sources"]:
        rows += runs[sid]["rows"]
        statuses[sid] = {"name": SOURCES[sid]["name"], "status": runs[sid]["status"], "count": len(runs[sid]["rows"]),
                         "seconds": runs[sid]["seconds"], "errors": runs[sid]["errors"]}
    results = _dedupe(rows)
    results.sort(key=lambda r: (not (r["email"] or r["phone"]), not r["website"],
                                -len([t for t in r["ad_tags"].split(", ") if t])))
    hint = ""
    if not results and req["engine_used"] == "duckduckgo" and {"ad_pixels", "google_transparency"} & set(req["sources"]):
        hint = ("DuckDuckGo returned nothing useful for these queries (it often ignores site: and quoted searches "
                "from apps). Add a free BRAVE_SEARCH_API_KEY / SERPER_API_KEY, or run your own SearXNG (SEARXNG_URL, no key), for reliable results.")
    return {"query": {k: req[k] for k in ("keywords", "audience", "state", "city", "engine")},
            "results": results, "total": len(results), "sources": statuses, "engine": req["engine_used"], "hint": hint}


def result_to_raw_lead(r: Dict[str, Any]) -> Dict[str, str]:
    details = [r.get("details", "")]
    if r.get("ad_link"):
        details.append(f"Ads: {r['ad_link']}")
    if r.get("ad_since"):
        details.append(f"Advertising since {r['ad_since']}")
    return {
        "company_name": r.get("company", ""),
        "email": r.get("email", ""),
        "mobile_number": r.get("phone", ""),
        "website": r.get("website", ""),
        "location": r.get("location", ""),
        "description": ". ".join(x for x in details if x)[:600],
        "source": f"Ad Library ({SOURCES.get(r.get('source_id', ''), {}).get('name', r.get('source', ''))})",
        "source_url": r.get("url", ""),
        "lead_type": "Active Advertiser",
    }

"""Scraping / Mining -> Ecommerce Platforms (online stores and sellers for a product category).

Wired into app.py (/api/ecommerce/*), frontend/lib/api.js, and frontend/app/page.js.
Entry points:
  list_sources() -> [{"id", "name", "kind", "status", "note", "reason", "keys"}]
  validate_request(data) -> clean dict, or raises ValueError("user-friendly message")
  search(data) -> {"query", "results", "total", "sources", "engine", "hint"}
  result_to_raw_lead(result) -> dict for lead_normalizer.MasterLeadRegistry.add_lead
"""
import concurrent.futures
import json
import os
import re
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests

import deep_search
import html_cache_manager as hcm
from job_portals import ALL_INDIA, INDIAN_STATES, _session
import search_engine

MAX_KEYWORDS = 5
MAX_LEN = 80
MAX_AUDIENCE = 5
MAX_AUDIENCE_LEN = 60
MAX_RESULTS_PER_SOURCE = 50
MAX_VERIFY_REQUESTS = 15
CITY_RE = re.compile(r"^[A-Za-z .'-]{1,60}$")
INSTAGRAM_PROFILE_RE = re.compile(r"^https?://(?:www\.)?instagram\.com/([a-zA-Z0-9_.]+)/?$", re.I)
INSTAGRAM_EXCLUDED = {
    "p", "reel", "reels", "explore", "stories", "direct", "accounts",
    "developer", "about", "legal", "terms", "privacy", "help", "tv",
    "highlights"
}

SOURCES: Dict[str, Dict[str, Any]] = {
    "shopify": {
        "name": "Shopify stores",
        "kind": "store_platform",
        "status": "available",
        "key": None,
        "note": "Finds direct-to-consumer Shopify stores using myshopify.com footprints",
        "reason": "",
        "keys": [],
    },
    "woocommerce": {
        "name": "WooCommerce stores",
        "kind": "store_platform",
        "status": "available",
        "key": None,
        "note": "Finds WordPress / WooCommerce online shops using cart and product footprints",
        "reason": "",
        "keys": [],
    },
    "instagram_shops": {
        "name": "Instagram shops",
        "kind": "store_platform",
        "status": "available",
        "key": None,
        "note": "Finds Indian Instagram business profiles taking orders via DM / WhatsApp",
        "reason": "",
        "keys": [],
    },
    "amazon_in": {
        "name": "Amazon.in sellers",
        "kind": "marketplace",
        "status": "unavailable",
        "key": None,
        "note": "Amazon blocks automated access; seller pages need a browser",
        "reason": "Amazon blocks automated access; seller pages need a browser",
        "keys": [],
    },
    "flipkart": {
        "name": "Flipkart sellers",
        "kind": "marketplace",
        "status": "unavailable",
        "key": None,
        "note": "Flipkart blocks automated access",
        "reason": "Flipkart blocks automated access",
        "keys": [],
    },
    "meesho": {
        "name": "Meesho sellers",
        "kind": "marketplace",
        "status": "unavailable",
        "key": None,
        "note": "Seller details need login",
        "reason": "Seller details need login",
        "keys": [],
    },
}


def make_result(source_id: str, **fields) -> Dict[str, str]:
    keys = ("source", "company", "email", "phone", "website", "location", "category", "platform", "url",
            "details", "keyword", "instagram", "facebook")
    out = {"source_id": source_id}
    out.update({k: str(fields.get(k) or "") for k in keys})
    return out


def list_sources() -> List[Dict[str, Any]]:
    out = []
    for sid, s in SOURCES.items():
        out.append({
            "id": sid,
            "name": s["name"],
            "kind": s["kind"],
            "status": s["status"],
            "note": s["note"],
            "reason": s["reason"],
            "keys": s["keys"],
        })
    return out


def _clean_list(values: Any, label: str, max_items: int, max_len: int, required: bool) -> List[str]:
    if values is None:
        values = []
    if not isinstance(values, list):
        raise ValueError(f"Enter at least one {label.lower()}" if required else f"{label} must be a list")
    out, seen = [], set()
    for v in values:
        if not isinstance(v, str):
            raise ValueError(f"{label} must be text")
        v = " ".join(v.split())
        if not v or v.lower() in seen:
            continue
        if len(v) > max_len:
            raise ValueError(f"{label} longer than {max_len} characters")
        if '"' in v:
            raise ValueError(f"{label} cannot contain double quotes")
        seen.add(v.lower())
        out.append(v)
    if required and not out:
        raise ValueError(f"Enter at least one {label.lower()}")
    if len(out) > max_items:
        raise ValueError(f"Use at most {max_items} {label.lower()}s")
    return out


def validate_request(data: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("Invalid request")

    keywords = _clean_list(data.get("keywords"), "Product or category", MAX_KEYWORDS, MAX_LEN, True)
    audience = _clean_list(data.get("audience"), "Target audience", MAX_AUDIENCE, MAX_AUDIENCE_LEN, False)

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
        s = SOURCES[sid]
        if s["status"] != "available":
            raise ValueError(f"{s['name']} is not available: {s['reason']}")

    engine_input = str(data.get("engine") or "auto")
    if engine_input not in ("auto", *search_engine.ENGINES.keys()):
        raise ValueError("Unknown search engine")
    resolved_engine = search_engine.resolve_engine(engine_input)
    if not search_engine.engine_available(resolved_engine):
        eng_meta = search_engine.ENGINES.get(resolved_engine, {})
        req_key = eng_meta.get("key") or "API key"
        raise ValueError(f"{eng_meta.get('name', resolved_engine)} needs {req_key} in .env")

    return {
        "keywords": keywords,
        "audience": audience,
        "state": state,
        "city": city,
        "sources": list(dict.fromkeys(sources)),
        "engine": engine_input,
        "engine_used": resolved_engine,
    }


def _matches_audience(r: Dict[str, Any], audience: List[str]) -> bool:
    text = f"{r.get('company', '')} {r.get('category', '')} {r.get('details', '')} {r.get('keyword', '')}".lower()
    words = [w for a in audience for w in re.findall(r"[a-z0-9]{3,}", a.lower())]
    return any(w in text for w in words)


def _verify_shopify(domain: str, session: requests.Session = None) -> Optional[bool]:
    """True when https://<domain>/products.json?limit=1 answers with Shopify product JSON.
    Uses the project's guarded GET: every redirect hop is checked (no private / local addresses), at most
    200 KB is read, and we identify ourselves (deep_search.HEADERS) instead of pretending to be a browser."""
    if not domain or not re.fullmatch(r"[a-z0-9.-]+\.[a-z]{2,}", domain.lower()):
        return False
    url = f"https://{domain}/products.json?limit=1"
    try:
        status, text, _ = hcm._guarded_get(url, deep_search.HEADERS, 5, deep_search.public_url_guard, 200_000)
        if status == 429:
            return None   # Shopify blocks non-browser clients (HTTP 429 "local_rate_limited"); we do not impersonate
        if status == 200:
            data = json.loads(text)
            return isinstance(data, dict) and isinstance(data.get("products"), list)
    except Exception:  # noqa: BLE001 - verification is optional; any failure just means "not verified"
        pass
    return False


def _run_shopify(engine: str, session: requests.Session, kw: str, place: str,
                 verify_budget: List[int], rows: List[Dict[str, Any]]) -> None:
    queries = [
        f'site:myshopify.com "{kw}"',
        f'"{kw}" "powered by Shopify" {place}'
    ]
    for idx, q in enumerate(queries):
        if idx > 0:
            time.sleep(search_engine.GAP_SECONDS.get(engine, 1.0))
        sites = search_engine.required_sites(q)
        raw_items = search_engine.ENGINE_FUNCS[engine](q, 25, "any", session) or []
        for raw in raw_items:
            url = raw.get("url") or ""
            if not url:
                continue
            if sites and not search_engine.matches_required(url, sites):
                continue
            dom = search_engine.domain_of(url)
            if not dom or search_engine._matches(dom, search_engine.JUNK_DOMAINS):
                continue
            if not sites and search_engine._matches(dom, search_engine.PLATFORM_DOMAINS):
                continue
            if search_engine.ARTICLE_RE.search(raw.get("title") or ""):
                continue

            emails, phones = search_engine.snippet_contacts(f"{raw.get('title', '')} {raw.get('snippet', '')}")
            company = search_engine.clean_title(raw.get("title", "")) or dom
            location = place if place != "India" else ""
            details = ""

            # Check verification budget
            if verify_budget[0] < MAX_VERIFY_REQUESTS:
                verify_budget[0] += 1
                verified = _verify_shopify(dom, session)
                if verified is None:              # blocked: stop verifying for the rest of this search
                    verify_budget[0] = MAX_VERIFY_REQUESTS
                elif verified:
                    details = "Shopify store verified"

            rows.append(make_result(
                "shopify",
                source=SOURCES["shopify"]["name"],
                company=company,
                email=", ".join(emails),
                phone=phones[0] if phones else "",
                website=url,
                location=location,
                category=kw,
                platform="Shopify",
                url=url,
                details=details,
                keyword=kw,
            ))


def _run_woocommerce(engine: str, session: requests.Session, kw: str, place: str,
                     rows: List[Dict[str, Any]]) -> None:
    queries = [
        f'"{kw}" "add to cart" "woocommerce" {place}',
        f'"{kw}" inurl:product-category {place}'
    ]
    for idx, q in enumerate(queries):
        if idx > 0:
            time.sleep(search_engine.GAP_SECONDS.get(engine, 1.0))
        raw_items = search_engine.ENGINE_FUNCS[engine](q, 25, "any", session) or []
        for raw in raw_items:
            url = raw.get("url") or ""
            if not url:
                continue
            dom = search_engine.domain_of(url)
            if not dom or search_engine._matches(dom, search_engine.JUNK_DOMAINS):
                continue
            if search_engine._matches(dom, search_engine.PLATFORM_DOMAINS):
                continue
            if search_engine.ARTICLE_RE.search(raw.get("title") or ""):
                continue

            emails, phones = search_engine.snippet_contacts(f"{raw.get('title', '')} {raw.get('snippet', '')}")
            company = search_engine.clean_title(raw.get("title", "")) or dom
            location = place if place != "India" else ""

            rows.append(make_result(
                "woocommerce",
                source=SOURCES["woocommerce"]["name"],
                company=company,
                email=", ".join(emails),
                phone=phones[0] if phones else "",
                website=url,
                location=location,
                category=kw,
                platform="WooCommerce",
                url=url,
                details="",
                keyword=kw,
            ))


def _run_instagram_shops(engine: str, session: requests.Session, kw: str, place: str,
                         rows: List[Dict[str, Any]]) -> None:
    q = f'site:instagram.com "{kw}" ("shop now" OR "DM to order" OR "order now") {place}'
    sites = search_engine.required_sites(q)
    raw_items = search_engine.ENGINE_FUNCS[engine](q, 30, "any", session) or []
    for raw in raw_items:
        url = raw.get("url") or ""
        if not url:
            continue
        if sites and not search_engine.matches_required(url, sites):
            continue

        match = INSTAGRAM_PROFILE_RE.match(url)
        if not match:
            continue
        handle = match.group(1).lower()
        if handle in INSTAGRAM_EXCLUDED:
            continue

        emails, phones = search_engine.snippet_contacts(f"{raw.get('title', '')} {raw.get('snippet', '')}")
        title_clean = search_engine.clean_title(raw.get("title", ""))
        company = title_clean or f"@{handle}"
        profile_url = f"https://www.instagram.com/{handle}/"
        location = place if place != "India" else ""

        rows.append(make_result(
            "instagram_shops",
            source=SOURCES["instagram_shops"]["name"],
            company=company,
            email=", ".join(emails),
            phone=phones[0] if phones else "",
            website="",
            location=location,
            category=kw,
            platform="Instagram",
            url=profile_url,
            details="",
            keyword=kw,
            instagram=profile_url,
        ))


def _run_source(sid: str, req: Dict[str, Any]) -> Dict[str, Any]:
    t0 = time.time()
    rows, errors = [], []
    session = _session()
    place = search_engine.place_text(req.get("state", ""), req.get("city", ""))
    engine = req.get("engine_used") or search_engine.resolve_engine(req.get("engine") or "auto")
    verify_budget = [0]  # mutable counter for max shopify verifications per search

    stopped_by_rate_limit = False

    for i, kw in enumerate(req["keywords"]):
        if stopped_by_rate_limit:
            break
        if i > 0:
            time.sleep(search_engine.GAP_SECONDS.get(engine, 1.0))

        try:
            if sid == "shopify":
                _run_shopify(engine, session, kw, place, verify_budget, rows)
            elif sid == "woocommerce":
                _run_woocommerce(engine, session, kw, place, rows)
            elif sid == "instagram_shops":
                _run_instagram_shops(engine, session, kw, place, rows)
        except search_engine.RateLimited as e:
            errors.append(f"{kw}: {e}")
            stopped_by_rate_limit = True
        except requests.Timeout:
            errors.append(f"{kw}: {SOURCES[sid]['name']} did not answer in time (server busy) - try again later")
        except requests.ConnectionError:
            errors.append(f"{kw}: could not reach {SOURCES[sid]['name']} - check the internet connection")
        except Exception as e:
            errors.append(f"{kw}: {e.__class__.__name__}: {str(e)[:120]}")

    if req.get("audience") and rows:
        kept = [r for r in rows if _matches_audience(r, req["audience"])]
        if kept:
            rows = kept
        else:
            errors.append("No result mentions the target audience - showing all results")

    status = "ok"
    if stopped_by_rate_limit and not rows:
        status = "error"
    elif errors and not rows and len(errors) >= len(req["keywords"]):
        status = "error"

    return {
        "rows": rows[:MAX_RESULTS_PER_SOURCE * len(req["keywords"])],
        "status": status,
        "errors": errors,
        "seconds": round(time.time() - t0, 1),
    }


def _dedupe_key(r: Dict[str, Any]) -> str:
    if r.get("source_id") == "instagram_shops" or r.get("platform") == "Instagram":
        ig = r.get("instagram") or r.get("url") or ""
        m = INSTAGRAM_PROFILE_RE.match(ig)
        if m:
            return f"ig:{m.group(1).lower()}"
        return f"ig:{re.sub(r'[^a-z0-9_.]', '', r.get('company', '').lower())}"

    dom = search_engine.domain_of(r.get("website") or r.get("url") or "")
    if dom:
        return f"dom:{dom.lower()}"
    return f"cmp:{re.sub(r'[^a-z0-9]', '', r.get('company', '').lower())}"


def _merge_missing_fields(target: Dict[str, Any], donor: Dict[str, Any]) -> None:
    for field in ("email", "phone", "website", "instagram", "facebook", "location", "category", "details"):
        dval = donor.get(field)
        if not dval:
            continue
        tval = target.get(field)
        if not tval:
            target[field] = dval
        elif field == "email" and tval != dval:
            cur_emails = [x.strip() for x in tval.split(",") if x.strip()]
            for cand in [x.strip() for x in dval.split(",") if x.strip()]:
                if cand.lower() not in [x.lower() for x in cur_emails]:
                    cur_emails.append(cand)
            target["email"] = ", ".join(cur_emails)


def search(data: Dict[str, Any]) -> Dict[str, Any]:
    req = validate_request(data)
    engine_used = req["engine_used"]

    with concurrent.futures.ThreadPoolExecutor(max_workers=min(3, len(req["sources"]))) as pool:
        runs = dict(zip(req["sources"], pool.map(lambda sid: _run_source(sid, req), req["sources"])))

    results: List[Dict[str, Any]] = []
    seen: Dict[str, Dict[str, Any]] = {}
    statuses: Dict[str, Dict[str, Any]] = {}

    for sid in req["sources"]:
        run = runs[sid]
        source_count = 0
        for r in run["rows"]:
            if source_count >= MAX_RESULTS_PER_SOURCE:
                break
            k = _dedupe_key(r)
            if k in seen:
                _merge_missing_fields(seen[k], r)
                continue
            seen[k] = r
            results.append(r)
            source_count += 1

        statuses[sid] = {
            "name": SOURCES[sid]["name"],
            "status": run["status"],
            "count": source_count,
            "seconds": run["seconds"],
            "errors": run["errors"],
        }

    # Ordering: rows with email/phone first, then those with a website
    results.sort(key=lambda r: (
        not (r.get("email") or r.get("phone")),
        not r.get("website"),
        r.get("company", "").lower()
    ))

    hint = ""
    if not results and engine_used == "duckduckgo":
        hint = ("DuckDuckGo returned nothing useful for these queries (it often ignores site: and quoted searches "
                "from apps). Add a free BRAVE_SEARCH_API_KEY / SERPER_API_KEY, or run your own SearXNG (SEARXNG_URL, no key), for reliable results.")

    return {
        "query": req,
        "results": results,
        "total": len(results),
        "sources": statuses,
        "engine": engine_used,
        "hint": hint,
    }


def result_to_raw_lead(r: Dict[str, Any]) -> Dict[str, str]:
    desc_parts = []
    if r.get("platform"):
        desc_parts.append(f"Platform: {r['platform']}")
    if r.get("category"):
        desc_parts.append(r["category"])
    if r.get("details"):
        desc_parts.append(r["details"])
    if r.get("instagram"):
        desc_parts.append(f"Instagram: {r['instagram']}")
    if r.get("facebook"):
        desc_parts.append(f"Facebook: {r['facebook']}")

    return {
        "company_name": r.get("company", ""),
        "email": r.get("email", ""),
        "mobile_number": r.get("phone", ""),
        "website": r.get("website", ""),
        "location": r.get("location", ""),
        "description": ". ".join(desc_parts)[:600],
        "source": f"Ecommerce ({r.get('source', r.get('source_id', ''))})",
        "source_url": r.get("url", ""),
        "lead_type": "Ecommerce Store",
    }

"""Scraping / Mining -> Real Estate: builders / developers and property agents.

Sources (checked 2026-11-12):
  karnataka_rera   Karnataka RERA "View All Projects" - public HTML, no captcha. ~10,000 registered projects with
                   project name + promoter (builder) name + registration number. No city / contact details, so
                   Deep Search finds the builder's website. The 6 MB page is cached for 7 days (html_cache).
  osm              OpenStreetMap estate agents / construction companies (free, via crm_sources.search_osm)
  google_places    Google Places "real estate builders / agents in <city>" (GOOGLE_PLACES_API_KEY)
  property_portals 99acres / MagicBricks / Housing.com builder & agent pages found through the search engine
  Unavailable (reason shown in the UI): MahaRERA, GujRERA, Rajasthan RERA (results only via JavaScript),
  Haryana RERA (captcha / blocked), UP RERA (did not respond), Telangana / MP RERA (not checked / down).

We never bypass captchas or logins, and identify ourselves with a descriptive User-Agent on government sites.
"""
import html as html_lib
import re
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Tuple

import requests

import crm_sources
import deep_search
import html_cache_manager as hcm
import maps_sources
import search_engine as se
from job_portals import ALL_INDIA, INDIAN_STATES, PortalError, _session

MAX_KEYWORDS = 5
MAX_RESULTS_PER_SOURCE = 50
LOOKING_FOR = ("builders", "agents", "both")
CITY_RE = re.compile(r"^[A-Za-z .'-]{1,60}$")
GOV_HEADERS = {"User-Agent": "LeadsGenAI/1.0 (real estate directory research; contact via app admin)",
               "Accept-Language": "en-IN,en;q=0.9"}
KARNATAKA_URL = "https://rera.karnataka.gov.in/viewAllProjects"
KARNATAKA_CACHE_DAYS = 7
KARNATAKA_MAX_BYTES = 15 * 1048576
# words that describe the trade, not a builder's name - matching them would match nothing useful
GENERIC_WORDS = {"builder", "builders", "developer", "developers", "real", "estate", "realty", "property", "properties",
                 "project", "projects", "apartment", "apartments", "flat", "flats", "villa", "villas", "plot", "plots",
                 "agent", "agents", "broker", "brokers", "residential", "commercial", "housing", "homes", "home",
                 "construction", "constructions", "infra", "infrastructure", "company", "companies", "in", "and", "the"}

SOURCES = {
    "karnataka_rera": {"name": "Karnataka RERA", "kind": "rera", "key": None, "states": ["Karnataka"],
                       "note": "Registered projects + builder names (official). No contacts: use Deep Search."},
    "osm": {"name": "OpenStreetMap", "kind": "map", "key": None, "states": ["*"],
            "note": "Estate agents and construction companies mapped by volunteers (free)."},
    "google_places": {"name": "Google Places API", "kind": "map", "key": "GOOGLE_PLACES_API_KEY", "states": ["*"],
                      "note": "Builders / agents with phone, website and rating."},
    "property_portals": {"name": "Property portals (99acres, MagicBricks, Housing)", "kind": "portal", "key": None,
                         "states": ["*"], "note": "Builder / agent pages found through the search engine."},
    "maharera": {"name": "MahaRERA (Maharashtra)", "kind": "rera", "unavailable": "Search results load only through JavaScript"},
    "gujrera": {"name": "GujRERA (Gujarat)", "kind": "rera", "unavailable": "The portal is a JavaScript-only app"},
    "rajasthan_rera": {"name": "Rajasthan RERA", "kind": "rera", "unavailable": "The portal is a JavaScript-only app"},
    "haryana_rera": {"name": "Haryana RERA", "kind": "rera", "unavailable": "Blocks automated requests (captcha / HTTP 403)"},
    "up_rera": {"name": "UP RERA", "kind": "rera", "unavailable": "Did not respond to requests"},
}


# ---------------------------------------------------------------------------
# Catalog + validation
# ---------------------------------------------------------------------------

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
                    "reason": reason, "keys": [s["key"]] if s.get("key") else [], "states": s.get("states", ["*"])})
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
    looking_for = data.get("looking_for") or "both"
    if looking_for not in LOOKING_FOR:
        raise ValueError("Looking for must be builders, agents or both")
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
    if "property_portals" in sources and not se.engine_available(engine_used):
        e = se.ENGINES[engine_used]
        raise ValueError(f"{e['name']} needs {e['key']} in .env")
    return {"keywords": keywords, "audience": audience, "state": state, "city": city, "looking_for": looking_for,
            "sources": list(dict.fromkeys(sources)), "engine": engine, "engine_used": engine_used}


def place_of(req: Dict[str, Any]) -> str:
    return req["city"] or (req["state"] if req["state"] != ALL_INDIA else "India")


def make_result(source_id: str, **f) -> Dict[str, Any]:
    out = {"source_id": source_id, "source": SOURCES[source_id]["name"]}
    for k in ("company", "email", "phone", "website", "location", "category", "url", "details", "keyword"):
        v = f.get(k)
        out[k] = str(v or "").strip() if k == "url" else " ".join(str(v or "").split())[:600]
    out["rating"] = f.get("rating")
    out["reviews"] = int(f.get("reviews") or 0)
    out["role"] = f.get("role") or ""              # "builder" | "agent" | ""
    out["kind"] = f.get("kind") or ("website" if out["website"] else "listing")
    return out


# ---------------------------------------------------------------------------
# Karnataka RERA
# ---------------------------------------------------------------------------

_KA_ROW = re.compile(
    r"applicationNameList\s*\.push\('((?:\\'|[^'])*)'\);\s*"
    r"applicationNameList2\s*\.push\('((?:\\'|[^'])*)'\);\s*"
    r"applicationNameList3\s*\.push\('((?:\\'|[^'])*)'\);\s*"
    r"applicationNameList4\s*\.push\('((?:\\'|[^'])*)'\)")


def parse_karnataka(html: str) -> List[Dict[str, str]]:
    """[{ack, reg_no, project, promoter}] in page order (newest registrations first)."""
    rows = []
    for ack, reg, project, promoter in _KA_ROW.findall(html or ""):
        promoter = html_lib.unescape(promoter.replace("\\'", "'")).strip()
        if promoter:
            rows.append({"ack": ack, "reg_no": reg.strip(),
                         "project": html_lib.unescape(project.replace("\\'", "'")).strip(), "promoter": promoter})
    return rows


def search_karnataka(session, keyword: str, req: Dict[str, Any]) -> List[Dict[str, Any]]:
    if req["state"] != "Karnataka":
        raise PortalError("only covers Karnataka - choose Karnataka as the state")
    if req["looking_for"] == "agents":
        raise PortalError("lists builders / promoters only - choose Builders or Both")
    try:
        deep_search.public_url_guard(KARNATAKA_URL)
    except hcm.BlockedUrl as e:
        raise PortalError(str(e))
    html, ok = hcm.fetch_or_get_cached_html(KARNATAKA_URL, headers=GOV_HEADERS, timeout=60,
                                             max_age_days=KARNATAKA_CACHE_DAYS, guard=deep_search.public_url_guard,
                                             max_bytes=KARNATAKA_MAX_BYTES)
    if not ok:
        raise PortalError("Karnataka RERA did not answer - try again later")
    words = [w for w in re.findall(r"[a-z0-9]{3,}", keyword.lower()) if w not in GENERIC_WORDS]
    builders: Dict[str, Dict[str, Any]] = {}
    for row in parse_karnataka(html):
        text = f"{row['project']} {row['promoter']}".lower()
        if words and not all(w in text for w in words):
            continue
        key = re.sub(r"[^a-z0-9]", "", row["promoter"].lower())
        b = builders.setdefault(key, {"promoter": row["promoter"], "projects": [], "reg_nos": [], "count": 0})
        if len(b["projects"]) < 5:
            b["projects"].append(row["project"])
            b["reg_nos"].append(row["reg_no"])
        b["count"] += 1
    out = []
    for b in list(builders.values())[:MAX_RESULTS_PER_SOURCE]:
        out.append(make_result(
            "karnataka_rera", company=b["promoter"].title() if b["promoter"].isupper() else b["promoter"],
            location="Karnataka", category="RERA registered builder / promoter", role="builder", kind="listing",
            # one link per builder (the register page + its first registration number): a shared link would make
            # every builder look like the same lead to the duplicate check
            url=f"{KARNATAKA_URL}?promoter={re.sub(r'[^A-Za-z0-9]+', '-', b['promoter']).strip('-')[:80]}",
            keyword=keyword,
            details=f"{b['count']} RERA project(s): " + "; ".join(f"{p} ({r})" if r else p
                                                                  for p, r in zip(b["projects"], b["reg_nos"]))))
    return out


# ---------------------------------------------------------------------------
# OpenStreetMap / Google Places / property portals
# ---------------------------------------------------------------------------

def _role_queries(req: Dict[str, Any]) -> List[Tuple[str, str]]:
    roles = {"builders": [("builder", "builder")], "agents": [("agent", "real estate")],
             "both": [("builder", "builder"), ("agent", "real estate")]}
    return roles[req["looking_for"]]


def search_osm(session, keyword: str, req: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = []
    for role, osm_kw in _role_queries(req):
        rows = crm_sources.search_osm(session, osm_kw, [], req["state"], req["city"])
        for r in rows:
            out.append(make_result("osm", **{k: r.get(k, "") for k in ("company", "phone", "website", "email",
                                                                       "location", "category", "url")},
                                   role=role, keyword=keyword))
    return out


def search_places(session, keyword: str, req: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = []
    for role, _ in _role_queries(req):
        text = f"{keyword} {'builders developers' if role == 'builder' else 'real estate agents'}"
        for r in maps_sources.search_places(session, text, req["state"], req["city"]):
            out.append(make_result("google_places", **{k: r.get(k, "") for k in ("company", "phone", "website", "email",
                                                                                 "location", "category", "url")},
                                   rating=r.get("rating"), reviews=r.get("reviews"), role=role, keyword=keyword))
    return out


PORTAL_QUERIES = {
    "builder": ['site:99acres.com "{kw}" builders {place}', 'site:magicbricks.com "{kw}" builders {place}',
                'site:housing.com "{kw}" developers {place}'],
    "agent": ['site:99acres.com "{kw}" agents {place}', 'site:magicbricks.com "{kw}" agents {place}'],
}


def search_portals(session, keyword: str, req: Dict[str, Any]) -> List[Dict[str, Any]]:
    engine = req["engine_used"]
    out = []
    for role, _ in _role_queries(req):
        for i, tpl in enumerate(PORTAL_QUERIES[role]):
            if i or out:
                time.sleep(se.GAP_SECONDS[engine])
            q = tpl.format(kw=keyword, place=place_of(req))
            try:
                hits = se.ENGINE_FUNCS[engine](q, 15, "any", requests.Session())
            except se.RateLimited:
                if out:
                    return out
                raise
            sites = se.required_sites(q)
            for h in hits:
                url = h.get("url", "")
                if not se.matches_required(url, sites):
                    continue
                emails, phones = se.snippet_contacts(f"{h.get('title', '')} {h.get('snippet', '')}")
                out.append(make_result("property_portals", company=se.clean_title(h.get("title", "")) or se.domain_of(url),
                                       email=", ".join(emails), phone=phones[0] if phones else "", url=url,
                                       location=place_of(req), category=se.domain_of(url), role=role, kind="listing",
                                       details=(h.get("snippet") or "")[:200], keyword=keyword))
    return out


SEARCH_FUNCS = {"karnataka_rera": search_karnataka, "osm": search_osm, "google_places": search_places,
                "property_portals": search_portals}


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

def _run_source(sid: str, req: Dict[str, Any]) -> Dict[str, Any]:
    t0, rows, errors = time.time(), [], []
    session = _session()
    for i, kw in enumerate(req["keywords"]):
        if i:
            time.sleep(1.0)
        try:
            rows += SEARCH_FUNCS[sid](session, kw, req)
        except PortalError as e:
            errors.append(f"{kw}: {e}")
        except se.RateLimited as e:
            errors.append(f"{kw}: {e}")
            break
        except requests.Timeout:
            errors.append(f"{kw}: {SOURCES[sid]['name']} did not answer in time (server busy) - try again later")
        except requests.ConnectionError:
            errors.append(f"{kw}: could not reach {SOURCES[sid]['name']} - check the internet connection")
        except Exception as e:  # noqa: BLE001 - one source must never fail the whole search
            errors.append(f"{kw}: {e.__class__.__name__}: {str(e)[:120]}")
        if errors and errors[-1].endswith(("choose Karnataka as the state", "choose Builders or Both")):
            return {"rows": [], "status": "skipped", "errors": errors[-1:], "seconds": 0}
    if req["audience"] and rows:
        words = [w for a in req["audience"] for w in re.findall(r"[a-z]{3,}", a.lower())]
        kept = [r for r in rows if any(w in f"{r['company']} {r['category']} {r['details']}".lower() for w in words)]
        if kept:
            rows = kept
        else:
            errors.append("No result mentions the target audience - showing all results")
    status = "error" if errors and not rows else "ok"
    return {"rows": rows, "status": status, "errors": errors, "seconds": round(time.time() - t0, 1)}


MERGE_FIELDS = ("email", "phone", "website", "location", "details")


def _dedupe(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    index, out = {}, []
    for r in rows:
        keys = []
        digits = re.sub(r"\D", "", r.get("phone") or "")[-10:]
        if len(digits) == 10:
            keys.append(("p", digits))
        if r.get("website"):
            keys.append(("w", se.domain_of(r["website"])))
        name = re.sub(r"[^a-z0-9]", "", (r.get("company") or "").lower())
        if name:
            keys.append(("n", name))
        if not keys:
            keys.append(("u", r.get("url", "")))
        kept = next((index[k] for k in keys if k in index), None)
        if kept is not None:
            for f in MERGE_FIELDS:
                if not kept.get(f) and r.get(f):
                    kept[f] = r[f]
            if kept.get("website") and kept.get("kind") == "listing":
                kept["kind"] = "website"
            for k in keys:
                index.setdefault(k, kept)
            continue
        for k in keys:
            index[k] = r
        out.append(r)
    return out


def search(data: Dict[str, Any]) -> Dict[str, Any]:
    req = validate_request(data)
    with ThreadPoolExecutor(max_workers=min(4, len(req["sources"]))) as pool:
        runs = dict(zip(req["sources"], pool.map(lambda sid: _run_source(sid, req), req["sources"])))
    all_rows, statuses = [], {}
    for sid in req["sources"]:
        run = runs[sid]
        rows = run["rows"][:MAX_RESULTS_PER_SOURCE * len(req["keywords"])]
        all_rows += rows
        statuses[sid] = {"name": SOURCES[sid]["name"], "status": run["status"], "count": len(rows),
                         "seconds": run["seconds"], "errors": run["errors"]}
    results = _dedupe(all_rows)
    for sid in statuses:  # counts after dedupe
        statuses[sid]["count"] = sum(1 for r in results if r["source_id"] == sid)
    results.sort(key=lambda r: (not (r["phone"] or r["email"]), not r["website"], -(r["rating"] or 0)))
    hint = ""
    if "property_portals" in req["sources"] and req["engine_used"] == "duckduckgo" and \
            not any(r["source_id"] == "property_portals" for r in results):
        hint = ("DuckDuckGo returned nothing for the property portals. Add a free BRAVE_SEARCH_API_KEY or "
                "SERPER_API_KEY in Settings > API Keys for reliable results.")
    return {"query": {k: req[k] for k in ("keywords", "audience", "state", "city", "looking_for", "engine")},
            "results": results, "total": len(results), "sources": statuses, "engine": req["engine_used"], "hint": hint}


def result_to_raw_lead(r: Dict[str, Any]) -> Dict[str, str]:
    role = {"builder": "Builder / Developer", "agent": "Property Agent"}.get(r.get("role", ""), "Real Estate")
    details = [r.get("category", ""), r.get("details", "")]
    if r.get("rating"):
        details.append(f"Google rating {r['rating']} ({r.get('reviews', 0)} reviews)")
    return {
        "company_name": r.get("company", ""),
        "email": r.get("email", ""),
        "mobile_number": r.get("phone", ""),
        "website": r.get("website", ""),
        "location": r.get("location", ""),
        "description": ". ".join(x for x in details if x)[:600],
        "source": f"Real Estate ({SOURCES.get(r.get('source_id', ''), {}).get('name', r.get('source', ''))})",
        "source_url": r.get("url", ""),
        "lead_type": f"Real Estate - {role}",
    }

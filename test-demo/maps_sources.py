"""Scraping / Mining -> Google Maps: local businesses by category and place.

Sources:
  osm            OpenStreetMap (Overpass)   free, no key - name, phone, website, email, address when mapped
  google_places  Google Places API (New)    GOOGLE_PLACES_API_KEY - the same data Google Maps shows
                                            (name, phone, website, address, rating, reviews, Maps link)
  google_maps    Google Maps page scraping  unavailable: against Google's terms and blocked quickly

Filters:
  website  any | with | without   - "without" = businesses with no website: direct leads for a website offer
  min_rating 0..4.5              - Google Places only (OpenStreetMap has no ratings)
  audience                        - keeps results whose name / category mention an audience word; if that
                                    leaves nothing for a source, the unfiltered results are kept (with a note)
"""
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List

import requests

import crm_sources
from job_portals import ALL_INDIA, INDIAN_STATES, PortalError, _session

MAX_KEYWORDS = 5
MAX_LEN = 80
MAX_AUDIENCE = 5
MAX_RESULTS_PER_SOURCE = 60
MIN_RATINGS = (0, 3, 3.5, 4, 4.5)
WEBSITE_FILTERS = ("any", "with", "without")
CITY_RE = re.compile(r"^[A-Za-z .'-]{1,60}$")
GAP_SECONDS = 1.0

SOURCES = {
    "osm": {"name": "OpenStreetMap", "kind": "map", "key": None,
            "note": "Free. Phone / website only where volunteers mapped them. Needs a state or city."},
    "google_places": {"name": "Google Places API", "kind": "map", "key": "GOOGLE_PLACES_API_KEY",
                      "note": "Same data as Google Maps incl. rating and reviews. Free monthly quota, card needed."},
    "google_maps": {"name": "Google Maps (page scraping)", "kind": "map", "key": None, "unavailable":
                    "Scraping google.com/maps is against Google's terms and gets blocked - use the Places API"},
}


def _key_set(name: str) -> bool:
    return bool(name and os.getenv(name, "").strip())


def source_status(sid: str) -> str:
    s = SOURCES[sid]
    if s.get("unavailable"):
        return "unavailable"
    if s["key"] and not _key_set(s["key"]):
        return "needs_key"
    return "available"


def list_sources() -> List[Dict[str, Any]]:
    out = []
    for sid, s in SOURCES.items():
        st = source_status(sid)
        reason = s.get("unavailable") or (f"Add {s['key']} in .env (Settings > API Keys)" if st == "needs_key" else "")
        out.append({"id": sid, "name": s["name"], "kind": s["kind"], "status": st, "note": s.get("note", ""),
                    "reason": reason, "keys": [s["key"]] if s["key"] else []})
    return out


def _clean_list(values: Any, label: str, max_items: int, max_len: int, required: bool) -> List[str]:
    if values is None:
        values = []
    if not isinstance(values, list):
        raise ValueError(f"{label} must be a list")
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
    keywords = _clean_list(data.get("keywords"), "Keyword", MAX_KEYWORDS, MAX_LEN, True)
    audience = _clean_list(data.get("audience"), "Target audience", MAX_AUDIENCE, 60, False)
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
    try:
        min_rating = float(data.get("min_rating") or 0)
    except (TypeError, ValueError):
        raise ValueError("Minimum rating must be a number")
    if min_rating not in MIN_RATINGS:
        raise ValueError("Minimum rating must be one of 0, 3, 3.5, 4, 4.5")
    website = data.get("website") or "any"
    if website not in WEBSITE_FILTERS:
        raise ValueError("Website filter must be any, with or without")
    return {"keywords": keywords, "audience": audience, "state": state, "city": city,
            "sources": list(dict.fromkeys(sources)), "min_rating": min_rating, "website": website}


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------

def make_result(source_id: str, **f) -> Dict[str, Any]:
    out = crm_sources.make_result(source_id, **{k: v for k, v in f.items() if k not in ("rating", "reviews")})
    out["source"] = SOURCES[source_id]["name"]
    out["rating"] = f.get("rating")          # float or None
    out["reviews"] = int(f.get("reviews") or 0)
    out["no_website"] = not out["website"]
    return out


def search_places(session, keyword: str, state: str, city: str) -> List[Dict[str, Any]]:
    key = os.getenv("GOOGLE_PLACES_API_KEY", "").strip()
    if not key:
        raise PortalError("GOOGLE_PLACES_API_KEY not set in .env")
    place = city or (state if state != ALL_INDIA else "India")
    body = {"textQuery": f"{keyword} in {place}, India", "pageSize": 20, "regionCode": "IN"}
    headers = {"X-Goog-Api-Key": key, "X-Goog-FieldMask": crm_sources.PLACES_FIELDS, "Content-Type": "application/json"}
    out = []
    for page in range(3):  # Text Search returns at most 60 results (3 pages of 20)
        r = session.post("https://places.googleapis.com/v1/places:searchText", json=body, headers=headers, timeout=25)
        if r.status_code in (400, 403) and "API key" in r.text:
            raise PortalError(f"Google rejected the API key (HTTP {r.status_code})")
        crm_sources._api_error(r, "Google Places")
        data = r.json() or {}
        for p in data.get("places") or []:
            if p.get("businessStatus") and p["businessStatus"] != "OPERATIONAL":
                continue
            out.append(make_result(
                "google_places", company=(p.get("displayName") or {}).get("text"),
                phone=p.get("nationalPhoneNumber") or p.get("internationalPhoneNumber"), website=p.get("websiteUri"),
                location=p.get("formattedAddress"), category=(p.get("primaryType") or "").replace("_", " "),
                url=p.get("googleMapsUri"), rating=p.get("rating"), reviews=p.get("userRatingCount"), keyword=keyword))
        token = data.get("nextPageToken")
        if not token:
            break
        body = {**body, "pageToken": token}
        time.sleep(GAP_SECONDS)
    return out


def search_osm(session, keyword: str, state: str, city: str) -> List[Dict[str, Any]]:
    rows = crm_sources.search_osm(session, keyword, [], state, city)
    return [make_result("osm", **{k: r.get(k, "") for k in ("company", "phone", "website", "email", "location",
                                                             "category", "url")}, keyword=keyword) for r in rows]


SEARCH_FUNCS = {"osm": search_osm, "google_places": search_places}


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

def _dedupe_key(r: Dict[str, Any]) -> str:
    digits = re.sub(r"\D", "", r.get("phone") or "")[-10:]
    if len(digits) == 10:
        return "p:" + digits
    if r.get("website"):
        host = re.sub(r"^https?://(www\.)?", "", r["website"].lower()).split("/")[0]
        return "w:" + host
    return "n:" + re.sub(r"[^a-z0-9]", "", (r.get("company") or "").lower()) + "|" + \
        re.sub(r"[^a-z0-9]", "", (r.get("location") or "").lower())[:30]


def _matches_audience(r: Dict[str, Any], audience: List[str]) -> bool:
    text = f"{r.get('company', '')} {r.get('category', '')} {r.get('details', '')}".lower()
    words = [w for a in audience for w in re.findall(r"[a-z]{3,}", a.lower())]
    return any(w in text for w in words)


def _run_source(sid: str, req: Dict[str, Any]) -> Dict[str, Any]:
    t0, rows, errors = time.time(), [], []
    session = _session()
    for i, kw in enumerate(req["keywords"]):
        if i:
            time.sleep(GAP_SECONDS)
        try:
            rows += SEARCH_FUNCS[sid](session, kw, req["state"], req["city"])
        except PortalError as e:
            errors.append(f"{kw}: {e}")
        except requests.Timeout:
            errors.append(f"{kw}: {SOURCES[sid]['name']} did not answer in time (server busy) - try again later")
        except requests.ConnectionError:
            errors.append(f"{kw}: could not reach {SOURCES[sid]['name']} - check the internet connection")
        except Exception as e:  # noqa: BLE001 - one keyword failing must not stop the others
            errors.append(f"{kw}: {e.__class__.__name__}: {str(e)[:120]}")
    if req["audience"] and rows:
        kept = [r for r in rows if _matches_audience(r, req["audience"])]
        if kept:
            rows = kept
        else:
            errors.append("No result mentions the target audience - showing all results")
    status = "error" if errors and not rows and len(errors) >= len(req["keywords"]) else "ok"
    return {"rows": rows[:MAX_RESULTS_PER_SOURCE * len(req["keywords"])], "status": status, "errors": errors,
            "seconds": round(time.time() - t0, 1)}


def search(data: Dict[str, Any]) -> Dict[str, Any]:
    req = validate_request(data)
    with ThreadPoolExecutor(max_workers=len(req["sources"])) as pool:
        runs = dict(zip(req["sources"], pool.map(lambda sid: _run_source(sid, req), req["sources"])))
    results, seen, statuses = [], set(), {}
    hidden = {"rating": 0, "website": 0}
    for sid in req["sources"]:
        run = runs[sid]
        count = 0
        for r in run["rows"]:
            if req["website"] == "with" and r["no_website"] or req["website"] == "without" and not r["no_website"]:
                hidden["website"] += 1
                continue
            if req["min_rating"] and r["rating"] is not None and r["rating"] < req["min_rating"]:
                hidden["rating"] += 1
                continue
            k = _dedupe_key(r)
            if k in seen:
                continue
            seen.add(k)
            results.append(r)
            count += 1
        statuses[sid] = {"name": SOURCES[sid]["name"], "status": run["status"], "count": count,
                         "seconds": run["seconds"], "errors": run["errors"]}
    results.sort(key=lambda r: (not r["phone"], -(r["rating"] or 0), -r["reviews"]))
    return {"query": req, "results": results, "total": len(results), "sources": statuses, "hidden": hidden}


def result_to_raw_lead(r: Dict[str, Any]) -> Dict[str, str]:
    details = [r.get("category", "")]
    if r.get("rating"):
        details.append(f"Google rating {r['rating']} ({r.get('reviews', 0)} reviews)")
    if not r.get("website"):
        details.append("No website listed - website / digital presence opportunity")
    if r.get("details"):
        details.append(r["details"])
    return {
        "company_name": r.get("company", ""),
        "email": r.get("email", ""),
        "mobile_number": r.get("phone", ""),
        "website": r.get("website", ""),
        "location": r.get("location", ""),
        "description": ". ".join(x for x in details if x)[:600],
        "source": f"Google Maps ({SOURCES.get(r.get('source_id', ''), {}).get('name', r.get('source', ''))})",
        "source_url": r.get("url", ""),
        "lead_type": "Local Business",
    }

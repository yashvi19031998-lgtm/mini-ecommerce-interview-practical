"""Scraping / Mining -> Global Directories (companies outside India from official / open sources).

Wired into app.py (/api/global-directories/*), frontend/lib/api.js, and frontend/app/page.js.
Entry points: list_sources(), validate_request(data), search(data), result_to_raw_lead(result).
"""

import concurrent.futures
import os
import re
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from job_portals import PortalError, slugify, _clean, _get, _session

MAX_KEYWORDS = 10
MAX_RESULTS_PER_SOURCE = 50
REQUEST_GAP_SECONDS = 1.0
OSM_USER_AGENT = "LeadsGenAI/1.0 (global business directory search; contact via app admin)"

# ---------------------------------------------------------------------------
# Supported Countries (outside India, sorted by name)
# ---------------------------------------------------------------------------

COUNTRIES: List[Dict[str, str]] = [
    {"id": "AU", "name": "Australia"},
    {"id": "CA", "name": "Canada"},
    {"id": "FR", "name": "France"},
    {"id": "DE", "name": "Germany"},
    {"id": "IE", "name": "Ireland"},
    {"id": "IL", "name": "Israel"},
    {"id": "IT", "name": "Italy"},
    {"id": "JP", "name": "Japan"},
    {"id": "KE", "name": "Kenya"},
    {"id": "MY", "name": "Malaysia"},
    {"id": "NL", "name": "Netherlands"},
    {"id": "NZ", "name": "New Zealand"},
    {"id": "NG", "name": "Nigeria"},
    {"id": "PH", "name": "Philippines"},
    {"id": "QA", "name": "Qatar"},
    {"id": "SA", "name": "Saudi Arabia"},
    {"id": "SG", "name": "Singapore"},
    {"id": "ZA", "name": "South Africa"},
    {"id": "ES", "name": "Spain"},
    {"id": "SE", "name": "Sweden"},
    {"id": "CH", "name": "Switzerland"},
    {"id": "AE", "name": "United Arab Emirates"},
    {"id": "GB", "name": "United Kingdom"},
    {"id": "US", "name": "United States"},
]

US_STATES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR", "california": "CA",
    "colorado": "CO", "connecticut": "CT", "delaware": "DE", "florida": "FL", "georgia": "GA",
    "hawaii": "HI", "idaho": "ID", "illinois": "IL", "indiana": "IN", "iowa": "IA",
    "kansas": "KS", "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS", "missouri": "MO",
    "montana": "MT", "nebraska": "NE", "nevada": "NV", "new hampshire": "NH", "new jersey": "NJ",
    "new mexico": "NM", "new york": "NY", "north carolina": "NC", "north dakota": "ND", "ohio": "OH",
    "oklahoma": "OK", "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT", "vermont": "VT",
    "virginia": "VA", "washington": "WA", "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
    "district of columbia": "DC"
}

# OpenStreetMap keyword fragment -> tag filters
OSM_TAGS = {
    "software": ['"office"="it"', '"office"="company"'], "it ": ['"office"="it"'], "it company": ['"office"="it"'],
    "web": ['"office"="it"'], "tech": ['"office"="it"'],
    "real estate": ['"office"="estate_agent"'], "builder": ['"office"="estate_agent"', '"office"="construction_company"'],
    "construction": ['"office"="construction_company"'],
    "hospital": ['"amenity"="hospital"'], "clinic": ['"amenity"="clinic"', '"amenity"="doctors"'],
    "doctor": ['"amenity"="doctors"'], "dentist": ['"amenity"="dentist"'], "pharmacy": ['"amenity"="pharmacy"'],
    "school": ['"amenity"="school"'], "college": ['"amenity"="college"', '"amenity"="university"'],
    "hotel": ['"tourism"="hotel"'], "restaurant": ['"amenity"="restaurant"'], "cafe": ['"amenity"="cafe"'],
    "lawyer": ['"office"="lawyer"'], "law firm": ['"office"="lawyer"'], "accountant": ['"office"="accountant"'],
    "insurance": ['"office"="insurance"'], "bank": ['"amenity"="bank"'], "finance": ['"office"="financial"'],
    "manufactur": ['"man_made"="works"', '"industrial"'], "factory": ['"man_made"="works"', '"industrial"'],
    "logistics": ['"office"="logistics"'], "transport": ['"office"="logistics"'], "company": ['"office"="company"'],
    "agency": ['"office"="company"'], "consulting": ['"office"="consulting"'],
}


# ---------------------------------------------------------------------------
# Result helper
# ---------------------------------------------------------------------------

def make_result(source_id: str, **fields) -> Dict[str, str]:
    keys = ("source", "company", "contact_name", "contact_title", "email", "phone", "website", "location",
            "country", "category", "url", "linkedin", "details", "keyword")
    out = {"source_id": source_id}
    out.update({k: str(fields.get(k) or "") for k in keys})
    return out


# ---------------------------------------------------------------------------
# Source Parsers
# ---------------------------------------------------------------------------

def _osm_filters(keyword: str) -> List[str]:
    kw = f"{keyword.lower()} "
    tags = []
    for frag, t in OSM_TAGS.items():
        if frag in kw:
            tags.extend(t)
    return list(dict.fromkeys(tags))


def search_osm(session: requests.Session, keyword: str, req: Dict[str, Any]) -> List[Dict[str, str]]:
    city = req.get("city", "")
    region = req.get("region", "")
    country = req.get("country", "")
    area_name = city or region
    if not area_name:
        raise PortalError("OpenStreetMap needs a city or region")

    generic = {"company", "companies", "services", "service", "shop", "shops", "store", "firm", "agency", "business"}
    words = [w for w in re.findall(r"[a-z]{4,}", keyword.lower()) if w not in generic]
    clauses = [f"nwr[{t}](area.a);" for t in _osm_filters(keyword)]
    if words:
        clauses += [f'nwr["name"~"{re.escape(words[0])}",i][{k}](area.a);' for k in ('"office"', '"craft"', '"shop"')]
    if not clauses:
        raise PortalError(f"no OpenStreetMap category matches '{keyword}' - try e.g. software, hospital, school, hotel")

    country_clause = f'area["ISO3166-1"="{country}"]->.country;' if country else ""
    in_country = "(area.country)" if country else ""
    query = (
        f'[out:json][timeout:25];'
        f'{country_clause}'
        f'area["name"="{area_name}"]{in_country}->.a;'
        f'({"".join(clauses)});'
        f'out center tags {MAX_RESULTS_PER_SOURCE * 2};'
    )

    for attempt in range(2):
        r = session.post("https://overpass-api.de/api/interpreter", data={"data": query},
                         headers={"User-Agent": OSM_USER_AGENT, "Accept": "*/*"}, timeout=35)
        if r.status_code not in (502, 504) or attempt:
            break
        time.sleep(5)

    if r.status_code in (406, 429, 502, 504):
        raise PortalError(f"OpenStreetMap is busy (HTTP {r.status_code}) - try again in a minute")
    r.raise_for_status()

    results = []
    for el in r.json().get("elements", []):
        tags = el.get("tags") or {}
        name = tags.get("name") or tags.get("name:en")
        if not name:
            continue
        addr = ", ".join(x for x in (tags.get("addr:housenumber"), tags.get("addr:street"), tags.get("addr:suburb"),
                                     tags.get("addr:city"), tags.get("addr:postcode")) if x)
        category = next((f"{k}: {tags[k]}" for k in ("office", "shop", "craft", "amenity", "industrial", "tourism") if tags.get(k)), "")
        results.append(make_result(
            "osm", source=SOURCES["osm"]["name"], company=name,
            website=tags.get("website") or tags.get("contact:website") or tags.get("url"),
            phone=tags.get("phone") or tags.get("contact:phone") or tags.get("contact:mobile"),
            email=tags.get("email") or tags.get("contact:email"),
            location=addr or area_name, country=country, category=category,
            url=f"https://www.openstreetmap.org/{el.get('type')}/{el.get('id')}",
            keyword=keyword,
        ))

    results.sort(key=lambda x: (not (x["website"] or x["phone"] or x["email"])))
    return results[:MAX_RESULTS_PER_SOURCE]


def search_companies_house(session: requests.Session, keyword: str, req: Dict[str, Any]) -> List[Dict[str, str]]:
    country = req.get("country", "")
    if country != "GB":
        raise PortalError("UK Companies House only covers the United Kingdom (GB)")

    key = os.getenv("COMPANIES_HOUSE_API_KEY", "").strip()
    if not key:
        raise PortalError("COMPANIES_HOUSE_API_KEY not set in .env")

    url = "https://api.company-information.service.gov.uk/advanced-search/companies"
    params = {
        "company_name_includes": keyword,
        "company_status": "active",
        "size": min(MAX_RESULTS_PER_SOURCE, 50),
    }
    if req.get("city"):
        params["location"] = req["city"]

    r = session.get(url, params=params, auth=(key, ""), timeout=25)
    if r.status_code == 401:
        raise PortalError("Invalid or unauthorized COMPANIES_HOUSE_API_KEY")
    if r.status_code in (403, 429):
        raise PortalError(f"Companies House rate limit or access block (HTTP {r.status_code})")
    r.raise_for_status()

    items = r.json().get("items", [])
    results = []
    for it in items:
        name = _clean(it.get("company_name", "")).title()
        cnum = str(it.get("company_number", "")).strip()
        if not name:
            continue
        addr_obj = it.get("registered_office_address") or {}
        loc = ", ".join(x for x in (
            addr_obj.get("address_line_1"),
            addr_obj.get("locality"),
            addr_obj.get("region"),
            addr_obj.get("postal_code")
        ) if x)
        sic_codes = it.get("sic_codes") or []
        category = f"SIC: {', '.join(sic_codes)}" if sic_codes else "Registered UK Company"
        ch_url = f"https://find-and-update.company-information.service.gov.uk/company/{cnum}" if cnum else ""
        details = f"Company Number {cnum} · Status: {it.get('company_status', 'active')}"
        results.append(make_result(
            "companies_house", source=SOURCES["companies_house"]["name"],
            company=name, location=loc or req.get("city") or "United Kingdom",
            country="GB", category=category, url=ch_url, details=details, keyword=keyword
        ))
    return results[:MAX_RESULTS_PER_SOURCE]


def search_sec_edgar(session: requests.Session, keyword: str, req: Dict[str, Any]) -> List[Dict[str, str]]:
    country = req.get("country", "")
    if country != "US":
        raise PortalError("US SEC EDGAR only covers the United States (US)")

    ua = os.getenv("SEC_USER_AGENT", "").strip()
    if not ua:
        raise PortalError("SEC_USER_AGENT not set in .env")

    region = req.get("region", "")
    state_code = ""
    if region:
        reg_clean = region.strip().lower()
        state_code = reg_clean.upper() if len(reg_clean) == 2 else US_STATES.get(reg_clean, "")

    # Primary: efts.sec.gov search-index JSON API
    url = "https://efts.sec.gov/LATEST/search-index"
    params = {"q": keyword}
    if state_code:
        params["biz_states"] = state_code
    elif req.get("city"):
        params["q"] = f"{keyword} {req['city']}"

    try:
        r = session.get(url, params=params, headers={"User-Agent": ua}, timeout=25)
        if r.status_code == 429:
            raise PortalError("SEC EDGAR rate limit (HTTP 429)")
        r.raise_for_status()
        hits = r.json().get("hits", {}).get("hits", [])
        results = []
        for h in hits:
            s = h.get("_source", {})
            names = s.get("display_names") or []
            disp = names[0] if names else ""
            comp_name = re.sub(r"\s*\(CIK\s*\d+\)", "", disp).strip()
            comp_name = re.sub(r"\s*/[A-Z0-9]+/$", "", comp_name).strip()
            if not comp_name:
                continue
            ciks = s.get("ciks") or []
            cik = str(ciks[0]).zfill(10) if ciks else ""
            locations = s.get("biz_locations") or []
            loc = locations[0] if locations else (state_code or "United States")
            sics = s.get("sics") or []
            sic = sics[0] if sics else ""
            category = f"SIC: {sic}" if sic else "US Public Company"
            edgar_url = f"https://www.sec.gov/edgar/browse/?CIK={cik}" if cik else "https://www.sec.gov/edgar/searchedgar/companysearch"
            details = f"CIK {cik} · SEC Form {s.get('form', '10-K')}"
            results.append(make_result(
                "sec_edgar", source=SOURCES["sec_edgar"]["name"],
                company=comp_name.title(), location=loc, country="US",
                category=category, url=edgar_url, details=details, keyword=keyword
            ))
        if results:
            return results[:MAX_RESULTS_PER_SOURCE]
    except PortalError:
        raise
    except Exception:
        pass

    # Fallback: browse-edgar atom XML feed
    atom_params = {"company": keyword, "type": "10-K", "owner": "include", "count": 40,
                   "action": "getcompany", "output": "atom"}
    if state_code:
        atom_params["State"] = state_code
    r = session.get("https://www.sec.gov/cgi-bin/browse-edgar", params=atom_params,
                    headers={"User-Agent": ua, "Accept": "application/atom+xml"}, timeout=25)
    if r.status_code == 429:
        raise PortalError("SEC EDGAR rate limit (HTTP 429)")
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "xml")
    results = []
    for entry in soup.find_all("entry"):
        link_el = entry.find("link")
        link = link_el.get("href") if link_el else ""
        summary_el = entry.find("summary")
        summary_text = summary_el.text if summary_el else ""
        cik_match = re.search(r"CIK:\s*(\d+)", summary_text)
        cik = cik_match.group(1).zfill(10) if cik_match else ""
        sic_match = re.search(r"SIC:\s*([^<\n,]+)", summary_text)
        sic = sic_match.group(1).strip() if sic_match else ""

        phone = ""
        loc = state_code or "United States"
        addr = entry.find("address", type="business")
        if addr:
            city_el = addr.find("city")
            state_el = addr.find("state")
            phone_el = addr.find("phone")
            if phone_el:
                phone = phone_el.text.strip()
            if city_el and state_el:
                loc = f"{city_el.text.strip()}, {state_el.text.strip()}"

        title_el = entry.find("title")
        t_text = title_el.text.strip() if title_el else ""
        if t_text and not t_text.startswith("ARRAY("):
            comp_name = t_text
        else:
            comp_name = f"SEC Registered Company (CIK {cik})" if cik else "SEC Registered Entity"

        results.append(make_result(
            "sec_edgar", source=SOURCES["sec_edgar"]["name"],
            company=comp_name, phone=phone, location=loc, country="US",
            category=f"SIC: {sic}" if sic else "US Public Company",
            url=link or f"https://www.sec.gov/edgar/browse/?CIK={cik}",
            details=f"CIK {cik} · SEC Filing", keyword=keyword
        ))
    return results[:MAX_RESULTS_PER_SOURCE]


def search_goodfirms(session: requests.Session, keyword: str, req: Dict[str, Any]) -> List[Dict[str, str]]:
    city = req.get("city", "")
    if not city:
        raise PortalError("GoodFirms needs a city")

    city_slug = slugify(city)
    url = f"https://www.goodfirms.co/directory/city/top-software-development-companies/{city_slug}"
    r = _get(session, url)
    soup = BeautifulSoup(r.text, "html.parser")
    results = []
    country = req.get("country", "")
    for card in soup.select(".firm-wrapper-item"):
        profile = card.select_one('a[href*="/company/"]')
        name_el = card.select_one(".firm-name, h3, h2") or profile
        name = _clean(name_el.get_text()) if name_el else ""
        if not name:
            continue
        site = next((a["href"].split("?")[0] for a in card.select("a[href^='http']")
                     if not urlparse(a["href"]).netloc.lower().endswith("goodfirms.co")), "")
        loc_el = card.select_one(".firm-location, .location, [class*='location']")
        prof = profile["href"] if profile else ""
        prof_url = prof if prof.startswith("http") else (f"https://www.goodfirms.co{prof}" if prof else "")
        results.append(make_result(
            "goodfirms", source=SOURCES["goodfirms"]["name"],
            company=name, website=site, location=_clean(loc_el.get_text()) if loc_el else city,
            country=country, category="Software development company",
            url=prof_url, details="IT service company (possible partner, not a buyer)",
            keyword=keyword,
        ))
    return results[:MAX_RESULTS_PER_SOURCE]


# ---------------------------------------------------------------------------
# Source Registry
# ---------------------------------------------------------------------------

SOURCES: Dict[str, Dict[str, Any]] = {
    "osm": {
        "id": "osm",
        "name": "OpenStreetMap (worldwide)",
        "kind": "directory",
        "keys": [],
        "countries": ["*"],
        "note": "Worldwide open business directory via Overpass API",
        "reason": "",
        "search": search_osm,
    },
    "companies_house": {
        "id": "companies_house",
        "name": "UK Companies House",
        "kind": "register",
        "keys": ["COMPANIES_HOUSE_API_KEY"],
        "countries": ["GB"],
        "note": "Official UK company register",
        "reason": "COMPANIES_HOUSE_API_KEY not set in .env",
        "search": search_companies_house,
    },
    "sec_edgar": {
        "id": "sec_edgar",
        "name": "US SEC EDGAR",
        "kind": "register",
        "keys": ["SEC_USER_AGENT"],
        "countries": ["US"],
        "note": "US public company filings & registration",
        "reason": "SEC_USER_AGENT not set in .env",
        "search": search_sec_edgar,
    },
    "goodfirms": {
        "id": "goodfirms",
        "name": "GoodFirms (worldwide)",
        "kind": "directory",
        "keys": [],
        "countries": ["*"],
        "note": "IT and software companies by city",
        "reason": "",
        "search": search_goodfirms,
    },
    "opencorporates": {
        "id": "opencorporates",
        "name": "OpenCorporates",
        "kind": "register",
        "keys": [],
        "countries": ["*"],
        "note": "Global company registry",
        "reason": "API is paid for commercial use",
        "search": None,
    },
    "yelp": {
        "id": "yelp",
        "name": "Yelp",
        "kind": "directory",
        "keys": [],
        "countries": ["*"],
        "note": "Local business reviews & directory",
        "reason": "Fusion API needs a paid plan for commercial use",
        "search": None,
    },
    "clutch": {
        "id": "clutch",
        "name": "Clutch",
        "kind": "directory",
        "keys": [],
        "countries": ["*"],
        "note": "B2B ratings & reviews directory",
        "reason": "Blocks automated requests (Cloudflare)",
        "search": None,
    },
    "europages": {
        "id": "europages",
        "name": "Europages / Kompass",
        "kind": "directory",
        "keys": [],
        "countries": ["*"],
        "note": "European B2B directory",
        "reason": "Listings blocked or behind login for automated access",
        "search": None,
    },
}


def _status(src: Dict[str, Any]) -> str:
    if src["keys"]:
        for k in src["keys"]:
            if not os.getenv(k, "").strip():
                return "needs_key"
    if src.get("search") is None:
        return "unavailable"
    return "available"


def list_sources() -> List[Dict[str, Any]]:
    out = []
    for s in SOURCES.values():
        st = _status(s)
        item = {
            "id": s["id"],
            "name": s["name"],
            "kind": s["kind"],
            "status": st,
            "note": s.get("note", ""),
            "reason": s.get("reason", "") if st != "available" else "",
            "keys": s.get("keys", []),
            "countries": s.get("countries", ["*"]),
        }
        out.append(item)
    return out


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_request(data: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("Invalid request format")

    # 1. keywords: list of 1..MAX_KEYWORDS, each max 80 chars, deduplicated case-insensitively, no "
    keywords_raw = data.get("keywords")
    if not isinstance(keywords_raw, list):
        raise ValueError("Keywords must be a list")

    keywords = []
    seen_kw = set()
    for k in keywords_raw:
        if not isinstance(k, str):
            continue
        cleaned = _clean(k)
        if not cleaned:
            continue
        if '"' in cleaned:
            raise ValueError('Keywords cannot contain quotes (")')
        if len(cleaned) > 80:
            raise ValueError("Each of the keywords must be 80 characters or less")
        if cleaned.lower() not in seen_kw:
            seen_kw.add(cleaned.lower())
            keywords.append(cleaned)

    if not keywords:
        raise ValueError("Enter at least one keyword")
    if len(keywords) > MAX_KEYWORDS:
        raise ValueError(f"Enter at most {MAX_KEYWORDS} keywords")

    # 2. audience: optional list of at most 5, each at most 60 chars
    audience_raw = data.get("audience")
    audience = []
    if audience_raw is not None:
        if not isinstance(audience_raw, list):
            raise ValueError("Audience must be a list")
        seen_aud = set()
        for a in audience_raw:
            if not isinstance(a, str):
                continue
            cleaned = _clean(a)
            if not cleaned:
                continue
            if len(cleaned) > 60:
                raise ValueError("Each audience target must be 60 characters or less")
            if cleaned.lower() not in seen_aud:
                seen_aud.add(cleaned.lower())
                audience.append(cleaned)
        if len(audience) > 5:
            raise ValueError("Enter at most 5 audience targets")

    # 3. country: required and must be in COUNTRIES
    country = str(data.get("country") or "").strip().upper()
    valid_country_ids = {c["id"] for c in COUNTRIES}
    if not country or country not in valid_country_ids:
        raise ValueError("Select a country")

    # 4. city / region: optional. Letters, spaces and .'- only, max 60 chars
    city = _clean(data.get("city") or "")
    if city:
        if len(city) > 60 or not re.fullmatch(r"[A-Za-z .'-]+", city):
            raise ValueError("City must be letters only (max 60 characters)")

    region = _clean(data.get("region") or "")
    if region:
        if len(region) > 60 or not re.fullmatch(r"[A-Za-z .'-]+", region):
            raise ValueError("Region must be letters only (max 60 characters)")

    # 5. sources: non-empty list of known ids, all available now
    source_ids = data.get("sources")
    if not isinstance(source_ids, list) or not source_ids:
        raise ValueError("Select at least one source")

    clean_sources = list(dict.fromkeys(source_ids))
    for sid in clean_sources:
        if sid not in SOURCES:
            raise ValueError(f"Unknown source: {sid}")
        st = _status(SOURCES[sid])
        if st == "needs_key":
            key_name = SOURCES[sid]["keys"][0] if SOURCES[sid]["keys"] else "API key"
            raise ValueError(f"{SOURCES[sid]['name']} needs {key_name} in .env")
        if st == "unavailable":
            raise ValueError(f"{SOURCES[sid]['name']} is not available: {SOURCES[sid]['reason']}")

    return {
        "keywords": keywords,
        "audience": audience,
        "country": country,
        "region": region,
        "city": city,
        "sources": clean_sources,
    }


# ---------------------------------------------------------------------------
# Search Orchestration
# ---------------------------------------------------------------------------

def _run_source(sid: str, req: Dict[str, Any]) -> Dict[str, Any]:
    src = SOURCES[sid]
    session = _session()
    results, errors, started = [], [], time.time()

    country = req.get("country", "")
    city = req.get("city", "")
    region = req.get("region", "")

    # Pre-checks for skip conditions
    if sid == "osm" and not (city or region):
        return {"results": [], "status": "skipped", "count": 0, "errors": ["OpenStreetMap needs a city or region"], "seconds": 0}

    if sid == "companies_house" and country != "GB":
        return {"results": [], "status": "skipped", "count": 0, "errors": ["UK Companies House only covers the United Kingdom (GB)"], "seconds": 0}

    if sid == "sec_edgar" and country != "US":
        return {"results": [], "status": "skipped", "count": 0, "errors": ["US SEC EDGAR only covers the United States (US)"], "seconds": 0}

    if sid == "goodfirms" and not city:
        return {"results": [], "status": "skipped", "count": 0, "errors": ["GoodFirms needs a city"], "seconds": 0}

    for i, kw in enumerate(req["keywords"]):
        if i:
            time.sleep(REQUEST_GAP_SECONDS)
        try:
            found = src["search"](session, kw, req)
            # Audience filtering: narrow results if matching, else keep all and add error note
            if req.get("audience"):
                aud_words = [w for a in req["audience"] for w in re.findall(r"[a-z]{3,}", a.lower())] or                     [a.lower() for a in req["audience"]]
                filtered = [
                    r for r in found
                    if any(w in f"{r.get('category', '')} {r.get('company', '')} {r.get('details', '')}".lower() for w in aud_words)
                ]
                if filtered:
                    found = filtered
                elif found:
                    errors.append(f"Audience filter ({', '.join(req['audience'])}) matched 0 results; kept {len(found)} unfiltered")
            results.extend(found)
        except PortalError as e:
            errors.append(f"{kw}: {e}")
        except requests.Timeout:
            errors.append(f"{kw}: {src['name']} did not answer in time (server busy) - try again later")
        except requests.ConnectionError:
            errors.append(f"{kw}: could not reach {src['name']} - check the internet connection")
        except Exception as e:  # noqa: BLE001 - one source failing must not fail the whole search
            errors.append(f"{kw}: {e.__class__.__name__}: {str(e)[:120]}")

    final_status = "ok" if (results or not errors) else "error"
    final_results = results[:MAX_RESULTS_PER_SOURCE]
    return {
        "results": final_results,
        "status": final_status,
        "count": len(final_results),
        "errors": errors,
        "seconds": round(time.time() - started, 1),
    }


def _domain(url: str) -> str:
    if not url:
        return ""
    try:
        host = urlparse(url if "://" in url else f"http://{url}").netloc.lower()
        return re.sub(r"^www\.", "", host)
    except Exception:
        return ""


MERGE_FIELDS = ("email", "phone", "website", "location", "category", "contact_name", "contact_title", "linkedin")


def _dedupe(results: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """One row per company (website domain, else name + country, else link). When a duplicate has details
    the kept row is missing (e.g. email or phone), they are copied over instead of being lost."""
    index: Dict[Any, Dict[str, str]] = {}
    out = []
    for r in results:
        dom = _domain(r.get("website", ""))
        comp = _clean(r.get("company", "")).lower()
        country = _clean(r.get("country", "")).upper()
        keys = []
        if dom:
            keys.append(("d", dom))
        if comp:
            keys.append(("n", comp, country))
        if not keys and r.get("url"):
            keys.append(("u", r["url"].lower(), country))
        if not keys:
            continue
        kept = next((index[k] for k in keys if k in index), None)
        if kept is not None:
            for f in MERGE_FIELDS:
                if not kept.get(f) and r.get(f):
                    kept[f] = r[f]
            for k in keys + ([("d", _domain(kept.get("website", "")))] if kept.get("website") else []):
                index.setdefault(k, kept)
            continue
        for k in keys:
            index[k] = r
        out.append(r)
    return out


def search(data: Dict[str, Any]) -> Dict[str, Any]:
    req = validate_request(data)
    statuses: Dict[str, Dict[str, Any]] = {}
    runnable = []

    for sid in req["sources"]:
        src = SOURCES[sid]
        st = _status(src)
        if st == "available":
            runnable.append(sid)
        else:
            statuses[sid] = {
                "name": src["name"],
                "status": "skipped",
                "count": 0,
                "seconds": 0,
                "errors": [src["reason"]],
            }

    all_results = []
    if runnable:
        max_workers = min(4, len(runnable))
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(_run_source, sid, req): sid for sid in runnable}
            for fut in concurrent.futures.as_completed(futures):
                sid = futures[fut]
                res = fut.result()
                all_results.extend(res.pop("results"))
                statuses[sid] = res

    for sid in statuses:
        statuses[sid]["name"] = SOURCES[sid]["name"]

    results = _dedupe(all_results)
    # Sort results: contactable (email, phone, website) first
    results.sort(key=lambda r: -(bool(r.get("email")) * 4 + bool(r.get("phone")) * 2 + bool(r.get("website"))))

    return {
        "query": {k: req[k] for k in ("keywords", "audience", "country", "region", "city")},
        "results": results,
        "total": len(results),
        "sources": statuses,
    }


# ---------------------------------------------------------------------------
# Lead Normalization
# ---------------------------------------------------------------------------

def result_to_raw_lead(r: Dict[str, Any]) -> Dict[str, str]:
    details = [x for x in (
        r.get("category"),
        r.get("details"),
        r.get("contact_title") and f"Contact: {r.get('contact_name')} ({r['contact_title']})",
        r.get("linkedin") and f"LinkedIn: {r['linkedin']}"
    ) if x]
    return {
        "company_name": r.get("company", ""),
        "full_name": r.get("contact_name", ""),
        "email": r.get("email", ""),
        "mobile_number": r.get("phone", ""),
        "website": r.get("website", ""),
        "location": ", ".join(x for x in (r.get("location"), r.get("country")) if x),
        "description": ". ".join(details) if details else r.get("details", ""),
        "source": f"Global Directory ({r.get('source', r.get('source_id', ''))})",
        "source_url": r.get("url", ""),
        "lead_type": "Global Directory",
    }

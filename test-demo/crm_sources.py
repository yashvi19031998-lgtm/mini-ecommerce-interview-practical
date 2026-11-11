"""
CRM Sources - find businesses and decision makers from directories and B2B contact databases.

Two kinds of sources (status verified with live requests on 2026-11-11):

Business directories (no key):
  OpenStreetMap   official Overpass API - businesses by category + city/state, often with website/phone
  GoodFirms       IT/software companies by city (useful as partners; they are service providers)
  Zaubacorp       companies registered with MCA by city - name, CIN, address (new companies need websites)

B2B contact databases (official APIs; work after you add the key to .env - UNVERIFIED without keys):
  Apollo.io       decision makers by title + location (reuses apollo_enricher.py)   APOLLO_API_KEY
  Hunter.io       companies by industry/location (Discover) + executive emails       HUNTER_API_KEY
  Google Places   businesses by "category in city" with phone + website (Enterprise SKU)  GOOGLE_PLACES_API_KEY
  Snov.io         company database search by industry + city                         SNOV_CLIENT_ID / SNOV_CLIENT_SECRET
  Lusha           contacts by title + location (previews; emails/phones need a paid reveal)  LUSHA_API_KEY
  RocketReach     people by title + location (contact details need a paid lookup)    ROCKETREACH_API_KEY

Unavailable (listed with the reason; we never bypass blocks): Justdial, Sulekha, IndiaMART, TradeIndia,
Clutch, YellowPages.in, AmbitionBox, Google Maps scraping.

Entry points (app.py): list_sources(), search(...), result_to_raw_lead(result)
"""

import concurrent.futures
import os
import re
import time
from typing import Any, Dict, List

from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

import env_loader  # noqa: F401
from job_portals import ALL_INDIA, INDIAN_STATES, PortalError, location_in_state, slugify, _clean, _get, _session

MAX_KEYWORDS = 10
MAX_TITLES = 10
MAX_RESULTS_PER_KEYWORD = 50
REQUEST_GAP_SECONDS = 1.0
ZAUBA_PAGES = 3
ZAUBA_GAP_SECONDS = 2.5
OSM_USER_AGENT = "LeadsGenAI/1.0 (business directory search; contact via app admin)"


# ---------------------------------------------------------------------------
# Common result shape
# ---------------------------------------------------------------------------

def make_result(source_id: str, **fields) -> Dict[str, str]:
    r = {"source_id": source_id, "source": SOURCES[source_id]["name"], "company": "", "contact_name": "",
         "contact_title": "", "email": "", "phone": "", "website": "", "location": "", "category": "",
         "url": "", "linkedin": "", "details": "", "keyword": ""}
    for k, v in fields.items():
        r[k] = _clean(v)[:600] if k != "url" else str(v or "").strip()
    return r


def _place(state: str, city: str) -> str:
    """Human-readable place for APIs: 'Ahmedabad, Gujarat' / 'Gujarat' / 'India'."""
    if city:
        return f"{city}, {state}" if state != ALL_INDIA else city
    return state if state != ALL_INDIA else "India"


def _primary_city(state: str, city: str) -> str:
    """City-only sources: the given city, else the state's biggest city."""
    if city:
        return city
    cities = INDIAN_STATES.get(state) or []
    if not cities:
        raise PortalError("this source needs a city - enter one or choose a state")
    return cities[0]


# ---------------------------------------------------------------------------
# Business directories
# ---------------------------------------------------------------------------

# keyword fragment -> OpenStreetMap tag filters
OSM_TAGS = {
    "software": ['"office"="it"', '"office"="company"'], "it ": ['"office"="it"'], "it company": ['"office"="it"'],
    "web": ['"office"="it"'], "tech": ['"office"="it"'],
    "real estate": ['"office"="estate_agent"'], "builder": ['"office"="estate_agent"', '"office"="construction_company"'],
    "construction": ['"office"="construction_company"'],
    "hospital": ['"amenity"="hospital"'], "clinic": ['"amenity"="clinic"', '"amenity"="doctors"'],
    "doctor": ['"amenity"="doctors"'], "dentist": ['"amenity"="dentist"'], "pharmacy": ['"amenity"="pharmacy"'],
    "school": ['"amenity"="school"'], "college": ['"amenity"="college"', '"amenity"="university"'],
    "coaching": ['"amenity"="school"', '"office"="educational_institution"'],
    "hotel": ['"tourism"="hotel"'], "restaurant": ['"amenity"="restaurant"'], "cafe": ['"amenity"="cafe"'],
    "lawyer": ['"office"="lawyer"'], "advocate": ['"office"="lawyer"'], "accountant": ['"office"="accountant"'],
    "ca firm": ['"office"="accountant"'], "insurance": ['"office"="insurance"'], "bank": ['"amenity"="bank"'],
    "manufactur": ['"man_made"="works"', '"industrial"'], "factory": ['"man_made"="works"', '"industrial"'],
    "textile": ['"industrial"', '"shop"="fabric"'], "jewel": ['"shop"="jewelry"'], "furniture": ['"shop"="furniture"'],
    "shop": ['"shop"'], "store": ['"shop"'], "retail": ['"shop"'], "gym": ['"leisure"="fitness_centre"'],
    "salon": ['"shop"="hairdresser"', '"shop"="beauty"'], "travel": ['"office"="travel_agent"', '"shop"="travel_agency"'],
    "logistics": ['"office"="logistics"'], "transport": ['"office"="logistics"'], "company": ['"office"="company"'],
}


def _osm_filters(keyword: str) -> List[str]:
    kw = f"{keyword.lower()} "
    tags = []
    for frag, t in OSM_TAGS.items():
        if frag in kw:
            tags.extend(t)
    return list(dict.fromkeys(tags))


def search_osm(session, keyword: str, titles: List[str], state: str, city: str) -> List[Dict]:
    if state == ALL_INDIA and not city:
        raise PortalError("choose a state or enter a city (all of India is too large for OpenStreetMap)")
    area_name = city or state
    level = '' if city else '["admin_level"="4"]'
    generic = {"company", "companies", "services", "service", "shop", "shops", "store", "firm", "agency", "business"}
    words = [w for w in re.findall(r"[a-z]{4,}", keyword.lower()) if w not in generic]
    clauses = [f"nwr[{t}](area.a);" for t in _osm_filters(keyword)]
    if words:  # name search is slow on big areas: one word, offices and crafts only
        clauses += [f'nwr["name"~"{re.escape(words[0])}",i][{k}](area.a);' for k in ('"office"', '"craft"')]
    if not clauses:
        raise PortalError(f"no OpenStreetMap category matches '{keyword}' - try e.g. software, hospital, school, hotel")
    query = (f'[out:json][timeout:25];area["name"="{area_name}"]["boundary"="administrative"]{level}->.a;'
             f'({"".join(clauses)});out center tags {MAX_RESULTS_PER_KEYWORD * 2};')
    for attempt in range(2):  # the public Overpass server is sometimes briefly overloaded (502/504)
        r = session.post("https://overpass-api.de/api/interpreter", data={"data": query},
                         headers={"User-Agent": OSM_USER_AGENT, "Accept": "*/*"}, timeout=35)
        if r.status_code not in (502, 504) or attempt:
            break
        time.sleep(5)
    if r.status_code in (429, 502, 504):
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
        category = next((f"{k}: {tags[k]}" for k in ("office", "shop", "amenity", "craft", "industrial", "tourism",
                                                      "leisure", "man_made") if tags.get(k)), "")
        results.append(make_result(
            "osm", company=name, website=tags.get("website") or tags.get("contact:website") or tags.get("url"),
            phone=tags.get("phone") or tags.get("contact:phone") or tags.get("contact:mobile"),
            email=tags.get("email") or tags.get("contact:email"), location=addr or area_name, category=category,
            url=f"https://www.openstreetmap.org/{el.get('type')}/{el.get('id')}",
        ))
    # entries with a website or phone first: they are the useful ones for outreach
    results.sort(key=lambda x: (not (x["website"] or x["phone"] or x["email"])))
    return results[:MAX_RESULTS_PER_KEYWORD]


def search_sulekha(session, keyword: str, titles: List[str], state: str, city: str) -> List[Dict]:
    city_name = _primary_city(state, city)
    r = session.get(f"https://www.sulekha.com/{slugify(keyword)}/{slugify(city_name)}", timeout=25)
    if r.status_code == 404:
        raise PortalError(f"Sulekha has no '{keyword}' page for {city_name} - try its category name, e.g. 'software companies'")
    if r.status_code in (403, 429):
        raise PortalError(f"blocked by the site (HTTP {r.status_code})")
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    results, seen = [], set()
    for a in soup.select('a[href^="/profile/"][title]'):
        href = a["href"].split("?")[0]
        if href in seen:
            continue
        seen.add(href)
        title = _clean(a.get("title"))
        name, _, where = title.partition(" in ")
        results.append(make_result("sulekha", company=name or title, location=where, category=keyword,
                                   url=f"https://www.sulekha.com{href}",
                                   details="Contact via Sulekha profile (listed phone numbers are Sulekha's)"))
    target_state = state if state != ALL_INDIA else ""
    return [x for x in results if not target_state or location_in_state(x["location"], target_state)
            or city_name.lower() in x["location"].lower()][:MAX_RESULTS_PER_KEYWORD]


def search_goodfirms(session, keyword: str, titles: List[str], state: str, city: str) -> List[Dict]:
    city_name = _primary_city(state, city)
    r = _get(session, f"https://www.goodfirms.co/directory/city/top-software-development-companies/{slugify(city_name)}")
    soup = BeautifulSoup(r.text, "html.parser")
    results = []
    for card in soup.select(".firm-wrapper-item"):
        profile = card.select_one('a[href*="/company/"]')
        name_el = card.select_one(".firm-name, h3, h2") or profile
        name = _clean(name_el.get_text()) if name_el else ""
        if not name:
            continue
        # company site links carry ?utm_source=goodfirms.co - check the host, not the whole URL
        site = next((a["href"].split("?")[0] for a in card.select("a[href^='http']")
                     if not urlparse(a["href"]).netloc.lower().endswith("goodfirms.co")), "")
        loc_el = card.select_one(".firm-location, .location, [class*='location']")
        prof = profile["href"] if profile else ""
        results.append(make_result(
            "goodfirms", company=name, website=site, location=_clean(loc_el.get_text()) if loc_el else city_name,
            category="Software development company",
            url=prof if prof.startswith("http") else f"https://www.goodfirms.co{prof}" if prof else "",
            details="IT service company (possible partner, not a buyer)",
        ))
    return results[:MAX_RESULTS_PER_KEYWORD]


def search_zauba(session, keyword: str, titles: List[str], state: str, city: str) -> List[Dict]:
    city_name = _primary_city(state, city)
    base = f"https://www.zaubacorp.com/companies-list/city-{city_name.upper().replace(' ', '-')}"
    words = [w for w in re.findall(r"[a-z]{3,}", keyword.lower()) if w not in ("company", "companies", "firm", "pvt", "ltd")]
    boxes = []
    for page in range(1, ZAUBA_PAGES + 1):  # 30 companies per page; the keyword is matched on the name
        if page > 1:
            time.sleep(ZAUBA_GAP_SECONDS)
        try:
            r = _get(session, base if page == 1 else f"{base}/p-{page}")
        except PortalError:
            if boxes:  # rate limited after some pages: keep what we have
                break
            raise
        found = BeautifulSoup(r.text, "html.parser").select(".companies-list")
        if not found:
            break
        boxes.extend(found)
    results = []
    for box in boxes:
        link = box.select_one("h2 a")
        if not link:
            continue
        name = _clean(link.get_text())
        if words and not any(w[:4] in name.lower() for w in words):
            continue
        badges = {(img.get("alt") or ""): _clean(img.parent.get_text()) for img in box.select(".badge img[alt]")}
        status = _clean((box.select_one(".badge-success, .badge-danger, .badge-warning") or link).get_text())
        results.append(make_result("zauba", company=name.title(), location=badges.get("Address", city_name),
                                   category="Registered company (MCA)", url=link.get("href", ""),
                                   details=f"CIN {badges.get('CIN', '')} · {status}"))
    return results[:MAX_RESULTS_PER_KEYWORD]


# ---------------------------------------------------------------------------
# B2B contact databases (official APIs)
# ---------------------------------------------------------------------------

def _key(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise PortalError(f"{name} not set in .env")
    return value


def _api_error(r: requests.Response, service: str) -> None:
    if r.status_code in (401, 403):
        raise PortalError(f"{service} rejected the API key or plan (HTTP {r.status_code})")
    if r.status_code == 402:
        raise PortalError(f"{service}: no credits left (HTTP 402)")
    if r.status_code == 429:
        raise PortalError(f"{service}: rate limit or quota reached (HTTP 429)")
    r.raise_for_status()


def search_apollo(session, keyword: str, titles: List[str], state: str, city: str) -> List[Dict]:
    key = _key("APOLLO_API_KEY")
    import apollo_enricher  # existing module: returns lead dicts (full_name, company_name, email, ...)
    people = apollo_enricher.search_apollo_prospects(
        keywords=keyword, locations=[_place(state, city) + ", India" if state != ALL_INDIA or city else "India"],
        titles=titles or None, per_page=MAX_RESULTS_PER_KEYWORD, api_key=key) or []
    results = []
    for p in people:
        desc = p.get("description", "")
        title = desc.split(" at ")[0] if " at " in desc else ""
        results.append(make_result(
            "apollo", company=p.get("company_name"), contact_name=p.get("full_name"), contact_title=title,
            email=p.get("email"), phone=p.get("mobile_number"), website=p.get("website"),
            location=p.get("location") or _place(state, city), category=keyword,
            linkedin=p.get("source_url") if "linkedin" in str(p.get("source_url", "")) else "",
            url=p.get("source_url") or p.get("website") or ""))
    return results


def search_hunter(session, keyword: str, titles: List[str], state: str, city: str) -> List[Dict]:
    key = _key("HUNTER_API_KEY")
    location = {"country": "IN"}
    if city:
        location["city"] = city
    elif state != ALL_INDIA:
        location["state"] = state
    body = {"headquarters_location": {"include": [location]}, "keywords": {"include": [keyword]}, "limit": 25}
    r = session.post("https://api.hunter.io/v2/discover", params={"api_key": key}, json=body, timeout=25)
    _api_error(r, "Hunter.io")
    companies = r.json().get("data") or []
    results = []
    for i, c in enumerate(companies):
        base = dict(company=c.get("organization") or c.get("domain"), website=f"https://{c['domain']}" if c.get("domain") else "",
                    location=_place(state, city), category=keyword, url=f"https://{c.get('domain', '')}",
                    details=f"{((c.get('emails_count') or {}).get('total') or 0)} emails known at Hunter")
        people = []
        if i < 5 and c.get("domain"):  # decision makers for the top companies only (Domain Search uses credits)
            time.sleep(0.3)
            d = session.get("https://api.hunter.io/v2/domain-search", timeout=25, params={
                "api_key": key, "domain": c["domain"], "seniority": "executive,senior", "limit": 3})
            if d.status_code == 200:
                people = (d.json().get("data") or {}).get("emails") or []
        if people:
            for p in people:
                results.append(make_result("hunter", **base, email=p.get("value"),
                                           contact_name=" ".join(x for x in (p.get("first_name"), p.get("last_name")) if x),
                                           contact_title=p.get("position"), phone=p.get("phone_number"),
                                           linkedin=p.get("linkedin")))
        else:
            results.append(make_result("hunter", **base))
    return results


PLACES_FIELDS = ",".join([
    "places.id", "places.displayName", "places.formattedAddress", "places.nationalPhoneNumber",
    "places.internationalPhoneNumber", "places.websiteUri", "places.googleMapsUri", "places.rating",
    "places.userRatingCount", "places.businessStatus", "places.primaryType", "nextPageToken",
])


def search_google_places(session, keyword: str, titles: List[str], state: str, city: str) -> List[Dict]:
    key = _key("GOOGLE_PLACES_API_KEY")
    body = {"textQuery": f"{keyword} in {_place(state, city)}, India", "pageSize": 20, "regionCode": "IN"}
    headers = {"X-Goog-Api-Key": key, "X-Goog-FieldMask": PLACES_FIELDS, "Content-Type": "application/json"}
    results = []
    for _ in range(3):  # Text Search returns at most 60 results (3 pages of 20)
        r = session.post("https://places.googleapis.com/v1/places:searchText", json=body, headers=headers, timeout=25)
        if r.status_code in (400, 403) and "API key" in r.text:
            raise PortalError(f"Google rejected the API key (HTTP {r.status_code})")
        _api_error(r, "Google Places")
        data = r.json()
        for p in data.get("places") or []:
            if p.get("businessStatus") and p["businessStatus"] != "OPERATIONAL":
                continue
            rating = f"★ {p['rating']} ({p.get('userRatingCount', 0)} reviews)" if p.get("rating") else ""
            results.append(make_result(
                "google_places", company=(p.get("displayName") or {}).get("text"),
                phone=p.get("internationalPhoneNumber") or p.get("nationalPhoneNumber"), website=p.get("websiteUri"),
                location=p.get("formattedAddress"), category=p.get("primaryType") or keyword,
                url=p.get("googleMapsUri"), details=rating))
        token = data.get("nextPageToken")
        if not token:
            break
        body = {**body, "pageToken": token}
        time.sleep(REQUEST_GAP_SECONDS)
    return results


def _snov_token(session) -> str:
    r = session.post("https://api.snov.io/v1/oauth/access_token", timeout=20, data={
        "grant_type": "client_credentials", "client_id": _key("SNOV_CLIENT_ID"),
        "client_secret": _key("SNOV_CLIENT_SECRET")})
    _api_error(r, "Snov.io")
    token = r.json().get("access_token")
    if not token:
        raise PortalError("Snov.io did not return an access token - check SNOV_CLIENT_ID / SNOV_CLIENT_SECRET")
    return token


def search_snov(session, keyword: str, titles: List[str], state: str, city: str) -> List[Dict]:
    token = _snov_token(session)
    headers = {"Authorization": f"Bearer {token}"}
    if city:
        loc = {"locality": [city], "location_type": "city"}
    elif state != ALL_INDIA:
        loc = {"locality": [state], "location_type": "state"}
    else:
        loc = {"locality": ["India"], "location_type": "country"}
    body = {"filters": {"locations": {"include": [loc]}, "company": {"industries": {"include": [keyword]}}}, "page": 1}
    r = session.post("https://api.snov.io/v2/database-search/companies/start", json=body, headers=headers, timeout=25)
    _api_error(r, "Snov.io")
    task = ((r.json().get("meta") or {}).get("task_hash")) or ""
    if not task:
        raise PortalError("Snov.io did not start the search")
    for _ in range(10):  # async: poll until completed
        time.sleep(1.5)
        res = session.get(f"https://api.snov.io/v2/database-search/companies/result/{task}", headers=headers, timeout=25)
        _api_error(res, "Snov.io")
        payload = res.json()
        if payload.get("status") == "completed":
            companies = (payload.get("data") or {}).get("companies") or []
            return [make_result("snov", company=c.get("name"), website=f"https://{c['domain']}" if c.get("domain") else "",
                                location=c.get("location"), category=c.get("industry") or keyword,
                                url=f"https://{c.get('domain', '')}", details=f"Size {c.get('size', '')}")
                    for c in companies][:MAX_RESULTS_PER_KEYWORD]
    raise PortalError("Snov.io search is still running - try again in a minute")


def search_lusha(session, keyword: str, titles: List[str], state: str, city: str) -> List[Dict]:
    key = _key("LUSHA_API_KEY")
    loc = {"country": "India"}
    if city:
        loc["city"] = city
    elif state != ALL_INDIA:
        loc["state"] = state
    contacts = {"locations": [loc]}
    if titles:
        contacts["jobTitles"] = titles
    body = {"pagination": {"page": 0, "size": 25},
            "filters": {"contacts": {"include": contacts}, "companies": {"include": {"keywords": [keyword]}}}}
    r = session.post("https://api.lusha.com/v3/contacts/prospecting", json=body, headers={"api_key": key}, timeout=25)
    _api_error(r, "Lusha")
    results = []
    for c in r.json().get("results") or []:
        comp = c.get("company") or {}
        loc_ = c.get("location") or {}
        has = ", ".join(c.get("has") or [])
        results.append(make_result(
            "lusha", company=comp.get("name"), contact_name=" ".join(x for x in (c.get("firstName"), c.get("lastName")) if x),
            contact_title=(c.get("jobTitle") or {}).get("title"), website=f"https://{comp['domain']}" if comp.get("domain") else "",
            location=", ".join(x for x in (loc_.get("city"), loc_.get("state"), loc_.get("country")) if x),
            linkedin=(c.get("socialLinks") or {}).get("linkedin"), category=comp.get("industry") or keyword,
            url=(c.get("socialLinks") or {}).get("linkedin") or "",
            details=f"Available on reveal (uses Lusha credits): {has}" if has else "Preview only"))
    return results


def search_rocketreach(session, keyword: str, titles: List[str], state: str, city: str) -> List[Dict]:
    key = _key("ROCKETREACH_API_KEY")
    geo = f"{city}, {state}, IN" if city and state != ALL_INDIA else (f"{state}, IN" if state != ALL_INDIA else "India")
    query = {"geo": [geo], "company_industry": [keyword]}
    if titles:
        query["current_title"] = titles
    r = session.post("https://api.rocketreach.co/api/v2/person/search", headers={"Api-Key": key}, timeout=25,
                     json={"query": query, "start": 1, "page_size": 25})
    _api_error(r, "RocketReach")
    data = r.json()
    profiles = data if isinstance(data, list) else data.get("profiles") or []
    return [make_result(
        "rocketreach", company=p.get("current_employer"), contact_name=p.get("name"),
        contact_title=p.get("current_title"),
        website=p.get("current_employer_website") or (f"https://{p['current_employer_domain']}" if p.get("current_employer_domain") else ""),
        location=p.get("location") or ", ".join(x for x in (p.get("city"), p.get("region")) if x),
        linkedin=p.get("linkedin_url"), category=keyword, url=p.get("linkedin_url") or "",
        details="Email/phone need a RocketReach lookup (uses credits)") for p in profiles]


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------

def _s(name, kind, status, search=None, reason="", note="", keys=()):
    return {"name": name, "kind": kind, "status": status, "search": search, "reason": reason, "note": note, "keys": keys}


SOURCES: Dict[str, Dict[str, Any]] = {
    "osm": _s("OpenStreetMap (Overpass)", "directory", "available", search_osm,
              note="Free official API. Businesses by category; many have website/phone."),
    "sulekha": _s("Sulekha", "directory", "unavailable",
                  reason="City listings load only with JavaScript; the page itself shows ads from other cities"),
    "goodfirms": _s("GoodFirms", "directory", "available", search_goodfirms,
                    note="IT/software companies only - partners or competitors, not buyers."),
    "zauba": _s("Zaubacorp (MCA companies)", "directory", "available", search_zauba,
                note="Registered companies in the city; keyword matched on company name. No contact details."),
    "apollo": _s("Apollo.io", "database", "needs_key", search_apollo, keys=("APOLLO_API_KEY",),
                 reason="Add APOLLO_API_KEY to .env"),
    "hunter": _s("Hunter.io", "database", "needs_key", search_hunter, keys=("HUNTER_API_KEY",),
                 reason="Add HUNTER_API_KEY to .env (free plan available)",
                 note="Companies by keyword + location; executive emails for the top 5 (uses credits)."),
    "google_places": _s("Google Places API", "database", "needs_key", search_google_places, keys=("GOOGLE_PLACES_API_KEY",),
                        reason="Add GOOGLE_PLACES_API_KEY to .env (Google Cloud, billing required)",
                        note="Phone + website fields are billed at the Enterprise rate."),
    "snov": _s("Snov.io", "database", "needs_key", search_snov, keys=("SNOV_CLIENT_ID", "SNOV_CLIENT_SECRET"),
               reason="Add SNOV_CLIENT_ID and SNOV_CLIENT_SECRET to .env"),
    "lusha": _s("Lusha", "database", "needs_key", search_lusha, keys=("LUSHA_API_KEY",),
                reason="Add LUSHA_API_KEY to .env", note="Returns previews; revealing email/phone uses Lusha credits."),
    "rocketreach": _s("RocketReach", "database", "needs_key", search_rocketreach, keys=("ROCKETREACH_API_KEY",),
                      reason="Add ROCKETREACH_API_KEY to .env", note="Contact details need a separate paid lookup."),
    "justdial": _s("Justdial", "directory", "unavailable", reason="Returns an empty page to automated requests"),
    "indiamart": _s("IndiaMART", "directory", "unavailable", reason="Listings load only with JavaScript in a browser"),
    "tradeindia": _s("TradeIndia", "directory", "unavailable", reason="Listings load only with JavaScript in a browser"),
    "clutch": _s("Clutch", "directory", "unavailable", reason="Blocks automated requests (Cloudflare)"),
    "yellowpages": _s("YellowPages.in", "directory", "unavailable", reason="Site did not respond"),
    "ambitionbox": _s("AmbitionBox", "directory", "unavailable", reason="Ignores the city filter (India-wide list only)"),
    "google_maps": _s("Google Maps (scraping)", "directory", "unavailable",
                      reason="Scraping is against Google's terms - use 'Google Places API' instead"),
}


def _status(src: Dict[str, Any]) -> str:
    if src["status"] != "needs_key":
        return src["status"]
    return "available" if all(os.getenv(k, "").strip() for k in src["keys"]) else "needs_key"


def list_sources() -> List[Dict[str, str]]:
    order = {"available": 0, "needs_key": 1, "unavailable": 2}
    items = []
    for sid, s in SOURCES.items():
        st = _status(s)
        items.append({"id": sid, "name": s["name"], "kind": s["kind"], "status": st, "note": s["note"],
                      "reason": "" if st == "available" else s["reason"]})
    return sorted(items, key=lambda x: (order[x["status"]], x["kind"], x["name"].lower()))


def _clean_list(values: Any, label: str, limit: int, required: bool) -> List[str]:
    if values in (None, "") and not required:
        return []
    if not isinstance(values, list):
        raise ValueError(f"{label} must be a list")
    out = list(dict.fromkeys(_clean(v) for v in values if isinstance(v, str) and _clean(v)))
    if required and not out:
        raise ValueError(f"Enter at least one {label[:-1].lower()}")
    if len(out) > limit:
        raise ValueError(f"Enter at most {limit} {label.lower()}")
    if any(len(v) > 80 for v in out):
        raise ValueError(f"Each of the {label.lower()} must be 80 characters or less")
    return out


def validate_request(keywords, titles, state, city, source_ids) -> Dict[str, Any]:
    kws = _clean_list(keywords, "Keywords", MAX_KEYWORDS, True)
    tts = _clean_list(titles, "Titles", MAX_TITLES, False)
    if state not in INDIAN_STATES and state != ALL_INDIA:
        raise ValueError("Select a valid state")
    city = _clean(city or "")
    if len(city) > 60 or (city and not re.fullmatch(r"[A-Za-z .'-]+", city)):
        raise ValueError("City must be letters only (max 60 characters)")
    if not isinstance(source_ids, list) or not source_ids:
        raise ValueError("Select at least one source")
    unknown = [s for s in source_ids if s not in SOURCES]
    if unknown:
        raise ValueError(f"Unknown source: {', '.join(map(str, unknown))}")
    return {"keywords": kws, "titles": tts, "state": state, "city": city, "source_ids": list(dict.fromkeys(source_ids))}


def _run_source(sid: str, req: Dict[str, Any]) -> Dict[str, Any]:
    src = SOURCES[sid]
    session = _session()
    results, errors, started = [], [], time.time()
    for i, kw in enumerate(req["keywords"]):
        if i:
            time.sleep(REQUEST_GAP_SECONDS)
        try:
            found = src["search"](session, kw, req["titles"], req["state"], req["city"])
            for f in found:
                f["keyword"] = kw
            results.extend(found)
        except PortalError as e:
            errors.append(f"{kw}: {e}")
        except (requests.RequestException, ValueError, KeyError, TypeError) as e:
            errors.append(f"{kw}: {e.__class__.__name__}: {str(e)[:120]}")
    status = "ok" if not errors else ("partial" if results else "error")
    return {"results": results, "status": status, "count": len(results), "errors": errors,
            "seconds": round(time.time() - started, 1)}


def _dedupe(results: List[Dict[str, str]]) -> List[Dict[str, str]]:
    seen, out = set(), []
    for r in results:
        key = (r["company"].lower(), r["contact_name"].lower(), r["email"].lower()) if r["company"] else (r["url"],)
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def search(keywords, titles, state, city, source_ids) -> Dict[str, Any]:
    req = validate_request(keywords, titles, state, city, source_ids)
    statuses: Dict[str, Dict[str, Any]] = {}
    runnable = []
    for sid in req["source_ids"]:
        if _status(SOURCES[sid]) == "available":
            runnable.append(sid)
        else:
            statuses[sid] = {"status": "skipped", "count": 0, "errors": [SOURCES[sid]["reason"]], "seconds": 0}
    all_results = []
    if runnable:
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, len(runnable))) as pool:
            futures = {pool.submit(_run_source, sid, req): sid for sid in runnable}
            for fut in concurrent.futures.as_completed(futures):
                res = fut.result()
                all_results.extend(res.pop("results"))
                statuses[futures[fut]] = res
    for sid in statuses:
        statuses[sid]["name"] = SOURCES[sid]["name"]
    results = _dedupe(all_results)
    # most contactable first
    results.sort(key=lambda r: -(bool(r["email"]) * 4 + bool(r["phone"]) * 2 + bool(r["website"])))
    return {"results": results, "total": len(results), "sources": statuses,
            "query": {k: req[k] for k in ("keywords", "titles", "state", "city")}}


def result_to_raw_lead(r: Dict[str, Any]) -> Dict[str, str]:
    details = [x for x in (r.get("category"), r.get("contact_title") and f"Contact: {r.get('contact_name')} ({r['contact_title']})",
                           r.get("details"), r.get("linkedin") and f"LinkedIn: {r['linkedin']}") if x]
    return {
        "company_name": r.get("company") or r.get("contact_name") or "",
        "full_name": r.get("contact_name", ""),
        "email": r.get("email", ""),
        "mobile_number": r.get("phone", ""),
        "website": r.get("website", ""),
        "location": r.get("location", ""),
        "description": ". ".join(details),
        "source": f"CRM Source ({r.get('source', r.get('source_id', ''))})",
        "source_url": r.get("url", ""),
        "lead_type": "B2B Contact" if r.get("contact_name") else "Business Directory",
    }


if __name__ == "__main__":
    import sys
    res = search(sys.argv[1:] or ["software"], [], "Gujarat", "Ahmedabad",
                 [s["id"] for s in list_sources() if s["status"] == "available"])
    for sid, st in res["sources"].items():
        print(f"{st['name']:<28} {st['status']:<8} {st['count']:>4}  {st['seconds']}s  {'; '.join(st['errors'])[:120]}")
    print(f"total {res['total']}")
    for r in res["results"][:12]:
        print(f" - [{r['source']}] {r['company'][:40]} | {r['website'][:35]} | {r['phone'][:18]} | {r['location'][:30]}")

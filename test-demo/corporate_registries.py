"""Data Extraction -> Corporate Registries: Company Scraper, PVT LTD Scraper and GST No Scraper.

Company data is the public Ministry of Corporate Affairs (MCA) register, read from ZaubaCorp's public listing pages
(robots.txt allows everything except PDFs). The official MCA and GST portals use captchas, so they are never used.

  company   ZaubaCorp company lists, filtered by industry (NIC section) / city or state / company type / status / age,
            or a search by company name. Rows: name, status, CIN, registered address, paid-up capital, plus what the
            CIN itself says (listed?, industry code, state, year of incorporation, company type).
  pvtltd    the same lists, fixed to Private Limited companies (CIN type PTC); "less than 1 year" by default -
            newly registered companies.
  details   (on request, up to 10 at a time) the company page: incorporation date, ROC, category, class, activity,
            website. Director names are personal data and are not collected; e-mails ZaubaCorp hides from bots
            (Cloudflare e-mail protection) are not decoded.
  gst_find  GST numbers shown on IndiaMART seller pages for a product / category (+ city); each GSTIN is validated.
  gst_check validate and decode GSTINs the user already has (offline: checksum, state, PAN, entity type).
            Live status (active / cancelled) needs the GST portal, which has a captcha - not available.
"""
import re
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote, urlparse

import requests
from bs4 import BeautifulSoup

import indian_directories as idr
import maps_sources
import robots_policy
import search_engine as se
from job_portals import ALL_INDIA, INDIAN_STATES

ZAUBA = "https://www.zaubacorp.com"
MAX_NAMES = 5
MAX_GSTINS = 100
PAGE_CHOICES = (1, 2, 3, 5)
SELLER_CHOICES = (10, 20, 30)
MAX_DETAILS_PER_CALL = 10
CITY_RE = re.compile(r"^[A-Za-z .'-]{1,60}$")
CIN_RE = re.compile(r"\b([LU])(\d{5})([A-Z]{2})(\d{4})([A-Z]{3})(\d{6})\b")
LLPIN_RE = re.compile(r"\b([A-Z]{3}-\d{4})\b")          # LLPs have an LLPIN, not a CIN (and no industry code)
GSTIN_RE = re.compile(r"\b(\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z])\b")
B36 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"

MODES = {
    "company": {"name": "Company Scraper", "note": "Registered companies (MCA data) by industry, place, type, status and age."},
    "pvtltd": {"name": "PVT LTD Scraper", "note": "Private Limited companies only - newly registered ones by default."},
    "gst": {"name": "GST No Scraper", "note": "GST numbers from IndiaMART seller pages, or check GSTINs you already have."},
}

COMPANY_TYPES = {
    "": "Any type", "PTC": "Private Limited Company", "LLP": "Limited Liability Partnership", "OPC": "One Person Company",
    "PLC": "Public Limited Company", "NPL": "Not For Profit (Section 8) Company", "FTC": "Subsidiary of a Foreign Company",
}
STATUSES = {"Active": "Active", "": "Any status", "Strike Off": "Strike Off", "Under process of striking off": "Under process of striking off"}
AGES = {"": "Any age", "A": "Less than 1 year (new)", "B": "1 to 3 years", "C": "3 to 5 years", "D": "5 to 10 years",
        "E": "10 to 25 years", "F": "More than 25 years"}
# ZaubaCorp groups companies by the NIC 2004 section of their main activity
INDUSTRIES = {
    "": "Any industry", "A": "Agriculture, hunting and forestry", "B": "Fishing", "C": "Mining and quarrying",
    "D": "Manufacturing", "E": "Electricity, gas and water supply", "F": "Construction",
    "G": "Wholesale and retail trade; repair", "H": "Hotels and restaurants", "I": "Transport, storage and communications",
    "J": "Financial intermediation", "K": "Real estate, renting and business activities (incl. IT / software)",
    "L": "Public administration and defence", "M": "Education", "N": "Health and social work",
    "O": "Other community, social and personal services",
}
# ZaubaCorp's state names where they differ from ours
ZAUBA_STATES = {"Odisha": "ORISSA", "Chhattisgarh": "CHATTISGARH", "Puducherry": "PONDICHERRY",
                "Jammu and Kashmir": "JAMMU & KASHMIR", "Andaman and Nicobar Islands": "ANDAMAN & NICOBAR",
                "Dadra and Nagar Haveli and Daman and Diu": "DADRA & NAGAR HAVELI"}
GST_STATES = {
    "01": "Jammu and Kashmir", "02": "Himachal Pradesh", "03": "Punjab", "04": "Chandigarh", "05": "Uttarakhand",
    "06": "Haryana", "07": "Delhi", "08": "Rajasthan", "09": "Uttar Pradesh", "10": "Bihar", "11": "Sikkim",
    "12": "Arunachal Pradesh", "13": "Nagaland", "14": "Manipur", "15": "Mizoram", "16": "Tripura", "17": "Meghalaya",
    "18": "Assam", "19": "West Bengal", "20": "Jharkhand", "21": "Odisha", "22": "Chhattisgarh", "23": "Madhya Pradesh",
    "24": "Gujarat", "25": "Daman and Diu", "26": "Dadra and Nagar Haveli and Daman and Diu", "27": "Maharashtra",
    "28": "Andhra Pradesh (old)", "29": "Karnataka", "30": "Goa", "31": "Lakshadweep", "32": "Kerala", "33": "Tamil Nadu",
    "34": "Puducherry", "35": "Andaman and Nicobar Islands", "36": "Telangana", "37": "Andhra Pradesh", "38": "Ladakh",
    "97": "Other Territory", "99": "Centre Jurisdiction",
}
PAN_ENTITY = {"C": "Company", "P": "Proprietorship (individual)", "F": "Firm / LLP", "H": "Hindu Undivided Family",
              "A": "Association of Persons", "T": "Trust", "B": "Body of Individuals", "L": "Local Authority",
              "J": "Artificial Juridical Person", "G": "Government"}
CIN_TYPES = {"PTC": "Private Limited", "PLC": "Public Limited", "OPC": "One Person Company", "NPL": "Section 8 (not for profit)",
             "FTC": "Subsidiary of a foreign company", "GOI": "Government of India company", "SGC": "State Government company",
             "ULT": "Private unlimited", "ULL": "Public unlimited", "FLC": "Financial lease company", "GAP": "General association (public)",
             "GAT": "General association (private)"}
CIN_STATES = {"AP": "Andhra Pradesh", "AR": "Arunachal Pradesh", "AS": "Assam", "BR": "Bihar", "CH": "Chandigarh",
              "CT": "Chhattisgarh", "DL": "Delhi", "DN": "Dadra and Nagar Haveli", "DD": "Daman and Diu", "GA": "Goa",
              "GJ": "Gujarat", "HP": "Himachal Pradesh", "HR": "Haryana", "JH": "Jharkhand", "JK": "Jammu and Kashmir",
              "KA": "Karnataka", "KL": "Kerala", "LD": "Lakshadweep", "MH": "Maharashtra", "ML": "Meghalaya", "MN": "Manipur",
              "MP": "Madhya Pradesh", "MZ": "Mizoram", "NL": "Nagaland", "OR": "Odisha", "PB": "Punjab", "PY": "Puducherry",
              "RJ": "Rajasthan", "SK": "Sikkim", "TG": "Telangana", "TN": "Tamil Nadu", "TR": "Tripura", "UP": "Uttar Pradesh",
              "UR": "Uttarakhand", "WB": "West Bengal", "AN": "Andaman and Nicobar Islands", "LA": "Ladakh"}


# ---------------------------------------------------------------------------
# Catalog + validation
# ---------------------------------------------------------------------------

def catalog() -> Dict[str, Any]:
    opt = lambda d: [{"id": k, "name": v} for k, v in d.items()]  # noqa: E731
    return {"modes": [{"id": k, **v} for k, v in MODES.items()], "companyTypes": opt(COMPANY_TYPES),
            "statuses": opt(STATUSES), "ages": opt(AGES), "industries": opt(INDUSTRIES),
            "pageChoices": list(PAGE_CHOICES), "sellerChoices": list(SELLER_CHOICES), "maxGstins": MAX_GSTINS,
            "maxNames": MAX_NAMES, "detailsBatch": MAX_DETAILS_PER_CALL}


def _place(data: Dict[str, Any]) -> Tuple[str, str]:
    state = data.get("state") or ALL_INDIA
    if state != ALL_INDIA and state not in INDIAN_STATES:
        raise ValueError("Unknown state")
    city = " ".join(str(data.get("city") or "").split())
    if city and not CITY_RE.match(city):
        raise ValueError("City must be letters only (max 60 characters)")
    return state, city


def _choice(data: Dict[str, Any], key: str, options: Dict[str, str], default: str, label: str) -> str:
    v = data.get(key, default)
    v = default if v is None else str(v)
    if v not in options:
        raise ValueError(f"Unknown {label}")
    return v


def validate_request(data: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("Invalid request")
    mode = data.get("mode")
    if mode not in ("company", "pvtltd", "gst_find", "gst_check"):
        raise ValueError("Unknown mode")
    audience = maps_sources._clean_list(data.get("audience"), "Target audience", 5, 60, False)
    if mode == "gst_check":
        raw = data.get("gstins")
        if not isinstance(raw, list) or not raw:
            raise ValueError("Paste at least one GST number")
        gstins = list(dict.fromkeys(re.sub(r"\s", "", str(g)).upper() for g in raw if str(g).strip()))
        if not gstins:
            raise ValueError("Paste at least one GST number")
        if len(gstins) > MAX_GSTINS:
            raise ValueError(f"Check at most {MAX_GSTINS} GST numbers at a time")
        return {"mode": mode, "gstins": gstins}
    state, city = _place(data)
    if mode == "gst_find":
        keywords = maps_sources._clean_list(data.get("keywords"), "Product / category", MAX_NAMES, 80, True)
        sellers = data.get("max_sellers", 10)
        if sellers not in SELLER_CHOICES:
            raise ValueError("Unknown number of sellers")
        return {"mode": mode, "keywords": keywords, "audience": audience, "state": state, "city": city, "max_sellers": sellers}
    names = maps_sources._clean_list(data.get("keywords"), "Company name", MAX_NAMES, 80, False)
    ctype = "PTC" if mode == "pvtltd" else _choice(data, "company_type", COMPANY_TYPES, "", "company type")
    status = _choice(data, "status", STATUSES, "Active", "status")
    age = _choice(data, "age", AGES, "A" if mode == "pvtltd" else "", "age")
    industry = _choice(data, "industry", INDUSTRIES, "", "industry")
    pages = data.get("pages", 1)
    if pages not in PAGE_CHOICES:
        raise ValueError("Unknown number of pages")
    if not names and state == ALL_INDIA and not city and not industry:
        raise ValueError("Choose a state, city or industry (or search by company name)")
    if not names and industry and state != ALL_INDIA and not city:
        raise ValueError("The register lists industries per city - enter a city, or choose All India")
    return {"mode": mode, "keywords": names, "audience": audience, "state": state, "city": city, "company_type": ctype,
            "status": status, "age": age, "industry": industry, "pages": pages}


# ---------------------------------------------------------------------------
# CIN / GSTIN helpers (pure)
# ---------------------------------------------------------------------------

def decode_cin(cin: str) -> Dict[str, str]:
    cin = (cin or "").strip().upper()
    if LLPIN_RE.fullmatch(cin):
        return {"company_kind": "Limited Liability Partnership", "type_code": "LLP"}
    m = CIN_RE.fullmatch(cin)
    if not m:
        return {}
    listed, nic, st, year, ctype, _ = m.groups()
    return {"listed": "Listed" if listed == "L" else "Unlisted", "nic_code": nic, "cin_state": CIN_STATES.get(st, st),
            "year": year, "company_kind": CIN_TYPES.get(ctype, ctype), "type_code": ctype}


def gstin_checksum(first14: str) -> str:
    total = 0
    for i, ch in enumerate(first14):
        p = B36.index(ch) * (2 if i % 2 else 1)
        total += p // 36 + p % 36
    return B36[(36 - total % 36) % 36]


def decode_gstin(gstin: str) -> Dict[str, Any]:
    g = re.sub(r"\s", "", gstin or "").upper()
    out = {"gstin": g, "valid": False, "problem": "", "state": "", "pan": "", "entity": "", "registration": ""}
    if not re.fullmatch(r"\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]", g):
        out["problem"] = "Not in GSTIN format (15 characters: 2-digit state, PAN, entity number, Z, check digit)"
        return out
    if g[:2] not in GST_STATES:
        out["problem"] = f"Unknown state code {g[:2]}"
        return out
    if gstin_checksum(g[:14]) != g[14]:
        out["problem"] = "Check digit does not match - the number has a typo or is not real"
        return out
    pan = g[2:12]
    out.update(valid=True, state=GST_STATES[g[:2]], entity=PAN_ENTITY.get(pan[3], "Other"),
               pan=pan if pan[3] != "P" else "",          # a proprietor's PAN is personal - not shown on its own
               registration=f"Registration {B36.index(g[12])} in this state")
    return out


# ---------------------------------------------------------------------------
# ZaubaCorp lists
# ---------------------------------------------------------------------------

def zauba_state(state: str) -> str:
    return ZAUBA_STATES.get(state, state.upper())


def list_url(req: Dict[str, Any], page: int = 1) -> str:
    parts = []
    if req["industry"]:
        parts.append(f"nic-{req['industry']}")
    if req["city"]:
        parts.append(f"city-{quote(req['city'].upper())}")
    elif req["state"] != ALL_INDIA:
        parts.append(f"state-{quote(zauba_state(req['state']), safe='&')}")
    if req["company_type"]:
        parts.append(f"companytype-{req['company_type']}")
    if req["status"]:
        parts.append(f"status-{quote(req['status'])}")
    if req["age"]:
        parts.append(f"age-{req['age']}")
    if page > 1:
        parts.append(f"p-{page}")
    if not parts:
        return f"{ZAUBA}/companies-list"
    return f"{ZAUBA}/companies-list/{'/'.join(parts)}-company.html"


def make_result(source_id: str, **f: Any) -> Dict[str, Any]:
    row = {"source_id": source_id, "source": "ZaubaCorp (MCA)" if source_id == "zaubacorp" else "IndiaMART seller page",
           "company": "", "url": "", "cin": "", "status": "", "address": "", "capital": "", "gstin": "", "gst_state": "",
           "entity": "", "pan": "", "gst_valid": "", "gst_problem": "", "email": "", "phone": "", "website": "",
           "location": "", "category": "", "details": "", "year": "", "company_kind": "", "nic_code": "", "listed": "",
           "kind": "listing"}
    row.update(f)
    return row


def parse_company_list(html: str) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html or "", "html.parser")
    rows = []
    for card in soup.select("div.companies-list"):
        a = card.select_one("h2 a[href]")
        if not a:
            continue
        name = " ".join(a.get_text(" ", strip=True).split())
        status_el = card.select_one("div.badge:not(.badge-border)")
        cin = addr = capital = ""
        for b in card.select("div.badge.badge-border"):
            img = b.find("img")
            icon = f"{(img.get('alt') if img else '') or ''} {(img.get('src') if img else '') or ''}"
            text = " ".join(b.get_text(" ", strip=True).split())
            if "CIN" in icon or "ic_hashtag" in icon:
                cin = text
            elif "Address" in icon or "ic_location" in icon:
                # search pages repeat "city state pin country" after two spaces
                addr = re.split(r"\s{2,}", b.get_text(" ", strip=True))[0]
            elif text.startswith("₹"):
                capital = text
        if not cin:
            m = CIN_RE.search(a["href"]) or LLPIN_RE.search(a["href"])
            cin = m.group(0) if m else ""
        info = decode_cin(cin)
        addr_clean = re.sub(r"\s*,\s*", ", ", re.sub(r",{2,}", ",", addr)).strip(", ")
        rows.append(make_result(
            "zaubacorp", company=name, url=a["href"] if a["href"].startswith("http") else f"{ZAUBA}{a['href']}",
            cin=cin, status=" ".join(status_el.get_text(" ", strip=True).split()) if status_el else "",
            address=addr_clean, capital=capital, location=addr_clean, year=info.get("year", ""),
            company_kind=info.get("company_kind", ""), nic_code=info.get("nic_code", ""), listed=info.get("listed", ""),
            category=info.get("company_kind", "")))
    return rows


def _filter_rows(rows: List[Dict[str, Any]], req: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Name searches return every match in India - apply the form's filters ourselves."""
    out = []
    for r in rows:
        if req["company_type"] and decode_cin(r["cin"]).get("type_code") != req["company_type"]:
            continue
        if req["status"] and r["status"] and r["status"].lower() != req["status"].lower():   # search pages show no status
            continue
        if req["city"] and req["city"].lower() not in r["address"].lower():
            continue
        if not req["city"] and req["state"] != ALL_INDIA and req["state"].lower() not in r["address"].lower() \
                and zauba_state(req["state"]).lower() not in r["address"].lower():
            continue
        out.append(r)
    return out


def _fetcher(sleep=time.sleep) -> idr.Fetcher:
    return idr.Fetcher("zaubacorp", sleep, gap=2.0)      # 2 s between live requests to ZaubaCorp


def run_lists(req: Dict[str, Any], sleep=time.sleep) -> Tuple[List[Dict[str, Any]], List[str], int]:
    f = _fetcher(sleep)
    rows, errors = [], []
    if req["keywords"]:
        for name in req["keywords"]:
            try:
                status, html, _ = f.get(f"{ZAUBA}/companysearchresults/{quote(name)}")
                if status != 200:
                    raise requests.HTTPError(f"HTTP {status}")
                found = parse_company_list(html)
                kept = _filter_rows(found, req)
                if found and not kept:
                    errors.append(f"{name}: {len(found)} compan{'y' if len(found) == 1 else 'ies'} found, none match the filters")
                elif not found:
                    errors.append(f"{name}: no company with this name on the MCA register")
                rows += kept
            except Exception as e:  # noqa: BLE001
                errors.append(f"{name}: {_err(e)}")
        return rows, errors, f.requests
    for page in range(1, req["pages"] + 1):
        try:
            status, html, final = f.get(list_url(req, page))
            if status == 404 and page == 1 and req["industry"]:
                # some combinations have no industry page (e.g. LLPs have no NIC code): drop that filter and say so
                errors.append(f"The register has no industry list for this combination - showing results without the "
                              f"industry filter ({INDUSTRIES[req['industry']]})")
                req = {**req, "industry": ""}
                status, html, final = f.get(list_url(req, page))
        except Exception as e:  # noqa: BLE001
            errors.append(f"page {page}: {_err(e)}")
            break
        got = parse_company_list(html) if status == 200 else []
        if status == 404 or (status == 200 and not got and page == 1):
            errors.append("No companies match these filters on the register (try another city spelling, e.g. 'Bangalore', "
                          "or remove a filter)")
            break
        if status != 200:
            errors.append(f"page {page}: HTTP {status}")
            break
        rows += got
        if len(got) < 30:
            break
    return rows, errors, f.requests


def _err(e: Exception) -> str:
    if isinstance(e, requests.Timeout):
        return "ZaubaCorp did not answer in time - try again later"
    if isinstance(e, requests.ConnectionError):
        return "could not reach the site - check the internet connection"
    return f"{e.__class__.__name__}: {str(e)[:120]}"


# ---------------------------------------------------------------------------
# Company details (company page)
# ---------------------------------------------------------------------------

def parse_company_page(html: str) -> Dict[str, str]:
    soup = BeautifulSoup(html or "", "html.parser")
    text = " ".join(soup.get_text(" ", strip=True).split())

    def grab(pattern: str) -> str:
        m = re.search(pattern, text)
        return m.group(1).strip(" .,") if m else ""

    website = grab(r"Website\s+((?:https?://|www\.)\S+)")
    if website and not website.startswith("http"):
        website = "https://" + website
    return {
        "incorporated": grab(r"Date of Incorporation\s+(\d{4}-\d{2}-\d{2})"),
        "roc": grab(r"\bROC\s+(ROC[ A-Za-z()-]+?)\s+Registration Number"),
        "category": grab(r"Company Category\s+(.+?)\s+Company Sub Category"),
        "sub_category": grab(r"Company Sub Category\s+(.+?)\s+Class of Company"),
        "class": grab(r"Class of Company\s+(\w+)"),
        "activity": grab(r"NIC Description:\s*(.+?)(?:\[|\s+Number of Members|\s+Company Status|$)")[:160],
        "website": website if website and not se.is_platform(website) else "",
    }


def details(items: Any, sleep=time.sleep) -> Dict[str, Any]:
    if not isinstance(items, list) or not items:
        raise ValueError("Select at least one company")
    if len(items) > MAX_DETAILS_PER_CALL:
        raise ValueError(f"Get details for at most {MAX_DETAILS_PER_CALL} companies at a time")
    f = _fetcher(sleep)
    out = []
    for it in items:
        url = str((it or {}).get("url") or "")
        key = str((it or {}).get("key") or url)[:300]
        p = urlparse(url)
        if p.scheme != "https" or p.hostname != "www.zaubacorp.com" or not (CIN_RE.search(p.path) or LLPIN_RE.search(p.path)):
            out.append({"key": key, "status": "error", "error": "Not a ZaubaCorp company page"})
            continue
        try:
            status, html, _ = f.get(url)
            if status != 200:
                raise requests.HTTPError(f"HTTP {status}")
            out.append({"key": key, "status": "ok", **parse_company_page(html)})
        except Exception as e:  # noqa: BLE001
            out.append({"key": key, "status": "error", "error": _err(e)})
    return {"results": out}


# ---------------------------------------------------------------------------
# GST
# ---------------------------------------------------------------------------

def robots_allowed(url: str) -> bool:
    return robots_policy.allowed(url)


def gstins_in(html: str) -> List[str]:
    text = BeautifulSoup(html or "", "html.parser").get_text(" ", strip=True)
    return [g for g in dict.fromkeys(GSTIN_RE.findall(text)) if decode_gstin(g)["valid"]]


def gst_row(g: str, **f: Any) -> Dict[str, Any]:
    d = decode_gstin(g)
    return make_result(f.pop("source_id", "gst"), gstin=d["gstin"], gst_valid="Valid" if d["valid"] else "Invalid",
                       gst_problem=d["problem"], gst_state=d["state"], entity=d["entity"], pan=d["pan"], **f)


def run_gst_find(req: Dict[str, Any], sleep=time.sleep) -> Tuple[List[Dict[str, Any]], List[str], int]:
    listing_req = {"keywords": req["keywords"], "audience": req["audience"], "state": req["state"], "city": req["city"],
                   "sources": ["indiamart"]}
    run = idr._run_source("indiamart", idr.validate_request(listing_req), sleep)
    errors = list(run["errors"])
    sellers = [r for r in run["rows"] if r.get("url", "").startswith("https://www.indiamart.com/")]
    f = idr.Fetcher("indiamart", sleep)
    rows, skipped = [], 0
    for s in sellers[:req["max_sellers"]]:
        if not robots_allowed(s["url"]):
            skipped += 1
            continue
        try:
            status, html, _ = f.get(s["url"])
        except Exception as e:  # noqa: BLE001
            errors.append(f"{s['company']}: {_err(e)}")
            continue
        found = gstins_in(html) if status == 200 else []
        common = dict(source_id="indiamart_gst", company=s["company"], url=s["url"], phone=s.get("phone", ""),
                      location=s.get("location", ""), category=s.get("category", ""), details=s.get("product", ""))
        if found:
            rows.append(gst_row(found[0], **common))
        else:
            rows.append(make_result(**common, gst_problem="No GST number on the seller page"))
    if skipped:
        errors.append(f"{skipped} seller page(s) skipped: not allowed by IndiaMART's robots.txt")
    if len(sellers) > req["max_sellers"]:
        errors.append(f"Checked the first {req['max_sellers']} of {len(sellers)} sellers (choose more in 'Sellers to check')")
    return rows, errors, run["requests"] + f.requests


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

def search(data: Dict[str, Any], sleep=time.sleep) -> Dict[str, Any]:
    req = validate_request(data)
    t0 = time.time()
    if req["mode"] == "gst_check":
        rows = [gst_row(g, source_id="gst_check", company="", category="GST check") for g in req["gstins"]]
        valid = sum(r["gst_valid"] == "Valid" for r in rows)
        return {"query": {"mode": "gst_check", "count": len(rows)}, "results": rows, "total": len(rows),
                "sources": {"gst_check": {"name": "GSTIN check (offline)", "status": "ok", "count": valid,
                                          "seconds": 0, "errors": [f"{len(rows) - valid} invalid"] if valid < len(rows) else []}}}
    if req["mode"] == "gst_find":
        rows, errors, n = run_gst_find(req, sleep)
        name, sid = "IndiaMART seller pages", "indiamart_gst"
    else:
        rows, errors, n = run_lists(req, sleep)
        name, sid = "ZaubaCorp (MCA register)", "zaubacorp"
        seen, unique = set(), []
        for r in rows:
            if r["cin"] and r["cin"] in seen:
                continue
            seen.add(r["cin"])
            unique.append(r)
        rows = unique
    if req.get("audience") and rows:
        words = [w for a in req["audience"] for w in re.findall(r"[a-z0-9]{3,}", a.lower())]
        kept = [r for r in rows if any(w in f"{r['company']} {r['details']} {r['category']}".lower() for w in words)]
        if kept:
            rows = kept
        else:
            errors.append("No result mentions the target audience - showing all")
    status = "error" if errors and not rows else "ok"
    return {"query": {k: v for k, v in req.items() if k != "gstins"}, "results": rows, "total": len(rows),
            "sources": {sid: {"name": name, "status": status, "count": len(rows), "seconds": round(time.time() - t0, 1),
                              "errors": errors, "requests": n}}}


def result_to_raw_lead(r: Dict[str, Any]) -> Dict[str, str]:
    parts = []
    for label, key in (("CIN", "cin"), ("Status", "status"), ("Type", "company_kind"), ("Listed", "listed"),
                       ("Paid-up capital", "capital"), ("Incorporated", "incorporated"), ("Year", "year"),
                       ("Activity", "activity"), ("ROC", "roc"), ("GSTIN", "gstin"), ("GST state", "gst_state"),
                       ("Entity", "entity"), ("Product", "details")):
        if r.get(key) and not (key == "year" and r.get("incorporated")):
            parts.append(f"{label}: {r[key]}")
    website = r.get("website", "")
    if website and se.is_platform(website):
        website = ""
    is_gst = r.get("source_id", "").endswith("gst") or r.get("source_id") == "gst_check"
    return {
        "company_name": r.get("company", "") or r.get("gstin", ""),
        "email": r.get("email", ""),
        "mobile_number": r.get("phone", ""),
        "website": website,
        "location": r.get("address") or r.get("location") or r.get("gst_state", ""),
        "description": ". ".join(parts)[:800],
        "source": "Corporate Registries (GST via IndiaMART)" if is_gst else "Corporate Registries (ZaubaCorp / MCA)",
        "source_url": r.get("url", "") or (f"gstin:{r.get('gstin')}" if r.get("gstin") else ""),
        "lead_type": "GST Registered Business" if is_gst else ("New Company (under 1 year)" if r.get("year") and
                                                                 r["year"] >= str(time.gmtime().tm_year - 1) else "Registered Company"),
    }

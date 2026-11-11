"""
Job Portal Scraper - search many job portals for companies that are hiring.

A company hiring a "React Developer" in Gujarat is a sales lead for an IT agency
(staff augmentation / project outsourcing). This module searches the selected portals
for each job title in a chosen Indian state and returns one common result format.

Portal status (verified with live requests, 2026-11-11):
  available    - works with plain Python requests
  needs_key    - official API; works after you add a free API key to .env
  unavailable  - blocks automated requests (captcha / Cloudflare / JavaScript-only); listed so the
                 UI can show it greyed out with the reason. We do NOT try to bypass these blocks.

Public entry points (used by app.py):
  list_portals()                          -> portal catalog for the UI
  INDIAN_STATES                           -> state dropdown values
  search_jobs(titles, state, portal_ids)  -> {"jobs": [...], "portals": {...per-portal status...}}
  job_to_raw_lead(job)                    -> raw record for lead_normalizer.MasterLeadRegistry
"""

import concurrent.futures
import datetime
import html as html_lib
import json
import os
import re
import time
from typing import Any, Dict, List

import requests
from bs4 import BeautifulSoup

import env_loader  # noqa: F401  (loads .env for the API keys below)

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
TIMEOUT = 20
MAX_RESULTS_PER_TITLE = 50     # per portal, per job title
REQUEST_GAP_SECONDS = 1.0      # between requests to the SAME portal
MAX_TITLES = 10
ALL_INDIA = "All India"

# State -> the cities job portals usually list. Used to keep only results in the chosen state
# for portals that cannot filter by state themselves.
INDIAN_STATES: Dict[str, List[str]] = {
    "Andhra Pradesh": ["Visakhapatnam", "Vijayawada", "Guntur", "Tirupati", "Nellore", "Kakinada", "Amaravati"],
    "Arunachal Pradesh": ["Itanagar"],
    "Assam": ["Guwahati", "Dibrugarh", "Silchar", "Jorhat"],
    "Bihar": ["Patna", "Gaya", "Muzaffarpur", "Bhagalpur"],
    "Chhattisgarh": ["Raipur", "Bhilai", "Bilaspur", "Durg"],
    "Goa": ["Panaji", "Margao", "Vasco da Gama", "Mapusa"],
    "Gujarat": ["Ahmedabad", "Surat", "Vadodara", "Baroda", "Rajkot", "Gandhinagar", "Bhavnagar", "Jamnagar",
                "Anand", "Mehsana", "Mahesana", "Vapi", "Bharuch", "Junagadh", "Navsari", "Morbi"],
    "Haryana": ["Gurgaon", "Gurugram", "Faridabad", "Panipat", "Ambala", "Karnal", "Sonipat", "Hisar"],
    "Himachal Pradesh": ["Shimla", "Dharamshala", "Solan", "Mandi"],
    "Jharkhand": ["Ranchi", "Jamshedpur", "Dhanbad", "Bokaro"],
    "Karnataka": ["Bangalore", "Bengaluru", "Mysore", "Mysuru", "Mangalore", "Mangaluru", "Hubli", "Belgaum"],
    "Kerala": ["Kochi", "Cochin", "Trivandrum", "Thiruvananthapuram", "Kozhikode", "Calicut", "Thrissur"],
    "Madhya Pradesh": ["Indore", "Bhopal", "Jabalpur", "Gwalior", "Ujjain"],
    "Maharashtra": ["Mumbai", "Pune", "Nagpur", "Nashik", "Thane", "Navi Mumbai", "Aurangabad", "Kolhapur"],
    "Manipur": ["Imphal"],
    "Meghalaya": ["Shillong"],
    "Mizoram": ["Aizawl"],
    "Nagaland": ["Kohima", "Dimapur"],
    "Odisha": ["Bhubaneswar", "Cuttack", "Rourkela"],
    "Punjab": ["Mohali", "Ludhiana", "Amritsar", "Jalandhar", "Patiala"],
    "Rajasthan": ["Jaipur", "Jodhpur", "Udaipur", "Kota", "Ajmer"],
    "Sikkim": ["Gangtok"],
    "Tamil Nadu": ["Chennai", "Coimbatore", "Madurai", "Tiruchirappalli", "Trichy", "Salem", "Hosur"],
    "Telangana": ["Hyderabad", "Secunderabad", "Warangal"],
    "Tripura": ["Agartala"],
    "Uttar Pradesh": ["Noida", "Greater Noida", "Lucknow", "Kanpur", "Ghaziabad", "Agra", "Varanasi", "Prayagraj"],
    "Uttarakhand": ["Dehradun", "Haridwar", "Roorkee"],
    "West Bengal": ["Kolkata", "Howrah", "Durgapur", "Siliguri"],
    "Andaman and Nicobar Islands": ["Port Blair"],
    "Chandigarh": ["Chandigarh"],
    "Dadra and Nagar Haveli and Daman and Diu": ["Silvassa", "Daman", "Diu"],
    "Delhi": ["Delhi", "New Delhi"],
    "Jammu and Kashmir": ["Srinagar", "Jammu"],
    "Ladakh": ["Leh"],
    "Lakshadweep": ["Kavaratti"],
    "Puducherry": ["Puducherry", "Pondicherry"],
}


class PortalError(Exception):
    """A portal could not be searched (blocked, changed layout, network)."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "en-IN,en;q=0.9"})
    return s


def _get(session: requests.Session, url: str, **kwargs) -> requests.Response:
    r = session.get(url, timeout=TIMEOUT, **kwargs)
    if r.status_code in (403, 406, 429, 503):
        raise PortalError(f"blocked by the site (HTTP {r.status_code})")
    r.raise_for_status()
    return r


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _clean(text: Any) -> str:
    return re.sub(r"\s+", " ", html_lib.unescape(str(text or ""))).strip()


def _strip_html(text: Any) -> str:
    return _clean(re.sub(r"<[^>]+>", " ", str(text or "")))


def _epoch_ms_to_str(ms: Any) -> str:
    try:
        return datetime.datetime.fromtimestamp(int(ms) / 1000).strftime("%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError, OSError, OverflowError):
        return ""


def location_in_state(location: str, state: str) -> bool:
    """True if a free-text location belongs to the state (by state name or one of its cities)."""
    if not state or state == ALL_INDIA:
        return True
    loc = (location or "").lower()
    names = [state] + INDIAN_STATES.get(state, [])
    return any(re.search(rf"\b{re.escape(n.lower())}\b", loc) for n in names)


# Words that say nothing about WHICH job it is - ignored when checking relevance
GENERIC_TITLE_WORDS = {
    "developer", "developers", "engineer", "engineers", "senior", "junior", "sr", "jr", "lead", "trainee",
    "intern", "fresher", "the", "and", "for", "of", "in", "a", "an", "job", "jobs", "executive", "specialist",
}


def significant_words(title: str) -> List[str]:
    words = [w.strip(".") for w in re.findall(r"[a-z0-9+#.]+", title.lower())]
    return [w for w in words if w and w not in GENERIC_TITLE_WORDS]


def is_relevant(job: Dict[str, str], wanted: str) -> bool:
    """Every significant word of the searched title must appear in the job's title or skills.
    (Portals' own search is fuzzy: a 'React Developer' search also returns '.NET' or 'Inside Sales'.)
    A title made only of generic words ('Developer') keeps everything."""
    words = significant_words(wanted)
    if not words:
        return True
    text = f"{job.get('title', '')} {job.get('skills', '')}".lower()
    return all(re.search(rf"(?<![a-z0-9]){re.escape(w)}", text) for w in words)


def title_matches(job_title: str, wanted: str) -> bool:
    return is_relevant({"title": job_title}, wanted)


def make_job(portal_id: str, **fields) -> Dict[str, str]:
    job = {
        "portal_id": portal_id,
        "portal": PORTALS[portal_id]["name"],
        "title": "", "company": "", "location": "", "experience": "", "salary": "",
        "posted_at": "", "url": "", "skills": "", "description": "", "searched_title": "",
    }
    job.update({k: _clean(v) if k != "description" else _strip_html(v)[:600] for k, v in fields.items()})
    return job


# ---------------------------------------------------------------------------
# Portal adapters: each returns a list of jobs for ONE title in ONE state
# ---------------------------------------------------------------------------

def search_foundit(session, title: str, state: str) -> List[Dict]:
    params = {"start": 0, "limit": MAX_RESULTS_PER_TITLE, "query": title}
    if state != ALL_INDIA:
        params["locations"] = state
    r = _get(session, "https://www.foundit.in/home/api/searchResultsPage", params=params,
             headers={"Accept": "application/json"})
    jobs = []
    for j in r.json().get("data") or []:
        locs = j.get("locations") or []
        exp_min = (j.get("minimumExperience") or {}).get("years")
        exp_max = (j.get("maximumExperience") or {}).get("years")
        sal_min = (j.get("minimumSalary") or {}).get("absoluteValue") or 0
        sal_max = (j.get("maximumSalary") or {}).get("absoluteValue") or 0
        jobs.append(make_job(
            "foundit",
            title=j.get("title"),
            company=(j.get("company") or {}).get("name") or j.get("companyName"),
            location=", ".join(dict.fromkeys(l.get("city", "") for l in locs if l.get("city"))),
            experience=f"{exp_min}-{exp_max} yrs" if exp_min is not None and exp_max is not None else "",
            salary=f"INR {sal_min:,.0f} - {sal_max:,.0f}/yr" if sal_max else "",
            posted_at=_epoch_ms_to_str(j.get("postedAt") or j.get("createdAt")),
            url=f"https://www.foundit.in{j['jdUrl']}" if j.get("jdUrl") else j.get("redirectUrl", ""),
            skills=", ".join(s.get("text", "") for s in (j.get("skills") or [])[:10]),
            description=j.get("description", ""),
        ))
    return jobs


def _next_rsc_payload(page: str) -> str:
    """Joins the Next.js App Router 'self.__next_f.push([1,"..."])' chunks into one string."""
    chunks = re.findall(r'self\.__next_f\.push\(\[1,"((?:[^"\\]|\\.)*)"\]\)', page)
    out = []
    for c in chunks:
        try:
            out.append(json.loads(f'"{c}"'))
        except json.JSONDecodeError:
            continue
    return "".join(out)


def _shine_page(session, path: str) -> List[Dict]:
    r = _get(session, f"https://www.shine.com/job-search/{path}")
    payload = _next_rsc_payload(r.text)
    match = re.search(r'"jobs"\s*:\s*\[', payload)
    if not match:
        raise PortalError("job list not found in page (layout may have changed)")
    try:
        data, _ = json.JSONDecoder().raw_decode(payload, match.end() - 1)
    except json.JSONDecodeError as e:
        raise PortalError(f"could not read job list ({e.msg})")
    return data


def search_shine(session, title: str, state: str) -> List[Dict]:
    # Shine's location pages work by city and still mix in other cities, so search the state and
    # its biggest city, then keep only jobs located in the state.
    base = f"{slugify(title)}-jobs"
    paths = [base] if state == ALL_INDIA else [f"{base}-in-{slugify(state)}"] + [
        f"{base}-in-{slugify(c)}" for c in INDIAN_STATES.get(state, [])[:1]]
    data, seen = [], set()
    for i, path in enumerate(paths):
        if i:
            time.sleep(REQUEST_GAP_SECONDS)
        for j in _shine_page(session, path):
            if j.get("id") not in seen:
                seen.add(j.get("id"))
                data.append(j)
    jobs = []
    for j in data:
        if not location_in_state(", ".join(j.get("locations") or []), state):
            continue
        jobs.append(make_job(
            "shine",
            title=j.get("title"), company=j.get("companyName"),
            location=", ".join(j.get("locations") or []),
            experience=j.get("experienceLabel"), salary=j.get("salaryLabel"),
            posted_at=(j.get("postedAt") or "").replace("T", " "),
            url=f"https://www.shine.com{j['detailUrl']}" if j.get("detailUrl") else "",
            skills=", ".join(j.get("skills") or []),
        ))
    return jobs[:MAX_RESULTS_PER_TITLE]


def search_internshala(session, title: str, state: str) -> List[Dict]:
    # Internshala has city pages, not state pages: search by keyword, filter by state afterwards.
    r = _get(session, f"https://internshala.com/jobs/keywords-{slugify(title)}/")
    soup = BeautifulSoup(r.text, "html.parser")
    jobs = []
    for card in soup.select(".individual_internship[data-href]"):
        title_el = card.select_one(".job-title-href")
        if not title_el:
            continue
        loc = ", ".join(_clean(a.get_text()) for a in card.select(".locations a, .locations span") if a.get_text(strip=True))
        salary_el = card.select_one(".stipend, .salary")
        exp_el = card.select_one(".ic-16-briefcase + span, .experience")
        kind = card.get("employment_type", "")
        jobs.append(make_job(
            "internshala",
            title=title_el.get_text() + (" (Internship)" if kind == "internship" else ""),
            company=(card.select_one(".company-name") or title_el).get_text(),
            location=loc, salary=salary_el.get_text() if salary_el else "",
            experience=exp_el.get_text() if exp_el else "",
            url=f"https://internshala.com{card['data-href']}",
            skills=", ".join(_clean(s.get_text()) for s in card.select(".job_skill")[:10]),
            description=(card.select_one(".about_job .text") or title_el).get_text(),
        ))
    return [j for j in jobs if location_in_state(j["location"], state) or "work from home" in j["location"].lower()]


def search_freshersworld(session, title: str, state: str) -> List[Dict]:
    path = f"{slugify(title)}-jobs" + ("" if state == ALL_INDIA else f"-in-{slugify(state)}")
    r = _get(session, f"https://www.freshersworld.com/jobs/jobsearch/{path}")
    soup = BeautifulSoup(r.text, "html.parser")
    jobs = []
    for card in soup.select(".job-container[job_display_url]"):
        title_el = card.select_one(".seo_title")
        title_text = title_el.find(string=True, recursive=False) if title_el else ""
        # "Sr. Python Developer Jobs Opening in ACME at Ahmedabad" -> "Sr. Python Developer"
        title_text = re.sub(r"\s+(Multiple\s+)?Jobs?\s+(Opening\s+)?in\s+.*$", "", _clean(title_text), flags=re.I)
        jobs.append(make_job(
            "freshersworld",
            title=title_text or (title_el.get_text() if title_el else ""),
            company=(card.select_one(".company-name") or card).get_text() if card.select_one(".company-name") else "",
            location=", ".join(_clean(a.get_text()) for a in card.select(".job-location a")),
            experience=(card.select_one(".experience") or card).get_text() if card.select_one(".experience") else "",
            url=card.get("job_display_url", ""),
        ))
    return [j for j in jobs if location_in_state(j["location"], state)]


def search_linkedin(session, title: str, state: str) -> List[Dict]:
    location = "India" if state == ALL_INDIA else f"{state}, India"
    jobs = []
    for start in range(0, MAX_RESULTS_PER_TITLE, 25):
        r = _get(session, "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search",
                 params={"keywords": title, "location": location, "start": start})
        soup = BeautifulSoup(r.text, "html.parser")
        cards = soup.select("li")
        for li in cards:
            t = li.select_one(".base-search-card__title")
            link = li.select_one("a.base-card__full-link")
            if not t:
                continue
            when = li.select_one("time")
            jobs.append(make_job(
                "linkedin",
                title=t.get_text(),
                company=(li.select_one(".base-search-card__subtitle") or t).get_text(),
                location=(li.select_one(".job-search-card__location") or t).get_text()
                if li.select_one(".job-search-card__location") else "",
                posted_at=when.get("datetime", "") if when else "",
                url=(link.get("href", "").split("?")[0]) if link else "",
            ))
        if len(cards) < 25:
            break
        time.sleep(REQUEST_GAP_SECONDS)
    return jobs


def search_apna(session, title: str, state: str) -> List[Dict]:
    r = _get(session, "https://apna.co/jobs", params={"search": "true", "text": title})
    soup = BeautifulSoup(r.text, "html.parser")
    jobs = []
    for card in soup.select('a[data-testid="job-card"]'):
        parts = [p for p in card.stripped_strings]
        if len(parts) < 3:
            continue
        exp = next((p for p in parts if p.lower().startswith(("min.", "fresher"))), "")
        salary = parts[3] if len(parts) > 3 and ("₹" in parts[3] or "disclosed" in parts[3].lower()) else ""
        jobs.append(make_job(
            "apna", title=parts[0], company=parts[1], location=parts[2],
            salary=salary, experience=exp, url=f"https://apna.co{card.get('href', '')}",
        ))
    return [j for j in jobs if location_in_state(j["location"], state)]


def search_instahyre(session, title: str, state: str) -> List[Dict]:
    r = _get(session, "https://www.instahyre.com/api/v1/job_search",
             params={"company_size": 0, "isLandingPage": "true", "job_type": 0, "search": "true",
                     "skills": title, "years": 0, "limit": MAX_RESULTS_PER_TITLE},
             headers={"Accept": "application/json"})
    jobs = []
    for j in r.json().get("objects") or []:
        jobs.append(make_job(
            "instahyre",
            title=j.get("title") or j.get("candidate_title"),
            company=(j.get("employer") or {}).get("company_name"),
            location=j.get("locations"), url=j.get("public_url"),
            skills=", ".join((j.get("keywords") or [])[:10]),
            description=(j.get("employer") or {}).get("instahyre_note", ""),
        ))
    return [j for j in jobs if location_in_state(j["location"], state)
            or "work from home" in j["location"].lower()]


def search_remotive(session, title: str, state: str) -> List[Dict]:
    r = _get(session, "https://remotive.com/api/remote-jobs", params={"search": title, "limit": MAX_RESULTS_PER_TITLE})
    return [make_job(
        "remotive", title=j.get("title"), company=j.get("company_name"),
        location=j.get("candidate_required_location") or "Remote", salary=j.get("salary"),
        posted_at=(j.get("publication_date") or "").replace("T", " "), url=j.get("url"),
        skills=", ".join((j.get("tags") or [])[:10]), description=j.get("description", ""),
    ) for j in (r.json().get("jobs") or [])]


def search_remoteok(session, title: str, state: str) -> List[Dict]:
    r = _get(session, "https://remoteok.com/api", headers={"Accept": "application/json"})
    jobs = []
    for j in r.json():
        if not isinstance(j, dict) or not j.get("position") or not title_matches(j["position"], title):
            continue
        sal = f"USD {j['salary_min']:,} - {j['salary_max']:,}" if j.get("salary_max") else ""
        jobs.append(make_job(
            "remoteok", title=j.get("position"), company=j.get("company"),
            location=j.get("location") or "Remote", salary=sal,
            posted_at=(j.get("date") or "")[:19].replace("T", " "), url=j.get("url") or j.get("apply_url"),
            skills=", ".join((j.get("tags") or [])[:10]), description=j.get("description", ""),
        ))
    return jobs[:MAX_RESULTS_PER_TITLE]


def search_arbeitnow(session, title: str, state: str) -> List[Dict]:
    r = _get(session, "https://www.arbeitnow.com/api/job-board-api", headers={"Accept": "application/json"})
    jobs = []
    for j in r.json().get("data") or []:
        if not title_matches(j.get("title", ""), title):
            continue
        jobs.append(make_job(
            "arbeitnow", title=j.get("title"), company=j.get("company_name"),
            location=("Remote" if j.get("remote") else "") or j.get("location"),
            posted_at=datetime.datetime.fromtimestamp(j["created_at"]).strftime("%Y-%m-%d %H:%M:%S")
            if j.get("created_at") else "",
            url=j.get("url"), skills=", ".join((j.get("tags") or [])[:10]), description=j.get("description", ""),
        ))
    return jobs[:MAX_RESULTS_PER_TITLE]


def search_adzuna(session, title: str, state: str) -> List[Dict]:
    app_id, app_key = os.getenv("ADZUNA_APP_ID", ""), os.getenv("ADZUNA_APP_KEY", "")
    if not (app_id and app_key):
        raise PortalError("ADZUNA_APP_ID / ADZUNA_APP_KEY not set in .env")
    params = {"app_id": app_id, "app_key": app_key, "what": title, "results_per_page": MAX_RESULTS_PER_TITLE,
              "content-type": "application/json"}
    if state != ALL_INDIA:
        params["where"] = state
    r = _get(session, "https://api.adzuna.com/v1/api/jobs/in/search/1", params=params)
    return [make_job(
        "adzuna", title=j.get("title"), company=(j.get("company") or {}).get("display_name"),
        location=(j.get("location") or {}).get("display_name"),
        salary=f"INR {j['salary_min']:,.0f} - {j['salary_max']:,.0f}" if j.get("salary_max") else "",
        posted_at=(j.get("created") or "")[:19].replace("T", " "), url=j.get("redirect_url"),
        description=j.get("description", ""),
    ) for j in (r.json().get("results") or [])]


def search_jooble(session, title: str, state: str) -> List[Dict]:
    key = os.getenv("JOOBLE_API_KEY", "")
    if not key:
        raise PortalError("JOOBLE_API_KEY not set in .env")
    body = {"keywords": title, "location": "India" if state == ALL_INDIA else f"{state}, India"}
    r = session.post(f"https://jooble.org/api/{key}", json=body, timeout=TIMEOUT)
    if r.status_code in (401, 403):
        raise PortalError(f"Jooble rejected the API key (HTTP {r.status_code})")
    r.raise_for_status()
    return [make_job(
        "jooble", title=j.get("title"), company=j.get("company"), location=j.get("location"),
        salary=j.get("salary"), posted_at=(j.get("updated") or "")[:19].replace("T", " "),
        url=j.get("link"), description=j.get("snippet", ""),
    ) for j in (r.json().get("jobs") or [])[:MAX_RESULTS_PER_TITLE]]


# ---------------------------------------------------------------------------
# Portal catalog
# ---------------------------------------------------------------------------

def _p(name, status, search=None, reason="", note="", region="India", website=""):
    return {"name": name, "status": status, "search": search, "reason": reason, "note": note,
            "region": region, "website": website}


PORTALS: Dict[str, Dict[str, Any]] = {
    # --- available: verified working with plain requests ---
    "foundit": _p("Foundit (Monster India)", "available", search_foundit, website="foundit.in"),
    "shine": _p("Shine.com", "available", search_shine, website="shine.com"),
    "linkedin": _p("LinkedIn Jobs (guest)", "available", search_linkedin, website="linkedin.com",
                   note="Uses LinkedIn's public guest job search. Automated access is against LinkedIn's terms; "
                        "heavy use can get your IP blocked."),
    "internshala": _p("Internshala", "available", search_internshala, website="internshala.com",
                      note="Includes internships. State is matched from the job's city."),
    "freshersworld": _p("Freshersworld", "available", search_freshersworld, website="freshersworld.com"),
    "apna": _p("Apna.co", "available", search_apna, website="apna.co",
               note="State is matched from the job's city."),
    "instahyre": _p("Instahyre", "available", search_instahyre, website="instahyre.com",
                    note="Searches by skill; state is matched from the job's city."),
    "remotive": _p("Remotive (remote jobs API)", "available", search_remotive, region="Remote / worldwide",
                   website="remotive.com", note="Worldwide remote jobs - the State filter does not apply."),
    "remoteok": _p("RemoteOK (remote jobs API)", "available", search_remoteok, region="Remote / worldwide",
                   website="remoteok.com", note="Worldwide remote jobs - the State filter does not apply."),
    "arbeitnow": _p("Arbeitnow (jobs API)", "available", search_arbeitnow, region="Europe / remote",
                    website="arbeitnow.com", note="Mostly Europe/remote jobs - the State filter does not apply."),
    # --- needs a free API key ---
    "adzuna": _p("Adzuna (official API)", "needs_key", search_adzuna, website="adzuna.in",
                 reason="Add ADZUNA_APP_ID and ADZUNA_APP_KEY to .env (free at developer.adzuna.com)"),
    "jooble": _p("Jooble (official API)", "needs_key", search_jooble, website="jooble.org",
                 reason="Add JOOBLE_API_KEY to .env (free at jooble.org/api/about)"),
    # --- unavailable: block automated requests ---
    "naukri": _p("Naukri.com", "unavailable", reason="Blocks automated requests (HTTP 406 + reCAPTCHA)"),
    "indeed": _p("Indeed India", "unavailable", reason="Blocks automated requests (Cloudflare security check)"),
    "glassdoor": _p("Glassdoor", "unavailable", reason="Blocks automated requests (Cloudflare challenge)"),
    "wellfound": _p("Wellfound (AngelList)", "unavailable", reason="Blocks automated requests (Cloudflare challenge)"),
    "careerjet": _p("Careerjet", "unavailable", reason="Blocks automated requests (Cloudflare challenge)"),
    "timesjobs": _p("TimesJobs", "unavailable", reason="Job list loads only with JavaScript in a browser"),
    "cutshort": _p("Cutshort", "unavailable", reason="Job list loads only with JavaScript in a browser"),
    "hirist": _p("Hirist", "unavailable", reason="Job list loads only with JavaScript in a browser"),
    "ncs": _p("National Career Service (NCS)", "unavailable", reason="Search works only through an interactive form"),
}


def _effective_status(portal: Dict[str, Any]) -> str:
    if portal["status"] != "needs_key":
        return portal["status"]
    keys = {"Adzuna (official API)": ("ADZUNA_APP_ID", "ADZUNA_APP_KEY"),
            "Jooble (official API)": ("JOOBLE_API_KEY",)}.get(portal["name"], ())
    return "available" if keys and all(os.getenv(k) for k in keys) else "needs_key"


def list_portals() -> List[Dict[str, str]]:
    """Catalog for the UI: available first, then needs-key, then unavailable."""
    order = {"available": 0, "needs_key": 1, "unavailable": 2}
    items = []
    for pid, p in PORTALS.items():
        status = _effective_status(p)
        items.append({"id": pid, "name": p["name"], "status": status, "region": p["region"],
                      "reason": "" if status == "available" else p["reason"], "note": p["note"],
                      "website": p["website"]})
    return sorted(items, key=lambda x: (order[x["status"]], x["name"].lower()))


# ---------------------------------------------------------------------------
# Search orchestration
# ---------------------------------------------------------------------------

def _search_one_portal(pid: str, titles: List[str], state: str) -> Dict[str, Any]:
    portal = PORTALS[pid]
    session = _session()
    jobs, errors = [], []
    started = time.time()
    for i, title in enumerate(titles):
        if i:
            time.sleep(REQUEST_GAP_SECONDS)
        try:
            found = [j for j in portal["search"](session, title, state) if is_relevant(j, title)]
            for job in found:
                job["searched_title"] = title
            jobs.extend(found)
        except PortalError as e:
            errors.append(f"{title}: {e}")
        except (requests.RequestException, ValueError, KeyError) as e:
            errors.append(f"{title}: {e.__class__.__name__}: {str(e)[:120]}")
    status = "ok" if not errors else ("partial" if jobs else "error")
    return {"jobs": jobs, "status": status, "count": len(jobs), "errors": errors,
            "seconds": round(time.time() - started, 1)}


def _dedupe(jobs: List[Dict[str, str]]) -> List[Dict[str, str]]:
    seen, out = set(), []
    for j in jobs:
        key = j["url"] or f"{j['title'].lower()}|{j['company'].lower()}|{j['portal_id']}"
        if key in seen:
            continue
        seen.add(key)
        out.append(j)
    return out


def validate_request(titles: Any, state: Any, portal_ids: Any) -> Dict[str, Any]:
    """Returns {"titles", "state", "portal_ids"} or raises ValueError with a user-facing message."""
    if not isinstance(titles, list):
        raise ValueError("titles must be a list of job titles")
    clean_titles = list(dict.fromkeys(_clean(t) for t in titles if isinstance(t, str) and _clean(t)))
    if not clean_titles:
        raise ValueError("Enter at least one job title")
    if len(clean_titles) > MAX_TITLES:
        raise ValueError(f"Enter at most {MAX_TITLES} job titles")
    if any(len(t) > 80 for t in clean_titles):
        raise ValueError("Each job title must be 80 characters or less")
    if state not in INDIAN_STATES and state != ALL_INDIA:
        raise ValueError("Select a valid state")
    if not isinstance(portal_ids, list) or not portal_ids:
        raise ValueError("Select at least one job portal")
    unknown = [p for p in portal_ids if p not in PORTALS]
    if unknown:
        raise ValueError(f"Unknown job portal: {', '.join(map(str, unknown))}")
    return {"titles": clean_titles, "state": state, "portal_ids": list(dict.fromkeys(portal_ids))}


def search_jobs(titles: List[str], state: str, portal_ids: List[str]) -> Dict[str, Any]:
    req = validate_request(titles, state, portal_ids)
    portal_status: Dict[str, Dict[str, Any]] = {}
    runnable = []
    for pid in req["portal_ids"]:
        status = _effective_status(PORTALS[pid])
        if status == "available":
            runnable.append(pid)
        else:
            portal_status[pid] = {"status": "skipped", "count": 0, "errors": [PORTALS[pid]["reason"]], "seconds": 0}

    all_jobs: List[Dict[str, str]] = []
    if runnable:
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, len(runnable))) as pool:
            futures = {pool.submit(_search_one_portal, pid, req["titles"], req["state"]): pid for pid in runnable}
            for fut in concurrent.futures.as_completed(futures):
                pid = futures[fut]
                result = fut.result()
                all_jobs.extend(result.pop("jobs"))
                portal_status[pid] = result

    for pid in portal_status:
        portal_status[pid]["name"] = PORTALS[pid]["name"]
    jobs = _dedupe(all_jobs)
    jobs.sort(key=lambda j: j["posted_at"] or "", reverse=True)
    return {"jobs": jobs, "total": len(jobs), "portals": portal_status,
            "query": {"titles": req["titles"], "state": req["state"]}}


# ---------------------------------------------------------------------------
# Save to leads
# ---------------------------------------------------------------------------

def job_to_raw_lead(job: Dict[str, Any]) -> Dict[str, str]:
    """A job posting -> a lead: the hiring company may need developers or an IT partner."""
    details = [f"Hiring: {job.get('title', '')}"]
    for label, key in (("Location", "location"), ("Experience", "experience"), ("Salary", "salary"),
                       ("Skills", "skills")):
        if job.get(key):
            details.append(f"{label}: {job[key]}")
    if job.get("description"):
        details.append(str(job["description"]))
    return {
        "company_name": job.get("company") or job.get("title", ""),
        "description": ". ".join(details),
        "source": f"Job Portal ({job.get('portal', job.get('portal_id', ''))})",
        "source_url": job.get("url", ""),
        "location": job.get("location", ""),
        "lead_type": "Job Posting",
        "posted_at": job.get("posted_at", ""),
    }


if __name__ == "__main__":
    import sys
    result = search_jobs(sys.argv[1:] or ["React Developer"], "Gujarat",
                         [p["id"] for p in list_portals() if p["status"] == "available"])
    for pid, st in result["portals"].items():
        print(f"{st['name']:<30} {st['status']:<8} {st['count']:>4} jobs  {st['seconds']}s  {'; '.join(st['errors'])[:110]}")
    print(f"\nTotal unique jobs: {result['total']}")
    for j in result["jobs"][:10]:
        print(f" - [{j['portal']}] {j['title'][:45]} | {j['company'][:30]} | {j['location'][:30]}")

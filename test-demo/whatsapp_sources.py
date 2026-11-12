"""Scraping / Mining -> WhatsApp Groups: public WhatsApp group invite links for a topic.

Only the group name (as the search engine shows it) and the public invite link are collected.

Sources:
  invite_links      search engine results that ARE invite links (site:chat.whatsapp.com) - name from the title
  link_directories  public "WhatsApp group links" pages found through the search engine; invite links are taken
                    from the search snippet and, for at most DIRECTORY_PAGES pages, from the page itself
                    (guarded fetch, HTML cache, honest User-Agent)
  group_members     unavailable: member phone numbers need joining groups with automation, which WhatsApp bans,
                    and India's DPDP Act 2023 protects personal numbers.

We never request chat.whatsapp.com / whatsapp.com ourselves (automated access is against WhatsApp's terms).
"""
import re
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup

import deep_search
import maps_sources
import search_engine as se
from job_portals import ALL_INDIA, INDIAN_STATES

MAX_KEYWORDS = 5
MAX_RESULTS_PER_SOURCE = 60
DIRECTORY_PAGES = 5
CITY_RE = re.compile(r"^[A-Za-z .'-]{1,60}$")
INVITE_RE = re.compile(r"(?:https?://)?chat\.whatsapp\.com/(?:invite/)?([A-Za-z0-9]{18,32})\b")
TITLE_NOISE = re.compile(r"\s*[-|:]?\s*(WhatsApp Group Invite|Join (?:my )?WhatsApp Group|WhatsApp Group Link|"
                         r"WhatsApp Group|WhatsApp)\s*$", re.I)

SOURCES = {
    "invite_links": {"name": "Invite links (search engine)", "kind": "search",
                     "note": "Invite links the search engine has indexed (needs Brave / Serper for good results)."},
    "link_directories": {"name": "Group link directories", "kind": "search",
                         "note": "Public pages that list group links for a topic; links are read from up to 5 pages."},
    "group_members": {"name": "Group members / phone numbers", "kind": "members",
                      "unavailable": "Needs joining groups with automation (WhatsApp bans the number) and personal "
                                     "numbers are protected by India's DPDP Act 2023"},
}


def source_status(sid: str) -> str:
    return "unavailable" if SOURCES[sid].get("unavailable") else "available"


def list_sources() -> List[Dict[str, Any]]:
    return [{"id": sid, "name": s["name"], "kind": s["kind"], "status": source_status(sid), "note": s.get("note", ""),
             "reason": s.get("unavailable", ""), "keys": []} for sid, s in SOURCES.items()]


def validate_request(data: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("Invalid request")
    keywords = maps_sources._clean_list(data.get("keywords"), "Topic", MAX_KEYWORDS, 80, True)
    audience = maps_sources._clean_list(data.get("audience"), "Target audience", 5, 60, False)
    state = data.get("state") or ALL_INDIA
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


def invite_url(code: str) -> str:
    return f"https://chat.whatsapp.com/{code}"


def make_result(source_id: str, code: str, name: str, keyword: str, found_on: str = "", details: str = "",
                location: str = "") -> Dict[str, Any]:
    name = " ".join((name or "").split())[:120]
    return {"source_id": source_id, "source": SOURCES[source_id]["name"], "company": name or f"WhatsApp group {code[:6]}…",
            "group_name": name, "invite_code": code, "url": invite_url(code), "found_on": found_on,
            "email": "", "phone": "", "website": "", "location": location, "category": keyword,
            "keyword": keyword, "details": " ".join((details or "").split())[:300], "kind": "listing"}


def clean_group_name(title: str) -> str:
    t = TITLE_NOISE.sub("", title or "").strip(" -|:")
    return "" if t.lower() in ("", "whatsapp", "whatsapp group", "join group chat") else t


def codes_in(text: str) -> List[str]:
    return list(dict.fromkeys(INVITE_RE.findall(text or "")))


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------

def search_invites(keyword: str, req: Dict[str, Any]) -> List[Dict[str, Any]]:
    place = se.place_text(req["state"], req["city"])
    out = []
    for i, q in enumerate([f'site:chat.whatsapp.com "{keyword}"', f'site:chat.whatsapp.com "{keyword}" {place}']):
        if i:
            time.sleep(se.GAP_SECONDS[req["engine_used"]])
        try:
            hits = se.ENGINE_FUNCS[req["engine_used"]](q, 25, "any", requests.Session())
        except se.RateLimited:
            if out:
                return out            # keep what the first query found
            raise
        for h in hits:
            url = h.get("url") or ""
            if se.domain_of(url) != "chat.whatsapp.com":
                continue                      # engines that ignore site: return unrelated pages
            for code in codes_in(url):
                out.append(make_result("invite_links", code, clean_group_name(h.get("title", "")), keyword,
                                       details=h.get("snippet", ""), location=place if place != "India" else ""))
    return out


def _links_from_page(html: str) -> List[Dict[str, str]]:
    soup = BeautifulSoup(html or "", "html.parser")
    found = []
    for a in soup.find_all("a", href=True):
        for code in codes_in(a["href"]):
            label = " ".join(a.get_text(" ", strip=True).split())
            if not label or "chat.whatsapp.com" in label.lower() or label.lower() in ("join", "join now", "click here", "join group"):
                prev = a.find_previous(["h2", "h3", "h4", "strong", "b"])
                label = prev.get_text(" ", strip=True) if prev else ""
            found.append({"code": code, "name": clean_group_name(label)})
    return found


def search_directories(keyword: str, req: Dict[str, Any], budget: List[int]) -> List[Dict[str, Any]]:
    place = se.place_text(req["state"], req["city"])
    q = f'"{keyword}" "whatsapp group link" {place}'
    out = []
    for h in se.ENGINE_FUNCS[req["engine_used"]](q, 15, "any", requests.Session()):
        url = h.get("url") or ""
        dom = se.domain_of(url)
        if not dom or dom.endswith("whatsapp.com") or se._matches(dom, se.JUNK_DOMAINS) or se.is_platform(url):
            continue
        for code in codes_in(f"{h.get('title', '')} {h.get('snippet', '')}"):
            out.append(make_result("link_directories", code, "", keyword, found_on=url))
        if budget[0] < DIRECTORY_PAGES:
            budget[0] += 1
            html = deep_search.fetch(url)     # guarded + cached + honest User-Agent; never whatsapp.com
            for link in _links_from_page(html):
                out.append(make_result("link_directories", link["code"], link["name"], keyword, found_on=url,
                                       location=place if place != "India" else ""))
    return out


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

def _run_source(sid: str, req: Dict[str, Any]) -> Dict[str, Any]:
    t0, rows, errors, budget = time.time(), [], [], [0]
    for i, kw in enumerate(req["keywords"]):
        if i:
            time.sleep(se.GAP_SECONDS.get(req["engine_used"], 1.0))
        try:
            rows += search_invites(kw, req) if sid == "invite_links" else search_directories(kw, req, budget)
        except se.RateLimited as e:
            errors.append(f"{kw}: {e}")
            break
        except requests.Timeout:
            errors.append(f"{kw}: {SOURCES[sid]['name']} did not answer in time (server busy) - try again later")
        except requests.ConnectionError:
            errors.append(f"{kw}: could not reach {SOURCES[sid]['name']} - check the internet connection")
        except Exception as e:  # noqa: BLE001 - one source must never fail the whole search
            errors.append(f"{kw}: {e.__class__.__name__}: {str(e)[:120]}")
    if req["audience"] and rows:
        words = [w for a in req["audience"] for w in re.findall(r"[a-z0-9]{3,}", a.lower())]
        kept = [r for r in rows if any(w in f"{r['group_name']} {r['details']} {r['category']}".lower() for w in words)]
        if kept:
            rows = kept
        else:
            errors.append("No group mentions the target audience - showing all groups")
    status = "error" if errors and not rows and len(errors) >= len(req["keywords"]) else "ok"
    return {"rows": rows, "status": status, "errors": errors, "seconds": round(time.time() - t0, 1)}


def search(data: Dict[str, Any]) -> Dict[str, Any]:
    req = validate_request(data)
    with ThreadPoolExecutor(max_workers=len(req["sources"])) as pool:
        runs = dict(zip(req["sources"], pool.map(lambda sid: _run_source(sid, req), req["sources"])))
    by_code: Dict[str, Dict[str, Any]] = {}
    results, statuses = [], {}
    for sid in req["sources"]:
        count = 0
        for r in runs[sid]["rows"]:
            kept: Optional[Dict[str, Any]] = by_code.get(r["invite_code"])
            if kept:                                   # same group seen twice: keep the best name / details
                if not kept["group_name"] and r["group_name"]:
                    kept["group_name"] = kept["company"] = r["group_name"]
                for f in ("found_on", "details", "location"):
                    if not kept.get(f) and r.get(f):
                        kept[f] = r[f]
                continue
            if count >= MAX_RESULTS_PER_SOURCE:
                continue
            by_code[r["invite_code"]] = r
            results.append(r)
            count += 1
        statuses[sid] = {"name": SOURCES[sid]["name"], "status": runs[sid]["status"], "count": count,
                         "seconds": runs[sid]["seconds"], "errors": runs[sid]["errors"]}
    results.sort(key=lambda r: (not r["group_name"], r["group_name"].lower()))
    hint = ""
    if not results and req["engine_used"] == "duckduckgo":
        hint = ("DuckDuckGo returned nothing useful for these queries (it often ignores site: and quoted searches "
                "from apps). Add a free BRAVE_SEARCH_API_KEY / SERPER_API_KEY, or run your own SearXNG (SEARXNG_URL, no key), for reliable results.")
    return {"query": {k: req[k] for k in ("keywords", "audience", "state", "city", "engine")},
            "results": results, "total": len(results), "sources": statuses, "engine": req["engine_used"], "hint": hint}


def result_to_raw_lead(r: Dict[str, Any]) -> Dict[str, str]:
    details = [f"WhatsApp group invite: {r.get('url', '')}", f"Topic: {r.get('category', '')}"]
    if r.get("found_on"):
        details.append(f"Found on {r['found_on']}")
    return {
        "company_name": r.get("group_name") or r.get("company", ""),
        "location": r.get("location", ""),
        "description": ". ".join(x for x in details if x)[:600],
        "source": f"WhatsApp Groups ({SOURCES.get(r.get('source_id', ''), {}).get('name', '')})",
        "source_url": r.get("url", ""),
        "lead_type": "WhatsApp Group (community)",
    }

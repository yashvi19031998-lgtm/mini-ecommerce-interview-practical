"""Scraping / Mining -> Global Directories (companies outside India from official / open sources).

STUB - the contract below is already wired into app.py (/api/global-directories/*), frontend/lib/api.js and
frontend/app/page.js. Implement the functions WITHOUT changing their names, arguments or return shapes.

Return shapes (same as crm_sources.py so the UI, Deep Search and Save work the same way):

  list_sources() -> [{"id", "name", "kind": "directory"|"register", "status": "available"|"needs_key"|"unavailable",
                      "note", "reason", "keys": [env var names], "countries": ["GB", ...] or ["*"]}]
  COUNTRIES      -> [{"id": "GB", "name": "United Kingdom"}, ...]
  validate_request(data) -> clean dict, or raises ValueError("user-friendly message")
  search(data)   -> {"query": {...}, "results": [result, ...], "total": int,
                     "sources": {source_id: {"name", "status": "ok"|"error"|"skipped", "count", "seconds", "errors": [str]}}}
  result         -> make_result(...) dict: source_id, source, company, contact_name, contact_title, email, phone,
                     website, location, country, category, url, linkedin, details, keyword
  result_to_raw_lead(result) -> dict for lead_normalizer.MasterLeadRegistry.add_lead (see crm_sources.result_to_raw_lead)
"""
from typing import Any, Dict, List

MAX_KEYWORDS = 10
MAX_RESULTS_PER_SOURCE = 50

COUNTRIES: List[Dict[str, str]] = []


def make_result(source_id: str, **fields) -> Dict[str, str]:
    keys = ("source", "company", "contact_name", "contact_title", "email", "phone", "website", "location",
            "country", "category", "url", "linkedin", "details", "keyword")
    out = {"source_id": source_id}
    out.update({k: str(fields.get(k) or "") for k in keys})
    return out


def list_sources() -> List[Dict[str, Any]]:
    return []


def validate_request(data: Dict[str, Any]) -> Dict[str, Any]:
    raise ValueError("Global Directories is not built yet")


def search(data: Dict[str, Any]) -> Dict[str, Any]:
    validate_request(data)
    return {"query": {}, "results": [], "total": 0, "sources": {}}


def result_to_raw_lead(r: Dict[str, Any]) -> Dict[str, str]:
    return {
        "company_name": r.get("company", ""),
        "full_name": r.get("contact_name", ""),
        "email": r.get("email", ""),
        "mobile_number": r.get("phone", ""),
        "website": r.get("website", ""),
        "location": ", ".join(x for x in (r.get("location"), r.get("country")) if x),
        "description": r.get("details", ""),
        "source": f"Global Directory ({r.get('source', r.get('source_id', ''))})",
        "source_url": r.get("url", ""),
        "lead_type": "Global Directory",
    }

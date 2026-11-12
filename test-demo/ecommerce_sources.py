"""Scraping / Mining -> Ecommerce Platforms (online stores and sellers for a product category).

STUB - the contract below is already wired into app.py (/api/ecommerce/*), frontend/lib/api.js and
frontend/app/page.js. Implement the functions WITHOUT changing their names, arguments or return shapes.

Return shapes (same family as crm_sources.py / global_directories.py):

  list_sources() -> [{"id", "name", "kind": "store_platform"|"marketplace", "status": "available"|"needs_key"|"unavailable",
                      "note", "reason", "keys": [env var names]}]
  validate_request(data) -> clean dict, or raises ValueError("user-friendly message")
      data keys: keywords, audience, state, city, sources, engine
  search(data)   -> {"query": {...}, "results": [result, ...], "total": int,
                     "sources": {source_id: {"name", "status": "ok"|"error"|"skipped", "count", "seconds", "errors": [str]}},
                     "engine": engine id actually used, "hint": str}
  result         -> make_result(...) dict
  result_to_raw_lead(result) -> dict for lead_normalizer.MasterLeadRegistry.add_lead
"""
from typing import Any, Dict, List

MAX_KEYWORDS = 5
MAX_RESULTS_PER_SOURCE = 50


def make_result(source_id: str, **fields) -> Dict[str, str]:
    keys = ("source", "company", "email", "phone", "website", "location", "category", "platform", "url",
            "details", "keyword", "instagram", "facebook")
    out = {"source_id": source_id}
    out.update({k: str(fields.get(k) or "") for k in keys})
    return out


def list_sources() -> List[Dict[str, Any]]:
    return []


def validate_request(data: Dict[str, Any]) -> Dict[str, Any]:
    raise ValueError("Ecommerce Platforms is not built yet")


def search(data: Dict[str, Any]) -> Dict[str, Any]:
    validate_request(data)
    return {"query": {}, "results": [], "total": 0, "sources": {}, "engine": "", "hint": ""}


def result_to_raw_lead(r: Dict[str, Any]) -> Dict[str, str]:
    return {
        "company_name": r.get("company", ""),
        "email": r.get("email", ""),
        "mobile_number": r.get("phone", ""),
        "website": r.get("website", ""),
        "location": r.get("location", ""),
        "description": ". ".join(x for x in (r.get("platform") and f"Platform: {r['platform']}", r.get("category"),
                                             r.get("details")) if x),
        "source": f"Ecommerce ({r.get('source', r.get('source_id', ''))})",
        "source_url": r.get("url", ""),
        "lead_type": "Ecommerce Store",
    }

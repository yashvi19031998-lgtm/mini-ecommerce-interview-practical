"""Lead Care -> Lead Enrichment: find missing website / e-mail / phone for SAVED leads, then fill them safely.

Flow:
  1. candidates()  pick leads by what they miss (e-mail / phone / website / website check), source and limit
  2. enrich()      for up to 5 leads per request: Deep Search (website by name when missing -> crawl homepage +
                   contact pages -> JSON-LD -> Zaubacorp for registered companies) and the website check
                   (website_signals). Returns PROPOSALS only - nothing is written.
  3. save()        the owner's chosen proposals go through lead_cleanup.apply_changes: backup of the whole file,
                   fill EMPTY fields only, change log, undo from the history. Values sent back by the browser are
                   validated again here (field allowed, lead exists, field still empty, value normalised).

Platform / directory links (IndiaMART, LinkedIn, job boards...) are never used as the company's website.
"""
import ipaddress
import re
from urllib.parse import urlparse
from typing import Any, Dict, List, Optional

import deep_search
import lead_cleanup
import lead_normalizer as ln
import search_engine as se
import website_signals

MAX_PER_CALL = 5
LIMIT_CHOICES = (10, 25, 50, 100)
NEEDS = {"email": "No e-mail", "mobile_number": "No phone", "website": "No website", "website_signals": "No website check"}
FILLABLE = ("website", "email", "mobile_number", "website_signals")


def _rows(master_path: str) -> List[Dict[str, str]]:
    return lead_cleanup._rows(master_path)


def candidates(master_path: str, data: Dict[str, Any]) -> Dict[str, Any]:
    needs = data.get("needs", ["email", "mobile_number"])
    if not isinstance(needs, list) or not needs or any(n not in NEEDS for n in needs):
        raise ValueError("Choose what is missing")
    limit = data.get("limit", 25)
    if limit not in LIMIT_CHOICES:
        raise ValueError("Unknown limit")
    source = " ".join(str(data.get("source") or "").split())[:60].lower()
    only_with_site = bool(data.get("only_with_website"))
    rows, total = [], 0
    for r in _rows(master_path):
        missing = [n for n in needs if not (r.get(n) or "").strip()]
        if not missing:
            continue
        if n_ok := (r.get("website") or "").strip():
            if se.is_platform(n_ok):
                n_ok = ""
        if only_with_site and not n_ok:
            continue
        if source and source not in (r.get("source") or "").lower():
            continue
        if not ((r.get("company_name") or "").strip() or n_ok):
            continue                                            # nothing to search with
        total += 1
        if len(rows) < limit:
            rows.append({"lead_id": r.get("lead_id", ""), "company": (r.get("company_name") or "")[:120],
                         "website": r.get("website", ""), "email": r.get("email", ""), "phone": r.get("mobile_number", ""),
                         "location": (r.get("location") or "")[:80], "source": (r.get("source") or "")[:80], "missing": missing})
    return {"results": rows, "matching": total, "needs": needs}


def _place(location: str) -> str:
    first = re.split(r"[,|/]", location or "")[0]
    return re.sub(r"[^A-Za-z .'-]", "", first)[:60].strip()


def enrich(master_path: str, lead_ids: Any, steps: Any = None, engine: str = "auto") -> Dict[str, Any]:
    if not isinstance(lead_ids, list) or not lead_ids:
        raise ValueError("Select at least one lead")
    if len(lead_ids) > MAX_PER_CALL:
        raise ValueError(f"At most {MAX_PER_CALL} leads per request")
    steps = steps or ["deep", "check"]
    if not isinstance(steps, list) or any(s not in ("deep", "check") for s in steps):
        raise ValueError("Unknown step")
    by_id = {r.get("lead_id"): r for r in _rows(master_path)}
    leads = [by_id[i] for i in lead_ids if i in by_id]
    if not leads:
        raise ValueError("Those leads were not found")
    proposals: List[Dict[str, str]] = []
    report: List[Dict[str, Any]] = []
    deep_results: Dict[str, Dict[str, Any]] = {}
    if "deep" in steps:
        items = []
        for r in leads:
            site = (r.get("website") or "").strip()
            src = (r.get("source_url") or "").strip()
            items.append({"key": r["lead_id"], "website": "" if se.is_platform(site) else site,
                          "url": src if src and not se.is_platform(src) and not deep_search.is_government(src) else "",
                          "company": (r.get("company_name") or "")[:150], "kind": "listing"})
        place = _place(leads[0].get("location", ""))
        res = deep_search.deep_search(items, engine=engine, use_hunter=False, place=place)
        deep_results = {d["key"]: d for d in res["results"]}
    for r in leads:
        lid = r["lead_id"]
        d = deep_results.get(lid, {})
        found_site = (r.get("website") or "").strip() or d.get("website", "")
        props = []
        if d:
            if not (r.get("website") or "").strip() and d.get("website") and not se.is_platform(d["website"]):
                props.append(("website", d["website"], "Deep Search: website found"))
            emails = [e for e in d.get("emails", []) if ln.normalize_email(e)]
            if not (r.get("email") or "").strip() and emails:
                props.append(("email", ", ".join(emails[:2]), f"Deep Search: {d.get('pages_checked', 0)} page(s) of the website"))
            phones = [ln.normalize_phone(p) for p in d.get("phones", [])]
            phones = [p for p in phones if p]
            if not (r.get("mobile_number") or "").strip() and phones:
                props.append(("mobile_number", ", ".join(phones[:2]), "Deep Search: website"))
        if "check" in steps and found_site and not (r.get("website_signals") or "").strip():
            props.append(("website_signals", website_signals.check_website(found_site), f"Website check of {se.domain_of(found_site)}"))
        for field, value, why in props:
            if value:
                proposals.append({"lead_id": lid, "company": (r.get("company_name") or "")[:80], "field": field, "old": "",
                                  "new": value[:500], "from": why})
        report.append({"lead_id": lid, "company": (r.get("company_name") or "")[:80], "status": d.get("status", "checked"),
                       "steps": d.get("steps", []), "proposals": len(props)})
    return {"proposals": proposals, "leads": report, "engine": se.resolve_engine(engine)}


def _clean_value(field: str, value: str) -> str:
    v = str(value or "").strip()[:500]
    if field == "email":
        return ln.normalize_email(v)
    if field == "mobile_number":
        return ln.normalize_phone(v)
    if field == "website":
        url = ln.clean_url(v)
        if not url or se.is_platform(url) or se.domain_of(url) in ln.INVALID_DOMAINS:
            return ""
        host = (urlparse(url).hostname or "").lower()
        if not host or host == "localhost" or host.endswith((".local", ".internal", ".localhost")):
            return ""
        try:
            if not ipaddress.ip_address(host).is_global:
                return ""                                   # private / loopback IP literal
        except ValueError:
            pass                                            # a name: stored only, never fetched here
        return url
    if field == "website_signals":
        return re.sub(r"[\r\n\t]+", " ", v)[:300]
    return ""


def save(master_path: str, changes: Any) -> Dict[str, Any]:
    if not isinstance(changes, list) or not changes:
        raise ValueError("Select at least one value to save")
    if len(changes) > 2000:
        raise ValueError("Too many values at once")
    rows = {r.get("lead_id"): r for r in _rows(master_path)}
    clean, skipped = [], 0
    for c in changes:
        if not isinstance(c, dict):
            skipped += 1
            continue
        lid, field = str(c.get("lead_id") or ""), str(c.get("field") or "")
        lead = rows.get(lid)
        value = _clean_value(field, c.get("new", "")) if field in FILLABLE else ""
        if not lead or not value or (lead.get(field) or "").strip():
            skipped += 1                                         # unknown lead, bad value, or already filled
            continue
        clean.append({"lead_id": lid, "company": (lead.get("company_name") or "")[:80], "field": field, "old": "",
                      "new": value, "from": str(c.get("from") or "")[:120], "fix": "enrichment"})
    res = lead_cleanup.apply_changes(master_path, clean, ["enrichment"])
    return {**res, "skipped": skipped + (len(clean) - res.get("applied", 0))}

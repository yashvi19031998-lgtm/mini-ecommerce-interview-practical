"""Lead Care -> Data Cleanup: safe fixes for the saved leads.

Promise (owner's rule: never delete anything old):
  - no lead (row) is ever removed and no filled value is ever changed or blanked;
  - fixes only FILL EMPTY fields, from information already inside the same lead;
  - every apply first copies the whole leads file to backups/, and writes a change log;
  - Undo puts back exactly the logged fields, and only where the value is still the one the fix wrote.

Fixes (each can be switched on / off):
  website_from_email   empty website <- the lead's own business e-mail domain (not free mail, not a platform,
                       not a domain shared by several different leads)
  email_from_text      empty e-mail  <- an e-mail address written in the lead's description / summary
  phone_from_text      empty phone   <- an Indian phone number written in the lead's description / summary
Reports (nothing is changed):
  shared_contacts      the same e-mail / phone / domain on several different leads - usually a platform's contact
  format_issues        values the current rules would write differently (shown only)
"""
import datetime
import glob
import json
import os
import re
import shutil
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional

import bulk_contacts as bc
import lead_normalizer as ln
import search_engine as se

FIXES = {
    "website_from_email": {"title": "Website from the lead's business e-mail",
                           "field": "website", "why": "Only for e-mails on the company's own domain (not Gmail / Yahoo…, not a platform)"},
    "email_from_text": {"title": "E-mail written in the description",
                        "field": "email", "why": "The address is already inside the lead's own text"},
    "phone_from_text": {"title": "Phone written in the description",
                        "field": "mobile_number", "why": "A valid Indian number already inside the lead's own text"},
}
TEXT_FIELDS = ("description", "ai_summary", "ai_requirement")
EMAIL_FIND = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
SHARED_LIMIT = 3            # a domain / contact on this many different leads is treated as a platform's
MAX_EXAMPLES = 200
KEEP_BACKUPS = 20


def backups_dir(master_path: str) -> str:
    return os.path.join(os.path.dirname(os.path.abspath(master_path)), "backups")


def _rows(master_path: str) -> List[Dict[str, str]]:
    import csv
    if not os.path.exists(master_path):
        return []
    with open(master_path, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def _text(r: Dict[str, str]) -> str:
    return " ".join(r.get(k, "") or "" for k in TEXT_FIELDS)


def _business_domain(email: str) -> str:
    d = email.split(",")[0].strip().lower().split("@")[-1] if "@" in email else ""
    if not d or d in bc.FREE_PROVIDERS or d in bc.DISPOSABLE or d in ln.INVALID_DOMAINS:
        return ""
    if se.is_platform(f"https://{d}") or se._matches(d, se.JUNK_DOMAINS):
        return ""
    return d


def _domain_matches_lead(domain: str, r: Dict[str, str]) -> bool:
    """The domain's name must appear in the lead itself (company, text or link) - an e-mail of another company
    mentioned in a job post must not become this lead's website."""
    label = re.sub(r"[^a-z0-9]", "", domain.split(".")[0])
    hay = re.sub(r"[^a-z0-9]", "", " ".join(r.get(k, "") or "" for k in ("company_name", "source_url", "full_name") + TEXT_FIELDS).lower())
    return len(label) >= 3 and label in hay


def scan(master_path: str, limit: Optional[int] = MAX_EXAMPLES) -> Dict[str, Any]:
    """limit = how many changes per fix to return (None = all, used by apply)."""
    rows = _rows(master_path)
    # how many different leads use each domain / e-mail / phone (to spot platform contacts)
    dom_users, mail_users, phone_users = defaultdict(set), defaultdict(set), defaultdict(set)
    for i, r in enumerate(rows):
        for e in [x.strip().lower() for x in (r.get("email") or "").split(",") if "@" in x]:
            mail_users[e].add(i)
            dom_users[e.split("@")[1]].add(i)
        for p in [re.sub(r"\D", "", x)[-10:] for x in (r.get("mobile_number") or "").split(",") if len(re.sub(r"\D", "", x)) >= 10]:
            phone_users[p].add(i)
        w = ln.canonicalize_domain(r.get("website") or "")
        if w:
            dom_users[w].add(i)
    shared_domains = {d for d, users in dom_users.items() if len(users) >= SHARED_LIMIT}

    changes: Dict[str, List[Dict[str, str]]] = {k: [] for k in FIXES}
    for r in rows:
        lid, comp = r.get("lead_id", ""), (r.get("company_name") or "")[:80]
        base = {"lead_id": lid, "company": comp}
        if not (r.get("website") or "").strip():
            d = _business_domain(r.get("email") or "")
            if d and d not in shared_domains and _domain_matches_lead(d, r):
                changes["website_from_email"].append({**base, "field": "website", "old": "", "new": f"https://{d}",
                                                      "from": (r.get("email") or "").split(",")[0].strip()})
        text = _text(r)
        if not (r.get("email") or "").strip() and text:
            found = [ln.normalize_email(e) for e in EMAIL_FIND.findall(text)]
            found = [e for e in found if e and e.split("@")[0] not in bc.NO_REPLY and e.split("@")[1] not in shared_domains]
            if found:
                changes["email_from_text"].append({**base, "field": "email", "old": "", "new": found[0], "from": "description"})
        if not (r.get("mobile_number") or "").strip() and text:
            phones = []
            for cand in bc.PHONE_CANDIDATE.findall(text):
                c = bc.classify_phone(cand)
                if c["status"] == "valid" and c["type"] == "Mobile" and len(phone_users.get(c["e164"][-10:], ())) < SHARED_LIMIT:
                    phones.append(ln.normalize_phone(c["e164"]))
            phones = [p for p in dict.fromkeys(phones) if p]
            if phones:
                changes["phone_from_text"].append({**base, "field": "mobile_number", "old": "", "new": phones[0], "from": "description"})

    shared = []
    for kind, users in (("e-mail", mail_users), ("phone", phone_users), ("domain", dom_users)):
        for value, idxs in users.items():
            companies = {(rows[i].get("company_name") or "").strip().lower() for i in idxs}
            if kind == "domain" and (value in bc.FREE_PROVIDERS or value in ln.INVALID_DOMAINS):
                continue
            if len(idxs) >= 2 and len(companies) >= 2:
                shared.append({"kind": kind, "value": value if kind != "phone" else f"…{value[-4:]}", "leads": len(idxs),
                               "examples": [f"{rows[i].get('lead_id')} {rows[i].get('company_name', '')[:40]}" for i in sorted(idxs)[:4]]})
    shared.sort(key=lambda s: -s["leads"])

    fmt = []
    for r in rows:
        for field, fn in (("email", ln.normalize_email), ("mobile_number", ln.normalize_phone), ("website", ln.clean_url)):
            v = (r.get(field) or "").strip()
            if v and fn(v) != v:
                fmt.append({"lead_id": r.get("lead_id", ""), "company": (r.get("company_name") or "")[:60], "field": field,
                            "value": v[:120], "rules_would_write": fn(v)[:120] or "(nothing - not valid)"})

    missing = Counter()
    for r in rows:
        for f, label in (("email", "no e-mail"), ("mobile_number", "no phone"), ("website", "no website")):
            if not (r.get(f) or "").strip():
                missing[label] += 1
    return {
        "leads": len(rows), "missing": dict(missing),
        "fixes": [{"id": k, **FIXES[k], "count": len(v), "changes": v if limit is None else v[:limit]} for k, v in changes.items()],
        "shared_contacts": shared[:100], "format_issues": fmt[:100],
        "history": history(master_path),
    }


# ---------------------------------------------------------------------------
# Apply / undo / history
# ---------------------------------------------------------------------------

def _stamp() -> str:
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")


def _prune_backups(folder: str) -> None:
    files = sorted(glob.glob(os.path.join(folder, "all_leads_master_*.csv")))
    for f in files[:-KEEP_BACKUPS]:
        try:
            os.remove(f)
        except OSError:
            pass


def apply(master_path: str, fix_ids: Any) -> Dict[str, Any]:
    if not isinstance(fix_ids, list) or not fix_ids or any(f not in FIXES for f in fix_ids):
        raise ValueError("Choose at least one fix")
    plan = {f["id"]: f for f in scan(master_path, limit=None)["fixes"]}
    wanted: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for f in fix_ids:
        for c in plan[f]["changes"]:
            wanted[c["lead_id"]].append({**c, "fix": f})
    if not wanted:
        return {"applied": 0, "log_id": "", "backup": ""}
    folder = backups_dir(master_path)
    os.makedirs(folder, exist_ok=True)
    stamp = _stamp()
    backup = os.path.join(folder, f"all_leads_master_{stamp}.csv")
    shutil.copy2(master_path, backup)                       # whole file, before anything is written

    reg = ln.MasterLeadRegistry(master_path)
    done = []
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for lead in reg.leads:
        for c in wanted.get(lead.get("lead_id"), []):
            if (lead.get(c["field"]) or "").strip():
                continue                                    # filled meanwhile: never overwrite
            lead[c["field"]] = c["new"]
            done.append({**c, "updated_old": lead.get("last_updated_at", ""), "updated_new": now})
            lead["last_updated_at"] = now
    if not done:
        os.remove(backup)
        return {"applied": 0, "log_id": "", "backup": ""}
    if not reg.save_master_safely():
        raise IOError("Could not write the leads file - nothing was changed")
    log = {"id": stamp, "at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "backup": os.path.basename(backup),
           "fixes": fix_ids, "changes": done, "undone": False}
    with open(os.path.join(folder, f"cleanup_{stamp}.json"), "w", encoding="utf-8") as fh:
        json.dump(log, fh, ensure_ascii=False, indent=1)
    _prune_backups(folder)
    return {"applied": len(done), "log_id": stamp, "backup": os.path.basename(backup),
            "by_fix": dict(Counter(c["fix"] for c in done))}


def history(master_path: str) -> List[Dict[str, Any]]:
    out = []
    for f in sorted(glob.glob(os.path.join(backups_dir(master_path), "cleanup_*.json")), reverse=True)[:20]:
        try:
            with open(f, encoding="utf-8") as fh:
                log = json.load(fh)
            out.append({"id": log["id"], "at": log["at"], "changes": len(log["changes"]), "fixes": log["fixes"],
                        "undone": log.get("undone", False), "backup": log.get("backup", "")})
        except (OSError, ValueError, KeyError):
            continue
    return out


def undo(master_path: str, log_id: Any) -> Dict[str, Any]:
    if not isinstance(log_id, str) or not re.fullmatch(r"\d{8}-\d{6}-\d{6}", log_id):
        raise ValueError("Unknown cleanup")
    path = os.path.join(backups_dir(master_path), f"cleanup_{log_id}.json")
    if not os.path.exists(path):
        raise ValueError("Unknown cleanup")
    with open(path, encoding="utf-8") as fh:
        log = json.load(fh)
    if log.get("undone"):
        raise ValueError("This cleanup was already undone")
    by_lead = defaultdict(list)
    for c in log["changes"]:
        by_lead[c["lead_id"]].append(c)
    reg = ln.MasterLeadRegistry(master_path)
    reverted, kept = 0, 0
    for lead in reg.leads:
        for c in by_lead.get(lead.get("lead_id"), []):
            if lead.get(c["field"]) == c["new"]:
                lead[c["field"]] = c["old"]
                if "updated_old" in c and lead.get("last_updated_at") == c.get("updated_new"):
                    lead["last_updated_at"] = c["updated_old"]
                reverted += 1
            else:
                kept += 1                                   # changed again since: leave the newer value alone
    if reverted and not reg.save_master_safely():
        raise IOError("Could not write the leads file - nothing was changed")
    log["undone"] = True
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(log, fh, ensure_ascii=False, indent=1)
    return {"reverted": reverted, "kept_newer": kept}

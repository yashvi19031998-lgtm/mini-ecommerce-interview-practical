"""
FollowUp History - activity log and follow-up queue for leads (Phase 1).

Storage: one CSV, logs/followup_activity.csv (the leads master file is NOT changed).
Every contact with a lead is one row: email sent, WhatsApp, call, meeting, note, status change.
A planned follow-up is also a row: type "followup" with due_at and followup_status
(pending / done / cancelled). A lead has at most one pending follow-up: scheduling a new one
cancels the previous one, so the queue never shows stale duplicates.

Rows keep a snapshot of the lead's name and email, so history stays readable even if lead ids
are re-numbered later.
"""

import csv
import datetime
import hashlib
import os
import threading
import uuid
from typing import Any, Dict, List, Optional

from lead_normalizer import normalize_datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ACTIVITY_FILE = os.path.join(BASE_DIR, "logs", "followup_activity.csv")
SENT_LOG_FILE = os.path.join(BASE_DIR, "logs", "sent_emails.csv")

FIELDS = [
    "activity_id", "lead_id", "lead_name", "lead_email", "type", "summary", "details",
    "occurred_at", "created_at", "source", "due_at", "followup_status", "completed_at",
]

# Types a user can log by hand, and types the system writes itself
MANUAL_TYPES = {"call", "meeting", "note", "whatsapp", "email"}
# email_sent / status_change: written by the app. reply / bounce / opted_out: Gmail reply check
# (reply_checker.py). sequence_stopped: follow-up sequence ended by hand.
SYSTEM_TYPES = {"email_sent", "status_change", "reply", "bounce", "opted_out", "sequence_stopped"}
FOLLOWUP = "followup"
ALL_TYPES = MANUAL_TYPES | SYSTEM_TYPES | {FOLLOWUP}

MAX_SUMMARY = 300
MAX_DETAILS = 2000
MAX_DAYS_AHEAD = 366
UPCOMING_DAYS = 7

_lock = threading.RLock()
TS = "%Y-%m-%d %H:%M:%S"


class FollowupError(ValueError):
    """Invalid input; the message is safe to show to the user."""


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

def _now() -> datetime.datetime:
    return datetime.datetime.now().replace(microsecond=0)


def _parse(stamp: str) -> Optional[datetime.datetime]:
    norm = normalize_datetime(stamp)
    return datetime.datetime.strptime(norm, TS) if norm else None


def _read_all(path: str = None) -> List[Dict[str, str]]:
    path = path or ACTIVITY_FILE
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return [{k: (row.get(k) or "") for k in FIELDS} for row in csv.DictReader(f)]


def _write_all(rows: List[Dict[str, str]], path: str = None) -> None:
    path = path or ACTIVITY_FILE
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    os.replace(tmp, path)


def _append(row: Dict[str, str], path: str = None) -> None:
    path = path or ACTIVITY_FILE
    os.makedirs(os.path.dirname(path), exist_ok=True)
    is_new = not os.path.exists(path)
    with open(path, "a", encoding="utf-8-sig" if is_new else "utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        if is_new:
            writer.writeheader()
        writer.writerow({k: row.get(k, "") for k in FIELDS})


def _clean(text: Any, limit: int) -> str:
    return " ".join(str(text or "").split())[:limit] if limit <= MAX_SUMMARY else str(text or "").strip()[:limit]


# ---------------------------------------------------------------------------
# Writing activities
# ---------------------------------------------------------------------------

def add_activity(lead_id: str, activity_type: str, summary: str, details: str = "", occurred_at: str = "",
                 source: str = "manual", lead_name: str = "", lead_email: str = "",
                 allow_system_types: bool = False) -> Dict[str, str]:
    """Logs one contact/event for a lead. Raises FollowupError on bad input."""
    allowed = (MANUAL_TYPES | SYSTEM_TYPES) if allow_system_types else MANUAL_TYPES
    if activity_type not in allowed:
        raise FollowupError(f"Activity type must be one of: {', '.join(sorted(allowed))}")
    summary = _clean(summary, MAX_SUMMARY)
    if not summary:
        raise FollowupError("Summary is required")
    if len(str(details or "")) > MAX_DETAILS:
        raise FollowupError(f"Details must be {MAX_DETAILS} characters or less")
    if not (lead_id or lead_email):
        raise FollowupError("A lead is required")

    now = _now()
    when = now
    if occurred_at:
        when = _parse(occurred_at)
        if not when:
            raise FollowupError("Date/time of the activity is not valid")
        if when > now + datetime.timedelta(minutes=5):
            raise FollowupError("Activity date cannot be in the future")

    row = {
        "activity_id": f"ACT-{uuid.uuid4().hex[:12]}",
        "lead_id": str(lead_id or ""), "lead_name": _clean(lead_name, 200), "lead_email": _clean(lead_email, 200),
        "type": activity_type, "summary": summary, "details": str(details or "").strip()[:MAX_DETAILS],
        "occurred_at": when.strftime(TS), "created_at": now.strftime(TS), "source": source,
        "due_at": "", "followup_status": "", "completed_at": "",
    }
    with _lock:
        _append(row)
    return row


def add_event_once(activity_id: str, lead_id: str, activity_type: str, summary: str, details: str = "",
                   occurred_at: str = "", source: str = "", lead_name: str = "",
                   lead_email: str = "") -> Optional[Dict[str, str]]:
    """Adds a system event with a fixed id (e.g. from an email Message-ID); returns None if it already exists."""
    if activity_type not in SYSTEM_TYPES:
        raise FollowupError(f"Unknown system event type: {activity_type}")
    now = _now().strftime(TS)
    row = {
        "activity_id": activity_id, "lead_id": str(lead_id or ""), "lead_name": _clean(lead_name, 200),
        "lead_email": _clean(lead_email, 200), "type": activity_type, "summary": _clean(summary, MAX_SUMMARY),
        "details": str(details or "").strip()[:MAX_DETAILS], "occurred_at": normalize_datetime(occurred_at) or now,
        "created_at": now, "source": source, "due_at": "", "followup_status": "", "completed_at": "",
    }
    with _lock:
        if any(r["activity_id"] == activity_id for r in _read_all()):
            return None
        _append(row)
    return row


def safe_log(lead_id: str, activity_type: str, summary: str, **kwargs) -> Optional[Dict[str, str]]:
    """Logging from automatic flows (email send, status change) must never break that flow."""
    try:
        return add_activity(lead_id, activity_type, summary, allow_system_types=True, **kwargs)
    except Exception as e:  # noqa: BLE001 - deliberately swallow; the main action already succeeded
        print(f"[followup] could not log {activity_type} for {lead_id or kwargs.get('lead_email')}: {e}")
        return None


def _validate_due(due_at: str) -> datetime.datetime:
    due = _parse(due_at)
    if not due:
        raise FollowupError("Follow-up date is not valid")
    today = _now().replace(hour=0, minute=0, second=0)
    if due < today:
        raise FollowupError("Follow-up date cannot be in the past")
    if due > today + datetime.timedelta(days=MAX_DAYS_AHEAD):
        raise FollowupError("Follow-up date must be within one year")
    if len(due_at.strip()) <= 10:  # date only -> 10:00 on that day
        due = due.replace(hour=10, minute=0)
    return due


def schedule_followup(lead_id: str, due_at: str, note: str = "", lead_name: str = "",
                      lead_email: str = "") -> Dict[str, str]:
    """Plans the next follow-up for a lead; any earlier pending follow-up for that lead is cancelled."""
    if not lead_id:
        raise FollowupError("A lead is required")
    due = _validate_due(due_at)
    note = _clean(note, MAX_SUMMARY) or "Follow up"
    now = _now().strftime(TS)
    with _lock:
        rows = _read_all()
        for r in rows:
            if r["type"] == FOLLOWUP and r["lead_id"] == str(lead_id) and r["followup_status"] == "pending":
                r["followup_status"], r["completed_at"] = "cancelled", now
        row = {
            "activity_id": f"FUP-{uuid.uuid4().hex[:12]}", "lead_id": str(lead_id),
            "lead_name": _clean(lead_name, 200), "lead_email": _clean(lead_email, 200),
            "type": FOLLOWUP, "summary": note, "details": "", "occurred_at": now, "created_at": now,
            "source": "manual", "due_at": due.strftime(TS), "followup_status": "pending", "completed_at": "",
        }
        rows.append(row)
        _write_all(rows)
    return row


def update_followup(activity_id: str, action: str, due_at: str = "") -> Dict[str, str]:
    """action: done | cancel | reschedule (needs due_at)."""
    if action not in ("done", "cancel", "reschedule"):
        raise FollowupError("Action must be done, cancel or reschedule")
    with _lock:
        rows = _read_all()
        row = next((r for r in rows if r["activity_id"] == activity_id and r["type"] == FOLLOWUP), None)
        if not row:
            raise LookupError("Follow-up not found")
        if row["followup_status"] != "pending":
            raise FollowupError(f"This follow-up is already {row['followup_status']}")
        now = _now().strftime(TS)
        if action == "reschedule":
            row["due_at"] = _validate_due(due_at).strftime(TS)
        else:
            row["followup_status"] = "done" if action == "done" else "cancelled"
            row["completed_at"] = now
        _write_all(rows)
    return row


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------

def bucket_of(row: Dict[str, str], now: datetime.datetime = None) -> str:
    """overdue / today / upcoming (next 7 days) / later - for pending follow-ups."""
    now = now or _now()
    due = _parse(row.get("due_at", ""))
    if not due:
        return "later"
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if due < today:
        return "overdue"
    if due < today + datetime.timedelta(days=1):
        return "today"
    if due < today + datetime.timedelta(days=UPCOMING_DAYS + 1):
        return "upcoming"
    return "later"


def queue(bucket: str = "all", now: datetime.datetime = None) -> List[Dict[str, str]]:
    if bucket not in ("all", "overdue", "today", "upcoming", "later"):
        raise FollowupError("Unknown bucket")
    now = now or _now()
    items = []
    for r in _read_all():
        if r["type"] != FOLLOWUP or r["followup_status"] != "pending":
            continue
        b = bucket_of(r, now)
        if bucket in ("all", b):
            items.append({**r, "bucket": b})
    return sorted(items, key=lambda r: r["due_at"])


def last_contact_by_lead() -> Dict[str, Dict[str, str]]:
    """Most recent non-followup activity per lead id (for 'last contacted' in the queue)."""
    latest: Dict[str, Dict[str, str]] = {}
    for r in _read_all():
        if r["type"] == FOLLOWUP or not r["lead_id"]:
            continue
        if r["occurred_at"] > latest.get(r["lead_id"], {}).get("occurred_at", ""):
            latest[r["lead_id"]] = r
    return latest


def history(lead_id: str = "", types: List[str] = None, q: str = "", limit: int = 100,
            offset: int = 0) -> Dict[str, Any]:
    """Newest-first activity feed with optional filters. Returns {"items", "total"}."""
    limit = max(1, min(int(limit or 100), 500))
    offset = max(0, int(offset or 0))
    types = [t for t in (types or []) if t]
    unknown = [t for t in types if t not in ALL_TYPES]
    if unknown:
        raise FollowupError(f"Unknown activity type: {', '.join(unknown)}")
    q = (q or "").strip().lower()
    rows = []
    for r in _read_all():
        if lead_id and r["lead_id"] != str(lead_id):
            continue
        if types and r["type"] not in types:
            continue
        if q and q not in f"{r['lead_name']} {r['lead_email']} {r['summary']} {r['details']}".lower():
            continue
        rows.append(r)
    rows.sort(key=lambda r: (r["occurred_at"], r["created_at"]), reverse=True)
    return {"items": rows[offset:offset + limit], "total": len(rows)}


def summary(now: datetime.datetime = None) -> Dict[str, int]:
    now = now or _now()
    counts = {"overdue": 0, "today": 0, "upcoming": 0, "later": 0}
    week_ago = (now - datetime.timedelta(days=7)).strftime(TS)
    contacts_week, total_activities = 0, 0
    for r in _read_all():
        if r["type"] == FOLLOWUP:
            if r["followup_status"] == "pending":
                counts[bucket_of(r, now)] += 1
            continue
        total_activities += 1
        if r["occurred_at"] >= week_ago:
            contacts_week += 1
    return {**counts, "pending": sum(counts.values()), "activities_7d": contacts_week,
            "activities_total": total_activities}


# ---------------------------------------------------------------------------
# Import emails sent before this module existed
# ---------------------------------------------------------------------------

def import_sent_emails(leads_by_email: Dict[str, Dict[str, str]], sent_log: str = None) -> Dict[str, int]:
    """Copies logs/sent_emails.csv into the activity log once (safe to run again: no duplicates).
    leads_by_email: lowercase email -> {"id", "name"} used to link each email to its lead."""
    sent_log = sent_log or SENT_LOG_FILE
    stats = {"imported": 0, "already_imported": 0, "matched_to_lead": 0, "unmatched": 0}
    if not os.path.exists(sent_log):
        return stats
    with _lock:
        rows = _read_all()
        existing = {r["activity_id"] for r in rows}
        # Emails sent from the app are already in the log (and also in sent_emails.csv): skip those
        logged = {(r["lead_email"].lower(), r["occurred_at"][:16]) for r in rows if r["type"] == "email_sent"}
        with open(sent_log, "r", encoding="utf-8-sig", errors="ignore", newline="") as f:
            for row in csv.DictReader(f):
                email = (row.get("email") or "").strip().lower()
                sent_at = normalize_datetime(row.get("sent_at"))
                if not email or not sent_at:
                    continue
                act_id = "IMP-" + hashlib.sha1(f"{email}|{sent_at}".encode()).hexdigest()[:12]
                if act_id in existing or (email, sent_at[:16]) in logged:
                    stats["already_imported"] += 1
                    continue
                lead = leads_by_email.get(email) or {}
                stats["matched_to_lead" if lead else "unmatched"] += 1
                _append({
                    "activity_id": act_id, "lead_id": lead.get("id", ""), "lead_name": lead.get("name", ""),
                    "lead_email": email, "type": "email_sent",
                    "summary": f"Email sent: {(row.get('subject') or '(no subject)').strip()[:200]}",
                    "details": "", "occurred_at": sent_at, "created_at": _now().strftime(TS),
                    "source": "import:sent_emails.csv",
                })
                existing.add(act_id)
                stats["imported"] += 1
    return stats


# ---------------------------------------------------------------------------
# Reply-rate report
# ---------------------------------------------------------------------------

def report(lead_sources: Dict[str, str] = None) -> Dict[str, Any]:
    """Outreach results per lead: contacted, replied, bounced, opted out - overall and per lead source.
    lead_sources: lead id -> source family (e.g. 'Reddit'); leads not in it are grouped as 'Unknown'."""
    lead_sources = lead_sources or {}
    per_lead: Dict[str, Dict[str, Any]] = {}
    for r in _read_all():
        key = r["lead_id"] or f"email:{r['lead_email'].lower()}"
        if not r["lead_id"] and not r["lead_email"]:
            continue
        info = per_lead.setdefault(key, {"contacted": False, "replied": False, "bounced": False,
                                         "opted_out": False, "sequence_emails": 0, "lead_id": r["lead_id"]})
        if r["type"] == "email_sent":
            info["contacted"] = True
            if r["source"].startswith("followup sequence"):
                info["sequence_emails"] += 1
        elif r["type"] == "reply":
            info["replied"] = True
        elif r["type"] == "bounce":
            info["bounced"] = True
        elif r["type"] == "opted_out":
            info["opted_out"] = info["replied"] = True

    def totals(items):
        contacted = [i for i in items if i["contacted"]]
        replied = sum(1 for i in contacted if i["replied"])
        return {
            "contacted": len(contacted), "replied": replied,
            "reply_rate_pct": round(100 * replied / len(contacted), 1) if contacted else 0.0,
            "bounced": sum(1 for i in contacted if i["bounced"]),
            "opted_out": sum(1 for i in contacted if i["opted_out"]),
            "followups_sent": sum(i["sequence_emails"] for i in contacted),
            "replied_after_followup": sum(1 for i in contacted if i["replied"] and i["sequence_emails"]),
        }

    groups: Dict[str, List[Dict[str, Any]]] = {}
    for info in per_lead.values():
        groups.setdefault(lead_sources.get(info["lead_id"], "Unknown"), []).append(info)
    by_source = [{"source": name, **totals(items)} for name, items in groups.items()]
    by_source = [row for row in by_source if row["contacted"]]
    by_source.sort(key=lambda r: (r["replied"], r["contacted"]), reverse=True)
    return {"overall": totals(list(per_lead.values())), "by_source": by_source}

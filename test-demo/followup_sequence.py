"""
FollowUp Phase 2 - automatic follow-up email sequence.

After the first outreach email to a lead, follow-ups are planned on day 3, 7 and 14
(FOLLOWUP_SEQUENCE_DAYS, max 3 steps). A step is "due" when its day has come.

Safety rules
- FOLLOWUP_AUTO_SEND is OFF by default: due steps are only listed in the dashboard
  ("Ready to send") and go out when a person clicks Send. With it ON, run_all_scrapers.py
  sends up to FOLLOWUP_MAX_PER_RUN per run.
- A sequence stops for good when the lead replied, bounced, asked to stop, or was stopped by
  hand, or when the lead's status is REPLIED / MEETING / WON / LOST / DISQUALIFIED.
- Only first emails from the last FOLLOWUP_MAX_AGE_DAYS (30) get follow-ups, and a step more than
  7 days late is skipped (so old emails never trigger a burst of late follow-ups).
- At least 2 days between any two emails to the same lead.
- Every follow-up carries an opt-out line ("reply STOP").
"""

import datetime
import json
import os
import string
from typing import Any, Callable, Dict, List, Optional

import env_loader  # noqa: F401  (loads .env for the settings below)
import followup_store as store

TS = "%Y-%m-%d %H:%M:%S"
SEQUENCE_SOURCE = "followup sequence #"   # activity.source prefix for sequence emails
STOP_STATUSES = {"REPLIED", "MEETING", "WON", "LOST", "DISQUALIFIED"}
STOP_EVENT_TYPES = {"reply", "bounce", "opted_out", "sequence_stopped"}
MAX_STEPS = 3
MAX_LATE_DAYS = 7
MIN_GAP_DAYS = 2

OPT_OUT_LINE = "If you'd rather not hear from us, just reply STOP and we won't email you again."

DEFAULT_TEMPLATES = [
    {
        "subject": "Re: {original_subject}",
        "body": ("Hi {name},\n\n"
                 "Just following up on my email from {first_date} - I'd love to know if {company} needs any help "
                 "with web, mobile or custom software work right now.\n\n"
                 "Would a short 10-minute call this week be useful?"),
    },
    {
        "subject": "Re: {original_subject}",
        "body": ("Hi {name},\n\n"
                 "Checking in once more. If you have a project on hold or need extra developers for a while, "
                 "we can usually start within a week.\n\n"
                 "Happy to share a few relevant examples of our work - just reply to this email."),
    },
    {
        "subject": "Re: {original_subject}",
        "body": ("Hi {name},\n\n"
                 "I don't want to fill your inbox, so this is my last note. If the timing isn't right, no problem "
                 "at all - feel free to reach out whenever you need a development partner.\n\n"
                 "Wishing {company} all the best."),
    },
]


# ---------------------------------------------------------------------------
# Editable templates (FollowUp History > Sequences > Edit templates)
# ---------------------------------------------------------------------------

TEMPLATES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "followup_templates.json")
PLACEHOLDERS = ("name", "company", "original_subject", "first_date")
MAX_SUBJECT = 200
MAX_BODY = 3000


class TemplateError(ValueError):
    """Invalid template; message is safe to show."""


def _check_placeholders(text: str, where: str) -> None:
    try:
        fields = [f for _, f, _, _ in string.Formatter().parse(text) if f is not None]
    except ValueError:
        raise TemplateError(f"{where}: unmatched {{ or }} - use {{name}}-style placeholders only")
    for f in fields:
        if f not in PLACEHOLDERS:
            raise TemplateError(f"{where}: unknown placeholder {{{f}}}. Allowed: "
                                + ", ".join("{" + p + "}" for p in PLACEHOLDERS))


def validate_templates(templates: Any) -> List[Dict[str, str]]:
    if not isinstance(templates, list) or len(templates) != len(DEFAULT_TEMPLATES):
        raise TemplateError(f"Exactly {len(DEFAULT_TEMPLATES)} templates are required")
    clean = []
    for i, t in enumerate(templates, start=1):
        label = f"Follow-up {i}" if i < len(DEFAULT_TEMPLATES) else "Final follow-up"
        if not isinstance(t, dict):
            raise TemplateError(f"{label}: invalid format")
        subject = str(t.get("subject") or "").strip()
        body = str(t.get("body") or "").strip()
        if not subject or not body:
            raise TemplateError(f"{label}: subject and message are required")
        if len(subject) > MAX_SUBJECT:
            raise TemplateError(f"{label}: subject must be {MAX_SUBJECT} characters or less")
        if len(body) > MAX_BODY:
            raise TemplateError(f"{label}: message must be {MAX_BODY} characters or less")
        _check_placeholders(subject, f"{label} subject")
        _check_placeholders(body, f"{label} message")
        clean.append({"subject": subject, "body": body})
    return clean


def load_templates() -> List[Dict[str, str]]:
    """Saved templates, or the defaults if none are saved (or the file is broken)."""
    try:
        with open(TEMPLATES_FILE, "r", encoding="utf-8") as f:
            return validate_templates(json.load(f))
    except (OSError, ValueError):
        return [dict(t) for t in DEFAULT_TEMPLATES]


def save_templates(templates: Any) -> List[Dict[str, str]]:
    clean = validate_templates(templates)
    tmp = TEMPLATES_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(clean, f, indent=2, ensure_ascii=False)
    os.replace(tmp, TEMPLATES_FILE)
    return clean


def reset_templates() -> List[Dict[str, str]]:
    if os.path.exists(TEMPLATES_FILE):
        os.remove(TEMPLATES_FILE)
    return [dict(t) for t in DEFAULT_TEMPLATES]


def templates_customized() -> bool:
    return os.path.exists(TEMPLATES_FILE)


def sequence_days() -> List[int]:
    raw = os.getenv("FOLLOWUP_SEQUENCE_DAYS", "3,7,14")
    try:
        days = sorted({int(d) for d in raw.split(",") if d.strip()})
    except ValueError:
        days = [3, 7, 14]
    return [d for d in days if 1 <= d <= 60][:MAX_STEPS] or [3, 7, 14]


def config() -> Dict[str, Any]:
    return {
        "days": sequence_days(),
        "auto_send": os.getenv("FOLLOWUP_AUTO_SEND", "false").lower() in ("1", "true", "yes"),
        "max_per_run": int(os.getenv("FOLLOWUP_MAX_PER_RUN", "10") or 10),
        "max_age_days": int(os.getenv("FOLLOWUP_MAX_AGE_DAYS", "30") or 30),
        "max_late_days": MAX_LATE_DAYS,
    }


def _parse(stamp: str) -> Optional[datetime.datetime]:
    try:
        return datetime.datetime.strptime(stamp[:19], TS)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Planning
# ---------------------------------------------------------------------------

def plan(leads: Dict[str, Dict[str, str]], now: datetime.datetime = None) -> Dict[str, List[Dict[str, Any]]]:
    """Works out which follow-up step (if any) is due for every lead.

    leads: lead id -> {"name", "email", "status"} (current data from the leads file)
    Returns {"due": [...], "stopped": [...], "waiting": [...]} - each item describes one lead.
    """
    now = now or datetime.datetime.now()
    cfg = config()
    days = cfg["days"]
    by_lead: Dict[str, List[Dict[str, str]]] = {}
    for row in store._read_all():
        if row["lead_id"]:
            by_lead.setdefault(row["lead_id"], []).append(row)

    due, stopped, waiting = [], [], []
    for lead_id, rows in by_lead.items():
        emails = sorted((r for r in rows if r["type"] == "email_sent"), key=lambda r: r["occurred_at"])
        firsts = [r for r in emails if not r["source"].startswith(SEQUENCE_SOURCE)]
        if not firsts:
            continue
        first = firsts[0]
        first_at = _parse(first["occurred_at"])
        if not first_at:
            continue
        lead = leads.get(lead_id)
        base = {"lead_id": lead_id, "lead_name": (lead or {}).get("name") or first["lead_name"],
                "email": (lead or {}).get("email") or first["lead_email"],
                "first_sent_at": first["occurred_at"], "original_subject": first["summary"].replace("Email sent: ", "", 1)}

        stop_event = next((r for r in rows if r["type"] in STOP_EVENT_TYPES and r["occurred_at"] >= first["occurred_at"]), None)
        status = str((lead or {}).get("status") or "").upper()
        reason = ""
        if not lead:
            reason = "lead no longer in the database"
        elif stop_event:
            reason = {"reply": "replied", "bounce": "email bounced", "opted_out": "asked to stop",
                      "sequence_stopped": "stopped by hand"}[stop_event["type"]]
        elif status in STOP_STATUSES:
            reason = f"status is {status}"
        elif not base["email"]:
            reason = "no email address"
        if reason:
            stopped.append({**base, "reason": reason})
            continue

        sent_steps = sum(1 for r in emails if r["source"].startswith(SEQUENCE_SOURCE))
        if sent_steps >= len(days):
            continue  # sequence finished
        if (now - first_at).days > cfg["max_age_days"]:
            continue  # too old to start following up now

        # Next step; steps that are too late are skipped (never sent in a burst)
        step = sent_steps + 1
        while step <= len(days):
            due_at = first_at + datetime.timedelta(days=days[step - 1])
            if (now - due_at).days <= MAX_LATE_DAYS:
                break
            step += 1
        if step > len(days):
            continue

        last_email_at = _parse(emails[-1]["occurred_at"]) or first_at
        earliest = max(due_at, last_email_at + datetime.timedelta(days=MIN_GAP_DAYS))
        item = {**base, "step": step, "total_steps": len(days), "due_at": earliest.strftime(TS),
                "last_email_at": emails[-1]["occurred_at"], "followups_sent": sent_steps}
        (due if earliest <= now else waiting).append(item)

    due.sort(key=lambda i: i["due_at"])
    waiting.sort(key=lambda i: i["due_at"])
    return {"due": due, "stopped": stopped, "waiting": waiting}


POST_TITLE_MARKERS = (":", "|", "[", "(", " - ", "hiring", "looking for", "show hn", "ask hn", "needed", "wanted")


def company_for_email(name: str) -> str:
    """Many scraped 'company names' are really post titles ('[Hiring] React dev needed...').
    Use the name only when it looks like a company; otherwise say 'your team'."""
    n = (name or "").strip()
    if not n or len(n) > 40 or any(m in n.lower() for m in POST_TITLE_MARKERS):
        return "your team"
    return n


def _template_for(item: Dict[str, Any], templates: List[Dict[str, str]]) -> Dict[str, str]:
    """The last scheduled step always gets the closing template; otherwise the wording follows how many
    follow-ups were actually sent (late steps may have been skipped)."""
    if item["step"] >= item.get("total_steps", len(templates)):
        return templates[-1]
    return templates[min(item.get("followups_sent", item["step"] - 1), len(templates) - 2)]


def render(item: Dict[str, Any], signature: str = "", templates: List[Dict[str, str]] = None) -> Dict[str, str]:
    """Fills the step's template. {name} falls back to 'there' when no contact name is known."""
    templates = templates or load_templates()
    tpl = _template_for(item, templates)
    first = _parse(item["first_sent_at"])
    values = {
        "name": "there", "company": company_for_email(item.get("lead_name", "")),
        "original_subject": item.get("original_subject") or "our conversation",
        "first_date": first.strftime("%d %b") if first else "last week",
    }
    subject = tpl["subject"].format(**values)
    body = tpl["body"].format(**values)
    if signature:
        body += f"\n\n---\n{signature.strip()}"
    body += f"\n\n{OPT_OUT_LINE}"
    return {"subject": subject[:200], "body": body}


# ---------------------------------------------------------------------------
# Sending
# ---------------------------------------------------------------------------

def send(items: List[Dict[str, Any]], send_fn: Callable[[str, str, str], Dict[str, Any]],
         signature: str = "", limit: int = None) -> Dict[str, Any]:
    """Sends the given due items with send_fn(to, subject, body) and logs each sent email.
    Returns {"sent": n, "failed": n, "results": [...]}."""
    results, sent, failed = [], 0, 0
    for item in items[: limit or len(items)]:
        msg = render(item, signature)
        try:
            res = send_fn(item["email"], msg["subject"], msg["body"])
        except Exception as e:  # noqa: BLE001 - one failure must not stop the batch
            res = {"success": False, "error": str(e)}
        if res.get("success"):
            sent += 1
            store.safe_log(item["lead_id"], "email_sent", f"Email sent: {msg['subject']}", details=msg["body"],
                           source=f"{SEQUENCE_SOURCE}{item['step']}", lead_name=item.get("lead_name", ""),
                           lead_email=item["email"])
        else:
            failed += 1
        results.append({"lead_id": item["lead_id"], "email": item["email"], "step": item["step"],
                        "success": bool(res.get("success")), "error": res.get("error", "")})
    return {"sent": sent, "failed": failed, "results": results}


def stop(lead_id: str, reason: str, lead_name: str = "", lead_email: str = "") -> Dict[str, str]:
    reason = (reason or "").strip() or "Stopped by hand"
    return store.add_activity(lead_id, "sequence_stopped", f"Follow-up sequence stopped: {reason}"[:300],
                              source="manual", lead_name=lead_name, lead_email=lead_email,
                              allow_system_types=True)

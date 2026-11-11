"""
FollowUp Phase 2 - read the Gmail inbox (IMAP, read-only) and record replies, bounces and opt-outs.

Setup: Gmail -> Google Account -> Security -> 2-Step Verification -> App passwords.
The same App Password used for SMTP works for IMAP. Settings (.env / GitHub secrets):
    IMAP_HOST=imap.gmail.com (default)    IMAP_USER / IMAP_PASSWORD (default: SMTP_USER / SMTP_PASS)

Only messages FROM an address we emailed are considered. For each one we store the subject and the
first 500 characters of the text - never the full message.

    python reply_checker.py      # check now and print what was found
"""

import datetime
import email
import email.policy
import email.utils
import hashlib
import imaplib
import json
import os
import re
from typing import Any, Dict, List, Optional, Set

import env_loader  # noqa: F401
import followup_store as store

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(BASE_DIR, "logs", "imap_state.json")
LOOKBACK_DAYS = 30
SNIPPET_CHARS = 500
MAX_MESSAGES_PER_RUN = 300

BOUNCE_SENDERS = ("mailer-daemon@", "postmaster@")
BOUNCE_SUBJECTS = ("delivery status notification", "undeliverable", "mail delivery failed",
                   "delivery failure", "returned mail", "failure notice")
OPT_OUT_PATTERNS = [r"^\s*stop\b", r"\bunsubscribe\b", r"\bremove me\b", r"\bnot interested\b",
                    r"\bdo not (contact|email)\b", r"\bdon'?t (contact|email)\b", r"\bstop (emailing|sending)\b"]
EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)*\.[a-zA-Z]{2,}")


def imap_settings() -> Dict[str, str]:
    return {
        "host": os.getenv("IMAP_HOST", "imap.gmail.com"),
        "user": os.getenv("IMAP_USER") or os.getenv("SMTP_USER", ""),
        "password": os.getenv("IMAP_PASSWORD") or os.getenv("SMTP_PASS", ""),
    }


def is_configured() -> bool:
    s = imap_settings()
    return bool(s["user"] and s["password"])


# ---------------------------------------------------------------------------
# Message parsing (pure functions - unit tested)
# ---------------------------------------------------------------------------

def _plain_text(msg: email.message.EmailMessage) -> str:
    part = msg.get_body(preferencelist=("plain", "html")) if msg.is_multipart() or msg.get_content_type() else None
    try:
        text = part.get_content() if part is not None else msg.get_content()
    except (KeyError, LookupError, AttributeError):
        payload = msg.get_payload(decode=True) or b""
        text = payload.decode("utf-8", errors="ignore") if isinstance(payload, bytes) else str(payload)
    if part is not None and part.get_content_type() == "text/html":
        text = re.sub(r"<[^>]+>", " ", text)
    return text


def _new_text_only(text: str) -> str:
    """Drops the quoted original ("On ... wrote:", "> ..." lines) so opt-out words in OUR text don't count."""
    lines = []
    for line in text.splitlines():
        if re.match(r"^\s*On .+wrote:\s*$", line) or line.strip().startswith("-----Original Message"):
            break
        if line.lstrip().startswith(">"):
            continue
        lines.append(line)
    return re.sub(r"\s+", " ", "\n".join(lines)).strip()


def classify(raw: bytes, contacted: Set[str]) -> Optional[Dict[str, Any]]:
    """Returns {"type": reply|opted_out|bounce, "email", "subject", "snippet", "received_at", "message_id"}
    for messages that matter, else None."""
    msg = email.message_from_bytes(raw, policy=email.policy.default)
    sender = email.utils.parseaddr(str(msg.get("From", "")))[1].lower()
    subject = str(msg.get("Subject", "")).strip()
    message_id = str(msg.get("Message-ID", "")).strip()
    try:
        received = email.utils.parsedate_to_datetime(str(msg.get("Date"))).astimezone().replace(tzinfo=None)
        received_at = received.strftime("%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        received_at = ""
    text = _plain_text(msg)

    is_bounce = sender.startswith(BOUNCE_SENDERS) or any(s in subject.lower() for s in BOUNCE_SUBJECTS)
    if is_bounce:
        failed = str(msg.get("X-Failed-Recipients", "")).lower()
        candidates = [e.lower() for e in EMAIL_RE.findall(f"{failed} {text}")]
        target = next((e for e in candidates if e in contacted), "")
        if not target:
            return None
        return {"type": "bounce", "email": target, "subject": subject, "snippet": "Delivery failed",
                "received_at": received_at, "message_id": message_id}

    if sender not in contacted:
        return None
    new_text = _new_text_only(text)
    opted_out = any(re.search(p, new_text, re.I | re.M) for p in OPT_OUT_PATTERNS) or \
        bool(re.match(r"^\s*(stop|unsubscribe)\b", subject, re.I))
    return {"type": "opted_out" if opted_out else "reply", "email": sender, "subject": subject,
            "snippet": new_text[:SNIPPET_CHARS], "received_at": received_at, "message_id": message_id}


# ---------------------------------------------------------------------------
# Inbox check
# ---------------------------------------------------------------------------

def _load_state() -> Dict[str, Any]:
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _save_state(state: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f)


def fetch_events(contacted: Set[str], imap_factory=imaplib.IMAP4_SSL) -> List[Dict[str, Any]]:
    """Reads new inbox messages (read-only) and returns classified events. Raises RuntimeError on IMAP errors."""
    s = imap_settings()
    if not (s["user"] and s["password"]):
        raise RuntimeError("Gmail reply check is not set up: add IMAP_USER/IMAP_PASSWORD (or SMTP_USER/SMTP_PASS)")
    state = _load_state()
    last_uid = int(state.get("last_uid", 0) or 0)
    since = (datetime.date.today() - datetime.timedelta(days=LOOKBACK_DAYS)).strftime("%d-%b-%Y")
    events = []
    try:
        conn = imap_factory(s["host"])
        conn.login(s["user"], s["password"])
        conn.select("INBOX", readonly=True)
        typ, data = conn.uid("search", None, f"(SINCE {since})")
        if typ != "OK":
            raise RuntimeError("inbox search failed")
        uids = [int(u) for u in (data[0] or b"").split() if int(u) > last_uid][-MAX_MESSAGES_PER_RUN:]
        for uid in uids:
            typ, msg_data = conn.uid("fetch", str(uid), "(BODY.PEEK[])")
            if typ != "OK" or not msg_data or not isinstance(msg_data[0], tuple):
                continue
            event = classify(msg_data[0][1], contacted)
            if event:
                events.append({**event, "uid": uid})
        if uids:
            state["last_uid"] = max(uids)
        state["last_checked_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        _save_state(state)
        conn.logout()
    except imaplib.IMAP4.error as e:
        raise RuntimeError(f"Gmail login/IMAP error: {e}") from e
    except OSError as e:
        raise RuntimeError(f"Could not connect to {s['host']}: {e}") from e
    return events


SUMMARIES = {"reply": "Reply received", "opted_out": "Asked to stop emails", "bounce": "Email bounced"}


def record_events(events: List[Dict[str, Any]], email_to_lead: Dict[str, Dict[str, str]]) -> Dict[str, Any]:
    """Logs events once (keyed by Message-ID) and returns lead updates for the caller to apply:
    {"logged": n, "skipped": n, "updates": [{"lead_id", "status"?: "REPLIED", "email_status"?: "INVALID"}]}"""
    logged, skipped, updates = 0, 0, []
    for ev in events:
        lead = email_to_lead.get(ev["email"], {})
        key = ev.get("message_id") or f"{ev['email']}|{ev.get('received_at')}|{ev.get('subject')}"
        act_id = "IMAP-" + hashlib.sha1(key.encode()).hexdigest()[:14]
        summary = f"{SUMMARIES[ev['type']]}: {ev['subject'] or '(no subject)'}"
        row = store.add_event_once(act_id, lead.get("id", ""), ev["type"], summary, details=ev.get("snippet", ""),
                                   occurred_at=ev.get("received_at", ""), source="gmail",
                                   lead_name=lead.get("name", ""), lead_email=ev["email"])
        if not row:
            skipped += 1
            continue
        logged += 1
        if lead.get("id"):
            if ev["type"] == "bounce":
                updates.append({"lead_id": lead["id"], "email_status": "INVALID"})
            else:
                updates.append({"lead_id": lead["id"], "status": "REPLIED"})
    return {"logged": logged, "skipped": skipped, "updates": updates}


def contacted_emails() -> Set[str]:
    return {r["lead_email"].lower() for r in store._read_all() if r["type"] == "email_sent" and r["lead_email"]}


def last_checked_at() -> str:
    return _load_state().get("last_checked_at", "")


if __name__ == "__main__":
    found = fetch_events(contacted_emails())
    for e in found:
        print(f"{e['type']:<10} {e['email']:<35} {e['subject'][:60]}")
    print(f"{len(found)} relevant messages")

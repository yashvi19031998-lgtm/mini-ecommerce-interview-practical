"""
FollowUp Phase 2 - read the Gmail inbox (IMAP, read-only) and record replies, bounces and opt-outs.

Setup: Gmail -> Google Account -> Security -> 2-Step Verification -> App passwords.
The same App Password used for SMTP works for IMAP. Settings (.env / GitHub secrets):
    IMAP_HOST=imap.gmail.com (default). The sending account (SMTP_USER / SMTP_PASS) is always read,
    because bounces arrive there; a different IMAP_USER / IMAP_PASSWORD inbox is read as well.

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


def imap_accounts() -> List[Dict[str, str]]:
    """Inboxes to read. The SENDING account comes first: "Address not found" bounces always land in the
    inbox of the account that sent the mail (SMTP_USER), whatever IMAP_USER says. A different IMAP_USER
    (e.g. the inbox replies are forwarded to) is read as well."""
    host = os.getenv("IMAP_HOST", "imap.gmail.com")
    accounts = []
    for user, password in ((os.getenv("SMTP_USER", ""), os.getenv("SMTP_PASS", "")),
                           (os.getenv("IMAP_USER", ""), os.getenv("IMAP_PASSWORD", ""))):
        user = user.strip()
        if user and password and user.lower() not in {a["user"].lower() for a in accounts}:
            accounts.append({"host": host, "user": user, "password": password})
    return accounts


def imap_settings() -> Dict[str, str]:
    """The first inbox (the sending account when it is set) - kept for callers that need one."""
    accounts = imap_accounts()
    return accounts[0] if accounts else {"host": os.getenv("IMAP_HOST", "imap.gmail.com"), "user": "", "password": ""}


def is_configured() -> bool:
    return bool(imap_accounts())


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


def _uid_state(state: Dict[str, Any]) -> Dict[str, int]:
    """Last message seen, per inbox. Older state files kept one number for the single inbox read then."""
    uids = state.get("uids")
    if not isinstance(uids, dict):
        uids = {}
        legacy_user = (os.getenv("IMAP_USER") or os.getenv("SMTP_USER") or "").strip().lower()
        if state.get("last_uid") and legacy_user:
            uids[legacy_user] = int(state.get("last_uid") or 0)
        state["uids"] = uids
    return uids


def _fetch_one(account: Dict[str, str], last_uid: int, contacted: Set[str], since: str, imap_factory):
    conn = imap_factory(account["host"])
    conn.login(account["user"], account["password"])
    conn.select("INBOX", readonly=True)
    typ, data = conn.uid("search", None, f"(SINCE {since})")
    if typ != "OK":
        raise RuntimeError("inbox search failed")
    uids = [int(u) for u in (data[0] or b"").split() if int(u) > last_uid][-MAX_MESSAGES_PER_RUN:]
    events = []
    for uid in uids:
        typ, msg_data = conn.uid("fetch", str(uid), "(BODY.PEEK[])")
        if typ != "OK" or not msg_data or not isinstance(msg_data[0], tuple):
            continue
        event = classify(msg_data[0][1], contacted)
        if event:
            events.append({**event, "uid": uid, "inbox": account["user"]})
    conn.logout()
    return events, (max(uids) if uids else last_uid)


def fetch_events(contacted: Set[str], imap_factory=imaplib.IMAP4_SSL) -> List[Dict[str, Any]]:
    """Reads new messages (read-only) from every inbox in imap_accounts() and returns classified events.
    Raises RuntimeError only when no inbox could be read."""
    accounts = imap_accounts()
    if not accounts:
        raise RuntimeError("Gmail reply check is not set up: add SMTP_USER/SMTP_PASS (or IMAP_USER/IMAP_PASSWORD)")
    state = _load_state()
    uids = _uid_state(state)
    since = (datetime.date.today() - datetime.timedelta(days=LOOKBACK_DAYS)).strftime("%d-%b-%Y")
    events, errors = [], []
    for account in accounts:
        key = account["user"].lower()
        try:
            found, last = _fetch_one(account, int(uids.get(key, 0) or 0), contacted, since, imap_factory)
        except imaplib.IMAP4.error as e:
            errors.append(f"Gmail login/IMAP error for {account['user']}: {e}")
            continue
        except OSError as e:
            errors.append(f"Could not connect to {account['host']} for {account['user']}: {e}")
            continue
        # A message forwarded from one inbox to the other is counted once
        seen = {e.get("message_id") for e in events if e.get("message_id")}
        events.extend(e for e in found if not e.get("message_id") or e["message_id"] not in seen)
        uids[key] = last
    if errors and len(errors) == len(accounts):
        raise RuntimeError("; ".join(errors))
    for err in errors:
        print(f"[reply check] {err}")
    state["last_checked_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    state.pop("last_uid", None)
    _save_state(state)
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

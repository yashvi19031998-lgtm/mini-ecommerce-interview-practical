"""
Email address checks before auto-outreach (fewer bounces = Gmail account stays healthy).

can_receive_mail(email) is True when the email's domain has a mail server:
  - an MX record, or
  - no MX but an A/AAAA record (RFC 5321 "implicit MX").
Results are cached per domain for the whole run. If DNS itself is unavailable (no internet,
dnspython missing) the check returns True so outreach is not blocked by our own problem.
"""

import re
from functools import lru_cache

try:
    import dns.exception
    import dns.resolver
    DNS_AVAILABLE = True
except ImportError:
    DNS_AVAILABLE = False

EMAIL_RE = re.compile(r"^[a-zA-Z0-9_.+-]+@([a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)*\.[a-zA-Z]{2,})$")
DNS_TIMEOUT = 6.0


@lru_cache(maxsize=2048)
def domain_accepts_mail(domain: str) -> bool:
    if not DNS_AVAILABLE:
        return True
    domain = domain.lower().strip(".")
    try:
        answers = dns.resolver.resolve(domain, "MX", lifetime=DNS_TIMEOUT)
        # A "null MX" (RFC 7505: preference 0, exchange ".") means the domain accepts no mail
        return any(str(r.exchange) not in (".", "") for r in answers)
    except dns.resolver.NXDOMAIN:
        return False  # domain does not exist
    except dns.resolver.NoAnswer:
        pass  # no MX: fall back to implicit MX (A/AAAA)
    except (dns.resolver.NoNameservers, dns.exception.Timeout):
        return True  # our DNS problem, not proof the address is bad
    for rtype in ("A", "AAAA"):
        try:
            dns.resolver.resolve(domain, rtype, lifetime=DNS_TIMEOUT)
            return True
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
            continue
        except (dns.resolver.NoNameservers, dns.exception.Timeout):
            return True
    return False


def can_receive_mail(email: str) -> bool:
    m = EMAIL_RE.match((email or "").strip())
    return bool(m) and domain_accepts_mail(m.group(1))


# ---------------------------------------------------------------------------
# Mailbox verification before any cold e-mail (2026-11-13: two Gmail accounts were blocked after
# "Address not found" bounces). Every first e-mail to an address is verified first.
# ---------------------------------------------------------------------------
import os
import random
import smtplib
import socket
import string
import threading

VERIFY_TIMEOUT = 12.0
VALID, INVALID, CATCH_ALL, UNKNOWN = "valid", "invalid", "catch_all", "unknown"

# Addresses that never belong to a person who could buy from us, or that bounce / go nowhere
_NO_REPLY_LOCAL = re.compile(r"^(no-?reply|do-?not-?reply|donotreply|noreply-.*|mailer-daemon|postmaster|bounces?|"
                             r"abuse|unsubscribe|privacy|legal|security|dmarc|root|webmaster|hostmaster)$")
_HR_LOCAL = re.compile(r"^(careers?|jobs?|job-?applications?|applications?|apply|hiring|recruit\w*|talent\w*|hr|"
                       r"humanresources|resumes?|cv)$")
_BAD_DOMAIN = re.compile(r"(^|\.)(example\.(com|org|net)|localhost|test|invalid|sentry\.io|wixpress\.com)$|"
                         r"ingest|sentry|\.local$")
_PUBLIC_SECTOR = re.compile(r"\.(gov|mil)(\.[a-z]{2})?$|\.gov\.[a-z]{2,3}$|(^|\.)nic\.in$|\.edu(\.[a-z]{2})?$|\.ac\.[a-z]{2}$")


def address_problem(email: str, policy: bool = True) -> str:
    """Why this address must not get a cold e-mail, or '' when it is fine to try.
    policy=False checks only addresses that can never work (syntax, no-reply, technical domains);
    policy=True (automatic e-mail) also skips HR inboxes and public-sector addresses."""
    e = (email or "").strip().lower()
    m = EMAIL_RE.match(e)
    if not m:
        return "not a valid e-mail address"
    local, domain = e.split("@", 1)
    if _NO_REPLY_LOCAL.match(local):
        return "no-reply / system address"
    if _BAD_DOMAIN.search(domain):
        return "technical or test domain (error tracking, example, localhost)"
    if re.fullmatch(r"[0-9a-f]{16,}", local):
        return "machine-generated address"
    if policy and _HR_LOCAL.match(local):
        return "job-application inbox (HR), not a buyer"
    if policy and _PUBLIC_SECTOR.search(domain):
        return "government / military / university address"
    return ""


_domain_catch_all = {}
_port25_blocked = {"value": None}
_lock = threading.Lock()


def _mx_hosts(domain: str):
    if not DNS_AVAILABLE:
        return []
    try:
        answers = dns.resolver.resolve(domain, "MX", lifetime=DNS_TIMEOUT)
        hosts = [str(r.exchange).rstrip(".") for r in sorted(answers, key=lambda r: r.preference)]
        return [h for h in hosts if h]
    except dns.resolver.NoAnswer:
        return [domain]  # implicit MX
    except Exception:
        return []


def _rcpt(mx: str, addresses, sender: str):
    """Asks the receiving server whether each address exists: MAIL FROM + RCPT TO, then QUIT.
    No DATA is sent, so this never delivers a message. Returns {address: smtp code} or raises."""
    s = smtplib.SMTP(mx, 25, timeout=VERIFY_TIMEOUT, local_hostname=(sender.split("@")[-1] or None))
    try:
        s.ehlo_or_helo_if_needed()
        if s.has_extn("starttls"):
            try:
                s.starttls()
                s.ehlo()
            except (smtplib.SMTPException, OSError):
                pass
        code, _ = s.mail(sender)
        if code >= 400:
            raise smtplib.SMTPResponseException(code, b"sender refused")
        return {a: s.rcpt(a)[0] for a in addresses}
    finally:
        try:
            s.quit()
        except Exception:
            pass


def verify_mailbox(email: str, sender: str = "") -> tuple:
    """(verdict, detail). verdict:
      valid      - the server confirmed this mailbox exists and is not a catch-all domain
      invalid    - the server said the mailbox does not exist (would bounce), or the domain has no mail server
      catch_all  - the domain accepts any address, so this one cannot be confirmed (bounce risk)
      unknown    - could not check (port 25 blocked, timeout, temporary error); try again later
    """
    e = (email or "").strip().lower()
    problem = address_problem(e, policy=False)
    if problem:
        return INVALID, problem
    domain = e.split("@", 1)[1]
    if not domain_accepts_mail(domain):
        return INVALID, "domain has no mail server"
    if _port25_blocked["value"]:
        return UNKNOWN, "this computer cannot reach mail servers on port 25"
    sender = sender or os.getenv("SMTP_USER") or "verify@sangeetainfotech.co.in"
    hosts = _mx_hosts(domain)
    if not hosts:
        return UNKNOWN, "could not look up the domain's mail server"
    probe = "zz-" + "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(14)) + "@" + domain
    last_error = ""
    for mx in hosts[:2]:
        try:
            with _lock:
                known_catch_all = _domain_catch_all.get(domain)
            ask = [e] if known_catch_all is not None else [e, probe]
            codes = _rcpt(mx, ask, sender)
            _port25_blocked["value"] = False
        except (socket.timeout, ConnectionRefusedError, TimeoutError) as err:
            last_error = f"{type(err).__name__} talking to {mx}"
            if _port25_blocked["value"] is None:
                _port25_blocked["value"] = True  # first ever attempt failed this way: port 25 is blocked here
                return UNKNOWN, "this computer cannot reach mail servers on port 25"
            continue
        except (smtplib.SMTPException, OSError) as err:
            last_error = f"{type(err).__name__}: {str(err)[:80]}"
            continue
        if probe in codes:
            with _lock:
                _domain_catch_all[domain] = 200 <= codes[probe] < 300
        code = codes[e]
        if 500 <= code < 600:
            return INVALID, f"mail server says the mailbox does not exist ({code})"
        if 400 <= code < 500:
            return UNKNOWN, f"temporary answer from the mail server ({code}); try later"
        if _domain_catch_all.get(domain):
            return CATCH_ALL, "domain accepts every address, so this mailbox cannot be confirmed"
        return VALID, f"mailbox confirmed by {mx}"
    return UNKNOWN, last_error or "no mail server answered"


# ---------------------------------------------------------------------------
# Whether mailbox checks work on the machine running the hourly job (GitHub runners often block port 25).
# Saved to logs/mail_check_status.json (committed with the other logs) and shown in the daily report.
# ---------------------------------------------------------------------------
STATUS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "mail_check_status.json")


def record_check_status(path: str = None) -> dict:
    """Writes what this run learned about port 25. Does nothing when no mailbox was checked this run."""
    import datetime
    import json
    blocked = _port25_blocked["value"]
    if blocked is None:
        return {}
    status = {
        "mailbox_check": "blocked" if blocked else "works",
        "checked_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "where": "GitHub Actions" if os.getenv("GITHUB_ACTIONS") == "true" else "this computer",
    }
    path = path or STATUS_FILE
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(status, fh)
    except OSError:
        pass
    return status


def read_check_status(path: str = None) -> dict:
    import json
    try:
        with open(path or STATUS_FILE, encoding="utf-8") as fh:
            data = json.load(fh)
            return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}

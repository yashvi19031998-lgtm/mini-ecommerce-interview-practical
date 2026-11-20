import os
import smtplib
import csv
import datetime
import html
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

SENT_LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "sent_emails.csv")

def ensure_sent_log_exists():
    """Ensure the sent emails permanent CSV exists."""
    os.makedirs(os.path.dirname(SENT_LOG_FILE), exist_ok=True)
    if not os.path.exists(SENT_LOG_FILE):
        with open(SENT_LOG_FILE, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["email", "sent_at", "subject"])

def get_already_sent_emails() -> set:
    """Returns a set of all lowercase emails that have ever received outreach."""
    ensure_sent_log_exists()
    sent = set()
    try:
        with open(SENT_LOG_FILE, mode="r", encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            for row in reader:
                em = str(row.get("email", "")).strip().lower()
                if em:
                    sent.add(em)
    except Exception as e:
        print(f"[WARN] Failed to read {SENT_LOG_FILE}: {e}")
    return sent

# ---------------------------------------------------------------------------------------------
# Who must never get an outreach mail
# ---------------------------------------------------------------------------------------------
# Free mail providers: different addresses there are different people, so the one-mail-per-company rule
# does not apply to them.
FREE_MAIL = {
    "gmail.com", "googlemail.com", "yahoo.com", "yahoo.in", "yahoo.co.in", "ymail.com", "outlook.com", "hotmail.com",
    "live.com", "msn.com", "icloud.com", "me.com", "aol.com", "proton.me", "protonmail.com", "rediffmail.com",
    "zoho.com", "zohomail.in", "gmx.com", "mail.com", "yandex.com",
}
# Second-level suffixes: "acme.co.in" is the company, not "co.in"
_SUFFIX2 = {"co.in", "org.in", "net.in", "firm.in", "gen.in", "ind.in", "ac.in", "edu.in", "gov.in", "nic.in",
            "co.uk", "org.uk", "ac.uk", "com.au", "net.au", "org.au", "co.nz", "com.sg", "com.br", "co.za", "com.my"}
# Addresses that never buy software: complaints, legal, privacy, robots, press
ROLE_BLOCK = re.compile(
    r"^(grievance|grievances|grievanceofficer|privacy|privacy[-._]?officer|dpo|dmca|abuse|legal|law|security|"
    r"compliance|no[-._]?reply|donotreply|do[-._]?not[-._]?reply|noreply\d*|mailer[-._]?daemon|postmaster|"
    r"webmaster|hostmaster|unsubscribe|press|media|pr|newsroom|affiliate|affiliates|warranty|escalation|"
    r"escalations|nodal|nodal[-._]?officer|investor|investors|ir|bounce|bounces)([-._].*)?$")
_LOCAL_OK = re.compile(r"^[a-z0-9][a-z0-9._%+-]*$")


def company_domain(email: str) -> str:
    """The company part of an address: info@mail.acme.co.in -> acme.co.in. Empty for free mail."""
    dom = str(email or "").strip().lower().rsplit("@", 1)[-1].strip(".")
    if not dom or dom in FREE_MAIL:
        return ""
    parts = dom.split(".")
    keep = 3 if ".".join(parts[-2:]) in _SUFFIX2 and len(parts) >= 3 else 2
    base = ".".join(parts[-keep:])
    return "" if base in FREE_MAIL else base


def outreach_block_reason(email: str, already_sent: set) -> str:
    """Why an automatic / bulk outreach mail must not go to this address ('' = it may go)."""
    email = str(email or "").strip().lower()
    local = email.split("@", 1)[0]
    if not _LOCAL_OK.match(local):
        return "the address looks broken"
    if ROLE_BLOCK.match(local):
        return f"'{local}@' is a complaints / legal / no-reply style address, not a buyer"
    dom = company_domain(email)
    if dom:
        for sent in already_sent:
            if sent != email and company_domain(sent) == dom:
                return f"this company ({dom}) already got a mail at {sent.split('@')[0]}@ - one mail per company"
    return ""


def refresh_sent_from_db() -> dict:
    """Adds addresses mailed from another machine (GitHub Actions) to the local sent log, so the duplicate and
    one-per-company checks see them. {'ok': bool, 'added': int, 'error': str}. ok is True when the database is
    not set up at all (nothing to check against)."""
    try:
        import datastore
        if not datastore.configured():
            return {"ok": True, "added": 0, "error": ""}
        remote = datastore.remote_sent_addresses()
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "added": 0, "error": str(e)[:200]}
    local = get_already_sent_emails()
    missing = sorted(remote - local)
    if missing:
        ensure_sent_log_exists()
        with open(SENT_LOG_FILE, mode="a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            for em in missing:
                writer.writerow([em, remote_note_time(), "(sent elsewhere - from the database)"])
    return {"ok": True, "added": len(missing), "error": ""}


def remote_note_time() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def record_email_sent(email: str, subject: str = ""):
    """Permanently appends an email to the sent log so it can NEVER be emailed again."""
    ensure_sent_log_exists()
    clean_email = email.strip().lower()
    existing = get_already_sent_emails()
    if clean_email in existing:
        return
    try:
        with open(SENT_LOG_FILE, mode="a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            writer.writerow([clean_email, now_str, subject.strip()[:100]])
    except Exception as e:
        print(f"[ERROR] Failed to record sent email to {SENT_LOG_FILE}: {e}")

def load_env():
    for fpath in (".env", ".env.local"):
        if os.path.exists(fpath):
            with open(fpath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip("'\"")
                    if k not in os.environ:
                        os.environ[k] = v

load_env()

def send_smtp_email(to_email: str, subject: str, message_body: str, bypass_duplicate_check: bool = False,
                    company_name: str = "", verify: str = "strict", **kwargs) -> dict:
    """
    Sends an email using Gmail SMTP credentials.

    verify - checks the recipient's mailbox with its mail server BEFORE sending, because
    "Address not found" bounces get the Gmail account blocked:
      "strict"  (default: automatic, bulk and import e-mail) - send only when the mailbox is confirmed
      "lenient" (a mail the user writes by hand) - also allows catch-all domains
      None      (follow-ups to an address that already accepted mail, tests to our own inbox) - no check
    A mailbox that does not exist is never e-mailed, whatever the setting.
    CRITICAL SAFETY: Checks get_already_sent_emails(). If to_email was EVER sent
    an email previously, the send is BLOCKED immediately to prevent spamming!
    Also enforces Do-Not-Contact blacklist rules (e.g. excluded companies like 8dots).
    """
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASS", "")
    from_email = os.getenv("SMTP_FROM_EMAIL", smtp_user or "info@sangeetainfotech.co.in")

    clean_email = str(to_email or "").strip().lower()
    website = kwargs.get("website", "")

    # DO-NOT-CONTACT / EXCLUDED COMPANIES SHIELD: checked first, before the mail login is even looked at,
    # so a blocked address is always reported as blocked. If the rule itself cannot be evaluated the
    # send is refused (fail closed) - a do-not-contact list must never be skipped by an error.
    try:
        from settings_manager import is_company_excluded
        is_ex, ex_reason = is_company_excluded(company_name=company_name, email=clean_email, website=website)
    except Exception as shield_err:
        return {"success": False, "error": f"Do-not-contact check failed, e-mail not sent: {shield_err}"}
    if is_ex:
        print(f"       [EXCLUDED-COMPANY BLOCKED] {clean_email} ({company_name}): {ex_reason}")
        return {
            "success": False,
            "error": f"Do-not-contact blacklist rule: {ex_reason}",
            "excluded": True
        }

    if not smtp_user or not smtp_pass:
        return {"success": False, "error": "SMTP credentials (SMTP_USER/SMTP_PASS) not configured in .env"}

    if not to_email or "@" not in to_email:
        return {"success": False, "error": f"Invalid recipient email: {to_email}"}

    # STRICT DUPLICATE SHIELD: Under no circumstances allow sending to the same email twice!
    if not bypass_duplicate_check:
        already_sent = get_already_sent_emails()
        # One outreach mail per company, and never to complaints / legal / no-reply addresses: several mails
        # to one company's inboxes get the sender reported and blocked.
        block = outreach_block_reason(clean_email, already_sent) if clean_email not in already_sent else ""
        if block:
            print(f"       [COMPANY / ROLE BLOCKED] {clean_email}: {block}")
            return {"success": False, "error": f"Not sent: {block}.", "blocked": True}
        if clean_email in already_sent:
            print(f"       [DUPLICATE BLOCKED] {clean_email} has ALREADY received an outreach email! Sending BLOCKED.")
            return {
                "success": False,
                "error": f"Email '{clean_email}' has already received an outreach email. Duplicate blocked.",
                "already_sent": True
            }

    # MAILBOX CHECK: never send to an address the receiving server says does not exist
    if verify:
        try:
            from email_checks import verify_mailbox, VALID, CATCH_ALL, INVALID
            verdict, detail = verify_mailbox(clean_email, sender=smtp_user)
        except Exception as verr:  # the check itself failed: do not risk a bounce
            verdict, detail = "unknown", f"address check failed: {verr}"
            VALID, CATCH_ALL, INVALID = "valid", "catch_all", "invalid"
        allowed = {VALID} if verify == "strict" else {VALID, CATCH_ALL}
        if verdict not in allowed:
            print(f"       [NOT VERIFIED] {clean_email}: {verdict} - {detail}")
            return {
                "success": False,
                "error": f"E-mail not sent - address not verified ({verdict}): {detail}",
                "verify": verdict,
                "invalid": verdict == INVALID,
            }


    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = f"\"Sangeeta Infotech\" <{from_email}>"
        msg["To"] = to_email
        msg["Subject"] = subject

        # Plain text
        plain_body = message_body
        if "wa.me/" not in plain_body:
            plain_body += "\n\n💬 Chat with us on WhatsApp: https://wa.me/919106060400?text=Hi%20Sangeeta%20Infotech%2C%20I%20got%20your%20email%20and%20would%20like%20to%20discuss."
        part_text = MIMEText(plain_body, "plain", "utf-8")
        msg.attach(part_text)

        # HTML formatting with bold highlights & key label styling
        escaped_body = html.escape(message_body)
        # 1. Convert markdown **bold** to styled <strong>
        html_styled = re.sub(
            r'\*\*(.+?)\*\*',
            r'<strong style="color: #0f172a; font-weight: 700;">\1</strong>',
            escaped_body
        )
        # 2. Bold key metadata labels (e.g. Email:, Phone:, Website:, Location:, Rate:)
        html_styled = re.sub(
            r'(?m)^([^\w\s\n]*\s*(?:Email|Phone|Phone/WhatsApp|WhatsApp|Website|Location|Address|Starting Rate|Rate)):(\s*)',
            r'<strong style="color: #0f172a; font-weight: 700;">\1:</strong>\2',
            html_styled
        )

        # High-Converting WhatsApp Action Box (Prominent & Mobile Responsive)
        wa_card_html = (
            '<div style="margin: 22px 0 16px 0; padding: 16px 20px; background: #f0fdf4; '
            'border: 1.5px solid #86efac; border-radius: 12px; display: inline-block; max-width: 520px; '
            'box-shadow: 0 4px 12px rgba(34, 197, 94, 0.08); font-family: -apple-system, BlinkMacSystemFont, \'Segoe UI\', Roboto, sans-serif;">'
            '<div style="font-size: 13.5px; font-weight: 700; color: #15803d; margin-bottom: 4px;">'
            '💬 કોઈ પ્રશ્ન હોય કે પ્રોજેક્ટ વિશે વાત કરવી હોય?'
            '</div>'
            '<div style="font-size: 12px; color: #166534; margin-bottom: 12px; line-height: 1.4;">'
            'WhatsApp પર અમારી ટીમ સાથે સીધી વાત કરવા નીચે ક્લિક કરો:'
            '</div>'
            '<a href="https://wa.me/919106060400?text=Hi%20Sangeeta%20Infotech%2C%20I%20got%20your%20email%20and%20would%20like%20to%20discuss." '
            'target="_blank" style="display: inline-block; background: #25D366; color: #ffffff !important; '
            'text-decoration: none; padding: 10px 22px; border-radius: 50px; font-weight: 700; font-size: 13.5px; '
            'box-shadow: 0 3px 8px rgba(37, 211, 102, 0.35); text-align: center;">'
            '<span style="font-size: 15px; vertical-align: -1px; margin-right: 6px;">💬</span> Chat with us on WhatsApp'
            '</a>'
            '</div>'
        )

        if "wa.me/" in html_styled:
            html_styled = re.sub(
                r'💬 Chat on WhatsApp: https://wa\.me/[^\s<]+',
                wa_card_html,
                html_styled
            )
        else:
            html_styled += "<br/>" + wa_card_html

        html_content = f"""<html>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #222; max-width: 650px; margin: 0 auto; padding: 20px;">
  <div style="font-size: 14px; white-space: pre-wrap;">{html_styled}</div>
</body>
</html>"""
        part_html = MIMEText(html_content, "html", "utf-8")
        msg.attach(part_html)

        server = smtplib.SMTP(smtp_host, smtp_port, timeout=12)
        server.starttls()
        try:
            server.login(smtp_user, smtp_pass)
        except (smtplib.SMTPResponseException, smtplib.SMTPServerDisconnected, smtplib.SMTPAuthenticationError, Exception) as lerr:
            # Check detailed diagnosis if Gmail rejected with 534 WebLoginRequired
            err_text = str(lerr)
            try:
                import base64
                diag_server = smtplib.SMTP(smtp_host, smtp_port, timeout=8)
                diag_server.starttls()
                auth_str = base64.b64encode(f"\0{smtp_user}\0{smtp_pass}".encode("utf-8")).decode("utf-8")
                code, resp = diag_server.docmd("AUTH", "PLAIN " + auth_str)
                resp_text = resp.decode("utf-8", "ignore") if isinstance(resp, bytes) else str(resp)
                diag_server.close()
                if code == 534 or "WebLoginRequired" in resp_text or "5.7.9" in resp_text:
                    return {
                        "success": False,
                        "error": "Gmail Blocked SMTP (534 WebLoginRequired). Visit https://accounts.google.com/DisplayUnlockCaptcha in browser, click Continue, then retry."
                    }
                elif code >= 400:
                    return {"success": False, "error": f"SMTP Auth Failed ({code}): {resp_text.strip()}"}
            except Exception:
                pass
            return {"success": False, "error": f"SMTP Connection/Login error: {err_text}"}
        server.sendmail(from_email, [to_email], msg.as_string())
        server.quit()

        # Record in permanent sent log immediately
        record_email_sent(clean_email, subject)

        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}

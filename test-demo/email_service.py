import os
import smtplib
import csv
import datetime
import html
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
                    company_name: str = "", verify: str = "strict") -> dict:
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

    # DO-NOT-CONTACT / EXCLUDED COMPANIES SHIELD: checked first, before the mail login is even looked at,
    # so a blocked address is always reported as blocked. If the rule itself cannot be evaluated the
    # send is refused (fail closed) - a do-not-contact list must never be skipped by an error.
    try:
        from settings_manager import is_company_excluded
        is_ex, ex_reason = is_company_excluded(company_name=company_name, email=clean_email)
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


    # STRICT DUPLICATE SHIELD: Under no circumstances allow sending to the same email twice!
    if not bypass_duplicate_check:
        already_sent = get_already_sent_emails()
        if clean_email in already_sent:
            print(f"       [DUPLICATE BLOCKED] {clean_email} has ALREADY received an outreach email! Sending BLOCKED.")
            return {
                "success": False,
                "error": f"Email '{clean_email}' has already received an outreach email. Duplicate blocked.",
                "already_sent": True
            }

    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = f"\"Sangeeta Infotech\" <{from_email}>"
        msg["To"] = to_email
        msg["Subject"] = subject

        # Plain text
        part_text = MIMEText(message_body, "plain", "utf-8")
        msg.attach(part_text)

        # HTML formatting
        html_content = f"""<html>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #222; max-width: 650px; margin: 0 auto; padding: 20px;">
  <div style="font-size: 14px; white-space: pre-wrap;">{html.escape(message_body)}</div>
</body>
</html>"""
        part_html = MIMEText(html_content, "html", "utf-8")
        msg.attach(part_html)

        server = smtplib.SMTP(smtp_host, smtp_port, timeout=12)
        server.starttls()
        try:
            server.login(smtp_user, smtp_pass)
        except smtplib.SMTPResponseException as lerr:
            err_msg = lerr.smtp_error.decode("utf-8", "ignore") if isinstance(lerr.smtp_error, bytes) else str(lerr.smtp_error)
            return {"success": False, "error": f"SMTP Login failed ({lerr.smtp_code}): {err_msg}"}
        server.sendmail(from_email, [to_email], msg.as_string())
        server.quit()

        # Record in permanent sent log immediately
        record_email_sent(clean_email, subject)

        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}

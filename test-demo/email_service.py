import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

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

def send_smtp_email(to_email: str, subject: str, message_body: str) -> dict:
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASS", "")
    from_email = os.getenv("SMTP_FROM_EMAIL", smtp_user or "sangeetainfotech19@gmail.com")

    if not smtp_user or not smtp_pass:
        return {"success": False, "error": "SMTP credentials (SMTP_USER/SMTP_PASS) not configured in .env"}

    if not to_email or "@" not in to_email:
        return {"success": False, "error": f"Invalid recipient email: {to_email}"}

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
  <div style="font-size: 14px; white-space: pre-wrap;">{message_body}</div>
</body>
</html>"""
        part_html = MIMEText(html_content, "html", "utf-8")
        msg.attach(part_html)

        server = smtplib.SMTP(smtp_host, smtp_port, timeout=12)
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(from_email, [to_email], msg.as_string())
        server.quit()

        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}

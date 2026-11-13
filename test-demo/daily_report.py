"""
Daily outreach report e-mail - "what happened today", sent every night at 12 AM (India time).

Run by .github/workflows/daily_report.yml (GitHub Actions, cron 18:30 UTC = 00:00 IST), so it works
even when nobody opens the app or the computer is off. It reads the files the hourly run commits:

    logs/sent_emails.csv          intro e-mails (one row per address, first send)
    logs/followup_activity.csv    follow-ups, dashboard sends, replies, bounces, opt-outs
    logs/scraper_runs.csv         one row per scraper per hourly run
    all_leads_master.csv          lead details (company, source, AI score, ...)

and mails one report to REPORT_EMAIL_TO (default: the company e-mail in Settings).

It is read-only: it never writes a data file, and the report itself is NOT added to sent_emails.csv
(that log is the "never e-mail this address twice" list for leads).

    python daily_report.py                    # report for the day that just ended, send it
    python daily_report.py --date 2026-11-13  # a given day
    python daily_report.py --dry-run          # build only; writes the HTML to a temp file, sends nothing

Times in the logs are local time of the machine that wrote them. The hourly GitHub run uses
TZ=Asia/Kolkata (see auto_scraper_1hr.yml), so its rows are India time too. Rows written by GitHub
before 2026-11-13 are in UTC (5 h 30 min behind).
"""

import argparse
import csv
import datetime
import html
import io
import os
import smtplib
import sys
import tempfile
from collections import Counter, defaultdict
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))

LEADS_CSV = os.path.join(BASE_DIR, "all_leads_master.csv")
SENT_CSV = os.path.join(BASE_DIR, "logs", "sent_emails.csv")
ACTIVITY_CSV = os.path.join(BASE_DIR, "logs", "followup_activity.csv")
RUNS_CSV = os.path.join(BASE_DIR, "logs", "scraper_runs.csv")
SETTINGS_JSON = os.path.join(BASE_DIR, "company_settings.json")

DAILY_CAP_DEFAULT = 50


# ---------------------------------------------------------------- reading (missing file = no rows)
def read_csv(path):
    try:
        with open(path, encoding="utf-8-sig", newline="") as fh:
            return [r for r in csv.DictReader(fh) if r]
    except OSError:
        return []


def load_env(path=os.path.join(BASE_DIR, ".env")):
    """Local runs: read .env without overriding real environment variables (GitHub secrets win)."""
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip("'\""))
    except OSError:
        pass


def load_settings():
    import json
    try:
        with open(SETTINGS_JSON, encoding="utf-8") as fh:
            data = json.load(fh)
            return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


# ---------------------------------------------------------------- helpers
def report_day(now=None):
    """The day to report: run just after midnight -> the day that just ended."""
    now = now or datetime.datetime.now(IST)
    return (now - datetime.timedelta(days=1)).date() if now.hour < 12 else now.date()


def on_day(value, day):
    return str(value or "").strip()[:10] == day.isoformat()


def time_of(value):
    v = str(value or "").strip()
    return v[11:16] if len(v) >= 16 else ""


def source_family(source):
    first = str(source or "Unknown").split("|")[0].strip().strip('"')
    return first.split(" (")[0].strip() or "Unknown"


def to_int(v):
    try:
        return int(float(v or 0))
    except (TypeError, ValueError):
        return 0


def lead_index(leads):
    by_email, by_id = {}, {}
    for lead in leads:
        by_id[lead.get("lead_id", "")] = lead
        for em in str(lead.get("email", "")).split(","):
            em = em.strip().lower()
            if em and "@" in em:
                by_email.setdefault(em, lead)
    return by_email, by_id


def lead_row(lead, email="", when="", subject="", how=""):
    lead = lead or {}
    return {
        "time": when, "company": lead.get("company_name") or "(not in leads list)",
        "email": email or str(lead.get("email", "")).split(",")[0].strip(),
        "subject": subject, "how": how, "lead_id": lead.get("lead_id", ""),
        "source": source_family(lead.get("source")) if lead else "",
        "ai_score": lead.get("ai_score", ""), "location": lead.get("location", ""),
        "phone": str(lead.get("mobile_number", "")).split(",")[0].strip(),
    }


SEND_KIND = {"auto outreach": "Auto (hourly run)", "dashboard": "Manual (dashboard)",
             "bulk email": "Bulk e-mail", "import": "Import"}


def send_kind(source):
    s = str(source or "").lower()
    if s.startswith("followup sequence"):
        return "Follow-up"
    for key, label in SEND_KIND.items():
        if key in s:
            return label
    return "Other"


# ---------------------------------------------------------------- the report
def _mail_check_status() -> dict:
    try:
        from email_checks import read_check_status
        return read_check_status()
    except Exception:
        return {}


def build_report(day, leads, sent, activities, runs, settings, daily_cap=DAILY_CAP_DEFAULT):
    by_email, by_id = lead_index(leads)

    # Intro e-mails: sent_emails.csv (first mail to an address). How it was sent comes from the
    # activity log when there is a matching row.
    act_kind = {}
    for a in activities:
        if a.get("type") == "email_sent" and on_day(a.get("occurred_at"), day):
            act_kind.setdefault(str(a.get("lead_email", "")).strip().lower(), send_kind(a.get("source")))
    # Our own addresses (the Settings "Send Test Verification Email" button goes there) are not outreach
    own = {str(a).strip().lower() for a in (settings.get("email"), os.getenv("SMTP_USER"), os.getenv("SMTP_FROM_EMAIL"),
                                            os.getenv("REPORT_EMAIL_TO")) if a}
    intro, own_tests = [], 0
    for r in sent:
        if not on_day(r.get("sent_at"), day):
            continue
        em = str(r.get("email", "")).strip().lower()
        if em in own:
            own_tests += 1
            continue
        intro.append(lead_row(by_email.get(em), em, time_of(r.get("sent_at")), r.get("subject", ""),
                              act_kind.get(em, "Auto / earlier tracking")))
    intro_emails = {row["email"].lower() for row in intro}

    followups, other_sends, replies, problems = [], [], [], []
    for a in activities:
        if not on_day(a.get("occurred_at"), day):
            continue
        em = str(a.get("lead_email", "")).strip().lower()
        lead = by_id.get(a.get("lead_id", "")) or by_email.get(em)
        row = lead_row(lead, em, time_of(a.get("occurred_at")), a.get("summary", ""), send_kind(a.get("source")))
        kind = a.get("type")
        if kind == "email_sent":
            if row["how"] == "Follow-up":
                followups.append(row)
            elif em not in intro_emails:
                other_sends.append(row)  # e.g. a second manual mail to the same address
        elif kind == "reply":
            replies.append(row)
        elif kind in ("bounce", "opted_out"):
            row["how"] = "Bounced" if kind == "bounce" else "Opted out"
            problems.append(row)

    new_leads = [lead_row(l, when=time_of(l.get("first_seen_at"))) for l in leads if on_day(l.get("first_seen_at"), day)]
    for row, lead in zip(new_leads, [l for l in leads if on_day(l.get("first_seen_at"), day)]):
        row["subject"] = str(lead.get("ai_category", ""))

    day_runs = [r for r in runs if on_day(r.get("start_time"), day)]
    per_scraper = defaultdict(lambda: {"runs": 0, "failed": 0, "records": 0, "new": 0, "duplicates": 0, "error": ""})
    for r in day_runs:
        name = str(r.get("scraper_name", "")).split(" (")[0].strip() or "unknown"
        s = per_scraper[name]
        s["runs"] += 1
        s["records"] += to_int(r.get("records_collected"))
        s["new"] += to_int(r.get("new_leads_added"))
        s["duplicates"] += to_int(r.get("duplicates_detected"))
        if str(r.get("status", "")).lower() not in ("success", "ok"):
            s["failed"] += 1
            s["error"] = str(r.get("error_summary", ""))[:120]
    scrapers = sorted(({"scraper": k, **v} for k, v in per_scraper.items()), key=lambda x: (-x["new"], -x["records"]))

    emails_today = len(intro) + len(followups) + len(other_sends)
    by_kind = Counter(r["how"] for r in intro + followups + other_sends)
    by_source = Counter(r["source"] or "Unknown" for r in intro + followups + other_sends)
    totals = {
        "emails_sent": emails_today, "intro": len(intro), "followups": len(followups), "other": len(other_sends),
        "replies": len(replies), "bounced_or_opted_out": len(problems), "new_leads": len(new_leads),
        "hourly_runs": len({r.get("run_id") for r in day_runs}), "scraper_failures": sum(s["failed"] for s in scrapers),
        "records_collected": sum(s["records"] for s in scrapers),
    }
    try:
        per_run = int(settings.get("maxPendingEmailsPerRun", 5))
    except (TypeError, ValueError):
        per_run = 5
    status = {
        "auto_send": bool(settings.get("autoSendEmail", True)),
        "per_run_limit": "no limit" if per_run == 0 else per_run,
        "daily_cap": daily_cap, "daily_cap_used": emails_today,
        "leads_failed_status": sum(1 for l in leads if str(l.get("email_status", "")).upper() == "FAILED"),
        "total_leads": len(leads),
        "excluded_companies": settings.get("excludedCompanies", []),
        "test_mails_to_own_address": own_tests,
        "mail_check": _mail_check_status(),
    }
    return {"day": day.isoformat(), "totals": totals, "by_kind": dict(by_kind), "by_source": dict(by_source),
            "intro": sorted(intro, key=lambda r: r["time"]), "followups": followups, "other_sends": other_sends,
            "replies": replies, "problems": problems, "new_leads": new_leads, "scrapers": scrapers, "status": status}


# ---------------------------------------------------------------- output
def _csv_safe(v):
    v = "" if v is None else str(v)
    return "'" + v if v[:1] in ("=", "+", "-", "@", "\t", "\r") else v


def sent_csv(report):
    out = io.StringIO()
    cols = ["time", "how", "company", "email", "phone", "subject", "lead_id", "source", "ai_score", "location"]
    w = csv.writer(out)
    w.writerow(cols)
    for r in report["intro"] + report["followups"] + report["other_sends"]:
        w.writerow([_csv_safe(r.get(c, "")) for c in cols])
    return "﻿" + out.getvalue()


def _table(rows, cols, empty):
    e = html.escape
    if not rows:
        return f'<p style="color:#8a8f98;margin:6px 0 18px">{e(empty)}</p>'
    head = "".join(f'<th style="text-align:left;padding:6px 8px;border-bottom:1px solid #e2e2e5;font-size:12px;color:#5b5f67">{e(label)}</th>' for _, label in cols)
    body = ""
    for r in rows:
        body += "<tr>" + "".join(f'<td style="padding:6px 8px;border-bottom:1px solid #f2f2f3;font-size:13px;vertical-align:top">{e(str(r.get(k, "")))}</td>' for k, _ in cols) + "</tr>"
    return f'<table style="border-collapse:collapse;width:100%;margin:6px 0 18px">{"<tr>" + head + "</tr>"}{body}</table>'


def _mail_check_html(mc: dict) -> str:
    """Tells the owner whether automatic e-mail can work where the hourly job runs."""
    if not mc:
        return ""
    if mc.get("mailbox_check") == "blocked":
        return ('<p style="background:#fdf1e3;color:#a2650d;padding:10px 12px;border-radius:10px">Mailbox check is '
                f'<b>blocked</b> on {html.escape(str(mc.get("where", "")))} (last seen {html.escape(str(mc.get("checked_at", "")))}). '
                'To avoid bounces, no automatic e-mail is sent from there. Send from the app on your computer '
                '(Run 1-Hour Cycle Now), or add a mailbox-verification service.</p>')
    return (f'<p style="font-size:13px;color:#1f9254">Mailbox check works on {html.escape(str(mc.get("where", "")))} '
            f'(last seen {html.escape(str(mc.get("checked_at", "")))}).</p>')


def render(report):
    e = html.escape
    t, st = report["totals"], report["status"]
    day_label = datetime.date.fromisoformat(report["day"]).strftime("%d %b %Y")
    subject = f"Daily lead report - {day_label}: {t['emails_sent']} e-mail{'s' if t['emails_sent'] != 1 else ''} sent, {t['new_leads']} new lead{'s' if t['new_leads'] != 1 else ''}"

    cards = [("E-mails sent", t["emails_sent"]), ("Intro e-mails", t["intro"]), ("Follow-ups", t["followups"]),
             ("Replies", t["replies"]), ("Bounced / opted out", t["bounced_or_opted_out"]),
             ("New leads found", t["new_leads"]), ("Hourly runs", t["hourly_runs"]), ("Scraper failures", t["scraper_failures"])]
    cells = [
        f'<td style="padding:10px 12px;background:#f7f7f8;border-radius:10px;text-align:center;width:25%">'
        f'<div style="font-size:22px;font-weight:700;color:#16181d">{v:,}</div><div style="font-size:12px;color:#5b5f67">{e(label)}</div></td>'
        for label, v in cards]
    card_rows = (f'<table style="width:100%;border-spacing:8px"><tr>{"".join(cells[:4])}</tr>'
                 f'<tr>{"".join(cells[4:])}</tr></table>')

    sent_cols = [("time", "Time"), ("how", "How"), ("company", "Company / lead"), ("email", "E-mail"),
                 ("subject", "Subject"), ("source", "Source"), ("ai_score", "AI score"), ("lead_id", "Lead ID")]
    mix = ", ".join(f"{k}: {v}" for k, v in sorted(report["by_kind"].items())) or "none"
    src = ", ".join(f"{k}: {v}" for k, v in sorted(report["by_source"].items(), key=lambda kv: -kv[1])) or "none"
    warn = ""
    if st["auto_send"] and t["emails_sent"] == 0 and t["hourly_runs"] > 0:
        warn = ('<p style="background:#fdf1e3;color:#a2650d;padding:10px 12px;border-radius:10px">Auto e-mail is on, the hourly '
                'run ran, but no e-mail went out. Check the Gmail login (app Settings &rarr; Send Test Verification Email) '
                'and the GitHub secret SMTP_PASS.</p>')
    if t["emails_sent"] >= st["daily_cap"]:
        warn += (f'<p style="background:#fdf1e3;color:#a2650d;padding:10px 12px;border-radius:10px">The daily limit of '
                 f'{st["daily_cap"]} e-mails was reached; the remaining leads are e-mailed tomorrow.</p>')

    body = f"""<html><body style="font-family:-apple-system,'Segoe UI',Roboto,Arial,sans-serif;color:#16181d;max-width:900px;margin:0 auto;padding:16px">
<h2 style="margin:0 0 4px">Daily lead report &mdash; {e(day_label)}</h2>
<p style="margin:0 0 12px;color:#5b5f67">LeadsGen AI &middot; everything that happened on this day (India time).</p>
{warn}{card_rows}
<p style="font-size:13px;color:#3c3f46">E-mails by type: {e(mix)}<br>E-mails by lead source: {e(src)}</p>
<h3 style="margin:18px 0 4px">E-mails sent ({t['emails_sent']})</h3>
{_table(report['intro'] + report['followups'] + report['other_sends'], sent_cols, 'No e-mail was sent on this day.')}
<h3 style="margin:18px 0 4px">Replies ({t['replies']})</h3>
{_table(report['replies'], [('time','Time'),('company','Company / lead'),('email','E-mail'),('subject','Summary'),('lead_id','Lead ID')], 'No replies recorded on this day.')}
<h3 style="margin:18px 0 4px">Bounced / opted out ({t['bounced_or_opted_out']})</h3>
{_table(report['problems'], [('time','Time'),('how','What'),('company','Company / lead'),('email','E-mail'),('lead_id','Lead ID')], 'None.')}
<h3 style="margin:18px 0 4px">Scrapers ({t['hourly_runs']} hourly runs, {t['records_collected']:,} records collected)</h3>
{_table(report['scrapers'], [('scraper','Scraper'),('runs','Runs'),('records','Records'),('new','New leads'),('duplicates','Duplicates'),('failed','Failed'),('error','Last error')], 'No scraper ran on this day.')}
<h3 style="margin:18px 0 4px">New leads found ({t['new_leads']})</h3>
{_table(report['new_leads'][:100], [('time','Time'),('company','Company / lead'),('email','E-mail'),('phone','Phone'),('source','Source'),('ai_score','AI score'),('subject','AI category'),('lead_id','Lead ID')], 'No new leads on this day.')}
{'<p style="color:#8a8f98;font-size:12px">Showing the first 100 new leads.</p>' if t['new_leads'] > 100 else ''}
<h3 style="margin:18px 0 4px">Settings at report time</h3>
<p style="font-size:13px;color:#3c3f46;line-height:1.7">
Auto e-mail: <b>{'ON' if st['auto_send'] else 'OFF'}</b> &middot; per hourly run: <b>{e(str(st['per_run_limit']))}</b> &middot;
daily limit: <b>{st['daily_cap_used']} / {st['daily_cap']}</b> used<br>
Total leads: <b>{st['total_leads']:,}</b> &middot; leads whose last send failed: <b>{st['leads_failed_status']}</b> &middot;
do-not-contact list: {e(', '.join(map(str, st['excluded_companies'])) or 'empty')}
{f"<br>Test mails to our own address (not counted above): <b>{st['test_mails_to_own_address']}</b>" if st['test_mails_to_own_address'] else ''}</p>
{_mail_check_html(st.get('mail_check') or {})}
<p style="color:#8a8f98;font-size:12px">The attached CSV lists every e-mail sent on this day. Sent automatically by the daily report (GitHub Actions).</p>
</body></html>"""

    lines = [f"Daily lead report - {day_label}", "",
             *[f"{label}: {v}" for label, v in cards], "",
             "E-mails sent:"]
    for r in report["intro"] + report["followups"] + report["other_sends"]:
        lines.append(f"  {r['time']}  {r['how']:<22} {r['company'][:40]:<40} {r['email']}")
    if not t["emails_sent"]:
        lines.append("  none")
    return subject, body, "\n".join(lines)


def send(subject, html_body, text_body, attachment, to_addr):
    user, pw = os.getenv("SMTP_USER", ""), os.getenv("SMTP_PASS", "")
    if not user or not pw:
        raise RuntimeError("SMTP_USER / SMTP_PASS are not set")
    from_addr = os.getenv("SMTP_FROM_EMAIL") or user
    msg = MIMEMultipart("mixed")
    msg["From"] = f'"LeadsGen AI Report" <{from_addr}>'
    msg["To"] = to_addr
    msg["Subject"] = subject
    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(text_body, "plain", "utf-8"))
    alt.attach(MIMEText(html_body, "html", "utf-8"))
    msg.attach(alt)
    if attachment:
        name, data = attachment
        part = MIMEApplication(data.encode("utf-8"), Name=name)
        part["Content-Disposition"] = f'attachment; filename="{name}"'
        msg.attach(part)
    server = smtplib.SMTP(os.getenv("SMTP_HOST") or "smtp.gmail.com", int(os.getenv("SMTP_PORT") or 587), timeout=30)
    try:
        server.starttls()
        server.login(user, pw)
        server.sendmail(from_addr, [to_addr], msg.as_string())
    finally:
        try:
            server.quit()
        except Exception:
            pass


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--date", help="YYYY-MM-DD (default: the day that just ended, India time)")
    ap.add_argument("--dry-run", action="store_true", help="build the report but do not send it")
    args = ap.parse_args(argv)
    load_env()
    try:  # Windows consoles cannot print every character in lead names (emoji etc.)
        sys.stdout.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass

    date_arg = args.date or os.getenv("REPORT_DATE", "").strip()
    try:
        day = datetime.date.fromisoformat(date_arg) if date_arg else report_day()
    except ValueError:
        print(f"Bad date {date_arg!r}: use YYYY-MM-DD")
        return 2
    settings = load_settings()
    try:
        cap = int(os.getenv("MAX_EMAILS_PER_DAY") or DAILY_CAP_DEFAULT)
    except ValueError:
        cap = DAILY_CAP_DEFAULT
    report = build_report(day, read_csv(LEADS_CSV), read_csv(SENT_CSV), read_csv(ACTIVITY_CSV),
                          read_csv(RUNS_CSV), settings, daily_cap=cap)
    subject, html_body, text_body = render(report)
    print(text_body)

    if args.dry_run:
        path = os.path.join(tempfile.gettempdir(), f"daily-report-{day.isoformat()}.html")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(html_body)
        print(f"\n[dry run] Not sent. Preview: {path}")
        return 0

    to_addr = (os.getenv("REPORT_EMAIL_TO") or settings.get("email") or os.getenv("SMTP_USER") or "").strip()
    if "@" not in to_addr:
        print("No address to send the report to: set REPORT_EMAIL_TO or the company e-mail in Settings.")
        return 1
    try:
        send(subject, html_body, text_body, (f"emails-sent-{day.isoformat()}.csv", sent_csv(report)), to_addr)
    except Exception as err:  # a failed report must show as a failed GitHub run
        print(f"\n[FAILED] Could not send the report to {to_addr}: {err}")
        return 1
    print(f"\nReport sent to {to_addr}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

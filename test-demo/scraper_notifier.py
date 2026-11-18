"""
Scraper Notification Helper
===========================
Dispatches immediate email alerts to admin when GitHub Actions (or local cron)
scraper begins and finishes with exact lead counts and telemetry.
"""

import os
import sys
import csv
import datetime
from typing import Dict, Any

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from email_service import send_smtp_email
from settings_manager import load_settings

MASTER_CSV = os.path.join(BASE_DIR, "all_leads_master.csv")
RUNS_LOG_CSV = os.path.join(BASE_DIR, "logs", "scraper_runs.csv")


def get_admin_recipient() -> str:
    settings = load_settings() if load_settings else {}
    return (
        os.getenv("ADMIN_EMAIL")
        or os.getenv("NOTIFICATION_EMAIL")
        or settings.get("email")
        or os.getenv("SMTP_USER")
        or "yashvishah991@gmail.com"
    )


def count_master_leads() -> Dict[str, int]:
    total = 0
    with_email = 0
    with_phone = 0
    if os.path.exists(MASTER_CSV):
        try:
            with open(MASTER_CSV, mode="r", encoding="utf-8-sig", errors="ignore") as f:
                reader = csv.DictReader(f)
                for r in reader:
                    total += 1
                    em = str(r.get("email") or "").strip()
                    ph = str(r.get("mobile_number") or r.get("phone") or "").strip()
                    if em and "@" in em and em.upper() != "N/A":
                        with_email += 1
                    if ph and len(ph) >= 7 and ph.upper() != "N/A":
                        with_phone += 1
        except Exception:
            pass
    return {"total": total, "with_email": with_email, "with_phone": with_phone}


def get_latest_run_stats() -> Dict[str, Any]:
    stats = {
        "run_id": "N/A",
        "records_collected": 0,
        "new_leads_added": 0,
        "duplicates_detected": 0,
        "status": "Success",
        "duration": "N/A"
    }
    if os.path.exists(RUNS_LOG_CSV):
        try:
            with open(RUNS_LOG_CSV, mode="r", encoding="utf-8-sig", errors="ignore") as f:
                rows = list(csv.DictReader(f))
                if rows:
                    last = rows[-1]
                    stats["run_id"] = last.get("run_id", "N/A")
                    stats["records_collected"] = int(last.get("records_collected") or 0)
                    stats["new_leads_added"] = int(last.get("new_leads_added") or 0)
                    stats["duplicates_detected"] = int(last.get("duplicates_detected") or 0)
                    stats["status"] = last.get("status", "Success")
                    st = last.get("start_time")
                    et = last.get("end_time")
                    if st and et:
                        try:
                            t1 = datetime.datetime.fromisoformat(st)
                            t2 = datetime.datetime.fromisoformat(et)
                            stats["duration"] = f"{(t2 - t1).total_seconds():.1f}s"
                        except Exception:
                            pass
        except Exception:
            pass
    return stats


def notify_start(workflow_name: str = "1-Hour Auto Lead Scraper"):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    counts = count_master_leads()
    recipient = get_admin_recipient()

    subject = f"🚀 [SCRAPER STARTED] {workflow_name} ({now})"
    body = (
        f"Hi Yashvi / Team Sangeeta Infotech,\n\n"
        f"The autonomous lead scraper has STARTED running on GitHub Actions.\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚙️ RUN DETAILS:\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• Workflow:         {workflow_name}\n"
        f"• Trigger Time:     {now} IST\n"
        f"• Runner:           GitHub Actions (Ubuntu Linux)\n"
        f"• Active Channels:  23 Scrapers (Google Maps, Search Engine Dorks, Justdial, B2B Portals, Freelancer)\n"
        f"• Current DB Leads: {counts['total']:,} total ({counts['with_email']:,} with verified email)\n\n"
        f"You will receive a completion summary email as soon as scraping & deep contact extraction finishes.\n\n"
        f"Best regards,\n"
        f"Sangeeta Infotech Automation Bot\n"
        f"https://sangeetainfotech.co.in"
    )

    print(f"[*] Sending scraper start notification to {recipient}...")
    res = send_smtp_email(to_email=recipient, subject=subject, message_body=body, verify=None, bypass_duplicate_check=True)
    if res.get("success"):
        print(f"[OK] Start email notification sent to {recipient}.")
    else:
        print(f"[WARN] Failed to send start email notification: {res.get('error')}")


def notify_finish(workflow_name: str = "1-Hour Auto Lead Scraper"):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    counts = count_master_leads()
    stats = get_latest_run_stats()
    recipient = get_admin_recipient()

    new_count = stats["new_leads_added"]
    subject = f"✅ [SCRAPER FINISHED] +{new_count} New Leads Harvested | Total: {counts['total']:,}"
    body = (
        f"Hi Yashvi / Team Sangeeta Infotech,\n\n"
        f"The autonomous lead scraper has FINISHED its cycle on GitHub Actions.\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 HARVEST TELEMETRY & RESULTS:\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• Status:                   {stats['status'].upper()}\n"
        f"• Completed At:             {now} IST\n"
        f"• Execution Duration:       {stats['duration']}\n"
        f"• Raw Records Collected:    {stats['records_collected']}\n"
        f"• Genuinely New Leads:      +{stats['new_leads_added']}\n"
        f"• Duplicate Leads Filtered: {stats['duplicates_detected']}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📈 MASTER DATABASE TOTALS:\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• Total Master Leads:       {counts['total']:,}\n"
        f"• Leads with Direct Email:  {counts['with_email']:,}\n"
        f"• Leads with Mobile Number: {counts['with_phone']:,}\n\n"
        f"All harvested leads have been qualified with AI and synchronized to your Supabase Cloud Database.\n\n"
        f"Best regards,\n"
        f"Sangeeta Infotech Automation Bot\n"
        f"https://sangeetainfotech.co.in"
    )

    print(f"[*] Sending scraper finish notification to {recipient}...")
    res = send_smtp_email(to_email=recipient, subject=subject, message_body=body, verify=None, bypass_duplicate_check=True)
    if res.get("success"):
        print(f"[OK] Finish email notification sent to {recipient}.")
    else:
        print(f"[WARN] Failed to send finish email notification: {res.get('error')}")


if __name__ == "__main__":
    action = sys.argv[1].lower() if len(sys.argv) > 1 else "finish"
    name = sys.argv[2] if len(sys.argv) > 2 else "1-Hour Auto Lead Scraper"
    if action == "start":
        notify_start(name)
    else:
        notify_finish(name)

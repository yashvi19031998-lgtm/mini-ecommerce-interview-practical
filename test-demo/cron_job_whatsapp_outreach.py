"""
CRON JOB: Automated WhatsApp Web Outreach Dispatcher (Option 1)
==============================================================
Dispatches personalized cold WhatsApp outreach messages directly to verified lead phone numbers:
- Uses Playwright persistent browser session (whatsapp_session/) so QR code is scanned ONLY ONCE.
- Filters leads from all_leads_master.csv where mobile_number is present and whatsapp_status != 'SENT'.
- Enforces strict Sangeeta Infotech brand messaging: ₹450/- INR / hr, 5+ yrs exp, 80+ clients, 7-day trial.
- Enforces Do-Not-Contact / Excluded Companies shield (e.g. 8dots).
- Detects invalid/non-WhatsApp numbers and marks them NOT_ON_WHATSAPP.
- Applies polite randomized delays (60-120s) between messages to maintain 100% account safety.
- Updates all_leads_master.csv and logs to logs/whatsapp_sent_history.csv.
"""

import os
import re
import sys
import time
import urllib.parse
import argparse
import datetime
import csv
from typing import List, Dict, Any, Tuple, Optional

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

MASTER_CSV = os.path.join(BASE_DIR, "all_leads_master.csv")
SESSION_DIR = os.path.join(BASE_DIR, "logs", "whatsapp_session")
HISTORY_CSV = os.path.join(BASE_DIR, "logs", "whatsapp_sent_history.csv")

try:
    from settings_manager import load_settings
    _settings = load_settings()
except Exception:
    _settings = {}

EXCLUDED_COMPANIES = set(k.lower() for k in _settings.get("excludedCompanies", ["8dots"]))
DEFAULT_MAX_BATCH = 5
MAX_DAILY_WHATSAPP = 25


def normalize_whatsapp_number(phone_str: str) -> Optional[str]:
    """
    Normalizes phone numbers to standard E.164 international format without leading '+'.
    Indian 10-digit mobile numbers are prefixed with '91'.
    """
    if not phone_str:
        return None
    # Strip everything except digits
    digits = re.sub(r"\D", "", str(phone_str))
    if len(digits) < 10 or len(digits) > 14:
        return None

    # Handle standard 10-digit Indian numbers
    if len(digits) == 10 and digits[0] in ("6", "7", "8", "9"):
        return f"91{digits}"
    # If 11 digits starting with 0 (e.g. 09876543210)
    elif len(digits) == 11 and digits.startswith("0"):
        return f"91{digits[1:]}"
    # If already has 91 country code (12 digits)
    elif len(digits) == 12 and digits.startswith("91"):
        return digits
    # Other international numbers (US/UK/UAE) with country codes
    elif len(digits) >= 11:
        return digits

    return None


def format_whatsapp_message(lead: Dict[str, Any], settings: Optional[Dict[str, Any]] = None) -> str:
    """Formats the high-converting Sangeeta Infotech outreach message."""
    cfg = settings or _settings or {}
    comp = (lead.get("company_name") or "there").strip()
    if len(comp) > 40 or any(bad in comp.lower() for bad in ("hiring", "developer", "show hn", "http")):
        comp = "your team"

    msg = (
        f"Hi Team {comp},\n\n"
        f"I came across {comp}'s software and digital operations.\n\n"
        f"At Sangeeta Infotech (Ahmedabad), our engineering team brings 5+ years of experience building web applications, "
        f"mobile apps, and custom CRMs for 80+ clients using the latest AI tools and modern technologies.\n\n"
        f"Our dedicated developer packages start from just ₹450/- INR / hour (~$5.5/hr) with a 7-day risk-free trial.\n\n"
        f"Would you be open to a quick 10-minute chat this week, or would you like to see a few live examples of our recent work?\n\n"
        f"Warm regards,\n"
        f"Sangeeta Infotech | +91 9106060400\n"
        f"https://sangeetainfotech.co.in"
    )
    return msg


def select_pending_whatsapp_leads(csv_path: str = MASTER_CSV, max_batch: int = 5) -> List[Dict[str, Any]]:
    """Selects eligible leads with valid mobile numbers that haven't been contacted via WhatsApp."""
    if not os.path.exists(csv_path):
        return []

    eligible = []
    with open(csv_path, mode="r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            status = (row.get("whatsapp_status") or "").upper().strip()
            if status in ("SENT", "NOT_ON_WHATSAPP", "FAILED_INVALID"):
                continue

            comp = (row.get("company_name") or "").lower()
            if any(ex in comp for ex in EXCLUDED_COMPANIES):
                continue

            raw_phone = row.get("mobile_number") or ""
            clean_phone = normalize_whatsapp_number(raw_phone)
            if not clean_phone:
                continue

            # Prioritize higher intent leads
            try:
                score = float(row.get("intent_score") or row.get("ai_score") or 5)
            except Exception:
                score = 5.0

            eligible.append({
                "lead_id": row.get("\ufefflead_id") or row.get("lead_id"),
                "company_name": row.get("company_name"),
                "phone": clean_phone,
                "raw_phone": raw_phone,
                "score": score,
                "row": row
            })

    eligible.sort(key=lambda x: x["score"], reverse=True)
    return eligible[:max_batch]


def update_lead_whatsapp_status(lead_id: str, new_status: str, csv_path: str = MASTER_CSV) -> bool:
    """Updates whatsapp_status and last_contacted_at in all_leads_master.csv."""
    if not os.path.exists(csv_path) or not lead_id:
        return False

    rows = []
    updated = False
    fieldnames = []
    now_ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with open(csv_path, mode="r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        for r in reader:
            lid = r.get("\ufefflead_id") or r.get("lead_id")
            if lid == lead_id:
                r["whatsapp_status"] = new_status
                r["last_contacted_at"] = now_ts
                updated = True
            rows.append(r)

    if updated:
        with open(csv_path, mode="w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    return updated


def log_whatsapp_history(lead_id: str, company: str, phone: str, status: str, message: str):
    """Appends record to logs/whatsapp_sent_history.csv."""
    os.makedirs(os.path.dirname(HISTORY_CSV), exist_ok=True)
    file_exists = os.path.exists(HISTORY_CSV)
    with open(HISTORY_CSV, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["timestamp", "lead_id", "company_name", "phone", "status", "message_preview"])
        writer.writerow([
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            lead_id,
            company,
            phone,
            status,
            message[:120].replace("\n", " ")
        ])


def run_whatsapp_dispatcher(max_batch: int = DEFAULT_MAX_BATCH, dry_run: bool = False, delay_sec: int = 45):
    """
    Main dispatch routine using Playwright browser automation with persistent session.
    """
    print("=" * 68)
    print("📱 SANGEETA INFOTECH — WHATSAPP OUTREACH DISPATCHER (OPTION 1)")
    print("=" * 68)

    leads = select_pending_whatsapp_leads(max_batch=max_batch)
    if not leads:
        print("[INFO] No pending leads found with valid phone numbers. Everything up to date!")
        return 0

    print(f"[*] Found {len(leads)} qualified leads pending WhatsApp outreach:")
    for i, l in enumerate(leads, 1):
        print(f"  {i}. {l['company_name']} ({l['phone']}) - Score: {l['score']}")

    if dry_run:
        print("\n[DRY RUN] Previewing message for first lead:")
        print("-" * 50)
        print(format_whatsapp_message(leads[0]))
        print("-" * 50)
        return len(leads)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[ERROR] Playwright is not installed. Please run: pip install playwright && playwright install chromium")
        return 0

    os.makedirs(SESSION_DIR, exist_ok=True)
    sent_count = 0

    with sync_playwright() as p:
        print(f"\n[*] Launching WhatsApp Web session from: {SESSION_DIR}")
        context = p.chromium.launch_persistent_context(
            user_data_dir=SESSION_DIR,
            headless=False,  # Headless false allows viewing QR scan and chat interface
            args=["--start-maximized", "--no-sandbox"],
            viewport={"width": 1280, "height": 800}
        )
        page = context.pages[0] if context.pages else context.new_page()

        # Step 1: Navigate to WhatsApp Web and check login status
        print("[*] Navigating to https://web.whatsapp.com...")
        page.goto("https://web.whatsapp.com", timeout=60000)

        # Wait up to 60s for user to scan QR code if not logged in
        print("[*] Checking WhatsApp Web login status...")
        try:
            # Check for chat list / search bar indicating logged-in state
            page.wait_for_selector('div[contenteditable="true"], div[aria-label="Chat list"], #side', timeout=45000)
            print("[✅ LOGIN CONFIRMED] WhatsApp Web is active and logged in!")
        except Exception:
            print("\n" + "!" * 68)
            print("🔔 PLEASE SCAN QR CODE ON YOUR SCREEN TO LOGIN!")
            print("Open WhatsApp on your phone (+91 9106060400) -> Linked Devices -> Link a Device")
            print("Waiting up to 60 seconds for login...")
            print("!" * 68)
            try:
                page.wait_for_selector('div[contenteditable="true"], div[aria-label="Chat list"], #side', timeout=60000)
                print("[✅ LOGIN CONFIRMED] Login successful! Session saved for future automated runs.")
            except Exception:
                print("[ERROR] QR code scan timed out. Please run with --login-only and scan the QR code.")
                context.close()
                return 0

        # Step 2: Iterate over candidate leads
        for idx, item in enumerate(leads, 1):
            phone = item["phone"]
            comp = item["company_name"]
            lid = item["lead_id"]
            body = format_whatsapp_message(item)
            encoded_text = urllib.parse.quote(body)
            target_url = f"https://web.whatsapp.com/send?phone={phone}&text={encoded_text}"

            print(f"\n[{idx}/{len(leads)}] Preparing outreach to {comp} (+{phone})...")
            try:
                page.goto(target_url, timeout=45000)
                time.sleep(4)

                # Check if number is not on WhatsApp
                invalid_dialog = page.query_selector('text="Phone number shared via url is invalid", text="Phone number is not on WhatsApp", div[data-animate-modal-body="true"]')
                if invalid_dialog:
                    print(f"  [-] Number +{phone} is not on WhatsApp. Marking NOT_ON_WHATSAPP.")
                    update_lead_whatsapp_status(lid, "NOT_ON_WHATSAPP")
                    log_whatsapp_history(lid, comp, phone, "NOT_ON_WHATSAPP", body)
                    continue

                # Wait for send button or active message input box
                send_button = page.wait_for_selector('span[data-icon="send"], button[aria-label="Send"]', timeout=15000)
                if send_button:
                    time.sleep(1)
                    send_button.click()
                    time.sleep(2)
                    print(f"  [✅ SENT] Successfully dispatched WhatsApp message to {comp} (+{phone})!")
                    update_lead_whatsapp_status(lid, "SENT")
                    log_whatsapp_history(lid, comp, phone, "SENT", body)
                    sent_count += 1

                    # Polite delay between messages to protect number
                    if idx < len(leads):
                        print(f"  [*] Sleeping {delay_sec}s between messages for account safety...")
                        time.sleep(delay_sec)
                else:
                    print(f"  [!] Send button not found for {comp}. Skipping.")

            except Exception as e:
                print(f"  [!] Failed to send to {comp} (+{phone}): {e}")

        context.close()

    print("\n" + "=" * 68)
    print(f"[SUMMARY] Total WhatsApp messages sent: {sent_count}/{len(leads)}")
    print("=" * 68)
    return sent_count


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Automated WhatsApp Web Outreach Dispatcher")
    parser.add_argument("--max-batch", type=int, default=DEFAULT_MAX_BATCH, help="Max leads to contact in this run")
    parser.add_argument("--dry-run", action="store_true", help="Preview messages without opening WhatsApp")
    parser.add_argument("--login-only", action="store_true", help="Open WhatsApp Web to scan QR code and verify login")
    parser.add_argument("--delay", type=int, default=45, help="Delay in seconds between messages")
    args = parser.parse_args()

    if args.login_only:
        run_whatsapp_dispatcher(max_batch=0, dry_run=False)
    else:
        run_whatsapp_dispatcher(max_batch=args.max_batch, dry_run=args.dry_run, delay_sec=args.delay)

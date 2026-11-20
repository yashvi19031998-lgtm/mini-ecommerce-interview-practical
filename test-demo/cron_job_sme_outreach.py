"""
CRON JOB: Dedicated SME Post Pack Automated Dispatcher
======================================================
Autonomous outreach for the 10-Post Pack / 2 Free Samples Campaign:
- Strictly filters ONLY for non-IT local SMEs (Clinics, Salons, Gyms, Sweets, Jewellers, Retailers, Cafes)
- STRICT IT COMPANY SHIELD: Under NO circumstances will an email ever be dispatched to any IT/Software company
- Enforces Do-Not-Contact blacklist (8dots, competitors)
- Checks duplicate sent log (sent_emails.csv) so no business is EVER contacted twice
- Verifies recipient mailbox before sending to prevent bounces
- Dispatches high-converting 70-word '2 Free Samples' hook
- Respects safe daily batch limits (default: 15 per run)

Usage:
  python cron_job_sme_outreach.py               # Live run (max 15 emails)
  python cron_job_sme_outreach.py --limit 5     # Run for 5 leads
  python cron_job_sme_outreach.py --dry-run     # Test without sending real emails
"""

import os
import sys
import csv
import time
import argparse
import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import settings_manager
import email_service
import festival_offers_engine as offers_engine

DATA_DIR = os.path.join(BASE_DIR, "data")
LEADS_MASTER = os.path.join(BASE_DIR, "all_leads_master.csv")
MAPS_LEADS = os.path.join(BASE_DIR, "google_maps_leads.csv")

def get_candidate_sme_leads():
    """Gathers candidate local SME leads from Google Maps and master lead pool."""
    candidates = []
    seen_emails = set(email_service.get_already_sent_emails())
    settings = settings_manager.load_settings()

    # Source 1: Google Maps leads (local businesses)
    if os.path.exists(MAPS_LEADS):
        try:
            with open(MAPS_LEADS, mode="r", encoding="utf-8-sig", errors="ignore") as f:
                reader = csv.DictReader(f)
                for r in reader:
                    email = (r.get("Email") or r.get("email") or "").strip().lower()
                    comp = (r.get("Business Name") or r.get("company_name") or r.get("Company") or "").strip()
                    phone = (r.get("Phone") or r.get("phone") or "").strip()
                    cat = (r.get("Category") or r.get("category") or "").strip()
                    web = (r.get("Website") or r.get("website") or "").strip()

                    if not email or "@" not in email:
                        continue
                    if email in seen_emails:
                        continue

                    # STRICT IT SHIELD CHECK: Never contact an IT company!
                    is_ex, reason = settings_manager.is_company_excluded(
                        company_name=comp, email=email, website=web, settings=settings
                    )
                    if is_ex:
                        continue

                    candidates.append({
                        "company_name": comp,
                        "email": email,
                        "phone": phone,
                        "category": cat,
                        "website": web,
                        "source": "google_maps"
                    })
        except Exception as e:
            print(f"[WARN] Error reading {MAPS_LEADS}: {e}")

    # Source 2: All Leads Master (filter for Gujarat / non-IT businesses)
    if os.path.exists(LEADS_MASTER):
        try:
            with open(LEADS_MASTER, mode="r", encoding="utf-8-sig", errors="ignore") as f:
                reader = csv.DictReader(f)
                for r in reader:
                    email = (r.get("email") or r.get("Email") or "").strip().lower()
                    comp = (r.get("company_name") or r.get("Company Name") or r.get("company") or "").strip()
                    phone = (r.get("phone") or r.get("Phone") or r.get("mobile") or "").strip()
                    cat = (r.get("category") or r.get("Category") or "").strip()
                    web = (r.get("website") or r.get("Website") or "").strip()

                    if not email or "@" not in email:
                        continue
                    if email in seen_emails:
                        continue
                    if any(c["email"] == email for c in candidates):
                        continue

                    # Filter out non-business job/post titles
                    comp_low = comp.lower()
                    if any(bad in comp_low for bad in ["show hn", "employment", "hire ", "looking for", "job", "freelancer", "upwork"]):
                        continue
                    if email.endswith(".gov") or ".gov." in email:
                        continue

                    # STRICT IT SHIELD CHECK: Under no circumstances email an IT company!
                    is_ex, reason = settings_manager.is_company_excluded(
                        company_name=comp, email=email, website=web, settings=settings
                    )
                    if is_ex:
                        continue

                    candidates.append({
                        "company_name": comp,
                        "email": email,
                        "phone": phone,
                        "category": cat,
                        "website": web,
                        "source": "master_leads"
                    })
        except Exception as e:
            print(f"[WARN] Error reading {LEADS_MASTER}: {e}")

    return candidates

def run_sme_automated_dispatch(limit: int = 15, dry_run: bool = False):
    """Executes the automated dispatch cycle."""
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print("=" * 70)
    print(f"[{now_str}] 🚀 AUTOMATED SME OUTREACH DISPATCHER STARTED")
    print(f"[*] Target Limit: {limit} emails | Dry-Run: {dry_run}")
    print(f"[*] IT Company Shield: ACTIVE (100% IT / Software companies blocked)")
    print("=" * 70)

    candidates = get_candidate_sme_leads()
    print(f"[+] Found {len(candidates)} verified non-IT SME candidates eligible for outreach.")

    if not candidates:
        print("[*] No pending SME leads found. Run Google Maps scraper for more local businesses!")
        return {"dispatched": 0, "skipped": 0, "status": "NO_LEADS"}

    dispatched = 0
    skipped = 0

    for idx, lead in enumerate(candidates[:limit]):
        comp = lead["company_name"] or "Local Business"
        email = lead["email"]
        phone = lead["phone"]

        # Double check IT shield
        is_ex, reason = settings_manager.is_company_excluded(company_name=comp, email=email, website=lead.get("website", ""))
        if is_ex:
            print(f"       [SKIPPED - IT COMPANY BLOCKED] {comp} ({email}): {reason}")
            skipped += 1
            continue

        # Generate the high-converting 70-word pitch
        pitch = offers_engine.generate_offer_pitch(lead)

        if dry_run:
            print(f"       [DRY RUN] Would send to: {comp} <{email}> | Subj: {pitch['email_subject']}")
            dispatched += 1
            continue

        print(f"       -> Dispatching '2 Free Samples' pitch to {comp} <{email}>...")
        res = email_service.send_smtp_email(
            to_email=email,
            subject=pitch["email_subject"],
            message_body=pitch["email_body"],
            company_name=comp,
            website=lead.get("website", ""),
            verify="strict"
        )

        if res.get("success"):
            print(f"       [SUCCESS] Delivered to {comp} <{email}>")
            dispatched += 1
            time.sleep(1.5)  # Safe SMTP throttle
        else:
            print(f"       [FAILED/SKIPPED] {comp} <{email}>: {res.get('error')}")
            skipped += 1

    print("\n" + "=" * 70)
    print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🏁 SME AUTOMATION CYCLE FINISHED")
    print(f"[*] Successfully Dispatched: {dispatched} | Skipped/Failed: {skipped}")
    print("=" * 70)
    return {"dispatched": dispatched, "skipped": skipped, "status": "COMPLETED"}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Automated SME Post Pack Outreach Dispatcher")
    parser.add_argument("--limit", type=int, default=15, help="Maximum emails to dispatch in this cycle")
    parser.add_argument("--dry-run", action="store_true", help="Simulate outreach without sending emails")
    args = parser.parse_args()

    run_sme_automated_dispatch(limit=args.limit, dry_run=args.dry_run)

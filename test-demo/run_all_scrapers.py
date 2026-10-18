"""
Common Lead Generation Master Runner
====================================
The single entry point coordinating all 10 existing lead scrapers,
enforcing incremental updates, preserving previous leads, executing safe writes,
preventing duplicate records, and recording execution history in logs/scraper_runs.csv.
"""

import os
import sys
import csv
import time
import uuid
import datetime
from typing import Dict, Any, List

from lead_normalizer import MasterLeadRegistry, MASTER_FIELDNAMES
import scraper_adapters

# Auto-Outreach & Supabase Sync integration
try:
    from email_service import send_smtp_email
    from settings_manager import load_settings, format_signature
except ImportError:
    send_smtp_email = None
    load_settings = None
    format_signature = None

try:
    import sync_to_supabase
except ImportError:
    sync_to_supabase = None

AUTO_SEND_EMAIL = os.getenv("AUTO_SEND_EMAIL", "false").lower() in ("true", "1", "yes")  # Disabled by default for safety!
AUTO_SYNC_SUPABASE = os.getenv("AUTO_SYNC_SUPABASE", "true").lower() in ("true", "1", "yes")
MAX_PENDING_EMAILS_PER_RUN = int(os.getenv("MAX_PENDING_EMAILS_PER_RUN", "0"))  # Disabled by default

MASTER_CSV = "all_leads_master.csv"
RUNS_LOG_CSV = os.path.join("logs", "scraper_runs.csv")
LOCK_FILE = ".scraper_runner.lock"

# List of all 12 scrapers to coordinate
SCRAPERS_CONFIG = [
    {
        "name": "scraper.py (Search Engine IT Hiring Scraper)",
        "func": scraper_adapters.run_scraper_adapter,
        "enabled": True,
        "category": "Search & Web Deep Crawl"
    },
    {
        "name": "lead_generation_master.py (RSS & Playwright Justdial Engine)",
        "func": scraper_adapters.run_lead_generation_master_adapter,
        "enabled": True,
        "category": "Multi-Source Harvester"
    },
    {
        "name": "direct_feed_csv.py (Reddit r/forhire Live Feed)",
        "func": scraper_adapters.run_direct_feed_csv_adapter,
        "enabled": True,
        "category": "RSS Feed"
    },
    {
        "name": "direct_feed_testing_2.py (Reddit, WWR & Remotive Feeds)",
        "func": scraper_adapters.run_direct_feed_testing_2_adapter,
        "enabled": True,
        "category": "Multi-RSS Aggregator"
    },
    {
        "name": "instant_lead_generator.py (Reddit & HN Algolia REST API)",
        "func": scraper_adapters.run_instant_lead_generator_adapter,
        "enabled": True,
        "category": "REST API"
    },
    {
        "name": "ddgs_bulk_scraper.py (DuckDuckGo Dorks Harvester)",
        "func": scraper_adapters.run_ddgs_bulk_scraper_adapter,
        "enabled": True,
        "category": "Search Dorks"
    },
    {
        "name": "b2b_portal_scraper.py (B2B Portals IndiaMART & TradeIndia)",
        "func": scraper_adapters.run_b2b_portal_scraper_adapter,
        "enabled": True,
        "category": "B2B Directory"
    },
    {
        "name": "freelance_reddit_scraper.py (Multi-Platform Dork Scraper)",
        "func": scraper_adapters.run_freelance_reddit_scraper_adapter,
        "enabled": True,
        "category": "Platform Search"
    },
    {
        "name": "linkedin_scraper.py (LinkedIn Company Search Discovery)",
        "func": scraper_adapters.run_linkedin_scraper_adapter,
        "enabled": True,
        "category": "LinkedIn Discovery"
    },
    {
        "name": "reddit_rss_scraper.py (Multi-Subreddit Filtered RSS)",
        "func": scraper_adapters.run_reddit_rss_scraper_adapter,
        "enabled": True,
        "category": "Subreddit RSS"
    },
    {
        "name": "google_maps_scraper.py (Google Maps Playwright Local Business Engine)",
        "func": scraper_adapters.run_google_maps_scraper_adapter,
        "enabled": True,
        "category": "Google Maps Playwright"
    },
    {
        "name": "telegram_scraper.py (Telegram Client Hiring & Freelance Channels)",
        "func": scraper_adapters.run_telegram_scraper_adapter,
        "enabled": True,
        "category": "Telegram Channels"
    },
]


def ensure_logs_directory():
    """Ensures logs directory and headers exist."""
    os.makedirs("logs", exist_ok=True)
    if not os.path.exists(RUNS_LOG_CSV):
        with open(RUNS_LOG_CSV, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "run_id",
                "start_time",
                "end_time",
                "scraper_name",
                "status",
                "records_collected",
                "new_leads_added",
                "existing_leads_updated",
                "duplicates_detected",
                "error_summary"
            ])


def log_scraper_run(run_id: str, start_time: str, end_time: str, scraper_name: str,
                    status: str, records: int, added: int, updated: int,
                    duplicates: int, error_summary: str = ""):
    """Appends scraper run telemetry to logs/scraper_runs.csv."""
    ensure_logs_directory()
    try:
        with open(RUNS_LOG_CSV, mode="a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                run_id,
                start_time,
                end_time,
                scraper_name,
                status,
                records,
                added,
                updated,
                duplicates,
                error_summary.replace("\n", " ").replace(",", " ")[:200]
            ])
    except Exception as e:
        print(f"[WARN] Failed to write run log: {e}")


def acquire_run_lock() -> bool:
    """Creates a lock file to prevent overlapping simultaneous runs."""
    if os.path.exists(LOCK_FILE):
        try:
            # Check if stale (older than 15 minutes)
            mtime = os.path.getmtime(LOCK_FILE)
            if time.time() - mtime > 900:
                os.remove(LOCK_FILE)
            else:
                return False
        except Exception:
            return False

    try:
        with open(LOCK_FILE, mode="w") as f:
            f.write(str(os.getpid()))
        return True
    except Exception:
        return False


def release_run_lock():
    """Removes the run lock file."""
    if os.path.exists(LOCK_FILE):
        try:
            os.remove(LOCK_FILE)
        except Exception:
            pass


def dispatch_pending_outreach_emails(registry: MasterLeadRegistry, max_batch: int = 0, delay_sec: float = 2.0) -> int:
    """
    Scans the master registry for leads that have not received outreach emails yet
    (email_status != 'SENT'), cross-references with permanent sent history and blacklist domains,
    and dispatches personalized outreach emails in controlled batches.
    """
    if not AUTO_SEND_EMAIL or not send_smtp_email or max_batch <= 0:
        print("       [AUTO-MAIL-PENDING] Auto-email dispatch is disabled for safety. Use Dashboard UI to send outreach emails.")
        return 0

    settings = load_settings() if load_settings else {}
    sig = format_signature(settings) if format_signature else ""

    sub_tpl = settings.get("defaultSubject", "Web & Software Engineering Collaboration - {company}")
    msg_tpl = settings.get("defaultMessage", "Hi {name},\n\nI came across {company}...")

    # Load permanent sent history from email_service
    sent_emails_seen = set()
    try:
        from email_service import get_already_sent_emails
        sent_emails_seen.update(get_already_sent_emails())
    except Exception:
        pass
    if os.path.exists("leads_new.csv"):
        try:
            import pandas as pd
            df_new = pd.read_csv("leads_new.csv")
            if "Email Status" in df_new.columns and "Email" in df_new.columns:
                sent_leads = df_new[df_new["Email Status"] == "SENT"]["Email"].dropna()
                for em_str in sent_leads:
                    for em in str(em_str).split(","):
                        e_clean = em.strip().lower()
                        if e_clean:
                            sent_emails_seen.add(e_clean)
        except Exception as e:
            pass

    # Also record emails already marked SENT in registry.leads
    for l in registry.leads:
        if str(l.get("email_status", "")).strip().upper() == "SENT":
            for em in str(l.get("email", "")).split(","):
                e_clean = em.strip().lower()
                if e_clean:
                    sent_emails_seen.add(e_clean)

    dispatched = 0
    from lead_normalizer import EMAIL_BLACKLIST_DOMAINS

    for lead_obj in registry.leads:
        if dispatched >= max_batch:
            break

        status = str(lead_obj.get("email_status", "")).strip().upper()
        if status == "SENT":
            continue

        raw_emails = str(lead_obj.get("email", "")).split(",")
        raw_email = raw_emails[0].strip() if raw_emails else ""

        if not raw_email or "@" not in raw_email or raw_email.upper() in ("N/A", "NONE"):
            continue

        email_lower = raw_email.lower()
        if email_lower in sent_emails_seen:
            # Already received email previously, update status to avoid retry
            lead_obj["email_status"] = "SENT"
            continue

        domain_part = email_lower.split("@")[-1]
        if domain_part in EMAIL_BLACKLIST_DOMAINS or "ingest" in domain_part or "sentry" in domain_part:
            lead_obj["email_status"] = "INVALID"
            continue

        comp_name = lead_obj.get("company_name") or lead_obj.get("full_name") or "your company"
        loc_name = lead_obj.get("location") or "your region"

        custom_sub = sub_tpl.replace("{company}", comp_name).replace("{name}", comp_name).replace("{location}", loc_name)
        custom_msg = msg_tpl.replace("{company}", comp_name).replace("{name}", comp_name).replace("{location}", loc_name)

        if sig and sig.strip()[:20] not in custom_msg:
            custom_msg = f"{custom_msg}\n\n---\n{sig.strip()}"

        print(f"       -> [AUTO-MAIL-PENDING] Dispatching outreach to {raw_email} ({comp_name})...")
        mail_res = send_smtp_email(raw_email, custom_sub, custom_msg)
        if mail_res.get("success"):
            lead_obj["email_status"] = "SENT"
            lead_obj["email_sent_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            sent_emails_seen.add(email_lower)
            print(f"       -> [AUTO-MAIL-PENDING] [SUCCESS] Delivered via Gmail SMTP.")
            dispatched += 1
            if delay_sec > 0:
                time.sleep(delay_sec)
        else:
            lead_obj["email_status"] = "FAILED"
            print(f"       -> [AUTO-MAIL-PENDING] [FAILED] {mail_res.get('error')}")

    return dispatched


def run_all_scrapers():
    """Main orchestration workflow."""
    if not acquire_run_lock():
        print("[ERROR] Another instance of run_all_scrapers.py is already running. Exiting.")
        sys.exit(1)

    overall_start = datetime.datetime.now()
    run_id = f"RUN-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"

    print("=" * 65)
    print("       COMMON UNIFIED LEAD GENERATION SYSTEM")
    print("=" * 65)
    print(f"Run ID:            {run_id}")
    print(f"Start Time:        {overall_start.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Master Target:     {os.path.abspath(MASTER_CSV)}")
    print("=" * 65 + "\n")

    # Step 1: Load Existing Master Leads
    registry = MasterLeadRegistry(MASTER_CSV)
    initial_lead_count = len(registry.leads)
    print(f"[*] Step 1: Loaded existing master database with {initial_lead_count} unique leads.\n")

    # Metrics
    scrapers_configured = len(SCRAPERS_CONFIG)
    scrapers_executed = 0
    scrapers_successful = 0
    scrapers_failed = 0

    total_raw_collected = 0
    total_invalid_skipped = 0
    total_duplicates_detected = 0
    total_leads_updated = 0
    total_new_leads_added = 0

    print("[*] Step 2: Executing all configured scrapers independently...\n")

    # Step 2: Run all scrapers independently
    for idx, config in enumerate(SCRAPERS_CONFIG, start=1):
        name = config["name"]
        func = config["func"]
        enabled = config["enabled"]

        if not enabled:
            print(f"[{idx:02d}/{scrapers_configured:02d}] [SKIPPED]  {name} (Disabled in config)")
            continue

        scrapers_executed += 1
        s_start = datetime.datetime.now()
        s_start_str = s_start.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{idx:02d}/{scrapers_configured:02d}] [RUNNING]  {name}...")

        scraper_raw_records = []
        status = "Success"
        error_msg = ""

        try:
            scraper_raw_records = func()
            scrapers_successful += 1
        except Exception as e:
            status = "Failed"
            error_msg = str(e)
            scrapers_failed += 1
            print(f"       -> [ERROR] Failed: {e}")

        s_end = datetime.datetime.now()
        s_end_str = s_end.strftime("%Y-%m-%d %H:%M:%S")

        # Step 3: Normalize and Merge Leads for this scraper
        s_added = 0
        s_updated = 0
        s_duplicates = 0
        s_invalid = 0

        # Load outreach signature & templates
        settings = load_settings() if load_settings else {}
        sig = format_signature(settings) if format_signature else ""
        sub_tpl = settings.get("defaultSubject", "Web & Software Engineering Collaboration - {company}")
        msg_tpl = settings.get("defaultMessage", "Hi {name},\n\nI came across {company} and your business...")

        for raw_lead in scraper_raw_records:
            total_raw_collected += 1
            outcome, lead_obj = registry.add_lead(raw_lead, default_source=name)

            if outcome == "added":
                s_added += 1
                total_new_leads_added += 1

                # Direct Auto Outreach Email Dispatch
                if AUTO_SEND_EMAIL and send_smtp_email and isinstance(lead_obj, dict):
                    raw_email = str(lead_obj.get("email", "")).split(",")[0].strip()
                    if raw_email and raw_email != "N/A" and "@" in raw_email:
                        comp_name = lead_obj.get("company_name") or lead_obj.get("full_name") or "your company"
                        loc_name = lead_obj.get("location") or "your region"

                        custom_sub = sub_tpl.replace("{company}", comp_name).replace("{name}", comp_name).replace("{location}", loc_name)
                        custom_msg = msg_tpl.replace("{company}", comp_name).replace("{name}", comp_name).replace("{location}", loc_name)

                        if sig and sig.strip()[:20] not in custom_msg:
                            custom_msg = f"{custom_msg}\n\n---\n{sig.strip()}"

                        print(f"       -> [AUTO-MAIL] Dispatching outreach to {raw_email} ({comp_name})...")
                        mail_res = send_smtp_email(raw_email, custom_sub, custom_msg)
                        if mail_res.get("success"):
                            lead_obj["email_status"] = "SENT"
                            lead_obj["email_sent_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            print(f"       -> [AUTO-MAIL] [SUCCESS] Delivered via Gmail SMTP.")
                        else:
                            lead_obj["email_status"] = "FAILED"
                            print(f"       -> [AUTO-MAIL] [FAILED] {mail_res.get('error')}")

            elif outcome == "updated":
                s_updated += 1
                total_leads_updated += 1
            elif outcome == "duplicate":
                s_duplicates += 1
                total_duplicates_detected += 1
            else:
                s_invalid += 1
                total_invalid_skipped += 1

        print(f"       -> [RESULT] Status: {status} | Harvested: {len(scraper_raw_records)} | New: {s_added} | Enriched: {s_updated} | Dups: {s_duplicates}")

        # Step 4: Record history in logs/scraper_runs.csv
        log_scraper_run(
            run_id=run_id,
            start_time=s_start_str,
            end_time=s_end_str,
            scraper_name=name,
            status=status,
            records=len(scraper_raw_records),
            added=s_added,
            updated=s_updated,
            duplicates=s_duplicates,
            error_summary=error_msg
        )

    # Step 2b: Dispatch Outreach to Backlog of Pending Leads (NOT_SENT / FAILED)
    if AUTO_SEND_EMAIL and send_smtp_email and MAX_PENDING_EMAILS_PER_RUN > 0:
        print(f"\n[*] Step 2b: Checking backlog for pending outreach emails (Batch limit: {MAX_PENDING_EMAILS_PER_RUN})...")
        pending_sent = dispatch_pending_outreach_emails(registry, max_batch=MAX_PENDING_EMAILS_PER_RUN)
        if pending_sent > 0:
            print(f"[*] [OK] Successfully dispatched {pending_sent} pending outreach emails!")
        else:
            print("[*] No pending uncontacted leads required outreach at this time.")

    # Step 5: Save Master Database Safely
    print("\n[*] Step 3: Performing safe atomic commit to master database...")
    save_ok = registry.save_master_safely()
    if save_ok:
        print(f"[*] [OK] Successfully written to '{MASTER_CSV}'.")
    else:
        print(f"[FATAL] Failed to write to '{MASTER_CSV}'!")

    # Step 5a: Deep Website Contact Enrichment
    try:
        import website_contact_extractor
        print("\n[*] Step 4: Running Deep Website Contact Extractor on leads with missing email/phone...")
        enriched_leads_count = website_contact_extractor.run_website_enrichment(master_csv_path=MASTER_CSV)
        total_leads_updated += enriched_leads_count
    except Exception as e:
        print(f"[WARN] Website Contact Extractor notice: {e}")

    # Step 5b: Direct Sync to Supabase Database
    if AUTO_SYNC_SUPABASE and sync_to_supabase:
        print("\n[*] Step 5: Syncing all leads directly to Supabase Database...")
        try:
            sync_to_supabase.sync(csv_filepath=MASTER_CSV)
            print("[*] [OK] Supabase cloud database sync complete!")
        except Exception as e:
            print(f"[WARN] Supabase sync notice: {e}")

    final_lead_count = len(registry.leads)
    overall_end = datetime.datetime.now()
    duration = (overall_end - overall_start).total_seconds()

    # Step 6: Console Summary Report
    print("\n" + "=" * 65)
    print("       COMMON LEAD GENERATION SYSTEM SUMMARY")
    print("=" * 65)
    print(f"Scrapers configured:              {scrapers_configured}")
    print(f"Scrapers executed:                {scrapers_executed}")
    print(f"Scrapers successful:              {scrapers_successful}")
    print(f"Scrapers failed:                  {scrapers_failed}")
    print("-" * 65)
    print(f"Previous master leads:            {initial_lead_count}")
    print(f"Raw records collected:            {total_raw_collected}")
    print(f"Invalid records skipped:          {total_invalid_skipped}")
    print(f"Duplicate records detected:       {total_duplicates_detected}")
    print(f"Existing leads enriched/updated:  {total_leads_updated}")
    print(f"Genuinely new leads added:        {total_new_leads_added}")
    print(f"Total unique leads in master CSV: {final_lead_count}")
    print("-" * 65)
    print(f"Total execution time:             {duration:.2f} seconds")
    print(f"Master file:                      {MASTER_CSV}")
    print(f"Run log file:                     {RUNS_LOG_CSV}")
    print("=" * 65 + "\n")

    release_run_lock()


if __name__ == "__main__":
    try:
        run_all_scrapers()
    except Exception as e:
        print(f"[FATAL UNHANDLED ERROR] {e}")
        release_run_lock()

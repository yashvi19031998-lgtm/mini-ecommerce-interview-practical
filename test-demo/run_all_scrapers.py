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

try:
    import lead_quality
    from lead_quality import is_outreach_ready
except ImportError:
    lead_quality = None
    is_outreach_ready = lambda lead: False  # without the quality module, never auto-email

try:
    _loaded_s = load_settings() if load_settings else {}
except Exception:
    _loaded_s = {}

_env_auto_email = os.getenv("AUTO_SEND_EMAIL")
if _env_auto_email is not None:
    AUTO_SEND_EMAIL = _env_auto_email.lower() in ("true", "1", "yes")
else:
    AUTO_SEND_EMAIL = bool(_loaded_s.get("auto_send_email", True))

AUTO_SYNC_SUPABASE = os.getenv("AUTO_SYNC_SUPABASE", "true").lower() in ("true", "1", "yes")
MAX_PENDING_EMAILS_PER_RUN = int(os.getenv("MAX_PENDING_EMAILS_PER_RUN", "10"))  # Batch of leads per run

MASTER_CSV = "all_leads_master.csv"
RUNS_LOG_CSV = os.path.join("logs", "scraper_runs.csv")
LOCK_FILE = ".scraper_runner.lock"

# List of all 12 scrapers to coordinate
import feedly_scraper
import intent_feeds
import hn_hiring_scraper
import freelancer_api_scraper
import apollo_enricher
from email_checks import can_receive_mail
import followup_store


def run_apollo_prospect_adapter() -> List[Dict[str, Any]]:
    """Adapter for Apollo.io B2B Prospect Search."""
    keywords = os.getenv("APOLLO_SEARCH_KEYWORDS", "").strip()
    api_key = os.getenv("APOLLO_API_KEY", "").strip()
    if not keywords or not api_key:
        return []
    locs_raw = os.getenv("APOLLO_SEARCH_LOCATIONS", "United States,United Kingdom,Canada,Australia,India")
    locs = [l.strip() for l in locs_raw.split(",") if l.strip()]
    return apollo_enricher.search_apollo_prospects(keywords=keywords, locations=locs, per_page=15)

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
    {
        "name": "feedly_scraper.py (Feedly API / RSS feeds from Feedly OPML)",
        "func": feedly_scraper.run_feedly_adapter,
        "enabled": True,
        "category": "Feeds"
    },
    {
        "name": "intent_feeds.py (Reddit buyer search, founder subreddits, funding news)",
        "func": intent_feeds.run_intent_feeds_adapter,
        "enabled": True,
        "category": "Feeds"
    },
    {
        "name": "hn_hiring_scraper.py (HN 'Who is hiring?' contract/freelance posts)",
        "func": hn_hiring_scraper.run_hn_hiring_adapter,
        "enabled": True,
        "category": "Hiring Threads"
    },
    {
        "name": "freelancer_api_scraper.py (Freelancer.com live projects, official API)",
        "func": freelancer_api_scraper.run_freelancer_adapter,
        "enabled": True,
        "category": "Freelance Marketplaces"
    },
    {
        "name": "apollo_enricher.py (Apollo.io Verified B2B Prospect Harvester)",
        "func": run_apollo_prospect_adapter,
        "enabled": bool(os.getenv("APOLLO_SEARCH_KEYWORDS", "").strip() and os.getenv("APOLLO_API_KEY", "").strip()),
        "category": "B2B Intelligence"
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


def dispatch_pending_outreach_emails(registry: MasterLeadRegistry, max_batch: int = 5, delay_sec: float = 2.0) -> int:
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
        if status in ("SENT", "INVALID", "INVALID_DOMAIN"):
            continue

        # Only contact leads the AI qualified as real buyers with a high score
        if not is_outreach_ready(lead_obj):
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

        # Domain must have a mail server, otherwise the email bounces and hurts our Gmail reputation
        if not can_receive_mail(raw_email):
            print(f"       -> [AUTO-MAIL-PENDING] Skipping {raw_email}: domain has no mail server")
            lead_obj["email_status"] = "INVALID_DOMAIN"
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
            followup_store.safe_log(lead_obj.get("lead_id", ""), "email_sent", f"Email sent: {custom_sub}",
                                    details=custom_msg, source="auto outreach", lead_name=comp_name,
                                    lead_email=raw_email)
            print(f"       -> [AUTO-MAIL-PENDING] [SUCCESS] Delivered via Gmail SMTP.")
            dispatched += 1
            if delay_sec > 0:
                time.sleep(delay_sec)
        else:
            lead_obj["email_status"] = "FAILED"
            print(f"       -> [AUTO-MAIL-PENDING] [FAILED] {mail_res.get('error')}")

    return dispatched


REPLY_UPGRADEABLE = {"", "NEW", "CONTACTED", "EMAIL_SENT"}


def run_followup_step(registry: MasterLeadRegistry) -> None:
    """Reply check (if Gmail IMAP is configured) and follow-up sequence (auto-send only if enabled)."""
    import followup_sequence
    import reply_checker

    registry.load_master()
    by_id = {l.get("lead_id"): l for l in registry.leads}
    changed = False

    if reply_checker.is_configured():
        print("\n[*] Step 5a: Checking Gmail for replies, bounces and opt-outs...")
        email_to_lead = {}
        for l in registry.leads:
            for em in str(l.get("email", "")).split(","):
                em = em.strip().lower()
                if em:
                    email_to_lead.setdefault(em, {"id": l.get("lead_id", ""), "name": l.get("company_name", "")})
        events = reply_checker.fetch_events(reply_checker.contacted_emails())
        result = reply_checker.record_events(events, email_to_lead)
        for u in result["updates"]:
            lead = by_id.get(u["lead_id"])
            if not lead:
                continue
            if u.get("status") and str(lead.get("status", "")).upper() in REPLY_UPGRADEABLE:
                followup_store.safe_log(u["lead_id"], "status_change",
                                        f"Status: {str(lead.get('status') or 'NEW').upper()} → {u['status']}",
                                        source="gmail", lead_name=lead.get("company_name", ""))
                lead["status"] = u["status"]
                changed = True
            if u.get("email_status"):
                lead["email_status"] = u["email_status"]
                changed = True
        print(f"[*] Gmail: {result['logged']} new replies/bounces/opt-outs logged.")
    else:
        print("\n[*] Step 5a: Gmail reply check not configured (IMAP_USER / IMAP_PASSWORD) - skipped.")

    cfg = followup_sequence.config()
    leads_index = {l.get("lead_id"): {"name": l.get("company_name", ""), "status": l.get("status", ""),
                                      "email": str(l.get("email", "")).split(",")[0].strip()}
                   for l in registry.leads if l.get("lead_id")}
    due = followup_sequence.plan(leads_index)["due"]
    if not cfg["auto_send"]:
        print(f"[*] Follow-up sequence: {len(due)} due (auto-send OFF - send them from the dashboard).")
    elif due and send_smtp_email:
        sig = format_signature(load_settings()) if (format_signature and load_settings) else ""
        res = followup_sequence.send(
            due, lambda to, sub, body: send_smtp_email(to, sub, body, bypass_duplicate_check=True),
            signature=sig, limit=cfg["max_per_run"])
        print(f"[*] Follow-up sequence: sent {res['sent']}, failed {res['failed']} (limit {cfg['max_per_run']}).")

    if changed and not registry.save_master_safely():
        print(f"[FATAL] Failed to save reply statuses to '{MASTER_CSV}'!")


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

                # Outreach happens later (Step 5), only after enrichment + AI qualification.

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

    # Step 3: Save Master Database Safely
    print("\n[*] Step 3: Performing safe atomic commit to master database...")
    save_ok = registry.save_master_safely()
    if save_ok:
        print(f"[*] [OK] Successfully written to '{MASTER_CSV}'.")
    else:
        print(f"[FATAL] Failed to write to '{MASTER_CSV}'!")

    # Step 4a: Deep Website Contact Enrichment
    try:
        import website_contact_extractor
        print("\n[*] Step 4a: Running Deep Website Contact Extractor on leads with missing email/phone...")
        enriched_leads_count = website_contact_extractor.run_website_enrichment(master_csv_path=MASTER_CSV)
        total_leads_updated += enriched_leads_count
    except Exception as e:
        print(f"[WARN] Website Contact Extractor notice: {e}")

    # Step 4a.2: Apollo.io Decision Maker & Contact Enrichment
    try:
        if os.getenv("APOLLO_API_KEY", "").strip():
            print("\n[*] Step 4a.2: Running Apollo.io Decision Maker Contact Enrichment...")
            apollo_count = apollo_enricher.run_apollo_enrichment(master_csv_path=MASTER_CSV)
            total_leads_updated += apollo_count
    except Exception as e:
        print(f"[WARN] Apollo Enrichment notice: {e}")

    # Step 4b: Cleanup + AI qualification
    if lead_quality:
        print("\n[*] Step 4b: Cleaning leads and running AI qualification...")
        try:
            lead_quality.run(MASTER_CSV)
        except Exception as e:
            print(f"[WARN] Lead quality step notice: {e}")

    # Step 5: Outreach to qualified leads only (reload: steps 4a/4b rewrote the CSV)
    if AUTO_SEND_EMAIL and send_smtp_email and MAX_PENDING_EMAILS_PER_RUN > 0:
        registry.load_master()
        print(f"\n[*] Step 5: Emailing AI-qualified leads (batch limit: {MAX_PENDING_EMAILS_PER_RUN})...")
        pending_sent = dispatch_pending_outreach_emails(registry, max_batch=MAX_PENDING_EMAILS_PER_RUN)
        print(f"[*] Outreach emails sent this run: {pending_sent}")
        if not registry.save_master_safely():
            print(f"[FATAL] Failed to save email statuses to '{MASTER_CSV}'!")

    # Step 5a: Follow-ups - Gmail reply check, then (only if FOLLOWUP_AUTO_SEND=true) due sequence emails
    try:
        run_followup_step(registry)
    except Exception as e:  # never let follow-ups break the scraper run
        print(f"[WARN] Follow-up step notice: {e}")

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

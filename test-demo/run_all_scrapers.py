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

_initial_settings = load_settings() if load_settings else {}
# AUTO_SEND_EMAIL=false (env / workflow variable) is a hard off switch; otherwise the Settings toggle decides.
try:
    from settings_manager import auto_send_state
    AUTO_SEND_EMAIL = auto_send_state(_initial_settings)[0]
except ImportError:
    AUTO_SEND_EMAIL = os.getenv("AUTO_SEND_EMAIL", "false").lower() in ("true", "1", "yes")
AUTO_SYNC_SUPABASE = os.getenv("AUTO_SYNC_SUPABASE", "true").lower() in ("true", "1", "yes")
# Intro e-mails per run. 0 = no per-run limit: every qualified lead found is e-mailed (still subject to
# the daily cap below). Settings decides; the MAX_PENDING_EMAILS_PER_RUN variable only applies when the
# setting is missing (e.g. a fresh install).
def _int_or(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


_per_run_setting = _initial_settings.get("maxPendingEmailsPerRun")
MAX_PENDING_EMAILS_PER_RUN = max(0, _int_or(
    _per_run_setting if _per_run_setting not in (None, "") else os.getenv("MAX_PENDING_EMAILS_PER_RUN"), 5))
# Gmail suspends sending for ~24 h above about 500 recipients a day (free accounts). Stay well below it,
# counting every mail the app sent today (manual, bulk, follow-ups and this run).
# 2026-11-13: two Gmail accounts were blocked, so the default is low; raise it slowly as the account ages.
MAX_EMAILS_PER_DAY = max(1, _int_or(os.getenv("MAX_EMAILS_PER_DAY"), 50))
# Prospects (companies with no request yet, AUTO_EMAIL_PROSPECT_SIGNALS=true) get their own, smaller daily
# limit inside MAX_EMAILS_PER_DAY, and are e-mailed only after every ready real buyer.
MAX_PROSPECT_EMAILS_PER_DAY = max(0, _int_or(os.getenv("MAX_PROSPECT_EMAILS_PER_DAY"), 15))
PROSPECT_SOURCE = "auto outreach (prospect)"
# Short intro for prospects, used when the AI e-mail writer is not available.
PROSPECT_SUBJECT = "Software help for {company}"
PROSPECT_MESSAGE = ("Hi {name},\n\n"
                    "I came across {company} and wanted to introduce Sangeeta Infotech, a software team from "
                    "Ahmedabad. We build and look after websites, web apps, mobile apps and online stores, and we "
                    "also work as an extra development team when in-house capacity is short.\n\n"
                    "If anything like that is on your list for the coming months, would a short call be useful? "
                    "If not, just let me know and I will not write again.")


def prospect_emails_sent_today(now=None) -> int:
    """Prospect intro e-mails sent today (follow-up log, source PROSPECT_SOURCE)."""
    today = (now or datetime.datetime.now()).strftime("%Y-%m-%d")
    try:
        rows = followup_store.history(types=["email_sent"], limit=1000)["items"]
    except Exception:
        return 0
    return sum(1 for r in rows if r.get("source") == PROSPECT_SOURCE and str(r.get("occurred_at", "")).startswith(today))
# Pause automatic e-mail when this many bounces ("Address not found") came back in the last 24 hours.
MAX_BOUNCES_PER_DAY = 2
# Stop the run's e-mailing after this many failures in a row (wrong password, Gmail block...): retrying
# every lead only hammers Gmail and marks good leads FAILED.
MAX_CONSECUTIVE_SEND_FAILURES = 3


def bounces_last_24h(now=None) -> int:
    """Bounces recorded by the Gmail reply check (followup_store) in the last 24 hours."""
    now = now or datetime.datetime.now()
    try:
        rows = followup_store.history(types=["bounce"], limit=500)["items"]
    except Exception:
        return 0
    n = 0
    for r in rows:
        try:
            when = datetime.datetime.strptime(str(r.get("occurred_at", ""))[:19], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
        if now - when <= datetime.timedelta(hours=24):
            n += 1
    return n


def emails_sent_today(path=None):
    """How many e-mails logs/sent_emails.csv records for today (local date)."""
    path = path or os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "sent_emails.csv")
    today = datetime.date.today().strftime("%Y-%m-%d")
    try:
        with open(path, encoding="utf-8", newline="") as fh:
            return sum(1 for row in csv.DictReader(fh) if str(row.get("sent_at", "")).startswith(today))
    except OSError:
        return 0

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
        "name": "job_portals.py (Job Openings & Tech Hiring - Remotive, Internshala, Foundit, Shine)",
        "func": scraper_adapters.run_job_portals_adapter,
        "enabled": True,
        "category": "Job Portals"
    },
    {
        "name": "corporate_registries.py (MCA & ZaubaCorp Registered IT Companies)",
        "func": scraper_adapters.run_corporate_registry_adapter,
        "enabled": True,
        "category": "Corporate Registries"
    },
    {
        "name": "crm_sources.py (GoodFirms B2B Tech Directory)",
        "func": scraper_adapters.run_crm_sources_adapter,
        "enabled": True,
        "category": "B2B Directory"
    },
    {
        "name": "ecommerce_sources.py (Shopify & WooCommerce E-commerce Stores)",
        "func": scraper_adapters.run_ecommerce_sources_adapter,
        "enabled": True,
        "category": "E-Commerce"
    },
    {
        "name": "quora_scraper (Quora Buyer Intent & Tech Recommendation Harvester)",
        "func": scraper_adapters.run_quora_scraper_adapter,
        "enabled": True,
        "category": "Quora Intent"
    },
    {
        "name": "yellowpages_scraper.py (Indian Yellow Pages B2B Tech Directory)",
        "func": scraper_adapters.run_yellowpages_adapter,
        "enabled": True,
        "category": "B2B Directory"
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


def dispatch_pending_outreach_emails(registry: MasterLeadRegistry, max_batch: int = 5, delay_sec: float = 2.0,
                                     daily_cap: int = None, sent_today: int = None) -> int:
    """
    Scans the master registry for leads that have not received outreach emails yet
    (email_status != 'SENT'), cross-references with permanent sent history and blacklist domains,
    and dispatches personalized outreach emails.

    max_batch: most e-mails this run; 0 = no per-run limit (every qualified lead).
    daily_cap: most e-mails per day across the whole app (Gmail limit protection).
    The run also stops e-mailing after MAX_CONSECUTIVE_SEND_FAILURES failures in a row.
    """
    daily_cap = MAX_EMAILS_PER_DAY if daily_cap is None else daily_cap
    sent_today = emails_sent_today() if sent_today is None else sent_today
    if not AUTO_SEND_EMAIL or not send_smtp_email or max_batch < 0:
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
    failures_in_row = 0
    from lead_normalizer import EMAIL_BLACKLIST_DOMAINS

    recent_bounces = bounces_last_24h()
    if recent_bounces >= MAX_BOUNCES_PER_DAY:
        print(f"       [AUTO-MAIL-PENDING] PAUSED: {recent_bounces} e-mails bounced in the last 24 hours. "
              f"No automatic e-mail until that settles, to protect the Gmail account.")
        return 0

    if sent_today >= daily_cap:
        print(f"       [AUTO-MAIL-PENDING] Daily limit reached ({sent_today}/{daily_cap} e-mails today). "
              f"The rest are sent on the next run after midnight.")
        return 0

    try:
        from lead_quality import is_prospect_lead
    except ImportError:
        is_prospect_lead = lambda lead: False
    prospect_cap = MAX_PROSPECT_EMAILS_PER_DAY
    prospects_today = prospect_emails_sent_today()
    prospects_sent = 0
    # Real buyers first, prospects after them (stable sort keeps the file order inside each group)
    for lead_obj in sorted(registry.leads, key=lambda l: bool(is_prospect_lead(l))):
        if max_batch and dispatched >= max_batch:
            print(f"       [AUTO-MAIL-PENDING] Per-run limit of {max_batch} reached; the rest go in the next run.")
            break
        if sent_today + dispatched >= daily_cap:
            print(f"       [AUTO-MAIL-PENDING] Daily limit of {daily_cap} e-mails reached; the rest go tomorrow.")
            break
        if failures_in_row >= MAX_CONSECUTIVE_SEND_FAILURES:
            print(f"       [AUTO-MAIL-PENDING] Stopped after {failures_in_row} failed sends in a row - check the "
                  f"Gmail login (Settings -> Send Test Verification Email). Unsent leads are tried next run.")
            break

        status = str(lead_obj.get("email_status", "")).strip().upper()
        if status in ("SENT", "INVALID", "INVALID_DOMAIN", "UNVERIFIABLE", "EXCLUDED_COMPANY"):
            continue

        # Only contact leads the AI qualified as real buyers with a high score (or allowed prospects)
        if not is_outreach_ready(lead_obj):
            continue
        prospect = bool(is_prospect_lead(lead_obj))
        if prospect and prospects_today + prospects_sent >= prospect_cap:
            continue  # prospect limit for today reached; real buyers were already handled above

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

        # DO-NOT-CONTACT / EXCLUDED COMPANIES SHIELD (e.g. 8dots)
        try:
            from settings_manager import is_company_excluded
            is_ex, ex_reason = is_company_excluded(company_name=comp_name, email=raw_email, website=lead_obj.get("website", ""), settings=settings)
            if is_ex:
                print(f"       -> [AUTO-MAIL-PENDING] [EXCLUDED-COMPANY BLOCKED] Skipping {raw_email} ({comp_name}): {ex_reason}")
                lead_obj["email_status"] = "EXCLUDED_COMPANY"
                continue
        except Exception as shield_err:
            print(f"       -> [AUTO-MAIL-PENDING] [EXCLUDED-COMPANY CHECK ERROR] Refusing send to {raw_email}: {shield_err}")
            lead_obj["email_status"] = "EXCLUDED_COMPANY"
            continue

        # Generate requirement-tailored personalized email via AI email generator
        try:
            from ai_email_generator import generate_personalized_email
            draft = generate_personalized_email(lead_obj, settings=settings)
            custom_sub = draft["subject"]
            custom_msg = draft["body"]
        except Exception:
            try:
                from followup_sequence import outreach_names
            except ImportError:  # keep sending with the plain name if the module is missing
                outreach_names = lambda name: (name, name)
            msg_name, msg_company = outreach_names(comp_name)
            s_tpl, m_tpl = (PROSPECT_SUBJECT, PROSPECT_MESSAGE) if prospect else (sub_tpl, msg_tpl)
            custom_sub = s_tpl.replace("{company}", msg_company).replace("{name}", msg_name).replace("{location}", loc_name)
            custom_msg = m_tpl.replace("{company}", msg_company).replace("{name}", msg_name).replace("{location}", loc_name)
            if sig and sig.strip()[:20] not in custom_msg:
                custom_msg = f"{custom_msg}\n\n---\n{sig.strip()}"

        kind = "prospect" if prospect else "buyer"
        print(f"       -> [AUTO-MAIL-PENDING] Dispatching outreach ({kind}) to {raw_email} ({comp_name})...")
        mail_res = send_smtp_email(raw_email, custom_sub, custom_msg, company_name=comp_name)
        if mail_res.get("success"):
            lead_obj["email_status"] = "SENT"
            lead_obj["email_sent_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            sent_emails_seen.add(email_lower)
            followup_store.safe_log(lead_obj.get("lead_id", ""), "email_sent", f"Email sent: {custom_sub}",
                                    details=custom_msg, source=PROSPECT_SOURCE if prospect else "auto outreach",
                                    lead_name=comp_name, lead_email=raw_email)
            print(f"       -> [AUTO-MAIL-PENDING] [SUCCESS] Delivered via Gmail SMTP.")
            dispatched += 1
            if prospect:
                prospects_sent += 1
            failures_in_row = 0
            if delay_sec > 0:
                time.sleep(delay_sec)
        elif mail_res.get("excluded"):
            lead_obj["email_status"] = "EXCLUDED_COMPANY"
        elif mail_res.get("verify"):
            # The mailbox check stopped it: nothing was sent, so this is not a send failure
            verdict = mail_res["verify"]
            print(f"       -> [AUTO-MAIL-PENDING] [NOT SENT] {raw_email}: {mail_res.get('error')}")
            if verdict == "invalid":
                lead_obj["email_status"] = "INVALID"          # would bounce: never try again
            elif verdict == "catch_all":
                lead_obj["email_status"] = "UNVERIFIABLE"     # cannot be confirmed: no automatic e-mail
            elif "port 25" in str(mail_res.get("error", "")):
                print("       [AUTO-MAIL-PENDING] This computer cannot check mailboxes (port 25 blocked), so no "
                      "e-mail is sent from here. Run the cycle from a computer where the check works.")
                break
            # "unknown" (timeout / temporary answer): leave as is, tried again next run
        else:
            lead_obj["email_status"] = "FAILED"
            failures_in_row += 1
            print(f"       -> [AUTO-MAIL-PENDING] [FAILED] {mail_res.get('error')}")

    try:  # remember whether mailbox checks work here (shown in the daily report)
        from email_checks import record_check_status
        st = record_check_status()
        if st:
            print(f"       [AUTO-MAIL-PENDING] Mailbox check on {st['where']}: {st['mailbox_check']}")
    except Exception:
        pass
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
        company_by_email = {str(i.get("email", "")).strip().lower(): i.get("lead_name", "") for i in due}
        res = followup_sequence.send(
            due, lambda to, sub, body: send_smtp_email(to, sub, body, bypass_duplicate_check=True, verify=None,
                                                       company_name=company_by_email.get(str(to).strip().lower(), "")),
            signature=sig, limit=cfg["max_per_run"])
        print(f"[*] Follow-up sequence: sent {res['sent']}, failed {res['failed']} (limit {cfg['max_per_run']}).")

    if changed and not registry.save_master_safely():
        print(f"[FATAL] Failed to save reply statuses to '{MASTER_CSV}'!")


def run_email_steps(registry: MasterLeadRegistry) -> int:
    """Gmail reply/bounce check first (a fresh bounce pauses auto-mail), then the intro e-mails to
    AI-qualified leads, then due follow-ups (only when FOLLOWUP_AUTO_SEND=true). Returns intro mails sent."""
    try:
        run_followup_step(registry)
    except Exception as e:  # never let follow-ups stop the intro e-mails
        print(f"[WARN] Follow-up step notice: {e}")
    if not (AUTO_SEND_EMAIL and send_smtp_email):
        print("\n[*] Intro e-mails: auto-send is OFF (Settings / AUTO_SEND_EMAIL).")
        return 0
    registry.load_master()  # the follow-up step may have saved reply statuses
    per_run = MAX_PENDING_EMAILS_PER_RUN or "none - every qualified lead"
    print(f"\n[*] Emailing AI-qualified leads (per-run limit: {per_run}; daily limit: {MAX_EMAILS_PER_DAY})...")
    sent = dispatch_pending_outreach_emails(registry, max_batch=MAX_PENDING_EMAILS_PER_RUN)
    print(f"[*] Outreach emails sent this run: {sent}")
    if not registry.save_master_safely():
        print(f"[FATAL] Failed to save email statuses to '{MASTER_CSV}'!")
    return sent


def sync_database():
    if AUTO_SYNC_SUPABASE and sync_to_supabase:
        print("\n[*] Syncing all data with the database...")
        try:
            sync_to_supabase.sync(csv_filepath=MASTER_CSV)
        except Exception as e:
            print(f"[WARN] Database sync notice: {e}")


def run_outreach_only():
    """--email-only: no scraping. Used by the GitHub 'Outreach Mail' workflow at office hours."""
    if not acquire_run_lock():
        print("[ERROR] Another instance of run_all_scrapers.py is already running. Exiting.")
        sys.exit(1)
    try:
        print("=" * 65)
        print(f"       OUTREACH MAIL RUN  {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 65)
        registry = MasterLeadRegistry(MASTER_CSV)
        print(f"[*] Loaded {len(registry.leads)} leads.")
        run_email_steps(registry)
        sync_database()
    finally:
        release_run_lock()


def run_all_scrapers(send_email: bool = True):
    """Main orchestration workflow. send_email=False (--no-email): scrape, enrich and score only."""
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

    # Step 5: e-mail (skipped with --no-email: on GitHub the "Outreach Mail" workflow does it at office hours)
    if send_email:
        registry.load_master()  # steps 4a/4b rewrote the CSV
        run_email_steps(registry)
    else:
        print("\n[*] Step 5: E-mail skipped in this run (--no-email). The outreach mail job sends them.")

    sync_database()

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
    # (no flag)      scrape + e-mail, as before (PC scheduler)
    # --no-email     scrape, enrich and score only (GitHub "1-Hour Auto Lead Scraper")
    # --email-only   Gmail reply check + intro e-mails + follow-ups, no scraping (GitHub "Outreach Mail")
    try:
        if "--email-only" in sys.argv:
            run_outreach_only()
        else:
            run_all_scrapers(send_email="--no-email" not in sys.argv)
    except Exception as e:
        print(f"[FATAL UNHANDLED ERROR] {e}")
        release_run_lock()

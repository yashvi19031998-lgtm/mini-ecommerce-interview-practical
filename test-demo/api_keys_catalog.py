"""Catalog of every API key / credential the app reads from .env, with a safe status check.

The status check only reports whether each variable is set - it never returns the value.
"""
import os
from typing import Dict, List

# group, name, env vars, what it is for, cost, where to get it, optional fallback note
INTEGRATIONS: List[Dict] = [
    {"group": "Core", "id": "supabase", "name": "Supabase",
     "keys": ["SUPABASE_URL|NEXT_PUBLIC_SUPABASE_URL",
              "SUPABASE_KEY|SUPABASE_SERVICE_ROLE_KEY|SUPABASE_ANON_KEY|NEXT_PUBLIC_SUPABASE_ANON_KEY"],
     "purpose": "Cloud sync of leads (login also works with the built-in project)", "used_by": "Login, Supabase Sync",
     "cost": "free", "cost_note": "Free plan", "url": "https://supabase.com/dashboard"},
    {"group": "Core", "id": "anthropic", "name": "Anthropic (Claude AI)",
     "keys": ["ANTHROPIC_API_KEY|ANTHROPIC_AUTH_TOKEN"],
     "purpose": "AI lead scoring and qualification", "used_by": "AI Lead Quality, Slack alerts",
     "cost": "paid", "cost_note": "Pay per use", "url": "https://console.anthropic.com/settings/keys"},

    {"group": "Email", "id": "smtp", "name": "Gmail SMTP (send)",
     "keys": ["SMTP_USER", "SMTP_PASS"],
     "purpose": "Send outreach and follow-up emails", "used_by": "Emails, FollowUp sequences",
     "cost": "free", "cost_note": "Free - Gmail App Password", "url": "https://myaccount.google.com/apppasswords"},
    {"group": "Email", "id": "imap", "name": "Gmail IMAP (read replies)",
     "keys": ["IMAP_USER", "IMAP_PASSWORD"], "fallback": ["SMTP_USER", "SMTP_PASS"],
     "purpose": "Detect replies, bounces and opt-outs", "used_by": "FollowUp History",
     "cost": "free", "cost_note": "Free - same App Password as SMTP", "url": "https://myaccount.google.com/apppasswords"},

    {"group": "Alerts", "id": "slack", "name": "Slack webhook",
     "keys": ["SLACK_WEBHOOK_URL"],
     "purpose": "Hot-lead alerts in a Slack channel", "used_by": "Scraper runs",
     "cost": "free", "cost_note": "Free", "url": "https://api.slack.com/messaging/webhooks"},

    {"group": "Lead sources", "id": "telegram", "name": "Telegram",
     "keys": ["TELEGRAM_API_ID", "TELEGRAM_API_HASH", "TELEGRAM_SESSION_STRING"],
     "purpose": "Scrape leads from Telegram groups", "used_by": "Scraper",
     "cost": "free", "cost_note": "Free", "url": "https://my.telegram.org/apps"},
    {"group": "Lead sources", "id": "feedly", "name": "Feedly API",
     "keys": ["FEEDLY_ACCESS_TOKEN"],
     "purpose": "Read Feedly streams (optional - RSS/OPML works without it)", "used_by": "Scraper",
     "cost": "paid", "cost_note": "Feedly Enterprise", "url": "https://feedly.com/i/team/api"},

    {"group": "Search Engines", "id": "brave", "name": "Brave Search API",
     "keys": ["BRAVE_SEARCH_API_KEY"],
     "purpose": "Web search with site: and quotes (best free option)", "used_by": "Scraping / Mining - Search Engines, Deep Search",
     "cost": "free", "cost_note": "Free plan with a monthly limit (card may be asked)",
     "url": "https://api-dashboard.search.brave.com/app/keys"},
    {"group": "Search Engines", "id": "serper", "name": "Serper.dev (Google results)",
     "keys": ["SERPER_API_KEY"],
     "purpose": "Google search results", "used_by": "Scraping / Mining - Search Engines, Deep Search",
     "cost": "limited", "cost_note": "Free starter credits, then paid", "url": "https://serper.dev/api-key"},

    {"group": "Global Directories", "id": "companies_house", "name": "UK Companies House API",
     "keys": ["COMPANIES_HOUSE_API_KEY"],
     "purpose": "UK registered companies (name, address, industry)", "used_by": "Scraping / Mining - Global Directories",
     "cost": "free", "cost_note": "Free key", "url": "https://developer.company-information.service.gov.uk/"},
    {"group": "Global Directories", "id": "sec_edgar", "name": "US SEC EDGAR (contact for User-Agent)",
     "keys": ["SEC_USER_AGENT"],
     "purpose": "US public companies; SEC requires a contact in the User-Agent, e.g. 'LeadsGenAI you@company.com'",
     "used_by": "Scraping / Mining - Global Directories",
     "cost": "free", "cost_note": "Free, no key - just your contact text", "url": "https://www.sec.gov/os/accessing-edgar-data"},

    {"group": "Job Portal Scraper", "id": "adzuna", "name": "Adzuna",
     "keys": ["ADZUNA_APP_ID", "ADZUNA_APP_KEY"],
     "purpose": "Job search on Adzuna India", "used_by": "Job Portal Scraper",
     "cost": "free", "cost_note": "Free", "url": "https://developer.adzuna.com/signup"},
    {"group": "Job Portal Scraper", "id": "jooble", "name": "Jooble",
     "keys": ["JOOBLE_API_KEY"],
     "purpose": "Job search on Jooble", "used_by": "Job Portal Scraper",
     "cost": "free", "cost_note": "Free", "url": "https://jooble.org/api/about"},

    {"group": "CRM Sources", "id": "hunter", "name": "Hunter.io",
     "keys": ["HUNTER_API_KEY"],
     "purpose": "Company emails by domain", "used_by": "CRM Sources",
     "cost": "free", "cost_note": "Free plan (monthly credits)", "url": "https://hunter.io/api-keys"},
    {"group": "CRM Sources", "id": "apollo", "name": "Apollo.io",
     "keys": ["APOLLO_API_KEY"],
     "purpose": "Decision makers + contact enrichment", "used_by": "CRM Sources, Apollo enricher",
     "cost": "limited", "cost_note": "Free plan - some API endpoints need a paid plan",
     "url": "https://app.apollo.io/#/settings/integrations/api"},
    {"group": "CRM Sources", "id": "google_places", "name": "Google Places API",
     "keys": ["GOOGLE_PLACES_API_KEY"],
     "purpose": "Business listings: name, phone, website", "used_by": "CRM Sources",
     "cost": "limited", "cost_note": "Free monthly quota - credit card required",
     "url": "https://console.cloud.google.com/apis/credentials"},
    {"group": "CRM Sources", "id": "snov", "name": "Snov.io",
     "keys": ["SNOV_CLIENT_ID", "SNOV_CLIENT_SECRET"],
     "purpose": "Company database search", "used_by": "CRM Sources",
     "cost": "paid", "cost_note": "Trial credits - API mostly on paid plans", "url": "https://app.snov.io/account/api"},
    {"group": "CRM Sources", "id": "lusha", "name": "Lusha",
     "keys": ["LUSHA_API_KEY"],
     "purpose": "Contact previews (full details use credits)", "used_by": "CRM Sources",
     "cost": "paid", "cost_note": "Paid plan for API", "url": "https://dashboard.lusha.com/enrich/api"},
    {"group": "CRM Sources", "id": "rocketreach", "name": "RocketReach",
     "keys": ["ROCKETREACH_API_KEY"],
     "purpose": "People search", "used_by": "CRM Sources",
     "cost": "paid", "cost_note": "Paid API plan", "url": "https://rocketreach.co/api"},
]


def _is_set(name: str) -> bool:
    """`A|B` means either variable is accepted."""
    return any(os.getenv(n, "").strip() for n in name.split("|"))


def integration_status() -> Dict:
    """Status of every integration. Values are never included - only set / missing."""
    items = []
    for it in INTEGRATIONS:
        keys = [{"name": k.split("|")[0], "aliases": k.split("|")[1:], "set": _is_set(k)} for k in it["keys"]]
        n_set = sum(k["set"] for k in keys)
        if n_set == len(keys):
            status = "configured"
        elif it.get("fallback") and all(_is_set(k) for k in it["fallback"]):
            status = "fallback"  # e.g. IMAP uses the SMTP login
        elif n_set:
            status = "partial"
        else:
            status = "missing"
        items.append({k: v for k, v in it.items() if k not in ("keys", "fallback")} |
                     {"keys": keys, "status": status, "fallback": it.get("fallback", [])})
    counts = {s: sum(1 for i in items if i["status"] == s) for s in ("configured", "fallback", "partial", "missing")}
    return {"items": items, "counts": counts, "total": len(items)}

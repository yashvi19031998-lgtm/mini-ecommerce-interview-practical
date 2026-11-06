"""
Lead quality pipeline: cleanup + contact channel + AI qualification.

    python lead_quality.py                 # clean + qualify up to AI_QUALIFY_LIMIT new leads
    python lead_quality.py --clean-only    # no AI calls
    python lead_quality.py --limit 300     # qualify more leads in one run (e.g. first backfill)

Steps
1. Clean: re-normalizes every row via MasterLeadRegistry (drops placeholder emails,
   moves reddit/bing "websites" into source_url) and removes paid-ad rows.
2. Contact channel: records HOW each lead can be reached (email / phone / reddit / ...).
3. AI qualification (needs ANTHROPIC_API_KEY): Claude reads each unqualified lead and returns
   a category, a 0-10 score, a one-line summary, the requirement, tech stack and budget.

Auto-outreach (run_all_scrapers.py) only emails leads where is_outreach_ready() is True.
"""

import re
import argparse
import datetime
import json
import os

import env_loader  # noqa: F401  (loads .env before reading settings below)
import slack_notifier
import website_signals
from lead_normalizer import MasterLeadRegistry, is_ad_url, lead_age_days

MASTER_CSV = "all_leads_master.csv"
AI_MODEL = os.getenv("AI_QUALIFY_MODEL", "claude-opus-5-5")
AI_QUALIFY_LIMIT = int(os.getenv("AI_QUALIFY_LIMIT", "40"))  # max new leads qualified per run
MIN_AI_SCORE_FOR_AUTO_EMAIL = int(os.getenv("MIN_AI_SCORE_FOR_AUTO_EMAIL", "7"))

# Posts older than this are usually already filled: their score is capped so they never
# reach Slack or auto-email. Age = post date if known, else when we first saw the lead.
STALE_AFTER_DAYS = int(os.getenv("STALE_AFTER_DAYS", "14"))
STALE_SCORE_CAP = 4

# Who you actually want as a client. Edit in .env to match your business.
IDEAL_CLIENT_PROFILE = os.getenv("IDEAL_CLIENT_PROFILE", "").strip() or (
    "Startups, scale-ups, and established businesses in the US, UK, Canada, Australia, Europe, UAE or India "
    "seeking Senior Developers, Tech Leads, or Engineering Partners with 8-9+ years of industry experience. "
    "Focus technologies: Next.js, React, TypeScript, Node.js, Python/FastAPI, AI/LLM agents, Flutter, mobile apps, "
    "and scalable SaaS/cloud architecture. "
    "Ideal budget: USD 1,000 to USD 20,000+ (or INR 80,000+), or ongoing monthly dedicated developer retainers ($2,500 - $6,000/mo). "
    "Unfavorable fit: Entry-level/intern work, trivial $50 fixes, academic assignments, or unpaid commission/equity-only."
)

# Categories that represent someone who may BUY software/dev services from us
BUYER_CATEGORIES = {"client_project", "hiring_developer"}

AI_CATEGORIES = [
    "client_project",     # wants a website/app/software built (agency or freelancer welcome)
    "hiring_developer",   # hiring a developer / dev team (contract or full-time) - we can pitch staff augmentation
    "service_provider",   # agency/freelancer SELLING dev services (competitor, not a buyer)
    "job_seeker",         # person looking for work ("[FOR HIRE]")
    "job_board_or_directory",  # Indeed, Upwork listing pages, directories, aggregators
    "prospect_signal",    # no request yet, but a strong trigger (e.g. just raised funding) - Slack only, never auto-emailed
    "irrelevant",         # non-IT work, articles, dictionaries, spam, ads
]

SYSTEM_PROMPT = f"""You qualify sales leads for Sangeeta Infotech, a premier software agency in Ahmedabad, India \
with 8-9+ years of senior software engineering, technical architecture, and product delivery experience. \
The agency provides seasoned Senior Developers, Tech Leads, and full engineering teams for web apps, \
mobile apps, custom SaaS/software, and AI integrations.

A good lead is a person or company that currently NEEDS software work done or wants to hire developers, \
so the agency could offer its services. Sellers of the same services, job seekers, job boards, \
directories, and non-software work (e.g. video editing, data entry, social media posting) are not leads.

Classify the lead into exactly one category:
- client_project: wants a website, app, or software built or fixed
- hiring_developer: hiring developers / a dev team (contract or full-time)
- service_provider: an agency or freelancer selling development services
- job_seeker: someone looking for work
- job_board_or_directory: a job board, listing page, marketplace or directory page rather than one buyer
- prospect_signal: no explicit request, but a specific company with a strong reason to need software \
work soon - e.g. a startup that just raised funding, launched, or is expanding. Score by how likely they \
are to buy development work (tech/product startups high; non-tech or very large companies low).
- irrelevant: anything else (non-IT work, articles, ads, spam)

Seniority & Quality Scoring Guide (0-10):
- HIGHEST PRIORITY (Score 8-10): Clients looking for Senior Engineers, Tech Leads, Lead Developers, Staff/Architect \
level engineers, 8+ or 9+ years of experience, or ambitious projects with healthy budgets ($1,000+ USD or ongoing retainers).
- STANDARD BUYER (Score 6-7): Clear software or web project with reasonable scope and reachable contacts.
- LOW PRIORITY / DISQUALIFIED (Score 0-3): Entry-level tasks, students, micro-tasks under $100, unpaid tests, competitors, \
job seekers, and recruiters demanding on-site presence outside India.

Base everything only on the text given. Use an empty string when a field is unknown; never invent budgets or tech."""

SYSTEM_PROMPT += f"""

Our ideal client:
{IDEAL_CLIENT_PROFILE}

Within the buyer categories, score higher the better the lead matches the ideal client \
(fit of work type, budget, location, and how specific the need is) and lower when it is a poor fit. \
Each lead shows when it was posted and today's date: a request posted more than about two weeks ago \
is probably already filled, so score it lower. \
"Seen in" lists every source where this same lead was found; several independent sources are a stronger signal. \
"Website check" lists problems found on the company's own website (not mobile-friendly, no HTTPS, old \
WordPress/jQuery, not updated in years, site builder), and "Website: none found" means a listed local business \
has no website. These are reasons a business may need web work: without an explicit request, classify such a \
real business as prospect_signal (stronger the more serious the problems); never treat them as a request."""

QUALIFY_SCHEMA = {
    "type": "object",
    "properties": {
        "category": {"type": "string", "enum": AI_CATEGORIES},
        "score": {"type": "integer"},
        "summary": {"type": "string", "description": "One sentence: who they are and what they want."},
        "requirement": {"type": "string", "description": "The concrete work they need, or empty."},
        "tech_stack": {"type": "string", "description": "Comma-separated technologies mentioned, or empty."},
        "budget": {"type": "string", "description": "Budget or rate exactly as stated, or empty."},
        "reason": {"type": "string", "description": "Short justification for the category and score."},
    },
    "required": ["category", "score", "summary", "requirement", "tech_stack", "budget", "reason"],
    "additionalProperties": False,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def derive_contact_channel(lead: dict) -> str:
    """Best available way to reach the lead, in order of preference."""
    if lead.get("email"):
        return "email"
    if lead.get("mobile_number"):
        return "phone"
    src = f"{lead.get('source_url', '')} {lead.get('source', '')}".lower()
    if "freelancer.com" in src:
        return "freelancer_bid"  # must be contacted through the platform
    if "ycombinator.com" in src or "hacker news" in src:
        return "hackernews"
    if "reddit.com" in src or "reddit" in src:
        return "reddit"
    if "t.me/" in src or "telegram" in src:
        return "telegram"
    if lead.get("website"):
        return "website"
    return "none"


def is_outreach_ready(lead: dict) -> bool:
    """True only for AI-qualified buyer leads with a high enough score and an email."""
    try:
        score = int(float(lead.get("ai_score") or 0))
    except ValueError:
        score = 0
    return (
        lead.get("ai_category") in BUYER_CATEGORIES
        and score >= MIN_AI_SCORE_FOR_AUTO_EMAIL
        and bool(lead.get("email"))
        and not is_stale(lead)
    )


def _age_label(lead: dict) -> str:
    age = lead_age_days(lead)
    if age is None:
        return "unknown"
    stamp = lead.get("posted_at") or lead.get("first_seen_at")
    kind = "" if lead.get("posted_at") else " (first seen by us; real post date unknown)"
    return f"{stamp[:10]}, {int(age)} days ago{kind}"


def is_stale(lead: dict) -> bool:
    age = lead_age_days(lead)
    return age is not None and age > STALE_AFTER_DAYS


def _sources(lead: dict) -> list:
    """Distinct sources this lead was merged from (the normalizer joins them with ' | ')."""
    parts = [p.strip() for p in str(lead.get("source") or "").split("|") if p.strip()]
    return list(dict.fromkeys(parts))


LOCAL_BUSINESS_SOURCES = ("google maps", "justdial", "indiamart", "tradeindia", "exportersindia")


def _is_local_business(lead: dict) -> bool:
    """Listing-directory businesses: for these, having no website is itself a sales signal."""
    src = str(lead.get("source") or "").lower()
    return any(s in src for s in LOCAL_BUSINESS_SOURCES)


def _lead_text(lead: dict) -> str:
    sources = _sources(lead)
    fields = [
        ("Posted", _age_label(lead)),
        ("Seen in", f"{len(sources)} sources: {'; '.join(sources)}" if len(sources) > 1 else ""),
        ("Title / company", lead.get("company_name")),
        ("Contact name", lead.get("full_name")),
        ("Description", lead.get("description")),
        ("Website", lead.get("website") or ("none found" if _is_local_business(lead) else "")),
        ("Website check", lead.get("website_signals")),
        ("Source", lead.get("source")),
        ("Source URL", lead.get("source_url")),
        ("Location", lead.get("location")),
        ("Has email", "yes" if lead.get("email") else "no"),
        ("Has phone", "yes" if lead.get("mobile_number") else "no"),
    ]
    return "\n".join(f"{k}: {v}" for k, v in fields if v)


# ---------------------------------------------------------------------------
# Step 1 + 2: cleanup
# ---------------------------------------------------------------------------

def clean_master(registry: MasterLeadRegistry) -> dict:
    """Drops ad rows and sets contact_channel. Registry load already re-normalized every row."""
    before = len(registry.leads)
    registry.leads = [
        l for l in registry.leads
        if not (is_ad_url(l.get("source_url")) or is_ad_url(l.get("website")))
    ]
    removed_ads = before - len(registry.leads)
    for lead in registry.leads:
        lead["contact_channel"] = derive_contact_channel(lead)
    return {"removed_ads": removed_ads, "remaining": len(registry.leads)}


# ---------------------------------------------------------------------------
# Step 3: AI qualification
# ---------------------------------------------------------------------------

def _get_client():
    if not os.getenv("ANTHROPIC_API_KEY") and not os.getenv("ANTHROPIC_AUTH_TOKEN"):
        return None
    try:
        import anthropic
    except ImportError:
        print("[AI] 'anthropic' package not installed - run: pip install -r requirements.txt")
        return None
    return anthropic.Anthropic()


def qualify_one(client, lead: dict) -> dict:
    """Returns the parsed qualification dict, or raises on API/refusal problems."""
    response = client.beta.messages.create(
        model=AI_MODEL,
        max_tokens=2048,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",  # if a safety classifier declines, retry on Anthropic's recommended model
        output_config={
            "effort": "low",  # simple classification - low effort keeps cost and latency down
            "format": {"type": "json_schema", "schema": QUALIFY_SCHEMA},
        },
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content":
                   f"Today's date: {datetime.date.today().isoformat()}\n\nQualify this lead:\n\n{_lead_text(lead)}"}],
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("model declined to classify this lead")
    if response.stop_reason == "max_tokens":
        raise RuntimeError("response truncated (max_tokens)")
    text = next((b.text for b in response.content if b.type == "text"), "")
    return json.loads(text)


def qualify_one_heuristic(lead: dict) -> dict:
    """Accurate rule-based NLP lead qualifier used when ANTHROPIC_API_KEY is not set or API fails."""
    text = (
        f"{lead.get('company_name', '')} {lead.get('description', '')} "
        f"{lead.get('source_url', '')} {lead.get('source', '')}"
    ).lower()

    # 1. Check for job seekers ([FOR HIRE])
    job_seeker_patterns = [
        "[for hire]", "for hire", "hire me", "my portfolio", "i am a developer",
        "i am offering", "freelancer available", "looking for work", "seeking employment"
    ]
    if any(p in text for p in job_seeker_patterns):
        return {
            "category": "job_seeker",
            "score": 1,
            "summary": "Candidate or freelancer looking for work (not a buyer).",
            "requirement": "",
            "tech_stack": "",
            "budget": "",
            "reason": "Author is offering services / job seeking."
        }

    # 2. Check for irrelevant / non-IT tasks
    irrelevant_patterns = [
        "tiktok poster", "art exhibit", "model", "actor", "voice actor",
        "video editor", "writer", "transcription", "data entry", "virtual assistant",
        "math tutor", "homework", "essay", "academic", "babysitter", "delivery driver"
    ]
    if any(p in text for p in irrelevant_patterns):
        return {
            "category": "irrelevant",
            "score": 0,
            "summary": "Non-IT or non-software request.",
            "requirement": "",
            "tech_stack": "",
            "budget": "",
            "reason": "Post is for non-software / non-IT task."
        }

    # 3. Check for job boards / aggregators / directories
    board_patterns = [
        "indeed", "apna", "naukri", "glassdoor", "ziprecruiter", "instahyre",
        "upwork listing", "fiverr gig", "directory"
    ]
    company_lower = (lead.get("company_name") or "").lower()
    if any(b in company_lower for b in board_patterns):
        return {
            "category": "job_board_or_directory",
            "score": 2,
            "summary": f"Job board or directory listing ({lead.get('company_name')}).",
            "requirement": "",
            "tech_stack": "",
            "budget": "",
            "reason": "Aggregator or job board, not an individual buyer."
        }

    # 4. Check for Competitor Agencies / Service Providers
    agency_patterns = [
        "we are a software development company", "we are an agency", "our dev team provides",
        "top it services company", "leading software company"
    ]
    if any(p in text for p in agency_patterns):
        return {
            "category": "service_provider",
            "score": 2,
            "summary": f"Competing agency or IT service provider ({lead.get('company_name')}).",
            "requirement": "",
            "tech_stack": "",
            "budget": "",
            "reason": "Competitor agency selling dev services, not a client."
        }

    # Extract technologies
    known_tech = [
        "react", "next.js", "nextjs", "node.js", "nodejs", "typescript", "python",
        "fastapi", "django", "flutter", "react native", "vue", "angular", "php",
        "laravel", "aws", "docker", "kubernetes", "postgresql", "supabase",
        "shopify", "wordpress", "tailwind", "graphql", "mongodb"
    ]
    found_tech = [t for t in known_tech if re.search(r'\b' + re.escape(t) + r'\b', text)]
    tech_stack_str = ", ".join(found_tech[:6])

    # Extract budget
    budget_match = re.search(r'(\$\s*\d+[\d,]*(\s*k|\s*usd|\s*\/hr|\s*\/hour|\s*\/mo)?|\b\d+k\s*usd|€\s*\d+[\d,]*|₹\s*\d+[\d,]*|inr\s*\d+[\d,]*)', text)
    budget_str = budget_match.group(0).strip() if budget_match else ""

    # Check for Senior / Tech Lead / 8-9+ years experience demand
    senior_patterns = [
        "senior", "tech lead", "lead developer", "lead engineer", "architect",
        "8+ years", "9+ years", "8-10 years", "staff engineer", "principal engineer", "head of"
    ]
    is_senior = any(s in text for s in senior_patterns)

    # Check for hiring / buyer intent
    hiring_patterns = [
        "[hiring]", "hiring", "looking for", "need a developer", "need developer",
        "looking to hire", "seeking developer", "contractor needed", "build an app",
        "build a website", "mvp", "redesign", "develop a", "agency needed"
    ]
    is_hiring = any(h in text for h in hiring_patterns)

    # 5. Score computation
    if is_senior and is_hiring:
        score = 9
        if budget_str:
            score = 10
        category = "hiring_developer"
        summary = f"Client hiring Senior / Lead Engineer for {tech_stack_str or 'software project'}."
        reason = "Explicit senior / lead developer hiring request with strong intent."
    elif is_hiring:
        score = 7
        if budget_str:
            score = 8
        category = "hiring_developer" if "developer" in text or "engineer" in text else "client_project"
        summary = f"Client hiring for {tech_stack_str or 'development project'}."
        reason = "Clear client requirement for software/web development."
    elif lead.get("website") and _is_local_business(lead):
        # Local business needing web presence
        score = 6 if not lead.get("website") else 4
        category = "prospect_signal"
        summary = f"Local business prospect: {lead.get('company_name')} ({lead.get('location', '')})."
        reason = "Established business prospect with potential digital/web development needs."
    elif found_tech:
        score = 5
        category = "client_project"
        summary = f"Technical lead involving {tech_stack_str}."
        reason = "Mention of specific tech stack in lead details."
    else:
        score = 3
        category = "prospect_signal"
        summary = f"General prospect: {lead.get('company_name') or 'Unknown organization'}."
        reason = "Basic contact without explicit current software posting."

    return {
        "category": category,
        "score": score,
        "summary": summary,
        "requirement": f"Needs {tech_stack_str}" if tech_stack_str else "Software engineering",
        "tech_stack": tech_stack_str,
        "budget": budget_str,
        "reason": reason
    }


def qualify_leads(registry: MasterLeadRegistry, limit: int = AI_QUALIFY_LIMIT) -> dict:
    stats = {"qualified": 0, "failed": 0, "skipped_no_key": False}
    pending = [l for l in registry.leads if not l.get("ai_qualified_at")]
    if not pending:
        return stats

    client = _get_client()
    if client is None:
        print(f"[AI] ANTHROPIC_API_KEY not set - evaluating {min(len(pending), limit)} leads via Fast Heuristic NLP Classifier...")
    else:
        print(f"[AI] Qualify leads via Claude AI ({AI_MODEL}) on up to {limit} leads...")

    # Newest leads first: they are the most likely to still be open
    pending.sort(key=lambda l: l.get("first_seen_at", ""), reverse=True)
    for lead in pending[:limit]:
        # Look at the company's own website first (when Claude is active and for small batch)
        if client is not None and lead.get("website") and not lead.get("website_signals") and limit <= 40:
            try:
                lead["website_signals"] = website_signals.check_website(lead["website"])
            except Exception:
                pass

        result = None
        if client is not None:
            try:
                result = qualify_one(client, lead)
            except Exception as e:
                # Fall back to heuristic engine if Claude API has issues
                result = qualify_one_heuristic(lead)
        else:
            result = qualify_one_heuristic(lead)

        if not result:
            stats["failed"] += 1
            continue

        score = max(0, min(10, int(result.get("score", 0))))
        reason = result.get("reason", "")
        if is_stale(lead) and score > STALE_SCORE_CAP:
            score = STALE_SCORE_CAP
            reason = f"[Stale: older than {STALE_AFTER_DAYS} days, score capped] {reason}"
        lead.update({
            "ai_category": result.get("category", ""),
            "ai_score": str(score),
            "ai_summary": result.get("summary", "")[:300],
            "ai_requirement": result.get("requirement", "")[:300],
            "ai_tech_stack": result.get("tech_stack", "")[:150],
            "ai_budget": result.get("budget", "")[:100],
            "ai_reason": reason[:300],
            "ai_qualified_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })
        stats["qualified"] += 1
        print(f"[AI] {lead.get('lead_id')}: {lead['ai_category']} ({score}/10) - {lead['ai_summary'][:80]}")
    return stats


def run(master_csv: str = MASTER_CSV, limit: int = AI_QUALIFY_LIMIT, use_ai: bool = True) -> dict:
    registry = MasterLeadRegistry(master_csv)  # loads + re-normalizes every row
    stats = clean_master(registry)
    if use_ai:
        stats.update(qualify_leads(registry, limit=limit))
    # Step 4: post new hot leads to Slack (no-op if SLACK_WEBHOOK_URL is not set)
    stats.update(slack_notifier.notify_hot_leads(registry.leads))
    if not registry.save_master_safely():
        raise RuntimeError(f"Failed to save {master_csv}")
    ready = sum(1 for l in registry.leads if is_outreach_ready(l))
    stats["outreach_ready"] = ready
    try:
        import source_report
        source_report.print_report(source_report.write_report(
            registry.leads, os.path.join(os.path.dirname(os.path.abspath(master_csv)), source_report.REPORT_PATH)))
    except OSError as e:
        print(f"[QUALITY] source report not written: {e}")
    print(f"[QUALITY] {stats}")
    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--clean-only", action="store_true", help="skip AI qualification")
    parser.add_argument("--limit", type=int, default=AI_QUALIFY_LIMIT, help="max leads to AI-qualify this run")
    parser.add_argument("--csv", default=MASTER_CSV)
    args = parser.parse_args()
    run(args.csv, limit=args.limit, use_ai=not args.clean_only)

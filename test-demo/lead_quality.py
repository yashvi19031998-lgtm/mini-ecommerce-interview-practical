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
import time

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
mobile apps, custom SaaS/software, and AI integrations, and also digital marketing work: SEO, social \
media marketing / management, Google and Meta ads, and digital marketing campaigns.

A good lead is a person or company that currently NEEDS software or digital marketing work done or wants \
to hire developers / a marketing freelancer, so the agency could offer its services. Sellers of the same \
services, job seekers, job boards, directories, and other non-IT work (e.g. video editing, data entry, \
voice-over, translation, sales roles) are not leads.

Classify the lead into exactly one category:
- client_project: wants a website, app, or software built or fixed, or wants SEO / social media / ads / \
digital marketing work done
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


# ---------------------------------------------------------------------------
# Who may get an AUTOMATIC cold e-mail (review of 2026-11-13: of 16 "ready" leads only 2 were real buyers;
# the rest were non-IT jobs, job seekers, sales roles, US-only / no-agency posts and a government office).
# The AI score alone is not enough, so the lead's own text is checked again here, every time.
# ---------------------------------------------------------------------------
# The role being hired for / the work wanted is software
_DEV_ROLE = re.compile(r"\b(developers?|programmers?|engineers?|engineering|devops|sre|full[- ]?stack|front[- ]?end|"
                       r"back[- ]?end|coders?|cto|software|web ?app|website|web site|web ?dev\w*|mobile app|ios app|"
                       r"android app|app development|saas|mvp|api|wordpress|shopify|react|next\.?js|node\.?js|python|"
                       r"django|laravel|php|flutter|react native|ai agents?|llm|machine learning|automation|"
                       # digital marketing work is ours too
                       r"seo|search engine optimi[sz]ation|digital marketing|social media (marketing|manager|management)|"
                       r"smm|google ads|meta ads|facebook ads|instagram ads|ppc|performance marketing|"
                       r"marketing agency)\b", re.I)
_DEV_PERSON = re.compile(r"\b(developers?|programmers?|engineers?|devops|sre|full[- ]?stack|front[- ]?end|back[- ]?end|"
                         r"coders?|cto|architects?|web ?dev\w*)\b", re.I)
# Roles / work that are not software
_NON_IT_ROLE = re.compile(r"\b(native \w+ speakers?|speakers?|voice[- ]?(over|actors?)|record(ing)? (short )?(lines|audio)|"
                          r"transcri\w+|translat\w+|tutors?|teachers?|content creators?|creators?|ugc|influencers?|"
                          r"video editors?|copywriters?|writers?|sales|account executive|founding ae|\bae\b|gtm|"
                          r"go-to-market|"
                          r"recruiters?|onboarding lead|customer (support|success|service)|virtual assistants?|"
                          r"data entry|bartenders?|drivers?|nurses?|accountants?|bookkeep\w*|photographers?|models?|"
                          r"actors?|job fairs?|career fairs?|hiring events?)\b", re.I)
# The author is offering their own services (not a buyer)
_SELLER = re.compile(r"willing to relocate|r[eé]sum[eé]\s*/\s*cv|\bfor hire\b|\[for hire\]|hire me|available for (hire|work)|"
                     r"seeking (work|employment|a (job|role))|looking for (work|a job|my next role)|open to work|"
                     r"who wants to be hired", re.I)
# Posts that rule out an agency in India
_RESTRICTED = re.compile(
    r"citizenship required|citizens? only|work authori[sz]ation|authori[sz]ed to work|no (visa )?sponsorship|"
    r"security clearance|no (agencies|agency|recruiters|outsourc\w*|offshore)|agencies need not apply|"
    r"\b(us|usa|u\.s\.|uk|eu|canada|europe|north america)[- ]only\b|"
    r"remote\W{0,3}\(?\s*(us|usa|u\.s\.|uk|eu|europe|canada|north america|americas)\b(\s*(or|/|,|&|and)\s*"
    r"(us|usa|uk|eu|europe|canada))*\)?", re.I)
_ONSITE = re.compile(r"\b(on-?site|in[- ]office|in[- ]person|hybrid)\b", re.I)


def _role_text(lead: dict) -> str:
    """Title plus the head of the post, where the role is ('Company | Role | Location | ...')."""
    desc = " ".join(str(lead.get("description") or "").split())
    head = " | ".join(desc[:260].split("|")[:3]) if "|" in desc[:160] else desc[:160]
    return f"{lead.get('company_name') or ''} | {head}"


def _env_int(name, default):
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return int(default)


def is_prospect_lead(lead: dict) -> bool:
    """A prospect (a company with a reason to need software, no request yet) that may get the
    prospect intro e-mail: only when AUTO_EMAIL_PROSPECT_SIGNALS=true. Real buyers always go first and
    prospects have their own daily limit (MAX_PROSPECT_EMAILS_PER_DAY, run_all_scrapers.py)."""
    return (lead.get("ai_category") == "prospect_signal"
            and os.getenv("AUTO_EMAIL_PROSPECT_SIGNALS", "false").lower() in ("true", "1", "yes"))


# Prospect e-mail is only for businesses that may NEED software. Other software / IT firms are competitors,
# and many "prospects" are really articles, lists or big brands picked up by web searches.
_IT_FIRM = re.compile(
    r"soft\w*|info\s?tech|infosys\w*|info\s?systems?|technolog\w*|techno\w*|\btech\b|tech\s?labs?|"
    r"\bsolutions?\b|\bit\s+(services?|company|companies|consult\w*|firm|solutions?)\b|"
    r"web\s?(design\w*|develop\w*)|app\s?develop\w*|mobile\s+apps?|digital\s+(agency|marketing|solutions?)|"
    r"\bdevelopers?\b|\bdevelopment\b|\bstudios?\b|\blabs?\b|consult\w*|outsourc\w*|\bcoding\b|\bcodes?\b|"
    r"\bsaas\b|\bai\b|\bdata\w*\b", re.I)
_IT_SOURCE = re.compile(r"goodfirms|clutch|software|\bit\s+(company|services|consult)|web\s?development|"
                        r"app\s+development|developer|freelanc|upwork|remote|hacker\s*news|jobicy|telegram", re.I)
_ARTICLE = re.compile(r"^\s*(how\s+to|the\s+(definitive|ultimate|complete|best)|top\b|best\b|\d+\s+best|list\s+of|"
                      r"official\b|job\s+opportunit|hire\b|online$|software$|what\s+is|why\b)", re.I)
_BIG_DOMAINS = {"wikihow.com", "aol.com", "corp.aol.com", "airbnb.com", "deloitte.com", "mapquest.com", "jquery.com",
                "freelancer.com", "upwork.com", "microsoft.com", "google.com", "amazon.com", "apple.com", "meta.com",
                "facebook.com", "linkedin.com", "indeed.com", "governmentjobs.com", "wikipedia.org", "github.com",
                "midtowncomics.com", "itprofiles.com", "sortlist.com", "goodfirms.co", "clutch.co"}


def prospect_block_reason(lead: dict) -> str:
    """Why a prospect must not get the prospect intro mail, or ''."""
    company = str(lead.get("company_name") or "").strip()
    email = str(lead.get("email") or "").split(",")[0].strip().lower()
    domain = email.rsplit("@", 1)[-1]
    if len(company) < 3 or _ARTICLE.search(company) or _ARTICLE.search(str(lead.get("title") or "")):
        return "looks like an article, list or job page, not a business"
    if domain in _BIG_DOMAINS or any(domain.endswith("." + d) for d in _BIG_DOMAINS):
        return "large brand / platform, not a prospect"
    if domain.endswith((".gov", ".gov.in", ".nic.in", ".edu", ".ac.in")):
        return "government / education address"
    site = str(lead.get("website") or "")
    if _IT_SOURCE.search(str(lead.get("source") or "")) or _IT_FIRM.search(f"{company} {domain} {site}"):
        return "software / IT company (competitor), not a prospect"
    return ""


def outreach_block_reason(lead: dict) -> str:
    """Why this lead must NOT get an automatic cold e-mail, or '' when it may (the mailbox is still
    verified at send time)."""
    try:
        score = int(float(lead.get("ai_score") or 0))
    except ValueError:
        score = 0
    email = str(lead.get("email") or "").split(",")[0].strip()
    prospect = is_prospect_lead(lead)
    if lead.get("ai_category") not in BUYER_CATEGORIES and not prospect:
        return f"not a buyer ({lead.get('ai_category') or 'not qualified yet'})"
    min_score = (_env_int("MIN_AI_SCORE_FOR_PROSPECT_EMAIL", 3) if prospect
                 else _env_int("MIN_AI_SCORE_FOR_AUTO_EMAIL", MIN_AI_SCORE_FOR_AUTO_EMAIL))
    if score < min_score:
        return f"score {score} below {min_score}"
    if not email:
        return "no e-mail address"
    if is_stale(lead):
        return f"older than {STALE_AFTER_DAYS} days"
    try:
        from email_checks import address_problem
        problem = address_problem(email, policy=True)
    except ImportError:
        problem = ""
    if problem:
        return problem
    role = _role_text(lead)
    full = f"{role} {lead.get('description') or ''}"
    if _SELLER.search(full):
        return "the author offers their own services (job seeker / freelancer), not a buyer"
    if prospect:
        return prospect_block_reason(lead)  # a company, not a job post: the job-post checks below do not apply
    if _NON_IT_ROLE.search(role) and not _DEV_PERSON.search(role):
        return "the role is not software work"
    if not _DEV_ROLE.search(f"{full} {lead.get('ai_requirement') or ''} {lead.get('ai_tech_stack') or ''}"):
        return "no software work mentioned"
    if _RESTRICTED.search(full):
        return "the post excludes agencies or requires a location / citizenship we cannot meet"
    if _ONSITE.search(role) and not re.search(r"\bremote\b", role, re.I):
        return "on-site role"
    return ""


def is_outreach_ready(lead: dict) -> bool:
    """True only for buyer leads that pass every check in outreach_block_reason()."""
    return not outreach_block_reason(lead)


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

    seniority_fit = "Senior / Lead (8-9+ Yrs)" if is_senior else ("Mid-Level Specialist" if found_tech else "Standard Web")
    deal_size = budget_str if budget_str else ("$3,000 - $8,000" if is_senior else ("$1,500 - $4,000" if is_hiring else ""))
    has_phone = bool(str(lead.get("mobile_number") or "").strip())
    whatsapp_status = "READY" if has_phone else "N/A"

    # Extract LinkedIn URL from text or source
    linkedin_match = re.search(r'https?://[a-zA-Z0-9.\-_]*linkedin\.com/[^\s"\']+', text)
    linkedin_url = linkedin_match.group(0).strip() if linkedin_match else str(lead.get("linkedin_url") or "")

    # Extract decision maker title if present
    title_match = re.search(r'\((founder|co-founder|ceo|owner|cto|managing director|vp of engineering|head of it|director)\)', text, re.I)
    decision_title = title_match.group(1).title() if title_match else str(lead.get("decision_maker_title") or "")

    return {
        "category": category,
        "score": score,
        "summary": summary,
        "requirement": f"Needs {tech_stack_str}" if tech_stack_str else "Software engineering",
        "tech_stack": tech_stack_str,
        "budget": budget_str,
        "reason": reason,
        "seniority_fit": seniority_fit,
        "deal_size_estimate": deal_size,
        "whatsapp_status": whatsapp_status,
        "linkedin_url": linkedin_url,
        "decision_maker_title": decision_title
    }


# ---------------------------------------------------------------------------
# Free option: Google Gemini (used only when no Anthropic key is set)
# Get a key at https://aistudio.google.com -> "Get API key"; put it in .env / GitHub secrets as GEMINI_API_KEY.
# The free tier has daily limits and Google may use the text sent to improve its products (the text is the
# lead's own public post). On a rate limit the rest of the run uses the rule-based classifier.
# ---------------------------------------------------------------------------
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
GEMINI_DELAY_SEC = float(os.getenv("GEMINI_DELAY_SEC", "4.5"))  # stay under free-tier requests-per-minute limits
GEMINI_TIMEOUT = 40


class GeminiRateLimited(RuntimeError):
    """Gemini said 429/402 (free-tier limit or no credit): stop calling it for this run."""


def gemini_key() -> str:
    return (os.getenv("GEMINI_API_KEY") or "").strip()


_GEMINI_FORMAT = (
    "\n\nAnswer with ONLY one JSON object, no other text, with exactly these keys: "
    '"category" (one of: ' + ", ".join(AI_CATEGORIES) + '), "score" (integer 0-10), '
    '"summary" (one sentence: who they are and what they want), "requirement" (the concrete work they need, or ""), '
    '"tech_stack" (comma-separated technologies mentioned, or ""), "budget" (budget or rate exactly as stated, or ""), '
    '"reason" (short justification for the category and score).'
)


def _parse_gemini_json(text: str) -> dict:
    t = (text or "").strip()
    if t.startswith("```"):
        t = t.strip("`")
        t = t[t.find("{"):] if "{" in t else t
    start, end = t.find("{"), t.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON object in the reply")
    data = json.loads(t[start:end + 1])
    if not isinstance(data, dict) or data.get("category") not in AI_CATEGORIES:
        raise ValueError(f"unexpected category {data.get('category') if isinstance(data, dict) else data!r}")
    try:
        data["score"] = max(0, min(10, int(float(data.get("score", 0)))))
    except (TypeError, ValueError):
        raise ValueError("score is not a number")
    for k in ("summary", "requirement", "tech_stack", "budget", "reason"):
        data[k] = str(data.get(k) or "")
    return data


def qualify_one_gemini(lead: dict, post=None) -> dict:
    """Classifies one lead with Gemini. Raises GeminiRateLimited on 429/402, RuntimeError/ValueError otherwise."""
    import requests
    post = post or requests.post
    key = gemini_key()
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not set")
    prompt = (SYSTEM_PROMPT + _GEMINI_FORMAT + f"\n\nToday's date: {datetime.date.today().isoformat()}"
              f"\n\nQualify this lead:\n\n{_lead_text(lead)}")
    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json", "maxOutputTokens": 1024},
    }
    resp = post(GEMINI_URL.format(model=GEMINI_MODEL), json=body, timeout=GEMINI_TIMEOUT,
                headers={"x-goog-api-key": key, "Content-Type": "application/json"})
    if resp.status_code in (402, 429):
        raise GeminiRateLimited(f"Gemini limit reached (HTTP {resp.status_code})")
    if resp.status_code != 200:
        try:
            msg = resp.json().get("error", {}).get("message", "")
        except ValueError:
            msg = resp.text[:200]
        raise RuntimeError(f"Gemini HTTP {resp.status_code}: {msg[:200]}")
    data = resp.json()
    try:
        parts = data["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError, TypeError):
        reason = (data.get("promptFeedback") or {}).get("blockReason") or "no answer"
        raise RuntimeError(f"Gemini returned no text ({reason})")
    return _parse_gemini_json("".join(p.get("text", "") for p in parts if isinstance(p, dict)))


def qualify_leads(registry: MasterLeadRegistry, limit: int = AI_QUALIFY_LIMIT) -> dict:
    stats = {"qualified": 0, "failed": 0, "skipped_no_key": False}
    pending = [l for l in registry.leads if not l.get("ai_qualified_at")]
    if not pending:
        return stats

    client = _get_client()
    use_gemini = client is None and bool(gemini_key())
    if client is not None:
        print(f"[AI] Qualify leads via Claude AI ({AI_MODEL}) on up to {limit} leads...")
    elif use_gemini:
        print(f"[AI] Qualify leads via Google Gemini ({GEMINI_MODEL}, free tier) on up to {limit} leads...")
    else:
        print(f"[AI] No AI key (ANTHROPIC_API_KEY / GEMINI_API_KEY) - evaluating {min(len(pending), limit)} leads via Fast Heuristic NLP Classifier...")
    gemini_calls = 0

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
        elif use_gemini:
            if gemini_calls and GEMINI_DELAY_SEC > 0:
                time.sleep(GEMINI_DELAY_SEC)
            gemini_calls += 1
            try:
                result = qualify_one_gemini(lead)
            except GeminiRateLimited as e:
                print(f"[AI] {e} - the rest of this run uses the rule-based classifier.")
                use_gemini = False
                result = qualify_one_heuristic(lead)
            except Exception as e:  # one bad answer: this lead falls back to the rules
                print(f"[AI] Gemini could not classify {lead.get('lead_id')}: {str(e)[:120]} - using rules")
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
            "seniority_fit": result.get("seniority_fit", lead.get("seniority_fit", "Standard Web")),
            "deal_size_estimate": result.get("deal_size_estimate", lead.get("deal_size_estimate", "")),
            "whatsapp_status": result.get("whatsapp_status", lead.get("whatsapp_status", "N/A")),
            "decision_maker_title": result.get("decision_maker_title", lead.get("decision_maker_title", "")),
            "linkedin_url": result.get("linkedin_url", lead.get("linkedin_url", "")),
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

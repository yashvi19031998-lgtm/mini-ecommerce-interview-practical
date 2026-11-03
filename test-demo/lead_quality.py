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

import argparse
import datetime
import json
import os

import env_loader  # noqa: F401  (loads .env before reading settings below)
import slack_notifier
from lead_normalizer import MasterLeadRegistry, is_ad_url

MASTER_CSV = "all_leads_master.csv"
AI_MODEL = os.getenv("AI_QUALIFY_MODEL", "claude-opus-5-5")
AI_QUALIFY_LIMIT = int(os.getenv("AI_QUALIFY_LIMIT", "40"))  # max new leads qualified per run
MIN_AI_SCORE_FOR_AUTO_EMAIL = int(os.getenv("MIN_AI_SCORE_FOR_AUTO_EMAIL", "7"))

# Categories that represent someone who may BUY software/dev services from us
BUYER_CATEGORIES = {"client_project", "hiring_developer"}

AI_CATEGORIES = [
    "client_project",     # wants a website/app/software built (agency or freelancer welcome)
    "hiring_developer",   # hiring a developer / dev team (contract or full-time) - we can pitch staff augmentation
    "service_provider",   # agency/freelancer SELLING dev services (competitor, not a buyer)
    "job_seeker",         # person looking for work ("[FOR HIRE]")
    "job_board_or_directory",  # Indeed, Upwork listing pages, directories, aggregators
    "irrelevant",         # non-IT work, articles, dictionaries, spam, ads
]

SYSTEM_PROMPT = f"""You qualify sales leads for Sangeeta Infotech, a software agency in Ahmedabad, India \
that builds web apps, mobile apps, custom software and AI automation, and provides dedicated developers.

A good lead is a person or company that currently NEEDS software work done or wants to hire developers, \
so the agency could offer its services. Sellers of the same services, job seekers, job boards, \
directories, and non-software work (e.g. video editing, data entry, social media posting) are not leads.

Classify the lead into exactly one category:
- client_project: wants a website, app, or software built or fixed
- hiring_developer: hiring developers / a dev team (contract or full-time)
- service_provider: an agency or freelancer selling development services
- job_seeker: someone looking for work
- job_board_or_directory: a job board, listing page, marketplace or directory page rather than one buyer
- irrelevant: anything else (non-IT work, articles, ads, spam)

score (0-10) = how worthwhile this lead is for the agency to contact now: \
10 = clear, specific, current software need with a reachable contact; 0 = not a lead. \
Score service_provider, job_seeker, job_board_or_directory and irrelevant at 2 or below.

Base everything only on the text given. Use an empty string when a field is unknown; never invent budgets or tech."""

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
    )


def _lead_text(lead: dict) -> str:
    fields = [
        ("Title / company", lead.get("company_name")),
        ("Contact name", lead.get("full_name")),
        ("Description", lead.get("description")),
        ("Website", lead.get("website")),
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
        messages=[{"role": "user", "content": f"Qualify this lead:\n\n{_lead_text(lead)}"}],
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("model declined to classify this lead")
    if response.stop_reason == "max_tokens":
        raise RuntimeError("response truncated (max_tokens)")
    text = next((b.text for b in response.content if b.type == "text"), "")
    return json.loads(text)


def qualify_leads(registry: MasterLeadRegistry, limit: int = AI_QUALIFY_LIMIT) -> dict:
    stats = {"qualified": 0, "failed": 0, "skipped_no_key": False}
    pending = [l for l in registry.leads if not l.get("ai_qualified_at")]
    if not pending:
        return stats

    client = _get_client()
    if client is None:
        stats["skipped_no_key"] = True
        print(f"[AI] ANTHROPIC_API_KEY not set - {len(pending)} leads left unqualified (auto-email stays off for them).")
        return stats

    import anthropic

    # Newest leads first: they are the most likely to still be open
    pending.sort(key=lambda l: l.get("first_seen_at", ""), reverse=True)
    for lead in pending[:limit]:
        try:
            result = qualify_one(client, lead)
        except anthropic.RateLimitError:
            print("[AI] Rate limited - stopping this run; remaining leads will be qualified next run.")
            break
        except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as e:
            print(f"[AI] Credentials rejected ({e.__class__.__name__}) - stopping.")
            break
        except (anthropic.APIStatusError, anthropic.APIConnectionError, RuntimeError, json.JSONDecodeError) as e:
            stats["failed"] += 1
            print(f"[AI] {lead.get('lead_id')}: {e}")
            continue

        score = max(0, min(10, int(result.get("score", 0))))
        lead.update({
            "ai_category": result.get("category", ""),
            "ai_score": str(score),
            "ai_summary": result.get("summary", "")[:300],
            "ai_requirement": result.get("requirement", "")[:300],
            "ai_tech_stack": result.get("tech_stack", "")[:150],
            "ai_budget": result.get("budget", "")[:100],
            "ai_reason": result.get("reason", "")[:300],
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
    print(f"[QUALITY] {stats}")
    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--clean-only", action="store_true", help="skip AI qualification")
    parser.add_argument("--limit", type=int, default=AI_QUALIFY_LIMIT, help="max leads to AI-qualify this run")
    parser.add_argument("--csv", default=MASTER_CSV)
    args = parser.parse_args()
    run(args.csv, limit=args.limit, use_ai=not args.clean_only)

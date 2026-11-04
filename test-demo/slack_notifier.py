"""
Post AI-qualified hot leads to a Slack channel via an Incoming Webhook.

Setup (one time):
  1. https://api.slack.com/apps -> Create App -> Incoming Webhooks -> On -> "Add New Webhook"
     -> choose the channel (e.g. #leads) -> copy the URL.
  2. Put it in .env (local) and as a GitHub Actions secret:  SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
     Treat the URL like a password: anyone with it can post to your channel.

Usage:
    python slack_notifier.py            # post any hot leads not yet posted
    python slack_notifier.py --test     # send one test message to check the webhook

Called automatically by lead_quality.run() after AI qualification.
"""

import argparse
import datetime
import os
import time

import requests

import env_loader  # noqa: F401  (loads .env before reading settings below)
from lead_normalizer import lead_age_days

SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "").strip()
MIN_AI_SCORE_FOR_SLACK = int(os.getenv("MIN_AI_SCORE_FOR_SLACK", "7"))
SLACK_MAX_PER_RUN = int(os.getenv("SLACK_MAX_PER_RUN", "20"))  # avoid flooding the channel on backfills
STALE_AFTER_DAYS = int(os.getenv("STALE_AFTER_DAYS", "14"))  # same setting as lead_quality.py

# prospect_signal (e.g. a startup that just raised funding) is alerted but never auto-emailed
BUYER_CATEGORIES = {"client_project", "hiring_developer", "prospect_signal"}
CATEGORY_LABELS = {"client_project": "Client project", "hiring_developer": "Hiring developers",
                   "prospect_signal": "Prospect (trigger event)"}


def _esc(text) -> str:
    """Escape the three characters Slack treats as control characters in mrkdwn."""
    return str(text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _score(lead: dict) -> int:
    try:
        return int(float(lead.get("ai_score") or 0))
    except ValueError:
        return 0


def is_hot_lead(lead: dict) -> bool:
    """AI-qualified, still-fresh buyer with a high score. Email not required - Reddit/phone leads count too."""
    age = lead_age_days(lead)
    if age is not None and age > STALE_AFTER_DAYS:
        return False
    return lead.get("ai_category") in BUYER_CATEGORIES and _score(lead) >= MIN_AI_SCORE_FOR_SLACK


def _contact_line(lead: dict) -> str:
    parts = []
    if lead.get("email"):
        parts.append(f"✉️ {_esc(lead['email'].split(',')[0].strip())}")
    if lead.get("mobile_number"):
        parts.append(f"📞 {_esc(lead['mobile_number'].split(',')[0].strip())}")
    link = lead.get("source_url") or lead.get("website")
    if link:
        if "reddit.com" in link:
            label = "Reddit post"
        elif "freelancer.com" in link:
            label = "Bid on Freelancer.com"
        elif "ycombinator.com" in link:
            label = "HN post"
        else:
            label = "Open source"
        parts.append(f"<{link}|{label}>")
    return "  •  ".join(parts) or "_No direct contact found_"


def build_message(lead: dict) -> dict:
    score = _score(lead)
    title = _esc(lead.get("company_name") or lead.get("full_name") or "New lead")[:150]
    category = CATEGORY_LABELS.get(lead.get("ai_category"), lead.get("ai_category", ""))
    details = [
        f"*Need:* {_esc(lead.get('ai_requirement') or lead.get('ai_summary'))}",
    ]
    if lead.get("ai_tech_stack"):
        details.append(f"*Tech:* {_esc(lead['ai_tech_stack'])}")
    if lead.get("ai_budget"):
        details.append(f"*Budget:* {_esc(lead['ai_budget'])}")
    if lead.get("location"):
        details.append(f"*Location:* {_esc(lead['location'])}")

    fallback_text = f"🔥 Hot lead ({score}/10): {lead.get('company_name', '')}"
    return {
        "text": fallback_text,  # shown in notifications / when blocks can't render
        "blocks": [
            {"type": "header", "text": {"type": "plain_text", "text": f"🔥 {score}/10 · {category}", "emoji": True}},
            {"type": "section", "text": {"type": "mrkdwn", "text": f"*{title}*\n{_esc(lead.get('ai_summary'))}"}},
            {"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(details)}},
            {"type": "section", "text": {"type": "mrkdwn", "text": _contact_line(lead)}},
            {"type": "context", "elements": [{"type": "mrkdwn", "text":
                f"{_esc(lead.get('lead_id'))} · {_esc((lead.get('source') or '')[:80])} · AI: {_esc(lead.get('ai_reason'))[:200]}"}]},
        ],
    }


def post_to_slack(payload: dict, webhook_url: str = None) -> bool:
    url = webhook_url or SLACK_WEBHOOK_URL
    try:
        r = requests.post(url, json=payload, timeout=10)
    except requests.RequestException as e:
        print(f"[SLACK] Network error: {e}")
        return False
    if r.status_code == 429:  # rate limited - Slack says how long to wait
        wait = int(r.headers.get("Retry-After", "1"))
        time.sleep(min(wait, 30))
        return post_to_slack(payload, webhook_url)
    if r.status_code != 200:
        print(f"[SLACK] Failed ({r.status_code}): {r.text[:200]}")
        return False
    return True


def notify_hot_leads(leads: list, limit: int = SLACK_MAX_PER_RUN) -> dict:
    """Posts hot leads not yet posted; marks each with slack_notified_at. Mutates the dicts."""
    stats = {"slack_posted": 0, "slack_failed": 0}
    if not SLACK_WEBHOOK_URL:
        return stats

    pending = [l for l in leads if is_hot_lead(l) and not l.get("slack_notified_at")]
    pending.sort(key=lambda l: (_score(l), l.get("first_seen_at", "")), reverse=True)

    for lead in pending[:limit]:
        if post_to_slack(build_message(lead)):
            lead["slack_notified_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            stats["slack_posted"] += 1
            time.sleep(1)  # Slack webhooks allow ~1 message/second
        else:
            stats["slack_failed"] += 1
    if len(pending) > limit:
        print(f"[SLACK] {len(pending) - limit} more hot leads will be posted in the next runs.")
    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--test", action="store_true", help="send a test message")
    args = parser.parse_args()

    if not SLACK_WEBHOOK_URL:
        raise SystemExit("SLACK_WEBHOOK_URL is not set (add it to .env).")
    if args.test:
        ok = post_to_slack({"text": "✅ Lead bot connected. Hot leads will appear here."})
        print("Test message sent." if ok else "Test message failed.")
    else:
        from lead_normalizer import MasterLeadRegistry
        reg = MasterLeadRegistry("all_leads_master.csv")
        print(notify_hot_leads(reg.leads))
        reg.save_master_safely()

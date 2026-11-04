"""
Freelancer.com live projects via the official public API (no key needed for search).

Every project here is a real client asking for work, with a budget. Note: Freelancer.com's
terms require you to contact these clients through the platform (place a bid) - the lead's
link opens the project page for that. Do not cold-email them off-platform.

Settings (.env):
    FREELANCER_QUERIES=website,mobile app,web application,...   (comma-separated)
    FREELANCER_MIN_BUDGET_USD=250     fixed-price projects below this are skipped
    FREELANCER_MIN_HOURLY_USD=15      hourly projects below this rate are skipped
    FREELANCER_MAX_BIDS=60            skip projects that already have this many bids

    python freelancer_api_scraper.py   # dry run
"""

import datetime
import os
import time
from typing import Any, Dict, List, Optional

import requests

import env_loader  # noqa: F401
from lead_normalizer import MAX_DESCRIPTION_CHARS

API = "https://www.freelancer.com/api/projects/0.1/projects/active/"
DEFAULT_QUERIES = [
    "website development", "web application", "mobile app", "flutter", "react native", "react",
    "python", "laravel", "saas", "mvp", "ai automation", "chatbot", "ecommerce website",
]
QUERIES = [q.strip() for q in os.getenv("FREELANCER_QUERIES", "").split(",") if q.strip()] or DEFAULT_QUERIES
MIN_BUDGET_USD = float(os.getenv("FREELANCER_MIN_BUDGET_USD", "250"))
MIN_HOURLY_USD = float(os.getenv("FREELANCER_MIN_HOURLY_USD", "15"))
MAX_BIDS = int(os.getenv("FREELANCER_MAX_BIDS", "60"))
MAX_AGE_DAYS = 3
PER_QUERY = 30

# Freelancer's text search is loose ("website" also matches SEO, translation or admin jobs).
# Each skill on a project carries Freelancer's own category, so we require that at least half of
# the project's skills are in software categories.
SOFTWARE_CATEGORIES = {"Websites, IT & Software", "Mobile Phones & Computing", "Artificial Intelligence"}


def has_software_skill(project: Dict[str, Any]) -> bool:
    jobs = project.get("jobs") or []
    if not jobs:
        return False
    software = sum(1 for j in jobs if ((j.get("category") or {}).get("name")) in SOFTWARE_CATEGORIES)
    return software * 2 >= len(jobs)


def budget_usd(project: Dict[str, Any]) -> Optional[float]:
    """Upper budget converted to USD (Freelancer gives an exchange_rate per currency)."""
    budget = project.get("budget") or {}
    amount = budget.get("maximum") or budget.get("minimum")
    rate = (project.get("currency") or {}).get("exchange_rate")
    if amount is None or not rate:
        return None
    return float(amount) * float(rate)


def is_worthwhile(project: Dict[str, Any]) -> bool:
    if not has_software_skill(project):
        return False
    usd = budget_usd(project)
    if usd is None:
        return False
    if project.get("type") == "hourly":
        if usd < MIN_HOURLY_USD:
            return False
    elif usd < MIN_BUDGET_USD:
        return False
    bids = (project.get("bid_stats") or {}).get("bid_count") or 0
    if bids >= MAX_BIDS:
        return False
    submitted = project.get("time_submitted")
    if submitted:
        age = datetime.datetime.now() - datetime.datetime.fromtimestamp(submitted)
        if age.days > MAX_AGE_DAYS:
            return False
    return True


def project_to_lead(project: Dict[str, Any]) -> Dict[str, Any]:
    budget = project.get("budget") or {}
    currency = (project.get("currency") or {}).get("code", "")
    kind = "per hour" if project.get("type") == "hourly" else "fixed"
    skills = ", ".join(j.get("name", "") for j in (project.get("jobs") or [])[:8])
    bids = (project.get("bid_stats") or {}).get("bid_count") or 0
    location = ((project.get("location") or {}).get("country") or {}).get("name", "")
    header = (f"Budget: {budget.get('minimum')}-{budget.get('maximum')} {currency} ({kind}, "
              f"~USD {budget_usd(project):.0f}). Bids so far: {bids}. Skills: {skills}.")
    submitted = project.get("time_submitted")
    return {
        "company_name": project.get("title", "")[:200],
        "description": f"{header}\n{project.get('description') or project.get('preview_description') or ''}"[:MAX_DESCRIPTION_CHARS],
        "source": "Freelancer.com (API)",
        "source_url": f"https://www.freelancer.com/projects/{project.get('seo_url')}",
        "location": location,
        "lead_type": "Freelance Project",
        "posted_at": str(submitted) if submitted else "",  # epoch seconds; normalizer converts
    }


def run_freelancer_adapter() -> List[Dict[str, Any]]:
    seen, leads = set(), []
    for query in QUERIES:
        try:
            r = requests.get(API, params={"query": query, "limit": PER_QUERY, "full_description": "true",
                                          "job_details": "true", "location_details": "true",
                                          "sort_field": "time_updated"}, timeout=20)
            if r.status_code == 429:
                print("       [Freelancer] rate limited - stopping for this run")
                break
            r.raise_for_status()
            projects = (r.json().get("result") or {}).get("projects") or []
        except (requests.RequestException, ValueError) as e:
            print(f"       [Freelancer] '{query}': {e}")
            continue
        new = [p for p in projects if p.get("id") not in seen and is_worthwhile(p)]
        seen.update(p.get("id") for p in projects)
        leads.extend(project_to_lead(p) for p in new)
        print(f"       [Freelancer] '{query}': {len(new)} worthwhile of {len(projects)}")
        time.sleep(1.5)
    return leads


if __name__ == "__main__":
    found = run_freelancer_adapter()
    print(f"\n{len(found)} projects")
    for lead in found[:15]:
        print(f" - {lead['company_name'][:70]} | {lead['description'][:60]}")

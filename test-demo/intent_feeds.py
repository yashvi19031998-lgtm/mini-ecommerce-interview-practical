"""
Built-in buyer-intent feeds - work out of the box, no account or token needed.

Groups
- Reddit, all of it: posts saying "looking for a developer", "need an app built", ...
- Reddit, founder/business subs (r/startups, r/SaaS, r/smallbusiness, r/Entrepreneur, r/hiring)
- Startup funding news (Inc42, YourStory): a company that just raised money usually needs to
  build product -> "prospect signal" leads (Slack alert only, never auto-emailed)

Add your own feeds (e.g. Google Alerts -> "Deliver to: RSS feed") with FEEDLY_FEEDS; those are
read by feedly_scraper.py. Turn this module off with INTENT_FEEDS_ENABLED=false.

    python intent_feeds.py     # dry run
"""

import os
import time
import urllib.parse
from typing import Any, Dict, List

import requests
import xml.etree.ElementTree as ET

import env_loader  # noqa: F401
from feedly_scraper import fetch_rss

ENABLED = os.getenv("INTENT_FEEDS_ENABLED", "true").lower() in ("1", "true", "yes")
REQUEST_GAP_SECONDS = 4  # Reddit rate-limits fast unauthenticated requests (HTTP 429)

BUYER_PHRASES = [
    '"looking for a developer"', '"looking for an app developer"', '"looking for a web developer"',
    '"need a developer"', '"need an app built"', '"need a website built"', '"looking for a dev agency"',
    '"looking for a development agency"', '"hire a developer"', '"technical cofounder or agency"',
]

FOR_HIRE_EXCLUDE = ["[for hire]", "for hire", "hire me", "available for work", "my portfolio",
                    "i am a developer looking", "i'm a developer looking", "offering my services",
                    "[available]", "seeking freelance", "seeking work", "open to work", "looking for work",
                    "looking for freelance projects", "looking for projects", "i built", "i've built", "we built",
                    "open-source", "open source", "show hn", "launched my"]

BUYER_INCLUDE = [
    "looking for a developer", "looking for an app developer", "looking for a web developer",
    "looking for developer", "need a developer", "need developer", "need an app", "need a website",
    "build an app", "build a website", "build my", "dev agency", "development agency", "hire a developer",
    "hiring", "mvp", "freelance developer", "outsource", "technical cofounder", "budget",
]

FUNDING_INCLUDE = ["raises", "raised", "funding", "seed round", "pre-seed", "series a", "series b",
                   "secures", "bags", "investment led by"]


def _reddit_search(query: str, subreddits: str = "") -> str:
    q = urllib.parse.quote(query)
    if subreddits:
        return f"https://www.reddit.com/r/{subreddits}/search.rss?q={q}&restrict_sr=1&sort=new&t=week"
    return f"https://www.reddit.com/search.rss?q={q}&sort=new&t=week"


FEED_GROUPS = [
    {
        "name": "Reddit buyer search",
        "urls": [
            _reddit_search(" OR ".join(BUYER_PHRASES[:5])),
            _reddit_search(" OR ".join(BUYER_PHRASES[5:])),
        ],
        "include": BUYER_INCLUDE, "exclude": FOR_HIRE_EXCLUDE,
        "max_age_days": 7, "source_prefix": "Reddit search", "lead_type": "Feed Post",
    },
    {
        "name": "Founder & business subreddits",
        "urls": [_reddit_search("developer OR agency OR \"build an app\" OR \"build a website\" OR MVP",
                                "startups+SaaS+smallbusiness+Entrepreneur+hiring")],
        "include": BUYER_INCLUDE, "exclude": FOR_HIRE_EXCLUDE,
        "max_age_days": 7, "source_prefix": "Reddit", "lead_type": "Feed Post",
    },
    {
        "name": "Startup funding news",
        "urls": ["https://inc42.com/feed/", "https://yourstory.com/feed"],
        "include": FUNDING_INCLUDE, "exclude": [],
        "max_age_days": 14, "source_prefix": "Funding news", "lead_type": "Funding News",
    },
]


def run_intent_feeds_adapter() -> List[Dict[str, Any]]:
    if not ENABLED:
        print("       [intent-feeds] disabled (INTENT_FEEDS_ENABLED=false)")
        return []
    leads: List[Dict[str, Any]] = []
    for group in FEED_GROUPS:
        options = {k: group[k] for k in ("include", "exclude", "max_age_days", "source_prefix", "lead_type")}
        for url in group["urls"]:
            try:
                got = fetch_rss(url, **options)
                print(f"       [intent-feeds] {group['name']}: {len(got)} matching posts")
                leads.extend(got)
            except (requests.RequestException, ET.ParseError) as e:
                print(f"       [intent-feeds] {group['name']}: {e}")
            time.sleep(REQUEST_GAP_SECONDS)
    return leads


if __name__ == "__main__":
    found = run_intent_feeds_adapter()
    print(f"\n{len(found)} posts found")
    for lead in found[:20]:
        print(f" - [{lead['lead_type']}] {lead['company_name'][:85]}")

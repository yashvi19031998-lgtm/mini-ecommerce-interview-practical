"""
Hacker News monthly hiring threads (official Algolia HN API - free, no key).

- "Ask HN: Who is hiring?" (1st weekday of each month): companies post one top-level comment
  each. We keep only posts open to CONTRACT / FREELANCE / AGENCY / part-time work - the ones an
  agency can actually sell to (staff augmentation or project work).
- "Ask HN: Freelancer? Seeking freelancer?" - discontinued after Oct 2025, but picked up
  automatically if HN brings it back. Only "SEEKING FREELANCER" posts are kept.

    python hn_hiring_scraper.py    # dry run
"""

import datetime
import html
import re
from typing import Any, Dict, List

import requests

from lead_normalizer import MAX_DESCRIPTION_CHARS

API = "https://hn.algolia.com/api/v1"
THREAD_MAX_AGE_DAYS = 40   # current month's thread (and last month's for a few days)
MAX_COMMENTS_PER_THREAD = 1000

CONTRACT_MARKERS = [
    "contract", "contractor", "freelance", "freelancer", "part-time", "part time", "agency",
    "agencies", "consultant", "consulting", "outsourc", "project-based", "project based", "c2c",
]
EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)*\.[a-zA-Z]{2,}")


def _clean(comment_html: str) -> str:
    text = re.sub(r"<p>|<br\s*/?>", "\n", comment_html or "")
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"[ \t]+", " ", html.unescape(text)).strip()


def find_threads(max_age_days: int = THREAD_MAX_AGE_DAYS) -> List[Dict[str, Any]]:
    r = requests.get(f"{API}/search_by_date", params={"tags": "story,author_whoishiring", "hitsPerPage": 12},
                     timeout=20)
    r.raise_for_status()
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=max_age_days)
    threads = []
    for hit in r.json().get("hits", []):
        title = hit.get("title", "")
        created = datetime.datetime.fromisoformat(hit["created_at"].replace("Z", "+00:00"))
        if created < cutoff:
            continue
        if title.startswith("Ask HN: Who is hiring?"):
            threads.append({"id": hit["objectID"], "title": title, "kind": "hiring"})
        elif title.startswith("Ask HN: Freelancer? Seeking freelancer?"):
            threads.append({"id": hit["objectID"], "title": title, "kind": "freelancer"})
    return threads


def fetch_top_level_comments(story_id: str) -> List[Dict[str, Any]]:
    r = requests.get(f"{API}/search_by_date",
                     params={"tags": f"comment,story_{story_id}", "hitsPerPage": MAX_COMMENTS_PER_THREAD},
                     timeout=30)
    r.raise_for_status()
    return [h for h in r.json().get("hits", []) if str(h.get("parent_id")) == str(story_id)]


def comment_to_lead(hit: Dict[str, Any], thread: Dict[str, Any]) -> Dict[str, Any]:
    text = _clean(hit.get("comment_text", ""))
    first_line = text.split("\n", 1)[0]
    company = first_line.split("|")[0].strip()[:120] or first_line[:120]
    return {
        "company_name": company,
        "description": text[:MAX_DESCRIPTION_CHARS],
        "source": f"Hacker News ({thread['title'].replace('Ask HN: ', '')})",
        "source_url": f"https://news.ycombinator.com/item?id={hit['objectID']}",
        "email": ", ".join(sorted(set(EMAIL_RE.findall(text)))),
        "full_name": hit.get("author", ""),
        "lead_type": "HN Hiring Post",
        "posted_at": hit.get("created_at", ""),
        "location": "Remote" if "remote" in first_line.lower() else "",
    }


def is_relevant(hit: Dict[str, Any], kind: str) -> bool:
    text = _clean(hit.get("comment_text", "")).lower()
    if kind == "freelancer":
        return text.startswith("seeking freelancer")
    return any(m in text for m in CONTRACT_MARKERS)


def run_hn_hiring_adapter() -> List[Dict[str, Any]]:
    leads: List[Dict[str, Any]] = []
    try:
        threads = find_threads()
    except (requests.RequestException, ValueError) as e:
        print(f"       [HN] could not list threads: {e}")
        return leads
    for thread in threads:
        try:
            comments = fetch_top_level_comments(thread["id"])
        except (requests.RequestException, ValueError) as e:
            print(f"       [HN] {thread['title']}: {e}")
            continue
        kept = [comment_to_lead(c, thread) for c in comments if is_relevant(c, thread["kind"])]
        print(f"       [HN] {thread['title']}: {len(kept)} of {len(comments)} posts open to contract/freelance work")
        leads.extend(kept)
    return leads


if __name__ == "__main__":
    found = run_hn_hiring_adapter()
    print(f"\n{len(found)} leads")
    for lead in found[:15]:
        print(f" - {lead['company_name'][:70]}  ->  {lead['source_url']}")

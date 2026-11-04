"""
Feedly lead source:  Feedly (or plain RSS) -> keyword pre-filter -> master CSV -> AI -> Slack

Two modes, picked automatically:

1. Feedly API mode  (needs a Feedly API token - per Feedly's docs, self-service tokens are
   Enterprise-only: https://feedly.com/i/team/api)
       FEEDLY_ACCESS_TOKEN=...
       FEEDLY_STREAM_IDS=feed/https://www.reddit.com/r/forhire/new/.rss,enterprise/<team>/category/<uuid>
   (comma-separated stream IDs: a feed is "feed/<rss url>"; a team folder id comes from
    GET /v3/enterprise/collections)

2. Direct RSS mode  (free - no token). Feedly only aggregates RSS feeds, so we read the same feeds:
       Feedly -> Organize -> Export OPML -> save as feedly_feeds.opml in this folder
   and/or list feeds directly:
       FEEDLY_FEEDS=https://www.reddit.com/r/forhire/new/.rss,https://weworkremotely.com/remote-jobs.rss

Only articles that look like someone NEEDS software work (keyword pre-filter) become leads;
the AI step in lead_quality.py then scores them, and hot ones go to Slack.

    python feedly_scraper.py      # dry run: prints what would be collected
"""

import datetime
import email.utils
import os
import re
import time
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

import requests

import env_loader  # noqa: F401  (loads .env before reading settings below)
from lead_normalizer import MAX_DESCRIPTION_CHARS

FEEDLY_API_BASE = os.getenv("FEEDLY_API_BASE", "https://api.feedly.com/v3").rstrip("/")
FEEDLY_ACCESS_TOKEN = os.getenv("FEEDLY_ACCESS_TOKEN", "").strip()
FEEDLY_STREAM_IDS = [s.strip() for s in os.getenv("FEEDLY_STREAM_IDS", "").split(",") if s.strip()]
FEEDLY_OPML_FILE = os.getenv("FEEDLY_OPML_FILE", "feedly_feeds.opml")
FEEDLY_FEEDS = [s.strip() for s in os.getenv("FEEDLY_FEEDS", "").split(",") if s.strip()]
FEEDLY_MAX_AGE_DAYS = min(int(os.getenv("FEEDLY_MAX_AGE_DAYS", "7")), 31)  # API refuses newerThan > 31 days
FEEDLY_MAX_PAGES = int(os.getenv("FEEDLY_MAX_PAGES", "3"))  # x100 articles per stream per run

USER_AGENT = "Mozilla/5.0 (compatible; LeadHarvester/1.0)"

# A post must match at least one of these (case-insensitive) to be kept.
DEFAULT_INTENT_KEYWORDS = [
    "looking for a developer", "looking for developer", "looking for a dev", "need a developer",
    "need developer", "need a website", "need an app", "hiring", "[hiring]", "seeking developer",
    "looking for an agency", "looking for agency", "development partner", "rfp", "request for proposal",
    "tender", "freelancer needed", "build an app", "build a website", "mvp", "outsource",
]
INTENT_KEYWORDS = [k.strip().lower() for k in os.getenv("FEEDLY_KEYWORDS", "").split(",") if k.strip()] \
    or DEFAULT_INTENT_KEYWORDS
# Posts by people OFFERING services are skipped before the AI step
EXCLUDE_KEYWORDS = ["[for hire]", "for hire", "available for work", "my portfolio", "hire me"]

EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)*\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"\+?\d[\d\s\-()]{8,15}\d")
TAG_RE = re.compile(r"<[^>]+>")


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _strip_html(html: str) -> str:
    return re.sub(r"\s+", " ", TAG_RE.sub(" ", html or "")).strip()


def is_lead_like(title: str, text: str, include=None, exclude=None) -> bool:
    """Keyword pre-filter. include/exclude default to the buyer-intent lists above."""
    blob = f"{title} {text}".lower()
    if any(x in blob for x in (EXCLUDE_KEYWORDS if exclude is None else exclude)):
        return False
    return any(k in blob for k in (INTENT_KEYWORDS if include is None else include))


def to_raw_lead(title: str, text: str, link: str, source_name: str, published: Optional[datetime.datetime],
                source_prefix: str = "Feedly", lead_type: str = "Feed Post") -> Dict[str, Any]:
    """Shape an article into the raw-record format lead_normalizer understands."""
    plain = _strip_html(text)
    return {
        "company_name": _strip_html(title)[:200],
        "description": plain[:MAX_DESCRIPTION_CHARS],
        "source": f"{source_prefix} ({source_name})" if source_name else source_prefix,
        "source_url": link,
        "email": ", ".join(sorted(set(EMAIL_RE.findall(plain)))),
        "Phone": ", ".join(PHONE_RE.findall(plain)[:2]),
        "lead_type": lead_type,
        "posted_at": published.strftime("%Y-%m-%d %H:%M:%S") if published else "",
    }


def _cutoff(max_age_days: float = None) -> datetime.datetime:
    days = FEEDLY_MAX_AGE_DAYS if max_age_days is None else max_age_days
    return datetime.datetime.now() - datetime.timedelta(days=days)


# ---------------------------------------------------------------------------
# Mode 1: Feedly API
# ---------------------------------------------------------------------------

def fetch_feedly_stream(stream_id: str, token: str = None) -> List[Dict[str, Any]]:
    token = token or FEEDLY_ACCESS_TOKEN
    newer_than = int(_cutoff().timestamp() * 1000)
    leads, continuation = [], None

    for _ in range(FEEDLY_MAX_PAGES):
        # The docs spell this param both "streamId" and "streamID"; send both.
        params = {"streamId": stream_id, "streamID": stream_id, "count": 100, "newerThan": newer_than}
        if continuation:
            params["continuation"] = continuation
        r = requests.get(f"{FEEDLY_API_BASE}/streams/contents", params=params,
                         headers={"Authorization": f"Bearer {token}"}, timeout=20)
        if r.status_code == 401:
            raise RuntimeError("Feedly token invalid or expired (401) - create a new one at feedly.com/i/team/api")
        if r.status_code == 429:
            reset = r.headers.get("X-RateLimit-Reset", "?")
            raise RuntimeError(f"Feedly rate limit reached (429) - resets in {reset}s")
        r.raise_for_status()
        data = r.json()

        for item in data.get("items", []):
            title = item.get("title", "")
            text = ((item.get("fullContent") if isinstance(item.get("fullContent"), str) else "")
                    or (item.get("content") or {}).get("content", "")
                    or (item.get("summary") or {}).get("content", ""))
            if not is_lead_like(title, text):
                continue
            link = item.get("canonicalUrl") or next(
                (a.get("href") for a in item.get("alternate", []) if a.get("href")), "") or item.get("originId", "")
            published = item.get("published") or item.get("crawled")
            pub_dt = datetime.datetime.fromtimestamp(published / 1000) if published else None
            leads.append(to_raw_lead(title, text, link, (item.get("origin") or {}).get("title", ""), pub_dt))

        continuation = data.get("continuation")
        if not continuation:
            break
    return leads


# ---------------------------------------------------------------------------
# Mode 2: direct RSS / Atom (feeds from Feedly's OPML export or FEEDLY_FEEDS)
# ---------------------------------------------------------------------------

def read_opml(path: str) -> List[str]:
    if not os.path.exists(path):
        return []
    tree = ET.parse(path)
    return [o.get("xmlUrl") for o in tree.iter("outline") if o.get("xmlUrl")]


def _parse_date(value: str) -> Optional[datetime.datetime]:
    if not value:
        return None
    try:  # RSS: RFC 822
        return email.utils.parsedate_to_datetime(value).astimezone().replace(tzinfo=None)
    except (TypeError, ValueError):
        pass
    try:  # Atom: ISO 8601
        return datetime.datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone().replace(tzinfo=None)
    except ValueError:
        return None


def parse_feed_xml(xml_text: str, feed_url: str = "", include=None, exclude=None, max_age_days: float = None,
                   source_prefix: str = "Feedly", lead_type: str = "Feed Post") -> List[Dict[str, Any]]:
    """Parses RSS 2.0 or Atom XML into raw leads (after keyword + age filtering)."""
    root = ET.fromstring(xml_text)
    atom = "{http://www.w3.org/2005/Atom}"
    feed_title = (root.findtext("channel/title") or root.findtext(f"{atom}title") or feed_url).strip()
    cutoff = _cutoff(max_age_days)
    leads = []
    shape = dict(source_prefix=source_prefix, lead_type=lead_type)

    for item in root.iter("item"):  # RSS 2.0
        title = item.findtext("title") or ""
        text = item.findtext("description") or item.findtext("{http://purl.org/rss/1.0/modules/content/}encoded") or ""
        pub = _parse_date(item.findtext("pubDate") or "")
        if (pub and pub < cutoff) or not is_lead_like(title, text, include, exclude):
            continue
        leads.append(to_raw_lead(title, text, item.findtext("link") or "", feed_title, pub, **shape))

    for entry in root.iter(f"{atom}entry"):  # Atom (Reddit uses this)
        title = entry.findtext(f"{atom}title") or ""
        text = entry.findtext(f"{atom}content") or entry.findtext(f"{atom}summary") or ""
        pub = _parse_date(entry.findtext(f"{atom}published") or entry.findtext(f"{atom}updated") or "")
        if (pub and pub < cutoff) or not is_lead_like(title, text, include, exclude):
            continue
        link_el = entry.find(f"{atom}link")
        link = link_el.get("href", "") if link_el is not None else ""
        leads.append(to_raw_lead(title, text, link, feed_title, pub, **shape))
    return leads


def fetch_feed_text(feed_url: str, retries: int = 2) -> str:
    """GET a feed. On HTTP 429 (rate limited) waits as the server asks (max 60s) and retries."""
    for attempt in range(retries + 1):
        r = requests.get(feed_url, headers={"User-Agent": USER_AGENT}, timeout=15)
        if r.status_code == 429 and attempt < retries:
            retry_after = r.headers.get("Retry-After", "")
            wait = min(int(retry_after), 60) if retry_after.isdigit() else 15 * (attempt + 1)
            print(f"       [feeds] rate limited by {feed_url.split('/')[2]}, waiting {wait}s...")
            time.sleep(wait)
            continue
        r.raise_for_status()
        return r.text
    r.raise_for_status()
    return r.text


def fetch_rss(feed_url: str, **parse_options) -> List[Dict[str, Any]]:
    return parse_feed_xml(fetch_feed_text(feed_url), feed_url, **parse_options)


# ---------------------------------------------------------------------------
# Entry point used by run_all_scrapers.py
# ---------------------------------------------------------------------------

def run_feedly_adapter() -> List[Dict[str, Any]]:
    leads: List[Dict[str, Any]] = []

    if FEEDLY_ACCESS_TOKEN and FEEDLY_STREAM_IDS:
        print(f"       [Feedly] API mode: {len(FEEDLY_STREAM_IDS)} stream(s)")
        for sid in FEEDLY_STREAM_IDS:
            try:
                got = fetch_feedly_stream(sid)
                print(f"       [Feedly] {sid[:70]}: {len(got)} lead-like posts")
                leads.extend(got)
            except (requests.RequestException, RuntimeError, ValueError) as e:
                print(f"       [Feedly] {sid[:70]}: {e}")
        return leads

    feeds = list(dict.fromkeys(FEEDLY_FEEDS + read_opml(FEEDLY_OPML_FILE)))  # dedupe, keep order
    if not feeds:
        print("       [Feedly] Not configured: set FEEDLY_ACCESS_TOKEN + FEEDLY_STREAM_IDS, "
              f"or export OPML to {FEEDLY_OPML_FILE}, or set FEEDLY_FEEDS.")
        return leads

    print(f"       [Feedly] RSS mode: {len(feeds)} feed(s)")
    for url in feeds:
        try:
            got = fetch_rss(url)
            print(f"       [Feedly] {url[:70]}: {len(got)} lead-like posts")
            leads.extend(got)
        except (requests.RequestException, ET.ParseError) as e:
            print(f"       [Feedly] {url[:70]}: {e}")
        time.sleep(1)  # be polite to feed hosts
    return leads


if __name__ == "__main__":
    found = run_feedly_adapter()
    print(f"\n{len(found)} lead-like posts found")
    for lead in found[:15]:
        print(f" - {lead['company_name'][:90]}  ->  {lead['source_url']}")

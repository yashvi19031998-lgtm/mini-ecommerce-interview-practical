"""
Competitor Client Harvester
===========================
Discovers and extracts active, paying clients of competing IT & software agencies
via agency footer footprints ("Designed & Developed by", "Website Developed by"),
client case studies, and public portfolio indexations.

Why this yields the highest-conversion leads:
1. Client already has a software budget and pays an agency.
2. Client already understands software development & maintenance.
3. Sangeeta Infotech pitches dedicated developers starting at ₹450/- INR / hour,
   which is 30-50% more cost-effective than standard agency retainers.
"""

import os
import re
import time
import random
import urllib.parse
from typing import List, Dict, Any, Set

try:
    import scraper
    SEARCH_WEB_FUNC = scraper.search_web
except Exception:
    SEARCH_WEB_FUNC = None

try:
    from duckduckgo_search import DDGS
except ImportError:
    try:
        from ddgs import DDGS
    except ImportError:
        DDGS = None

from lead_normalizer import MAX_DESCRIPTION_CHARS

# Major IT & Web Development Agencies (Ahmedabad, Gujarat & Pan-India)
DEFAULT_COMPETITORS = [
    "Hyperlink InfoSystem",
    "Hidden Brains",
    "OpenXcell",
    "Radixweb",
    "Simform",
    "Bacancy",
    "Mindinventory",
    "Agile Infoways",
    "The One Technologies",
    "Space-O Technologies",
    "TatvaSoft",
    "Krish TechnoLabs",
    "ZealousWeb",
    "DevsTree",
    "Brainvire",
    "E2M Solutions",
    "Elsner Technologies",
    "Techugo",
    "Appinventiv",
    "RipenApps"
]

FOOTPRINT_TEMPLATES = [
    '"{footprint}" "{competitor}"',
    '"{footprint}" "{competitor}" -site:{competitor_domain}'
]

FOOTPRINTS = [
    "Designed & Developed by",
    "Website Developed by",
    "Website Designed by",
    "Developed by",
    "Web Design by",
    "Crafted by",
    "Powered by",
    "Built by"
]

# Domains that are platforms, dictionaries, directories, or competitor self-domains (NOT client sites)
EXCLUDED_DOMAINS = {
    "linkedin.com", "facebook.com", "twitter.com", "x.com", "instagram.com",
    "youtube.com", "pinterest.com", "github.com", "gitlab.com", "medium.com",
    "clutch.co", "goodfirms.co", "glassdoor.com", "indeed.com", "ambitionbox.com",
    "google.com", "bing.com", "yahoo.com", "duckduckgo.com", "wikipedia.org",
    "justdial.com", "indiamart.com", "tradeindia.com", "sulekha.com", "yellowpages.com",
    "dictionary.com", "cambridge.org", "collinsdictionary.com", "thesaurus.com",
    "merriam-webster.com", "usdictionary.com", "askdifference.com", "britannica.com",
    "w3schools.com", "geeksforgeeks.org", "tutorialspoint.com", "thefreedictionary.com"
}


def _clean_competitor_slug(name: str) -> str:
    """e.g. 'Hyperlink InfoSystem' -> 'hyperlinkinfosystem.com'"""
    s = re.sub(r"[^a-zA-Z0-9]", "", name).lower()
    return f"{s}.com"


def _extract_domain(url: str) -> str:
    try:
        parsed = urllib.parse.urlparse(url)
        netloc = parsed.netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return netloc
    except Exception:
        return ""


def _is_client_url(url: str, competitor: str) -> bool:
    """Returns True if the URL is likely a real client website and not a directory/competitor page."""
    if not url or not url.startswith("http"):
        return False
    domain = _extract_domain(url)
    if not domain or len(domain) < 4:
        return False

    # Exclude major aggregators, platforms, tech brands, and dictionaries
    if any(ex in domain for ex in EXCLUDED_DOMAINS):
        return False

    # Exclude government and educational institutions
    if re.search(r"\.(gov|mil|edu|nic|ac)(\.[a-z]{2,3})?$", domain) or "gov" in domain or "edu" in domain:
        return False

    # Exclude mega tech platforms & vocabulary/reference sites
    if any(b in domain for b in ("whatsapp.com", "apple.com", "microsoft.com", "google.com", "web.dev", "w3.org", "mozilla.org", "android.com", "vocabulary.com", "thesaurus.com", "dictionary.com")):
        return False

    # Exclude competitor's own domain name
    comp_clean = re.sub(r"[^a-zA-Z0-9]", "", competitor).lower()
    domain_clean = re.sub(r"[^a-zA-Z0-9]", "", domain).lower()
    if comp_clean in domain_clean or domain_clean in comp_clean:
        return False

    # Exclude 8dots blacklist
    if "8dots" in domain:
        return False

    return True


def harvest_competitor_clients(competitors: List[str] = None, max_results_per_competitor: int = 4) -> List[Dict[str, Any]]:
    """
    Harvests live client websites of competitor agencies using Google/DDG footer footprints.
    """
    leads: List[Dict[str, Any]] = []
    if not DDGS:
        return leads

    target_competitors = competitors or DEFAULT_COMPETITORS
    # Pick a random subset of 2 competitors per run to avoid rate limits and keep variety
    selected_competitors = random.sample(target_competitors, min(2, len(target_competitors)))

    seen_domains: Set[str] = set()

    for competitor in selected_competitors:
        footprint = random.choice(FOOTPRINTS)
        queries = [
            f'"{footprint}" "{competitor}"',
            f'"{competitor}" "Case Study" "client"',
            f'{footprint} {competitor}'
        ]
        query = random.choice(queries)
        hits = []

        if SEARCH_WEB_FUNC:
            try:
                raw_hits = SEARCH_WEB_FUNC(query, max_results=max_results_per_competitor * 2) or []
                hits = [{"href": h.get("url"), "title": h.get("title", ""), "body": h.get("body", "") or h.get("snippet", "")} for h in raw_hits if h.get("url")]
            except Exception:
                hits = []

        if not hits and DDGS:
            try:
                with DDGS() as ddgs:
                    hits = list(ddgs.text(query, max_results=max_results_per_competitor * 2)) or []
            except Exception:
                hits = []

        print(f"  -> Competitor: '{competitor}' | Query: '{query}' -> {len(hits)} hits")

        for h in hits:
            url = h.get("href") or h.get("url", "")
            title = h.get("title", "")
            body = h.get("body", "")

            if not _is_client_url(url, competitor):
                continue

            domain = _extract_domain(url)
            if domain in seen_domains:
                continue
            seen_domains.add(domain)

            # Clean company name from page title
            clean_title = re.sub(r"\s*[-|:]\s*.*", "", title).strip()
            if not clean_title or len(clean_title) < 2:
                clean_title = domain.split(".")[0].capitalize()

            emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z]{2,}', f"{title} {body}")
            clean_emails = [e for e in emails if not e.endswith(('.png', '.jpg', '.jpeg', '.gif', '.svg'))]
            phones = re.findall(r'(\+?\d[\d\s\-\(\)]{8,15}\d)', f"{title} {body}")

            desc = (
                f"Active client of {competitor}. Identified via agency credit/portfolio. "
                f"{body or title}"
            )[:MAX_DESCRIPTION_CHARS]

            lead = {
                "company_name": clean_title[:80],
                "website": f"https://{domain}",
                "source": f"Competitor Client ({competitor})",
                "source_url": url,
                "email": ", ".join(set(clean_emails)) if clean_emails else "",
                "mobile_number": phones[0].strip() if phones else "",
                "description": desc,
                "lead_type": "Competitor Paying Client",
                "intent_score": "9",
                "location": "India / Worldwide"
            }
            leads.append(lead)
            if len(leads) >= max_results_per_competitor * 2:
                break

        time.sleep(1.0)

    return leads


if __name__ == "__main__":
    print("[*] Testing Competitor Client Harvester...")
    results = harvest_competitor_clients(max_results_per_competitor=3)
    print(f"[OK] Found {len(results)} competitor client leads:")
    for r in results:
        print(f"  -> {r['company_name']} | Web: {r['website']} | Src: {r['source']}")

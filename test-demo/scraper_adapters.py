"""
Unified Scraper Adapters Module (Supercharged High-Yield Edition)
================================================================
Provides non-destructive execution adapters for each of the 12 lead generation
scrapers, using modern robust libraries (ddgs, REST APIs, live feeds, rotated search dorks),
preventing artificial throttling, rotating queries across regions & niches, and
extracting enriched structured records into memory.
"""

import os
import re
import csv
import time
import random
import datetime
import urllib.request
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Tuple

from lead_normalizer import MAX_DESCRIPTION_CHARS

try:
    from ddgs import DDGS
except ImportError:
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        DDGS = None


# ==============================================================================
# 1. SCRAPER.PY ADAPTER (Dynamic Search Discovery & Deep Website Crawler)
# ==============================================================================
DYNAMIC_SEARCH_QUERIES = [
    'software development company Ahmedabad',
    'web development agency Gujarat',
    'IT consulting services Ahmedabad',
    'hire dedicated software developers Ahmedabad',
    'custom software solutions Surat',
    'mobile app development company Pune',
    'looking for software development company India',
    'need full stack development agency remote',
    'Python AI machine learning development company India',
    'React Node.js development agency Ahmedabad',
    'Shopify ecommerce web development agency Gujarat',
    'Laravel PHP software development company India',
    'MVP development agency for startups remote',
    'IT services and software company Vadodara'
]

def run_scraper_adapter() -> List[Dict[str, Any]]:
    """Invokes scraper.py functions with dynamic multi-query rotation."""
    import scraper

    leads = []
    # Pick 2-3 fresh rotating queries
    chosen_queries = random.sample(DYNAMIC_SEARCH_QUERIES, min(3, len(DYNAMIC_SEARCH_QUERIES)))

    for q in chosen_queries:
        try:
            search_hits = scraper.search_web(q, max_results=5)
            for hit in search_hits:
                lead_record, rej = scraper.crawl_and_evaluate(hit["url"], hit.get("title", ""), q)
                if lead_record:
                    leads.append({
                        "company_name": lead_record.get("Company Name"),
                        "website": lead_record.get("Website URL"),
                        "email": lead_record.get("Email"),
                        "mobile_number": lead_record.get("Mobile Number"),
                        "source": f"Search Engine ({q})",
                        "source_url": lead_record.get("Website URL"),
                        "lead_type": lead_record.get("Lead Type", "Software Company"),
                        "intent_score": str(lead_record.get("Lead Score", 7)),
                        "location": lead_record.get("Location") or "Ahmedabad"
                    })
            time.sleep(1.0)
        except Exception as e:
            print(f"  [scraper.py dynamic search notice on '{q}'] {e}")

    return leads


# ==============================================================================
# 2. LEAD_GENERATION_MASTER.PY ADAPTER (Reddit RSS + WWR RSS + Playwright Justdial)
# ==============================================================================
def run_lead_generation_master_adapter() -> List[Dict[str, Any]]:
    """Runs lead_generation_master components in-memory."""
    import lead_generation_master as lgm

    leads = []

    class TempStore:
        def __init__(self):
            self.collected = []
            self.seen = set()

        def is_duplicate(self, title, url):
            return url in self.seen or title.lower() in self.seen

        def save_lead(self, lead_obj):
            if self.is_duplicate(lead_obj.title, lead_obj.url):
                return False
            self.seen.add(lead_obj.url)
            self.seen.add(lead_obj.title.lower())
            self.collected.append(lead_obj.to_dict())
            return True

    temp_store = TempStore()
    harvester = lgm.RssLeadHarvester(temp_store)

    try:
        harvester.scrape_reddit_hiring(subreddit="forhire", limit=20)
    except Exception as e:
        print(f"  [Reddit RSS error] {e}")

    try:
        harvester.scrape_reddit_hiring(subreddit="freelance_forhire", limit=15)
    except Exception as e:
        print(f"  [Reddit freelance RSS error] {e}")

    try:
        harvester.scrape_weworkremotely(limit=15)
    except Exception as e:
        print(f"  [WWR RSS error] {e}")

    for item in temp_store.collected:
        leads.append({
            "company_name": item.get("Business Name/Title"),
            "source": item.get("Source"),
            "lead_type": item.get("Category", "Client Hiring"),
            "location": item.get("City", "Remote"),
            "mobile_number": item.get("Phone", ""),
            "email": item.get("Email", ""),
            "website": item.get("Website", ""),
            "source_url": item.get("URL", ""),
            "description": item.get("Snippet", ""),
            "first_seen_at": item.get("Scraped At")
        })

    # Playwright Justdial Harvester (if available)
    if getattr(lgm, "PLAYWRIGHT_AVAILABLE", False):
        try:
            jd_scraper = lgm.PlaywrightJustdialScraper(temp_store)
            jd_scraper.scrape(
                search_query="Software-Developers",
                location="Ahmedabad",
                max_results=8,
                headless=True
            )
            for item in temp_store.collected[len(leads):]:
                leads.append({
                    "company_name": item.get("Business Name/Title"),
                    "source": item.get("Source"),
                    "lead_type": item.get("Category"),
                    "location": item.get("City", "Ahmedabad"),
                    "mobile_number": item.get("Phone"),
                    "email": item.get("Email"),
                    "website": item.get("Website"),
                    "source_url": item.get("URL"),
                    "description": item.get("Snippet"),
                    "first_seen_at": item.get("Scraped At")
                })
        except Exception as e:
            print(f"  [Justdial notice] {e}")

    return leads


# ==============================================================================
# 3. DIRECT_FEED_CSV.PY ADAPTER (Reddit r/forhire Live XML Feed)
# ==============================================================================
def run_direct_feed_csv_adapter() -> List[Dict[str, Any]]:
    """Polls Reddit r/forhire live XML feed using direct_feed_csv logic."""
    import direct_feed_csv as dfc

    leads = []
    feed_url = dfc.FEED_URL
    req = urllib.request.Request(
        feed_url,
        headers={"User-Agent": "LeadHarvesterBot/2.5 (Aggregator; contact: contact@domain.com)"}
    )

    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            xml_data = response.read()

        root = ET.fromstring(xml_data)
        namespace = {'atom': 'http://www.w3.org/2005/Atom'}
        entries = root.findall('atom:entry', namespace)

        for entry in entries:
            title_el = entry.find('atom:title', namespace)
            link_el = entry.find('atom:link', namespace)
            updated_el = entry.find('atom:updated', namespace)
            content_el = entry.find('atom:content', namespace)

            title = title_el.text if title_el is not None else ""
            url = link_el.attrib.get('href', '') if link_el is not None else ""
            published = updated_el.text if updated_el is not None else ""
            snippet = content_el.text if content_el is not None else ""

            snippet_clean = snippet.replace("<br>", " ").replace("<b>", "").replace("</b>", "").replace("&amp;", "&")
            full_text = f"{title} {snippet_clean}"

            # Strict hiring check: must NOT be a job seeker
            if "[for hire]" in title.lower() or "[for-hire]" in title.lower() or "for hire" in title.lower():
                continue

            is_hiring = "hiring" in title.lower() or "looking for" in title.lower() or "need" in title.lower()
            matched_kw = any(kw.lower() in full_text.lower() for kw in dfc.KEYWORDS)

            if matched_kw and is_hiring:
                contacts = dfc.extract_contacts(full_text)
                clean_comp = re.sub(r"\[hiring\]", "", title, flags=re.I).strip()
                leads.append({
                    "company_name": clean_comp[:80],
                    "source": "Reddit (r/forhire RSS)",
                    "source_url": url,
                    "posted_at": published,
                    "email": contacts.get("Email", "") if contacts.get("Email") != "Not Found" else "",
                    "mobile_number": contacts.get("Mobile", "") if contacts.get("Mobile") != "Not Found" else "",
                    "description": snippet_clean[:MAX_DESCRIPTION_CHARS],
                    "lead_type": "Client Hiring",
                    "location": "Remote"
                })
    except Exception as e:
        print(f"  [direct_feed_csv notice] {e}")

    return leads


# ==============================================================================
# 4. DIRECT_FEED_TESTING_2.PY ADAPTER (Multi-Feed RSS: Reddit, WWR, Remotive)
# ==============================================================================
def run_direct_feed_testing_2_adapter() -> List[Dict[str, Any]]:
    """Polls Reddit, WWR, and Remotive feeds."""
    import direct_feed_testing_2 as dft

    leads = []
    for feed_url in dft.FEEDS:
        user_agent = "PythonLeadBot/2.5 (contact: bot@leadgen.com)"
        req = urllib.request.Request(feed_url, headers={"User-Agent": user_agent})

        try:
            with urllib.request.urlopen(req, timeout=12) as response:
                xml_data = response.read()

            root = ET.fromstring(xml_data)
            items = root.findall('.//item')
            if not items:
                namespace = {'atom': 'http://www.w3.org/2005/Atom'}
                items = root.findall('atom:entry', namespace)

            for item in items:
                title_elem = item.find('title') if item.find('title') is not None else item.find('{http://www.w3.org/2005/Atom}title')
                link_elem = item.find('link') if item.find('link') is not None else item.find('{http://www.w3.org/2005/Atom}link')
                desc_elem = item.find('description') if item.find('description') is not None else item.find('{http://www.w3.org/2005/Atom}content')

                title = title_elem.text if title_elem is not None and title_elem.text else ""
                url = link_elem.text if link_elem is not None and link_elem.text else link_elem.attrib.get('href', '') if link_elem is not None else ""
                snippet = desc_elem.text if desc_elem is not None and desc_elem.text else ""
                pub_date = (item.findtext('pubDate') or item.findtext('{http://www.w3.org/2005/Atom}published')
                            or item.findtext('{http://www.w3.org/2005/Atom}updated') or "")

                if "[for hire]" in title.lower() or "[for-hire]" in title.lower():
                    continue

                full_text = f"{title} {snippet}"
                matched_kw = any(kw.lower() in full_text.lower() for kw in dft.KEYWORDS)

                if "reddit.com" in feed_url:
                    is_valid = "hiring" in title.lower() or "looking for" in title.lower()
                else:
                    is_valid = True

                if matched_kw and is_valid:
                    contacts = dft.extract_contacts(full_text)
                    leads.append({
                        "company_name": title.strip()[:80],
                        "source": f"RSS Feed ({feed_url.split('/')[2]})",
                        "source_url": url,
                        "email": contacts.get("Email", "") if contacts.get("Email") != "Not Found" else "",
                        "mobile_number": contacts.get("Mobile", "") if contacts.get("Mobile") != "Not Found" else "",
                        "description": re.sub(r'<[^>]+>', '', snippet)[:MAX_DESCRIPTION_CHARS].strip(),
                        "posted_at": pub_date,
                        "lead_type": "Remote Tech Hiring",
                        "location": "Remote"
                    })
        except Exception as e:
            print(f"  [direct_feed_testing_2 notice on {feed_url}] {e}")

    return leads


# ==============================================================================
# 5. INSTANT_LEAD_GENERATOR.PY ADAPTER (Reddit, HN, RemoteOK, Jobicy APIs)
# ==============================================================================
def run_instant_lead_generator_adapter() -> List[Dict[str, Any]]:
    """Polls Reddit JSON API, Hacker News Algolia, RemoteOK API, and Jobicy API."""
    import instant_lead_generator as ilg

    leads = []
    # 1. Reddit Client JSON API
    try:
        reddit_leads = ilg.fetch_reddit_leads()
        for r in reddit_leads:
            leads.append({
                "company_name": r.get("Job Title / Requirement", "")[:80],
                "full_name": r.get("Client Name / Handle", ""),
                "email": r.get("Email", ""),
                "mobile_number": r.get("Mobile Number", ""),
                "source": r.get("Platform", "Reddit JSON API"),
                "source_url": r.get("Direct URL", ""),
                "description": r.get("Snippet") or r.get("Job Title / Requirement", ""),
                "lead_type": "Client Hiring",
                "location": "Remote",
                "intent_score": "9"
            })
    except Exception as e:
        print(f"  [instant_lead_generator Reddit notice] {e}")

    # 2. Hacker News Algolia API
    try:
        hn_leads = ilg.fetch_hackernews_leads()
        for h in hn_leads:
            leads.append({
                "company_name": h.get("Job Title / Requirement", "")[:80],
                "full_name": h.get("Client Name / Handle", ""),
                "email": h.get("Email", ""),
                "mobile_number": h.get("Mobile Number", ""),
                "source": "Hacker News Algolia API",
                "source_url": h.get("Direct URL", ""),
                "description": h.get("Snippet") or h.get("Job Title / Requirement", ""),
                "lead_type": "HN Hiring Post",
                "location": "Remote",
                "intent_score": "8"
            })
    except Exception as e:
        print(f"  [instant_lead_generator HN notice] {e}")

    # 3. RemoteOK API (High Yield Verified Tech Companies)
    try:
        rok_leads = ilg.fetch_remoteok_leads()
        for r in rok_leads:
            leads.append({
                "company_name": r.get("Client Name / Handle", "Tech Company"),
                "full_name": r.get("Client Name / Handle", ""),
                "email": r.get("Email", ""),
                "mobile_number": r.get("Mobile Number", ""),
                "source": "RemoteOK API",
                "source_url": r.get("Direct URL", ""),
                "website": r.get("Direct URL", ""),
                "description": r.get("Snippet", ""),
                "lead_type": "Remote Tech Hiring",
                "location": r.get("Location", "Remote"),
                "intent_score": "9"
            })
    except Exception as e:
        print(f"  [instant_lead_generator RemoteOK notice] {e}")

    # 4. Jobicy Remote Jobs API (Verified Company Positions)
    try:
        jobicy_leads = ilg.fetch_jobicy_leads()
        for j in jobicy_leads:
            leads.append({
                "company_name": j.get("Client Name / Handle", "Hiring Company"),
                "full_name": j.get("Client Name / Handle", ""),
                "email": j.get("Email", ""),
                "mobile_number": j.get("Mobile Number", ""),
                "source": "Jobicy Remote API",
                "source_url": j.get("Direct URL", ""),
                "website": j.get("Direct URL", ""),
                "description": j.get("Snippet", ""),
                "lead_type": "Remote Tech Hiring",
                "location": j.get("Location", "Remote"),
                "intent_score": "8"
            })
    except Exception as e:
        print(f"  [instant_lead_generator Jobicy notice] {e}")

    return leads


# ==============================================================================
# 6. DDGS_BULK_SCRAPER.PY ADAPTER (DuckDuckGo Dorks Harvester with Rotation)
# ==============================================================================
DDGS_ROTATING_DORKS = [
    'site:reddit.com/r/forhire "hiring" "developer"',
    'site:reddit.com/r/forhire "hiring" "full stack"',
    'site:reddit.com/r/forhire "hiring" "react"',
    'site:reddit.com/r/forhire "hiring" "python"',
    'site:reddit.com/r/freelance_forhire "looking for" "developer"',
    'site:reddit.com/r/jobbit "hiring" remote',
    'site:reddit.com/r/forhire "budget $" "developer"',
    'site:upwork.com/jobs "full stack developer" remote',
    'site:news.ycombinator.com "who is hiring" remote',
    'site:dev.to "hiring" "software developer"',
    'site:twitter.com "hiring" "developer" remote',
    'site:freelancer.com/projects "software development"'
]

def run_ddgs_bulk_scraper_adapter() -> List[Dict[str, Any]]:
    """Runs a dynamically sampled subset of DuckDuckGo Dorks safely."""
    leads = []
    if not DDGS:
        return leads

    try:
        sampled_queries = random.sample(DDGS_ROTATING_DORKS, min(4, len(DDGS_ROTATING_DORKS)))
        with DDGS() as ddgs:
            for q in sampled_queries:
                try:
                    results = list(ddgs.text(q, max_results=5))
                    if results:
                        for r in results:
                            url = r.get("href", "")
                            if url:
                                snippet = r.get("body", "")
                                emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z]{2,}', snippet)
                                phones = re.findall(r'(\+?\d[\d\s\-\(\)]{8,15}\d)', snippet)
                                leads.append({
                                    "company_name": r.get("title", "")[:80],
                                    "source": "DuckDuckGo Dork",
                                    "source_url": url,
                                    "email": ", ".join(set(emails)) if emails else "",
                                    "mobile_number": phones[0] if phones else "",
                                    "description": snippet[:250],
                                    "lead_type": "Developer Requirement",
                                    "intent_score": "7"
                                })
                    time.sleep(1.5)
                except Exception:
                    pass
    except Exception as e:
        print(f"  [ddgs_bulk_scraper notice] {e}")

    return leads


# ==============================================================================
# 7. B2B_PORTAL_SCRAPER.PY ADAPTER (IndiaMART / TradeIndia with Location Rotation)
# ==============================================================================
B2B_LOCATIONS = ["Ahmedabad", "Surat", "Pune", "Mumbai", "Bengaluru", "Vadodara", "Jaipur"]

def run_b2b_portal_scraper_adapter() -> List[Dict[str, Any]]:
    """Runs B2B portal search with rotated locations and robust extraction."""
    leads = []
    if not DDGS:
        return leads

    loc = random.choice(B2B_LOCATIONS)
    try:
        import b2b_portal_scraper as bps

        with DDGS() as ddgs:
            for portal in ["IndiaMART", "TradeIndia"]:
                query = f'site:{portal.lower()}.com "software development company" {loc}'
                try:
                    results = list(ddgs.text(query, max_results=4))
                    if results:
                        for r in results:
                            url = r.get("href") or r.get("url")
                            if url and portal.lower() in url:
                                snippet = r.get("body", "")
                                emails, phones = bps.extract_contacts_from_url(url)
                                # Fallback to snippet regex
                                if not emails:
                                    emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z]{2,}', snippet)
                                if not phones:
                                    phones = re.findall(r'(\+?\d[\d\s\-\(\)]{8,15}\d)', snippet)

                                leads.append({
                                    "company_name": r.get("title", "").replace(" - IndiaMART", "").replace(" - Tradeindia", "")[:80],
                                    "website": url,
                                    "source": f"B2B Portal ({portal})",
                                    "source_url": url,
                                    "email": ", ".join(emails) if emails else "",
                                    "mobile_number": ", ".join(phones[:2]) if phones else "",
                                    "description": snippet[:250],
                                    "location": loc,
                                    "lead_type": "B2B IT Company",
                                    "intent_score": "7"
                                })
                    time.sleep(1.5)
                except Exception:
                    pass
    except Exception as e:
        print(f"  [b2b_portal_scraper notice] {e}")

    return leads


# ==============================================================================
# 8. FREELANCE_REDDIT_SCRAPER.PY ADAPTER (Multi-Platform Dorks)
# ==============================================================================
def run_freelance_reddit_scraper_adapter() -> List[Dict[str, Any]]:
    """Queries freelance platform search dorks using modern ddgs."""
    leads = []
    if not DDGS:
        return leads

    try:
        import freelance_reddit_scraper as frs

        sampled_platforms = random.sample(frs.PLATFORM_QUERIES, min(3, len(frs.PLATFORM_QUERIES)))
        with DDGS() as ddgs:
            for platform in sampled_platforms:
                q = platform["queries"][0]
                try:
                    results = list(ddgs.text(q, max_results=4))
                    if results:
                        for r in results:
                            snippet = r.get("body", "")
                            contacts = frs.extract_contacts(snippet)
                            url = r.get("href") or r.get("url")
                            leads.append({
                                "company_name": r.get("title", "")[:80],
                                "source": f"Platform ({platform['name']})",
                                "source_url": url,
                                "email": contacts.get("email", ""),
                                "description": snippet[:250],
                                "lead_type": "Freelance Client Requirement",
                                "intent_score": "7"
                            })
                    time.sleep(1.5)
                except Exception:
                    pass
    except Exception as e:
        print(f"  [freelance_reddit_scraper notice] {e}")

    return leads


# ==============================================================================
# 9. LINKEDIN_SCRAPER.PY ADAPTER (Public Search Snippet Contact Discovery)
# ==============================================================================
def run_linkedin_scraper_adapter() -> List[Dict[str, Any]]:
    """Extracts LinkedIn company mentions from public search snippets with location rotation."""
    leads = []
    if not DDGS:
        return leads

    loc = random.choice(B2B_LOCATIONS)
    try:
        import linkedin_scraper as ls

        with DDGS() as ddgs:
            query = f'site:linkedin.com/company "software company" {loc}'
            try:
                results = list(ddgs.text(query, max_results=5))
                if results:
                    for r in results:
                        title = r.get("title", "").replace(" - LinkedIn", "").replace(" | LinkedIn", "")[:80]
                        snippet = r.get("body", "")
                        emails = ls.extract_emails(snippet)
                        phones = ls.extract_phones(snippet)
                        leads.append({
                            "company_name": title,
                            "source": "LinkedIn (Public Search)",
                            "source_url": r.get("href", ""),
                            "email": ", ".join(emails) if emails else "",
                            "mobile_number": ", ".join(phones) if phones else "",
                            "description": snippet[:250],
                            "location": loc,
                            "lead_type": "LinkedIn Company",
                            "intent_score": "7"
                        })
                time.sleep(1.5)
            except Exception:
                pass
    except Exception as e:
        print(f"  [linkedin_scraper notice] {e}")

    return leads


# ==============================================================================
# 10. REDDIT_RSS_SCRAPER.PY ADAPTER (Multi-Subreddit RSS with Strict Filter)
# ==============================================================================
def run_reddit_rss_scraper_adapter() -> List[Dict[str, Any]]:
    """Polls subreddits with strict exclusion of [FOR HIRE] posts."""
    leads = []
    subreddits = ["forhire", "freelance_forhire", "jobbit"]

    for sub in subreddits:
        rss_url = f"https://www.reddit.com/r/{sub}/new/.rss"
        req = urllib.request.Request(
            rss_url,
            headers={"User-Agent": "LeadBotMulti/2.5 (contact: info@domain.com)"}
        )

        try:
            with urllib.request.urlopen(req, timeout=12) as response:
                xml_data = response.read()

            root = ET.fromstring(xml_data)
            namespace = {'atom': 'http://www.w3.org/2005/Atom'}
            entries = root.findall('atom:entry', namespace)

            for entry in entries:
                title_el = entry.find('atom:title', namespace)
                link_el = entry.find('atom:link', namespace)
                content_el = entry.find('atom:content', namespace)
                pub_date = (entry.findtext('atom:published', default="", namespaces=namespace)
                            or entry.findtext('atom:updated', default="", namespaces=namespace))

                title = title_el.text if title_el is not None else ""
                url = link_el.attrib.get('href', '') if link_el is not None else ""
                snippet = content_el.text if content_el is not None else ""

                clean_summary = re.sub(r'<[^>]+>', ' ', snippet)
                text_to_check = f"{title} {clean_summary}".lower()

                # STRICT HIRING REQUIREMENT: Must NOT be [for hire]
                if "[for hire]" in text_to_check or "[for-hire]" in text_to_check or "for hire" in text_to_check:
                    continue

                if "hiring" in title.lower() or "looking for" in title.lower() or "need" in title.lower():
                    emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z]{2,}', clean_summary)
                    clean_emails = [e for e in emails if not e.endswith(('.png', '.jpg', '.jpeg'))]
                    phones = re.findall(r'(\+?\d[\d\s\-\(\)]{8,15}\d)', clean_summary)
                    clean_comp = re.sub(r"\[hiring\]", "", title, flags=re.I).strip()
                    leads.append({
                        "company_name": clean_comp[:80],
                        "source": f"Reddit (r/{sub})",
                        "source_url": url,
                        "email": ", ".join(set(clean_emails)) if clean_emails else "",
                        "mobile_number": phones[0] if phones else "",
                        "description": clean_summary[:MAX_DESCRIPTION_CHARS].strip(),
                        "posted_at": pub_date,
                        "lead_type": "Client Hiring",
                        "location": "Remote",
                        "intent_score": "8"
                    })
        except Exception as e:
            print(f"  [reddit_rss_scraper on r/{sub} notice] {e}")

    return leads


# ==============================================================================
# 11. GOOGLE_MAPS_SCRAPER.PY ADAPTER (Playwright Google Maps Local Business Scraper)
# ==============================================================================
def run_google_maps_scraper_adapter() -> List[Dict[str, Any]]:
    """Runs Playwright Google Maps scraper safely without re-dumping entire historical cache."""
    leads = []

    # Live Playwright Google Maps Scraping
    try:
        import google_maps_scraper
        loc = random.choice(B2B_LOCATIONS)
        live_results = google_maps_scraper.scrape_google_maps(
            search_query="Software Development Company",
            location=loc,
            max_results=8,
            headless=True
        )
        for r in live_results:
            b_name = r.get("Business Name")
            if b_name:
                leads.append({
                    "company_name": b_name,
                    "mobile_number": r.get("Phone", ""),
                    "website": r.get("Website", ""),
                    "location": r.get("Address") or r.get("City", loc),
                    "source": f"Google Maps ({r.get('Category', 'Business')} in {loc})",
                    "source_url": r.get("Google Maps URL", ""),
                    "lead_type": r.get("Category", "Local Business"),
                    "intent_score": "7" if r.get("Rating") and r.get("Rating") != "N/A" else "5",
                    "description": f"Rating: {r.get('Rating', 'N/A')} ({r.get('Reviews Count', '0')} reviews) | {r.get('Address', '')}"
                })
    except Exception as e:
        print(f"  [google_maps_scraper execution notice] {e}")

    return leads


# ==============================================================================
# 12. TELEGRAM_SCRAPER.PY ADAPTER (Telegram Client Job / Freelance Channels)
# ==============================================================================
def run_telegram_scraper_adapter() -> List[Dict[str, Any]]:
    """Runs live Telegram channel scraper without dumping stale historical cache."""
    leads = []

    # Live Telegram Client Scan
    try:
        import telegram_scraper
        live_results = telegram_scraper.run_telegram_scraper_sync()
        for r in live_results:
            msg = r.get("Message", "")
            sender = r.get("Sender Username", "")
            channel = r.get("Channel/Group", "")
            if msg:
                emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z]{2,}', msg)
                phones = re.findall(r'(\+?\d[\d\s\-\(\)]{8,15}\d)', msg)
                leads.append({
                    "company_name": f"{sender} ({channel})",
                    "full_name": sender,
                    "email": ", ".join(set(emails)) if emails else "",
                    "mobile_number": phones[0].strip() if phones else "",
                    "description": msg[:MAX_DESCRIPTION_CHARS].strip(),
                    "posted_at": r.get("Date", ""),
                    "source": f"Telegram ({channel})",
                    "source_url": f"https://t.me/{channel.replace('@', '')}" if channel else "",
                    "lead_type": "Telegram Client Hiring",
                    "intent_score": "8",
                    "location": "Remote"
                })
    except Exception as e:
        print(f"  [telegram_scraper execution notice] {e}")

    return leads


# ==============================================================================
# 13. JOB_PORTALS.PY ADAPTER (Active Client Hiring & High-Intent Tech Roles)
# ==============================================================================
JOB_PORTAL_ROLES = [
    'React Developer', 'Python Developer', 'Full Stack Developer',
    'Node.js Developer', 'Mobile App Developer', 'Software Engineer',
    'PHP Laravel Developer', 'Frontend Developer', 'Backend Developer',
    'WordPress Developer', 'DevOps Engineer', 'UI UX Designer'
]

def run_job_portals_adapter() -> List[Dict[str, Any]]:
    """Runs job_portals search across Remotive, Internshala, Foundit, and Shine."""
    leads = []
    try:
        import job_portals
        roles = random.sample(JOB_PORTAL_ROLES, min(2, len(JOB_PORTAL_ROLES)))
        available_portals = ['remotive', 'internshala', 'foundit', 'shine']
        state = random.choice(['Gujarat', 'All India'])

        res = job_portals.search_jobs(titles=roles, state=state, portal_ids=available_portals)
        jobs = res.get("jobs", []) if isinstance(res, dict) else (res if isinstance(res, list) else [])
        for j in jobs:
            raw = job_portals.job_to_raw_lead(j)
            if raw and raw.get("company_name"):
                raw["intent_score"] = "8"
                leads.append(raw)
    except Exception as e:
        print(f"  [job_portals adapter notice] {e}")

    return leads


# ==============================================================================
# 14. CORPORATE_REGISTRIES.PY ADAPTER (MCA & ZaubaCorp Active Companies)
# ==============================================================================
CORP_KEYWORDS = [
    'software', 'infotech', 'technologies', 'digital', 'solutions',
    'systems', 'innovations', 'consultancy', 'tech', 'data'
]

def run_corporate_registry_adapter() -> List[Dict[str, Any]]:
    """Runs corporate_registries search for newly incorporated Indian IT businesses."""
    leads = []
    try:
        import corporate_registries
        kws = random.sample(CORP_KEYWORDS, min(2, len(CORP_KEYWORDS)))
        res = corporate_registries.search({
            "mode": "company",
            "keywords": kws,
            "state": "Gujarat",
            "pages": 1
        })
        results = res.get("results", []) if isinstance(res, dict) else []
        for r in results:
            raw = corporate_registries.result_to_raw_lead(r)
            if raw and raw.get("company_name"):
                raw["intent_score"] = "7"
                leads.append(raw)
    except Exception as e:
        print(f"  [corporate_registries adapter notice] {e}")

    return leads


# ==============================================================================
# 15. CRM_SOURCES.PY ADAPTER (GoodFirms B2B Tech Agency Harvester)
# ==============================================================================
def run_crm_sources_adapter() -> List[Dict[str, Any]]:
    """Runs crm_sources directory discovery via GoodFirms."""
    leads = []
    try:
        import crm_sources
        res = crm_sources.search(
            keywords=['software development', 'web development'],
            titles=['director', 'founder', 'ceo'],
            state='Gujarat',
            city='Ahmedabad',
            source_ids=['goodfirms']
        )
        results = res.get("results", []) if isinstance(res, dict) else []
        for r in results:
            raw = crm_sources.result_to_raw_lead(r)
            if raw and raw.get("company_name"):
                raw["intent_score"] = "7"
                leads.append(raw)
    except Exception as e:
        print(f"  [crm_sources adapter notice] {e}")

    return leads


# ==============================================================================
# 16. ECOMMERCE_SOURCES.PY ADAPTER (Shopify & WooCommerce Online Stores)
# ==============================================================================
ECOMMERCE_NICHES = [
    'apparel', 'fashion', 'clothing', 'cosmetics', 'jewellery',
    'electronics', 'furniture', 'footwear', 'organic food'
]

def run_ecommerce_sources_adapter() -> List[Dict[str, Any]]:
    """Runs ecommerce_sources search for active D2C stores needing tech/dev services."""
    leads = []
    try:
        import ecommerce_sources
        kws = random.sample(ECOMMERCE_NICHES, min(2, len(ECOMMERCE_NICHES)))
        res = ecommerce_sources.search({
            "sources": ["shopify", "woocommerce"],
            "keywords": kws,
            "state": "All India",
            "engine": "auto"
        })
        results = res.get("results", []) if isinstance(res, dict) else []
        for r in results:
            raw = ecommerce_sources.result_to_raw_lead(r)
            if raw and raw.get("company_name"):
                raw["intent_score"] = "7"
                leads.append(raw)
    except Exception as e:
        print(f"  [ecommerce_sources adapter notice] {e}")

    return leads


# ==============================================================================
# 17. QUORA_SCRAPER ADAPTER (Buyer Intent & Tech Recommendations Harvester)
# ==============================================================================
QUORA_INTENT_QUERIES = [
    'quora software development company Ahmedabad',
    'quora web development company Gujarat',
    'quora custom software development company India',
    'quora hire python react developers Ahmedabad',
    'quora mobile app development agency Gujarat',
    'quora IT consulting services Ahmedabad',
    'quora looking for software company India',
    'quora top web development companies Surat',
    'quora hire dedicated developers startup India'
]

def run_quora_scraper_adapter() -> List[Dict[str, Any]]:
    """Harvests software client inquiries and agency recommendations from Quora search dorks."""
    leads = []
    try:
        import requests
        from bs4 import BeautifulSoup
        import scraper

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        }
        seen_urls = set()
        chosen = random.sample(QUORA_INTENT_QUERIES, min(2, len(QUORA_INTENT_QUERIES)))

        for q in chosen:
            try:
                r = requests.post('https://html.duckduckgo.com/html/', data={'q': q}, headers=headers, timeout=10)
                soup = BeautifulSoup(r.text, 'html.parser')
                results = soup.find_all('div', class_='result__body')

                for res in results[:5]:
                    title_tag = res.find('a', class_='result__url')
                    snippet_tag = res.find('a', class_='result__snippet')
                    if not title_tag:
                        continue
                    href = title_tag.get('href', '')
                    if 'uddg=' in href:
                        m = re.search(r'uddg=([^&]+)', href)
                        if m:
                            href = urllib.parse.unquote(m.group(1))

                    if not href or href in seen_urls:
                        continue
                    seen_urls.add(href)

                    raw_title = title_tag.get_text(strip=True)
                    snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""

                    if 'quora.com' in href:
                        clean_title = re.sub(r'https?://(?:www\.)?quora\.com/', '', href)
                        clean_title = clean_title.replace('-', ' ').split('?')[0].strip()
                        emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z]{2,}', snippet)
                        phones = re.findall(r'(\+?\d[\d\s\-\(\)]{8,15}\d)', snippet)
                        leads.append({
                            "company_name": clean_title[:80] if clean_title else "Quora Tech Inquiry",
                            "website": "",
                            "source": f"Quora Discussions ({q})",
                            "source_url": href,
                            "email": ", ".join(set(emails)) if emails else "",
                            "mobile_number": phones[0].strip() if phones else "",
                            "description": f"{raw_title} | {snippet}"[:MAX_DESCRIPTION_CHARS],
                            "lead_type": "Quora Buyer Discussion",
                            "intent_score": "7",
                            "location": "Ahmedabad / Gujarat"
                        })
                    else:
                        # Deep crawl recommended company site
                        lead_record, _ = scraper.crawl_and_evaluate(href, raw_title, q)
                        if lead_record:
                            leads.append({
                                "company_name": lead_record.get("Company Name") or raw_title[:80],
                                "website": lead_record.get("Website URL") or href,
                                "email": lead_record.get("Email", ""),
                                "mobile_number": lead_record.get("Mobile Number", ""),
                                "location": lead_record.get("Address") or lead_record.get("Location") or "Gujarat, India",
                                "source": f"Quora Recommendations ({q})",
                                "source_url": href,
                                "lead_type": lead_record.get("Lead Type", "Software Company"),
                                "intent_score": str(lead_record.get("Lead Score", 8)),
                                "description": snippet[:MAX_DESCRIPTION_CHARS]
                            })
                        else:
                            emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z]{2,}', snippet)
                            phones = re.findall(r'(\+?\d[\d\s\-\(\)]{8,15}\d)', snippet)
                            leads.append({
                                "company_name": raw_title[:80],
                                "website": href,
                                "email": ", ".join(set(emails)) if emails else "",
                                "mobile_number": phones[0].strip() if phones else "",
                                "location": "Gujarat, India",
                                "source": f"Quora Search Dorks ({q})",
                                "source_url": href,
                                "lead_type": "Recommended Tech Company",
                                "intent_score": "7",
                                "description": snippet[:MAX_DESCRIPTION_CHARS]
                            })
                time.sleep(1.0)
            except Exception as e:
                print(f"  [quora adapter notice on '{q}'] {e}")
    except Exception as e:
        print(f"  [quora adapter execution notice] {e}")

    return leads


# ==============================================================================
# 18. YELLOWPAGES_SCRAPER ADAPTER (Indian Yellow Pages & B2B Directory)
# ==============================================================================
YELLOWPAGES_LOCATIONS = ["Ahmedabad", "Surat", "Vadodara", "Rajkot", "Gujarat", "India"]

def run_yellowpages_adapter() -> List[Dict[str, Any]]:
    """Harvests software & IT companies from Indian Yellow Pages directories."""
    leads = []
    if not DDGS:
        return leads

    loc = random.choice(YELLOWPAGES_LOCATIONS)
    seen_urls = set()
    yp_queries = [
        f'site:indianyellowpages.com "software development" {loc}',
        f'site:indianyellowpages.com "web development" {loc}',
        f'yellowpages "software development company" {loc}',
        f'yellowpages "IT services" {loc}',
        f'site:yellowpages-india.in software {loc}'
    ]
    chosen = random.sample(yp_queries, min(2, len(yp_queries)))

    try:
        with DDGS() as ddgs:
            for q in chosen:
                try:
                    hits = list(ddgs.text(q, max_results=5)) or []
                    for h in hits:
                        url = h.get("href") or h.get("url", "")
                        title = h.get("title", "")
                        body = h.get("body", "")

                        if not url or url in seen_urls:
                            continue
                        seen_urls.add(url)

                        clean_title = re.sub(r"\s*[-|]\s*IndianYellowPages.*", "", title, flags=re.I).strip()
                        clean_title = re.sub(r"\s*[-|]\s*Yellow Pages.*", "", clean_title, flags=re.I).strip()
                        clean_title = re.sub(r"\s*in\s+(Ahmedabad|Gujarat|Surat|India).*", "", clean_title, flags=re.I).strip()
                        if not clean_title or len(clean_title) < 3:
                            clean_title = title[:80]

                        emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z]{2,}', body)
                        phones = re.findall(r'(\+?\d[\d\s\-\(\)]{8,15}\d)', body)

                        leads.append({
                            "company_name": clean_title[:80],
                            "website": url if not any(x in url for x in ("yellowpages", "google", "bing")) else "",
                            "source": f"Yellow Pages ({loc})",
                            "source_url": url,
                            "email": ", ".join(set(emails)) if emails else "",
                            "mobile_number": phones[0].strip() if phones else "",
                            "description": f"{title} | {body}"[:MAX_DESCRIPTION_CHARS],
                            "lead_type": "B2B Directory Listing",
                            "intent_score": "7",
                            "location": f"{loc}, Gujarat" if loc != "India" else "India"
                        })
                    time.sleep(1.0)
                except Exception as e:
                    print(f"  [yellowpages adapter notice on '{q}'] {e}")
    except Exception as e:
        print(f"  [yellowpages adapter execution notice] {e}")

    return leads

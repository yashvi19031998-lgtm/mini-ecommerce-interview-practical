"""
Unified Scraper Adapters Module
===============================
Provides non-destructive execution adapters for each of the 10 existing
lead generation scrapers, extracting structured records into memory.
"""

import os
import re
import csv
import time
import datetime
import urllib.request
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Tuple


# ==============================================================================
# 1. SCRAPER.PY ADAPTER (Search Discovery & Deep Website Crawler)
# ==============================================================================
def run_scraper_adapter() -> List[Dict[str, Any]]:
    """Invokes scraper.py functions or harvests high-quality leads."""
    import scraper

    leads = []
    # If leads.csv already exists with recent results, harvest them
    if os.path.exists("leads.csv"):
        with open("leads.csv", mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                leads.append({
                    "company_name": row.get("Company Name"),
                    "website": row.get("Website URL"),
                    "email": row.get("Email"),
                    "mobile_number": row.get("Mobile Number"),
                    "source": f"Search Engine ({row.get('Search Query', 'IT Hiring')})",
                    "source_url": row.get("Website URL"),
                    "lead_type": row.get("Lead Type", "Potential Buyer"),
                    "intent_score": row.get("Lead Score", "5"),
                    "location": scraper.SEARCH_LOCATION or "Ahmedabad"
                })

    # Also run 1 quick targeted search query for live discovery without overwhelming
    try:
        sample_query = f'"need software development company" {scraper.SEARCH_LOCATION}'.strip()
        search_hits = scraper.search_web(sample_query, max_results=3)
        for hit in search_hits:
            lead_record, rej = scraper.crawl_and_evaluate(hit["url"], hit.get("title", ""), sample_query)
            if lead_record:
                leads.append({
                    "company_name": lead_record.get("Company Name"),
                    "website": lead_record.get("Website URL"),
                    "email": lead_record.get("Email"),
                    "mobile_number": lead_record.get("Mobile Number"),
                    "source": f"Search Engine ({sample_query})",
                    "source_url": lead_record.get("Website URL"),
                    "lead_type": lead_record.get("Lead Type"),
                    "intent_score": str(lead_record.get("Lead Score")),
                    "location": scraper.SEARCH_LOCATION or "Ahmedabad"
                })
    except Exception as e:
        print(f"  [scraper.py notice] Search fallback completed: {e}")

    return leads


# ==============================================================================
# 2. LEAD_GENERATION_MASTER.PY ADAPTER (Reddit RSS + WWR RSS + Playwright Justdial)
# ==============================================================================
def run_lead_generation_master_adapter() -> List[Dict[str, Any]]:
    """Runs lead_generation_master components in-memory."""
    import lead_generation_master as lgm

    leads = []

    # 1. RSS Harvester (Reddit & WeWorkRemotely)
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
        harvester.scrape_reddit_hiring(subreddit="forhire", limit=15)
    except Exception as e:
        print(f"  [Reddit RSS error] {e}")

    try:
        harvester.scrape_weworkremotely(limit=10)
    except Exception as e:
        print(f"  [WWR RSS error] {e}")

    # Convert collected leads
    for item in temp_store.collected:
        leads.append({
            "company_name": item.get("Business Name/Title"),
            "source": item.get("Source"),
            "lead_type": item.get("Category"),
            "location": item.get("City"),
            "mobile_number": item.get("Phone"),
            "email": item.get("Email"),
            "website": item.get("Website"),
            "source_url": item.get("URL"),
            "description": item.get("Snippet"),
            "first_seen_at": item.get("Scraped At")
        })

    # 2. Playwright Justdial Harvester (if available)
    if getattr(lgm, "PLAYWRIGHT_AVAILABLE", False):
        try:
            jd_scraper = lgm.PlaywrightJustdialScraper(temp_store)
            jd_scraper.scrape(
                search_query="Software-Developers",
                location="Ahmedabad",
                max_results=8,
                headless=True
            )
            # Re-read new additions
            for item in temp_store.collected:
                leads.append({
                    "company_name": item.get("Business Name/Title"),
                    "source": item.get("Source"),
                    "lead_type": item.get("Category"),
                    "location": item.get("City"),
                    "mobile_number": item.get("Phone"),
                    "email": item.get("Email"),
                    "website": item.get("Website"),
                    "source_url": item.get("URL"),
                    "description": item.get("Snippet"),
                    "first_seen_at": item.get("Scraped At")
                })
        except Exception as e:
            print(f"  [Justdial error] {e}")

    return leads


# ==============================================================================
# 3. DIRECT_FEED_CSV.PY ADAPTER (Reddit r/forhire Pure Standard Lib)
# ==============================================================================
def run_direct_feed_csv_adapter() -> List[Dict[str, Any]]:
    """Polls Reddit r/forhire live XML feed using direct_feed_csv logic."""
    import direct_feed_csv as dfc

    leads = []
    feed_url = dfc.FEED_URL
    req = urllib.request.Request(
        feed_url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
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

            matched_kw = any(kw.lower() in full_text.lower() for kw in dfc.KEYWORDS)
            is_hiring = "hiring" in title.lower() and "[for hire]" not in title.lower()

            if matched_kw and is_hiring:
                contacts = dfc.extract_contacts(full_text)
                leads.append({
                    "company_name": title.replace("[Hiring]", "").replace("[HIRING]", "").strip(),
                    "source": "Reddit (r/forhire RSS)",
                    "source_url": url,
                    "first_seen_at": published,
                    "email": contacts.get("Email", ""),
                    "mobile_number": contacts.get("Mobile", ""),
                    "description": snippet_clean[:250],
                    "lead_type": "Client Hiring",
                    "location": "Remote"
                })
    except Exception as e:
        print(f"  [direct_feed_csv error] {e}")

    return leads


# ==============================================================================
# 4. DIRECT_FEED_TESTING_2.PY ADAPTER (Multi-Feed RSS: Reddit, WWR, Remotive)
# ==============================================================================
def run_direct_feed_testing_2_adapter() -> List[Dict[str, Any]]:
    """Polls Reddit, WWR, and Remotive feeds."""
    import direct_feed_testing_2 as dft

    leads = []
    for feed_url in dft.FEEDS:
        user_agent = "PythonLeadScraper/2.0 (Contact: admin@example.com)" if "reddit.com" in feed_url else "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
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

                full_text = f"{title} {snippet}"
                matched_kw = any(kw.lower() in full_text.lower() for kw in dft.KEYWORDS)

                if "reddit.com" in feed_url:
                    is_valid = "hiring" in title.lower() and "[for hire]" not in title.lower()
                else:
                    is_valid = True

                if matched_kw and is_valid:
                    contacts = dft.extract_contacts(full_text)
                    leads.append({
                        "company_name": title.strip(),
                        "source": f"RSS Feed ({feed_url.split('/')[2]})",
                        "source_url": url,
                        "email": contacts.get("Email", ""),
                        "mobile_number": contacts.get("Mobile", ""),
                        "description": re.sub(r'<[^>]+>', '', snippet)[:250].strip(),
                        "lead_type": "Remote Tech Hiring",
                        "location": "Remote"
                    })
        except Exception as e:
            print(f"  [direct_feed_testing_2 error on {feed_url}] {e}")

    return leads


# ==============================================================================
# 5. INSTANT_LEAD_GENERATOR.PY ADAPTER (Reddit JSON + HN Algolia REST APIs)
# ==============================================================================
def run_instant_lead_generator_adapter() -> List[Dict[str, Any]]:
    """Polls Reddit JSON API and Hacker News Algolia Search API."""
    import instant_lead_generator as ilg

    leads = []
    try:
        reddit_leads = ilg.fetch_reddit_leads()
        for r in reddit_leads:
            leads.append({
                "company_name": r.get("Job Title / Requirement"),
                "full_name": r.get("Client Name / Handle"),
                "source": "Reddit JSON API",
                "source_url": r.get("Direct URL"),
                "description": r.get("Job Title / Requirement"),
                "lead_type": "Client Hiring",
                "location": "Remote"
            })
    except Exception as e:
        print(f"  [instant_lead_generator Reddit error] {e}")

    try:
        hn_leads = ilg.fetch_hackernews_leads()
        for h in hn_leads:
            leads.append({
                "company_name": h.get("Job Title / Requirement"),
                "full_name": h.get("Client Name / Handle"),
                "source": "Hacker News Algolia API",
                "source_url": h.get("Direct URL"),
                "description": h.get("Job Title / Requirement"),
                "lead_type": "HN Hiring Story",
                "location": "Remote"
            })
    except Exception as e:
        print(f"  [instant_lead_generator HN error] {e}")

    return leads


# ==============================================================================
# 6. DDGS_BULK_SCRAPER.PY ADAPTER (DuckDuckGo Dorks Harvester)
# ==============================================================================
def run_ddgs_bulk_scraper_adapter() -> List[Dict[str, Any]]:
    """Runs a throttled subset of DuckDuckGo Dorks safely."""
    leads = []
    try:
        from duckduckgo_search import DDGS
        import ddgs_bulk_scraper as dbs

        with DDGS() as ddgs:
            # Query the first 3 targeted queries to avoid aggressive IP throttling
            for q in dbs.QUERIES[:3]:
                try:
                    results = ddgs.text(q, max_results=3)
                    if results:
                        for r in results:
                            url = r.get("href", "")
                            if url:
                                leads.append({
                                    "company_name": r.get("title", ""),
                                    "source": "DuckDuckGo Dork",
                                    "source_url": url,
                                    "description": r.get("body", ""),
                                    "lead_type": "Developer Requirement"
                                })
                    time.sleep(2.0)
                except Exception:
                    pass
    except Exception as e:
        print(f"  [ddgs_bulk_scraper error] {e}")

    return leads


# ==============================================================================
# 7. B2B_PORTAL_SCRAPER.PY ADAPTER (IndiaMART / TradeIndia with Fixed Imports)
# ==============================================================================
def run_b2b_portal_scraper_adapter() -> List[Dict[str, Any]]:
    """Runs B2B portal search with corrected import and strict domain filtering."""
    leads = []
    try:
        from duckduckgo_search import DDGS
        import requests
        import b2b_portal_scraper as bps

        with DDGS() as ddgs:
            for portal in ["IndiaMART", "TradeIndia"]:
                query = f'site:{portal.lower()}.com "software development company"'
                try:
                    results = ddgs.text(query, max_results=3)
                    if results:
                        for r in results:
                            url = r.get("href") or r.get("url")
                            if url and portal.lower() in url:
                                emails, phones = bps.extract_contacts_from_url(url)
                                leads.append({
                                    "company_name": r.get("title", ""),
                                    "website": url,
                                    "source": f"B2B Portal ({portal})",
                                    "source_url": url,
                                    "email": ", ".join(emails) if emails else "",
                                    "mobile_number": ", ".join(phones) if phones else "",
                                    "description": r.get("body", ""),
                                    "lead_type": "B2B IT Company"
                                })
                    time.sleep(2.0)
                except Exception:
                    pass
    except Exception as e:
        print(f"  [b2b_portal_scraper error] {e}")

    return leads


# ==============================================================================
# 8. FREELANCE_REDDIT_SCRAPER.PY ADAPTER (Multi-Platform Dorks with Fixed Imports)
# ==============================================================================
def run_freelance_reddit_scraper_adapter() -> List[Dict[str, Any]]:
    """Queries freelance platform search dorks using corrected duckduckgo_search."""
    leads = []
    try:
        from duckduckgo_search import DDGS
        import freelance_reddit_scraper as frs

        with DDGS() as ddgs:
            for platform in frs.PLATFORM_QUERIES[:2]:
                q = platform["queries"][0]
                try:
                    results = ddgs.text(q, max_results=3)
                    if results:
                        for r in results:
                            snippet = r.get("body", "")
                            contacts = frs.extract_contacts(snippet)
                            leads.append({
                                "company_name": r.get("title", ""),
                                "source": f"Platform ({platform['name']})",
                                "source_url": r.get("href") or r.get("url"),
                                "email": contacts.get("email", ""),
                                "description": snippet,
                                "lead_type": "Freelance Requirement"
                            })
                    time.sleep(2.0)
                except Exception:
                    pass
    except Exception as e:
        print(f"  [freelance_reddit_scraper error] {e}")

    return leads


# ==============================================================================
# 9. LINKEDIN_SCRAPER.PY ADAPTER (Public Search Snippet Contact Discovery)
# ==============================================================================
def run_linkedin_scraper_adapter() -> List[Dict[str, Any]]:
    """Extracts LinkedIn company mentions from public search snippets safely."""
    leads = []
    try:
        from duckduckgo_search import DDGS
        import linkedin_scraper as ls

        with DDGS() as ddgs:
            query = 'site:linkedin.com/company "software company" Ahmedabad'
            try:
                results = ddgs.text(query, max_results=3)
                if results:
                    for r in results:
                        title = r.get("title", "").replace(" - LinkedIn", "").replace(" | LinkedIn", "")
                        snippet = r.get("body", "")
                        emails = ls.extract_emails(snippet)
                        phones = ls.extract_phones(snippet)
                        leads.append({
                            "company_name": title,
                            "source": "LinkedIn (Public Search)",
                            "source_url": r.get("href", ""),
                            "email": ", ".join(emails) if emails else "",
                            "mobile_number": ", ".join(phones) if phones else "",
                            "description": snippet,
                            "location": "Ahmedabad",
                            "lead_type": "LinkedIn Company"
                        })
                time.sleep(2.0)
            except Exception:
                pass
    except Exception as e:
        print(f"  [linkedin_scraper error] {e}")

    return leads


# ==============================================================================
# 10. REDDIT_RSS_SCRAPER.PY ADAPTER (Multi-Subreddit RSS with Filter & stdlib)
# ==============================================================================
def run_reddit_rss_scraper_adapter() -> List[Dict[str, Any]]:
    """Polls subreddits with strict exclusion of [FOR HIRE] posts."""
    leads = []
    subreddits = ["forhire", "freelance_forhire", "jobbit"]

    for sub in subreddits:
        rss_url = f"https://www.reddit.com/r/{sub}/new/.rss"
        req = urllib.request.Request(
            rss_url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
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

                title = title_el.text if title_el is not None else ""
                url = link_el.attrib.get('href', '') if link_el is not None else ""
                snippet = content_el.text if content_el is not None else ""

                clean_summary = re.sub(r'<[^>]+>', ' ', snippet)
                text_to_check = f"{title} {clean_summary}".lower()

                # STRICT HIRING REQUIREMENT: Must NOT be [for hire]
                if "[for hire]" in text_to_check or "[for-hire]" in text_to_check:
                    continue

                if "hiring" in title.lower() or "looking for" in title.lower():
                    # Extract email regex
                    emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', clean_summary)
                    leads.append({
                        "company_name": title.strip(),
                        "source": f"Reddit (r/{sub})",
                        "source_url": url,
                        "email": ", ".join(set(emails)) if emails else "",
                        "description": clean_summary[:250].strip(),
                        "lead_type": "Client Hiring",
                        "location": "Remote"
                    })
        except Exception as e:
            print(f"  [reddit_rss_scraper on r/{sub} error] {e}")

    return leads

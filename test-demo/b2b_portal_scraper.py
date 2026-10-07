import csv
import re
import time
from ddgs import DDGS
import requests
from bs4 import BeautifulSoup

# Define fallback footprints per portal
PORTAL_FOOTPRINTS = {
    "IndiaMART": [
        'site:indiamart.com "software development"',
        'site:indiamart.com "IT services"',
        'site:indiamart.com "web development"',
    ],
    "TradeIndia": [
        'site:tradeindia.com "software development"',
        'site:tradeindia.com "IT services"',
        'site:tradeindia.com "software company"',
    ],
    "ExportersIndia": [
        'site:exportersindia.com "software development"',
        'site:exportersindia.com "IT services"',
        'site:exportersindia.com "software company"',
    ],
}

# Generic fallbacks if site: queries fail
GENERIC_FALLBACKS = [
    '"software development company" India',
    '"IT services provider" India',
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def search_ddg(query, max_results=20):
    results = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append(r)
                time.sleep(0.5)
    except Exception as e:
        print(f"[ERROR] Search failed for '{query}': {e}")
    return results

def extract_contacts_from_url(url):
    emails, phones = set(), set()
    try:
        resp = requests.get(url, headers=HEADERS, timeout=8)
        text = resp.text
        emails.update(re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text))
        phones.update(re.findall(r'\+?\d{1,3}[-.\s]?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}', text))
    except Exception:
        pass
    return list(emails), list(phones)

def run_b2b_scraper():
    print("=" * 60)
    print("      B2B PORTAL LEADS COLLECTOR (INDIAMART, TRADEINDIA, EXPORTERSINDIA)")
    print("=" * 60)
    
    collected_leads = []
    seen_urls = set()

    for portal, queries in PORTAL_FOOTPRINTS.items():
        print(f"\n[INFO] Starting search for {portal}...")
        portal_hits = []
        # Try footprints
        for q in queries:
            print(f"  -> Query: {q}")
            res = search_ddg(q)
            for item in res:
                link = item.get("href") or item.get("url")
                if link and link not in seen_urls:
                    seen_urls.add(link)
                    portal_hits.append((portal, item.get("title", "N/A"), link, item.get("body", "")))
            if portal_hits:
                break  # stop once we have hits
            time.sleep(1)
        # Generic fallback if no hits
        if not portal_hits:
            print(f"  [WARN] No direct hits for {portal}. Trying generic fallback search...")
            domain_keyword = portal.lower().replace(" ", "")
            for gq in GENERIC_FALLBACKS:
                res = search_ddg(f'{gq} site:{domain_keyword}.com')
                for item in res:
                    link = item.get("href") or item.get("url")
                    if link and link not in seen_urls:
                        seen_urls.add(link)
                        portal_hits.append((portal, item.get("title", "N/A"), link, item.get("body", "")))
                if portal_hits:
                    break
        print(f"[INFO] Found {len(portal_hits)} raw leads for {portal}.")
        for p_name, title, link, body in portal_hits:
            emails, phones = extract_contacts_from_url(link)
            collected_leads.append({
                "Portal_Source": p_name,
                "Title_Requirement": title,
                "Portal_URL": link,
                "Extracted_Emails": " | ".join(emails) if emails else "None",
                "Extracted_Phones": " | ".join(phones[:2]) if phones else "None",
                "Snippet": body[:150]
            })
    output_file = "b2b_portals_leads.csv"
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["Portal_Source", "Title_Requirement", "Portal_URL", "Extracted_Emails", "Extracted_Phones", "Snippet"])
        writer.writeheader()
        writer.writerows(collected_leads)
    print("\n" + "-" * 60)
    print(f"[SUCCESS] Collected {len(collected_leads)} total leads across B2B portals.")
    print(f"[INFO] Saved to '{output_file}'.")

if __name__ == "__main__":
    run_b2b_scraper()

import time
import re
import csv
import urllib.parse
import pandas as pd
import requests
from bs4 import BeautifulSoup
from ddgs import DDGS

# 1. CONFIGURATION
# ==============================================================================
SEARCH_QUERIES = [
    "site:linkedin.com/company IT software company",
    "site:linkedin.com/in freelance software developer",
]

MAX_RESULTS_PER_QUERY = 5
REQUEST_TIMEOUT = 10

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Referer": "https://duckduckgo.com/"
}

# 2. HELPER FUNCTIONS
# ==============================================================================
def extract_emails(text):
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    emails = re.findall(email_pattern, text)
    valid_emails = set()
    for e in emails:
        e = e.lower()
        if not e.endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg')):
            if "example" not in e and "email" not in e:
                valid_emails.add(e)
    return list(valid_emails)

def extract_phones(text):
    phone_pattern = r'(?:(?:\+|00)\d{1,3}[\s-]?)?(?:\(?\d{2,4}\)?[\s-]?)?\d{3,4}[\s-]?\d{3,4}'
    matches = re.findall(phone_pattern, text)
    valid_phones = set()
    for p in matches:
        clean_p = re.sub(r'[^\d+]', '', p)
        if 8 <= len(clean_p) <= 15:
            valid_phones.add(p.strip())
    return list(valid_phones)

def extract_external_website(soup):
    # LinkedIn pages often have 'Visit website' or similar external links in the About section
    for a in soup.find_all('a', href=True):
        href = a['href']
        text = a.get_text(strip=True).lower()
        if 'visit website' in text or 'company website' in text:
            # Parse LinkedIn redirect if applicable
            if 'linkedin.com/company' not in href and 'http' in href:
                return href
    return None

# 3. MAIN SCRAPING LOGIC
# ==============================================================================
def scrape_linkedin_leads():
    print("=" * 70)
    print("      LINKEDIN B2B IT/SOFTWARE LEAD COLLECTOR (DUCKDUCKGO DEMO)")
    print("=" * 70)
    
    collected_leads = []
    ddgs = DDGS()

    for query in SEARCH_QUERIES:
        print(f"\n[INFO] Searching DuckDuckGo for LinkedIn profiles: '{query}'")
        
        try:
            # Using duckduckgo-search text search
            results = list(ddgs.text(query, max_results=MAX_RESULTS_PER_QUERY))
        except Exception as e:
            print(f"[ERROR] Search failed for '{query}'. See details below:")
            import traceback
            traceback.print_exc()
            continue
            
        if not results:
            print(f"  -> [WARN] DuckDuckGo returned 0 results. It may be blocking automated queries.")
            continue
            
        time.sleep(2)
        
        for result in results:
            url = result.get('href')
            if not url or 'linkedin.com' not in url:
                continue
                
            print(f"  -> Visiting LinkedIn: {url}")
            try:
                response = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
                if response.status_code != 200:
                    print(f"     [WARN] Status code {response.status_code}. Moving to next.")
                    continue
            except Exception as e:
                print(f"     [ERROR] Request failed: {e}")
                continue

            soup = BeautifulSoup(response.text, 'html.parser')
            page_text = soup.get_text(separator=' ')
            
            # Extract basic info
            title = soup.title.string.strip() if soup.title else "Unknown Title"
            emails = extract_emails(page_text)
            phones = extract_phones(page_text)
            
            external_site = extract_external_website(soup)
            
            # Fallback strategy: Visit external website to find contacts if missing
            if external_site and (not emails and not phones):
                print(f"     -> Found external website, exploring: {external_site}")
                try:
                    ext_resp = requests.get(external_site, headers=HEADERS, timeout=REQUEST_TIMEOUT)
                    if ext_resp.status_code == 200:
                        ext_soup = BeautifulSoup(ext_resp.text, 'html.parser')
                        ext_text = ext_soup.get_text(separator=' ')
                        
                        emails = extract_emails(ext_text)
                        phones = extract_phones(ext_text)
                except Exception as e:
                    print(f"     [ERROR] Failed to fetch external site: {e}")

            emails_str = " | ".join(emails) if emails else ""
            phones_str = " | ".join(phones) if phones else ""
            
            collected_leads.append({
                "Title": title,
                "LinkedIn_URL": url,
                "External_Website": external_site or "",
                "Emails": emails_str,
                "Phones": phones_str
            })
            
            if emails_str or phones_str:
                print(f"     [SUCCESS] Found contacts!")
            else:
                print(f"     [INFO] No visible contacts found. (Saved URL anyway)")
                
            time.sleep(1.5)

    # 4. EXPORT RESULTS
    # ==============================================================================
    print("\n" + "-" * 70)
    print(f"[INFO] Collected {len(collected_leads)} potential leads.")
    
    if collected_leads:
        df = pd.DataFrame(collected_leads)
        df.to_csv("linkedin_leads.csv", index=False)
        print("[INFO] Results saved to 'linkedin_leads.csv'.")
        print(df.to_string())
    else:
        print("[INFO] No leads collected.")

if __name__ == "__main__":
    scrape_linkedin_leads()

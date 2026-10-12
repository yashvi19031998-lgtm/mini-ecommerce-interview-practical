import csv
import os
import re
import urllib.request
import xml.etree.ElementTree as ET

# Multiple Direct Feeds
FEEDS = [
    "https://www.reddit.com/r/forhire/new/.rss",
    "https://weworkremotely.com/categories/remote-back-end-programming-jobs.rss",
    "https://remotive.com/remote-jobs/feed"
]

CSV_FILE = "all_leads_clean.csv"
KEYWORDS = ["python", "developer", "freelance", "remote", "script", "react", "fullstack"]

def extract_contacts(text):
    contacts = {"Email": "Not Found", "Telegram": "Not Found", "Mobile": "Not Found"}
    
    if not text:
        return contacts
        
    # Clean HTML tags if present in text
    clean_text = re.sub(r'<[^>]+>', ' ', text)
    
    # Email regex
    emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', clean_text)
    if emails:
        contacts["Email"] = ", ".join(set(emails))
        
    # Telegram handle regex
    telegram = re.findall(r'@[a-zA-Z0-9_]{4,}', clean_text)
    if telegram:
        contacts["Telegram"] = ", ".join(set(telegram))
        
    # Mobile number regex
    phones = re.findall(r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', clean_text)
    if phones:
        valid_phones = [p.strip() for p in phones if len(re.sub(r'\D', '', p)) >= 10]
        if valid_phones:
            contacts["Mobile"] = ", ".join(set(valid_phones))
        
    return contacts

def get_existing_urls():
    existing = set()
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, mode="r", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            for row in reader:
                if "URL" in row:
                    existing.add(row["URL"])
    return existing

def save_lead_to_csv(lead_data):
    file_exists = os.path.exists(CSV_FILE)
    with open(CSV_FILE, mode="a", newline="", encoding="utf-8") as file:
        fieldnames = ["Source", "Title", "URL", "Email", "Telegram", "Mobile", "Snippet"]
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(lead_data)

def fetch_all_feeds():
    existing_urls = get_existing_urls()
    total_new = 0

    for feed_url in FEEDS:
        print(f"\n[INFO] Fetching from source: {feed_url}")
        
        if "reddit.com" in feed_url:
            user_agent = "PythonLeadScraper/2.0 (Contact: admin@example.com)"
        else:
            user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

        req = urllib.request.Request(feed_url, headers={"User-Agent": user_agent})
        
        try:
            with urllib.request.urlopen(req) as response:
                xml_data = response.read()
        except Exception as e:
            print(f"  [ERROR] Failed to fetch feed: {e}")
            continue

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
            
            if link_elem is not None:
                url = link_elem.text if link_elem.text else link_elem.attrib.get('href', '')
            else:
                url = ""

            snippet = desc_elem.text if desc_elem is not None and desc_elem.text else ""
            full_text = title + " " + snippet

            matched_keyword = any(kw.lower() in full_text.lower() for kw in KEYWORDS)

            # Special condition for Reddit: Only take [Hiring] posts, ignore [For Hire]
            if "reddit.com" in feed_url:
                is_valid_client = "hiring" in title.lower()
            else:
                is_valid_client = True # WWR and Remotive posts are inherently company hiring posts

            if matched_keyword and is_valid_client and url and url not in existing_urls:
                contacts = extract_contacts(full_text)
                
                lead_data = {
                    "Source": feed_url.split('/')[2],
                    "Title": title,
                    "URL": url,
                    "Email": contacts["Email"],
                    "Telegram": contacts["Telegram"],
                    "Mobile": contacts["Mobile"],
                    "Snippet": re.sub(r'<[^>]+>', '', snippet)[:200].strip()
                }
                save_lead_to_csv(lead_data)
                existing_urls.add(url)
                total_new += 1
                print(f"  [+] Saved Client Lead: {title[:40]}... | Email: {contacts['Email']}")

    print(f"\n[SUCCESS] Badha feeds mathi maliine total {total_new} clean client leads save thai gai!")

if __name__ == "__main__":
    fetch_all_feeds()
import csv
import os
import re
import urllib.request
import xml.etree.ElementTree as ET

# 1. Direct Public RSS Feed
FEED_URL = "https://www.reddit.com/r/forhire/new/.rss"

# 2. CSV File Name
CSV_FILE = "leads_perfect.csv"

# 3. Keywords to filter relevant posts
KEYWORDS = ["python", "developer", "freelance", "remote", "script", "react", "fullstack"]

def extract_contacts(text):
    """Text ma thi Email, Telegram, ane Mobile / Phone Number extract karse."""
    contacts = {
        "Email": "Not Found", 
        "Telegram": "Not Found", 
        "Mobile": "Not Found"
    }
    
    # Email regex pattern
    emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', text)
    if emails:
        contacts["Email"] = ", ".join(set(emails))
        
    # Telegram handle regex pattern (e.g., @username)
    telegram = re.findall(r'@[a-zA-Z0-9_]{4,}', text)
    if telegram:
        contacts["Telegram"] = ", ".join(set(telegram))
        
    # Mobile / Phone Number regex pattern (supports international + country codes & standard numbers)
    # E.g., +1-555-555-5555, +91 9876543210, (555) 555-5555
    phones = re.findall(r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', text)
    if phones:
        # Filter out tiny matching numbers that are just random digits
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
        fieldnames = ["Title", "URL", "Published", "Email", "Telegram", "Mobile", "Snippet"]
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        
        if not file_exists:
            writer.writeheader()
            
        writer.writerow(lead_data)

def fetch_reddit_feed():
    print("[INFO] Fetching direct live feed and extracting all contacts...")
    
    req = urllib.request.Request(
        FEED_URL, 
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    )
    
    try:
        with urllib.request.urlopen(req) as response:
            xml_data = response.read()
    except Exception as e:
        print(f"[ERROR] Feed fetch karta vakhte bhul aai: {e}")
        return

    root = ET.fromstring(xml_data)
    namespace = {'atom': 'http://www.w3.org/2005/Atom'}
    entries = root.findall('atom:entry', namespace)
    
    existing_urls = get_existing_urls()
    new_leads_count = 0

    for entry in entries:
        title_elem = entry.find('atom:title', namespace)
        link_elem = entry.find('atom:link', namespace)
        updated_elem = entry.find('atom:updated', namespace)
        content_elem = entry.find('atom:content', namespace)

        title = title_elem.text if title_elem is not None else ""
        url = link_elem.attrib.get('href', '') if link_elem is not None else ""
        published = updated_elem.text if updated_elem is not None else ""
        snippet = content_elem.text if content_elem is not None else ""
        
        # Clean HTML tags
        snippet_clean = snippet.replace("<br>", " ").replace("<b>", "").replace("</b>", "").replace("&amp;", "&")
        
        full_text = title + " " + snippet_clean
        
        # Check keywords AND prioritize "[Hiring]" posts so you get real clients
        matched_keyword = any(kw.lower() in full_text.lower() for kw in KEYWORDS)
        is_hiring = "hiring" in title.lower()

        if matched_keyword and is_hiring and url and url not in existing_urls:
            contacts = extract_contacts(full_text)
            
            lead_data = {
                "Title": title,
                "URL": url,
                "Published": published,
                "Email": contacts["Email"],
                "Telegram": contacts["Telegram"],
                "Mobile": contacts["Mobile"],
                "Snippet": snippet_clean[:200].strip()
            }
            save_lead_to_csv(lead_data)
            existing_urls.add(url)
            new_leads_count += 1
            print(f"  [+] Saved Client Lead: {title[:40]}... | Email: {contacts['Email']} | Mobile: {contacts['Mobile']}")

    print(f"\n[SUCCESS] Process puri thayi! Total {new_leads_count} client leads mobile, email ane telegram sathe save thai gyi che.")

if __name__ == "__main__":
    fetch_reddit_feed()
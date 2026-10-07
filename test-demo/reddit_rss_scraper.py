import csv
import feedparser
import re
import html

# Target Subreddits
SUBREDDITS = [
    "forhire",
    "freelance_forhire",
    "jobbit"
]

def clean_html(raw_html):
    cleanr = re.compile('<.*?>')
    cleanned = re.sub(cleanr, '', raw_html)
    return html.unescape(cleanned)

def extract_contacts(text):
    contacts = []
    
    # 1. Email finder
    emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
    if emails:
        contacts.append(f"Email: {', '.join(set(emails))}")
        
    # 2. Discord finder
    discord = re.findall(r'(discord\.gg\/[a-zA-Z0-9]+|[a-zA-Z0-9_]{2,32}#\d{4})', text)
    if discord:
        contacts.append(f"Discord: {', '.join(set(discord))}")
        
    # 3. Telegram finder
    telegram = re.findall(r'(t\.me\/[a-zA-Z0-9_]+|@[a-zA-Z0-9_]{4,})', text)
    if telegram:
        contacts.append(f"Telegram: {', '.join(set(telegram))}")
        
    if not contacts:
        contacts.append("Reddit PM / DM Only")
        
    return " | ".join(contacts)

def run_reddit_rss_scraper():
    print("=" * 60)
    print("      REDDIT RSS FEED LEAD COLLECTOR")
    print("=" * 60)

    leads = []
    seen_urls = set()

    for sub in SUBREDDITS:
        rss_url = f"https://www.reddit.com/r/{sub}/new/.rss"
        print(f"\n[INFO] Fetching posts from r/{sub} via RSS...")
        
        try:
            feed = feedparser.parse(rss_url, agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
            
            if not feed.entries:
                print(f"  [WARN] No entries found for r/{sub}.")
                continue

            print(f"  -> Found {len(feed.entries)} recent posts.")

            for entry in feed.entries:
                title = entry.get("title", "")
                link = entry.get("link", "")
                raw_summary = entry.get("summary", "")
                
                if not link or link in seen_urls:
                    continue
                seen_urls.add(link)

                clean_summary = clean_html(raw_summary)
                text_to_check = (title + " " + clean_summary).lower()
                
                # Check for hiring keywords
                if any(kw in text_to_check for kw in ["hiring", "looking for", "need", "developer", "freelance"]):
                    
                    contact_info = extract_contacts(clean_summary)
                    
                    leads.append({
                        "Subreddit": f"r/{sub}",
                        "Title": title,
                        "Post_URL": link,
                        "Contact_Details": contact_info,
                        "Snippet": clean_summary[:250].replace("\n", " ")
                    })

        except Exception as e:
            print(f"  [ERROR] Failed to fetch r/{sub}: {e}")

    # Export to CSV
    output_file = "reddit_rss_leads.csv"
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["Subreddit", "Title", "Post_URL", "Contact_Details", "Snippet"])
        writer.writeheader()
        writer.writerows(leads)

    print("\n" + "-" * 60)
    print(f"[SUCCESS] Collected {len(leads)} active hiring posts.")
    print(f"[INFO] Saved to '{output_file}'.")

if __name__ == "__main__":
    run_reddit_rss_scraper()

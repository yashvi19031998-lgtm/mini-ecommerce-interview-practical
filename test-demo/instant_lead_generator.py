import requests
import pandas as pd
from datetime import datetime
import time
import re

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
        contacts.append("Check Post URL (PM / DM)")
        
    return " | ".join(contacts)

def fetch_reddit_leads():
    print("Fetching leads from Reddit...")
    leads = []
    subreddits = ['forhire', 'freelance_forhire']
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    for sub in subreddits:
        try:
            url = f'https://www.reddit.com/r/{sub}/new.json?limit=30'
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                data = response.json()
                for post in data['data']['children']:
                    post_data = post['data']
                    title = post_data.get('title', '').lower()
                    selftext = post_data.get('selftext', '')
                    
                    # Filter for hiring posts
                    if '[hiring]' in title or 'hiring' in title or 'looking for' in title:
                        full_text = title + " " + selftext
                        contact_info = extract_contacts(full_text)
                        
                        leads.append({
                            'Platform': 'Reddit',
                            'Date Found': datetime.now().strftime("%Y-%m-%d"),
                            'Client Name / Handle': f"u/{post_data.get('author', 'unknown')}",
                            'Job Title / Requirement': post_data.get('title', ''),
                            'Direct URL': f"https://reddit.com{post_data.get('permalink', '')}",
                            'Contact Method': contact_info,
                            'Status': 'New'
                        })
            time.sleep(1) # Be nice to the API
        except Exception as e:
            print(f"Error fetching from r/{sub}: {e}")
            
    return leads

def fetch_hackernews_leads():
    print("Fetching leads from Hacker News...")
    leads = []
    try:
        # Search Algolia API for recent "who is hiring" or "freelance" posts
        url = 'https://hn.algolia.com/api/v1/search_by_date?query="looking for" OR "hiring"&tags=story'
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            for hit in data.get('hits', [])[:15]:
                full_text = hit.get('title', '')
                contact_info = extract_contacts(full_text)
                
                leads.append({
                    'Platform': 'Hacker News',
                    'Date Found': datetime.now().strftime("%Y-%m-%d"),
                    'Client Name / Handle': hit.get('author', 'unknown'),
                    'Job Title / Requirement': hit.get('title', ''),
                    'Direct URL': f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}",
                    'Contact Method': contact_info,
                    'Status': 'New'
                })
    except Exception as e:
        print(f"Error fetching from Hacker News: {e}")
        
    return leads

def main():
    print("Starting Instant Lead Generator with Contact Extraction...")
    
    reddit_leads = fetch_reddit_leads()
    hn_leads = fetch_hackernews_leads()
    
    all_leads = reddit_leads + hn_leads
    
    if not all_leads:
        print("No leads found at this time. Try again later.")
        return

    # Convert to DataFrame and save to CSV
    df = pd.DataFrame(all_leads)
    
    # Check if file exists to append or write new
    filename = 'instant_leads_master.csv'
    try:
        existing_df = pd.read_csv(filename)
        # Drop duplicates based on URL
        combined_df = pd.concat([existing_df, df]).drop_duplicates(subset=['Direct URL'], keep='first')
        combined_df.to_csv(filename, index=False)
        print(f"Added {len(combined_df) - len(existing_df)} new leads to {filename}")
    except FileNotFoundError:
        df.to_csv(filename, index=False)
        print(f"Created {filename} with {len(df)} leads")
        
    print("Lead generation complete! Open instant_leads_master.csv to view them.")

if __name__ == '__main__':
    main()

import requests
import pandas as pd
from datetime import datetime
import time
import re
from typing import List, Dict, Any

def extract_contacts_dict(text: str) -> Dict[str, str]:
    """Extracts email, phone, discord, telegram from text."""
    # 1. Email finder
    emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z]{2,}', text)
    clean_emails = [e.lower() for e in emails if not e.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg'))]
    
    # 2. Discord finder
    discord = re.findall(r'(discord\.gg\/[a-zA-Z0-9]+|[a-zA-Z0-9_]{2,32}#\d{4})', text)
    
    # 3. Telegram finder
    telegram = re.findall(r'(t\.me\/[a-zA-Z0-9_]+|@[a-zA-Z0-9_]{4,})', text)
    
    # 4. Phone finder
    phones = re.findall(r'(\+?\d[\d\s\-\(\)]{8,15}\d)', text)
    valid_phones = [p.strip() for p in phones if len(re.sub(r'\D', '', p)) >= 10]

    return {
        "email": ", ".join(sorted(set(clean_emails))),
        "phone": valid_phones[0] if valid_phones else "",
        "discord": ", ".join(set(discord)),
        "telegram": ", ".join(set(telegram))
    }

def fetch_reddit_leads() -> List[Dict[str, Any]]:
    print("Fetching live leads from Reddit client subreddits...")
    leads = []
    subreddits = ['forhire', 'freelance_forhire', 'jobbit', 'remotework']
    headers = {
        'User-Agent': 'LeadFinderBot/2.5 (Automated Tech Hiring Harvester; contact: info@leadgen.com)'
    }

    for sub in subreddits:
        try:
            url = f'https://www.reddit.com/r/{sub}/new.json?limit=25'
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                for post in data.get('data', {}).get('children', []):
                    post_data = post.get('data', {})
                    raw_title = post_data.get('title', '')
                    title_lower = raw_title.lower()
                    selftext = post_data.get('selftext', '')
                    
                    # Strictly skip [FOR HIRE] job seekers! We want CLIENTS HIRING!
                    if '[for hire]' in title_lower or '[for-hire]' in title_lower or 'for hire' in title_lower:
                        continue

                    # Filter for client hiring posts
                    if '[hiring]' in title_lower or 'hiring' in title_lower or 'looking for' in title_lower or 'need a developer' in title_lower or 'need developer' in title_lower or 'budget' in title_lower:
                        full_text = f"{raw_title} {selftext}"
                        contacts = extract_contacts_dict(full_text)
                        
                        leads.append({
                            'Platform': f'Reddit (r/{sub})',
                            'Date Found': datetime.now().strftime("%Y-%m-%d"),
                            'Client Name / Handle': f"u/{post_data.get('author', 'unknown')}",
                            'Job Title / Requirement': raw_title,
                            'Direct URL': f"https://reddit.com{post_data.get('permalink', '')}",
                            'Email': contacts["email"],
                            'Mobile Number': contacts["phone"],
                            'Contact Method': f"Email: {contacts['email']} | Telegram: {contacts['telegram']}".strip(" |"),
                            'Snippet': selftext[:300].strip(),
                            'Status': 'New'
                        })
            time.sleep(1)
        except Exception as e:
            print(f"  [Reddit API notice on r/{sub}] {e}")
            
    return leads

def fetch_hackernews_leads() -> List[Dict[str, Any]]:
    print("Fetching leads from Hacker News Algolia API...")
    leads = []
    queries = ['"who is hiring"', '"looking for" developer', '"seeking freelancer"', 'hiring fullstack']
    for q in queries:
        try:
            url = f'https://hn.algolia.com/api/v1/search_by_date?query={requests.utils.quote(q)}&tags=story&hitsPerPage=10'
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                for hit in data.get('hits', []):
                    raw_title = hit.get('title', '')
                    item_url = hit.get('url') or f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}"
                    story_text = hit.get('story_text') or ''
                    contacts = extract_contacts_dict(f"{raw_title} {story_text}")
                    
                    leads.append({
                        'Platform': 'Hacker News',
                        'Date Found': datetime.now().strftime("%Y-%m-%d"),
                        'Client Name / Handle': hit.get('author', 'unknown'),
                        'Job Title / Requirement': raw_title,
                        'Direct URL': item_url,
                        'Email': contacts["email"],
                        'Mobile Number': contacts["phone"],
                        'Contact Method': contacts["email"] or "HN Post Discussion",
                        'Snippet': (story_text or raw_title)[:300].strip(),
                        'Status': 'New'
                    })
            time.sleep(0.5)
        except Exception as e:
            print(f"  [HN Algolia notice] {e}")
            
    return leads

def fetch_remoteok_leads() -> List[Dict[str, Any]]:
    print("Fetching live tech hiring leads from RemoteOK API...")
    leads = []
    try:
        url = 'https://remoteok.com/api'
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)'}
        resp = requests.get(url, headers=headers, timeout=12)
        if resp.status_code == 200:
            items = resp.json()
            # First item in remoteok API is metadata
            for item in items[1:35]:
                company = item.get('company') or 'Tech Company'
                position = item.get('position') or 'Developer Requirement'
                job_url = item.get('apply_url') or item.get('url') or ''
                desc = re.sub(r'<[^>]+>', ' ', item.get('description', ''))[:300].strip()
                contacts = extract_contacts_dict(desc)

                leads.append({
                    'Platform': 'RemoteOK API',
                    'Date Found': datetime.now().strftime("%Y-%m-%d"),
                    'Client Name / Handle': company,
                    'Job Title / Requirement': f"{position} at {company}",
                    'Direct URL': job_url,
                    'Email': contacts["email"],
                    'Mobile Number': contacts["phone"],
                    'Location': item.get('location') or 'Remote',
                    'Contact Method': item.get('apply_url') or job_url,
                    'Snippet': desc,
                    'Status': 'New'
                })
    except Exception as e:
        print(f"  [RemoteOK API notice] {e}")

    return leads

def fetch_jobicy_leads() -> List[Dict[str, Any]]:
    print("Fetching verified remote jobs leads from Jobicy API...")
    leads = []
    try:
        url = 'https://jobicy.com/api/v2/remote-jobs?count=25'
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        resp = requests.get(url, headers=headers, timeout=12)
        if resp.status_code == 200:
            data = resp.json()
            for job in data.get('jobs', []):
                company = job.get('companyName') or 'Hiring Company'
                title = job.get('jobTitle') or 'Developer'
                job_url = job.get('url') or ''
                snippet = re.sub(r'<[^>]+>', ' ', job.get('jobExcerpt') or job.get('jobDescription') or '')[:300].strip()
                contacts = extract_contacts_dict(snippet)

                leads.append({
                    'Platform': 'Jobicy Remote API',
                    'Date Found': datetime.now().strftime("%Y-%m-%d"),
                    'Client Name / Handle': company,
                    'Job Title / Requirement': f"{title} - {company}",
                    'Direct URL': job_url,
                    'Email': contacts["email"],
                    'Mobile Number': contacts["phone"],
                    'Location': job.get('jobGeo') or 'Remote',
                    'Contact Method': job_url,
                    'Snippet': snippet,
                    'Status': 'New'
                })
    except Exception as e:
        print(f"  [Jobicy API notice] {e}")

    return leads

def main():
    print("=" * 60)
    print("      MULTI-API INSTANT LEAD GENERATION SYSTEM")
    print("=" * 60)
    
    reddit_leads = fetch_reddit_leads()
    hn_leads = fetch_hackernews_leads()
    rok_leads = fetch_remoteok_leads()
    jobicy_leads = fetch_jobicy_leads()
    
    all_leads = reddit_leads + hn_leads + rok_leads + jobicy_leads
    
    if not all_leads:
        print("[INFO] No leads found at this time.")
        return

    df = pd.DataFrame(all_leads)
    filename = 'instant_leads_master.csv'
    try:
        existing_df = pd.read_csv(filename)
        combined_df = pd.concat([existing_df, df]).drop_duplicates(subset=['Direct URL'], keep='first')
        combined_df.to_csv(filename, index=False)
        print(f"[SUCCESS] Added {len(combined_df) - len(existing_df)} new leads to {filename}")
    except FileNotFoundError:
        df.to_csv(filename, index=False)
        print(f"[SUCCESS] Created {filename} with {len(df)} leads")
        
    print(f"[INFO] Harvest complete! Total records collected: {len(all_leads)}")

if __name__ == '__main__':
    main()

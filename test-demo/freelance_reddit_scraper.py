import csv
import re
import time
from ddgs import DDGS

# Expanded queries for each platform
PLATFORM_QUERIES = [
    # Reddit
    {
        "name": "Reddit (r/forhire)",
        "queries": [
            "site:reddit.com/r/forhire hiring developer",
            "site:reddit.com/r/forhire \"hiring\" \"software\"",
            "site:reddit.com/r/forhire \"looking for\" developer",
        ],
    },
    # Reddit freelance
    {
        "name": "Reddit (r/freelance_forhire)",
        "queries": [
            "site:reddit.com/r/freelance_forhire hiring",
            "site:reddit.com/r/freelance_forhire \"looking for\"",
        ],
    },
    # Freelancer
    {
        "name": "Freelancer.com",
        "queries": [
            "site:freelancer.com/projects \"software\"",
            "site:freelancer.com/projects \"web development\"",
            "site:freelancer.com/projects \"python\"",
        ],
    },
    # Upwork
    {
        "name": "Upwork.com",
        "queries": [
            "site:upwork.com/jobs \"python\"",
            "site:upwork.com/jobs \"software developer\"",
            "site:upwork.com/jobs \"web development\"",
        ],
    },
    # Twitter (X)
    {
        "name": "Twitter (X)",
        "queries": [
            "site:twitter.com \"hiring\" \"developer\"",
            "site:twitter.com \"looking for\" \"software\"",
        ],
    },
]

# Regex patterns for contact extraction
EMAIL_REGEX = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}")
DISCORD_REGEX = re.compile(r"discord[:#]?\s*[A-Za-z0-9_-]+", re.I)
URL_REGEX = re.compile(r"https?://[^\s)]+")

OUTPUT_CSV = "freelance_reddit_leads_v2.csv"

def search_ddg(query, max_results=20):
    results = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append(r)
                time.sleep(0.5)  # gentle throttle
    except Exception as e:
        print(f"[ERROR] DDG search failed for '{query}': {e}")
    return results

def extract_contacts(text: str) -> dict:
    email = EMAIL_REGEX.search(text)
    discord = DISCORD_REGEX.search(text)
    url = URL_REGEX.search(text)
    return {
        "email": email.group(0) if email else "",
        "discord": discord.group(0) if discord else "",
        "url": url.group(0) if url else "",
    }

def run_freelance_scraper():
    print("=" * 60)
    print("      FREELANCE & REDDIT LEAD COLLECTOR (ROBUST)")
    print("=" * 60)

    leads = []
    seen = set()

    for platform in PLATFORM_QUERIES:
        name = platform["name"]
        print(f"\n[INFO] Searching {name}...")
        platform_hits = []
        for q in platform["queries"]:
            print(f"  -> Query: {q}")
            results = search_ddg(q)
            for r in results:
                url = r.get("href") or r.get("url")
                if not url or url in seen:
                    continue
                seen.add(url)
                platform_hits.append((url, r.get("title", ""), r.get("body", "")))
            if platform_hits:
                break  # stop after first successful query
            time.sleep(1)
        if not platform_hits:
            print(f"  [WARN] No results for {name} after all queries.")
            continue
        print(f"[INFO] Collected {len(platform_hits)} raw hits for {name}.")
        for url, title, snippet in platform_hits:
            contacts = extract_contacts(snippet)
            leads.append({
                "Platform": name,
                "Title": title,
                "Post_URL": url,
                "Extracted_Email_Contact": contacts["email"],
                "Extracted_Discord_Contact": contacts["discord"],
                "Extracted_External_URL": contacts["url"],
                "Description_Snippet": snippet[:300],
            })
        time.sleep(2)

    if not leads:
        print("[INFO] No leads collected.")
        return

    fieldnames = [
        "Platform",
        "Title",
        "Post_URL",
        "Extracted_Email_Contact",
        "Extracted_Discord_Contact",
        "Extracted_External_URL",
        "Description_Snippet",
    ]
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(leads)
    print("\n" + "-" * 60)
    print(f"[SUCCESS] Exported {len(leads)} leads to {OUTPUT_CSV}")

if __name__ == "__main__":
    run_freelance_scraper()

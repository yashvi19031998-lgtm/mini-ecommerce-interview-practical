import csv
import time
try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS

# 20 Pre-generated targeted search queries (Google Dorks style)
QUERIES = [
    'site:reddit.com/r/forhire "hiring" "python"',
    'site:reddit.com/r/forhire "hiring" "react"',
    'site:reddit.com/r/forhire "hiring" "full stack"',
    'site:reddit.com/r/freelance_forhire "looking for" "developer"',
    'site:reddit.com/r/freelance_forhire "need" "programmer"',
    'site:reddit.com/r/jobbit "hiring"',
    'site:reddit.com/r/jobbit "remote"',
    'site:reddit.com/r/forhire "backend developer"',
    'site:reddit.com/r/forhire "frontend developer"',
    'site:reddit.com/r/forhire "freelance project"',
    'site:twitter.com "hiring developer" "python"',
    'site:twitter.com "looking for developer" "react"',
    'site:twitter.com "need a freelancer" "web"',
    'site:upwork.com/jobs "python developer"',
    'site:upwork.com/jobs "full stack developer"',
    'site:upwork.com/jobs "react developer"',
    'site:news.ycombinator.com "who is hiring" "remote"',
    'site:news.ycombinator.com "freelance" "developer"',
    'site:dev.to "hiring" "software engineer"',
    'site:github.com "looking for" "developer"'
]

def run_bulk_scraper():
    print("=" * 60)
    print("      BULK LEAD SCRAPER (20 QUERIES AUTOMATION)")
    print("=" * 60)

    all_leads = []
    seen_urls = set()

    # Using DDGS context manager
    with DDGS() as ddgs:
        for idx, query in enumerate(QUERIES, 1):
            print(f"\n[INFO] ({idx}/20) Running query: {query}")
            try:
                # Fetch up to 5 results per query
                results = ddgs.text(query, max_results=5)
                
                if results:
                    count = 0
                    for r in results:
                        url = r.get("href", "")
                        if url and url not in seen_urls:
                            seen_urls.add(url)
                            all_leads.append({
                                "Search_Query": query,
                                "Title": r.get("title", ""),
                                "Direct_URL": url,
                                "Snippet": r.get("body", "").replace("\n", " ")
                            })
                            count += 1
                    print(f"  -> Captured {count} new unique leads.")
                else:
                    print("  -> No results found for this query.")
                
                # Brief pause to prevent rate-limiting or blocks
                time.sleep(2.5)

            except Exception as e:
                print(f"  [ERROR] Failed query due to: {e}")

    # Export all collected leads into a CSV file
    output_file = "bulk_leads_output.csv"
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["Search_Query", "Title", "Direct_URL", "Snippet"])
        writer.writeheader()
        writer.writerows(all_leads)

    print("\n" + "=" * 60)
    print(f"[SUCCESS] Total unique leads collected: {len(all_leads)}")
    print(f"[INFO] Successfully exported to '{output_file}'.")
    print("=" * 60)

if __name__ == "__main__":
    run_bulk_scraper()

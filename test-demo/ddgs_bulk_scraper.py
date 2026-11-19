import csv
import time
try:
    from duckduckgo_search import DDGS
except ImportError:
    try:
        from ddgs import DDGS
    except ImportError:
        DDGS = None

# 20 High-Intent Targeted Search Queries (Validated High-Conversion Google Dorks)
QUERIES = [
    # 1. RFPs, RFQs & Vendor Selection
    '("request for proposal" OR "request for quotation" OR RFP OR RFQ) ("web development" OR "mobile app development" OR "custom software" OR "CRM implementation") ("vendor" OR "agency" OR "development partner")',
    '("looking for web development agency" OR "looking for software development company" OR "need development agency" OR "hire development agency") ("budget" OR "proposal" OR "quote" OR "RFP")',
    'site:*.org ("RFP" OR "request for proposal") ("website redesign" OR "web application" OR "mobile application" OR "CRM" OR "software development") ("proposal due" OR "submission deadline")',
    '("vendor selection" OR "selecting a vendor" OR "development partner" OR "technology partner") ("custom software" OR "web application" OR "mobile app" OR "CRM") ("United States" OR "UK" OR "Canada" OR "Australia" OR "UAE")',
    '("seeking proposals" OR "inviting proposals" OR "requesting proposals") ("website" OR "web portal" OR "mobile app" OR "custom software" OR "CRM integration") ("proposal deadline" OR "submission date")',
    
    # 2. Maintenance, Fixes & Framework Migrations
    '("website maintenance" OR "website support" OR "WordPress maintenance" OR "website AMC") ("looking for" OR "need" OR "hire") ("agency" OR "developer" OR "company")',
    '("WordPress broken" OR "WordPress hacked" OR "WordPress slow" OR "WordPress error" OR "website down") ("need developer" OR "looking for developer" OR "need help" OR "urgent")',
    '("PHP migration" OR "Laravel migration" OR "CodeIgniter migration" OR "legacy PHP" OR "PHP upgrade") ("looking for" OR "need" OR "hire") ("developer" OR "agency" OR "development company")',
    '("Node.js migration" OR "Angular migration" OR "React migration" OR "Next.js migration" OR "legacy application modernization") ("need" OR "looking for" OR "hire") ("developer" OR "agency" OR "software company")',
    '("website speed optimization" OR "Core Web Vitals" OR "website performance audit" OR "site speed fix") ("need" OR "looking for" OR "hire") ("developer" OR "WordPress expert" OR "agency")',

    # 3. CRM, Dashboards & Creative Needs
    '("need CRM integration" OR "CRM integration project" OR "HubSpot integration" OR "Salesforce integration" OR "Zoho CRM integration") ("looking for" OR "need" OR "hire") ("developer" OR "agency" OR "development company")',
    '("custom dashboard" OR "admin dashboard" OR "reporting dashboard" OR "business dashboard") ("need" OR "looking for" OR "hire") ("developer" OR "web development agency" OR "software company")',
    '("ecommerce" OR "e-commerce" OR "Shopify" OR "WooCommerce" OR "DTC brand") ("need" OR "looking for") ("custom development" OR "integration" OR "CRM" OR "mobile app" OR "dashboard") ("developer" OR "agency")',
    '("need social media content" OR "looking for content creator" OR "need reels" OR "need short form video" OR "social media creatives") ("business" OR "brand" OR "company") ("hire" OR "agency" OR "freelancer")',
    '("need branding" OR "rebranding" OR "brand identity" OR "festival creatives" OR "social media design") ("looking for" OR "need" OR "hire") ("design agency" OR "creative agency" OR "freelancer")',

    # 4. Competitor Agency Footprints & Direct Hires
    'site:radixweb.com OR site:tatvasoft.com OR site:bacancytechnology.com OR site:mindinventory.com OR site:hyperlinkinfosystem.com ("case study" OR "portfolio" OR "client" OR "success story")',
    '"Radixweb" OR "Tatvasoft" OR "Bacancy" OR "Mindinventory" OR "Hyperlink InfoSystem" ("powered by" OR "developed by" OR "designed by" OR "built by") -site:radixweb.com -site:tatvasoft.com -site:bacancytechnology.com -site:mindinventory.com -site:hyperlinkinfosystem.com',
    '("looking for mobile app development company" OR "need Flutter developer" OR "need React Native developer") ("budget" OR "hire" OR "agency")',
    '("hire dedicated PHP developer" OR "hire Laravel developer" OR "hire CodeIgniter developer") ("hourly rate" OR "dedicated developer" OR "agency")',
    '("looking for Next.js developer" OR "looking for Angular developer" OR "hire Node.js developer") ("contract" OR "remote" OR "agency")',
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

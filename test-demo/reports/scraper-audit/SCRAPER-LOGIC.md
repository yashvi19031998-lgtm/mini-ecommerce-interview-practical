# Detailed Scraper Logic & Architectural Data Flow Audit

**Project:** `test-demo`  
**Location:** `c:\xampp\htdocs\Yashvi-Practical\test-demo`  
**Audit Date:** October 12, 2026  

---

## Overview

This report breaks down the internal architecture, algorithmic steps, data transformations, filtering heuristics, and failure modes for all 10 scrapers found in the project.

---

## 1. [`scraper.py`](file:///c:/xampp/htdocs/Yashvi-Practical/test-demo/scraper.py) — Public IT & Software Hiring Lead Scraper (High-Accuracy Engine)

### 1. Starting Point
Triggered via manual CLI command: `python scraper.py` from the main entry point `if __name__ == "__main__": main()`.

### 2. Source
Multi-engine search discovery:
- Primary: Google Search via `googlesearch-python` (`google_search(query)`).
- Secondary / Fallbacks: Yahoo Search (`https://search.yahoo.com/search?p=...`) and Bing Search (`https://www.bing.com/search?q=...`) via direct HTTP requests.
- Downstream: The actual target business website discovered in search results, plus up to 2 discovered internal contact subpages (`/contact`, `/about-us`, etc.).

### 3. Input
- `SEARCH_QUERIES`: 10 intent-based phrases (`"looking for software development company"`, `"need web development company"`, `"hire software development company"`, etc.).
- `SEARCH_LOCATION`: Hardcoded as `"Ahmedabad"` (appended to each search query).
- `MAX_RESULTS_PER_QUERY`: 10 URLs evaluated per query.
- `MIN_LEAD_SCORE`: Quality cutoff threshold set to `4`.

### 4. Collection Logic (Step-by-Step)
1. Combines each query with location (e.g. `"hire software development company" Ahmedabad`).
2. Invokes `search_web()`: Attempts Google search first. If Google blocks/rate-limits, switches to `search_public_engine()` parsing Yahoo (`div.compTitle a` with `/RU=` redirection decode) and Bing (`li.b_algo h2 a` with base64 `&u=a1...` tracking decode).
3. Evaluates discovered URLs against `filter_search_result()`.
4. Keeps track of unique domains in `seen_domains` set.
5. For each accepted candidate site, runs `crawl_and_evaluate()`:
   - Fetches homepage HTML via `fetch_page()` with browser User-Agent.
   - Extracts Company Name via OpenGraph (`og:site_name`), application-name meta, Schema.org JSON-LD (`Organization`/`LocalBusiness`), `<title>` delimiter splitting, and domain fallback.
   - Extracts emails (from `mailto:` and regex) and validates against blacklist.
   - Extracts Indian phone numbers via regex and normalizes (`+91` mobile or `079-` STD landline).
   - If contact details are missing, discovers internal subpage links matching keywords (`contact`, `about`, `company`) and fetches up to 2 subpages to complete contact details.
   - Analyzes intent and classifies site type via `analyze_intent_and_type()`.
   - Computes weighted score via `calculate_lead_score()`.
6. Compares score against `MIN_LEAD_SCORE` (4).
7. If qualified, appends to `accepted_leads` dictionary (keyed by domain). If rejected, appends to `rejected_leads` list.

### 5. Pagination
No deep multi-page pagination on search engines; fetches the top `MAX_RESULTS_PER_QUERY` (10) search hits per query.

### 6. Extraction
- **Company Name:** Cleaned brand name without generic suffixes (e.g. removes "Pvt Ltd", "Home | Services", "Official Website").
- **Website URL:** Base target URL.
- **Email:** Strict RFC-like regex with domain exclusion. Prioritizes business prefixes (`info@`, `contact@`, `sales@`, `hello@`).
- **Mobile / Phone:** Strictly validated Indian mobile (`+91 98765 43210`) and landline (`079-40001234`).
- **Search Query:** Search query string that produced the lead.
- **Intent Level:** `High`, `Medium`, or `Low`.
- **Lead Type:** `Potential Buyer`, `IT Service Provider`, `Blog/Article`, or `Unknown`.
- **Lead Score:** Integer score.

### 7. Filtering
- **Domain Exclusion List:** 45+ blacklisted domains spanning Social media (Facebook, Instagram, LinkedIn, Reddit, Twitter), Search engines, Dictionaries (Cambridge, Merriam-Webster, Britannica), Media streaming (Hotstar, Netflix, IMDb), and Directories/YellowPages (Justdial, IndiaMART, Upwork, Fiverr, Clutch, GoodFirms).
- **Keyword Filtering:** Discards URLs or titles containing dictionary words (`dictionary`, `thesaurus`, `grammar`) or entertainment words (`streaming`, `movie`, `tv-show`).
- **Seller vs. Buyer Discrimination:** Detects service sellers (`"we provide software development"`, `"our IT services"`) and penalizes them by `-5` points so only hiring/buying clients qualify.

### 8. Deduplication
- Search result level: In-memory `seen_domains` set.
- Candidate lead level: Dictionary `accepted_leads` keyed by root domain. If the same business appears under multiple queries, it merges the search queries (`Query1 | Query2`).

### 9. Validation
- Emails: Excludes image extensions (`.png`, `.jpg`), placeholder domains (`example.com`, `test.com`, `wixpress.com`, `sentry.io`), and length boundaries (6 to 60 characters).
- Phones: Rejects non-Indian formats, repetitive digits (e.g. `9999999999`), timestamps, and dates. Formats into `+91 XXXXX XXXXX` or `079-XXXXXXX`.

### 10. Storage
- Qualified leads: Saved to [`leads.csv`](file:///c:/xampp/htdocs/Yashvi-Practical/test-demo/leads.csv) with columns: `No`, `Company Name`, `Website URL`, `Email`, `Mobile Number`, `Search Query`, `Intent`, `Lead Type`, `Lead Score`.
- Rejected candidates: Saved to [`rejected_leads.csv`](file:///c:/xampp/htdocs/Yashvi-Practical/test-demo/rejected_leads.csv) with columns: `Company Name`, `Website URL`, `Rejection Reason`, `Lead Type`, `Score`.

### 11. Error Handling
- Handles HTTP timeouts (`REQUEST_TIMEOUT = 10s`).
- Handles rate-limiting on Google by logging a graceful fallback message and switching to Yahoo/Bing.
- Handles malformed URLs and redirects with `try-except` blocks.

### 12. Dependencies
- Python packages: `requests`, `beautifulsoup4`, `pandas`, `googlesearch-python` (optional import).
- No API keys or environment variables required.

---

## 2. [`lead_generation_master.py`](file:///c:/xampp/htdocs/Yashvi-Practical/test-demo/lead_generation_master.py) — Multi-Source Lead Generation & Deep Contact Harvester

### 1. Starting Point
Triggered via CLI: `python lead_generation_master.py` calling `run_lead_pipeline()`.

### 2. Source
3 distinct channels:
1. Reddit RSS feed (`https://www.reddit.com/r/{subreddit}/new/.rss`).
2. WeWorkRemotely RSS feed (`https://weworkremotely.com/categories/remote-programming-jobs.rss`).
3. Justdial Local Business directory (`https://www.justdial.com/{location}/{search_query}`) via automated Playwright Chromium browser.
4. Target company websites discovered in listings/posts (deep crawled for contacts).

### 3. Input
- Reddit: Subreddit name (`"forhire"`), limit (`15`).
- WeWorkRemotely: Category URL, limit (`10`).
- Justdial: Search query (`"Software-Developers"`), location (`"Ahmedabad"`), max results (`15`), headless (`True`).

### 4. Collection Logic (Step-by-Step)
1. **LeadStore Initialization:** Checks [`master_leads.csv`](file:///c:/xampp/htdocs/Yashvi-Practical/test-demo/master_leads.csv). Loads existing URLs and lowercase titles into `seen_identifiers` set for cross-session deduplication.
2. **Channel 1 — Reddit RSS (`RssLeadHarvester`):**
   - Fetches XML via `requests.get()`. Parses Atom `<entry>` elements.
   - Filters out `[for hire]` freelancer posts; requires `[hiring]` client posts.
   - Extracts email, obfuscated email, Telegram handle, and phone numbers from title + content.
   - If an external client website URL is mentioned and email is missing, triggers `ContactExtractor.deep_crawl_website()` to crawl homepage and `/contact` page.
   - Saves new leads to store.
3. **Channel 2 — WeWorkRemotely RSS:**
   - Fetches XML, parses `<item>` tags.
   - Extracts title, link, description.
   - Treats the job link as company website and deep crawls for official emails/phones.
   - Saves new leads to store.
4. **Channel 3 — Justdial Browser Automation (`PlaywrightJustdialScraper`):**
   - Launches Playwright Chromium with anti-detection flags (`--disable-blink-features=AutomationControlled`).
   - Navigates to `https://www.justdial.com/Ahmedabad/Software-Developers`.
   - Closes popups/login modals (`.icon_cross`, `.closebtn`, `#login-close`).
   - Executes mouse wheel scroll cycles (15 cycles, 1200-1600px each) to trigger infinite scroll.
   - Parses business cards (`div.resultbox`, `div.store-details`).
   - Extracts business name, address, phone number (`a[href^="tel:"]` or `.callcontent` / `span[data-phone]`), and website URL.
   - Deep crawls company website to capture official company email.
   - Saves new leads to store.

### 5. Pagination
- RSS: Retrieves latest items in XML feed (up to configured limits).
- Justdial: Infinite scrolling via `page.mouse.wheel()` up to 15 scroll cycles.

### 6. Extraction
- `Business Name/Title`: Post title or business brand name.
- `Source`: Origin platform (e.g. `Reddit (r/forhire)`, `WeWorkRemotely`, `Justdial`).
- `Category`: `Client Hiring`, `Remote Programming`, or local search category.
- `City`: `Remote / Worldwide` or specified city (e.g. `Ahmedabad`).
- `Phone`: Decoded phone number or scraped telephone.
- `Email`: Extracted or enriched email.
- `Telegram`: `@username` Telegram handle.
- `Website`: Direct company website URL.
- `URL`: Detail page or job permalink.
- `Snippet`: Job description or local business address.
- `Scraped At`: Timestamp (`YYYY-MM-DD HH:MM:SS`).

### 7. Filtering
- Reddit: Strictly filters out candidate freelancer submissions (`[for hire]`, `[for-hire]`) to ensure only paying clients are collected.
- Justdial: Skips internal aggregator links (`justdial.com`, `google.com`) when extracting external company websites.

### 8. Deduplication
Persistent cross-run deduplication: Reads `master_leads.csv` on boot, tracks both exact URLs and lowercase business titles. Ignores duplicates before saving.

### 9. Validation
- Emails: Standard regex + Obfuscated regex (`user [at] domain [dot] com`, `user(at)domain.com`).
- Phones: Digit count checking (10 to 13 digits).
- Telegram: Blacklists common word false positives (`@gmail`, `@yahoo`, `@channel`, `@group`).

### 10. Storage
Appends qualified leads directly into [`master_leads.csv`](file:///c:/xampp/htdocs/Yashvi-Practical/test-demo/master_leads.csv) with `utf-8-sig` encoding.

### 11. Error Handling
- Playwright execution wrapped in `try-except-finally` guaranteeing `browser.close()`.
- HTTP and XML parsing errors trapped without crashing pipeline.
- Fallback check: If Playwright is not installed, prints error and gracefully skips Justdial step.

### 12. Dependencies
- Python packages: `requests`, `beautifulsoup4`, `playwright`.
- Playwright browser binary: Chromium.

---

## 3. [`direct_feed_csv.py`](file:///c:/xampp/htdocs/Yashvi-Practical/test-demo/direct_feed_csv.py) — Reddit Direct RSS Lead Harvester

### 1. Starting Point
Triggered via CLI: `python direct_feed_csv.py` executing `fetch_reddit_feed()`.

### 2. Source
Reddit Public RSS feed: `https://www.reddit.com/r/forhire/new/.rss`.

### 3. Input
- `FEED_URL`: Reddit RSS endpoint.
- `KEYWORDS`: `["python", "developer", "freelance", "remote", "script", "react", "fullstack"]`.
- `CSV_FILE`: `"leads_perfect.csv"`.

### 4. Collection Logic
1. Reads existing URLs from `leads_perfect.csv` to prevent duplicate writes.
2. Sends HTTP GET via `urllib.request.urlopen()` with custom User-Agent.
3. Parses XML string with `xml.etree.ElementTree`.
4. Iterates through `<atom:entry>` tags.
5. Extracts title, link URL, published date, and content snippet.
6. Strips basic HTML formatting tags (`<br>`, `<b>`).
7. Checks if full text matches any keyword AND contains `"hiring"` in the title.
8. If matched and URL is unseen, executes regex contact extraction for email, Telegram, mobile.
9. Appends record to CSV file.

### 5. Pagination
Single feed request (latest 25 entries in Reddit's Atom feed).

### 6. Extraction
- `Title`: Post title.
- `URL`: Reddit thread permalink.
- `Published`: Atom updated timestamp.
- `Email`: Regex matches or `"Not Found"`.
- `Telegram`: Regex `@username` or `"Not Found"`.
- `Mobile`: Regex phone number or `"Not Found"`.
- `Snippet`: Cleaned text preview (up to 200 chars).

### 7. Filtering
Requires at least one target tech keyword AND explicit presence of `"hiring"` in post title.

### 8. Deduplication
URL-based deduplication against previously stored entries in `leads_perfect.csv`.

### 9. Validation
Phone numbers must have >= 10 non-digit-stripped characters.

### 10. Storage
Appends to [`leads_perfect.csv`](file:///c:/xampp/htdocs/Yashvi-Practical/test-demo/leads_perfect.csv).

### 11. Error Handling
Traps `urllib.request` network errors in `try-except`.

### 12. Dependencies
Zero external dependencies. Pure Python standard library (`urllib.request`, `xml.etree.ElementTree`, `re`, `csv`, `os`).

---

## 4. [`direct_feed_testing_2.py`](file:///c:/xampp/htdocs/Yashvi-Practical/test-demo/direct_feed_testing_2.py) — Multi-Feed Remote Jobs & Client Harvester

### 1. Starting Point
Triggered via CLI: `python direct_feed_testing_2.py` executing `fetch_all_feeds()`.

### 2. Source
3 RSS endpoints:
1. `https://www.reddit.com/r/forhire/new/.rss`
2. `https://weworkremotely.com/categories/remote-back-end-programming-jobs.rss`
3. `https://remotive.com/remote-jobs/feed`

### 3. Input
- `FEEDS`: Array of 3 RSS URLs.
- `KEYWORDS`: Tech keywords (`python`, `developer`, `freelance`, `remote`, `script`, `react`, `fullstack`).
- `CSV_FILE`: `"all_leads_clean.csv"`.

### 4. Collection Logic
1. Loads existing URLs from `all_leads_clean.csv`.
2. Iterates over each feed URL.
3. Uses custom Reddit User-Agent (`PythonLeadScraper/2.0`) for Reddit, standard browser User-Agent for others.
4. Fetches XML data via `urllib.request`.
5. Supports dual XML structures: RSS 2.0 (`.//item`) and Atom (`atom:entry`).
6. Extracts title, link, and description.
7. Checks keyword matching across combined text.
8. Enforces client hiring rule for Reddit (`"hiring" in title.lower()`), while treating WWR/Remotive as auto-valid.
9. Runs regex contact extractor and appends lead to CSV.

### 5. Pagination
Single-page RSS snapshot per feed.

### 6. Extraction
`Source`, `Title`, `URL`, `Email`, `Telegram`, `Mobile`, `Snippet`.

### 7. Filtering
Tech keyword filter + Reddit hiring post check.

### 8. Deduplication
URL-based check against `all_leads_clean.csv`.

### 9. Validation
Phone numbers validated for >= 10 digits; HTML tags stripped via regex.

### 10. Storage
Appends to [`all_leads_clean.csv`](file:///c:/xampp/htdocs/Yashvi-Practical/test-demo/all_leads_clean.csv).

### 11. Error Handling
Catches network or XML parsing errors per feed. Continues to subsequent feeds.

### 12. Dependencies
Pure Python standard library (`urllib.request`, `xml.etree.ElementTree`, `re`, `csv`, `os`).

---

## 5. [`instant_lead_generator.py`](file:///c:/xampp/htdocs/Yashvi-Practical/test-demo/instant_lead_generator.py) — Instant Reddit & Hacker News API Lead Generator

### 1. Starting Point
Triggered via CLI: `python instant_lead_generator.py` executing `main()`.

### 2. Source
1. Reddit JSON API: `https://www.reddit.com/r/{sub}/new.json?limit=30` (`forhire`, `freelance_forhire`).
2. Hacker News Algolia REST API: `https://hn.algolia.com/api/v1/search_by_date?query="looking for" OR "hiring"&tags=story`.

### 3. Input
Hardcoded subreddit list (`forhire`, `freelance_forhire`) and Algolia query filter.

### 4. Collection Logic
1. **Reddit Collector (`fetch_reddit_leads()`):**
   - Sends `requests.get` with browser User-Agent to Reddit's `/new.json`.
   - Iterates through `data['data']['children']`.
   - Inspects title for `[hiring]`, `hiring`, `looking for`.
   - Extracts author handle (`u/{author}`), title, permalink (`https://reddit.com{permalink}`), and runs regex contact extraction.
2. **Hacker News Collector (`fetch_hackernews_leads()`):**
   - Queries HN Algolia API for recent stories.
   - Takes top 15 hits.
   - Extracts author, title, item URL (`https://news.ycombinator.com/item?id={id}`).
3. **Consolidation & Merge:**
   - Merges lists into a Pandas DataFrame.
   - Reads existing [`instant_leads_master.csv`](file:///c:/xampp/htdocs/Yashvi-Practical/test-demo/instant_leads_master.csv) if present.
   - Merges and deduplicates via `drop_duplicates(subset=['Direct URL'])`.
   - Writes updated CSV.

### 5. Pagination
Limit of 30 on Reddit endpoint; top 15 results on Algolia API.

### 6. Extraction
`Platform`, `Date Found`, `Client Name / Handle`, `Job Title / Requirement`, `Direct URL`, `Contact Method`, `Status`.

### 7. Filtering
Reddit filtered on title containing `[hiring]`, `hiring`, or `looking for`. Algolia queries API for hiring phrases.

### 8. Deduplication
Handled in Pandas: `combined_df.drop_duplicates(subset=['Direct URL'], keep='first')`.

### 9. Validation
Contact extraction searches for standard email, Discord handles/invites, Telegram links/handles.

### 10. Storage
Saved to [`instant_leads_master.csv`](file:///c:/xampp/htdocs/Yashvi-Practical/test-demo/instant_leads_master.csv).

### 11. Error Handling
`try-except` blocks around each network request and file operation.

### 12. Dependencies
`requests`, `pandas`, `re`, `datetime`, `time`.

---

## 6. [`ddgs_bulk_scraper.py`](file:///c:/xampp/htdocs/Yashvi-Practical/test-demo/ddgs_bulk_scraper.py) — DuckDuckGo 20-Query Dork Bulk Scraper

### 1. Starting Point
Triggered via CLI: `python ddgs_bulk_scraper.py` executing `run_bulk_scraper()`.

### 2. Source
DuckDuckGo search engine via `duckduckgo_search` library.

### 3. Input
20 hardcoded targeted queries searching Reddit, Twitter, Upwork, Hacker News, Dev.to, GitHub (e.g. `site:reddit.com/r/forhire "hiring" "python"`, `site:twitter.com "hiring developer" "python"`).

### 4. Collection Logic
1. Opens `DDGS()` context manager.
2. Loops through all 20 queries sequentially.
3. Invokes `ddgs.text(query, max_results=5)`.
4. Collects title, href URL, body snippet.
5. Imposes `time.sleep(2.5)` between queries.
6. Writes collected rows to CSV.

### 5. Pagination
Max 5 results per query.

### 6. Extraction
`Search_Query`, `Title`, `Direct_URL`, `Snippet`. (Does NOT extract emails, phones, or contacts).

### 7. Filtering
Relies solely on DuckDuckGo search dorks. No post-search filtering.

### 8. Deduplication
In-memory `seen_urls` set.

### 9. Validation
None.

### 10. Storage
Writes to [`bulk_leads_output.csv`](file:///c:/xampp/htdocs/Yashvi-Practical/test-demo/bulk_leads_output.csv).

### 11. Error Handling
Catches query exceptions per iteration.

### 12. Dependencies & Failure Notes
- Dependencies: `duckduckgo_search`.
- **Current Failure:** When tested or executed, DuckDuckGo rapidly throttles automated Dork searches with empty results or rate limit exceptions. `bulk_leads_output.csv` currently contains 0 records (39 bytes header only).

---

## 7. [`b2b_portal_scraper.py`](file:///c:/xampp/htdocs/Yashvi-Practical/test-demo/b2b_portal_scraper.py) — B2B Directory Footprint Scraper

### 1. Starting Point
CLI entry: `python b2b_portal_scraper.py` calling `run_b2b_scraper()`.

### 2. Source
DuckDuckGo search targeting IndiaMART, TradeIndia, ExportersIndia, followed by direct HTTP requests to result URLs.

### 3. Input
`PORTAL_FOOTPRINTS` mapping portals to site search queries; generic fallback queries.

### 4. Collection Logic
1. Iterates through portal footprints.
2. Searches DDG via `search_ddg()`.
3. If no hits, runs generic fallback search: `GENERIC_FALLBACKS` + `site:{portal}.com`.
4. For every hit, visits URL via `requests.get()` (`extract_contacts_from_url`).
5. Extracts emails and phone numbers from the page HTML.
6. Saves records to CSV.

### 5. Pagination
Up to 20 results per query.

### 6. Extraction
`Portal_Source`, `Title_Requirement`, `Portal_URL`, `Extracted_Emails`, `Extracted_Phones`, `Snippet`.

### 7. Filtering & Severe Semantic Bug
When targeted queries fail, the fallback search string logic:
`res = search_ddg(f'{gq} site:{domain_keyword}.com')`
fails to match portal listings and returns random web pages like Wikipedia, Softonic, ComputerHope, and GeeksforGeeks.

### 8. Deduplication
In-memory `seen_urls` set.

### 9. Validation
Phone regex matches arbitrary number sequences (e.g. `1377063225` and `401190627519795` from Microsoft download links).

### 10. Storage
Writes to [`b2b_portals_leads.csv`](file:///c:/xampp/htdocs/Yashvi-Practical/test-demo/b2b_portals_leads.csv).

### 11. Error Handling
Suppresses request exceptions in `extract_contacts_from_url()`.

### 12. Dependencies & Failure Notes
- **Fatal Error:** Line 4 uses `from ddgs import DDGS`. The installed package in the virtual environment is `duckduckgo_search`. Running this file crashes immediately with `ModuleNotFoundError: No module named 'ddgs'`.

---

## 8. [`freelance_reddit_scraper.py`](file:///c:/xampp/htdocs/Yashvi-Practical/test-demo/freelance_reddit_scraper.py) — Multi-Platform Freelance Dork Scraper

### 1. Starting Point
CLI entry: `python freelance_reddit_scraper.py` calling `run_freelance_scraper()`.

### 2. Source
DuckDuckGo search querying Reddit, Freelancer.com, Upwork.com, and Twitter (X).

### 3. Input
`PLATFORM_QUERIES` dictionary with platform names and search dorks.

### 4. Collection Logic
1. Iterates over 5 platforms.
2. Runs DDG search queries for hiring posts.
3. Once hits are found for a platform, stops checking further queries for that platform.
4. Runs regex extraction on snippet text for email, Discord, and external URLs.
5. Saves leads to CSV.

### 5. Pagination
Max 20 results per query.

### 6. Extraction
`Platform`, `Title`, `Post_URL`, `Extracted_Email_Contact`, `Extracted_Discord_Contact`, `Extracted_External_URL`, `Description_Snippet`.

### 7. Filtering
Stops after first query returning hits per platform.

### 8. Deduplication
In-memory `seen` URL set.

### 9. Validation
Regex for email, Discord, and URL.

### 10. Storage
Writes to [`freelance_reddit_leads_v2.csv`](file:///c:/xampp/htdocs/Yashvi-Practical/test-demo/freelance_reddit_leads_v2.csv).

### 11. Error Handling
Catches search exceptions per query.

### 12. Dependencies & Failure Notes
- **Fatal Error:** Line 4 uses `from ddgs import DDGS`. Crashes immediately on execution with `ModuleNotFoundError: No module named 'ddgs'`.

---

## 9. [`linkedin_scraper.py`](file:///c:/xampp/htdocs/Yashvi-Practical/test-demo/linkedin_scraper.py) — LinkedIn B2B Company & Profile Scraper

### 1. Starting Point
CLI entry: `python linkedin_scraper.py` calling `scrape_linkedin_leads()`.

### 2. Source
DuckDuckGo search querying `site:linkedin.com/company` and `site:linkedin.com/in`, then direct HTTP requests to LinkedIn URLs and linked external websites.

### 3. Input
`SEARCH_QUERIES`: `"site:linkedin.com/company IT software company"`, `"site:linkedin.com/in freelance software developer"`. `MAX_RESULTS_PER_QUERY = 5`.

### 4. Collection Logic
1. Queries DuckDuckGo for LinkedIn profile and company URLs.
2. For each URL, performs a direct `requests.get()` to the LinkedIn page.
3. Parses HTML using BeautifulSoup.
4. Searches for company title, emails, phone numbers, and external website links (e.g. "visit website").
5. If contacts are missing on LinkedIn and an external website is discovered, makes an HTTP GET to the external website to find emails and phones.
6. Saves collected data to CSV via Pandas.

### 5. Pagination
Max 5 results per query.

### 6. Extraction
`Title`, `LinkedIn_URL`, `External_Website`, `Emails`, `Phones`.

### 7. Filtering
Filters URLs to ensure `linkedin.com` is present.

### 8. Deduplication
None (relies on DDG search return order).

### 9. Validation
Validates email extensions; checks phone digit length (8 to 15 digits).

### 10. Storage
Exports via Pandas to [`linkedin_leads.csv`](file:///c:/xampp/htdocs/Yashvi-Practical/test-demo/linkedin_leads.csv).

### 11. Error Handling
Catches request errors and status code non-200 responses.

### 12. Dependencies & Failure Notes
- **Fatal Error 1:** Line 8 uses `from ddgs import DDGS`. Fails on import with `ModuleNotFoundError: No module named 'ddgs'`.
- **Fatal Error 2:** LinkedIn Anti-Bot: LinkedIn immediately blocks unauthenticated `requests.get()` calls with HTTP 999 or redirect walls, making direct HTML scraping non-viable.

---

## 10. [`reddit_rss_scraper.py`](file:///c:/xampp/htdocs/Yashvi-Practical/test-demo/reddit_rss_scraper.py) — Reddit Multi-Subreddit RSS Harvester

### 1. Starting Point
CLI entry: `python reddit_rss_scraper.py` calling `run_reddit_rss_scraper()`.

### 2. Source
Reddit RSS feeds across 3 subreddits: `r/forhire`, `r/freelance_forhire`, `r/jobbit`.

### 3. Input
Hardcoded subreddit list: `["forhire", "freelance_forhire", "jobbit"]`.

### 4. Collection Logic
1. Iterates through subreddits.
2. Uses `feedparser.parse()` to read `https://www.reddit.com/r/{sub}/new/.rss`.
3. Cleans HTML tags from summary via regex and `html.unescape`.
4. Checks text for keywords: `["hiring", "looking for", "need", "developer", "freelance"]`.
5. Extracts contacts (Email, Discord, Telegram). If none found, defaults to `"Reddit PM / DM Only"`.
6. Appends to leads list and exports to CSV.

### 5. Pagination
Latest entries in RSS feed (typically 25).

### 6. Extraction
`Subreddit`, `Title`, `Post_URL`, `Contact_Details`, `Snippet`.

### 7. Filtering & Severe Flaw
Line 75 checks if `any(kw in text_to_check for kw in ["hiring", "looking for", "need", "developer", "freelance"])`. Because `"developer"` and `"freelance"` are keywords, all `[FOR HIRE]` posts by job seekers are falsely categorized as hiring leads.

### 8. Deduplication
In-memory `seen_urls` set.

### 9. Validation
Regex for email, Discord, Telegram.

### 10. Storage
Writes to [`reddit_rss_leads.csv`](file:///c:/xampp/htdocs/Yashvi-Practical/test-demo/reddit_rss_leads.csv).

### 11. Error Handling
Catches feed fetching exceptions.

### 12. Dependencies & Failure Notes
- **Fatal Error:** Line 2 has `import feedparser`. Package `feedparser` is not in `requirements.txt` and not installed in the virtual environment. Crashes immediately with `ModuleNotFoundError: No module named 'feedparser'`.

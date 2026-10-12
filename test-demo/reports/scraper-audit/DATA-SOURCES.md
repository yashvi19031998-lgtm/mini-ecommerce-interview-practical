# Data Sources & External Provider Audit

**Project:** `test-demo`  
**Location:** `c:\xampp\htdocs\Yashvi-Practical\test-demo`  
**Audit Date:** October 12, 2026  

---

## 1. Overview of Identified Data Sources

Across the 10 scrapers, the system interacts with **7 distinct data providers/sources**:

1. **Google Search (Web Search Results)**
2. **Yahoo & Bing Public Search Engines**
3. **Reddit Public Feeds (RSS/Atom & JSON REST API)**
4. **WeWorkRemotely & Remotive (Remote Job RSS Feeds)**
5. **Hacker News (Algolia Search API)**
6. **Justdial Ahmedabad (Local Business Directory)**
7. **DuckDuckGo Search Engine (Dork Scraping)**

> [!NOTE]
> **Google Maps, Google Business Profile API, and OpenStreetMap / Overpass API** are **NOT implemented anywhere in the current codebase**. The project relies exclusively on public web search engines, direct RSS feeds, public REST endpoints, and HTML directory scraping.

---

## 2. Source-by-Source Deep Technical Breakdown

### Source 1: Google Search (Web Results)
- **Used by:** [`scraper.py`](file:///c:/xampp/htdocs/Yashvi-Practical/test-demo/scraper.py)
- **Domain / Endpoint:** `https://www.google.com/search` (via `googlesearch-python` client library)
- **Mechanism:** Search-based HTML collector / automated query wrapper.
- **Authentication:** None (No API key; uses automated web requests).
- **Data Fields Returned:** URL, Title, Snippet (text description).
- **Contact Details Provided:** Does **not** provide direct email or phone numbers; provides URLs of candidate businesses which must then be crawled.
- **Verification Level:** Publicly listed web search indexing only.
- **Rate Limits & Anti-Bot:** Aggressive anti-bot detection. Google presents automated reCAPTCHA challenges after 10–25 programmatic queries, triggering an exception.
- **Current Status & Known Errors:** Handled gracefully in `scraper.py` via fallback mechanism to Yahoo/Bing.

---

### Source 2: Yahoo Search & Bing Search
- **Used by:** [`scraper.py`](file:///c:/xampp/htdocs/Yashvi-Practical/test-demo/scraper.py)
- **Domain / Endpoints:**
  - Yahoo: `https://search.yahoo.com/search?p={query}`
  - Bing: `https://www.bing.com/search?q={query}`
- **Mechanism:** Direct HTTP GET request parsing HTML (`BeautifulSoup`).
- **Authentication:** None required.
- **Data Fields Returned:** URL (decoded from redirect parameters `/RU=` and `&u=a1<base64>`), Page Title, Snippet.
- **Contact Details Provided:** None directly; used as URL discovery engines.
- **Rate Limits & Restrictions:** More tolerant than Google for modest request volumes with 1.5s delay; no CAPTCHA triggered during standard runs.
- **Current Status & Known Errors:** Verified working as the primary fallback in `scraper.py`.

---

### Source 3: Reddit (Public Atom RSS & Public JSON API)
- **Used by:** [`lead_generation_master.py`](file:///c:/xampp/htdocs/Yashvi-Practical/test-demo/lead_generation_master.py), [`direct_feed_csv.py`](file:///c:/xampp/htdocs/Yashvi-Practical/test-demo/direct_feed_csv.py), [`direct_feed_testing_2.py`](file:///c:/xampp/htdocs/Yashvi-Practical/test-demo/direct_feed_testing_2.py), [`instant_lead_generator.py`](file:///c:/xampp/htdocs/Yashvi-Practical/test-demo/instant_lead_generator.py), [`reddit_rss_scraper.py`](file:///c:/xampp/htdocs/Yashvi-Practical/test-demo/reddit_rss_scraper.py)
- **Endpoints:**
  - RSS/Atom: `https://www.reddit.com/r/{subreddit}/new/.rss`
  - JSON REST: `https://www.reddit.com/r/{subreddit}/new.json?limit=30`
  - Target Subreddits: `r/forhire`, `r/freelance_forhire`, `r/jobbit`
- **Mechanism:** Direct XML Atom feed & unauthenticated REST JSON endpoint.
- **Authentication:** None required (public endpoints; requires descriptive `User-Agent` header to prevent HTTP 429).
- **Data Fields Returned:** Post Title, Author Handle, Permanent Post URL, Publication Timestamp, Post Body Content (`selftext`).
- **Contact Details Provided:** Client emails, Discord tags, and Telegram handles are extracted **only when explicitly typed into the post body by the poster**. No private or platform-verified emails are available.
- **Rate Limits & Restrictions:** Reddit rate limits unauthenticated requests to ~30-60 requests per minute.
- **Current Status & Known Errors:**
  - RSS parsing in `lead_generation_master.py`, `direct_feed_csv.py`, and `direct_feed_testing_2.py` is verified working.
  - In `reddit_rss_scraper.py`, broken due to missing `feedparser` library and flawed filter matching job seekers.

---

### Source 4: WeWorkRemotely & Remotive (Job Board RSS Feeds)
- **Used by:** [`lead_generation_master.py`](file:///c:/xampp/htdocs/Yashvi-Practical/test-demo/lead_generation_master.py), [`direct_feed_testing_2.py`](file:///c:/xampp/htdocs/Yashvi-Practical/test-demo/direct_feed_testing_2.py)
- **Endpoints:**
  - `https://weworkremotely.com/categories/remote-programming-jobs.rss`
  - `https://weworkremotely.com/categories/remote-back-end-programming-jobs.rss`
  - `https://remotive.com/remote-jobs/feed`
- **Mechanism:** Public XML RSS 2.0 Feeds (`<item>` tags).
- **Authentication:** None.
- **Data Fields Returned:** Job Title, Company Name (often embedded in title e.g. "Company: Role"), Job URL, Description HTML, Publication Date.
- **Contact Details Provided:** Descriptions rarely include raw email/phone. Contact info is obtained when `lead_generation_master.py` extracts the hiring company's website link and crawls its `/contact` page.
- **Rate Limits & Restrictions:** Highly permissive public feeds intended for RSS aggregators.
- **Current Status & Known Errors:** Verified working.

---

### Source 5: Hacker News (Algolia Search API)
- **Used by:** [`instant_lead_generator.py`](file:///c:/xampp/htdocs/Yashvi-Practical/test-demo/instant_lead_generator.py)
- **Endpoint:** `https://hn.algolia.com/api/v1/search_by_date?query="looking for" OR "hiring"&tags=story`
- **Mechanism:** Direct REST API returning structured JSON.
- **Authentication:** None required (free public API provided by Algolia).
- **Data Fields Returned:** Story Title, Author Handle, Object ID, Creation Timestamp, Points, Comments Count.
- **Contact Details Provided:** Does not provide direct email or phone. Returns discussion thread URLs where users occasionally post hiring needs.
- **Rate Limits & Restrictions:** 10,000 requests per hour.
- **Current Status & Known Errors:** Verified working.

---

### Source 6: Justdial (Local Business Directory)
- **Used by:** [`lead_generation_master.py`](file:///c:/xampp/htdocs/Yashvi-Practical/test-demo/lead_generation_master.py)
- **Endpoint / Domain:** `https://www.justdial.com/Ahmedabad/Software-Developers`
- **Mechanism:** Headless Chromium Browser Automation (`playwright.sync_api`).
- **Authentication:** None.
- **Data Fields Returned:** Business Name, Detail Page URL, Physical Address / Locality, Phone Number (extracted from `a[href^="tel:"]`, call button attributes, or `.callcontent`), External Website Link.
- **Contact Details Provided:** Public business telephone/mobile numbers and official company websites. Emails are obtained by crawling the business's external website.
- **Rate Limits & Restrictions:** Justdial uses client-side bot detection and login prompt modals. Handled via automated popup dismissal and anti-detection arguments in Playwright (`--disable-blink-features=AutomationControlled`).
- **Current Status & Known Errors:** Browser automation engine is verified working in the environment.

---

### Source 7: DuckDuckGo Search Engine
- **Used by:** [`ddgs_bulk_scraper.py`](file:///c:/xampp/htdocs/Yashvi-Practical/test-demo/ddgs_bulk_scraper.py), [`b2b_portal_scraper.py`](file:///c:/xampp/htdocs/Yashvi-Practical/test-demo/b2b_portal_scraper.py), [`freelance_reddit_scraper.py`](file:///c:/xampp/htdocs/Yashvi-Practical/test-demo/freelance_reddit_scraper.py), [`linkedin_scraper.py`](file:///c:/xampp/htdocs/Yashvi-Practical/test-demo/linkedin_scraper.py)
- **Library / Endpoint:** DuckDuckGo HTML/API via `duckduckgo_search` (`DDGS.text()`)
- **Mechanism:** Automated search queries.
- **Authentication:** None.
- **Data Fields Returned:** URL (`href`), Title, Snippet (`body`).
- **Contact Details Provided:** Search snippets only.
- **Rate Limits & Restrictions:** Very strict anti-scraping and rate limits on complex queries or Dorks.
- **Current Status & Known Errors:**
  - In `ddgs_bulk_scraper.py`: Queries return 0 results or get throttled (`bulk_leads_output.csv` is empty).
  - In `b2b_portal_scraper.py`, `freelance_reddit_scraper.py`, `linkedin_scraper.py`: Fatal import error `from ddgs import DDGS` because the library is installed as `duckduckgo_search`.

---

## 3. Data Source Capability Matrix

| Source Provider | Direct API or Scraper | Company / Client Name | Direct Email Available | Direct Phone Available | Website URL | Intent / Description | Current Reliability |
|---|---|---|---|---|---|---|---|
| **Google Search** | Scraper Wrapper | No (Extracted via crawl) | No (Crawl required) | No (Crawl required) | Yes | Search Snippet | Low (Rate-limits quickly) |
| **Yahoo & Bing** | Direct HTML Scraper | No (Extracted via crawl) | No (Crawl required) | No (Crawl required) | Yes | Search Snippet | High (Reliable fallback) |
| **Reddit RSS & JSON** | Direct XML / REST API | Author Handle (`u/...`) | Only if in post text | Only if in post text | Thread Permalink | Full Post Body | High (Very stable) |
| **WeWorkRemotely RSS** | Direct XML RSS | Yes (in Job Title) | Via website deep crawl | Via website deep crawl | Company Job Link | Full Job Description | High (Very stable) |
| **Hacker News Algolia**| Direct REST API | HN Username | Rare (Discussion thread)| No | Discussion Link | Story Title / Question| High (Very stable) |
| **Justdial Ahmedabad** | Playwright Browser | Yes (Store / Org Name) | Via website deep crawl | Yes (`tel:` / button)| Yes (External site) | Address & Category | High (Working with Playwright) |
| **DuckDuckGo Search** | Search Wrapper | In search snippet | In search snippet | Rare in snippet | Search Result URL | Search Snippet | Low (Throttles / blocks dorks) |

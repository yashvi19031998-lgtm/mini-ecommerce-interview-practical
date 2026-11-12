# Web Crawler — Module Guide

**Status:**
- **QA passed:** live (2026-11-12).
- QA report: `reports/qa/2026-11-12-web-crawler.md`. **Updated:** 2026-11-12.

---

## English

### Purpose
Four tools that read **websites you name**: collect contacts, find company websites on list pages, find pages about a topic, and list everything a site publishes.

### Menus
| Menu | Input | Output |
|---|---|---|
| **Site Crawler** | Up to 5 websites; pages to read (10 / 25 / 50, all sites together); depth (1–3 clicks from the start page) | Per page: title, e-mails, phones, social links. Per site: everything combined. Save sites as leads (`Web Crawler (Site Crawler)`). |
| **Link Harvester** | Up to 5 list pages (association members, expo exhibitors, "top companies" articles); optionally follow "Next" pages (up to 5) | The **outside company websites** they link to, with the link text as the company name. **Get contacts** then reads each website (10 per request). Save as leads (`Web Crawler (Link Harvester)`). |
| **Keyword Page Finder** | Up to 3 websites, up to 10 keywords, pages and depth | Pages that mention each keyword, with the number of mentions, whether the word is in the URL, and two text snippets. Links whose URL or text contains a keyword are read first. |
| **Sitemap Explorer** | One website | Every page in its sitemap(s) (robots.txt `Sitemap:` lines, `/sitemap.xml`, `/sitemap_index.xml`, `/wp-sitemap.xml`; up to 10 child sitemaps and 5,000 pages), with last-updated date and priority. Pages per section; the newest and oldest update. |

### Rules every request follows
- **robots.txt is obeyed.**
  - Disallowed pages are skipped and counted.
  - A missing robots.txt (404) means no rules.
  - If robots.txt cannot be read (server error / network), the site is **not** crawled.
- **Crawl-delay is honoured**: at least 1 s between pages of the same site, at most 10 s.
- **Public addresses only.** The URL guard blocks localhost and private networks, on every redirect hop and for robots.txt too.
- **HTML cache and honest User-Agent** (`LeadsGenAI-DeepSearch/1.0`).
- **Limits:**
  - Each request stops after **90 s** and says so; run it again to continue (pages already read come from the cache).
  - Files (PDF, images, ZIP…), `mailto:` and `javascript:` links are never fetched.
  - `www.` / no `www.`, `http` / `https` and a trailing `/` count as the same page.
- **Sitemaps** are read with a pattern match, not an XML parser, so entity tricks in a hostile file cannot expand. Compressed (`.gz`) sitemaps are skipped with a note. Sitemaps of other sites listed in an index are ignored.
- **Link Harvester** ignores social sites, directory portals, CDNs and fonts, link shorteners and app stores. Government sites are kept but flagged.

### Technical
| Item | Value |
|---|---|
| Backend | `web_crawler.py`, plus the shared `robots_policy.py` (also used by the GST No Scraper) |
| API (login required) | `GET /api/web-crawler`, `POST /api/web-crawler/{site,links,keywords,sitemap}`. Contacts and save use `/api/bulk-contacts/websites` and `/api/bulk-contacts/save`. |
| Frontend | `WebCrawler.js` (prop `tool`), sidebar group **Web Crawler** (`CRAWLER_ITEMS`) |
| Tests | `test_web_crawler.py` (12 tests, in hourly CI) |

---

## ગુજરાતી

### હેતુ
તમે આપેલી **websites** વાંચવા માટે 4 tools:
- contacts ભેગા કરવા
- યાદીવાળા pages પરથી company websites શોધવી
- કોઈ શબ્દ કયા pages પર છે એ શોધવું
- site નાં બધાં pages ની યાદી કાઢવી

### Menus
- **Site Crawler:** website ના અંદરનાં pages વાંચીને email, phone અને social links ભેગા કરે છે.
- **Link Harvester:** members કે exhibitors ની યાદીવાળા page પરથી બહારની company websites કાઢે છે. પછી "Get contacts" થી દરેકના contacts મળે છે.
- **Keyword Page Finder:** "careers", "tender", "franchise" જેવા શબ્દો કયા pages પર છે એ શોધે છે, આસપાસના લખાણ સાથે.
- **Sitemap Explorer:** website ના sitemap માંથી બધાં pages, sections અને છેલ્લી update ની તારીખ બતાવે છે.

### નિયમો
- દરેક site નો robots.txt માનવામાં આવે છે.
- એક જ site નાં pages વચ્ચે ઓછામાં ઓછી 1 સેકન્ડ રાહ જોવાય છે.
- ફક્ત public addresses ખૂલે છે.
- દરેક run 90 સેકન્ડમાં અટકે છે. વધુ pages માટે ફરી ચલાવો; જૂનાં pages cache માંથી આવશે.

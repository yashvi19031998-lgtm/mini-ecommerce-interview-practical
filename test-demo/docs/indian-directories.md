# Data Extraction → Indian Directories — Module Guide

**Status:**
- **QA passed:** live on all 5 working portals (2026-11-12).
- **Justdial:** not available (see below).
- QA report: `reports/qa/2026-11-12-indian-directories.md`. **Updated:** 2026-11-12.

---

## English

### Purpose
Collect supplier and business listings from Indian directory portals. Each portal has its own menu item under **Data Extraction → Indian Directories**.

### Portals
| Menu | What is read | Data you get | Phone |
|---|---|---|---|
| **MLMDiary Scraper** | MLMDiary directory listing (by state / city) | MLM **companies**, number of members listed, cities, plans | — (member numbers are personal data and are never collected) |
| **IndiaMART Scraper** | Category page, city-wise (`dir.indiamart.com/<city>/<category>.html`) or all India | company, product, city / area, rating, GST verified, years on IndiaMART | IndiaMART call-forwarding number, with extension (e.g. `08047625603 ext 5093`) |
| **Justdial Scraper** | — | **Not available** | — |
| **Sulekha Scraper** | Category page per city (`sulekha.com/<category>/<city>`, 2 pages) | business name, area, pincode, description | Yes, when Sulekha shows it |
| **TradeIndia Scraper** | Manufacturer category page, plus the city page when TradeIndia has one | company, city, state, business type, established year, certificates, product, price | Hidden by TradeIndia |
| **ExportersIndia Scraper** | Category page, city-wise or all India | company, profile, area, years on the site, product, price | Behind a "View Mobile" click, so not collected |

**Why Justdial is not available:** Justdial returns an empty page to automated requests (bot protection). Getting the data would mean bypassing that protection, and this app does not do that. The Justdial page links to Sulekha and IndiaMART instead.

### Rules the scraper follows
- **Allowed pages only.** It reads only public listing pages that the site's `robots.txt` allows. Search pages that robots.txt blocks (IndiaMART `search.mp`, TradeIndia / ExportersIndia search, the MLMDiary `?keyword=` search) are never used.
- **Polite requests:**
  - an honest User-Agent (`LeadsGenAI-DeepSearch/1.0`) and the URL guard (public addresses only)
  - a pause between requests: 2 s, or 5 s for MLMDiary, which asks for it
- **Cache:**
  - The same page within the HTML cache age is not downloaded again.
  - The same search within 72 hours returns the saved result (`INDIAN_DIRECTORIES_CACHE_HOURS`).
- **Hidden data stays hidden.** Numbers the site hides behind a click or a login are not collected.
- **Privacy (DPDP Act 2023):** MLMDiary lists individual people. Only the company each person names is kept; person names, photos and numbers are dropped while the page is read.

### Category names
Each portal names its categories in its own way. The app tries the name you type, then its singular / plural form, then `<name> services`. That is at most 3 pages per keyword.

If nothing matches, the page says so and, when the site gives them, shows related categories. Names that work today include:
- **IndiaMART:** `bakery products`
- **Sulekha:** `interior designers decorators`, `packers and movers`
- **TradeIndia / ExportersIndia:** `bakery products`

### How to use
1. Open **Data Extraction → Indian Directories → <portal>**.
2. Fill in:
   - **Product / category**, up to 5. For MLMDiary this is optional and filters by company name.
   - **Target audience** (optional).
   - **State**.
   - **City**: required for Sulekha; for IndiaMART / ExportersIndia it gives city pages.
3. Click **Search**. Use **Filter results** to narrow the list.
4. **Deep Search** looks for each company's own website by name, using the search engine (a directory page is never treated as the website), then reads it for email / phone.
5. **Export CSV** or **Save to Leads**.
   - Saved leads get the source `Indian Directories (<portal>)`.
   - The listing link is kept as the source link.
   - The lead type is `Directory Listing (B2B / services)` or `MLM Company`.

### Technical
| Item | Value |
|---|---|
| Backend | `indian_directories.py` (parsers are pure functions; fetches go through `html_cache_manager.fetch_page`) |
| API (login required) | `GET /api/indian-directories`, `POST /api/indian-directories/search`, `POST /api/indian-directories/save` |
| Frontend | `IndianDirectory.js` (one component; the menu passes the portal), shared `MiningForm` |
| Sidebar | `EXTRACTION_ITEMS` in `Sidebar.js`. Groups now open / close independently, and items can carry a `section` heading. |
| Tests | `test_indian_directories.py` (23 tests, in hourly CI) |

### Fixes made while building this
- **`fetch_page`** (new in `html_cache_manager.py`) reports the HTTP status and the final URL, and does not cache a page that was redirected elsewhere. TradeIndia redirects an unknown category to a generic page instead of returning 404.
- **`lead_normalizer.normalize_phone`** dropped Indian numbers written with the trunk 0 (`09533376923`, `08047763186`, `022…`). They are now kept as `+91 …`. This affects every source that gives such numbers.

---

## ગુજરાતી

### હેતુ
Indian directory sites પરથી suppliers અને businesses ની યાદી મેળવવી. **Data Extraction → Indian Directories** માં દરેક site નું અલગ menu છે.

### કઈ site માંથી શું મળે છે
- **MLMDiary:** ફક્ત MLM **companies**, કેટલા members છે અને કયાં શહેરોમાં છે. વ્યક્તિઓનાં નામ કે નંબર ક્યારેય save નથી થતાં (DPDP Act).
- **IndiaMART:** company, product, શહેર, rating, GST verified અને phone. Phone IndiaMART નો call-forwarding number હોય છે, extension સાથે.
- **Justdial:** **ઉપલબ્ધ નથી.** Justdial apps ને ખાલી page આપે છે, અને bot-protection તોડવું અમે નથી કરતા.
- **Sulekha:** business નું નામ, વિસ્તાર અને phone. City ફરજિયાત છે.
- **TradeIndia:** company, શહેર, state, business type અને product. Phone TradeIndia છુપાવે છે.
- **ExportersIndia:** company, વિસ્તાર, product અને price. Phone "View Mobile" click પાછળ છે, એટલે લેવાતો નથી.

### નિયમો
- ફક્ત એ જ pages વંચાય છે જે site નું robots.txt મંજૂર કરે છે.
- Requests ધીમે ધીમે થાય છે: 2 સેકન્ડ, અને MLMDiary માટે 5 સેકન્ડ. Cache વપરાય છે.
- Site જે માહિતી છુપાવે છે એ લેવામાં નથી આવતી.

### Category નું નામ
દરેક site પોતાનું નામ વાપરે છે, જેમ કે Sulekha માં "interior designers decorators". નામ ન મળે તો page પર સાફ message આવે છે અને સંબંધિત categories ના નામ સૂચવાય છે.

### વાપરવાની રીત
1. Menu ખોલો અને product / category, state અને city લખો.
2. **Search** દબાવો. પછી **Deep Search** (website, email) ચલાવો, **Export CSV** કરો અથવા **Save to Leads** કરો.

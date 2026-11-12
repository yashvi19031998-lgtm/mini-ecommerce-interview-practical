# Scraping / Mining → Search Engines + Deep Search — Module Guide

**Status:**
- **QA passed:** UI flow, Deep Search, Save, the Import merge, and unit tests.
- **UNVERIFIED:** Brave and Serper live results (no keys yet), and live DuckDuckGo result quality (DuckDuckGo throttled the test IP).
- QA report: `reports/qa/2026-11-12-search-engines.md`. **Updated:** 2026-11-12.

---

## English

### Menu
Sidebar → **Scraping / Mining** has 9 submenus:
1. Search Engines
2. Google Maps
3. Social Media
4. Ad Library
5. Ecommerce Platforms
6. Job Portals
7. Global Directories
8. WhatsApp Groups
9. Real Estate

- **Search Engines** is new.
- **Job Portals** is the existing Job Portal Scraper, moved here from the main menu.
- The other 7 are marked **Soon**. Each opens a page that says what the module will do, which free or official method it will use, and what it will not do.

### How to use Search Engines
1. **Keywords:** up to 5 (Enter or comma).
2. **Search type:**

| Type | Queries it runs (per keyword) |
|---|---|
| Companies & websites | `"kw" company <place>`, `kw services <place> "contact us"` |
| Contact pages | `"kw" <place> "contact us" email`, `"kw" <place> "@gmail.com" OR "+91"` |
| B2B portals | `site:indiamart.com` / `site:tradeindia.com` / `site:exportersindia.com "kw" <place>` |
| LinkedIn company pages | `site:linkedin.com/company "kw" <place>` |
| Buyer intent | `"looking for" "kw"`, `"need a" "kw"`, Reddit r/forhire, Upwork |
| Tenders & RFPs | `"kw" tender <place> site:gov.in`, `"request for proposal" "kw"` |
| Custom query | Your own query; `{keyword}` and `{city}` are replaced |

3. **Search engine:**
   - **Auto** uses Brave if its key is set, then Serper, otherwise DuckDuckGo.
   - An engine without a key is greyed out. Add the key in Settings → API Keys.
4. **State / City:** the place used in the queries (city, else state, else "India").
5. **Published:** any time, past day, week, month or year.
6. **Max results:** 10, 25, 50 or 100.
7. **Exclude sites:** up to 10 sites to leave out (e.g. justdial.com).
8. **Search.** The page shows the engine's result count and every query that was run (**Queries used**).

### Results
- **Duplicates:** one row per company website. A result whose domain is already in the list is dropped.
- **Kind of result:**
  - A result on a platform (LinkedIn, IndiaMART…) is a **listing**; Deep Search finds the company's own website.
  - Pages like "Top 10 IT companies in Ahmedabad" are marked **list article**. They are not one company, so Deep Search skips them.
- **Junk removed:** Wikipedia, dictionaries, Microsoft, download sites and similar.
- **site: queries:** results from other sites are hidden, because some engines ignore `site:`. The page shows how many were hidden.
- **Already saved:** results already in the leads database show **In leads**. This is checked again on every search, saved results included.
- **Contacts in the snippet:** emails and Indian phone numbers found in the result text are shown straight away.

### Deep Search
- **What it runs on:** select rows and click **Deep Search selected**. With nothing selected, it runs on every row without an email (list articles excluded).
- **Speed:** it works through 10 rows at a time, and the button shows its progress.
- **Steps, in order:**
  1. **Website:** the result's own site. For a listing, the engine searches for the company and takes the result whose domain matches the company name.
  2. **Crawl:** the homepage plus up to 3 Contact / About pages (emails, Indian phones, address, social links). Pages come from the HTML cache when fresh.
  3. **JSON-LD:** schema.org company data (email, phone, address, sameAs links, name).
  4. **Zaubacorp:** only for Pvt Ltd, Limited or LLP companies; adds the MCA email and CIN.
  5. **Hunter:** only when **Use Hunter credits** is ticked (needs `HUNTER_API_KEY`).
  6. **Guess:** `info@domain` if the domain accepts mail. It is shown as "(guess)" and **never saved as the email**.
- **Status badge:** Found / Website only / Nothing found / Failed. Hover over it to see each step's result.
- **Safety:** only public `http(s)` websites on ports 80 and 443 are opened. Every redirect is checked again, so localhost and private networks are refused. Pages are capped at 3 MB.

### Save / Export
- **Save to Leads:**
  - Saved leads get the source `Search Engine (<engine>)` and the lead type `Search Engine - <search type>`.
  - Saving the same result again creates no duplicate.
  - The save also syncs to Supabase, the same way the old Import did.
- **Send intro email on save:** off by default, and it asks for confirmation before sending. It uses your SMTP settings and the default template. This was carried over from the old Import "Dispatch Instant Cold Email".
- **Export CSV:** downloads the visible rows. Spreadsheet formulas are neutralised.

### Merged from Import & Parse
- The old **Live Query Search** tab is removed. Its button now opens Search Engines.
- All its features are here:
  - **Modes:** its "all / clients / b2b / linkedin" modes are now the search types.
  - **Duplicate check:** now the **In leads** badge.
  - **Commit + optional instant email + Supabase sync:** now Save to Leads.
- The API `/api/import/search` is removed. WhatsApp chat and Raw text imports are unchanged.
- **Fix found on the way:** Import & Parse did not refresh the leads list after a commit (wrong prop name). This is fixed.

### Rate limits and caching
- **Rate limits:** queries run one at a time, with a gap per engine (Brave 1.1 s, DuckDuckGo 2 s). On a rate limit the search stops, keeps what it found and shows a warning. We never rotate IPs or bypass bot checks.
- **Caching:** the same search is answered from saved results for `SEARCH_ENGINE_CACHE_HOURS` (default 24 h). **Search live again** always goes live. A search with a failed engine is not saved.

### Known limits
- **DuckDuckGo (no key) is best effort.**
  - It often returns nothing for `site:` or quoted queries from apps.
  - After a few searches it may return empty results for a while.
  - The page then shows a hint to add a free **Brave** or **Serper** key.
- **Brave and Serper are UNVERIFIED:** they are covered by unit tests with mocked answers only, until keys are added.

### Settings / keys
- **Search engine keys:** `BRAVE_SEARCH_API_KEY` (free plan) and `SERPER_API_KEY` (free starter credits). Both are listed in Settings → API Keys.
- **Optional:** `HUNTER_API_KEY` (Deep Search step 5) and `SEARCH_ENGINE_CACHE_HOURS`.

### Technical
| Item | Value |
|---|---|
| Backend | `search_engine.py` (queries, engines, validation), `deep_search.py` (waterfall), uses `scraper.py` extractors and `html_cache_manager.py` |
| API (login required) | `GET /api/search-engine`, `POST /api/search-engine/search`, `POST /api/search-engine/deep`, `POST /api/search-engine/save` |
| Frontend | `SearchEngine.js`, `MiningComingSoon.js`, `ChipInput.js` (shared with CRM Sources), `Sidebar.js` group |
| Tests | `test_search_engine.py` (37 tests, in hourly CI) |

---

## ગુજરાતી

### Menu
- Sidebar માં **Scraping / Mining** ની નીચે 9 submenus છે.
- **Search Engines** નવું છે.
- **Job Portals** એ જૂનું Job Portal Scraper છે, હવે અહીં.
- બાકીના 7 **Soon** છે. દરેકના page પર લખ્યું છે કે એ module શું કરશે અને કઈ રીતે કરશે.

### Search Engines કેવી રીતે વાપરવું
1. **Keywords:** 5 સુધી.
2. **Search type** પસંદ કરો: Companies, Contact pages, B2B portals, LinkedIn, Buyer intent, Tenders અથવા Custom.
3. **Search engine:**
   - **Auto** પહેલાં Brave, પછી Serper, અને key ન હોય તો DuckDuckGo વાપરે છે.
   - Key વગરનું engine grey દેખાય છે.
4. **State / City**, **Published** (સમય), **Max results** અને **Exclude sites** ભરો.
5. **Search** દબાવો. કઈ queries ચાલી એ **Queries used** માં દેખાય છે.

### Results
- એક company ની website એક જ વાર દેખાય છે.
- **Listing:** LinkedIn, IndiaMART જેવા platform પરનું page.
- **List article:** "Top 10 companies" જેવા page. એ એક company નથી, એટલે Deep Search એને છોડી દે છે.
- **Junk:** Wikipedia, dictionary, Microsoft જેવા results આપોઆપ નીકળી જાય છે.
- **In leads:** જે company પહેલેથી leads માં છે તેના પર આ badge દેખાય છે.

### Deep Search
Rows પસંદ કરો અને **Deep Search** દબાવો. આ ક્રમમાં તપાસ થાય છે:
1. Company ની website શોધે છે.
2. Home, Contact અને About pages વાંચીને email, phone, address અને social links કાઢે છે.
3. JSON-LD (schema.org) data વાંચે છે.
4. Pvt Ltd / LLP હોય તો Zaubacorp પરથી MCA email અને CIN લે છે.
5. Hunter (credits વપરાય, tick કરો તો જ).
6. `info@` નો અંદાજ: "(guess)" તરીકે દેખાય છે, **email તરીકે save થતો નથી**.

**સુરક્ષા:** ફક્ત public websites જ ખોલાય છે. localhost કે private network ક્યારેય નહીં.

### Save
- **Save to Leads** થી lead save થાય છે. ફરી save કરો તો duplicate નથી બનતો.
- **Send intro email on save** default માં બંધ છે, અને email મોકલતાં પહેલાં પૂછે છે.

### Import & Parse માંથી merge
- જૂનું **Live Query Search** અહીં આવી ગયું છે, અને તેના બધા features અહીં છે.
- WhatsApp chat અને Raw text import પહેલાં જેવાં જ છે.

### મર્યાદા
- **DuckDuckGo (key વગર):** ભરોસાપાત્ર નથી. ઘણી વાર 0 results આપે છે, ખાસ કરીને `site:` વાળી queries માટે.
- **સારા results માટે:** free **Brave** કે **Serper** key, Settings → API Keys માં ઉમેરો.

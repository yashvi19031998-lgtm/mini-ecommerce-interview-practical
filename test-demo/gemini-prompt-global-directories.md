# Task: build the "Global Directories" module (Scraping / Mining → Global Directories)

You are working in an existing lead-generation app. Another engineer owns the rest of the code and is working in parallel, so **stay strictly inside the files listed in "Files you may change"**. Everything else (routes, sidebar, API client, page wiring, settings) is already connected for you.

## 0. Project facts (read first)

- **Root:** `test-demo/`. Backend is Python 3.14 + Flask (`app.py`, venv at `test-demo/venv`). Frontend is Next.js in `test-demo/frontend` (React, no TypeScript).
- **This Next.js version has breaking changes.** Read `frontend/AGENTS.md` and the guide in `frontend/node_modules/next/dist/docs/` before writing frontend code.
- **Lead storage:** `all_leads_master.csv` via `lead_normalizer.MasterLeadRegistry`. Never write to this file from tests.
- **The owner's working rules (must follow):**
  - Ask before installing any dependency. **Do not install anything**; use only libraries already in the venv: `requests`, `bs4`, `duckduckgo_search`, stdlib.
  - Never commit, push, or deploy.
  - Never edit `.env`, and never print, log, or hard-code secrets.
  - Never bypass captchas, logins, Cloudflare, or other bot protection. Never rotate IPs or user agents to avoid blocks. If a site blocks automated access, mark that source `unavailable` with the reason.
  - Docs must be bilingual: English + Gujarati.
  - "Developed ≠ Completed": anything not verified live must be marked **UNVERIFIED** in the QA report.

## 1. Goal

A page where the user finds **companies outside India** by keyword, target audience, country, and optional city/region. Results show company name, website, address, phone/email when available, and source. The user can then **Deep Search** rows (to find email/phone from the company website), **Export CSV**, and **Save to Leads**.

## 2. Already wired (do NOT change these files)

| What | Where | Contract |
|---|---|---|
| Catalog API | `app.py` → `GET /api/global-directories` | returns `{sources: list_sources(), countries: COUNTRIES, maxKeywords: MAX_KEYWORDS}` |
| Search API | `POST /api/global-directories/search` | passes `{keywords, audience, country, region, city, sources}` to `global_directories.search(params)`. A `ValueError` becomes HTTP 400 with your message. Results are cached by `search_cache.py` (module `globaldirectories`, 72 h), and only cached when every source has status `ok`/`skipped` and `total > 0`. Request body may include `refresh: true` to bypass the cache. |
| Save API | `POST /api/global-directories/save` | `{results: [...]}`, uses your `result_to_raw_lead()` and returns `{added, updated, duplicate, skipped_invalid}` |
| Frontend API | `frontend/lib/api.js` | `fetchGlobalDirectories()`, `searchGlobalDirectories(params)`, `saveGlobalDirectoryResults(results)`, `runDeepSearch({items, engine, use_hunter, place})` |
| Page | `frontend/app/page.js` | renders `<GlobalDirectories onLeadsSaved onOpenSearchEngine />` when the sidebar item "Global Directories" is clicked |
| Keys in Settings | `api_keys_catalog.py`, `.env.example` | `COMPANIES_HOUSE_API_KEY`, `SEC_USER_AGENT`, `GLOBAL_DIR_CACHE_HOURS` are already listed |

## 3. Files you may change / create

1. `test-demo/global_directories.py`: currently a **stub with the contract in its docstring**. Implement it without changing function names, arguments, or return shapes.
2. `test-demo/frontend/components/GlobalDirectories.js`: currently a stub. Replace it with the real page.
3. **New:** `test-demo/test_global_directories.py`
4. **New:** `test-demo/docs/global-directories.md` (English + Gujarati)
5. **New:** `test-demo/reports/qa/<YYYY-MM-DD>-global-directories.md` (English + Gujarati)

Do not edit any other file. If you believe another file must change, stop and write the exact change you need in your final message.

## 4. Backend: `global_directories.py`

**Study these first** and copy their patterns: `crm_sources.py` (very similar module), `job_portals.py` (helpers `_session`, `_get`, `_clean`, `PortalError`), `search_engine.py` (validation style).

### 4.1 Sources (`list_sources()`)

| id | name | status | how |
|---|---|---|---|
| `osm` | OpenStreetMap (worldwide) | available | Overpass API `https://overpass-api.de/api/interpreter`. Find the city/region area by name inside the selected country (ISO code, e.g. `area["ISO3166-1"="GB"]`), then search `office`/`craft`/`shop` features with a name regex for the keyword, like `crm_sources.search_osm`. Needs a city or region; if neither is given, return the source as `skipped` with errors `["OpenStreetMap needs a city or region"]`. Use `[timeout:25]`, a 35 s request timeout, one retry on 502/504, then a "busy - try again" error. Send a descriptive User-Agent like `crm_sources.OSM_USER_AGENT`. |
| `companies_house` | UK Companies House | needs_key (`COMPANIES_HOUSE_API_KEY`) | Official API `https://api.company-information.service.gov.uk/advanced-search/companies` (HTTP Basic auth: key as username, empty password). Params: `company_name_includes=<keyword>`, `location=<city>` (optional), `company_status=active`, `size=<max>`. Map: name, `company_number`, registered office address, SIC codes (as category). URL = `https://find-and-update.company-information.service.gov.uk/company/<number>`. Only for country `GB`; otherwise `skipped`. |
| `sec_edgar` | US SEC EDGAR | needs_key (`SEC_USER_AGENT`) | SEC requires a descriptive User-Agent with contact info: use exactly the value of `SEC_USER_AGENT`, never invent one. Use the official endpoints at `https://www.sec.gov` / `https://efts.sec.gov` (e.g. company search `https://www.sec.gov/cgi-bin/browse-edgar?company=<kw>&State=<2-letter>&type=10-K&owner=include&count=40&action=getcompany&output=atom`, or the full-text search API). Keep under 10 requests/second. Map company name, CIK, state, and the EDGAR URL. Only for country `US`; `region` = US state name or code (optional). |
| `goodfirms` | GoodFirms (worldwide, IT/software only) | available | Reuse `crm_sources.search_goodfirms` logic for a city (e.g. `london`, `new-york`). Only when a city is given; otherwise `skipped`. |
| `opencorporates` | OpenCorporates | unavailable | reason: "API is paid for commercial use" |
| `yelp` | Yelp | unavailable | reason: "Fusion API needs a paid plan for commercial use" |
| `clutch` | Clutch | unavailable | reason: "Blocks automated requests (Cloudflare)" |
| `europages` | Europages / Kompass | unavailable | reason: "Listings blocked or behind login for automated access" |

- **Status:** a `needs_key` source becomes `available` automatically when its env var is set; check it at call time, like `crm_sources.list_sources()` does.
- **Verify before you write:** before writing each parser, call the real endpoint once with a small request and check the actual response shape. Do not guess field names. If an endpoint does not work as described here, mark the source `unavailable` with the real reason and say so in the report.

### 4.2 `COUNTRIES`

A list of `{"id": ISO-3166 alpha-2, "name"}` sorted by name. Include at least: AE, AU, CA, DE, FR, GB, IE, IL, IT, JP, KE, MY, NG, NL, NZ, PH, QA, SA, SE, SG, ES, CH, US, ZA. Exclude IN, because India has its own modules.

### 4.3 `validate_request(data)`

Raise `ValueError` with these messages:
- **keywords:** a list of 1..`MAX_KEYWORDS`, each at most 80 characters, de-duplicated case-insensitively, no `"`. Message: `"Enter at least one keyword"`, etc.
- **audience:** an optional list of at most 5, each at most 60 characters. Use it to narrow results: keep a result if any audience word appears in its category/name/details. If that leaves zero results for a source, keep the unfiltered results and add a note in `errors`.
- **country:** required and must be in `COUNTRIES`. Message: `"Select a country"`.
- **city / region:** optional. Letters, spaces and `.'-` only, at most 60 characters.
- **sources:** a non-empty list of known ids, all `available` now. Message: `"Select at least one source"` / `"<name> needs <ENV> in .env"`.

### 4.4 `search(data)`

- **Run:** validate the request, then run the selected sources in parallel with `ThreadPoolExecutor` (max 4), each in try/except.
- **Per-source status:** `{"name", "status": "ok"|"error"|"skipped", "count", "seconds", "errors"}`.
- **Results:** at most `MAX_RESULTS_PER_SOURCE` per source. Dedupe by website domain, else by normalised company name + country. Put results with email/phone/website first.
- **Never raise** for one source failing. Only a `ValueError` from validation may escape.

### 4.5 `result_to_raw_lead()`

This is already written in the stub. Keep it, or extend it carefully, e.g. add the CIN/company number to the description.

## 5. Frontend: `GlobalDirectories.js`

- **Copy the structure of `frontend/components/SearchEngine.js` and `CrmSources.js`.** The user wants every Scraping / Mining page to look and behave the same.
- **Form:** use the shared **`MiningForm`** (`frontend/components/MiningForm.js`):
  - `idPrefix="gd"`
  - `keywords` (required)
  - `audience` (enabled)
  - `location={{ mode: 'country', countries, country, setCountry, countryError, city, setCity, cityError, onClear }}`
  - `extra`: one optional "Region / State" text input (`id="gd-region"`), hinted "(optional — US state for SEC, region for OpenStreetMap)"
  - `sources` multi-select with groups: Directories, Official registers, "Need API key", "Not available"
  - no `maxResults`
- **Panel header:** icon `Globe` from `lucide-react`, title "Global Directories", one-line subtitle.
- **After a search:**
  - success/error notice (`role="status"`), `<CacheNote>` with "Search live again" (`refresh: true`), a chip per source (`jp-status-chip`)
  - results table with filter box, select-all, columns: Company, Email, Phone, Website, Location (+country), Category, Source, Open-link
  - **Deep Search** button: call `runDeepSearch` in batches of 10 with items `{key: url, url, website, company, kind: website ? 'website' : 'listing'}` and `place: city || region`, and merge the results into the rows the same way `SearchEngine.js` does (email/phone/website/socials/status badge)
  - **Export CSV** (prefix cells starting with `= + - @` with `'`)
  - **Save to Leads** (`saveGlobalDirectoryResults`, then call `onLeadsSaved()`)
- **Styling:** reuse the existing CSS classes (`theme-card-panel`, `jp-*`, `se-*`). Do not edit `globals.css`; use small inline styles if really needed.
- **Mobile:** no horizontal page scroll at 390 px width.

## 6. Tests: `test_global_directories.py` (unittest, NO network)

Mock every HTTP call (`unittest.mock`). Cover:
- **Validation:** every rule and message.
- **Catalog:** status flips from `needs_key` to `available` when the env var is set (`mock.patch.dict(os.environ, ...)`).
- **Parsers:** each source, using small realistic sample responses that you captured once from the real API (trim them). Include an empty response and an HTTP error (401/403/429/5xx → readable error, no crash).
- **Skip rules:** Companies House only for GB; SEC only for US; OSM/GoodFirms without a city are `skipped`.
- **Search behaviour:** audience filtering and its fallback; dedupe and ordering; one source failing → others still return.
- **Saving:** `result_to_raw_lead()` output.
- **API endpoints** (Flask `app.app.test_client()`): auth pattern exactly as in `test_crm_sources.py` class `Api`; 401 without login; 400 on bad input; save with `mock.patch.object(app, "MASTER_PATH", <temp file>)` → added then duplicate. Patch `html_cache_manager.CACHE_DIR` to a temp dir so the real cache is not touched.

## 7. Verify (run all, paste the outputs in the QA report)

```bash
cd test-demo
venv/Scripts/python.exe -m unittest test_global_directories -v
venv/Scripts/python.exe -m unittest test_lead_system test_quality_and_auth test_feedly test_accuracy test_html_cache test_sources test_website_signals test_apollo test_job_portals test_followups test_followup_phase2 test_followup_extras test_crm_sources test_api_keys test_search_cache test_search_engine test_supabase_sync test_global_directories
cd frontend && npm run build
```

- **Live smoke test without keys:** OSM country GB, city London, keyword "software"; and GoodFirms London. Record the counts in the report.
- **Mark UNVERIFIED** anything you could not run live, e.g. Companies House and SEC without keys.
- **Protect the leads file:** before any manual save test, copy `all_leads_master.csv` to a backup and restore it afterwards; check that the md5 matches.

## 8. Docs

- `docs/global-directories.md`: English then Gujarati. Cover purpose, how to use, a sources table (status, key, limits), result rules, known limits, and a technical table. Follow the style of `docs/crm-sources.md`.
- QA report: follow the style of `reports/qa/2026-11-11-crm-sources.md`. Cover automated tests, live checks, bugs found/fixed, UNVERIFIED items, and data safety.

## 9. Final message to the owner

List:
- every file you created or changed
- the test results (counts)
- what is verified and what is UNVERIFIED
- any change you need in a file you were not allowed to edit

Do not commit.

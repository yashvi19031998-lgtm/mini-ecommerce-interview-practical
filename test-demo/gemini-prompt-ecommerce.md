# Task: build the "Ecommerce Platforms" module (Scraping / Mining → Ecommerce Platforms)

You are working in an existing lead-generation app. Another engineer owns the rest of the code and works in parallel, so **stay strictly inside the files listed in section 3**. Routes, API client, page wiring and cache are already connected for you.

You built "Global Directories" last time. The review of that module found the bugs listed in **section 9**. Avoid all of them here; the reviewer will check each one again.

## 0. Project facts (read first)

- **Root:** `test-demo/`. Backend is Python 3.14 + Flask (`app.py`, venv `test-demo/venv`). Frontend is Next.js in `test-demo/frontend` (React, no TypeScript).
- **This Next.js version has breaking changes.** Read `frontend/AGENTS.md` and `frontend/node_modules/next/dist/docs/` before writing frontend code.
- **Lead storage:** `all_leads_master.csv` via `lead_normalizer.MasterLeadRegistry`. Never write to it from tests.
- **The owner's rules (must follow):**
  - **Do not install anything.** Use only `requests`, `bs4`, stdlib and the project's modules.
  - Never commit, push, or deploy.
  - Never edit `.env`; never print, log, or hard-code secrets.
  - **Never bypass captchas, logins, Cloudflare, or other bot protection**, and never rotate IPs or user agents. If a site blocks automated access, mark that source `unavailable` with the real reason.
  - Docs must be bilingual: English + Gujarati.
  - "Developed ≠ Completed": mark anything not verified live as **UNVERIFIED**.
  - **Do not leave scratch / probe scripts in the repo.** Put them in a temp folder outside `test-demo/` and delete them when done.

## 1. Goal

A page where the user finds **online stores and sellers** (D2C brands, small shops selling online) for a product category in India, e.g. "handmade jewellery", "organic tea", "kurti". These are leads for website, app, or marketing services.

- **Results:** store name, website, platform (Shopify / WooCommerce / …), category, location if known, Instagram/Facebook if found, email/phone if found.
- **Actions:** **Deep Search** (email/phone from the store website), **Export CSV**, **Save to Leads**.

## 2. Already wired (do NOT change these files)

| What | Where | Contract |
|---|---|---|
| Catalog API | `app.py` → `GET /api/ecommerce` | returns `{sources: list_sources(), engines: search_engine.list_engines(), states, maxKeywords: MAX_KEYWORDS, deepBatch}` |
| Search API | `POST /api/ecommerce/search` | passes `{keywords, audience, state, city, sources, engine, engine_used}` to `ecommerce_sources.search(params)`. `ValueError` → HTTP 400. Cached by `search_cache.py` (module `ecommerce`, 48 h); only cached when no source has status `error` and `total > 0`. `refresh: true` bypasses the cache. The route already marks `in_leads` / `match` on every result. |
| Save API | `POST /api/ecommerce/save` | `{results}` → your `result_to_raw_lead()` → `{added, updated, duplicate, skipped_invalid}` |
| Frontend API | `frontend/lib/api.js` | `fetchEcommerceSources()`, `searchEcommerce(params)`, `saveEcommerceResults(results)`, `runDeepSearch({items, engine, use_hunter, place})` |
| Page | `frontend/app/page.js` | renders `<Ecommerce onLeadsSaved onOpenSearchEngine />` for the sidebar item "Ecommerce Platforms" |

## 3. Files you may change / create

1. `test-demo/ecommerce_sources.py`: a **stub with the contract in its docstring**. Implement it without changing names, arguments, or return shapes.
2. `test-demo/frontend/components/Ecommerce.js`: a stub. Replace it with the real page.
3. **New:** `test-demo/test_ecommerce_sources.py`
4. **New:** `test-demo/docs/ecommerce-platforms.md` (English + Gujarati)
5. **New:** `test-demo/reports/qa/<YYYY-MM-DD>-ecommerce-platforms.md` (English + Gujarati)

Do not edit any other file. If another file must change, stop and write the exact change in your final message.

## 4. Backend: `ecommerce_sources.py`

**Study first:**
- `search_engine.py`: engines, `ENGINE_FUNCS`, `resolve_engine`, `engine_available`, `RateLimited`, `EngineError`, `domain_of`, `is_platform`, `JUNK_DOMAINS`, `ARTICLE_RE`, `clean_title`, `snippet_contacts`, `required_sites` / `matches_required`.
- `deep_search.py` (`public_url_guard`, `fetch`).
- `maps_sources.py` and `global_directories.py`: the structure to copy.

### 4.1 How results are found

Search engines find stores with "footprint" queries. You must **reuse `search_engine.ENGINE_FUNCS[engine](query, count, "any", session)`**. Do not call any search engine directly, and do not scrape Google/Bing/DuckDuckGo HTML.

### 4.2 Sources (`list_sources()`)

| id | name | kind | status | how |
|---|---|---|---|---|
| `shopify` | Shopify stores | store_platform | available | Queries like `site:myshopify.com "{kw}"` and `"{kw}" "powered by Shopify" {place}`. Platform = Shopify. **Optional verification**: GET `https://<domain>/products.json?limit=1` through `deep_search.fetch` / a guarded GET (public endpoint); if it returns JSON with `products`, set `details` to "Shopify store verified". Never send more than 1 verification request per store, at most 15 stores per search. |
| `woocommerce` | WooCommerce stores | store_platform | available | `"{kw}" "add to cart" "woocommerce" {place}` and `"{kw}" inurl:product-category {place}`. Platform = WooCommerce. |
| `instagram_shops` | Instagram shops | store_platform | available | `site:instagram.com "{kw}" ("shop now" OR "DM to order" OR "order now") {place}`. Keep only profile URLs (`instagram.com/<handle>/`, not `/p/`, `/reel/`, `/explore/`). company = handle or title; put the profile URL in `instagram` and `url`; no website. |
| `amazon_in` | Amazon.in sellers | marketplace | unavailable | reason: "Amazon blocks automated access; seller pages need a browser" |
| `flipkart` | Flipkart sellers | marketplace | unavailable | reason: "Flipkart blocks automated access" |
| `meesho` | Meesho sellers | marketplace | unavailable | reason: "Seller details need login" |

- **Off-target results:** drop them for queries with `site:` using `search_engine.required_sites` / `matches_required`, and drop `JUNK_DOMAINS` and list articles (`ARTICLE_RE`).
- **Before writing each parser:** run one real query per source (any engine that works) and check what comes back. If a footprint returns nothing useful, say so in the report. Do not invent results.

### 4.3 `validate_request(data)` (`ValueError` messages)

- **keywords:** list, 1..5 items, each ≤ 80 chars, no `"`, de-duplicated case-insensitively. Message: `"Enter at least one product or category"`.
- **audience:** optional, ≤ 5 items, each ≤ 60 chars, no `"`. Narrow results **by word** (split into words of 3+ letters, see the review notes). If nothing matches, keep all results and add a note in that source's `errors`.
- **state:** required, `"All India"` or a key of `job_portals.INDIAN_STATES`. Message: `"Select a state"`. **city:** optional, letters / space / `.'-`, ≤ 60 chars.
- **sources:** non-empty, known ids, all `available`. Messages: `"Select at least one source"`, `"<name> is not available: <reason>"`.
- **engine:** `"auto"` or an id from `search_engine.ENGINES`. Use `search_engine.resolve_engine()`. If the resolved engine is not available, raise `"<engine name> needs <KEY> in .env"`.
- **Place text** for queries: city, else state, else "India".

### 4.4 `search(data)`

- **Sources in parallel:** `ThreadPoolExecutor`, max 3. **Queries inside one source run one after another** with `time.sleep(search_engine.GAP_SECONDS[engine])` between them.
- **Rate limit:** on `search_engine.RateLimited`, stop that source, keep what it found, set status `ok` if it has results (else `error`), and add the message to `errors`.
- **Catch every exception per source** (`except Exception`). One source must never fail the whole search. Show `requests.Timeout` as "did not answer in time (server busy) - try again later".
- **Results:** at most `MAX_RESULTS_PER_SOURCE` per source. One row per store domain (Instagram: per handle). **When a duplicate has fields the kept row is missing (email, phone, website, instagram, facebook), copy them over.** Do not drop them.
- **Snippet contacts:** use `search_engine.snippet_contacts()` on title + snippet.
- **Order:** rows with email/phone first, then those with a website.
- **Return:** `{"query", "results", "total", "sources", "engine": <engine used>, "hint"}`. If `total == 0` and the engine is `duckduckgo`, set `hint` to the same advice text `search_engine.search()` uses (add a Brave/Serper key).

### 4.5 `result_to_raw_lead()`

Keep the stub's mapping, or extend it carefully (e.g. add the Instagram URL to the description). The lead type must stay `"Ecommerce Store"`.

## 5. Frontend: `Ecommerce.js`

- **Copy the structure of `frontend/components/GoogleMaps.js`.** It is the most recent and reviewed page; match its look and behaviour.
- **Form:** use **`MiningForm`**:
  - `idPrefix="ec"`
  - `keywords` (label "Product / category", placeholder "e.g. handmade jewellery, organic tea, kurti")
  - `audience` enabled
  - `location={{ mode: 'india', ... stateRequired: true }}` with city
  - `sources` with groups: Store platforms / Marketplaces / Not available
  - `extra` = a **Search engine** select (`id="ec-engine"`), exactly like `SearchEngine.js`: options from `engines`, disabled when `status !== 'available'`, with the "— add key in Settings" suffix and the engine note below
- **Header:** icon `ShoppingCart`, title "Ecommerce Platforms", one-line subtitle.
- **After a search:**
  - notice (`role="status"`); show an error notice when every source failed
  - `CacheNote` with "Search live again"
  - per-source chips (`jp-status-chip`) and an error list (`se-errors`)
  - the `hint` as a warning (`jp-alert se-alert-warn`) when present
- **Table:**
  - Columns: select | Store (name + platform badge + category/location) | Email | Phone | Website | Social (ig/fb links) | **Status** | open link.
  - **Status** shows the `In leads` badge (`se-badge inleads`) and the Deep Search badge (`se-badge deep-<status>`, steps as a ` | ` separated title). Use `New` when neither applies.
- **Deep Search:** batches of `deepBatch`; skip rows without a website (Instagram-only rows); merge emails/phones/socials into the rows the same way `GoogleMaps.js` does.
- **Export CSV:** prefix cells that start with `= + - @` with `'`; add a UTF-8 BOM.
- **Save to Leads:** afterwards mark the saved rows `in_leads` and call `onLeadsSaved()`.
- **Styling:** only existing CSS classes (`theme-*`, `jp-*`, `se-*`, `cache-note`). Do not edit `globals.css`. Mobile 390 px: no horizontal page scroll.
- **Escapes:** inside JSX use `' | '` as the steps separator, not a newline.

## 6. Tests: `test_ecommerce_sources.py` (unittest, NO network)

Mock `search_engine.ENGINE_FUNCS` and every HTTP call. Cover:
- **Validation:** every rule and message, including the engine needing a key (`mock.patch.dict(os.environ, {"BRAVE_SEARCH_API_KEY": ""})`).
- **Query building:** per source, with the place text.
- **Instagram:** profile-URL filter (posts and reels are dropped).
- **Filtering:** off-target `site:` results dropped; junk and list articles dropped.
- **Dedupe:** merges missing contact fields from duplicates.
- **Audience:** word matching, e.g. "IT / Software" matches "software"; fallback note when nothing matches.
- **Rate limit:** keeps partial results.
- **Errors:** an unexpected exception (e.g. `AttributeError`) in one source → that source `error`, the others still return.
- **Shopify verification:** at most 15 requests; a non-JSON answer is handled.
- **Lead mapping:** `result_to_raw_lead`.
- **API:**
  - auth exactly like `test_maps_sources.py` class `Api`
  - patch `html_cache_manager.CACHE_DIR` to a temp dir
  - 401 without login; 400 on bad input
  - search cached on the second call (mock `ecommerce_sources.search`)
  - save → added, then duplicate, with `mock.patch.object(app, "MASTER_PATH", <temp>)`

## 7. Verify (run all, paste outputs in the QA report)

```bash
cd test-demo
venv/Scripts/python.exe -m unittest test_ecommerce_sources -v
venv/Scripts/python.exe -m unittest test_lead_system test_quality_and_auth test_feedly test_accuracy test_html_cache test_sources test_website_signals test_apollo test_job_portals test_followups test_followup_phase2 test_followup_extras test_crm_sources test_api_keys test_search_cache test_search_engine test_supabase_sync test_maps_sources test_global_directories test_ecommerce_sources
cd frontend && npm run build
```

- **Live check:** run one live search per available source with the engine that works (DuckDuckGo without a key is often empty; that is expected, so record it honestly). Record the counts.
- **Protect the leads file:** before any manual save test, back up `all_leads_master.csv`, restore it afterwards, and compare the md5.

## 8. Docs

- `docs/ecommerce-platforms.md`: English then Gujarati. Cover purpose, how to use, a sources table, result rules, known limits (search-engine dependent, DuckDuckGo unreliable, marketplaces unavailable and why), and a technical table. Follow the style of `docs/google-maps.md`.
- QA report: follow the style of `reports/qa/2026-11-12-google-maps.md`.

## 9. Bugs found in your last module: do not repeat

1. **A URL built with an f-string and an unencoded keyword.** Always use `params=` with requests.
2. **Audience matched the whole phrase.** Match by words.
3. **Only some exception types were caught**, so one source could fail the whole search with HTTP 500. Catch `Exception` per source.
4. **Dedupe dropped the duplicate that had the email/phone.** Merge the missing fields.
5. **The Deep Search status badge was computed but never shown.** Render it.
6. **"Found 0" success notice when every source failed.** Show an error notice instead.

## 10. Final message to the owner

List:
- the files created or changed
- the test counts
- what is verified and what is UNVERIFIED
- any change needed in a file you were not allowed to edit

Do not commit.

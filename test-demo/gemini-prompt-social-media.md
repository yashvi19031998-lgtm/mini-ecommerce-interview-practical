# Task: build the "Social Media" module (Scraping / Mining → Social Media)

You are working in an existing lead-generation app. Another engineer owns the rest of the code and works in parallel (building "Ad Library" and "WhatsApp Groups" right now), so **stay strictly inside the files listed in section 3**. Routes, API client, page wiring and cache are already connected for you.

You built "Global Directories" and "Ecommerce Platforms" before. **Section 9 lists every mistake found in those reviews.** Avoid all of them; the reviewer checks each one.

## 0. Project facts (read first)

- **Root:** `test-demo/`. Backend is Python 3.14 + Flask (`app.py`, venv `test-demo/venv`). Frontend is Next.js in `test-demo/frontend` (React, no TypeScript).
- **This Next.js version has breaking changes.** Read `frontend/AGENTS.md` and `frontend/node_modules/next/dist/docs/` before writing frontend code.
- **Lead storage:** `all_leads_master.csv` via `lead_normalizer.MasterLeadRegistry`. Never write to it from tests.
- **The owner's rules (must follow):**
  - **Do not install anything.** Use only `requests`, `bs4`, stdlib and the project's modules.
  - Never commit, push, or deploy. Never edit `.env`; never print, log, or hard-code secrets.
  - **Never bypass captchas, logins, rate limits, or bot protection.** Never rotate IPs or user agents, and **never send a browser-like User-Agent** (no `Mozilla/5.0 …`). **Do not request instagram.com, facebook.com, linkedin.com, x.com or youtube.com pages yourself.** They require login or block bots, and scraping them breaks their terms. All social data comes **only from search-engine results** (title, URL, snippet).
  - **Privacy (India DPDP Act 2023):** collect **business / brand pages only**. Skip pages that look like a private person's profile (see 4.3). Never collect follower lists, comments, or people's personal details.
  - Docs must be bilingual: English + Gujarati. "Developed ≠ Completed": mark anything not verified live as **UNVERIFIED**.
  - **Do not leave scratch / probe scripts in the repo.** Use a temp folder outside `test-demo/` and delete them.

## 1. Goal

Find **business pages** on social networks for a business category in a place, e.g. "bakery" in Ahmedabad, "interior designer" in Pune. Many small businesses only have an Instagram / Facebook page, and no website. These are leads for website, marketing, or app services.

- **Results:** business name, network, handle / page URL, category, place, followers (if the snippet shows it), email / phone (if the snippet shows it), website (if the snippet shows it).
- **Actions:** **Deep Search** (only for rows that have a website), **Export CSV**, **Save to Leads**.

## 2. Already wired (do NOT change these files)

| What | Where | Contract |
|---|---|---|
| Catalog API | `app.py` → `GET /api/social` | `{sources: list_sources(), engines: search_engine.list_engines(), states, maxKeywords: MAX_KEYWORDS, deepBatch}` |
| Search API | `POST /api/social/search` | passes `{keywords, audience, state, city, sources, engine, engine_used}` to `social_sources.search(params)`. `ValueError` → HTTP 400. Cached (module `social`, 48 h) only when no source is `error` and `total > 0`. `refresh: true` bypasses the cache. The route marks `in_leads` / `match` on every result. |
| Save API | `POST /api/social/save` | `{results}` → your `result_to_raw_lead()` → `{added, updated, duplicate, skipped_invalid}`. A row needs `company` or `handle`, plus `profile_url` / `url` / `website` / `email` / `phone`. |
| Frontend API | `frontend/lib/api.js` | `fetchSocialSources()`, `searchSocial(params)`, `saveSocialResults(results)`, `runDeepSearch({items, engine, use_hunter, place})` |
| Page | `frontend/app/page.js` | renders `<SocialMedia onLeadsSaved onOpenSearchEngine />` for "Social Media" |

## 3. Files you may change / create

1. `test-demo/social_sources.py`: a **stub with the contract in its docstring**. Implement it without changing names, arguments, or return shapes.
2. `test-demo/frontend/components/SocialMedia.js`: a stub. Replace it with the real page.
3. **New:** `test-demo/test_social_sources.py`
4. **New:** `test-demo/docs/social-media.md` (English + Gujarati)
5. **New:** `test-demo/reports/qa/<YYYY-MM-DD>-social-media.md` (English + Gujarati)

Do not edit any other file. The sidebar "Soon" badge is removed by the reviewer. If another file must change, stop and write the exact change in your final message.

## 4. Backend: `social_sources.py`

**Study first:**
- `ecommerce_sources.py`: your own reviewed module. Copy its structure, especially `_run_source`, dedupe merge, the 429 handling idea, and the Instagram profile regex.
- `search_engine.py`: `ENGINE_FUNCS`, `resolve_engine`, `engine_available`, `RateLimited`, `domain_of`, `required_sites`, `matches_required`, `snippet_contacts`, `clean_title`, `place_text`, `GAP_SECONDS`.
- `realestate_sources.py`.

### 4.1 Sources (`list_sources()`); all results come from `search_engine.ENGINE_FUNCS[engine](query, count, "any", session)`

| id | name | status | queries ({kw}, {place}) | keep only these URLs |
|---|---|---|---|---|
| `instagram` | Instagram business pages | available | `site:instagram.com "{kw}" {place}`, `site:instagram.com "{kw}" {place} ("DM" OR "order" OR "booking" OR "enquiry")` | `instagram.com/<handle>/` (not `/p/`, `/reel/`, `/reels/`, `/explore/`, `/stories/`, `/tv/`, `/accounts/`) |
| `facebook` | Facebook business pages | available | `site:facebook.com "{kw}" {place}` | `facebook.com/<page>` or `facebook.com/profile.php?id=…` (not `/groups/`, `/events/`, `/posts/`, `/photos/`, `/videos/`, `/watch/`, `/marketplace/`, `/sharer`, `/login`, `/help/`) |
| `linkedin` | LinkedIn company pages | available | `site:linkedin.com/company "{kw}" {place}` | `linkedin.com/company/<slug>` only (never `/in/`, which is a person) |
| `x` | X (Twitter) business accounts | available | `site:x.com "{kw}" {place}`, `site:twitter.com "{kw}" {place}` | `x.com/<handle>` / `twitter.com/<handle>` (not `/status/`, `/hashtag/`, `/search`, `/i/`, `/intent/`) |
| `youtube` | YouTube channels | available | `site:youtube.com "{kw}" {place} channel` | `youtube.com/@handle`, `/c/…`, `/channel/…`, `/user/…` (not `/watch`, `/shorts/`, `/playlist`) |
| `whatsapp_business` | WhatsApp Business catalogs | unavailable | — | reason: "Business catalogs are only visible inside the WhatsApp app" |

- **Off-target results:** for `site:` queries use `search_engine.required_sites` / `matches_required`.
- **Verify before you write each parser:** run one real query per network (DuckDuckGo may return nothing; record it honestly). Do not invent results.

### 4.2 Fields from the result (title / URL / snippet only)

- **handle:** from the URL path. **network:** "Instagram" / "Facebook" / "LinkedIn" / "X" / "YouTube".
- **company:** `search_engine.clean_title(title)` with suffixes like `• Instagram photos and videos`, `| Facebook`, `on LinkedIn`, `(@handle)` removed. Fall back to the handle.
- **profile_url:** a normalised `https://www.<network>/<path>` without query strings (except Facebook `profile.php?id=`). Use it as `url` too.
- **followers:** if the snippet contains e.g. `12.5K Followers` / `1,234 followers`, keep the text as shown (e.g. `12.5K`).
- **email / phone:** `search_engine.snippet_contacts(title + snippet)`.
- **website:** a URL that appears in the snippet (`https?://…` or `www.…`), else empty. Never use as website a social network URL, a link shortener / link-in-bio page (`bit.ly`, `linktr.ee`, `linkin.bio`, `wa.me`) or a search-engine URL.
- **category:** the keyword; **location:** the place text.

### 4.3 Privacy filter (must have, must be tested)

Keep a result only if it looks like a business:
- it is a LinkedIn **company** page, or YouTube channel, or
- the title/snippet contains a business word (shop, store, studio, salon, cafe, bakery, boutique, clinic, academy, classes, services, solutions, agency, official, pvt, ltd, llp, co., enterprises, traders, restaurant, hotel, interiors, designs, photography, events, real estate, builders, or the searched keyword itself), or
- it shows a phone / email / website in the snippet.

Otherwise drop it as a probable private person, and count these as `"skipped_personal"` in the source's `errors` note (e.g. "4 personal-looking profiles skipped").

### 4.4 `validate_request(data)` / `search(data)` / `result_to_raw_lead()`

- **Same validation and messages as `ecommerce_sources.py`:**
  - keywords 1..5, ≤ 80 chars, no `"` → `"Enter at least one business type or keyword"`
  - audience ≤ 5
  - state required, plus city
  - sources available
  - engine resolved/available
- **Search:**
  - Sources in parallel (max 3); queries inside a source one after another with `GAP_SECONDS[engine]`.
  - `RateLimited` stops that source and keeps its partial results.
  - `except Exception` per source; `requests.Timeout` gets the friendly message.
- **Results:**
  - Dedupe per `network + handle` (case-insensitive). Merge missing fields from duplicates.
  - Audience narrows by words, with a fallback note.
  - Order: rows with phone/email first, then with website, then by followers (parse K/M) descending.
- **Return:** `hint` when `total == 0` and the engine is `duckduckgo` (same text as `search_engine.search()`).
- **`result_to_raw_lead()`:** keep the stub mapping; the lead type stays `"Social Media Business"`.

## 5. Frontend: `SocialMedia.js`

- **Copy `frontend/components/Ecommerce.js`** (your reviewed page). The structure, `MiningForm` usage, engine select (`id="sm-engine"`), notices, `CacheNote`, chips, hint, Deep Search, CSV and Save are the same.
  - `idPrefix="sm"`, header icon `Share2`, title "Social Media".
  - **Sources groups:** `{ status: 'available', label: 'Social networks' }`, `{ status: 'needs_key', label: 'Needs API key' }`, `{ status: 'unavailable', label: 'Not available' }`. **Each source must appear exactly once.**
- **Table columns:** select | Business (name + network badge + category/location) | Handle (link to `profile_url`) | Followers | Email | Phone | Website | **Status** (In leads / Deep Search badge with ` | ` separated steps / New) | open link.
- **Deep Search** only for rows with a website. Send `{key, url: website, website, company, kind: 'website'}`; never send the social profile URL.
- **Filter row:** add a small select "Network: All / Instagram / Facebook / LinkedIn / X / YouTube" (client-side filter).
- Only existing CSS classes; mobile 390 px with no horizontal scroll; CSV with BOM and `= + - @` protection.

## 6. Tests: `test_social_sources.py` (unittest, NO network)

Mock `search_engine.ENGINE_FUNCS` and every HTTP call. Cover:
- **Validation:** every rule and message.
- **URL filters:** every network, with good and bad URLs from the table in 4.1 (incl. LinkedIn `/in/` dropped).
- **Field extraction:** handle / company cleaning, followers ("12.5K Followers", "1,234 followers"), website from snippet (social and shortener URLs not used as website).
- **Privacy filter:** business kept; personal-looking profile dropped and counted.
- **Results:** dedupe per network+handle with merge; audience by words with fallback; order incl. followers.
- **Errors:** rate limit keeps partial results; an `AttributeError` in one source does not affect the others; DuckDuckGo-empty hint.
- **No network calls to social sites:** patch `requests.Session.get`, `requests.get` and `html_cache_manager._guarded_get` to fail the test if called during `search()`.
- **Lead mapping:** `result_to_raw_lead`.
- **API:** like `test_ecommerce_sources.py`: 401, 400, cache hit, save added then duplicate, temp `CACHE_DIR` and `MASTER_PATH`.

## 7. Verify (paste outputs in the QA report)

```bash
cd test-demo
venv/Scripts/python.exe -m unittest test_social_sources -v
venv/Scripts/python.exe -m unittest test_lead_system test_quality_and_auth test_feedly test_accuracy test_html_cache test_sources test_website_signals test_apollo test_job_portals test_followups test_followup_phase2 test_followup_extras test_crm_sources test_api_keys test_search_cache test_search_engine test_supabase_sync test_maps_sources test_global_directories test_realestate_sources test_ecommerce_sources test_social_sources
cd frontend && npm run build
```

- **Live check:** one live search per network, recording the real counts (0 on DuckDuckGo is acceptable, but say so).
- **Protect the leads file:** before any manual save test, back up `all_leads_master.csv`, restore it afterwards, and compare the md5.

## 8. Docs

- `docs/social-media.md`: English then Gujarati, in the style of `docs/ecommerce-platforms.md`. Include the privacy rule and why WhatsApp Business is unavailable.
- QA report in the style of `reports/qa/2026-11-12-ecommerce-platforms.md`.

## 9. Mistakes found in your earlier modules: do not repeat any

1. A URL built with an f-string and an unencoded keyword. Use `params=`.
2. Audience matched the whole phrase. Match by words.
3. Only some exception types caught. Catch `Exception` per source.
4. Dedupe dropped the duplicate that had the email/phone. Merge.
5. The Deep Search status badge was computed but not shown.
6. "Found 0" success notice when every source failed.
7. **Browser-impersonating User-Agent** (`Mozilla/5.0 (Windows NT…)`). Never.
8. **Unguarded HTTP GET** (redirects not re-checked). Not needed here at all: this module makes **no HTTP requests of its own**.
9. **A source listed twice in the menu** (overlapping groups).
10. **Treating numbers inside scripts as phone numbers.** Only use `snippet_contacts()` on title + snippet.

## 10. Final message to the owner

List:
- the files created or changed
- the test counts
- what is verified and what is UNVERIFIED
- any change needed in a file you were not allowed to edit

Do not commit.

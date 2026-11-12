# QA Report — Scraping / Mining → Search Engines + Deep Search (and same-day changes)

**Date:** 2026-11-12 · **Build:** uncommitted working tree on `master`
**Result:** PASSED, with the UNVERIFIED items listed in section 5.

**Scope:**
- Scraping / Mining menu with 9 submenus
- Search Engines + Deep Search
- Merge of the old Import "Live Query Search"
- Settings → API Keys
- HTML / search cache rules

---

## English

### 1. Automated tests (Python, no network)
| Suite | Result |
|---|---|
| `test_search_engine.py` (new) | 37/37 pass |
| `test_search_cache.py` (new) | 9/9 pass |
| `test_api_keys.py` (new) | 9/9 pass |
| `test_html_cache.py` (index, size cap, redirect guard added) | 12/12 pass |
| **Full regression (17 suites)** | **259/259 pass** |

**What the new tests cover:**
- **Input checks:** every validation rule.
- **Queries:** every search type builds queries; `{keyword}` / `{city}` placeholders.
- **Results:**
  - `site:` off-target filtering
  - junk domains, list articles, duplicate domains
  - contacts found in the snippet
- **Engines:**
  - rate limit keeps partial results; all queries failing gives an error
  - the DuckDuckGo key hint
  - Brave and Serper request/response parsing and their 401 / 402 / 429 errors
- **Already in leads:** results already saved are marked.
- **Safety:** blocks localhost, private, link-local and IPv6-loopback addresses, other ports, and a redirect to a private IP.
- **Deep Search:**
  - extraction: JSON-LD `@graph`, share buttons ignored, emails on the company's own domain first
  - each waterfall step: website by name match, Zaubacorp, Hunter, guess
  - a list article is skipped; one failing site doesn't break the batch
- **API:**
  - login required on all endpoints; old `/api/import/search` returns 404
  - cache hit, with "in leads" re-checked
  - save field mapping, email off by default, no duplicates on re-save

### 2. Live checks (real network)
- **Deep Search on 3 real company websites** (prakashinfotech.com, agileinfoways.com, spectricssolutions.com): **3/3 Found**, in about 10 s.
  - Results included emails, phones, address and social links.
  - Example: Prakash gave 3 emails, 2 phones and 6 social links from 4 pages, plus JSON-LD data.
- **Private URL blocked:** `http://127.0.0.1:5000/` was blocked ("port 5000 not allowed").
- **DuckDuckGo (no key)** was inconsistent:
  - A plain query returned 25, then 10, then 5, then 0 results as the day went on.
  - `site:` B2B queries returned 0, or results from other sites. Those are now filtered out, and the page shows the add-a-key hint.

### 3. End-to-end UI test (Playwright, real browser and backend) — 19/19 pass
| ID | Test | Result |
|---|---|---|
| SE01 | Sidebar order: Dashboard, Scraping / Mining, FollowUp, CRM; 9 submenus in the requested order; 7 "Soon"; expand/collapse | PASS |
| SE02 | 7 planned-module pages render; "Use Search Engines meanwhile" works | PASS |
| SE03 | Job Portals submenu opens the existing Job Portal Scraper | PASS |
| SE04 | 7 search types; Brave/Serper disabled without keys; 37 states | PASS |
| SE05 | Validation: keyword, custom query, city | PASS |
| SE06 | B2B dork search on DuckDuckGo: 0 results → key hint shown | PASS |
| SE07 | Results table + "Queries used" | PASS* |
| SE08 | Filter + "Only without email/phone" | PASS |
| SE09 | Deep Search on 3 selected websites → 3 × Found | PASS |
| SE10 | Export CSV = visible rows | PASS |
| SE11 | "Send intro email" asks first; cancel saves nothing | PASS |
| SE12 | Save 3 → 3 new leads, source `Search Engine (DuckDuckGo)`, rows marked "In leads" | PASS |
| SE13 | Save again → "0 new, 3 already saved"; master unchanged | PASS |
| SE14 | Same search again → saved results in 0.2 s; "In leads" still shown | PASS |
| SE15 | Import & Parse: Live Query Search tab gone; link opens Search Engines | PASS |
| SE16 | Settings → API Keys lists Brave + Serper (17 integrations) | PASS |
| SE17 | Collapsed sidebar shows the submenu icons | PASS |
| SE18 | Mobile 390 px: no horizontal scroll | PASS |
| SE19 | No browser console errors | PASS |

\* **About SE07:** during the run, DuckDuckGo returned no results for this machine's IP. So the results list was **seeded** with 6 real search results (4 company websites, 1 LinkedIn listing, 1 list article) through the search cache. Everything after the search (table, Deep Search on the live websites, save, export, cache) ran for real.

### 4. Regression of earlier modules
- **CRM Sources UI:** 17/18 pass after `ChipInput` was moved to a shared file.
  - The one failure is the old test's sidebar check. It expected "Job Portal Scraper" as the 2nd item, which is an intended menu change.
- **Cache UI:** 4/4 pass.
- **Settings API Keys UI:** 6/6 pass.

### 5. UNVERIFIED (not tested live)
| Item | Why | How to verify |
|---|---|---|
| Brave Search / Serper results | No API keys yet | Add `BRAVE_SEARCH_API_KEY` / `SERPER_API_KEY`, then search each type |
| Live DuckDuckGo result quality | DuckDuckGo throttled this IP during QA | Re-test on another day / IP |
| Deep Search "find website" for listings and the Zaubacorp step | Need a working search engine | Re-test with a Brave or Serper key |
| Hunter step | No `HUNTER_API_KEY` | Add the key and tick "Use Hunter credits" |
| Supabase sync on save | Supabase keys were blanked during QA (on purpose) | Check one save with keys on |

**Verified later the same day with the owner's test Gmail account** (SMTP + IMAP credentials in `.env`):

| Test | Result |
|---|---|
| E1 SMTP send to the test address | PASS: delivered; found in the inbox over IMAP |
| E2 IMAP login, inbox opened read-only | PASS |
| E3 Search Engines "Send intro email on save" (dummy lead with the test address) | PASS: `emails_sent: 1`, lead `email_status = SENT`, entry in FollowUp History |
| E3a Same address a second time | Blocked by the existing duplicate shield in `email_service.py`, which is correct behaviour |

Test data was removed afterwards: master CSV restored, test rows removed from `logs/sent_emails.csv` and `logs/followup_activity.csv`.

### 6. Bugs found and fixed during this work
1. **Wrong results for `site:` queries:** DuckDuckGo ignores `site:` and returned unrelated pages (e.g. deepmind.google). Off-target results are now filtered.
2. **"Top 10 companies" list pages treated as companies:** they are now marked "list article" and skipped by Deep Search.
3. **Short company names:** `scraper.extract_company_name` splits titles on spaces ("Acme Infotech | …" became "Acme"). Deep Search now uses the JSON-LD name, og:site_name or a cleaned title first. `scraper.py` itself is unchanged.
4. **Import & Parse did not refresh leads after a commit** (prop name mismatch). Fixed.
5. **Ugly lead source names** like "Search Engine (DuckDuckGo (no key))". Now short names are used.
6. **False "Supabase synced" reports.**
   - The bug: `sync_to_supabase.sync()` quietly does nothing when keys are missing, but Import / Save and the "Sync with Supabase" button still reported success.
   - The fix: `sync()` now returns True or False. Save reports `supabase_synced: false`, and the button shows an error. New test `test_supabase_sync.py` (2 tests, in CI); full regression is now **261/261**.

### 7. Data safety
- `all_leads_master.csv` was backed up before QA and restored afterwards (md5 `e015f6f7…` matches).
- SMTP, IMAP and Supabase write keys were blank during QA.
- QA search-cache entries were deleted.

---

## ગુજરાતી

### સારાંશ
- **Unit tests:** 259/259 pass.
- **Browser test:** 19/19 pass. Menu, Search Engines, Deep Search, Save, CSV, cache, Import merge, mobile અને collapsed sidebar ચકાસ્યાં.
- **Deep Search:** 3 સાચી company websites પરથી 3/3 email અને phone મળ્યાં.

### ધ્યાન રાખવાનું
- QA દરમિયાન DuckDuckGo એ આ IP ને 0 results આપ્યાં, એટલે results table ની ચકાસણી 6 સાચા saved results થી કરી. Deep Search, Save અને Export live ચાલ્યાં.
- Brave / Serper, Hunter, email મોકલવું અને Supabase sync હજુ **UNVERIFIED** છે. Keys ઉમેર્યા પછી ફરી test કરવું પડશે.

### Fix થયેલા bugs
- `site:` query માં બીજી sites નાં results આવતાં હતાં. હવે filter થાય છે.
- "Top 10 companies" પ્રકારનાં list pages ને company ગણાતાં હતાં. હવે અલગ ઓળખાય છે.
- Company નામ અધૂરું આવતું હતું ("Acme Infotech" ની જગ્યાએ "Acme"). Fix થયું.
- Import પછી leads list refresh થતી ન હતી. Fix થયું.

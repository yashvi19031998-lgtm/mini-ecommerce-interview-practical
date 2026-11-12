# QA Report — Data Extraction → Indian Directories

**Date:** 2026-11-12 · **Build:** uncommitted working tree on `master` · **Result:** PASSED, with the UNVERIFIED item listed in section 5.

## English

### 1. Feasibility check (live, before building)
Every portal was opened with the app's honest User-Agent, and its `robots.txt` was read first.

| Portal | Result |
|---|---|
| MLMDiary | Directory listing allowed (crawl-delay 5 s). The `?keyword=` search is disallowed, so it is not used. |
| IndiaMART | City and category pages allowed and full of data. `search.mp` is disallowed, so it is not used. |
| **Justdial** | **Empty response (0 KB)** to automated requests. Marked **not available**; no bypass is attempted. |
| Sulekha | City + category pages allowed; data is in JSON-LD. |
| TradeIndia | Category pages allowed. Search is disallowed, so it is not used. |
| ExportersIndia | City and category pages allowed. Search is disallowed, so it is not used. |

### 2. Automated tests (Python, no network)
| Suite | Result |
|---|---|
| `test_indian_directories.py` (new) | 23/23 |
| Full regression (25 suites) | **404/404** |

**What the new tests cover:**
- validation, and the catalog (Justdial unavailable)
- slug variants
- the 5 parsers on hand-made copies of each portal's real page structure
- IndiaMART phone extension
- MLMDiary: companies only — **person names never appear in the output**
- variant fallback, then a clear "no category" message
- TradeIndia redirect treated as not found
- the TradeIndia city page
- Sulekha page 2
- the ExportersIndia state filter
- the MLMDiary 5 s crawl-delay
- network-error isolation
- keyword merge, the audience filter, lead mapping
- `fetch_page` does not cache redirects
- API 401 / 400 / cache / save — the phone really reaches the leads file
- trunk-0 phone numbers

### 3. Browser QA (Playwright, real backend, **live portals**) — 10/10 pass
| ID | Test | Result |
|---|---|---|
| DX01 | Sidebar "Data Extraction → Indian Directories" with 6 items. Justdial page shows "Not available" (no form) and links to Sulekha. Breadcrumb is correct. | PASS |
| DX02 | Sulekha: the city is required. "packers and movers", Ahmedabad → **20 listings**, 5 with a phone. | PASS |
| DX03 | IndiaMART: "bakery products", Ahmedabad → **28 listings**; phone shown as `08047625603 ext 5093`. | PASS |
| DX04 | IndiaMART wrong category ("zzqq nonsense") → clear "no category page named …" message. | PASS |
| DX05 | TradeIndia: "bakery products", all India → **28 listings**; 26 rows show the phone as "Hidden". | PASS |
| DX06 | ExportersIndia: "bakery products", Ahmedabad → **32 listings**. | PASS |
| DX07 | MLMDiary: Gujarat → **80 MLM companies**, with member counts and cities; privacy note shown. | PASS |
| DX08 | Deep Search on 2 rows finished (0 found — DuckDuckGo only). Save 2 → 2 new leads, source `Indian Directories (IndiaMART)`, **phone saved** (`+91 80476 25603`), and the IndiaMART link is never the website. | PASS |
| DX09 | CSV columns (incl. `phone_ext`); mobile at 390 px, no sideways scroll. | PASS |
| DX10 | No console errors. | PASS |

### 4. Bugs found and fixed
1. **IndiaMART phone with an extension.** `8047625603,5093` became a 14-digit number. It is now split into the number and the extension.
2. **Phone not saved to leads.** The lead mapping used the key `phone`, but the registry reads `mobile_number`. Fixed; a test now checks the saved file.
3. **`normalize_phone` dropped trunk-0 numbers.** Numbers such as `09533376923` (Sulekha) and `08047763186` (IndiaMART) were silently removed. This was a shared bug that affected every source; they are now kept as `+91 …`.
4. **TradeIndia unknown category.** It redirects to a generic page with HTTP 200, which would have been cached as the category page. The new `html_cache_manager.fetch_page` reports the final URL and never caches a redirected page.

### 5. UNVERIFIED
| Item | Why |
|---|---|
| Deep Search finding websites for directory companies | It needs a search engine. DuckDuckGo found nothing today; SearXNG / a key would help. |

### 6. Data safety
- `all_leads_master.csv` was restored after QA (md5 `963d94bc…` matches).
- SMTP, IMAP and Supabase were off during QA.

## ગુજરાતી
- **Live tests:** 10/10 pass. Sulekha 20, IndiaMART 28, TradeIndia 28, ExportersIndia 32 અને MLMDiary 80 companies મળી.
- **Justdial:** ઉપલબ્ધ નથી, કારણ કે site apps ને ખાલી page આપે છે. એનું page Sulekha અને IndiaMART તરફ લઈ જાય છે.
- **4 bugs fix થયા.** સૌથી મહત્ત્વનો: `0` થી શરૂ થતા phone numbers (જેમ કે `09533376923`) leads માં save નહોતા થતા. આ બધા sources ને અસર કરતું હતું, હવે સુધરી ગયું છે.
- **Tests:** unit 404/404 pass.

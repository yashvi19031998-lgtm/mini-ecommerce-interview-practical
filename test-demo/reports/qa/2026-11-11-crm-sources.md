# QA Report — CRM Sources

**Date:** 2026-11-11 · **Build:** uncommitted working tree on `master` · **Result:** PASSED for directory sources. Contact databases are UNVERIFIED (no API keys).

---

## English

### 1. Automated tests (Python, no network)
| Suite | Result |
|---|---|
| `test_crm_sources.py` (new) | 20/20 pass |
| Full regression (13 suites) | **198/198 pass** |

### 2. API checks (real Flask backend) — 3/3 pass
| ID | Test | Result |
|---|---|---|
| API01 | `GET /api/crm-sources`: 17 sources (available / needs_key / unavailable), 37 states | PASS |
| API02 | Bad input → HTTP 400: no keywords, no state, bad city, unknown source, keyword > 80 chars, unknown state, empty save | PASS |
| API03 | Needs-key source (Apollo, no key) → returns cleanly with an "add key" message, no crash | PASS |

### 3. End-to-end UI test (Playwright, real browser, live sites) — 15/15 pass
| ID | Test | Result |
|---|---|---|
| TC01 | Sidebar order: Dashboard, Job Portal Scraper, FollowUp History, CRM Sources | PASS |
| TC02 | Page loads; 37 state options | PASS |
| TC03 | Empty form → 3 field errors | PASS |
| TC04 | Keyword/title chips: Enter/comma, case-insensitive duplicate ignored, > 80 chars rejected, remove | PASS |
| TC05 | City with a digit rejected; error clears on edit | PASS |
| TC06 | Source menu: 3 enabled, 14 disabled with reasons, 3 groups | PASS |
| TC07 | Select a single source (GoodFirms) | PASS |
| TC08 | Live search "software", Gujarat / Ahmedabad, GoodFirms → 48 results | PASS |
| TC09 | Result filter, plus a "no match" message | PASS |
| TC10 | Export CSV → 48 rows | PASS |
| TC11 | Save 2 results → 2 new leads, source `CRM Source (GoodFirms)` | PASS |
| TC12 | Save the same 2 again → "0 new leads, 2 already saved"; master CSV unchanged | PASS |
| TC13 | Search all 3 available sources → a chip per source, partial failure shown | PASS |
| TC14 | Mobile 390 px: no horizontal scroll | PASS |
| TC15 | No browser console errors | PASS |

Screenshots: `crm01_form.png` … `crm07_mobile.png`, in the session scratchpad `qa/` folder.

### 4. Bug found and fixed during QA
- **Bug:** a search running longer than 30 s failed in the browser with HTTP 500. The Next.js proxy cut the request off ("socket hang up"). This also affected Job Portal Scraper searches that run 30–60 s.
- **Fix:** set `experimental.proxyTimeout: 120000` in `frontend/next.config.mjs`.
- **Retest:** TC13 and TC15 now pass.

### 5. Live source status on the test day
| Source | Result |
|---|---|
| GoodFirms | 48 results — works |
| OpenStreetMap | `failed`: the public Overpass server returned HTTP 502. Mirror servers did not respond either. External outage → **UNVERIFIED** |
| Zaubacorp | 0 results for "software". Expected, because it matches the name of only the ~90 newest companies. Works, but its value is low for broad keywords. |
| Apollo, Hunter, Google Places, Snov, Lusha, RocketReach | **UNVERIFIED**: no API keys yet. Parsers are covered only by unit tests with mocked responses. |

### 6. Data safety
- `all_leads_master.csv` was backed up before QA and restored afterwards (md5 `e015f6f7…` matches).
- SMTP and IMAP were disabled during QA, so no emails were sent.

### 7. Open items
1. Add the API keys, then re-test each contact database (it uses credits).
2. Re-test OpenStreetMap when Overpass is back up.

---

## ગુજરાતી

### સારાંશ
- **Unit tests:** 20/20 નવા tests pass, પૂરું regression 198/198 pass.
- **API checks:** 3/3 pass. ખોટા input પર 400 આવે છે, અને key વગરનો source crash થતો નથી.
- **Browser test:** 15/15 pass. Form, validation, chips, live GoodFirms search (48 results), filter, CSV, Save to Leads અને duplicate check (ફરી save કરતાં નવી lead બનતી નથી) બધું ચકાસ્યું. Mobile માં પણ બરાબર દેખાય છે.

### QA માં મળેલો bug (fix થઈ ગયો)
- **Bug:** 30 સેકન્ડથી લાંબો search browser માં 500 error આપતો હતો, કારણ કે Next.js proxy વચ્ચેથી request કાપી નાખતું હતું. Job Portal Scraper ને પણ આ જ bug અસર કરતો હતો.
- **Fix:** `next.config.mjs` માં timeout 120 સેકન્ડ કર્યો. ફરી test કરતાં pass થયું.

### UNVERIFIED (હજુ ચકાસાયું નથી)
- **OpenStreetMap:** test વખતે તેનું public server બંધ હતું (HTTP 502).
- **Apollo, Hunter, Google Places, Snov, Lusha, RocketReach:** API keys નથી. Keys ઉમેર્યા પછી ફરી test કરવું પડશે.

### Data સુરક્ષા
- Leads CSV નો QA પહેલાં backup લીધો હતો અને QA પછી restore કર્યો.
- QA દરમિયાન email મોકલવાનું બંધ હતું.

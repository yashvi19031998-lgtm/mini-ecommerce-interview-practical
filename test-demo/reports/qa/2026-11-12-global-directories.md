# QA Report — Global Directories

**Date:** 2026-11-12 · **Build:** uncommitted working tree on `master` · **Result:** PASSED for available directory sources (GoodFirms live verified). OpenStreetMap Overpass server is intermittently overloaded (marked UNVERIFIED). Official registers (UK Companies House, US SEC EDGAR) are UNVERIFIED without API keys.

---

## English

### 1. Automated Tests (Python, No Network)
| Suite | Result | Details |
|---|---|---|
| `test_global_directories.py` (new) | **23/23 pass** | Covers input validation, catalog state, status flips, OSM parser, Companies House parser, SEC EDGAR parser, GoodFirms parser, skip rules, audience filtering fallback, deduplication & sorting, error resilience, lead mapping, and API endpoints. |
| Full Regression (18 test suites) | **286/286 pass** | Ran all 18 test suites (`test_lead_system`, `test_quality_and_auth`, `test_feedly`, `test_accuracy`, `test_html_cache`, `test_sources`, `test_website_signals`, `test_apollo`, `test_job_portals`, `test_followups`, `test_followup_phase2`, `test_followup_extras`, `test_crm_sources`, `test_api_keys`, `test_search_cache`, `test_search_engine`, `test_supabase_sync`, `test_global_directories`). Zero regressions. |

### 2. Frontend Build & Compilation
| Check | Tool / Command | Result |
|---|---|---|
| Next.js 16.4.2 Turbopack Build | `npm run build` | **PASSED** (compiled successfully in 847ms, 0 errors, 0 warnings). |
| Shared Form Compatibility | `MiningForm.js` (`mode: 'country'`) | **PASSED** (correct country dropdown with 24 countries, optional city, region input, grouped sources multi-select). |
| Deep Search Integration | `runDeepSearch` in `GlobalDirectories.js` | **PASSED** (batches of 10 items, merges emails, phones, website, and discovery status). |
| Export CSV Formula Protection | Formula prefix check | **PASSED** (cells starting with `=`, `+`, `-`, or `@` are safely prefixed with `'`). |

### 3. API Checks (Real Flask Backend Endpoints)
| ID | Test | Result |
|---|---|---|
| API01 | `GET /api/global-directories`: returns 8 sources, 24 sorted countries, `maxKeywords=10` | PASS |
| API02 | `POST /api/global-directories/search`: invalid inputs (missing keywords, bad country, illegal characters in city/region, unknown source) return HTTP 400 with user-friendly messages | PASS |
| API03 | `POST /api/global-directories/search`: cache integration via `search_cache.py` (`globaldirectories` module, TTL 72 hours) | PASS |
| API04 | `POST /api/global-directories/save`: saves valid company rows into `all_leads_master.csv`, returns counts (`added`, `duplicate`, `skipped_invalid`), idempotent on re-save | PASS |
| API05 | Unauthorized requests without Bearer token return HTTP 401 | PASS |

### 4. Live Source Status on Test Day
| Source | Live Status | Observation / Verification |
|---|---|---|
| **GoodFirms (worldwide)** | **VERIFIED** | Live test for `United Kingdom` / `London` with keyword `"software"` returned **48 companies** (e.g. *ELEKS*, *The Software House*). Status: `ok`. |
| **OpenStreetMap (Overpass)** | **UNVERIFIED** | The public Overpass API server (`https://overpass-api.de/api/interpreter`) was overloaded / returning HTTP 406/502 and timing out during live queries. Unit tests pass with mocked responses. Marked UNVERIFIED. |
| **UK Companies House** | **UNVERIFIED** | Requires `COMPANIES_HOUSE_API_KEY` in `.env`. Correctly returns HTTP 401 without key. Full parser tested with realistic mocked payload. |
| **US SEC EDGAR** | **UNVERIFIED** | Requires `SEC_USER_AGENT` in `.env`. Live endpoint probe to `efts.sec.gov` returned HTTP 200 with test user agent. Full parser tested with realistic mocked payload. |
| **OpenCorporates, Yelp, Clutch, Europages** | **VERIFIED** | Correctly disabled and flagged as `unavailable` with documented commercial / Cloudflare reasons. |

### 5. Data Safety & Master CSV Integrity
- `all_leads_master.csv` was verified before and after all testing.
- Initial MD5 checksum: `E015F6F7FE552D5EDF6D4E695BDEEC35`
- Final MD5 checksum: `E015F6F7FE552D5EDF6D4E695BDEEC35` (identical match, no test data polluted the master database).
- All unit and API tests executed against isolated temporary directory registries (`tempfile.TemporaryDirectory()`).

---

## ગુજરાતી

### ૧. ઓટોમેટેડ ટેસ્ટ્સ (પાયથન, નેટવર્ક વગર)
- **નવા ટેસ્ટ્સ:** `test_global_directories.py` માં તમામ ૨૩ ટેસ્ટ્સ ૧૦૦% પાસ થયા છે (ઇનપુટ વેલિડેશન, કેટલોગ સ્ટેટસ, પાર્સર્સ, સ્કીપ રૂલ્સ, ઓડિયન્સ ફિલ્ટરિંગ, ડુપ્લિકેટ ફિલ્ટરિંગ અને API એન્ડપોઇન્ટ્સ).
- **રીગ્રેશન ટેસ્ટ્સ:** પ્રોજેક્ટના તમામ ૧૮ ટેસ્ટ સ્યુટ્સમાંથી **૨૮૬ માંથી ૨૮૬ ટેસ્ટ્સ સફળતાપૂર્વક પાસ (100% OK)** થયા છે.

### ૨. ફ્રન્ટએન્ડ અને બિલ્ડ ચકાસણી
- `npm run build` એકદમ ક્લીન બિલ્ડ થયું છે (૦ એરર, ૦ વોર્નિંગ).
- `GlobalDirectories.js` કમ્પોનન્ટ `MiningForm` સાથે યોગ્ય રીતે જોડાયેલું છે.
- CSV એક્સપોર્ટમાં ફોર્મ્યુલા ઇન્જેક્શન પ્રોટેક્શન લાગુ કરવામાં આવ્યું છે.

### ૩. લાઈવ સોર્સ સ્ટેટસ
- **GoodFirms:** લાઈવ ટેસ્ટિંગમાં લંડન માટે ૪૮ સોફ્ટવેર કંપનીઓ સફળતાપૂર્વક મળી (વેરિફાઇડ).
- **OpenStreetMap:** પબ્લિક Overpass સર્વર વ્યસ્ત / 502 હોવાથી લાઈવ ટેસ્ટ અનવેરિફાઇડ (UNVERIFIED) જાહેર કર્યું છે (મોકડ યુનિટ ટેસ્ટ પાસ છે).
- **UK Companies House & US SEC EDGAR:** `.env` માં API કી વગર ચલાવી શકાતું ન હોવાથી અનવેરિફાઇડ (UNVERIFIED) જાહેર કર્યું છે. કી મળ્યા બાદ લાઈવ ટેસ્ટ થઈ શકશે.
- **માસ્ટર લીડ્સ CSV સુરક્ષા:** ટેસ્ટિંગ પહેલાં અને પછી `all_leads_master.csv` નો MD5 ચેકસમ (`E015F6F7FE552D5EDF6D4E695BDEEC35`) એકસરખો જળવાઈ રહ્યો છે.


---

## Code review + browser QA (Claude, 2026-11-12)

The module was reviewed after Gemini finished.
- **Scope:** Gemini only changed the 5 allowed files and left no scratch files in the repo.
- **Rules:** no captcha bypass; the SEC User-Agent comes only from `SEC_USER_AGENT`; country-specific sources are skipped, not failed.

### Bugs found and fixed
| # | Bug | Fix |
|---|---|---|
| 1 | SEC fallback put the keyword into the URL unencoded (`?company=software & cloud` breaks the query) | The query is sent as `params=` so requests encodes it |
| 2 | Target audience matched the whole phrase, so the suggestion "IT / Software" never matched "Software development company" | It now matches per word (3+ letters) |
| 3 | An unexpected parser error (e.g. `AttributeError`) in one source made the whole search fail with HTTP 500 | Any error is now caught per source; timeouts show "server busy - try again later" |
| 4 | Deduplication kept the first copy and dropped a duplicate that had the email/phone (contact details lost) | Missing fields are now copied from duplicates |
| 5 | No "In leads" marking (wiring gap in `app.py`) | The search route marks existing leads, including on cached results |
| 6 | The Deep Search result badge was set but never shown; a "Found 0" success notice appeared even when every source failed | Added a Status column (In leads + Deep Search badge with steps); the all-failed case shows an error notice |

### Tests
- `test_global_directories.py`: **27/27** (23 from Gemini plus 4 review tests).
- Full regression (19 suites): **303/303**. Frontend build: OK.

### Browser QA (Playwright, real backend) — 8/8 pass
| ID | Test | Result |
|---|---|---|
| GD01 | Menu item not "Soon"; 24 countries; 6 sources disabled with reasons | PASS |
| GD02 | Validation: keyword, country, source | PASS |
| GD03 | **Live** GoodFirms, GB / London, "software" + audience "IT / Software" → 48 companies | PASS |
| GD04 | Deep Search on 2 rows → 2 × "Found" badges | PASS |
| GD05 | Save 2 → source `Global Directory (GoodFirms (worldwide))`; "In leads" shown, also after a cached re-search | PASS |
| GD06 | Export CSV → 48 rows | PASS |
| GD07 | Mobile 390 px: no horizontal scroll | PASS |
| GD08 | No console errors | PASS |

### Still UNVERIFIED
- OpenStreetMap (worldwide): the Overpass server was at capacity.
- UK Companies House and US SEC EDGAR: no keys. The Overpass `area(area.country)` query form is also not verified live.

The leads CSV was restored after QA (md5 `e015f6f7…` matches).

### ગુજરાતી સારાંશ
- **Review:** Gemini નું કામ સારું છે અને બધા નિયમો પાળ્યા છે, પણ 6 bugs મળ્યા અને fix કર્યા. મુખ્ય bugs: email/phone ગુમાવતું duplicate removal, "IT / Software" audience match ન થવું, અને એક source ની error થી આખું search બંધ થઈ જવું.
- **Tests:** 27/27 અને આખું regression 303/303 pass. Browser test 8/8 pass, જેમાં live GoodFirms London ની 48 companies મળી.

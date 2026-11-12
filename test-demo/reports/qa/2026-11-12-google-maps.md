# QA Report — Scraping / Mining → Google Maps

**Date:** 2026-11-12 · **Build:** uncommitted working tree on `master` · **Result:** PASSED, with the UNVERIFIED items listed in section 4.

## English

### 1. Automated tests (Python, no network)
| Suite | Result |
|---|---|
| `test_maps_sources.py` (new) | 13/13 pass |
| Full regression (18 suites) | **276/276 pass** |

**What the new tests cover:**
- source statuses follow the keys
- every validation rule
- the website filter with hidden counts
- the min-rating filter (Places only)
- dedupe across sources by phone, and result order
- the audience filter and its fallback
- one source timing out while the other still returns
- Places parsing: paging, closed businesses skipped, rating / reviews / no_website, a rejected key
- the lead mapping
- the API: login required, 400 on bad input, cache hit, "in leads" field, save, no duplicates

### 2. Live checks
- **OpenStreetMap** (Ahmedabad, "restaurant" / "hospital"): **no answer**. The Overpass server said *"currently at capacity, all query workers are busy"*, and even a tiny query took 38 s. The page shows *"OpenStreetMap did not answer in time (server busy) - try again later"*, with no crash.
- **Deep Search** on the 2 real company websites in the seeded rows (prakashinfotech.com, agileinfoways.com): **2/2 Found**.

### 3. End-to-end UI test (Playwright, real browser and backend) — 9/9 pass
| ID | Test | Result |
|---|---|---|
| GM01 | Menu item no longer "Soon" (6 left); Places key hint shown; OpenStreetMap preselected | PASS |
| GM02 | Validation errors; website filter options | PASS |
| GM03 | Live OSM search → clear "no source answered" message and the reason under the chip | PASS |
| GM04 | Results table: 4 rows, 2 "No website" badges, "2 without website" count | PASS* |
| GM05 | Deep Search runs only on rows with a website → 2/2 Found | PASS |
| GM06 | Export CSV with the `no_website` column | PASS |
| GM07 | Save 4 → 4 new leads, source `Google Maps (OpenStreetMap)`, 2 with the "No website" note; save again → 0 new | PASS |
| GM08 | Mobile 390 px: no horizontal scroll | PASS |
| GM09 | No console errors | PASS |

\* GM04 to GM07 used 4 seeded results (2 real company websites + 2 sample businesses without a website) through the search cache, because OSM was down. Everything after the search ran for real.

### 4. UNVERIFIED
| Item | Why | How to verify |
|---|---|---|
| Live OpenStreetMap results | The Overpass server was at capacity during QA | Search Ahmedabad "hospital" again later |
| Google Places API | No `GOOGLE_PLACES_API_KEY` | Add the key, then search with a min rating and "Without website" |

### 5. Fixes made during QA
1. **Raw timeout text:** "ReadTimeout: HTTPSConnectionPool…" is replaced with a plain message.
2. **"Found 0" when every source failed:** the page now shows a clear error notice instead.
3. **Shared form, single source:** the source picker said "All available sources (1)". It now shows the source name. This affects every page that uses `MiningForm`.

### 6. Data safety
- `all_leads_master.csv` was restored after QA (md5 `e015f6f7…` matches).
- SMTP, IMAP and Supabase were off during QA.
- The QA search cache was deleted.

## ગુજરાતી
- **Tests:** unit tests 13/13 (નવા), આખું regression 276/276. Browser test 9/9 pass.
- **"Without website" filter:** બરાબર ચાલે છે. Deep Search ફક્ત website વાળી rows પર ચાલે છે અને 2/2 માં email/phone મળ્યાં.
- **OpenStreetMap:** આજે તેનું server busy હતું ("at capacity"). App crash નથી થતી, સાફ message બતાવે છે. Live result **UNVERIFIED** છે.
- **Google Places:** key નથી, એટલે **UNVERIFIED** છે.

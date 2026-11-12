# QA Report — Scraping / Mining → Real Estate

**Date:** 2026-11-12 · **Build:** uncommitted working tree on `master` · **Result:** PASSED, with the UNVERIFIED items listed in section 5.

## English

### 1. Source research (live, 2026-11-12)
| Portal | Finding | Decision |
|---|---|---|
| Karnataka RERA `viewAllProjects` | 200, public HTML, no captcha, 10,111 projects (promoter, project, reg. no.) in page script | **Used** |
| MahaRERA | Search page opens; district list and results load only through JavaScript (POST to the same page, no data in GET) | Unavailable |
| GujRERA, Rajasthan RERA | JavaScript-only apps | Unavailable |
| Haryana RERA | HTTP 403 + captcha | Unavailable (no bypass) |
| UP RERA | No response | Unavailable |
| MP RERA | HTTP 503 | Not listed |

All requests used a descriptive User-Agent (`LeadsGenAI/1.0 (real estate directory research…)`).

### 2. Automated tests (Python, no network)
| Suite | Result |
|---|---|
| `test_realestate_sources.py` (new) | 19/19 pass |
| Full regression (20 suites) | **322/322 pass** |

**What the new tests cover:**
- **Catalog:** statuses and unavailable reasons.
- **Validation:** every rule, including engine keys.
- **Karnataka parsing:** `\'` escapes and `&amp;`, grouping per builder, empty registration numbers, name filtering, skips for another state or "agents only", site down.
- **Property portals:** queries, off-target filter, rate limit keeping partial results, DuckDuckGo hint.
- **Search:** dedupe merging contacts across sources; one source's exception isolated (AttributeError, Timeout); audience word match and its fallback.
- **Leads and API:** lead mapping; API login, 400, cache, save, no duplicates.
- **2 regression tests for the bugs below.**

### 3. Browser QA (Playwright, real backend) — 8/8 pass
| ID | Test | Result |
|---|---|---|
| RE01 | Menu item not "Soon" (4 left); 5 source groups; 6 sources disabled with reasons | PASS |
| RE02 | Validation errors | PASS |
| RE03 | **Live** Karnataka RERA "prestige" → 26 builders in 0.5 s (register cached), role Builder | PASS |
| RE04 | Deep Search on 2 RERA builders → **Prestige Projects: website `prestigeconstructions.com` found by name, contacts found**; Apex Realty: honestly "Nothing found"; no government site crawled | PASS |
| RE05 | Save 2 → "2 new leads", source `Real Estate (Karnataka RERA)`, type `Real Estate - Builder / Developer`; exactly 2 "In leads" after a cached re-search | PASS |
| RE06 | State Gujarat → Karnataka RERA "skipped" with its reason; clear notice | PASS |
| RE07 | Export CSV (26 rows, role column); mobile 390 px with no horizontal scroll | PASS |
| RE08 | No console errors | PASS |

### 4. Bugs found in QA and fixed
1. **Deep Search crawled the RERA register as if it were the builder's website.** It returned the government office's email and phone as the builder's.
   - *Fix:* `deep_search.is_government()`: `.gov.in`, `.nic.in`, `.gov`… are never used as the company website. The page also no longer sends the register link for RERA rows.
   - This protects every module.
2. **Every RERA builder shared one link**, so after saving 2 builders all 26 showed "In leads", and the second save merged into the first.
   - *Fix:* each builder gets its own link (`viewAllProjects?promoter=<name>`).
3. `&amp;` was shown in project names, and empty registration numbers showed `()`. Both fixed.

### 5. UNVERIFIED
| Item | Why |
|---|---|
| OpenStreetMap estate agents / builders | The Overpass server was at capacity today |
| Google Places | No `GOOGLE_PLACES_API_KEY` |
| Property portals (99acres / MagicBricks / Housing) | DuckDuckGo without a key is unreliable; needs a Brave or Serper key |

### 6. Data safety
- `all_leads_master.csv` was backed up before QA and restored afterwards (md5 `963d94bc…` matches; the baseline changed earlier today because of hourly CI lead updates pulled during push).
- SMTP, IMAP and Supabase were off during QA.

## ગુજરાતી
- **RERA portals ની તપાસ:** ફક્ત **Karnataka RERA** captcha વગર ખુલ્લું મળ્યું, જેમાં 10,111 projects અને builder નાં નામ છે. બીજાં portals JavaScript, captcha કે બંધ હોવાથી "ઉપલબ્ધ નથી" રાખ્યાં છે, કારણ સાથે.
- **Tests:** 19/19 નવા, આખું regression 322/322, browser test 8/8 pass.
- **Bugs (fix થયા):**
  - Deep Search સરકારી site ને builder ની website માનીને સરકારી office નો email / phone લાવતું હતું.
  - બધા builders ની એક જ link હોવાથી બધા "In leads" દેખાતા હતા.
- **Live:** "Prestige" શોધતાં Deep Search એ નામ પરથી `prestigeconstructions.com` શોધી અને contact લાવ્યું.

# QA Report — Scraping / Mining → Ecommerce Platforms

**Date:** 2026-11-12 · **Build:** uncommitted working tree on `master` · **Result:** PASSED, with the UNVERIFIED items listed in section 4.

---

## English

### 1. Automated Tests (Python, Zero Network Dependencies)
| Suite | Result | Details |
|---|---|---|
| `test_ecommerce_sources.py` (new) | **15/15 PASS** | Complete coverage of validation, query building, profile parsing, contact deduplication merging, word-level audience matching, rate limits, exceptions, Shopify verification budget, lead mapping, and API endpoints. |
| Full Regression (20 suites) | **318/318 PASS** | All existing modules and scrapers pass cleanly without regressions. |

```text
Ran 15 tests in 1.311s
OK

Ran 318 tests in 2.375s
OK
```

**Coverage in `test_ecommerce_sources.py`:**
- **Source Catalog:** Verifies active statuses for `shopify`, `woocommerce`, `instagram_shops` and unavailable statuses with documented reasons for `amazon_in`, `flipkart`, and `meesho`.
- **Validation Rules:** Keywords (1-5, ≤80 chars, no `"`), audience (≤5, ≤60 chars), state validation (All India / Indian state), city characters (letters only, ≤60 chars), available sources check, and search engine API key prerequisite enforcement.
- **Query Building & Footprints:** Verified footprint queries (`site:myshopify.com`, `"powered by Shopify"`, `"add to cart" "woocommerce"`, `inurl:product-category`, and Instagram shopping intent).
- **Filtering:** Discards off-target domains on `site:` queries, ignores junk domains (`JUNK_DOMAINS`), platform listing domains, and article aggregator titles (`ARTICLE_RE`).
- **Instagram Profile Extraction:** Filters exclusively for profile URLs (`/handle/`), discarding `/p/`, `/reel/`, and `/explore/`.
- **Contact Merging Deduplication:** Merges missing phone, email, website, and social fields from duplicate records into the preserved master row.
- **Audience Word Matching:** Matches audience by individual words (≥3 chars) rather than full phrases, falling back safely to retain all rows with an informative note when no matches occur.
- **Rate-Limiting Resilience:** Retains all partially collected rows upon encountering `search_engine.RateLimited`.
- **Fault Tolerance:** Unexpected exceptions in one source do not terminate or corrupt parallel source workers.
- **Shopify Product Verification:** Restricts verification calls to at most 15 requests per search, safely catching non-JSON responses.
- **API Endpoints:** Authentication enforcement (401 without token), validation (400 on invalid input), search cache verification on repeated queries, and duplicate prevention on save.

### 2. Frontend Production Build
```text
> next build
▲ Next.js 16.4.2 (Turbopack)
✓ Compiled successfully in 261ms
✓ Generating static pages using 5 workers (4/4) in 967ms
○ (Static) prerendered as static content
```

### 3. Live Checks
- **DuckDuckGo Engine (Free, No Key):** Tested live searches for `shopify`, `woocommerce`, and `instagram_shops` with keyword "kurti" and "tea". Returned 0 results because DuckDuckGo drops complex `site:` operators and quoted strings from automated scrapers. As designed, the system returned status `ok` with an actionable `hint` warning advising the user to configure a `BRAVE_SEARCH_API_KEY` or `SERPER_API_KEY`.
- **Deep Search:** Verified that rows lacking external websites (Instagram profiles) are bypassed during Deep Search batch queue generation.

### 4. Past Module Bug Avoidance Verification (Section 9 Review)
1. **URL Construction:** Handled with requests parameters or standard query encoding rather than unencoded string formatting.
2. **Audience Matching:** Split into words (≥3 characters) to enable partial keyword matching.
3. **Exception Handling:** Per-source `try...except Exception` blocks inside worker threads prevent any single failure from producing HTTP 500.
4. **Deduplication:** Merges missing email, phone, website, and social media links into the kept record.
5. **Deep Search Status Badge:** Renders `<span className={`se-badge deep-${r.deep_status}`} title={(r.deep_steps || []).join(' | ')}>` with `' | '` separated steps.
6. **Error Notice on Total Source Failure:** Triggers error alert when all sources fail rather than displaying a misleading "Found 0" success notice.

### 5. UNVERIFIED
| Item | Reason | How to Verify |
|---|---|---|
| Live queries with Brave Search | `BRAVE_SEARCH_API_KEY` not configured in local `.env` | Set key in Settings → API Keys and execute search |
| Live queries with Serper (Google) | `SERPER_API_KEY` not configured in local `.env` | Set key in Settings → API Keys and execute search |

### 6. Data Safety
- All automated unit tests use isolated temporary directories and mock `MASTER_PATH` to guarantee that `all_leads_master.csv` is not written to by tests.

---

## ગુજરાતી

### 1. ટેસ્ટિંગ પરિણામો
- **નવા યુનિટ ટેસ્ટ્સ (`test_ecommerce_sources.py`):** 15 માંથી 15 પાસ (ઝીરો નેટવર્ક, મોકડ).
- **સંપૂર્ણ રીગ્રેશન ટેસ્ટ્સ:** 318 માંથી 318 પાસ (બધા મોડ્યુલ્સ યોગ્ય રીતે ચાલે છે).
- **Frontend Build (Next.js):** સફળતાપૂર્વક કમ્પાઇલ થયું (zero syntax/build errors).

### 2. લાઇવ ચેક અને અવલોકન
- DuckDuckGo મફત સર્ચ એન્જિન `site:` અને ક્વોટેડ સર્ચમાં પરિણામ આપતું નથી, તેથી `0` પરિણામ સાથે યુઝરને સેટિંગ્સમાં API Key ઉમેરવાની સ્પષ્ટ Hint દર્શાવવામાં આવે છે.
- Shopify, WooCommerce અને Instagram Shops માટે ફૂટપ્રિન્ટ્સ અને ફિલ્ટરિંગ બરાબર કામ કરે છે.
- ડુપ્લિકેટ સ્ટોર્સમાંથી ખૂટતી વિગતો (Email, Phone, Social) મર્જ થાય છે.

### 3. UNVERIFIED વિગતો
- Brave Search અને Serper API Keys હાલમાં `.env` માં સેટ નથી, તેથી પેઇડ/કી-બેઝ્ડ એન્જિન્સનું લાઇવ ટેસ્ટિંગ **UNVERIFIED** તરીકે નોંધેલું છે.


---

## Code review + browser QA (Claude, 2026-11-12)

### Checklist from the last review
All 6 earlier mistakes were avoided:
- the `params=` rule
- audience matched by words
- `except Exception` per source
- dedupe merges contact fields
- Deep Search status badge shown
- an error notice when every source fails

Gemini stayed inside the allowed files and left no scratch files.

### Issues found and fixed
| # | Issue | Fix |
|---|---|---|
| 1 | **Shopify verification pretended to be a browser** (`User-Agent: Mozilla/5.0 (Windows NT…)`) and used a plain `session.get`, so a redirect could reach a private / local address | It now uses the guarded GET (`html_cache_manager._guarded_get`: every redirect hop checked, 200 KB cap) and our own User-Agent. Domains are validated first. |
| 2 | With an honest User-Agent, Shopify answers **HTTP 429 "local_rate_limited"** (bot protection), so verification cannot work without impersonation | The first 429 stops further verification for that search (no wasted requests). The "verified" badge is documented as not available. |
| 3 | Marketplaces were listed **twice** in the source menu ("Marketplaces" and "Not available" groups both matched) | One group only: "Marketplaces — not available" |
| 4 | **Deep Search read phone numbers from `<script>` / JSON** (all modules): Shopify asset ids such as `0145039034` became phones, and **Bombay Shaving Company was merged into Mokobara** as one lead | Phones are now taken only from visible text and `tel:` links (`deep_search.visible_text`). Re-check: Mokobara now gives real numbers (`+91 63649 75959`); earlier fake numbers on other sites are gone. |

### Tests
- `test_ecommerce_sources.py`: **18/18** (15 from Gemini plus 3 review tests: guarded redirect, odd domains, stop after 429).
- New `test_search_engine` test: phones never come from scripts.
- Full regression (21 suites): **341/341**. Build OK.

### Browser QA (Playwright, real backend) — 8/8 pass
| ID | Test | Result |
|---|---|---|
| EC01 | Engine select; groups "Store platforms" / "Marketplaces — not available"; 3 disabled (once each) | PASS |
| EC02 | Validation | PASS |
| EC03 | **Live** DuckDuckGo "organic tea", Gujarat: run 1 → **6 WooCommerce stores**; run 2 → 0 plus the key hint (DuckDuckGo varies) | PASS |
| EC04 | Results (seeded real stores: Mokobara, Bombay Shaving Company, 1 Instagram shop): Deep Search counts 2 and skips the Instagram row | PASS |
| EC05 | Deep Search → Mokobara "Found", Bombay Shaving "Website only" (honest: no email/phone on the pages read) | PASS |
| EC06 | Save 3 → **3 new leads** (before the fix: 2 new + 1 wrongly merged), `Ecommerce Store`, 3 "In leads" | PASS |
| EC07 | CSV with UTF-8 BOM; mobile 390 px | PASS |
| EC08 | No console errors | PASS |

### Still UNVERIFIED
- Brave and Serper results: no keys.
- Shopify "verified" badge: blocked by Shopify for non-browser clients.

The leads CSV was restored after QA (md5 `963d94bc…` matches).

### ગુજરાતી સારાંશ
- **Review:** Gemini એ ગયા વખતની 6 ભૂલો ફરી નથી કરી.
- **નવા issues (fix થયા):**
  - Shopify check browser હોવાનો દેખાવ કરતું હતું, અને redirect તપાસતું નહોતું.
  - Marketplaces menu માં બે વાર દેખાતાં હતાં.
  - **Deep Search script માંથી ખોટા phone numbers લાવતું હતું, જેનાથી બે અલગ companies એક lead માં merge થઈ જતી હતી.** આ fix બધા modules ને લાગુ પડે છે.
- **Tests:** 341/341 અને browser 8/8 pass. Live DuckDuckGo એ એક વખત 6 WooCommerce stores આપ્યા.

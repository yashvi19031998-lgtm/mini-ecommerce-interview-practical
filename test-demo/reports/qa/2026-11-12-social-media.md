# QA Report — Scraping / Mining → Social Media

**Date:** 2026-11-12 · **Build:** uncommitted working tree on `master` · **Result:** PASSED, with the UNVERIFIED items listed in section 5.

## English

### 1. Automated tests (Python, no network)
| Suite | Result |
|---|---|
| `test_social_sources.py` (new) | 11/11 |
| Full regression (24 suites) | **374/374** |

**What the new tests cover:**
- every validation rule
- URL filters for all 5 networks, good and bad URLs (incl. LinkedIn `/in/` dropped)
- field extraction: name cleaning, followers, website (shorteners / social links rejected)
- the privacy filter, with its skipped count
- dedupe that merges website / followers, and ordering
- off-target filtering; audience by words, with its fallback
- a rate limit in the middle of a keyword keeps partial results
- per-source error isolation; the DuckDuckGo hint
- **no HTTP request is made to social sites** (`requests` and the guarded GET are patched to fail)
- lead mapping; API: 401 / 400 / cache / save / no duplicates

### 2. Browser QA (Playwright, real backend) — 6/6 pass
| ID | Test | Result |
|---|---|---|
| SM01 | Menu: **0 "Soon" left** (all 9 Scraping / Mining submenus live); 6 sources each listed once; privacy note; validation | PASS |
| SM02 | **Live** DuckDuckGo "bakery", Ahmedabad → 0 on all 5 networks, the key hint is shown (DuckDuckGo ignores `site:` today) | PASS |
| SM03 | Results (seeded: 1 real brand with a website + 2 sample pages); Network filter (LinkedIn → 1); Deep Search counts only rows with a website; "2 personal-looking profile(s) skipped" note | PASS |
| SM04 | Deep Search + Save 3 → 3 new leads; **social links never stored as the website** (only the real website mokobara.com) | PASS |
| SM05 | CSV columns; mobile 390 px | PASS |
| SM06 | No console errors | PASS |

### 3. Bugs found and fixed
1. **Partial results lost on a rate limit.** If the 2nd query of a keyword hit a rate limit, the 1st query's results were thrown away. The results found so far are now kept and the remaining keywords are skipped.
2. **The same bug in WhatsApp Groups invite links.** Fixed there too, with a test.

### 4. Design notes
- This module was specified in `gemini-prompt-social-media.md`. The owner then asked Claude to build it, and it follows that brief, including the 10-item "do not repeat" list.

### 5. UNVERIFIED
| Item | Why |
|---|---|
| Live results for all 5 networks | DuckDuckGo returned nothing for `site:` queries today; needs `BRAVE_SEARCH_API_KEY` or `SERPER_API_KEY` |

### 6. Data safety
- `all_leads_master.csv` was restored after QA (md5 `963d94bc…` matches).
- SMTP, IMAP and Supabase were off during QA.

## ગુજરાતી
- **Tests:** 11/11 નવા, આખું regression 374/374 અને browser 6/6 pass. હવે sidebar માં એક પણ "Soon" નથી, એટલે **Scraping / Mining ના બધા 9 modules તૈયાર છે.**
- **Privacy:** ફક્ત business pages રાખવામાં આવે છે. App social sites પર ક્યારેય સીધી request નથી કરતી, અને tests આ તપાસે છે.
- **Bug fix:** rate limit આવે ત્યારે અગાઉ મળેલાં results ગુમ થઈ જતાં હતાં. આ Social Media અને WhatsApp બંનેમાં fix થયું.
- **UNVERIFIED:** live results. Brave કે Serper key ઉમેર્યા પછી ચકાસવું પડશે.

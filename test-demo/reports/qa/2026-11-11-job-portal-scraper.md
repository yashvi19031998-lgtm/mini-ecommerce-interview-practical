# QA Report — Dashboard + Job Portal Scraper

**Date:** 2026-11-11 · **Build:** uncommitted working tree on `master` · **Result:** PASSED (with open items below)

---

## English

### 1. Automated tests (Python, no network)
| Suite | Result |
|---|---|
| `test_job_portals.py` (new) | 30/30 pass |
| Full regression (9 suites) | **109/109 pass** |

Covers: input validation (titles, state, portals), portal catalog statuses, every portal parser, state + relevance filters, de-duplication, Save to Leads (no duplicate leads), API login + 400 errors.

### 2. Live portal check (real requests, "React Developer" + "Python Developer", Gujarat)
- 114 unique jobs in ~7 s: Foundit 38, Internshala 28, Shine 27, LinkedIn 16, Remotive 3, RemoteOK 2, Arbeitnow 1, Instahyre 1, Apna 0, Freshersworld 0.
- Apna / Freshersworld 0 = correct: their results for this search were outside Gujarat / not React or Python jobs.

### 3. End-to-end UI test (Playwright, real browser, real backend) — 17/17 pass
| ID | Test | Result |
|---|---|---|
| TC01 | Sidebar order: 1. Dashboard, 2. Job Portal Scraper | PASS |
| TC02 | Dashboard is the default view | PASS |
| TC03 | Form loads; state list = All India + 36 | PASS |
| TC04 | Empty form → 3 field errors | PASS |
| TC05 | Multiple titles: Enter / comma, duplicate ignored, remove | PASS |
| TC06 | Title > 80 chars rejected | PASS |
| TC07 | Select state; error clears | PASS |
| TC08 | Portal multi-select: select all/none, blocked portals disabled with reason | PASS |
| TC09 | Live search → results + per-portal status | PASS |
| TC10 | All India-portal results are in Gujarat (or Remote) | PASS |
| TC11 | Results filter + empty state | PASS |
| TC12 | Export CSV | PASS |
| TC13 | Save to Leads; saving again → "already saved" | PASS |
| TC14 | Select all rows | PASS |
| TC15 | Saved jobs counted on Dashboard | PASS |
| TC16 | 390 px width: no horizontal scroll; form becomes 1 column | PASS (see open item 2) |
| TC17 | No browser console errors | PASS |

QA data written by TC13 was removed afterwards: `all_leads_master.csv` restored from backup (md5 verified identical).

### 4. Bugs found and fixed during QA
| Bug | Fix |
|---|---|
| Shine ignored the state (Hyderabad jobs in a Gujarat search) | Search state + main city, keep only jobs in the state |
| Fuzzy portal search returned unrelated jobs (.NET, Inside Sales) | Relevance filter on title + skills |
| Shine parser failed if JSON had spaces | Regex-based, tolerant parser |
| Field errors stayed after fixing the field | Errors clear on change |
| "0 jobs" portals shown green | Neutral grey chip |
| Save had no visible confirmation (see open item 1) | Inline success/error message in the page |

### 5. Open items (not fixed — need your decision)
1. **Toasts never appear anywhere in the app.** `app/page.js` renders `<Toast message=… />` per toast, but `Toast.js` expects a `toasts` array → it always renders nothing. Pre-existing; fix touches shared files `page.js`/`Toast.js` + CSS. *Awaiting approval.*
2. **App shell not mobile-responsive.** At 390 px the sidebar stays open and squeezes content. Pre-existing layout issue. *Awaiting approval.*
3. **Security:** a recent commit added an `X-Demo-User` header bypass in `api_auth.py` and a one-click local login. Any request with that header is accepted on localhost without a login. *Recommend review.*
4. Dashboard "Top hot leads" shows non-IT roles (e.g. "Senior Paid Media Manager") at 10/10 — scores in existing data look heuristic, not AI. *Recommend review.*
5. Adzuna / Jooble not tested live (no API keys). Marked **UNVERIFIED** until keys are added.

---

## ગુજરાતી

### 1. Automated tests (Python, internet વગર)
| Suite | પરિણામ |
|---|---|
| `test_job_portals.py` (નવું) | 30/30 pass |
| આખું regression (9 suites) | **109/109 pass** |

ચકાસ્યું: input validation (titles, state, portals), portals ની status, દરેક portal parser, state અને relevance filters, duplicate દૂર કરવા, Save to Leads (duplicate lead નહીં), API login અને 400 errors.

### 2. Live portal check (સાચી requests, "React Developer" + "Python Developer", Gujarat)
- ~7 સેકન્ડમાં 114 અલગ jobs: Foundit 38, Internshala 28, Shine 27, LinkedIn 16, Remotive 3, RemoteOK 2, Arbeitnow 1, Instahyre 1, Apna 0, Freshersworld 0.
- Apna / Freshersworld 0 = સાચું: આ search માટે તેમના results Gujarat બહારના / React-Python સિવાયના હતા.

### 3. End-to-end UI test (Playwright, સાચું browser, સાચું backend) — 17/17 pass
ઉપરના English ટેબલ મુજબ TC01–TC17 બધા PASS. TC13 એ ઉમેરેલો QA data પછી દૂર કર્યો: `all_leads_master.csv` backup થી પાછી મૂકી (md5 સરખો ચકાસ્યો).

### 4. QA દરમ્યાન મળેલા અને સુધારેલા bugs
| Bug | સુધારો |
|---|---|
| Shine state ને અવગણતું (Gujarat search માં Hyderabad jobs) | State + મુખ્ય શહેર search, ફક્ત state ની jobs રાખી |
| Portal search અસંબંધિત jobs આપતું (.NET, Inside Sales) | Title + skills પર relevance filter |
| JSON માં space હોય તો Shine parser fail | Regex-આધારિત મજબૂત parser |
| Field સુધાર્યા પછી પણ error રહેતો | બદલાવ પર error સાફ |
| "0 jobs" portals લીલા દેખાતા | Grey chip |
| Save પછી કોઈ સંદેશ દેખાતો નહીં (open item 1) | Page પર જ success/error સંદેશ |

### 5. બાકી મુદ્દા (સુધાર્યા નથી — તમારો નિર્ણય જોઈએ)
1. **આખી app માં toast message ક્યારેય દેખાતા નથી.** `page.js` અને `Toast.js` વચ્ચે props મેળ ખાતા નથી. જૂનો bug; shared files બદલવી પડે. *Approval ની રાહ.*
2. **App mobile પર responsive નથી.** 390 px પર sidebar ખુલ્લો રહે છે. જૂનો layout પ્રશ્ન. *Approval ની રાહ.*
3. **Security:** તાજેતરના commit એ `api_auth.py` માં `X-Demo-User` header bypass અને one-click local login ઉમેર્યું છે. Localhost પર આ header વાળી request login વગર ચાલે છે. *Review ની ભલામણ.*
4. Dashboard "Top hot leads" માં IT સિવાયની jobs (જેમ કે "Senior Paid Media Manager") ને 10/10 — હાલના data ના scores heuristic લાગે છે. *Review ની ભલામણ.*
5. Adzuna / Jooble live ચકાસ્યા નથી (API keys નથી). Keys ઉમેરાય ત્યાં સુધી **UNVERIFIED**.

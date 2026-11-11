# QA Report — FollowUp History (Phase 1)

**Date:** 2026-11-11 · **Build:** uncommitted working tree on `master` · **Result:** PASSED (open items below)

---

## English

### 1. Automated tests (Python, no network)
| Suite | Result |
|---|---|
| `test_followups.py` (new) | 25/25 pass |
| Full regression (10 suites) | **134/134 pass** |

Covers: activity validation (type, summary, details, future date), follow-up buckets (overdue / today / upcoming / later), one-pending-per-lead, done / cancel / reschedule rules, history filters + paging, import (once, no duplicates, matches any lead email), all API endpoints incl. login (401) and 400/404 errors, automatic logging of status change and sent email, failed email not logged.

### 2. End-to-end UI test (Playwright, real browser, real backend, real data) — 11/11 pass
| ID | Test | Result |
|---|---|---|
| FU01 | Sidebar: 3rd item is FollowUp History | PASS |
| FU02 | Summary cards + empty queue message | PASS |
| FU03 | Import past emails: 234 imported (124 linked, 110 unmatched); 2nd click → 0 new | PASS |
| FU04 | History: 50 per page, Load more, type filter, search | PASS |
| FU05 | Log activity validation: lead, summary, future date, custom follow-up date | PASS |
| FU06 | Log a call + follow-up in 3 days → appears in queue with last contact | PASS |
| FU07 | Timeline drawer: activity, details, pending follow-up; Log activity preselects lead | PASS |
| FU08 | Reschedule +7, bucket filters, mark done → queue empty, counts updated | PASS |
| FU09 | Status change in Leads table logged automatically (`NEW → CONTACTED`) | PASS |
| FU10 | 390 px width: no horizontal page scroll | PASS |
| FU11 | No browser console errors | PASS |

QA data was removed afterwards: `logs/followup_activity.csv` deleted (it did not exist before), `all_leads_master.csv` restored from backup (md5 verified identical).

### 3. Bug found and fixed during QA
| Bug | Fix |
|---|---|
| Timeline header flooded by one lead whose phone field holds hundreds of scraped numbers | Show only the first phone; header limited to 2 lines (regression test added) |

### 4. Open items (need your decision)
1. **110 of 234 past emails match no current lead** (lead deleted or email changed). They stay in history as "Unknown lead".
2. **Data quality:** some scraped leads hold many emails/phones (e.g. one lead got many imported "Email sent" rows). Scraper clean-up recommended.
3. **Privacy:** `logs/followup_activity.csv` stores contact emails and message text. The hourly GitHub Action commits `logs/` to the **public** repo. Recommend making the repo private or excluding this file.
4. Still open from the Job Portal report: global toast bug, mobile app shell, `X-Demo-User` auth bypass.
5. Phase 2 (auto sequence, Gmail reply detection) not built.

---

## ગુજરાતી

### 1. Automated tests (Python, internet વગર)
| Suite | પરિણામ |
|---|---|
| `test_followups.py` (નવું) | 25/25 pass |
| આખું regression (10 suites) | **134/134 pass** |

ચકાસ્યું: activity validation, follow-up buckets, એક lead નો એક જ બાકી follow-up, done / cancel / reschedule, history filters અને paging, import (એક જ વાર, duplicate નહીં), બધા API (login 401, 400/404 errors સાથે), status change અને email નું આપોઆપ log, નિષ્ફળ email log ન થાય.

### 2. End-to-end UI test (Playwright, સાચું browser, સાચો data) — 11/11 pass
ઉપરના English ટેબલ મુજબ FU01–FU11 બધા PASS. QA નો data પછી દૂર કર્યો: `logs/followup_activity.csv` કાઢી નાખી (પહેલાં નહોતી), `all_leads_master.csv` backup થી પાછી મૂકી (md5 સરખો).

### 3. QA દરમ્યાન મળેલો અને સુધારેલો bug
| Bug | સુધારો |
|---|---|
| એક lead ના phone field માં સેંકડો numbers હોવાથી timeline header ભરાઈ જતું | ફક્ત પહેલો phone બતાવ્યો; header 2 લીટી સુધી (regression test ઉમેર્યો) |

### 4. બાકી મુદ્દા (તમારો નિર્ણય જોઈએ)
1. **234 માંથી 110 જૂના emails હાલની કોઈ lead સાથે મેળ ખાતા નથી** (lead કાઢી નાખેલી અથવા email બદલાયેલો). History માં "Unknown lead" તરીકે રહે છે.
2. **Data quality:** કેટલીક scraped leads માં ઘણા emails/phones છે. Scraper સફાઈની ભલામણ.
3. **Privacy:** `logs/followup_activity.csv` માં emails અને message લખાણ છે. Hourly GitHub Action `logs/` ને **public** repo માં commit કરે છે. Repo private કરવાની અથવા આ file ને બાકાત રાખવાની ભલામણ.
4. Job Portal report ના બાકી મુદ્દા: global toast bug, mobile layout, `X-Demo-User` auth bypass.
5. Phase 2 (auto sequence, Gmail reply detection) બનાવ્યું નથી.

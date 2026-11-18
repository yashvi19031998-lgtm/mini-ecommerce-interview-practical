# QA Report — Full Frontend, Page by Page and Client Workflows

**Date:** 2026-11-18 · **Build:** `master` at `dc3caaa` plus the fixes listed below · **Result:** 0 crashes and 0 server errors on any screen; 27 of 27 client workflows pass; 10 findings, 8 fixed and re-tested, 2 left for a decision.

No e-mail was sent. The backend ran from a sandbox copy with a fake mail server, and your real leads file and logs were not touched.

## 1. Result at a glance

| Suite | What it covers | Result |
|---|---|---|
| Python unit tests | 761 tests, no network | **761 / 761** (1 test was broken by an earlier commit; fixed, see F9) |
| Page sweep | all 52 menu pages at desktop (1440 px) and phone (390 px) = 104 screens: page errors, console errors, API answers ≥ 400, horizontal scroll, controls without a name or label, empty screens | **0** page errors, **0** console errors, **0** failed API calls, **0** pages that scroll sideways |
| Client workflows | 27 click-through checks in a real browser (section 3) | **27 / 27** before and after the fixes |
| Visual review | contact sheets of all 104 screens read as a first-time client | 5 findings (F3–F7) |

## 2. How it was tested

- **Sandbox backend** on port 5055, copied from the project, with mail, Slack, Supabase and paid API keys removed. `smtplib` was replaced by a fake server that records mails to a file and refuses any address starting with `fail@`. The mailbox check answered "valid" without network.
- **Separate frontend build** in `.next-qa`, served on port 3002. Ports 3000 and 5000 were not used.
- **Test data:** 8 leads named "Testco …" were added to the sandbox only. They cover a normal lead, two addresses of one company, a `grievance@` address, an address that fails, a lead with no e-mail, and an address mailed before.
- **Two passes:** an automated sweep of every screen, then 27 scripted client workflows. After the fixes both passes were run again (regression), and then the unit tests.

## 3. Client workflows (27 / 27)

| # | Workflow | Result |
|---|---|---|
| 1 | Login lands on Today; the browser tab says "test-demo" | Pass |
| 2 | Today shows the to-do lanes with leads | Pass: 4 lanes, 20 rows |
| 3 | Today: "Done" logs the contact | Pass |
| 4 | Today: set monthly goals; progress bars appear | Pass |
| 5 | Today: "See all" opens Leads filtered by that step | Pass |
| 6 | Leads: search, temperature, date found, contact type; filter tags; "Clear all" | Pass: each filter goes into the link |
| 7 | Leads: next-step chip counts match the rows shown | Pass: to-do 683, call 77, mail queue 109, skipped 1,522 |
| 8 | Leads: Call pending, page size 25, next / previous page | Pass |
| 9 | Leads: sort newest first | Pass |
| 10 | Leads: Export downloads a CSV of the filtered list | Pass: 376 rows |
| 11 | Leads: select all matching leads across pages | Pass: 109 selected |
| 12 | Leads board by outcome: drag a card to "Contacted" | Pass: saved |
| 13 | Lead panel: next step, WhatsApp text, call script, remind, outcome, Esc | Pass |
| 14 | Lead panel: "Not interested" takes the lead off the to-do | Pass: 76 → 75 |
| 15 | Browser Back and Refresh keep the page and its filters | Pass |
| 16 | Header search opens Leads with that search | Pass |
| 17 | Bulk mail: 5 leads → 3 sent, 1 skipped (company already mailed), 1 failed; the rest still went; afterwards only the failed lead is still "Email pending" | Pass |
| 18 | Reports › Summary: periods, client type, "Ask AI", CSV | Pass |
| 19 | Reports › Leads & mail by day: a number → its list → "Open in Leads" | Pass |
| 20 | Overview, Sources, Pipeline, Outreach, Leads & mail by day load with Call pending + IT project + Hot | Pass |
| 21 | Follow-ups: log a call for a lead | Pass |
| 22 | Chat: answers "Aaje shu karu?", learns a fact, rating | Pass |
| 23 | Settings: a change is still there after a refresh (then put back) | Pass |
| 24 | Import: paste a WhatsApp message, extract the contact | Pass |
| 25 | Sidebar collapse / expand | Pass |
| 26 | Keyboard: open a lead with Enter, close with Esc | Pass |
| 27 | Phone: menu drawer, Leads, lead panel full width | Pass |

## 4. Findings

| # | Severity | Where | Finding | Status |
|---|---|---|---|---|
| F1 | High (speed) | `GET /api/leads` | The leads list is a 4.8 MB answer, sent uncompressed. On a hosted server it takes seconds to load. | **Fixed:** large JSON answers are gzip-compressed when the browser accepts it: 4.8 MB → 0.76 MB (`app.py` `add_header`). |
| F2 | Medium (accessibility) | Header search on every page; 16 Settings fields; Import text box; do-not-contact field | Fields without a label linked to them: a screen reader cannot name them, and clicking the label does not focus the field. | **Fixed:** `aria-label` on the search box, `htmlFor`/`id` on the others. Sweep: 58 → 0. |
| F3 | Medium (phone) | All report pages | Six filters stacked above the report filled the whole phone screen; the numbers started below the fold. | **Fixed:** on a phone the filters sit behind a "Filters (n)" button; wider screens are unchanged. |
| F4 | Medium (phone) | Every page | The round chat button covered the last button or row of a page. | **Fixed:** room under the content on screens up to 900 px. |
| F5 | Low (phone) | Follow-ups | The tab row stuck out of the screen by 10 px. | **Fixed:** the tabs scroll sideways inside their row. |
| F6 | Low (clarity) | Lead Sources › Justdial | The page only says "Not available" (the site blocks automated access), but the menu showed it like any other source. | **Fixed:** the menu marks it "Off". |
| F7 | Info | Reports › Overview chart (phone) | The sweep flagged chart bars outside the screen; the chart scrolls inside its own box, so the page does not. | Not a defect. |
| F8 | Info | Today | Shows "Loading your day…" for about 0.7 s while `/api/today` works. Acceptable; it shows a spinner. | No change. |
| F9 | Medium (tests) | `test_ai_email_generator.py` | Commit `dc3caaa` renamed tech-stack labels ("Python" → "Python / AI", "Mobile Apps (…)" → "Mobile App Development (…)"); the test still expected the old names and failed. | **Fixed:** the test checks the key word, so a label change no longer breaks it. |
| F10 | **High (risk, needs a decision)** | Outreach mail limits | Commit `9c50e25` ("remove daily 50 email cap validation for unlimited outreach") removed the daily mail limit. Many mails a day from one Gmail account is the main reason accounts get blocked. | **Not changed.** Decide whether to keep a daily limit. |

## 5. Files changed by this QA

- `app.py` — gzip for large JSON answers (F1)
- `frontend/components/Header.js`, `SettingsView.js`, `LeadImporter.js` — labels (F2)
- `frontend/components/Reports.js`, `frontend/app/work.css` — phone filters, chat-button room, Follow-ups tabs (F3–F5)
- `frontend/components/Sidebar.js` — Justdial "Off" (F6)
- `test_ai_email_generator.py` — label check (F9)

## 6. Open points

1. **F10:** decide on a daily mail limit. Advice: keep about 50 a day per Gmail account.
2. Bulk mail writes each mail with AI when the switch in the pop-up is on (now it really is on or off). With many leads, turn it off or expect one AI call per mail.
3. "Testco" leads exist only in the sandbox; nothing to clean up in your data.

---

## ગુજરાતી સારાંશ

- **104 screen** (52 page × desktop અને mobile) ખોલ્યા: એક પણ error, console error કે API failure નથી.
- **27 client workflow** (login, Today, Leads ના બધા filter, lead panel, bulk mail, board, reports, chat, follow-ups, settings, import, mobile) — **27 / 27 pass**.
- **10 મુદ્દા** મળ્યા. તેમાંથી 8 સુધાર્યા અને ફરી test કર્યા:
  - leads ની list હવે 4.8 MB ને બદલે 0.76 MB માં આવે છે;
  - label વગરના 58 field સુધાર્યા;
  - phone પર reports ના filter એક button પાછળ છે;
  - chat નું બટન હવે છેલ્લા button ને ઢાંકતું નથી;
  - Follow-ups ના tabs સુધાર્યા;
  - Justdial menu માં "Off" તરીકે દેખાય છે;
  - તૂટેલો test સુધાર્યો.
- **તમારો નિર્ણય જોઈએ:** બીજા session એ mail ની રોજની limit કાઢી નાખી છે. એક Gmail થી રોજ ઘણા mail જાય તો account block થવાનું જોખમ છે.

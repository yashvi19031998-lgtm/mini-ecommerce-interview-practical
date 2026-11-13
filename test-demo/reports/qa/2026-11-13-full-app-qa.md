# QA Report — Full Application Test, Client-Eye Review and Self-Healing Fixes

**Date:** 2026-11-13 · **Build:** uncommitted working tree on `master` (includes the in-progress Auto Scraper screen) · **Result:** 18 bugs found and fixed over two rounds, and 9 of the 12 suggestions in section 5 done in a third round (section 9). All re-tested.

Nothing is committed. Your real leads file and logs are byte-for-byte unchanged, and no e-mail was sent.

**Round 2 (11:39–11:55)** re-tested everything after the do-not-contact list and other changes were added. It is in section 8; sections 1–7 describe round 1.

## English

### 1. Result at a glance

| Suite | What it covers | Before fixes | After fixes |
|---|---|---|---|
| Python unit tests | 33 → 35 suites, no network | 497 / 497 | **519 / 519** |
| API sweep | 571 calls: every route without login, with a forged token, and with 8 kinds of bad input | 86 crashes or raw HTML error pages | **0** |
| Login guard | 92 route + method pairs without login, plus 1 forged token | 93 / 93 refused | 93 / 93 refused |
| Screen walkthrough | all 43 screens at desktop (1440 px) and phone (390 px), real browser | phone top bar cut off on 42 screens; 5 screens unstyled | **86 / 86 load clean, 0 console errors** |
| Client workflows | 22 click-through tests: login, lead table, pop-ups, settings, auto scraper, tools, sign-out | 11 / 22 | **22 / 22** |

The 519 unit tests are the earlier 497, plus 16 new ones for these fixes (`test_api_safety.py`), plus 6 from `test_auto_scheduler_and_settings.py` (see section 7).

### 2. How it was tested (and kept safe)

- **Sandbox copy.** The backend ran from a temporary copy on port 5055 with mail, Slack, Supabase and paid API keys removed. Every browser request was routed to that copy.
- **Separate build.** The frontend was built into `.next-qa` and served on port 3001. Your `next dev` on port 3000 and backend on port 5000 were never stopped or called.
- **Client-eye pass.** Every screen was screenshotted at both sizes and read as a first-time user would: is it styled, is anything cut off, does each button do what its label says.
- **Self-healing loop.** Each failure was traced to its cause, fixed in the code, and the full set of suites was run again until green.

### 3. Bugs found and fixed

#### High

1. **Five screens and three pop-ups had lost their styling.**
   - **Seen:** Settings, Live Scrapers, Import & Parse, the API Keys panel and the e-mail, bulk e-mail and WhatsApp pop-ups showed as raw unformatted HTML. The pop-ups opened squeezed into the page instead of on top of it.
   - **Cause:** about 70 style names used by these screens were dropped from `globals.css` in an earlier restyle (commit `6ce28e6`).
   - **Fix:** the styles are rewritten to match the current theme. See `2026-11-13-screens/before-settings.png` → `after-settings.png`, and the same pairs for `email-popup` and `live-scrapers`.
2. **The lead filter pills did nothing.**
   - **Seen:** clicking "Hot AI Leads (292)" still listed all 929 leads. Two pill counts also used a different rule from the filter itself.
   - **Fix:** pills and the KPI cards now share one filter, and each count comes from the same rule that filters the rows. Verified: 292 → 292, 212 → 212, 210 → 210.
3. **Saving Settings damaged the settings file.**
   - **Seen:** one save removed five saved values (sender role, services, signature template, WhatsApp number, e-mail delay). It also wrote the mail password as plain text into `company_settings.json`, which is tracked by git.
   - **Also:** the password typed there was never used; the backend only reads `.env`.
   - **Fix:** a save now merges into the file, never stores passwords or tokens, and the password box is replaced by a note that says where the password goes. Git history was checked: no password was ever committed.
4. **The "auto e-mail off" switch was ignored.**
   - **Seen:** your `.env` says `AUTO_SEND_EMAIL=false`, but the new hourly-run code turned auto e-mail on anyway whenever the Settings toggle was on (its default). "Run 1-Hour Cycle Now" would have e-mailed up to 5 real leads.
   - **Fix:** `AUTO_SEND_EMAIL=false` is now a hard off switch, locally and as a GitHub Actions variable. When it is not set to false, the Settings toggle decides.
5. **The Auto Scraper (1-Hr) screen showed wrong information.**
   - **History:** it said "No execution logs recorded yet" although 173 runs are logged (a missing `import csv`). It now lists the latest 50 results with run and lead totals.
   - **E-mail status:** it showed "Auto-Send ON" from the toggle alone. It now shows the real state and the reason.
   - **Run button:** one click started a full scrape and outreach with no question, and a quick double click could start two runs. It now asks first and refuses a second run.
   - **Title:** the page header said "B2B Intelligence Database". Fixed. See `before-auto-scraper.png` → `after-auto-scraper.png`.
6. **Bad input crashed the API.**
   - **Seen:** a list or plain text instead of a JSON object crashed 47 routes with an HTML "500 Internal Server Error" page. Older routes returned HTML for a missing body too.
   - **Fix:** every `/api` answer is now JSON, and bad input gets a clear 400 message.

#### Medium

7. **Phone top bar ran off the screen.** The search box shrank to one letter and the status pill and action buttons were cut off, on every page. Fixed (`before-phone-header.png` → `after-phone-header.png`).
8. **The top search bar did nothing outside the Leads page.** Typing now opens the leads list with the results.
9. **Lead status changes were unsafe.**
   - Any text was accepted as a status, and an unknown lead id still answered "success". Both are now refused.
   - Two saves at the same moment could silently drop one change. All writers of the leads file now share one lock.
10. **Invisible icons.** Three colour names used across the screens were never defined, so some icons and headings were invisible or black. Defined.
11. **Lead KPI cards sat on top of every tool page**, pushing the tool itself down. They now show on Dashboard and Leads only. This is a layout choice — it is one line in `app/page.js` if you prefer the old way.
12. **Settings overflowed sideways on phones.** Fixed.
13. **Search could crash on odd input** when building its saved-results key. Fixed.

### 4. Files changed

| Area | Files |
|---|---|
| Backend | `app.py`, `settings_manager.py`, `run_all_scrapers.py`, `search_cache.py` |
| Frontend | `app/globals.css`, `app/page.js`, `components/LeadsTable.js`, `Header.js`, `Sidebar.js`, `SettingsView.js`, `AutoScheduler.js` |
| Tests | `test_api_safety.py` (new, 16 tests), added to the test gate in `.github/workflows/auto_scraper_1hr.yml` |
| Report | this file and `reports/qa/2026-11-13-screens/` (10 before/after screenshots) |

### 5. Not fixed — suggestions for your decision

| # | Finding | Suggestion |
|---|---|---|
| S1 | **Real sign-in cannot be reached.** The Supabase address did not answer from this machine, so only the one-click local login works. Sign-in and sign-up are untested. | Check whether the Supabase project is paused. |
| S2 | **Outreach text uses job-post titles as the company name**, e.g. "Hi Senior Paid Media Manager - Full Time - Remote (USA only) Team". Many leads are job posts. | Use a cleaned short name, or "Hi there" when no real company name exists. This is what a recipient sees first. |
| S3 | The one-click admin login button always shows on the login screen. The server only honours it on localhost, so on a deployed site it would show and fail. | Hide it in production builds. |
| S4 | The ▶ icon in the top bar starts a scraper on one click, and bulk "Dismiss" marks leads DISQUALIFIED with no question and no undo. | Add a confirmation, as the 1-hour run now has. |
| S5 | "Verified Emails" only means the lead has an e-mail; nothing was verified. | Rename to "Has Email", or count only checked addresses. |
| S6 | SMTP host and port in Settings are not used; the backend reads `.env`. | Make them read-only, or wire them in. |
| S7 | Sidebar labels are cut ("Leads Intellige…", "Live Scrap…") by their badges. | Shorten the badges. |
| S8 | "12 READY" and "12 Scraper Engines" are fixed text, while Live Scrapers shows 8 cards. | Take the number from the real list. |
| S9 | The star and panel icons in the top bar do nothing. | Remove them or give them a job. |
| S10 | The Data Cleanup table is slightly wider than a phone screen; some checkboxes are small to tap. | Minor polish. |
| S11 | The frontend has no automated tests or lint. | Keep a small browser smoke test in CI; the scripts from this run can be the start. |
| S12 | The backend runs on Flask's development server. | Fine locally; use a production server when you deploy (hosting is deferred, as agreed). |

### 6. Not tested

- Sending real e-mail, the Gmail reply check, Supabase sync, Slack and Telegram (all switched off for safety).
- Live scraping results from external sites — only the forms, input checks and error handling were tested this time; each module has its own earlier report.
- Browsers other than Chromium.

### 7. Things you should know

- **Restart the backend.** The Flask process on port 5000 still runs the old code. The fixes take effect after a restart. Your `next dev` picks up the frontend changes by itself.
- **Another session was editing this project during the test.** Between 11:02 and 11:15 these changed and were not made by this QA run:
  - `company_settings.json` (sender e-mail changed to `info@sangeetainfotech.co.in`, automation defaults added)
  - `frontend/components/MiningForm.js` (pre-fills keywords and city from Settings)
  - `test_auto_scheduler_and_settings.py` (new, 6 tests)

  They are left as they are. The 6 tests pass together with the fixes above, and the final browser pass included the `MiningForm.js` change.
- **Auto e-mail on GitHub Actions.** The workflow default is `AUTO_SEND_EMAIL=true` and the settings file now says `autoSendEmail: true`, so the hourly cloud run will e-mail qualified leads. To stop it, set the repository variable `AUTO_SEND_EMAIL=false` — that switch now works.
- **Data safety.** `all_leads_master.csv` md5 `22fd3f86…` before and after. The three log files are also identical. QA servers on ports 3001 and 5055 are stopped.

### 8. Round 2 — re-test after the do-not-contact list was added

Between the two rounds, another session added a Do-Not-Contact list (Settings → "Excluded Companies", default `8dots`), pre-filled search defaults, and changed `.env` to `AUTO_SEND_EMAIL=true`. Everything was tested again on that code.

#### Result

| Suite | Round 2 result |
|---|---|
| Python unit tests (35 suites) | **527 / 527** — 6 more new tests for the do-not-contact list |
| API sweep (571 calls) | **0** crashes or raw error pages |
| Screen walkthrough (43 screens × 2 sizes) | **86 / 86** load clean, 0 console errors |
| Client workflows | **22 / 22** |
| New-feature browser tests | **9 / 9** — list shown, saved, cleared; defaults pre-filled; blocked send; honest bulk result |

All round-1 fixes were still in place.

#### Bugs found and fixed in round 2

14. **The do-not-contact rule blocked unrelated companies.**
    - **Seen:** the rule matched any shared fragment, in both directions. With the default `8dots`, a company called "Dots", "S" or "D" was blocked. A short entry such as `IT` would have blocked every company and e-mail with those two letters anywhere (for example "Infinity Digital").
    - **Fix:** a rule now matches the company name as whole words ("8dots Technology LLP", "8-Dots Pvt Ltd", "8 Dots Infotech") or the domain of the e-mail or website (`8dots.in`, `mail.8dots.co.in`, `8dotstech.com`). None of your 929 leads was wrongly blocked before or after.
15. **Dashboard sends skipped the company-name check.**
    - **Seen:** single e-mail, bulk e-mail, follow-up sequences and the quick scraper sent only the address to the shield. A lead of the excluded company using a personal mailbox (for example Gmail) would have been e-mailed.
    - **Fix:** every send path now passes the company name. Verified in the browser: the send is refused and the user sees "Do-not-contact blacklist rule: Company '8dots Technology LLP' matches…" (`2026-11-13-screens/round2-blocked-send.png`).
16. **The shield could be skipped.**
    - **Seen:** it ran after the mail-login check, and any error inside it was silently ignored, letting the e-mail go out.
    - **Fix:** it now runs first, and if the rule cannot be checked the e-mail is refused. This also made one of the other session's tests pass on machines without a mail login (it failed in the sandbox before).
17. **Bulk e-mail claimed success when nothing was sent.**
    - **Seen:** if every selected lead was refused, the message said "Campaign finished! 1 emails dispatched" and the rows turned to EMAIL_SENT on screen.
    - **Fix:** only leads the server really e-mailed are marked, and the message says how many were sent and why the rest were not (`round2-bulk-blocked.png`).
18. **A failed single send left an unhandled error** in the browser. Fixed; the pop-up stays open so the text is not lost.

Also fixed: the Data Cleanup history table no longer runs off a phone screen (part of S10).

#### Files changed in round 2

| Area | Files |
|---|---|
| Backend | `settings_manager.py`, `email_service.py`, `app.py`, `run_all_scrapers.py`, `scraper.py` |
| Frontend | `app/page.js`, `components/SingleEmailModal.js`, `BulkEmailModal.js`, `LeadCleanup.js` |
| Tests | `test_api_safety.py` (now 22 tests), one line in `test_followup_phase2.py` so its stand-in mail function accepts the company name |

#### Important: auto e-mail is now ON on this machine

- `.env` now has `AUTO_SEND_EMAIL=true` and a real mail login, and the Settings toggle is on.
- So "Run 1-Hour Cycle Now", and any hourly run started here, will send up to 5 intro e-mails to real leads per run. The run button asks for confirmation and says so.
- To stop it, set `AUTO_SEND_EMAIL=false` in `.env` or turn the toggle off in Settings. Section 3 item 4 describes `.env` as it was during round 1.
- The backend on port 5000 was restarted at 11:26, before the round-2 fixes. **Restart it once more** so fixes 14–16 are active.

### 9. Round 3 — the open suggestions from section 5

You asked for the remaining items to be done. Nine of the twelve are now fixed and tested; three could not be done here.

#### Result

| Suite | Round 3 result |
|---|---|
| Python unit tests (35 suites) | **529 / 529** — 2 more new tests for the e-mail wording |
| API sweep (571 calls) | **0** crashes or raw error pages |
| Screen walkthrough (43 screens × 2 sizes) | **86 / 86** load clean, 0 console errors |
| Client workflows | **22 / 22** |
| Do-not-contact browser tests (round 2) | **9 / 9** |
| Suggestion checks | **9 / 9**, plus e-mail drafts checked on 8 real leads (2 companies, 6 job posts) |

#### What was done

| # | Suggestion | Status |
|---|---|---|
| S2 | Job-post titles used as the company name in outreach | **Fixed.** A real company still gets "Hi BCDRPulse Team". A job post now gets "Hi there" and "your team"; its title is never written into the e-mail or WhatsApp text. Applies to the e-mail and WhatsApp pop-ups, bulk e-mail, the hourly run, imports and the quick scraper (`round3-email-wording.png`). |
| S3 | One-click admin login always visible | **Fixed.** It shows only when the app is opened on this computer (localhost). The dark box behind its label is also gone. |
| S4 | Scraper and bulk Dismiss with no question | **Fixed.** Starting a scraper (top bar, sidebar, leads page, Live Scrapers) and bulk Dismiss now ask first. |
| S5 | "Verified Emails" pill | **Fixed.** Renamed "Has Email". |
| S6 | Unused SMTP host and port fields | **Fixed.** Shown read-only, with a note that they come from `.env`. |
| S7 | Cut-off sidebar labels | **Fixed.** Smaller badges; long submenu names wrap. No label is cut off now. |
| S8 | Fixed "12" texts | **Fixed.** The number is removed from the sidebar badge, the KPI card, the page title and the Live Scrapers buttons. |
| S9 | Top-bar star and panel icons that did nothing | **Fixed.** Removed. |
| S10 | Small checkboxes, wide Data Cleanup table | **Fixed.** Checkboxes are 17 px; the table scrolls inside its card. |
| S11 | No frontend tests | **Partly.** The three browser and API test scripts from this run are saved in `qa/`. They are not wired into GitHub Actions; that needs a browser set up in the workflow. `test_auto_scheduler_and_settings` is now in the hourly run's test gate. |
| S1 | Supabase sign-in unreachable | **Not fixable here.** The address still does not answer. While it is down, a failed sign-in spins for up to about 30 seconds before the message appears. Check the project on supabase.com. |
| S12 | Flask development server | **Left as agreed** — hosting is to be decided at the end of the project. |

#### New observations

- **Non-IT leads are in the list.** For example "Bartender at Birds – New York, NY" has an e-mail address and a draft button. Auto e-mail only goes to AI-qualified leads, but a manual bulk send would include such rows. Worth a filter or a review before bulk sends.
- **Two backends are running on port 5000.** After `run_project.bat` was run again, the old process (PID 19720) is still alive next to the new one (PID 10740). Close the old window or run `taskkill /PID 19720 /F`, then restart the new one once so it loads the round-3 code.

#### Files changed in round 3

| Area | Files |
|---|---|
| Backend | `followup_sequence.py`, `app.py`, `run_all_scrapers.py`, `lead_importer.py`, `scraper.py`, `outreach_manager.py` |
| Frontend | `lib/leadNames.js` (new), `app/page.js`, `app/globals.css`, `components/AuthScreen.js`, `Header.js`, `Sidebar.js`, `LeadsTable.js`, `SettingsView.js`, `SingleEmailModal.js`, `WhatsAppModal.js`, `StatsCards.js`, `ScraperConsole.js`, `AutoScheduler.js` |
| Tests | `test_api_safety.py` (now 24 tests), `qa/` (3 scripts), workflow test gate |

## ગુજરાતી

- **Round 3:** બાકીનાં 12 સૂચનોમાંથી 9 fix થયાં. E-mail માં હવે job-post નું title નામ તરીકે નથી જતું ("Hi there" લખાય છે), scraper અને Dismiss પહેલાં પૂછે છે, "Verified Emails" નું નામ "Has Email" થયું, અને ખોટા "12" લખાણો દૂર થયાં. 529/529 tests pass. Supabase login હજી બંધ છે, તે supabase.com પર તમારે જોવું પડશે.
- **Port 5000 પર બે backend ચાલે છે:** જૂની window બંધ કરો (અથવા `taskkill /PID 19720 /F`), પછી નવું backend એક વાર restart કરો.
- **Round 2:** Do-Not-Contact list ઉમેરાયા પછી બધું ફરી test કર્યું. 5 નવા bugs મળ્યા અને fix થયા: rule બીજી કંપનીઓને પણ block કરતો હતો ("Dots", "S"), dashboard થી મોકલતાં company name check નહોતું થતું, અને bulk e-mail કંઈ ન મોકલાયું હોય તોય "sent" બતાવતું હતું. હવે 527/527 tests pass.
- **ખાસ ધ્યાન:** `.env` માં હવે `AUTO_SEND_EMAIL=true` છે, એટલે "Run 1-Hour Cycle Now" સાચા leads ને e-mail મોકલશે. Backend ફરી એક વાર restart કરો.
- **પરિણામ (round 1):** 13 bugs મળ્યા અને બધા fix થયા. Unit tests 519/519, API sweep માં 0 crash, 43 screens desktop અને phone બંને પર બરાબર, 22/22 workflows pass.
- **સૌથી મોટી ખામીઓ જે fix થઈ:**
  - Settings, Live Scrapers, Import અને e-mail / WhatsApp pop-up નું styling ગાયબ હતું.
  - Leads ના filter pills કામ નહોતા કરતા.
  - Settings save કરવાથી 5 values ભૂંસાઈ જતી હતી, અને mail password file માં ખુલ્લો લખાતો હતો.
  - `.env` માં `AUTO_SEND_EMAIL=false` હોવા છતાં auto e-mail ચાલુ થઈ જતો હતો.
  - Auto Scraper screen ખાલી history અને ખોટું status બતાવતી હતી.
- **તમારો data સલામત:** leads file અને logs બિલકુલ બદલાયાં નથી, કોઈ e-mail મોકલાયો નથી, કંઈ commit નથી કર્યું.
- **તમારે કરવાનું:**
  - Backend (port 5000) restart કરો, તો જ fixes લાગુ પડશે.
  - Section 5 ના 12 સૂચનો પર નિર્ણય લો — ખાસ S1 (Supabase login બંધ) અને S2 (e-mail માં job-post title નામ તરીકે જાય છે).
- **ધ્યાન આપો:** test દરમિયાન બીજી session એ `company_settings.json`, `MiningForm.js` અને એક નવી test file બદલી. તે જેમ છે તેમ રાખ્યાં છે.

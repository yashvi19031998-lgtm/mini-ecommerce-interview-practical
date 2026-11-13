# Task: build the "Reports" module (new sidebar menu → Reports)

You are working in an existing lead-generation app (LeadsGen AI). Another engineer owns the rest of the code and works in parallel, so **stay strictly inside the files listed in section 3**.

Nothing is wired for you this time: you add the API routes, the API client functions, the sidebar item and the page yourself, in the exact places given below.

The owner's words: *"Reports is the most important module. Everything must be in it. Not a single lead's follow-up may be missed. How much data came from how many scrapers. Everything the customer would want."*

A full QA of the app was done on 2026-11-13. Its bugs are listed in **section 9**. Avoid every one of them; the reviewer will check each one again.

## 0. Project facts (read first)

- **Root:** `test-demo/`.
  - Backend: Python 3.14 + Flask (`app.py`, venv `test-demo/venv`).
  - Frontend: Next.js in `test-demo/frontend` (React, plain JavaScript, no TypeScript, no UI or chart library).
- **This Next.js version has breaking changes.** Read `frontend/AGENTS.md` and `frontend/node_modules/next/dist/docs/` before writing frontend code.
- **Run tests:** `venv\Scripts\python.exe -m unittest discover -p "test_*.py"`. There are 529 tests and all pass today; they must still pass when you finish.
- **Build the frontend for checking** with `NEXT_DIST_DIR=.next-qa npm run build`. Never build into `.next`: the owner runs `next dev` on port 3000 from that folder, and a build there breaks it.
- **The owner's rules (must follow):**
  - **Do not install anything.** No new Python or npm packages; draw charts with plain HTML/CSS or inline SVG.
  - Never commit, push, or deploy.
  - Never edit `.env`; never print, log, or hard-code secrets.
  - **Reports are read-only.** Nothing in this module may write to `all_leads_master.csv`, `company_settings.json`, `logs/*` or any other data file, send an e-mail, or start a scraper. The only exception is the "Schedule follow-up" action in 6.4, which must call the existing follow-up API.
  - Docs must be bilingual: English + Gujarati.
  - "Developed ≠ Completed": mark anything not verified in a real browser as **UNVERIFIED**.
  - **Do not leave scratch / probe scripts in the repo.** Put them in a temp folder outside `test-demo/` and delete them when done.

## 1. Goal

A **Reports** page that answers, at a glance and with exact numbers:

1. **What happened** in a chosen period: leads found, contacted, replied, meetings, won.
2. **Which scrapers and sources work:** how much data each scraper brought, how many new leads, duplicates and failures.
3. **Which leads need attention now**, so that no follow-up is ever missed.
4. **Where leads get stuck** in the pipeline.
5. **How healthy the data is:** missing e-mail, phone, website; stale leads.

Every number on the page must be clickable or explained, and every table must export to CSV.

## 2. Data that already exists (read it, never write it)

| Data | File / helper | Notes |
|---|---|---|
| Leads | `all_leads_master.csv` (929 rows today). Read with `app.read_leads()` — it is cached by file time, returns copies, and adds UI names (`Company Name`, `Email`, `Status`, `Source`, ...). | Key columns: `lead_id, company_name, email, mobile_number, website, source, location, first_seen_at, last_seen_at, last_updated_at, email_status, email_sent_at, posted_at, status, ai_category, ai_score, ai_summary, deal_size_estimate, seniority_fit, whatsapp_status, last_contacted_at`. |
| Lead stages | `app.LEAD_STATUSES` | `NEW, CONTACTED, EMAIL_SENT, REPLIED, MEETING, WON, LOST, DISQUALIFIED`. Today all 929 leads are `NEW`, so every stage report must look right with zeros. |
| Source of a lead | `source_report.source_family(lead)` | `'Reddit (r/forhire) \| Search Engine (...)'` → `'Reddit'`. Reuse it; do not write a second version. |
| Hot lead | `source_report.HOT_SCORE` (7) and `HOT_CATEGORIES` | The leads table counts a lead as hot when its AI score is ≥ 7; `source_report` also requires a buyer category. Use the leads-table rule (score ≥ 7) everywhere in Reports so the numbers match the Dashboard, and say so in a `title`. |
| Stale lead | `lead_quality.is_stale(lead)` | Reuse it. |
| Scraper runs | `logs/scraper_runs.csv` (~2,150 rows) | Columns: `run_id, start_time, end_time, scraper_name, status, records_collected, new_leads_added, existing_leads_updated, duplicates_detected, error_summary`. **One row per scraper per run**; a "run" is all rows sharing a `run_id`. Scraper names contain commas inside quotes — read with `csv.reader`/`DictReader`, never `split(",")`. |
| Sent e-mails | `logs/sent_emails.csv` | `email, sent_at, subject`. Older sends are only here, not in the follow-up log. |
| Follow-up activity | `followup_store.py` → `logs/followup_activity.csv` | **The file does not exist yet** (no activity has been logged). Your code must treat a missing file as "no activity", never as an error. Use the module's functions: `queue(bucket)`, `summary()`, `history(...)`, `last_contact_by_lead()`, `report(lead_sources)`, `bucket_of(row)`. Activity `type` values: `call, meeting, note, whatsapp, email, email_sent, status_change, reply, bounce, opted_out, sequence_stopped, followup`. |
| Follow-up sequence | `followup_sequence.plan(app._lead_index())` | Returns `due`, `waiting`, `stopped`. `followup_sequence.config()` gives the step days. |
| Do-not-contact list | `settings_manager.load_settings()["excludedCompanies"]` and `settings_manager.is_company_excluded(company, email, website, settings=...)` | Use it to show how many leads are on the do-not-contact list. Pass `settings=` so it does not reload the file per lead. |
| Settings | `settings_manager.load_settings()` | Read only. |

**Timestamps** are local time strings `YYYY-MM-DD HH:MM:SS` (some lead dates are `YYYY-MM-DD` or ISO with `T`). Parse defensively; a value that cannot be parsed counts as "unknown date", never as a crash.

## 3. Files you may change / create

1. **New:** `test-demo/reports_engine.py` — all report logic (pure functions, no Flask).
2. `test-demo/app.py` — **append one block at the very end, just above `if __name__ == "__main__":`**, with a header comment `# REPORTS (reports_engine.py)`. Do not change any existing line.
3. `test-demo/frontend/lib/api.js` — **append** your functions at the end of the file. Do not change existing functions.
4. **New:** `test-demo/frontend/components/Reports.js` (and, if it grows past ~600 lines, `frontend/components/reports/*.js`).
5. `test-demo/frontend/components/Sidebar.js` — add **one** nav item (6.1). Nothing else.
6. `test-demo/frontend/components/Header.js` — add **one** entry to `tabTitles`.
7. `test-demo/frontend/app/page.js` — add the import and **one** `{activeTab === 'reports' && ...}` block next to the others.
8. `test-demo/frontend/app/globals.css` — **append** a section `/* ---- Reports ---- */` at the end; prefix every new class with `rp-`.
9. **New:** `test-demo/test_reports_engine.py`
10. **New:** `test-demo/docs/reports.md` (English + Gujarati)
11. **New:** `test-demo/reports/qa/<YYYY-MM-DD>-reports.md` (English + Gujarati)
12. `.github/workflows/auto_scraper_1hr.yml` — add `test_reports_engine` to the end of the `python -m unittest ...` line in the "Run tests" step. Nothing else in that file.

Do not edit any other file. If another file must change, stop and write the exact change in your final message.

## 4. Backend: `reports_engine.py`

**Study first:** `source_report.py`, `followup_store.py` (`report`, `queue`, `bucket_of`), `followup_sequence.py` (`plan`, `company_for_email`), `lead_quality.py` (`is_stale`), and `get_scheduler_status()` in `app.py` (how it reads `scraper_runs.csv`).

### 4.1 Shape

- Every public function takes its data as arguments (`leads`, `runs`, `activities`, `sent`, `now`, `date_from`, `date_to`, filters) and returns plain dicts/lists. **No file access inside the report functions**, so they are easy to test.
- Put file loading in small separate helpers (`load_runs(path)`, `load_sent(path)`) that return `[]` when the file is missing or unreadable.
- `now` is always a parameter (default `datetime.now()`), so tests can fix the date.

### 4.2 Filters (shared by every report)

- `date_from`, `date_to`: `YYYY-MM-DD`, both inclusive. Default: last 30 days. Presets the UI offers: Today, Yesterday, Last 7 days, Last 30 days, This month, Last month, All time.
- `source`: a source family, or `all`.
- `status`: a lead stage, or `all`.
- Validate everything. Unknown filter value or `date_from > date_to` → `ValueError` with a clear message (the route turns it into HTTP 400). Range longer than 3 years → `ValueError`.
- Which date applies to a lead: `first_seen_at` (fallback `posted_at`, then `last_updated_at`). For runs: `start_time`. For activity: `occurred_at`. For sent e-mails: `sent_at`.

### 4.3 Reports to build

**R1 Summary** — `summary(leads, runs, activities, sent, filters, now)`
- Cards: total leads (all time), new leads in the period, hot leads in the period, contacted, replied, meetings, won, lost, e-mails sent in the period, scraper runs in the period, failed scraper results in the period, follow-ups overdue (always "now", not the period).
- For each card: the value, the value for the **previous period of the same length**, and the change (`+12`, `-3`, or `null` when there is no previous data). Never divide by zero.
- A daily series for the period: new leads per day and e-mails sent per day (every day present, zeros included).

**R2 Scraper report** — `scraper_report(runs, filters, now)`
- Per scraper (group by the script name before the first ` (`, e.g. `reddit_rss_scraper.py`; keep the full label too): times run, successful, failed, records collected, new leads added, existing leads updated, duplicates, duplicate %, new-lead yield % (`new / records`), last run time, last status, last error (if any), **days since it last added a new lead**.
- Totals row.
- Per run: `run_id`, start, end, duration in minutes, scrapers in the run, failed scrapers, total records, total new leads.
- A flag list: scrapers that failed in their last run; scrapers that added 0 new leads in their last 10 runs ("not producing"); scrapers that have not run for more than 24 hours although the schedule is hourly.

**R3 Source quality** — `source_report_rows(leads, activities, filters)`
- Per source family: leads, with e-mail %, with phone %, with any contact %, AI-scored, average AI score, hot, hot %, contacted, replied, reply rate %, meetings, won, stale.
- Sort by hot leads, then leads. Mark sources with ≥ 20 leads and 0 hot as "low value".

**R4 Follow-up watchlist ("no lead missed")** — `followup_watchlist(leads, activities, sent, sequence_plan, settings, now)`

This is the most important report. One row per lead that needs action, each with a **reason**, the **days waiting**, the lead's company, e-mail, phone, source, AI score, status, last contact (type + date) and next due date. Reasons, in priority order (a lead appears once, with its highest-priority reason):

1. `overdue_followup` — a scheduled follow-up whose due date has passed (`followup_store.bucket_of == "overdue"`).
2. `replied_no_answer` — a `reply` after which there is no later outbound activity (`email_sent`, `email`, `call`, `whatsapp`, `meeting`) from us.
3. `due_today` — follow-up due today.
4. `sequence_due` — in `sequence_plan["due"]`.
5. `meeting_no_next_step` — status `MEETING` with no scheduled follow-up in the future.
6. `contacted_gone_quiet` — contacted (activity `email_sent`, or the lead's `email_status` is SENT, or the address is in `sent_emails.csv`) more than N days ago (default 5, a parameter), no reply, no later contact, no follow-up scheduled, status not `WON/LOST/DISQUALIFIED`.
7. `hot_never_contacted` — AI score ≥ 7, has an e-mail or phone, never contacted, not on the do-not-contact list, status `NEW`.
8. `stale_open` — `lead_quality.is_stale(lead)` and status still open.

Also return counts per reason, and **do not drop rows silently**: a lead the rules cannot classify (bad dates etc.) is still listed with reason `needs_review`.

Leads on the do-not-contact list never get reasons 6 or 7; show their count separately ("blocked by do-not-contact list").

**R5 Pipeline / funnel** — `pipeline(leads, activities, filters)`
- Count per stage (all eight stages, zeros included), in order.
- Conversion between consecutive stages, with `null` when the earlier stage is 0.
- Average days from first seen to contacted, and contacted to replied, when the data allows; otherwise `null` with a note.
- Stuck leads: count per stage of leads with no activity for more than 14 days.

**R6 Outreach report** — `outreach(leads, activities, sent, settings, filters)`
- E-mails sent in the period, split: auto (hourly run), manual (dashboard single), bulk, follow-up sequence. Use the activity `source` field; anything you cannot classify goes to "other", not lost. Also count `sent_emails.csv` rows that have no matching activity ("sent before tracking").
- Replies, reply rate %, bounces, opt-outs.
- Leads blocked by the do-not-contact list.
- Top 10 subjects by sends and by replies.

**R7 Data health** — `data_health(leads, now)`
- Missing e-mail, missing phone, missing website, missing all three, no AI score, stale, duplicate e-mails (same address on more than one lead), possible duplicate companies (same normalised name), leads whose "company name" is really a post title (use `followup_sequence.company_for_email(name) == "your team"`).
- Each with a count and a sample of up to 20 lead ids.

**R8 Daily activity log** — `activity_log(runs, activities, sent, leads, day)`
- Everything that happened on one day, newest first: scraper runs (with new leads added), leads added, e-mails sent, replies, status changes, manual activities, follow-ups scheduled and completed.

**R9 Export** — every report table must be exportable. Do this in the frontend (build the CSV from the rows already on screen, with the current filters) so no extra endpoint is needed. CSV must be UTF-8 with BOM (Excel shows Gujarati correctly) and must neutralise formula injection: prefix a value that starts with `=`, `+`, `-`, `@`, tab or CR with `'`.

### 4.4 Performance

- 929 leads and ~2,150 run rows today; it must stay fast at 50,000 leads and 100,000 run rows. Read each file once per request, index by lead id / e-mail once, no nested full scans per lead.
- Target: every report endpoint under 1 second for today's data.

## 5. API routes (append to `app.py`, section 3 item 2)

All `GET`, all read-only, all JSON. Login is already enforced for every `/api/*` route (`api_auth.py`); do not add your own.

| Route | Returns |
|---|---|
| `GET /api/reports/summary` | R1 |
| `GET /api/reports/scrapers` | R2 |
| `GET /api/reports/sources` | R3 |
| `GET /api/reports/followups` | R4 (query `quiet_days`, default 5, 1–60) |
| `GET /api/reports/pipeline` | R5 |
| `GET /api/reports/outreach` | R6 |
| `GET /api/reports/data-health` | R7 |
| `GET /api/reports/activity` | R8 (query `day=YYYY-MM-DD`, default today) |
| `GET /api/reports/options` | the list of source families, stages, date presets and the default range, for the filter bar |

- Filters come as query parameters: `date_from`, `date_to`, `source`, `status`.
- Wrap each in `try: ... except ValueError as e: return jsonify({"success": False, "error": str(e)}), 400`. Success responses are `{"success": True, ...}`.
- Leads: `read_leads()`. Paths: build from `BASE_DIR` (e.g. `os.path.join(BASE_DIR, "logs", "scraper_runs.csv")`), never a bare relative path.

## 6. Frontend: `Reports.js`

**Study first:** `AutoScheduler.js` (cards + table layout), `FollowUpHistory.js` / `FollowUpSequences.js` (tabs, `fu-` styles, ReportPanel), `JobPortalScraper.js` (`jp-table`, `jp-alert`, `jp-hint`), `LeadsTable.js` (filter pills), and the `theme-*` classes in `globals.css`. Use the existing classes first; add `rp-` classes only for what is missing.

### 6.1 Wiring

- `Sidebar.js`: add `{ id: 'reports', label: 'Reports', icon: BarChart3 }` (import `BarChart3` from `lucide-react`) to `navItems`, **directly after the `dashboard` item**. No badge.
- `Header.js`: `reports: { root: 'LeadsGen AI', leaf: 'Reports' }`.
- `page.js`: `{activeTab === 'reports' && <Reports onOpenLeads={() => setActiveTab('leads')} onOpenFollowups={() => setActiveTab('followups')} onOpenScraper={() => setActiveTab('autoscheduler')} />}`. The KPI cards above the page are only shown on `dashboard` and `leads`; leave that rule as it is.

### 6.2 Layout

- **Top:** title "Reports", one line of explanation, and the **filter bar** (date preset select + custom from/to date inputs, source select, status select, Refresh button). Filters apply to every tab and are kept in the URL hash or `localStorage` (wrapped in try/catch) so a reload keeps them.
- **Tabs** (`role="tablist"`, keyboard reachable): **Overview** (R1) · **Follow-ups** (R4) · **Scrapers** (R2) · **Sources** (R3) · **Pipeline** (R5) · **Outreach** (R6) · **Data health** (R7) · **Daily log** (R8).
- **Overview** shows the cards with the change vs. the previous period, a simple bar chart of new leads per day (inline SVG or CSS bars, with the exact number in a `title` tooltip and a text alternative), and three short "needs attention" boxes linking to Follow-ups, Scrapers and Data health with their counts.
- **Follow-ups** opens by default **when it has overdue or due-today rows** (otherwise Overview). Group rows by reason with counts as filter chips. Each row has **Open lead** (opens the leads list filtered to that company — use `onOpenLeads`) and **Schedule follow-up** (a small form: date + note, posting to the existing `scheduleFollowup({ lead_id, due_at, note })` in `lib/api.js`; refresh the tab afterwards and show a toast/alert with the result).
- **Scrapers** shows the per-scraper table first (sortable by each column), then the flag list in a `jp-alert`, then the per-run table (latest 50, with "Show more").
- Every table: sortable headers, sticky header, a row count ("Showing 20 of 134"), pagination of 50, an **Export CSV** button, and a proper empty state that says *why* it is empty ("No scraper runs in this period", "No follow-up activity has been logged yet — log calls and e-mails in FollowUp History").
- Loading: one spinner per tab, never a blank page. Errors: a `jp-alert jp-alert-error` with the server's message and a Retry button.

### 6.3 Look and feel

- Match the current theme: white background, `var(--bg-subtle)` panels, `var(--primary-blue)` accent, 16 px card radius, `theme-pill-btn` buttons. Colours only from the CSS variables at the top of `globals.css` (and the extra ones in the "RESTORED SHARED STYLES" section). Do not invent new colour names.
- Numbers: Indian grouping (`toLocaleString('en-IN')`), percentages with one decimal, dates shown as `13 Nov 2026, 11:05`.
- **Phone (390 px):** no horizontal page scroll; tables scroll inside their own container (`theme-table-scroll`); cards stack; the filter bar wraps.

### 6.4 Behaviour rules

- Read-only, except "Schedule follow-up" (section 0).
- Never show a number you cannot explain: each card has a `title` saying how it is counted.
- Do not show placeholder or demo numbers. If data is missing, show 0 or "—" and say why.

## 7. Tests: `test_reports_engine.py`

No network, no real files: build small in-memory leads / runs / activities / sent lists, or use `tempfile` copies. At least:

- **Filters:** presets resolve to the right dates for a fixed `now`; `date_from > date_to`, unknown source, unknown status and a 4-year range raise `ValueError`.
- **Summary:** counts in range, previous-period comparison, change is `null` when the previous period has no data, daily series includes zero days.
- **Scraper report:** grouping by script name; a scraper label containing commas is read correctly from a real CSV written with `csv.writer`; duplicate % and yield % with `records = 0` do not crash; "not producing" and "failed last run" flags.
- **Follow-up watchlist:** one test per reason (1–8); priority (a lead that is both overdue and hot appears once, as overdue); a lead on the do-not-contact list never appears as `hot_never_contacted`; a missing activity file → empty activity, not an error; bad dates → `needs_review`, not dropped.
- **Pipeline:** all eight stages present with zeros; conversion is `null` when the previous stage is 0.
- **Outreach:** sends classified by source; unknown source goes to "other"; `sent_emails.csv` rows with no activity counted as "sent before tracking".
- **Data health:** duplicate e-mails, post-title company names, samples capped at 20.
- **API:** every route returns 401 without login; 200 with the `X-Demo-User: true` header (the local login used by the existing tests — see `test_api_safety.py`, which also shows how to point `app` at temporary files with `mock.patch.object`); 400 on bad filters; **the leads file's bytes are identical before and after calling every route**.
- **Performance:** with 50,000 generated leads and 100,000 run rows, `summary` + `followup_watchlist` + `scraper_report` each finish under 3 seconds.

## 8. Browser check (before you call it done)

1. Build with `NEXT_DIST_DIR=.next-qa npm run build`, run `NEXT_DIST_DIR=.next-qa npm run start -- -p 3001`. **Do not touch ports 3000 or 5000** (the owner's servers).
2. Run a copy of the backend on another port (copy `test-demo` without `venv`, `frontend`, `.git` to a temp folder, set `FLASK_PORT=5055`, and blank `SMTP_USER`, `SMTP_PASS`, `SLACK_WEBHOOK_URL`, `SUPABASE_KEY`, `ANTHROPIC_API_KEY` in that copy's `.env`). Route the browser's `/api/*` calls to it (Playwright `context.route`, as in `test-demo/qa/ui_workflows.py`).
3. Use the one-click local login; open Reports; go through every tab with at least three filter combinations; check desktop (1440 px) and phone (390 px); check the console has no errors; export one CSV and open it.
4. Save screenshots under `reports/qa/<date>-reports-screens/`.
5. Re-run `qa/ui_screens.py` and `qa/ui_workflows.py` to prove you broke nothing (adjust only the list of tabs to include `reports`).

## 9. Bugs found in the 2026-11-13 QA — do not repeat them

1. **Unstyled screens.** Components used class names that do not exist in `globals.css`, so screens showed as raw HTML. Every class you use must exist; check with a search before you finish.
2. **Undefined CSS variables** (`--primary-lavender` and others were used but never defined, so icons were invisible). Use only defined variables.
3. **Filter pills that did not filter**, and counts that used a different rule than the filter. A count shown next to a filter must come from the same function that filters the rows.
4. **Crashes on bad input:** a list or text sent where an object was expected gave an HTML 500 page. Validate every parameter; every `/api` answer must be JSON.
5. **Missing import** (`csv` was used but not imported, so a page silently showed "no data"). Never hide an exception that makes a report empty: return an error the UI can show.
6. **Reading `scraper_runs.csv` with naive splitting / without skipping the header** gave wrong counts. Use `csv.DictReader`, skip malformed rows, and count them in a `skipped_rows` field.
7. **Honest numbers.** The bulk e-mail screen once said "Campaign finished! 1 emails dispatched" when nothing was sent. Never show a success or a number that is not true.
8. **Hard-coded counts** ("12 scrapers", "12 READY") that did not match reality. Derive every number from data.
9. **Phone layout:** the top bar and some tables ran off the screen at 390 px. Test at 390 px.
10. **No question before a big action.** Not relevant if you stay read-only — so stay read-only.
11. **Writing data from a read path:** reports must never write any file (section 0).
12. **Unhandled promise errors** in the browser when an API call failed. Catch every API error and show it.

## 10. What to hand back

- Every file you changed or created, with a one-line purpose each.
- Test result line (`Ran N tests ... OK`) — the full suite, not only yours.
- Browser check result per tab, desktop and phone, with screenshot paths.
- Anything marked **UNVERIFIED**, and any change you needed in a file outside section 3 (as an exact diff, not applied).
- The QA report in `reports/qa/` and the doc in `docs/reports.md`, both English + Gujarati.

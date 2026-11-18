# LeadsGen AI – UX & Frontend Audit

18 Nov 2026

The app is a toolbox, not a workflow. It opens on charts and holds 54 pages behind one URL. The question "what do I do with this lead next?" is spread over five screens, which use three different status vocabularies. Scraping is easy to find; acting on a lead is not.

## 1. Screens and user journey

There are 54 pages, 4 modals and 2 overlays. One component (`app/page.js`) renders all of them by switching on an `activeTab` string. Only about 8 pages are about working leads; the other 46 find leads or are utility tools.

**Pages, grouped as the sidebar now shows them**

| Area | Pages | Purpose |
| --- | --- | --- |
| Today | Dashboard, Lead Status, Reply Today, All Leads, Follow-ups, Daily Leads & Mail | Working leads |
| Find Leads | Freelance Projects, Run Scrapers (live console), Auto Scraper | Running scrapers |
| Find Leads › Lead Sources | 9 web/social sources (Search Engines, Google Maps, Social Media, Ad Library, Ecommerce, Job Portals, Global Directories, WhatsApp Groups, Real Estate), 6 Indian directories, 3 company registries | One form per source |
| Contacts | Import Leads, Uploaded Files, CRM Sources | Getting data in |
| Contacts › Contact Tools | Clean Up Leads, Fill Missing Details, Find Contacts on Websites, Verify Emails, Clean Phone Numbers, Import & Remove Duplicates | Data repair |
| Insights › Reports | Overview, New Leads – Not Contacted, Follow-up Watchlist, Scrapers, Sources, Pipeline, Outreach, Data Health, Daily Log | Analytics |
| Tools › Web Tools | Website Analyzer, 4 crawler tools, 4 domain tools | Utilities |
| — | Settings & Email | SMTP, API keys, signature |

**Modals and overlays**

| Component | Opened from | What it does |
| --- | --- | --- |
| `AILeadDossierModal` | A lead row, or its "Dossier" button | Shows the AI summary, requirement, fit, deal size and tech stack. Has buttons for email, WhatsApp, LinkedIn and the original post. |
| `SingleEmailModal` | "Email" on a lead row or in the dossier | Draft and send one email |
| `BulkEmailModal` | All Leads, after ticking rows | Send to the selected leads |
| `WhatsAppModal` | "WhatsApp" on a lead row | Prepare a WhatsApp message |
| `ChatAssistant` | Floating bubble, every page | Ask questions about the data |
| `Toast` | Everywhere | Success / error messages |

**Where a user lands.** Every session starts on Dashboard, after the login screen (`AuthScreen`: Supabase sign-in or one-click local demo). The open page lives only in React state, and the URL is always `/`:

- a browser refresh returns to Dashboard;
- the Back button leaves the app;
- no page can be bookmarked or linked to a colleague.

**Journey to act on one lead today (5 steps, 2 modals)**

```
Log in ──> 1. Dashboard ──> 2. All Leads
           (4 KPI cards,     (6 pills, 20 per page,
            top 6 leads,      no source/date filter)
            no to-do)                │
                                     v
5. Log the contact <── 4. Email or WhatsApp <── 3. Dossier modal
   (row status dropdown,  (a second modal;          (AI profile, read only,
    or Follow-ups page)    bulk WhatsApp opens       no status or history)
                           the first lead only)

Shortcut since 17 Nov: Lead Status page — pick a stage, contact, mark done (2 steps, 1 page).
It is one menu click away, but users still land on Dashboard.
```

1. Dashboard shows 4 KPI cards, the top 6 hot leads and a source chart, but no to-do.
2. Click a KPI card or "All Leads". This opens a card list, 20 leads per page, sorted by AI score, with 6 filter pills.
3. Click a row to open the Dossier modal. It is read-only: it shows no status, history or next step.
4. Close it and use "Email" or "WhatsApp" on the row. This opens a second modal.
5. Log the contact elsewhere: change the row's status dropdown, or log an activity on the Follow-ups page.

**Overloaded or repeated screens**

| Screen | Problem |
| --- | --- |
| All Leads (`LeadsTable`, 18 buttons) | Two search boxes (header and table), 6 pills, a sort toggle, an Actions menu and a bulk bar. Each row also has a status dropdown plus Dossier, Email and WhatsApp buttons. There is no source, date or stage filter. |
| Follow-ups (`FollowUpHistory`, 24 buttons) | The activity log, follow-up queue, score bands, sequences and a report panel are all on one page. |
| Dashboard + All Leads | Both show the same 4 KPI cards (`StatsCards`). Two of them, "Senior Fit (8–9+ Yrs)" and "$3k–$8k Deal Fit", come from a job-seeker framing, not from an agency selling services. |
| Reports | Three pages show the same thing: New Leads – Not Contacted, Follow-up Watchlist and Follow-ups all list leads waiting for contact. |
| Lead Sources | 18 near-identical forms. Most users run the scheduled scraper and never need them. |
| Header | The refresh and "quick scraper" icons repeat the sidebar buttons. Typing in the header search jumps to All Leads without warning. |

## 2. Navigation and information architecture

The only navigation is the sidebar: 16 top-level entries in 5 headed sections. Four folding groups inside it hold 38 more pages. Until 17 Nov the sidebar showed about 51 entries, all unfolded.

| Layer | What exists | Component |
| --- | --- | --- |
| Sidebar | Sections Today, Find Leads, Contacts, Insights and Tools. Folding groups: Lead Sources (18), Contact Tools (6), Reports (9), Web Tools (9). | `Sidebar.js` |
| Header | Collapse toggle, breadcrumb, global search, DB status pill, refresh, quick-scraper | `Header.js` |
| In-page tabs | Reports has its own tab bar, hidden when opened from the sidebar. Follow-ups has bucket and score chips; Settings has sub-panels. | `Reports.js`, `FollowUpHistory.js`, `SettingsView.js` |
| Cross-links | Buttons that jump to another page, e.g. Dashboard → Job Portals, Freelance → Reply Today, Reports → Auto Scraper | props such as `onOpenLeads`, `onOpenScraper` |

**Why it is confusing**

- **No URLs.** All 54 pages share one route (`/`). Refresh resets the page, Back exits the app, and nothing can be shared or bookmarked.
- **Organised by tool, not by task.** The menu follows how the code was built: one page per scraper or utility. A user's day is "find, contact, follow up, close", and those steps sit in different sections.
- **One idea, many entry points.**
  - Leads waiting for contact appear in Lead Status, Reply Today, Follow-ups, Follow-up Watchlist and New Leads – Not Contacted.
  - Scraper runs appear in Run Scrapers, Auto Scraper, Freelance Projects and Reports › Scrapers.
- **Silent jumps.** The header search, the KPI cards and many cross-link buttons switch page with no visible cue.
- **System words in the UI.** Labels like "Dossier", "Senior Fit", "Data Health", "Pipeline" and "Lead Care" describe the system, not the user's goal.

## 3. Lead statuses and action pipeline

The UI shows three unrelated sets of status values, and only one of them answers "what is pending". There is no kanban: the lead list is a paged card list.

| Status set | Values | Where it shows | Stored in |
| --- | --- | --- | --- |
| Pipeline status | NEW, CONTACTED, REPLIED, MEETING, WON, LOST, DISQUALIFIED | A dropdown on every All Leads row, and Reports › Pipeline | `status` column, changed by hand |
| Email status | NOT_SENT, SENT, INVALID, INVALID_DOMAIN (+ BOUNCED, OPTED_OUT, UNVERIFIABLE) | Not on the row. Only counted in Daily Leads & Mail. | `email_status` column, set by the mailer |
| Score band | All Leads: a Hot (7–10) or "warm" badge. Reports and Follow-ups: High / Medium / Low / Not scored. | Score badge, pills, chips | `ai_score` |
| Next action (new) | Replied, Follow-up due, Call / WhatsApp pending, Message pending, No reply, Mail pending, Waiting, Post too old, No contact, Not a fit, Closed | The Lead Status page only | Worked out on each request in `lead_status.py` |

**Gaps and bugs**

- **Bug: "EMAIL_SENT" leads show as "NEW".**
  - The mailer writes `status = EMAIL_SENT`; 40 leads had it on 17 Nov.
  - The row dropdown's options (`PIPELINE_STAGES` in `LeadsTable.js`) do not include it, so the dropdown falls back to its first option.
- **Pending actions are invisible where users work.** All Leads, Dashboard and the Dossier never say "call pending" or "mail pending". Only the new Lead Status page does.
- **No Cold band.** Every score from 0 to 6 shows as "warm", and Hot/Warm/Cold is not a filter anywhere.
- **Contact logging is in several places**, and nothing shows one lead's full history:
  - the row dropdown logs a status change;
  - calls and WhatsApp are logged on Follow-ups, or with Lead Status' "Called" buttons;
  - emails sent from the modal are logged automatically.
- **Bulk WhatsApp opens only the first selected lead.** `onBulkWhatsAppOpen` in `page.js` picks `ids[0]`.

**Current counts** (Lead Status logic, 17 Nov, 1,897 leads):

| Group | Leads |
| --- | --- |
| Need a person | 531 (67 call/WhatsApp, 356 message on a post, 108 no reply) |
| Waiting for auto-mail | 120 |
| Waiting for a reply | 92 |
| No action needed | 1,154 |

## 4. Filters and reporting

The lead list, where users spend most of their time, has the weakest filters. The reports have good filters, but they sit on separate pages and do not link back to a list a user can act on.

**Filters available today**

| Screen | Date | Source | Status / stage | Score | Contact type | Next action | Search |
| --- | --- | --- | --- | --- | --- | --- | --- |
| All Leads | — | — | — | Hot pill only (≥7) | Has email, WhatsApp ready | — | Yes (+ header search) |
| Dashboard | — | — | — | KPI cards jump to All Leads | — | — | — |
| Lead Status | — | Yes | — | 5 bands | via stage | Yes (11 stages) | Yes |
| Reports (most pages) | 7 presets + custom range | Yes | Pipeline stage | Daily Leads only | — | — | — |
| Follow-ups | Due bucket (overdue, today, 7 days, later) | — | — | 4 bands | — | — | Yes |

All Leads also has "Senior match" and "High deal fit" pills. They filter on AI guesses (`seniority_fit`, `deal_size_estimate`), not on anything a user acts on.

**Reports that exist**

| Report | What it shows |
| --- | --- |
| Overview | 12 KPI cards, each compared with the previous period: total, new, hot, contacted, replied, meetings, won, lost, emails sent, scraper runs, scraper failures, overdue follow-ups. Also a daily leads vs. emails bar chart. |
| Daily Leads & Mail | Per day: found, mail sent, pending, no email, invalid. Split by score band, with click-through to the leads. |
| Lead Status | Count per next-action stage, with a click-through list that has contact buttons |
| Pipeline | Count and share per pipeline stage, and leads stuck over 14 days |
| Outreach | Sends, replies, bounces, do-not-contact blocks, per subject |
| Sources | Per source: leads, email %, phone %, hot %, average score, contacted, replied, reply rate, meetings, won |
| Scrapers | Runs, duration, records, new leads, duplicates, failures |
| Follow-up Watchlist / Not Contacted / Reply Today | Lead lists waiting for a contact |
| Data Health | Missing email, phone, website and duplicates, with samples |
| Daily Log | Timeline of one day's events |

**Missing views**

- A next-action filter on the main lead list: pending mail, call, WhatsApp, message, follow-up due.
- Hot / Warm / Cold as one consistent band everywhere, including Cold.
- On All Leads: date-found, source and pipeline-stage filters, plus saved views ("My hot calls this week").
- A per-lead timeline: every mail, call, message, reply and status change.
- A funnel (found → contacted → replied → meeting → won) showing drop-off, per source and per week.
- A daily summary for each person, shown on landing: "today you have N calls, N replies, N follow-ups".
- Owner or assignee. Nothing records who handles a lead, so a team cannot split the work.

## 5. Components and data flow

The frontend is one Next.js page with no router. It loads the whole leads list into the browser and filters it there; the reports are computed on the Flask side.

| Role | Components (`frontend/`) | Data source |
| --- | --- | --- |
| Shell and routing | `app/page.js` (580 lines: the `activeTab` switch, all modals, toasts), `Sidebar.js`, `Header.js`, `AuthScreen.js` | `GET /api/leads`, once on load and again after changes |
| a) Dashboard / overview | `Dashboard.js` (hot leads + leads by source), `StatsCards.js` (4 KPI cards, also on All Leads) | The leads array held in the browser |
| b) Lead detail / action | `AILeadDossierModal.js` (read-only AI profile), `SingleEmailModal.js`, `BulkEmailModal.js`, `WhatsAppModal.js`. Row actions in `LeadsTable.js`. `reports/LeadStatusTab.js` (contact buttons + "Called / Mailed" logging). | `/api/leads/send-email`, `/api/leads/bulk-email`, `PATCH /api/leads/<id>/status`, `/api/reports/lead-status/done` |
| c) Filters and search | `LeadsTable.js` (`FILTER_RULES`, pills, search, paging), `Header.js` (global search), the filter bar in `Reports.js`, chips in `FollowUpHistory.js` and `LeadStatusTab.js` | Filtered in the browser for All Leads; query strings for reports |
| d) Reports / analytics | `Reports.js` (section switch + date/source/stage filters) and 10 tabs in `components/reports/` (`OverviewTab`, `DailyLeadsTab`, `LeadStatusTab`, `PipelineTab`, `OutreachTab`, `SourcesTab`, `ScrapersTab`, `FollowupsTab`, `DataHealthTab`, `DailyLogTab`), plus `ReplyToday.js` | `/api/reports/*` (`reports_engine.py`, `daily_leads_report.py`, `lead_status.py`) |
| Follow-ups | `FollowUpHistory.js` (720 lines), `FollowUpSequences.js` | `/api/followups/*`, `logs/followup_activity.csv` |
| Unused | `Navbar.js` (not imported anywhere) | — |

**Data flow**

1. Scrapers write `all_leads_master.csv` and then sync it to the Supabase `app_data` table. They run hourly on GitHub Actions, or from the PC cron engine.
2. Flask reads the CSV through `read_leads()`. `GET /api/leads` returns all ~1,900 rows in one response.
3. `page.js` keeps them in `leads` state. `StatsCards`, `Dashboard` and `LeadsTable` filter and count in the browser.
4. Actions (email, status change, activity log) call Flask, which updates the CSV and the activity log. The page then reloads the whole list.
5. Each report calls its own endpoint. The endpoint combines the leads with `logs/sent_emails.csv`, `logs/followup_activity.csv` and `logs/scraper_runs.csv` on every request.

Loading the full list is fine at 1,900 rows. It will slow the browser past roughly 20,000, so filtering, paging and counts should move to the server before then.

## Redesign priorities

Make one "Today" inbox the landing page, and the lead list the single place to act. Move the tools out of the way.

1. **Land on a to-do, not charts.** Replace Dashboard with the Lead Status counts (reply, follow-up, call, message, no reply) and the top items of each.
2. **One status model.**
   - Show the next action and a Hot / Warm / Cold band on every lead row and in the lead details view.
   - Keep the pipeline dropdown for the outcome only: Replied, Meeting, Won, Lost.
   - Fix the EMAIL_SENT display bug.
3. **One lead list with real filters:** next action, band, source, date found, pipeline stage, contact type and saved views, with paging on the server.
4. **A lead drawer instead of the Dossier modal.** One panel beside the list with the profile, contact buttons, "log call / WhatsApp / message", the next follow-up date and the full timeline.
5. **A URL per page** (`/today`, `/leads?stage=call_pending`, `/reports/sources`), so refresh, Back and sharing work.
6. **Fold the tools away.**
   - Merge Not Contacted, Follow-up Watchlist and Reply Today into the inbox.
   - Put the 18 source forms and the web/domain tools on one "Tools" page.
7. **Name things by the user's goal.** "Dossier" → "Lead details"; "Data Health" → "Missing contact details"; drop the "Senior Fit" and "Deal Fit" cards.

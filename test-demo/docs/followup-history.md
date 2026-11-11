# FollowUp History — Module Guide (Phase 1)

**Module:** FollowUp History · **Status:** QA passed (see `reports/qa/2026-11-11-followup-history.md`) · **Updated:** 2026-11-11

---

## English

### Purpose
- One place for **every contact with a lead** and **who to follow up with next**.

### Where
- Sidebar → **3. FollowUp History**.

### Screens
| Part | What it does |
|---|---|
| Summary cards | Overdue · Due today · Next 7 days · Activities in last 7 days (click to filter) |
| **Follow-up Queue** | Pending follow-ups: All / Overdue / Today / Next 7 days / Later. Actions: **Done**, **Reschedule** (+1 / +3 / +7 days or pick a date) |
| **Activity History** | Newest-first feed of all activity. Filter by type, search by lead / email / text, 50 per page + **Load more** |
| **Timeline** (click a lead) | Lead details, next follow-up (Done / Reschedule), full history, **Log activity** for that lead |
| **Log activity** | Lead (search) · type (Call / Meeting / WhatsApp / Email / Note) · when · summary (max 300) · details (max 2000) · next follow-up (None / +3 / +7 / +14 days / pick date) + note |
| **Import past emails** | Copies `logs/sent_emails.csv` into the history once. Safe to click again (no duplicates) |

### Logged automatically
- Email sent from the dashboard (single and bulk), auto-outreach (`run_all_scrapers.py`) and importer outreach — with subject and message.
- Pipeline status change in the Leads table, e.g. `Status: NEW → CONTACTED`.
- Not automatic yet: WhatsApp (log it by hand), replies, calls.

### Rules
- One pending follow-up per lead: planning a new one cancels the old one.
- Follow-up date: today up to 1 year ahead. A date without a time = 10:00.
- Activity date cannot be in the future.
- Each row keeps the lead's name/email at that time, so history stays readable if leads change.

### Technical
| Item | Value |
|---|---|
| Backend | `followup_store.py` |
| Storage | `logs/followup_activity.csv` (new file; the leads master file is **not** changed) |
| API (login required) | `GET /api/followups/summary`, `GET /api/followups/queue?bucket=`, `GET /api/followups/history`, `GET /api/leads/<id>/timeline`, `POST /api/followups/activities`, `POST /api/followups/schedule`, `PATCH /api/followups/<id>`, `POST /api/followups/import-sent-emails` |
| Frontend | `components/FollowUpHistory.js` |
| Tests | `test_followups.py` (25 tests) |
| New dependencies | none |

### Phase 2 — Sequences, Gmail replies, Report (built 2026-11-11)
| Part | What it does |
|---|---|
| **Sequences** tab | Follow-up emails that are due now (day 3 / 7 / 14 after the first email, max 3). Preview each email, **Send selected** (asks for confirmation), or **Stop** a lead's sequence (with reason) |
| Auto-send | **OFF by default.** `FOLLOWUP_AUTO_SEND=true` → the hourly run sends up to `FOLLOWUP_MAX_PER_RUN` (10) |
| **Check replies now** | Reads the Gmail inbox (read-only, IMAP). Logs replies, "stop/unsubscribe/not interested" (opt-out) and bounces. Reply → lead status `REPLIED` (only from NEW / CONTACTED / EMAIL_SENT). Bounce → email status `INVALID` |
| **Report** tab | Leads contacted, replied, reply rate, follow-ups sent, replied after a follow-up, bounced, asked to stop — overall and per lead source |

Safety rules:
- A sequence stops for good on reply, bounce, opt-out, manual stop, or status `REPLIED` / `MEETING` / `WON` / `LOST` / `DISQUALIFIED`.
- Only first emails from the last 30 days; a step more than 7 days late is skipped (no burst of old follow-ups); at least 2 days between two emails.
- Every follow-up ends with: "If you'd rather not hear from us, just reply STOP…".
- A lead name that looks like a post title is not used in the email ("your team" instead).
- Only subject + first 500 characters of a reply are stored.

Settings: `FOLLOWUP_AUTO_SEND`, `FOLLOWUP_SEQUENCE_DAYS`, `FOLLOWUP_MAX_PER_RUN`, `FOLLOWUP_MAX_AGE_DAYS`, `IMAP_USER`, `IMAP_PASSWORD` (Gmail App Password; defaults to `SMTP_USER` / `SMTP_PASS`).
Code: `followup_sequence.py`, `reply_checker.py`, `components/FollowUpSequences.js`. API: `GET /api/followups/sequence`, `POST /api/followups/sequence/send`, `POST /api/followups/sequence/stop`, `POST /api/followups/check-replies`, `GET /api/followups/report`. Tests: `test_followup_phase2.py` (34).

### Extras (2026-11-11)
- **WhatsApp auto-log:** opening a WhatsApp chat from the dashboard adds a `whatsapp` entry ("WhatsApp chat opened (+91 …)"). We can only know it was opened, not sent.
- **Edit templates:** Sequences → **Edit templates**. 3 templates (Follow-up 1, 2, Final). Allowed placeholders `{name}` `{company}` `{original_subject}` `{first_date}`; anything else is rejected. **Reset to default** available. Saved in `followup_templates.json`. API: `GET/PUT/DELETE /api/followups/templates`.
- App-wide fixes: toasts now show; mobile sidebar works as a drawer; header shows the right page title; email HTML is escaped; local one-click login (`X-Demo-User`) works only when the server is bound to localhost (`LOCAL_DEMO_LOGIN=false` turns it off).

---

## ગુજરાતી

### હેતુ
- Lead સાથેનો **દરેક સંપર્ક** અને **હવે કોને follow-up કરવાનું છે** — બધું એક જગ્યાએ.

### ક્યાં છે
- Sidebar → **3. FollowUp History**.

### Screens
| ભાગ | શું કરે છે |
|---|---|
| Summary cards | Overdue · આજે · આવતા 7 દિવસ · છેલ્લા 7 દિવસની activities (click કરવાથી filter) |
| **Follow-up Queue** | બાકી follow-ups: All / Overdue / Today / Next 7 days / Later. Actions: **Done**, **Reschedule** (+1 / +3 / +7 દિવસ અથવા તારીખ પસંદ કરો) |
| **Activity History** | બધી activity, નવી પહેલાં. Type પ્રમાણે filter, lead / email / લખાણ થી search, પાને 50 + **Load more** |
| **Timeline** (lead પર click) | Lead ની વિગત, આગલો follow-up (Done / Reschedule), આખી history, એ lead માટે **Log activity** |
| **Log activity** | Lead (search) · type (Call / Meeting / WhatsApp / Email / Note) · ક્યારે · summary (300 સુધી) · details (2000 સુધી) · આગલો follow-up (None / +3 / +7 / +14 દિવસ / તારીખ) + note |
| **Import past emails** | `logs/sent_emails.csv` ને એક વાર history માં લાવે. ફરી click કરો તો duplicate નહીં બને |

### આપોઆપ log થાય છે
- Dashboard થી મોકલેલો email (single અને bulk), auto-outreach (`run_all_scrapers.py`) અને importer outreach — subject અને message સાથે.
- Leads table માં pipeline status બદલાય, જેમ કે `Status: NEW → CONTACTED`.
- હજુ આપોઆપ નહીં: WhatsApp (હાથથી log કરો), replies, calls.

### નિયમો
- એક lead નો એક જ બાકી follow-up: નવો નક્કી કરો તો જૂનો cancel થાય.
- Follow-up તારીખ: આજથી 1 વર્ષ સુધી. સમય વગરની તારીખ = 10:00.
- Activity ની તારીખ ભવિષ્યની ન હોઈ શકે.
- દરેક row એ સમયનું lead નું નામ/email સાચવે છે, જેથી lead બદલાય તો પણ history વાંચી શકાય.

### Technical
| વિગત | માહિતી |
|---|---|
| Backend | `followup_store.py` |
| Storage | `logs/followup_activity.csv` (નવી file; leads ની master file **બદલાતી નથી**) |
| API (login જરૂરી) | ઉપરના English ટેબલ મુજબ |
| Frontend | `components/FollowUpHistory.js` |
| Tests | `test_followups.py` (25 tests) |
| નવી dependencies | કોઈ નહીં |

### Phase 2 — Sequences, Gmail replies, Report (2026-11-11 બન્યું)
| ભાગ | શું કરે છે |
|---|---|
| **Sequences** tab | અત્યારે due follow-up emails (પહેલા email પછી દિવસ 3 / 7 / 14, વધુમાં વધુ 3). દરેક email નો preview, **Send selected** (પુષ્ટિ પૂછે છે), અથવા lead નો sequence **Stop** (કારણ સાથે) |
| Auto-send | **Default OFF.** `FOLLOWUP_AUTO_SEND=true` → hourly run વધુમાં વધુ `FOLLOWUP_MAX_PER_RUN` (10) મોકલે |
| **Check replies now** | Gmail inbox વાંચે (ફક્ત વાંચે, IMAP). Reply, "stop/unsubscribe/not interested" (opt-out) અને bounce log કરે. Reply → lead status `REPLIED` (ફક્ત NEW / CONTACTED / EMAIL_SENT માંથી). Bounce → email status `INVALID` |
| **Report** tab | Contact કરેલી leads, reply, reply rate, follow-ups, follow-up પછી reply, bounce, stop — કુલ અને lead source પ્રમાણે |

સલામતી ના નિયમો:
- Reply, bounce, opt-out, હાથથી stop, અથવા status `REPLIED` / `MEETING` / `WON` / `LOST` / `DISQUALIFIED` થાય તો sequence કાયમ માટે બંધ.
- ફક્ત છેલ્લા 30 દિવસના પહેલા emails; 7 દિવસથી વધુ મોડું step skip (જૂના follow-ups નો ઢગલો નહીં); બે emails વચ્ચે ઓછામાં ઓછા 2 દિવસ.
- દરેક follow-up ના અંતે: "…reply STOP…" લીટી.
- Post ના title જેવું lead નામ email માં વપરાતું નથી ("your team" વપરાય).
- Reply નો ફક્ત subject + પહેલા 500 અક્ષર સચવાય.

Settings, code, API અને tests ઉપરના English ભાગ મુજબ.

### વધારાના ફેરફારો (2026-11-11)
- **WhatsApp આપોઆપ log:** Dashboard થી WhatsApp chat ખોલો એટલે `whatsapp` entry બને ("WhatsApp chat opened (+91 …)"). ફક્ત ખોલ્યું એટલું જ ખબર પડે, મોકલ્યું કે નહીં તે નહીં.
- **Templates edit:** Sequences → **Edit templates**. 3 templates (Follow-up 1, 2, Final). ફક્ત `{name}` `{company}` `{original_subject}` `{first_date}` placeholders ચાલે; બીજું હોય તો save નહીં થાય. **Reset to default** છે. `followup_templates.json` માં સચવાય.
- આખી app ના સુધારા: toasts દેખાય છે; mobile પર sidebar drawer તરીકે ખૂલે છે; header માં સાચું page નામ; email HTML escape; local one-click login (`X-Demo-User`) ફક્ત localhost server પર ચાલે (`LOCAL_DEMO_LOGIN=false` થી બંધ).

# QA Report — FollowUp Phase 2 (Sequences, Gmail replies, Report)

**Date:** 2026-11-11 · **Build:** uncommitted working tree on `master` · **Result:** PASSED (open items below)

---

## English

### 1. Automated tests (Python, no network, no real email)
| Suite | Result |
|---|---|
| `test_followup_phase2.py` (new) | 34/34 pass |
| Full regression (11 suites) | **168/168 pass** |

Covers: due dates (day 3/7/14), step progress and finish, 2-day gap, late steps skipped (no burst), 30-day age limit, every stop condition (reply, bounce, opt-out, manual stop, status), old reply before first email ignored, settings parsing, email text (date, opt-out line, post-title names replaced, wording when steps were skipped), sending (success logged, failures and exceptions not logged, limit), Gmail parsing (reply, opt-out phrases, quoted "STOP" in our own text ignored, bounce, unrelated sender, HTML-only mail), fake IMAP (read-only, incremental by UID, dedupe by Message-ID, login error), status never downgraded (MEETING stays), report numbers, import does not duplicate app-logged emails, all new API endpoints (401 / 400 / 502), hourly runner with auto-send OFF and ON.

### 2. End-to-end UI test (Playwright, real browser, real data) — 8/8 pass
SMTP and IMAP were switched off on the backend for this test, so **no email could be sent**.
| ID | Test | Result |
|---|---|---|
| P2-01 | Sequences and Report tabs present | PASS |
| P2-02 | Settings shown; auto-send OFF; Gmail "not set up"; 45 due follow-ups after importing past emails | PASS |
| P2-03 | Email preview: first-email date + opt-out line | PASS |
| P2-04 | Send asks "They go to real people" and fails safely without SMTP | PASS |
| P2-05 | Stop sequence: removed from due list, logged with reason | PASS |
| P2-06 | Report: 198 leads contacted, 18 source rows | PASS |
| P2-07 | 390 px width: no horizontal scroll | PASS |
| P2-08 | No unexpected console errors | PASS |

QA data removed afterwards: `logs/followup_activity.csv` and `logs/imap_state.json` deleted, `all_leads_master.csv` restored (md5 verified identical).

### 3. Bugs found in QA and fixed
| Bug | Fix |
|---|---|
| Email said "Wishing Show HN: Structured search for Who is hiring threads all the best" (lead names are often post titles) | Names that look like post titles → "your team" |
| When early steps were skipped, the first follow-up said "Checking in once more" | Wording now follows how many follow-ups were really sent; last step always the closing note |

### 4. Not tested live (UNVERIFIED)
- Real Gmail IMAP login and a real reply/bounce: no App Password on this machine. Logic is covered by unit tests with a fake IMAP server.
- Real SMTP send of a follow-up: intentionally not done (would email real people).

### 5. Open items (need your decision)
1. **45 follow-ups are due now** after importing past emails. Many of these "leads" are post titles / non-buyers (e.g. "Show HN: …"). **Review the list before turning on `FOLLOWUP_AUTO_SEND`.**
2. **Privacy:** replies (500-char snippets) are stored in `logs/followup_activity.csv`, which the hourly GitHub Action commits to the **public** repo.
3. `email_service.py` puts the message text into HTML without escaping (existing code); a lead name containing `<` could break the email layout.
4. Still open: global toast bug, mobile app shell, `X-Demo-User` auth bypass.

---

## ગુજરાતી

### 1. Automated tests (internet વગર, સાચો email વગર)
| Suite | પરિણામ |
|---|---|
| `test_followup_phase2.py` (નવું) | 34/34 pass |
| આખું regression (11 suites) | **168/168 pass** |

ચકાસ્યું: due તારીખો (3/7/14), steps, 2 દિવસનો ગાળો, મોડા steps skip, 30 દિવસની મર્યાદા, બધી stop શરતો, emails નું લખાણ, મોકલવું (સફળ log, નિષ્ફળ log નહીં), Gmail parsing (reply, opt-out, અમારા લખાણમાં quoted "STOP" ને અવગણ્યું, bounce), fake IMAP (ફક્ત વાંચે, duplicate નહીં), status ક્યારેય નીચે નથી જતો, report, નવા API, hourly runner (auto-send OFF અને ON).

### 2. End-to-end UI test (સાચું browser, સાચો data) — 8/8 pass
આ test દરમ્યાન backend માં SMTP અને IMAP બંધ રાખ્યા, એટલે **કોઈ email જઈ શકે તેમ નહોતો**. P2-01 થી P2-08 બધા PASS (ઉપરના ટેબલ મુજબ). QA data પછી દૂર કર્યો અને `all_leads_master.csv` પાછી મૂકી (md5 સરખો).

### 3. QA માં મળેલા અને સુધારેલા bugs
| Bug | સુધારો |
|---|---|
| Email માં "Wishing Show HN: … all the best" (lead નામ ઘણી વાર post નું title હોય છે) | Post title જેવું નામ → "your team" |
| શરૂઆતના steps skip થાય ત્યારે પહેલો follow-up "Checking in once more" કહેતો | હવે ખરેખર મોકલેલા follow-ups પ્રમાણે શબ્દો; છેલ્લો step હંમેશા closing note |

### 4. Live ચકાસ્યું નથી (UNVERIFIED)
- સાચું Gmail IMAP login અને સાચો reply/bounce: આ machine પર App Password નથી. Logic fake IMAP server થી unit tests માં ચકાસ્યું.
- Follow-up નો સાચો SMTP send: જાણી જોઈને કર્યો નથી (સાચા લોકોને email જાય).

### 5. બાકી મુદ્દા (તમારો નિર્ણય જોઈએ)
1. જૂના emails import કર્યા પછી **45 follow-ups અત્યારે due છે.** એમાંની ઘણી "leads" post titles / buyers નથી (જેમ કે "Show HN: …"). **`FOLLOWUP_AUTO_SEND` ચાલુ કરતા પહેલા list જુઓ.**
2. **Privacy:** replies (500 અક્ષર) `logs/followup_activity.csv` માં સચવાય છે, જેને hourly GitHub Action **public** repo માં commit કરે છે.
3. `email_service.py` message ને escape કર્યા વગર HTML માં મૂકે છે (જૂનો code); `<` વાળું lead નામ email ની ડિઝાઇન બગાડી શકે.
4. હજુ બાકી: toast bug, mobile layout, `X-Demo-User` auth bypass.

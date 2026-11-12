# QA Report — Bulk Contacts

**Date:** 2026-11-12 · **Build:** uncommitted working tree on `master` · **Result:** PASSED.

## English

### 1. Scope
The owner could not recall the submenus of the earlier app, and no list was found in the repository. The owner then chose these four: **Bulk Website Contacts**, **Bulk Email Verifier**, **Bulk Phone Cleaner** and **Contact Import & Dedupe**.

### 2. Automated tests (Python, no network)
| Suite | Result |
|---|---|
| `test_bulk_contacts.py` (new) | 14/14 |
| Full regression (27 suites) | **437/437** |

**What the new tests cover:**
- **E-mail:** every status, the typo hint, null MX, a no-answer domain (A-only), a timeout with one retry, one lookup per domain, "in leads", and limits.
- **Phones:** 11 formats (mobile with 0 / +91 / dashes; landline 079, 022 and 011 with a separate STD code; toll-free; international; fake; short), duplicates, text extraction, "in leads".
- **CSV:**
  - header guessing (comma and semicolon files), the mapping rules, file limits
  - statuses: new, partial (bad e-mail kept), in-file duplicate, in leads, company-only
  - **spreadsheet line numbers kept** across blank rows
  - save, then no double save
- **Websites:** de-duplication by domain, platform pages never crawled, a private address blocked, limits.
- **API:** 401 without login and 400 on bad input (all 7 endpoints); import → save → re-check shows 0 new; a request over 6 MB is refused.

### 3. Browser QA (Playwright, real backend, **live DNS and websites**) — 7/7 pass
| ID | Test | Result |
|---|---|---|
| BC01 | Sidebar group "Bulk Contacts" with 4 items; breadcrumb; empty-input validation. | PASS |
| BC02 | E-mails (live DNS): gmail = **valid**, info@infosys = **risky** (role), gmial.com = invalid + "Did you mean", mailinator = invalid, unknown domain = invalid, upper-case repeat = **duplicate**, `bad@@x` = invalid. | PASS |
| BC03 | Phones: text with 2 numbers on one line → `+91 98250 12345` (mobile), `079-2654 3210` (landline); `0982…` marked duplicate; the filter works. | PASS |
| BC04 | Websites (live): mokobara.com → 3 e-mails; python.org → socials only; facebook.com → **skipped**; non-existent domain → error. Save → 1 new lead. | PASS |
| BC05 | CSV import: 7 columns mapped automatically; "2 new, 1 already in Leads, 1 repeated in the file". Save 2 → source `Bulk Contacts (bc_import)`. Re-check → **0 new**. | PASS |
| BC06 | CSV export; mobile at 390 px, no sideways scroll. | PASS |
| BC07 | No console errors. | PASS |

### 4. Bugs found and fixed during the build
1. **Landline vs mobile.** `079-26543210` was read as a mobile number, and Delhi `011-…` numbers were rejected. A separate STD code now means a landline.
2. **CSV line numbers** shifted after a blank row. The real spreadsheet line numbers are now kept.
3. **Company-only rows** were never matched with existing leads. The import now also matches on company + city, the same rule the leads registry uses when saving.
4. **DNS timeouts.** The home router sometimes timed out on gmail.com when several queries ran at once (seen in one QA run). There is now one retry and fewer parallel lookups. The rerun passed, and an unanswered domain is honestly shown as "unknown".

### 5. Known limits (by design)
- "Valid" e-mail = the domain accepts mail. Mailboxes are not probed over SMTP.
- Excel files must be saved as CSV first (no new dependency was installed).

### 6. Data safety
- `all_leads_master.csv` was restored after QA (md5 `963d94bc…` matches).
- SMTP, IMAP and Supabase were off during QA. No e-mails were sent.

## ગુજરાતી
- **Tests:** browser QA 7/7 pass અને unit tests 437/437 pass.
- **Live પરિણામ:**
  - Email check માં gmail valid આવ્યું, info@ "risky" આવ્યું, અને gmial.com પર "Did you mean gmail.com" સૂચન દેખાયું.
  - Website tool થી mokobara.com પરથી 3 emails મળ્યા.
  - CSV import એ duplicate અને પહેલેથી Leads માં હોય એવા contacts સાચા પકડ્યા.
- **4 bugs fix થયા:** landline ની ઓળખ, CSV line numbers, company-only match, અને DNS retry.

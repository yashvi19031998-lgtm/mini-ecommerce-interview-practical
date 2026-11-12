# Bulk Contacts — Module Guide

**Status:**
- **QA passed:** live (2026-11-12).
- QA report: `reports/qa/2026-11-12-bulk-contacts.md`. **Updated:** 2026-11-12.

---

## English

### Purpose
Four tools for contact lists you **already have**, from an expo, a purchased list or an old Excel file. They find, check, clean and de-duplicate the contacts before they become leads. **Nothing here sends e-mails or messages.**

### Menus
| Menu | Input | Output |
|---|---|---|
| **Bulk Website Contacts** | Up to 200 website addresses (sent 10 at a time, with progress) | e-mails, phones, social links and address from each site's homepage and contact pages. Save chosen sites as leads. |
| **Bulk Email Verifier** | Up to 500 e-mail addresses | **valid** / **risky** / **unknown** / **invalid** / **duplicate**, with the reason. Typo hints ("did you mean x@gmail.com?"). Role / free-mail / disposable tags. "In leads" flag. |
| **Bulk Phone Cleaner** | Up to 1,000 numbers, or any text containing numbers | Clean `+91` numbers; Mobile / Landline / Toll-free / International. Fake (repeated / sequential) and duplicate numbers marked. "In leads" flag. Works offline. |
| **Contact Import & Dedupe** | A CSV file (≤ 5 MB, ≤ 5,000 rows) | Columns are guessed from the headers, and you can change them. Each row is then marked **new**, **in leads** (by email, phone, website or company + city), **duplicate** (repeated in the file) or **invalid**. Save only the new rows. |

### How the e-mail check works (and what it does not do)
1. **Format and duplicates** (case-insensitive).
2. **Typos** of common providers, e.g. `gmial.com` → `gmail.com`.
3. **No-reply** addresses and **disposable** (temporary) mailboxes are marked invalid.
4. **DNS:** does the domain accept e-mail? It checks the MX record; a domain that does not exist, or that publishes a "null MX", is invalid. The lookup is made once per domain, with one retry, because home routers sometimes drop a query.
5. **Role addresses** (`info@`, `sales@`…) are **risky**. They are fine for B2B, but get fewer replies.

**Not done:** connecting to the mail server to "probe" a mailbox (SMTP RCPT). Many servers accept everything or block probing, and probing gets the sending IP blacklisted. "Valid" therefore means *the domain accepts e-mail*, not *the mailbox surely exists*.

### Phone rules
- `98250 12345`, `+91-98250-12345` and `09825012345` are the same **mobile** number, `+919825012345`.
- A separate STD code (`079-2654 3210`, `(022) 2555 1234`, `011 2345 6789`) means a **landline**, even when the code starts with 7 or 8.
- `1800…` / `1860…` numbers are **toll-free**. Numbers with another `+` country code are **international**.

### CSV import
- **Excel files:** File → Save As → CSV first. No extra library is needed then; installing one would need the owner's approval.
- **Saved leads:**
  - source `Bulk Contacts (<source name>)`; the source name defaults to the file name
  - lead type `Imported Contact`
- **Line numbers** in the results are the spreadsheet's own; blank rows are skipped but keep the numbering.

### Technical
| Item | Value |
|---|---|
| Backend | `bulk_contacts.py` (website crawl = `deep_search.crawl_site`: URL guard, HTML cache, honest User-Agent) |
| API (login required) | `GET /api/bulk-contacts`, `POST /api/bulk-contacts/{websites,emails,phones}`, `POST …/import/preview`, `POST …/import/check`, `POST …/save` (kind `import` or `websites`). Requests are limited to 6 MB. |
| Frontend | `BulkContacts.js` (prop `tool`), sidebar group **Bulk Contacts** (`BULK_ITEMS`) |
| Tests | `test_bulk_contacts.py` (14 tests, in hourly CI). DNS and websites are faked. |

---

## ગુજરાતી

### હેતુ
તમારી પાસે **પહેલેથી હોય** એવી contact યાદીઓ (expo, ખરીદેલી list, જૂની Excel) માટે 4 tools. Leads માં મૂકતાં પહેલાં contacts ને શોધે, તપાસે, સાફ કરે અને duplicate કાઢે છે. **કોઈ email કે message મોકલાતો નથી.**

### Menus
- **Bulk Website Contacts:** ઘણી websites આપો, દરેકમાંથી email, phone અને social links મળશે.
- **Bulk Email Verifier:** email સાચો છે કે નહીં તપાસે છે: format, typo (gmial.com → gmail.com), temporary email, અને domain mail સ્વીકારે છે કે નહીં.
  - Mailbox ને SMTP થી "probe" નથી કરતું, કારણ કે એનાથી તમારું IP blacklist થઈ શકે છે.
- **Bulk Phone Cleaner:** numbers ને +91 format માં કરે છે, mobile કે landline ઓળખે છે, અને નકલી તથા duplicate numbers કાઢે છે.
- **Contact Import & Dedupe:** CSV upload કરો. Columns આપોઆપ ઓળખાય છે. પછી કયા contacts નવા છે, કયા પહેલેથી Leads માં છે અને કયા file માં બે વાર છે એ દેખાય છે. ફક્ત નવા contacts save કરો.

### ધ્યાન રાખવું
Excel file ને પહેલાં **CSV** તરીકે save કરો (File → Save As → CSV).

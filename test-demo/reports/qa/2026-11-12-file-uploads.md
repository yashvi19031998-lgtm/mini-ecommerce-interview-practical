# QA Report — File Uploads

**Date:** 2026-11-12 · **Build:** uncommitted working tree on `master` · **Result:** PASSED, with the item listed in section 5.

## English

### 1. Scope and approvals
- **Chosen by the owner:** Excel, vCard, Word, e-mail files, PDF and visiting-card OCR.
- **`pypdf` 6.21.4 installed:** into the project venv and added to `requirements.txt` (`pypdf>=5,<7`). The owner chose the PDF option, which stated that this install was needed.
- **Tesseract OCR not installed:** it is a system program, so it waits for the owner's explicit approval.

### 2. Automated tests (Python, no network)
| Suite | Result |
|---|---|
| `test_file_uploads.py` (new) | 16/16 |
| Full regression (29 suites) | **465/465** |

**What the new tests cover:**
- **Input:** bad type, an old `.xls`, an empty file, bad base64, over 10 MB, a data-URL prefix.
- **Excel:** shared strings, inline strings, `9825044444.0` → digits, gaps kept, two sheets, header-only sheet refused.
- **Security:** a **DOCTYPE / ENTITY file refused**; **an oversized ZIP part refused unread**.
- **Word:** blocks plus table rows; a `.co.in` e-mail kept; a landline kept as `079-26543210`.
- **vCard:** v3 and v2.1, folded lines, quoted-printable, `item1.` prefixes, duplicates.
- **E-mail:** `.eml` sender + signature; `.mbox` with no-reply skipped.
- **PDF:** a text PDF; a scanned (no text) PDF and a broken PDF give clear errors.
- **Text and images:** `.txt`; image without OCR → message; image with OCR (mocked) → contact.
- **Normaliser:** multi-part e-mail domains.
- **API:** 401, 400, parse → save → re-parse shows "in leads"; a request over 15 MB refused.

### 3. Browser QA (Playwright, real backend, sample files) — 9/9 pass
| ID | Test | Result |
|---|---|---|
| FU01 | Page, 6 type groups; "Card photo — needs Tesseract" shown. | PASS |
| FU02 | vCard → 2 new + 1 repeated in the file. | PASS |
| FU03 | Word (2), PDF (1), mbox (2, no-reply skipped), eml (1), txt (1) contacts found. | PASS |
| FU04 | Word: `amit@qa-gamma.co.in` kept; `079-26543210` kept as a landline. | PASS |
| FU05 | Excel → columns matched automatically → check → save 2 → source `Bulk Contacts (members)`. | PASS |
| FU06 | Save the PDF contact; uploading it again shows "already in Leads". | PASS |
| FU07 | Unsupported type and "OCR not installed" messages. | PASS |
| FU08 | Mobile at 390 px, no sideways scroll. | PASS |
| FU09 | No console errors. | PASS |

### 4. Bugs found and fixed
1. **Shared, affected every source:** `normalize_email` dropped every e-mail on a multi-part domain (`.co.in`, `.org.in`, sub-domains). The leads file has **0** `.co.in` e-mails, which confirms the old loss. Fixed and tested.
2. **Landlines found in files** were saved in mobile format (`+91 79265 43210`). They now stay `079-26543210`.
3. **UI:** the "Show:" / "View" / "Network" dropdowns had clipped text (fixed height with large padding) in Bulk Contacts, Web Crawler and Social Media.

### 5. NOT ACTIVE
| Item | Why |
|---|---|
| Visiting-card OCR | Needs Tesseract OCR (system program, about 100 MB) plus `pytesseract` and `Pillow`. Waiting for the owner's approval. The code path is tested with a mocked OCR. |

### 6. Data safety
- `all_leads_master.csv` was restored after QA (md5 `963d94bc…` matches).
- SMTP, IMAP and Supabase were off during QA.
- Only fictional sample data was used.

## ગુજરાતી
- **Tests:** browser QA 9/9 pass અને unit tests 465/465 pass.
- **શું ચાલે છે:** Excel, vCard, Word, email, PDF અને text, બધામાંથી contacts મળ્યા.
- **મહત્ત્વનો સુધારો:** `.co.in` વાળા emails આખી app માં નીકળી જતા હતા. હવે સાચા save થાય છે.
- **હજી ચાલુ નથી:** Visiting card OCR. એ માટે Tesseract install કરવું પડશે, અને એ તમારી મંજૂરી પછી જ થશે.

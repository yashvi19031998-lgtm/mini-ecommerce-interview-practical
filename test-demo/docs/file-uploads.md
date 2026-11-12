# File Uploads — Module Guide

**Status:**
- **QA passed:** Excel, vCard, Word, e-mail (.eml / .mbox), PDF, text and HTML (2026-11-12).
- **NOT ACTIVE:** visiting-card photos (OCR). They need Tesseract OCR, which is not installed yet (see below).
- QA report: `reports/qa/2026-11-12-file-uploads.md`. **Updated:** 2026-11-12.

---

## English

### Purpose
Turn the contacts inside files you already have into leads. Examples: an Excel list, phone contacts, an expo catalogue, a brochure, an e-mail inbox or a visiting card. Before anything is saved you see which contacts are new, already in Leads, repeated in the file, or unusable.

### Supported files
| Type | Extensions | What is read |
|---|---|---|
| Excel | `.xlsx` | Each sheet (up to 10) becomes a table. It opens the **column-matching** screen (the same one as Contact Import), then you check and save. |
| vCard | `.vcf` | Phone / Outlook contact exports (v2.1 and v3): name, organisation, title, phones, e-mails, website, address. Folded and quoted-printable lines are handled. |
| Word | `.docx` | Paragraphs and table rows. Each block that has an e-mail or a phone becomes a contact. |
| E-mail | `.eml`, `.mbox` | The **sender**, plus the phone, website and company in the **signature** (last 15 lines). No-reply senders are skipped. Up to 2,000 messages. |
| PDF | `.pdf` | Text of each page (up to 100) → contact blocks. Scanned (image-only) and password-protected PDFs get a clear message. |
| Text / web page | `.txt`, `.html`, `.htm` | Contact blocks in the text. |
| Visiting card | `.jpg`, `.jpeg`, `.png`, `.webp` | **OCR**, only when Tesseract is installed; otherwise the page says so. |

**How a contact block becomes a lead:**
- **Emails, phones and website** are taken from the block.
  - Indian phones are cleaned; a landline keeps its STD code, e.g. `079-26543210`.
  - With no website, the business e-mail's domain is used (never Gmail and similar).
- **Company:** the line with a company word (Pvt, Ltd, LLP, Industries, Traders, Studio…), else the website's domain.
- **Person:** a 2–4-word capitalised name.
- **Title and address:** a title line (Director, Manager…) and an address line (6-digit pincode or Road / Nagar…).

### Safety limits
- **Size:** 10 MB per file. The file is read in memory and not kept; an `.mbox` uses a temporary file that is deleted at once.
- **Office files:**
  - Only the needed parts of the ZIP are read, each at most 30 MB unpacked (zip-bomb guard).
  - XML that contains a DOCTYPE / ENTITY is refused.
  - Old `.xls` / `.doc` files must be saved as `.xlsx` / `.docx`.
- **Contacts:** at most 2,000 per file.
- **Nothing is sent to anyone.** Saving uses the same rules as Contact Import (source `Bulk Contacts (<file name>)`, lead type `Imported Contact`).

### Visiting-card OCR (not active yet)
It needs the **Tesseract OCR** program (about 100 MB, installed on the computer) and two Python libraries (`pytesseract`, `Pillow`). They are not installed. Installing them needs the owner's approval. Until then the "Card photo" chip shows "needs Tesseract" and an upload explains why.

### Shared fix made with this module
`lead_normalizer.normalize_email` **dropped every e-mail on a multi-part domain** (`name@company.co.in`, `hr@mail.acme.org.in`), because the old pattern allowed only one dot after `@`. That affected every source. It now accepts them, and the current leads file has **no** `.co.in` e-mail, which confirms the old loss.

### Technical
| Item | Value |
|---|---|
| Backend | `file_uploads.py` (standard library + `pypdf`, newly added to `requirements.txt`); checking via `bulk_contacts.check_leads` |
| API (login required) | `GET /api/file-uploads` (types, OCR status), `POST /api/file-uploads/parse` (`{name, data: base64}`, ≤ 15 MB request). Save: `/api/bulk-contacts/save` (kind `import`). |
| Frontend | `FileUploads.js` (sidebar item **File Uploads**). Results and Excel mapping reuse `BulkContacts.js` through its new `preset` prop. |
| Tests | `test_file_uploads.py` (16 tests, in hourly CI) |

---

## ગુજરાતી

### હેતુ
તમારી પાસે હોય એવી files (Excel list, phone contacts, expo catalogue, brochure, emails, visiting card) માંથી contacts કાઢીને leads બનાવવા. Save કરતાં પહેલાં દેખાય છે કે કયા contacts નવા છે અને કયા પહેલેથી Leads માં છે.

### કઈ files ચાલે છે
- **Excel (.xlsx):** column મેળવવાની screen ખૂલે છે.
- **vCard (.vcf):** phone ના contacts નું export.
- **Word (.docx), Text, HTML.**
- **Email (.eml / .mbox):** મોકલનાર અને signature માંનો phone, website અને company.
- **PDF:** text વાળી PDF. Scan કરેલી (image) PDF નથી ચાલતી.
- **Visiting card photo:** હજી ચાલુ નથી. એ માટે Tesseract OCR install કરવું પડશે, અને એ તમારી મંજૂરી પછી જ થશે.

### મહત્ત્વનો સુધારો
અત્યાર સુધી `.co.in` વાળા emails (જેમ કે `name@company.co.in`) આખી app માં ચૂપચાપ નીકળી જતા હતા. હવે એ સાચા save થાય છે.

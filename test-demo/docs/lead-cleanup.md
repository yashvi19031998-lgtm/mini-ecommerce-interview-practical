# Lead Care → Data Cleanup — Module Guide

**Status:**
- **QA passed** (2026-11-12) on a copy of the real 921 leads. The cleanup was applied and then undone, so the file is byte-identical to before.
- **The owner has not applied it to the live data yet.**
- QA report: `reports/qa/2026-11-12-lead-cleanup.md`.

---

## English

### The rule: nothing old is ever deleted
- No lead (row) is removed, and **no filled value is changed or blanked**. Fixes only **fill empty fields**, using information that is already inside the same lead.
- **Dry run first:** the page shows every change (lead, field, new value, where it came from) before anything is written.
- **Apply:**
  - copies the whole leads file to `backups/all_leads_master_<time>.csv`
  - writes a change log `backups/cleanup_<time>.json`
  - never overwrites a field that was filled in the meantime
- **Undo** puts back exactly the logged fields (and their "last updated" date), but only where the value is still the one the cleanup wrote. Anything you edited later is left alone.
- The last 20 cleanup backups are kept. The existing `backups/pre_migration/` folder is untouched.

### Fixes
| Fix | Fills | From | Safety checks |
|---|---|---|---|
| Website from business e-mail | empty **website** | the lead's own e-mail domain | Not Gmail / Yahoo / Outlook…, not disposable, not a platform or junk domain, not a domain shared by 3+ different leads; the domain's name must appear in the lead (company, text or link) |
| E-mail in the description | empty **e-mail** | an address in the description / AI summary / requirement | not no-reply, not a shared (platform) domain; multi-part domains such as `.co.in` are kept |
| Phone in the description | empty **phone** | a valid Indian mobile in the same text | not a number shared by 3+ leads |

### Reports (nothing is changed)
- **Shared contacts:** the same e-mail, phone or domain on different leads. These are usually a job portal's contact (for example `jane@freelancer.com` on 8 Freelancer posts), not the client's. Check them by hand.
- **Format notes:** saved values that today's rules would write differently. They are shown only.

### First run on the real data (dry run, 2026-11-12)
- **921 leads:** 716 have no e-mail, 709 no phone and 714 no website. Those gaps need **Lead Enrichment** (Deep Search); cleanup cannot invent data.
- **Safe fixes:** 40 websites from business e-mails and 2 e-mails from descriptions (both `.co.*` addresses the old rules had dropped). There were 0 phones.
- **Reports:** 34 shared-contact groups and 1 format note.

### Fixed with this module: the leads file was being changed silently
Loading and saving the leads file used to rewrite every row through the **current** normalising rules. When a rule changed, old values changed or were **blanked** on the next save by any module or the hourly scraper. For example, a `.gov.in` website became empty, and a phone list was reformatted.

Now the stored values are kept exactly; the normalised copy is used only for duplicate matching. A plain load + save changes **0** cells (it changed 2 before).

### Technical
| Item | Value |
|---|---|
| Backend | `lead_cleanup.py`; `lead_normalizer.MasterLeadRegistry.load_master` (lossless) |
| API (login required) | `GET /api/lead-care/cleanup` (dry run), `POST …/apply` (`{fixes}`), `POST …/undo` (`{log_id}`). Writes hold the shared save lock. |
| Frontend | `LeadCleanup.js`, sidebar group **Lead Care** (`LEADCARE_ITEMS`) |
| Tests | `test_lead_cleanup.py` (8 tests, in hourly CI) |

---

## ગુજરાતી

### નિયમ: જૂનું કંઈ delete નહીં થાય
- **કોઈ lead કાઢવામાં નથી આવતી**, અને **ભરેલું કોઈ field બદલાતું કે ખાલી થતું નથી.**
- ફક્ત **ખાલી fields ભરાય છે**, અને એ પણ એ જ lead ની અંદર પહેલેથી લખેલી માહિતીમાંથી.
- પહેલાં **dry run** માં બધા ફેરફાર દેખાય છે. પછી Apply કરો ત્યારે:
  - આખી leads file નો **backup** બને છે.
  - દરેક ફેરફારનો **log** રહે છે.
  - **Undo** થી બધું પહેલાં જેવું થઈ જાય છે.

### શું ભરાય છે
- **Website:** lead ના business email ના domain પરથી (Gmail કે platform નહીં).
- **Email અને phone:** lead ના description માં લખેલાં હોય તો ત્યાંથી.

### મહત્ત્વનો સુધારો
અત્યાર સુધી leads file save થાય ત્યારે નિયમ બદલાયા હોય તો જૂની values ચૂપચાપ બદલાઈ કે ખાલી થઈ જતી હતી, જેમ કે `.gov.in` વાળી website. હવે file માં જે છે એ જ રહે છે.

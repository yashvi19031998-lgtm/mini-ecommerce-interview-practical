# Lead Care → Lead Enrichment — Module Guide

**Status:**
- **QA passed** (2026-11-12) on the real leads: enrich, save, then undo, and the file is byte-identical.
- **The owner has not saved any enrichment to the live data yet.**
- QA report: `reports/qa/2026-11-12-lead-enrichment.md`.

---

## English

### Purpose
Find the missing **e-mail, phone, website and website check** for leads you have **already saved**, then keep only what you approve.

### Flow
1. **Find leads.**
   - Filters:
     - what is missing (e-mail / phone / website / website check)
     - source contains…
     - how many (10 / 25 / 50 / 100)
     - "only leads that already have a website"
   - Directory and portal links (IndiaMART, LinkedIn, job boards) do not count as a website.
2. **Enrich.** The leads run 5 per request, with progress and a **Stop** button:
   - **Deep Search:**
     - website from the lead or found by company name (search engine)
     - crawl of the homepage and contact pages, plus JSON-LD
     - Zaubacorp for registered companies
   - **Website check:** old WordPress / jQuery, not mobile-friendly, no HTTPS, an old copyright year…

   Enrich writes **nothing**: it returns proposals, and only for fields that are empty.
3. **Review** each proposal (all are ticked by default) and click **Save**.

### Safety (the owner's "never delete" rule)
- **Fill-only saving:** it uses the same writer as Data Cleanup:
  - a full backup of the leads file
  - only EMPTY fields are filled, and a field filled in the meantime is skipped
  - a change log, with **Undo** from Data Cleanup → history
- **Values from the browser are checked again on the server:**
  - only website / e-mail / phone / website check can be filled
  - the lead must exist, and the field must still be empty
  - the value is normalised: an invalid e-mail or phone is dropped; a portal, invalid-domain or private-IP website is refused
- **Never used as the company website:** platform links and government pages.

### What to expect
- **Leads with a website** are fast: about 1 s each.
- **Leads without a website** first need the search engine to find one. DuckDuckGo finds few, so a SearXNG / Brave / Serper setup finds more.
- **QA run:** the first 10 leads with a website gave 10 website checks but no new e-mails or phones. Their sites had already been read when they were saved.

### Technical
| Item | Value |
|---|---|
| Backend | `lead_enrichment.py` (Deep Search + `website_signals`); saving through `lead_cleanup.apply_changes` |
| API (login required) | `POST /api/lead-care/enrichment/candidates`, `…/run` (up to 5 lead ids), `…/save` (`{changes}`). The save holds the shared lock. |
| Frontend | `LeadEnrichment.js` (Lead Care → Lead Enrichment) |
| Tests | `test_lead_enrichment.py` (5 tests, in hourly CI) |

---

## ગુજરાતી

### હેતુ
પહેલેથી save કરેલા leads માં ખૂટતાં **email, phone, website અને website check** શોધવાં. પછી તમે પસંદ કરો એ જ save થાય છે.

### કેવી રીતે
1. **Leads પસંદ કરો:** શું ખૂટે છે, source અને કેટલા leads.
2. **Enrich દબાવો:** 5-5 leads પર Deep Search ચાલે છે. Progress દેખાય છે, અને Stop પણ કરી શકાય છે.
3. **Save:** મળેલી values જુઓ, ટીક કરો અને Save દબાવો.

### સુરક્ષા
- **ફક્ત ખાલી fields ભરાય છે.** જૂનું કંઈ બદલાતું કે delete થતું નથી.
- **Save પહેલાં backup બને છે,** અને Data Cleanup → history માંથી **Undo** થઈ શકે છે.

# Data Extraction → Corporate Registries — Module Guide

**Status:**
- **QA passed:** live (2026-11-12).
- **UNVERIFIED:** live GST status (not possible, see below) and Deep Search websites (needs a search engine).
- QA report: `reports/qa/2026-11-12-corporate-registries.md`. **Updated:** 2026-11-12.

---

## English

### Purpose
Leads from India's company register (MCA) and from GST registrations. Newly registered companies often need a website, IT and marketing, so they make good leads.

### Menus
| Menu | Data | Source |
|---|---|---|
| **Company Scraper** | Registered companies by **industry** (NIC section), **city or state**, **company type** (Pvt Ltd, LLP, OPC, Public, Section 8, foreign subsidiary), **status** and **age** — or search by **company name** | ZaubaCorp public listing pages (MCA data) |
| **PVT LTD Scraper** | The same, fixed to **Private Limited** companies; "less than 1 year" (new companies) by default | ZaubaCorp |
| **GST No Scraper** | **Find:** GST numbers shown on IndiaMART seller pages for a product / city.<br>**Check:** validate GSTINs you already have — offline. | IndiaMART seller pages; the offline GSTIN algorithm |

### What each result contains
- **Company:**
  - name, status, CIN, registered address, paid-up capital
  - From the CIN, with no extra request: listed / unlisted, industry code, state, year of incorporation, company type. LLPs have an LLPIN (e.g. `ACB-1234`) and are shown as LLP.
- **Company details** (button, 10 at a time):
  - It opens each company page for the incorporation date, ROC, category, class, activity and website.
- **GST:**
  - GSTIN, valid / invalid (check digit), state, entity type (company, firm / LLP, proprietorship…)
  - the PAN, except for a proprietorship, where the PAN is personal and is not shown on its own

### What is not collected, and why
| Item | Why |
|---|---|
| Director names | Personal data. The page shows them, but the parser never reads that table. |
| E-mail from ZaubaCorp | The site hides it from bots (Cloudflare e-mail protection). Decoding it would defeat that protection, so use **Deep Search** (the company's own website) instead. |
| Live GST status (active / cancelled), name from a GSTIN | Only the official GST portal has these, and it uses a **captcha**. This app does not bypass captchas. |
| MCA portal (mca.gov.in), data.gov.in | Captcha / robots.txt disallows apps. |

### Rules the scraper follows
- **Allowed pages only.** ZaubaCorp's robots.txt allows everything except PDFs. IndiaMART seller pages are checked against IndiaMART's robots.txt one by one, and disallowed ones are skipped and counted.
- **Polite requests.** An honest User-Agent, the URL guard, the HTML cache and 2 s between requests.
- **Cache.** The same search within 72 hours returns the saved result (`CORPORATE_REGISTRIES_CACHE_HOURS`). The offline GST check is never cached.
- **Filters the register does not have.**
  - **Industry + state** (without a city) does not exist, so the form asks for a city.
  - **Industry + LLP** does not exist either, because LLPs have no industry code. The search then runs without the industry filter and says so.

### How to use
1. Open **Data Extraction → Corporate Registries → <menu>**.
2. Set the filters.
   - For Company / PVT LTD: state / city, type, status, age, industry and pages (30 companies per page).
   - Or type company names to search by name. The other filters are then applied to the matches.
3. Click **Search**. Then:
   - **Company details** (incorporation, activity, website)
   - **Deep Search** (website, email, phone)
   - **Export CSV**
   - **Save to Leads**:
     - source `Corporate Registries (ZaubaCorp / MCA)` or `Corporate Registries (GST via IndiaMART)`
     - lead type `New Company (under 1 year)`, `Registered Company` or `GST Registered Business`
     - CIN / GSTIN in the description
4. **GST check:** paste GSTINs (one per line or comma separated, up to 100) and click **Check**. Results can be exported; they are not saved as leads, because they have no company name.

### Technical
| Item | Value |
|---|---|
| Backend | `corporate_registries.py`. Parsers and the CIN / GSTIN decoders are pure functions; fetches go through `html_cache_manager.fetch_page`. |
| API (login required) | `GET /api/corporate-registries`, `POST …/search`, `POST …/details`, `POST …/save` |
| Frontend | `CorporateRegistry.js` (prop `mode`: `company` / `pvtltd` / `gst`), shared `MiningForm` |
| Tests | `test_corporate_registries.py` (19 tests, in hourly CI) |

---

## ગુજરાતી

### હેતુ
ભારતના company register (MCA) અને GST registrations માંથી leads મેળવવા. નવી companies ને website, IT અને marketing ની જરૂર હોય છે, એટલે એ સારા leads છે.

### Menus
- **Company Scraper:** udyog, શહેર કે state, company type, status અને ઉંમર પ્રમાણે companies. નામથી પણ શોધી શકાય છે.
- **PVT LTD Scraper:** ફક્ત Private Limited companies. Default માં 1 વર્ષથી નવી companies આવે છે.
- **GST No Scraper:**
  - **Find:** IndiaMART seller pages પરથી GST નંબર.
  - **Check:** તમારી પાસેના GST નંબર સાચા છે કે નહીં, એ internet વગર તપાસે છે (state, PAN અને entity પણ બતાવે છે).

### શું નથી લેવાતું
- Directors નાં નામ (અંગત માહિતી).
- Site જે email છુપાવે છે એ. Email માટે Deep Search વાપરો.
- GST નંબર active છે કે cancel, એ માટે સરકારી portal પર captcha છે, અને અમે captcha bypass નથી કરતા.

### વાપરવાની રીત
1. Menu ખોલો, filters પસંદ કરો અને **Search** દબાવો.
2. પછી **Company details**, **Deep Search**, **Export CSV** અથવા **Save to Leads** કરો.

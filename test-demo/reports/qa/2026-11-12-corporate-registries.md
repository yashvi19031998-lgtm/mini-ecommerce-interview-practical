# QA Report — Data Extraction → Corporate Registries

**Date:** 2026-11-12 · **Build:** uncommitted working tree on `master` · **Result:** PASSED, with the UNVERIFIED items listed in section 5.

## English

### 1. Feasibility check (live, before building)
| Source | Result |
|---|---|
| ZaubaCorp (MCA data) | robots.txt allows all pages except PDFs. No captcha. The listing pages combine filters (industry / city or state / type / status / age / page); name search works. |
| Tofler | Allowed, but not needed. |
| mca.gov.in | **Captcha.** Not used. |
| data.gov.in | **Captcha, and robots.txt disallows.** Not used. |
| GST portal (services.gst.gov.in) | The taxpayer search needs a **captcha.** Not used, so live GST status is not available. |
| IndiaMART seller pages | Allowed for most pages (checked per URL). Real GSTINs are shown, e.g. `24ACHPG0469J1ZO`. |

### 2. Automated tests (Python, no network)
| Suite | Result |
|---|---|
| `test_corporate_registries.py` (new) | 19/19 |
| Full regression (26 suites) | **423/423** |

**What the new tests cover:**
- validation
- list URL order, and state names (`Odisha` → `ORISSA`, `Jammu and Kashmir` → `JAMMU & KASHMIR`)
- CIN and LLPIN decoding
- GSTIN check digit, verified on 2 real GSTINs. A proprietor's PAN is not shown.
- GSTINs in page text (scripts ignored, bad check digit dropped)
- list card and search card parsing
- the company page parser — **director names never appear**
- pagination stops on a short page; the "no match" message
- name search with local filters
- the industry filter dropped when the register has no such list
- details opens only ZaubaCorp company pages (max 10)
- GST find: robots-disallowed seller pages are skipped
- GST check makes no network call
- lead mapping; API 401 / 400 / cache / save

### 3. Browser QA (Playwright, real backend, **live sites**) — 10/10 pass
| ID | Test | Result |
|---|---|---|
| CR01 | Menu "Corporate Registries" with 3 items. Validation: a place is needed, and industry needs a city. | PASS |
| CR02 | Company Scraper: Ahmedabad, real estate / business, LLP, 1–3 years → **30 LLPs**. There is no industry list for LLPs, so it ran without that filter and said so. | PASS |
| CR03 | Company details for 2 selected → 2 of 2, incorporation date shown. | PASS |
| CR04 | PVT LTD Scraper: Ahmedabad, new, 2 pages → **60 Private Limited companies**, incorporated 2025–2026. | PASS |
| CR05 | Search by name "sj polycraft" → found. | PASS |
| CR06 | Save → 1 new lead, source `Corporate Registries (ZaubaCorp / MCA)`, type `New Company (under 1 year)`, CIN in the description. | PASS |
| CR07 | GST find: "bakery products", Ahmedabad, 10 sellers → **5 GSTINs found, all valid**. | PASS |
| CR08 | GST check: valid (Maharashtra, company), bad check digit, bad format. No "Save" button for checks. | PASS |
| CR09 | CSV export; mobile at 390 px, no sideways scroll. | PASS |
| CR10 | No console errors. | PASS |

### 4. Bugs found and fixed during the build
1. **Search-page cards** have no `alt` text and no status. Fields are now recognised by their icon, and the status filter is skipped when the status is unknown.
2. **Industry + state** pages do not exist (404). The form now asks for a city.
3. **Industry + LLP** pages do not exist (404). The search falls back to no industry filter and tells the user.
4. **LLPIN** (`ACB-1234`) was not recognised. LLPs now show as "Limited Liability Partnership", and their details pages are allowed.
5. **`Fetcher`** can take its own pause, so the registries module does not add a fake portal to the Indian Directories list.

### 5. UNVERIFIED / not possible
| Item | Why |
|---|---|
| Live GST status, legal name from a GSTIN | The GST portal needs a captcha. Not possible without a bypass. |
| Deep Search finding websites for these companies | It needs a search engine; DuckDuckGo is weak today. |

### 6. Data safety
- `all_leads_master.csv` was restored after QA (md5 `963d94bc…` matches).
- SMTP, IMAP and Supabase were off during QA.

## ગુજરાતી
- **Live tests:** 10/10 pass. PVT LTD Scraper માં Ahmedabad ની 60 નવી Pvt Ltd companies મળી. GST માં 10 sellers માંથી 5 GST નંબર મળ્યા, બધા valid.
- **શક્ય નથી:** GST નંબર active છે કે cancel, એ જોવું. સરકારી portal પર captcha છે.
- **Privacy:** Directors નાં નામ અને proprietor નો PAN અલગથી નથી બતાવાતો.
- **Tests:** unit 423/423 pass.

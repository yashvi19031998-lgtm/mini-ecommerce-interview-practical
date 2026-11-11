# Job Portal Scraper — Module Guide

**Module:** Job Portal Scraper · **Status:** QA passed (see `reports/qa/2026-11-11-job-portal-scraper.md`) · **Updated:** 2026-11-11

---

## English

### Purpose
- Find companies that are **hiring** for given job titles in a chosen Indian state.
- A hiring company = a sales lead (staff augmentation / project outsourcing).

### Where
- Sidebar → **1. Dashboard**, **2. Job Portal Scraper** (inside the existing LeadsGen AI app).

### How to use
1. **Job Titles** — type a title, press `Enter` or `,`. Up to 10 titles, 80 characters each. Duplicates are ignored.
2. **State** — one of 36 states/UTs, or `All India`.
3. **Job Portals** — pick one, many, or **Select all available**. Greyed portals show why they can't be used.
4. Click **Search Jobs** → results list below (usually 5–30 seconds).
5. Tick jobs → **Save to Leads** (adds the hiring companies to the leads database). **Export CSV** downloads the visible list.

### Portals
| Status | Portals |
|---|---|
| Available | Foundit, Shine, LinkedIn (guest), Internshala, Freshersworld, Apna, Instahyre, Remotive, RemoteOK, Arbeitnow |
| Needs free API key | Adzuna (`ADZUNA_APP_ID`, `ADZUNA_APP_KEY`), Jooble (`JOOBLE_API_KEY`) in `.env` |
| Not available (blocked) | Naukri, Indeed, Glassdoor, Wellfound, Careerjet (captcha/Cloudflare); TimesJobs, Cutshort, Hirist (JavaScript-only); NCS (form-only) |

- We do **not** bypass captchas or blocks.
- **LinkedIn:** automated access is against LinkedIn's terms; heavy use can get the IP blocked.
- **Remotive / RemoteOK / Arbeitnow:** worldwide remote jobs; the State filter does not apply.

### Result rules
- **State:** native filter where the portal supports it (Foundit, LinkedIn, Adzuna, Jooble); otherwise matched by the job's city (`INDIAN_STATES` city list). `Remote` / `Work from home` jobs are kept.
- **Relevance:** every significant word of the title (e.g. `react`) must be in the job title or skills. Generic words (`developer`, `senior`, …) are ignored.
- **Duplicates:** removed by job link. Saving the same job twice does not create a second lead.

### Technical
| Item | Value |
|---|---|
| Backend | `job_portals.py` |
| API | `GET /api/job-portals`, `POST /api/job-portals/search`, `POST /api/job-portals/save` (login required) |
| Frontend | `components/JobPortalScraper.js`, `components/Dashboard.js` |
| Saved lead | `lead_type = Job Posting`, `source = Job Portal (<portal>)` |
| Tests | `test_job_portals.py` (30 tests) |
| New dependencies | none |

---

## ગુજરાતી

### હેતુ
- પસંદ કરેલા રાજ્યમાં આપેલા job titles માટે **ભરતી કરતી કંપનીઓ** શોધવી.
- ભરતી કરતી કંપની = sales lead (developers આપવા / project outsourcing).

### ક્યાં છે
- Sidebar → **1. Dashboard**, **2. Job Portal Scraper** (હાલની LeadsGen AI app ની અંદર).

### કેવી રીતે વાપરવું
1. **Job Titles** — title લખો, `Enter` અથવા `,` દબાવો. વધુમાં વધુ 10 titles, દરેક 80 અક્ષર સુધી. એક જ title બે વાર નહીં ઉમેરાય.
2. **State** — 36 રાજ્યો/કેન્દ્રશાસિત પ્રદેશોમાંથી એક, અથવા `All India`.
3. **Job Portals** — એક, ઘણા, અથવા **Select all available**. ગ્રે portals ઉપર કેમ નથી ચાલતું તેનું કારણ દેખાય છે.
4. **Search Jobs** દબાવો → નીચે results આવશે (સામાન્ય રીતે 5–30 સેકન્ડ).
5. Jobs ટિક કરો → **Save to Leads** (ભરતી કરતી કંપનીઓ leads database માં ઉમેરાય). **Export CSV** દેખાતી list download કરે.

### Portals
| Status | Portals |
|---|---|
| ચાલે છે | Foundit, Shine, LinkedIn (guest), Internshala, Freshersworld, Apna, Instahyre, Remotive, RemoteOK, Arbeitnow |
| Free API key જોઈએ | Adzuna (`ADZUNA_APP_ID`, `ADZUNA_APP_KEY`), Jooble (`JOOBLE_API_KEY`) — `.env` માં |
| નથી ચાલતા (block) | Naukri, Indeed, Glassdoor, Wellfound, Careerjet (captcha/Cloudflare); TimesJobs, Cutshort, Hirist (ફક્ત JavaScript); NCS (ફક્ત form) |

- Captcha કે block ને અમે **bypass કરતા નથી**.
- **LinkedIn:** automated access LinkedIn ના terms વિરુદ્ધ છે; વધુ વાપરવાથી IP block થઈ શકે.
- **Remotive / RemoteOK / Arbeitnow:** દુનિયાભરની remote jobs; State filter લાગુ નથી પડતું.

### Result ના નિયમો
- **State:** portal support કરે ત્યાં સીધું filter (Foundit, LinkedIn, Adzuna, Jooble); બાકીમાં job ના શહેર પરથી (`INDIAN_STATES` શહેરોની list). `Remote` / `Work from home` jobs રાખવામાં આવે છે.
- **Relevance:** title નો દરેક મુખ્ય શબ્દ (જેમ કે `react`) job title અથવા skills માં હોવો જોઈએ. સામાન્ય શબ્દો (`developer`, `senior`, …) ગણાતા નથી.
- **Duplicates:** job link પરથી દૂર થાય. એ જ job બે વાર save કરવાથી બીજી lead નથી બનતી.

### Technical
| વિગત | માહિતી |
|---|---|
| Backend | `job_portals.py` |
| API | `GET /api/job-portals`, `POST /api/job-portals/search`, `POST /api/job-portals/save` (login જરૂરી) |
| Frontend | `components/JobPortalScraper.js`, `components/Dashboard.js` |
| Save થયેલી lead | `lead_type = Job Posting`, `source = Job Portal (<portal>)` |
| Tests | `test_job_portals.py` (30 tests) |
| નવી dependencies | કોઈ નહીં |

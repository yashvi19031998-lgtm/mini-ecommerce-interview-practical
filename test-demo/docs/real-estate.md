# Scraping / Mining → Real Estate — Module Guide

**Status:**
- **QA passed:** live Karnataka RERA search, Deep Search, Save, and unit tests.
- **UNVERIFIED:** OpenStreetMap (server busy today), Google Places (no key) and the property portals (need a search-engine key for reliable results).
- QA report: `reports/qa/2026-11-12-real-estate.md`. **Updated:** 2026-11-12.

---

## English

### Purpose
Find **builders / developers** and **property agents** for real-estate offers: websites, CRM, marketing and apps.

### How to use
1. **Keywords:** e.g. `builder`, `apartment`, `villa`, or a builder name such as `Prestige`.
   - For the RERA register, trade words like builder, apartment and villa match everyone, so the newest registered builders are listed.
   - A name narrows the list.
2. **Target audience** (optional): e.g. residential, commercial, luxury. This uses word matching, and all results are kept if nothing matches.
3. **Looking for:** Builders and agents / Builders only / Agents only.
4. **Search engine:** used by property portals and Deep Search. Add a Brave or Serper key for reliable results.
5. **State** (required) and **City** (recommended for maps and portals).
6. **Sources:** Karnataka RERA and OpenStreetMap are preselected.
7. **Search**, then:
   - **Deep Search:** for RERA builders it first finds the builder's website by name, then reads email and phone from it.
   - **Export CSV**, **Save to Leads**.

### Sources (checked 2026-11-12)
| Source | Status | Data |
|---|---|---|
| **Karnataka RERA** | Available | Official register of about 10,100 projects: builder / promoter name, project names, registration numbers. No contacts, so use Deep Search. The 6 MB page is cached for 7 days. Karnataka only, builders only. |
| OpenStreetMap | Available (free) | Estate agents and construction companies, where mapped. |
| Google Places API | Needs `GOOGLE_PLACES_API_KEY` | Builders / agents with phone, website and rating. |
| Property portals (99acres, MagicBricks, Housing) | Available, via the search engine | Builder / agent pages. Off-target results are hidden. DuckDuckGo without a key often returns nothing. |
| MahaRERA, GujRERA, Rajasthan RERA | Not available | Results load only through JavaScript |
| Haryana RERA | Not available | Blocks automated requests (captcha / HTTP 403) |
| UP RERA | Not available | Did not respond |

We never bypass captchas or logins. On government sites we identify ourselves with a descriptive User-Agent.

### Result rules
- **Grouping:** RERA projects are grouped per builder ("3 RERA project(s): …"). ALL-CAPS names are title-cased.
- **Duplicates:** removed across sources, matched by phone, then website, then name. Missing contacts are copied from duplicates.
- **Order:** results with a phone or email come first, then those with a website, then by rating.
- **Saved leads:** source `Real Estate (<source>)` and lead type `Real Estate - Builder / Developer` or `Real Estate - Property Agent`.
- **Deep Search:** a government register (`.gov.in`, `.nic.in`…) is never treated as the company's website, so the register's own contacts are never saved as a builder's.
- **Caching:** the same search is answered from saved results for `REALESTATE_CACHE_HOURS` (default 72 h).

### Known limits
- **Karnataka only:** only Karnataka RERA is open today. The register has no city, so the City field does not filter it.
- **Promoters:** some promoters are individuals (landowners). Treat their data carefully under the DPDP Act.
- **Deep Search** finds a builder's website by name through the search engine. It works best with a Brave or Serper key.

### Technical
| Item | Value |
|---|---|
| Backend | `realestate_sources.py`; reuses `crm_sources.search_osm`, `maps_sources.search_places`, `search_engine`, `deep_search`, `html_cache_manager` |
| API (login required) | `GET /api/realestate`, `POST /api/realestate/search`, `POST /api/realestate/save` |
| Frontend | `RealEstate.js` (shared `MiningForm`) |
| Tests | `test_realestate_sources.py` (19 tests, in hourly CI) |

---

## ગુજરાતી

### હેતુ
**Builders / developers** અને **property agents** શોધવા. એ website, CRM, marketing અને app સેવા માટેના leads છે.

### કેવી રીતે વાપરવું
1. **Keywords:** builder, apartment, villa, કે builder નું નામ (જેમ કે Prestige).
2. **Looking for:** Builders / Agents / બંને.
3. **State** ફરજિયાત છે, **City** ભરવાની સલાહ છે.
4. **Search** કરો, પછી **Deep Search** (builder ની website નામ પરથી શોધીને email / phone લાવે છે), **Export CSV** અને **Save to Leads**.

### Sources
- **Karnataka RERA:** સરકારી રજિસ્ટર, આશરે 10,100 projects, builder ના નામ સાથે. Contact નથી, એટલે Deep Search વાપરો.
- **OpenStreetMap:** free. **Google Places:** key જોઈએ. **99acres / MagicBricks / Housing:** search engine દ્વારા.
- **ઉપલબ્ધ નથી:**
  - MahaRERA, GujRERA, Rajasthan: ફક્ત JavaScript થી ચાલે છે.
  - Haryana: captcha.
  - UP: જવાબ નથી આપતું.
- અમે captcha કે login ક્યારેય bypass નથી કરતા.

### મર્યાદા
- આજે ફક્ત Karnataka RERA ખુલ્લું છે, અને તેમાં city નથી.
- અમુક promoters વ્યક્તિઓ છે (જમીન માલિકો). તેમનો data DPDP Act ધ્યાનમાં રાખીને વાપરો.
- Deep Search Brave કે Serper key સાથે સૌથી સારું ચાલે છે.

# Global Directories — Module Guide

**Module:** Global Directories (Scraping / Mining → Global Directories) · **Status:** QA passed for available sources (GoodFirms verified); OpenStreetMap Overpass server busy; registers UNVERIFIED (no API keys yet) · see `reports/qa/2026-11-12-global-directories.md` · **Updated:** 2026-11-12

---

## English

### Purpose
- Find **companies outside India** by keyword, target audience, country, and optional city or region.
- Discover registered entities from **official government registers** (UK Companies House, US SEC EDGAR).
- Discover businesses from open global directories (OpenStreetMap, GoodFirms).
- Deep search discovered company websites to enrich direct emails, phone numbers, and social links.
- Export results to sanitized CSV or save them directly into the Leads Database (`all_leads_master.csv`).

### Where
- Sidebar → **Scraping / Mining** → **Global Directories** (URL tab: `mining-directories`).

### How to use
1. **Keywords / Business category** (required): type and press `Enter` or `,`. You can add up to 10 keywords, each at most 80 characters. Duplicates are ignored and double quotes (`"`) are rejected.
2. **Target audience** (optional): enter up to 5 industry or segment keywords (e.g. `IT / Software`, `Startups`, `Manufacturing`). If results match the audience, they are narrowed; if no results match the audience filter, unfiltered results are preserved with an informative notice.
3. **Country** (required): select one of the 24 supported international countries (e.g. `United Kingdom`, `United States`, `Canada`, `Germany`, `Australia`). India (`IN`) is excluded because it has dedicated domestic mining modules.
4. **Region / State** (optional): enter a state or administrative region (e.g. `California` or `CA` for US SEC filings, or a province/region for OpenStreetMap). Letters, spaces, and `.'-` only (max 60 characters).
5. **City** (optional): enter a city name (e.g. `London`, `New York`, `Berlin`). Letters, spaces, and `.'-` only (max 60 characters). Some directories (like GoodFirms) require a city.
6. **Sources**: pick one or more sources from the grouped multi-select dropdown, or click **Select all available**. Greyed-out sources display the reason they cannot be queried.
7. Click **Search**. Queries run in parallel across selected sources (up to 4 threads). A status chip is displayed for each source with result counts, `failed`, or `skipped`.
8. Review results in the responsive data table.
9. **Deep Search**: click to automatically crawl company websites in batches of 10 to extract contact emails, phone numbers, and addresses.
10. **Export CSV**: downloads the filtered list with CSV formula injection protection (cells starting with `=`, `+`, `-`, or `@` are safely prefixed).
11. **Save to Leads**: select rows and click **Save to Leads** to commit them into `all_leads_master.csv`.

### Sources
| Source | Type | Status | Key / Environment | Countries | Description / Limit |
|---|---|---|---|---|---|
| OpenStreetMap (worldwide) | Directory | Available | None (Public API) | Worldwide (`*`) | Overpass API `https://overpass-api.de/api/interpreter`. Requires city or region. Max 50 results. |
| GoodFirms (worldwide) | Directory | Available | None | Worldwide (`*`) | IT and software development agencies by city. Requires city. Max 50 results. |
| UK Companies House | Official Register | Needs key | `COMPANIES_HOUSE_API_KEY` | United Kingdom (`GB`) | Official UK company register API. Requires free API key from service.gov.uk. Max 50 results. |
| US SEC EDGAR | Official Register | Needs key | `SEC_USER_AGENT` | United States (`US`) | Official US public company filings & registration via `efts.sec.gov` & SEC browse. Requires custom User-Agent. Max 50 results. |
| OpenCorporates | Official Register | Unavailable | None | Worldwide (`*`) | API requires a paid commercial license. |
| Yelp | Directory | Unavailable | None | Worldwide (`*`) | Yelp Fusion API requires a paid commercial plan. |
| Clutch | Directory | Unavailable | None | Worldwide (`*`) | Blocks automated requests via Cloudflare challenge. |
| Europages / Kompass | Directory | Unavailable | None | Worldwide (`*`) | Listings blocked or behind authentication gates for automated access. |

### Why some sources are not available
- **Anti-bot blocks:** Clutch is protected by Cloudflare bot protection. Per project governance rules, we never bypass Cloudflare, captchas, or login walls.
- **Commercial licensing required:** OpenCorporates and Yelp require paid commercial subscriptions.
- **Gated listings:** Europages / Kompass listings are restricted or behind login barriers.

### Known limits
- **OpenStreetMap Overpass:** The public `overpass-api.de` server frequently experiences heavy traffic and may return HTTP 502/504 or rate-limit requests. The module automatically retries once before reporting a friendly busy notice.
- **UK Companies House:** Restricted strictly to United Kingdom (`GB`). Queries for other countries are marked `skipped`.
- **US SEC EDGAR:** Restricted strictly to United States (`US`). SEC enforces a rate limit of under 10 requests per second.
- **GoodFirms:** Dedicated exclusively to IT and software development firms and requires a specific city.

### Result rules
- **Deduplication:** Results are deduplicated first by website domain (normalized host), and secondly by normalized company name + country.
- **Prioritization:** Companies with verified contact coordinates (email, phone, website) are sorted first.
- **Lead Normalization:** Leads saved from this module receive `source = "Global Directory (<Source Name>)"` and `lead_type = "Global Directory"`.
- **Idempotence:** Saving the same company repeatedly will not create duplicates; existing records report `"already saved"`.

### Technical Architecture
| Component | Implementation |
|---|---|
| Backend Module | `global_directories.py` |
| REST API Endpoints | `GET /api/global-directories`<br>`POST /api/global-directories/search`<br>`POST /api/global-directories/save` |
| Cache Integration | `search_cache.py` (`globaldirectories` module, TTL 72 hours, SQLite cache in `html_cache/search_results.sqlite`) |
| Lead Storage | `lead_normalizer.MasterLeadRegistry` writing to `all_leads_master.csv` |
| Frontend Component | `frontend/components/GlobalDirectories.js` |
| Automated Tests | `test_global_directories.py` (23 tests, 0 network dependencies) |

---

## ગુજરાતી

### હેતુ
- કીવર્ડ, ટાર્ગેટ ઓડિયન્સ, દેશ અને શહેર/રાજ્ય મુજબ **ભારત બહારની વિદેશી કંપનીઓ (Global Companies)** શોધવી.
- અધિકૃત સરકારી રજિસ્ટર (UK Companies House, US SEC EDGAR) માંથી નોંધાયેલી કંપનીઓ શોધવી.
- વૈશ્વિક ઓપન ડિરેક્ટરીઝ (OpenStreetMap, GoodFirms) માંથી વ્યવસાયો શોધવા.
- ડીપ સર્ચ (Deep Search) દ્વારા કંપની વેબસાઇટ પરથી ડાયરેક્ટ ઈમેઈલ, ફોન નંબર અને સોશિયલ લિંક્સ મેળવવી.
- મેળવેલા પરિણામોને CSV માં એક્સપોર્ટ કરવા અથવા એક જ ક્લિકમાં Leads Database (`all_leads_master.csv`) માં લીડ તરીકે સાચવવા.

### ક્યાં છે
- સાઇડબાર → **Scraping / Mining** → **Global Directories** (ટેબ: `mining-directories`).

### કેવી રીતે વાપરવું
1. **Keywords / Business category** (ફરજિયાત): કીવર્ડ લખીને `Enter` અથવા `,` દબાવો. વધુમાં વધુ 10 કીવર્ડ્સ ઉમેરી શકાય છે (દરેક વધુમાં વધુ 80 અક્ષર).
2. **Target audience** (મરજિયાત): તમારા લક્ષિત ઉદ્યોગ અથવા સેગમેન્ટ્સ લખો (દા.ત. `IT / Software`, `Startups`, `Manufacturing`).
3. **Country** (ફરજિયાત): આપેલા 24 આંતરરાષ્ટ્રીય દેશોમાંથી દેશ પસંદ કરો (દા.ત. `United Kingdom`, `United States`, `Germany`, `Canada`). ભારત માટે અલગ મોડ્યુલ હોવાથી અહીં ભારત બહારના દેશો રાખવામાં આવ્યા છે.
4. **Region / State** (મરજિયાત): રાજ્ય કે પ્રોવિન્સ લખો (દા.ત. US SEC માટે `California` અથવા `CA`, OSM માટે રીજન).
5. **City** (મરજિયાત): શહેરનું નામ લખો (દા.ત. `London`, `New York`, `Berlin`). GoodFirms માટે શહેર જરૂરી છે.
6. **Sources**: ઉપલબ્ધ સોર્સિસ પસંદ કરો અથવા **Select all available** પર ક્લિક કરો.
7. **Search** બટન પર ક્લિક કરો. પાયથન બેકેન્ડ તમામ પસંદ કરેલા સોર્સિસમાંથી સમાંતર (parallel) ડેટા લાવશે.
8. **Deep Search**: ટેબલમાં આવેલી કંપનીઓની વેબસાઈટ ક્રાઉલ કરી ઈમેલ અને ફોન નંબર શોધવા Deep Search બટન વાપરો.
9. **Export CSV**: દેખાતા પરિણામોની સુરક્ષિત CSV ફાઈલ ડાઉનલોડ કરો.
10. **Save to Leads**: જોઈતી કંપનીઓને સિલેક્ટ કરી Leads Database માં સેવ કરો.

### સ્ત્રોતોની વિગત (Sources)
- **OpenStreetMap (Overpass):** વૈશ્વિક ઓપન બિઝનેસ ડિરેક્ટરી. શહેર અથવા રીજન જરૂરી છે.
- **GoodFirms:** આઈટી અને સોફ્ટવેર કંપનીઓની ડિરેક્ટરી. શહેર મુજબ ડેટા આપે છે.
- **UK Companies House:** યુકે સરકારનું સત્તાવાર કંપની રજિસ્ટર (મફત `COMPANIES_HOUSE_API_KEY` જરૂરી).
- **US SEC EDGAR:** અમેરિકન પબ્લિક કંપનીઓનું સત્તાવાર SEC ફાઈલિંગ રજિસ્ટર (`SEC_USER_AGENT` જરૂરી).
- **અનુપલબ્ધ સોર્સિસ:** Clutch (Cloudflare બોટ બ્લોક), OpenCorporates / Yelp (પેઇડ કોમર્શિયલ લાયસન્સ જરૂરી). અમે કોઈ પણ બ્લોક કે કેપ્ચા બાયપાસ કરતા નથી.


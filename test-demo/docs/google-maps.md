# Scraping / Mining → Google Maps — Module Guide

**Status:**
- **QA passed:** the UI flow, filters, Deep Search, Save, and unit tests.
- **UNVERIFIED:** live OpenStreetMap results (the public Overpass server was "at capacity" during QA) and Google Places (no key yet).
- QA report: `reports/qa/2026-11-12-google-maps.md`. **Updated:** 2026-11-12.

---

## English

### Purpose
- Find **local businesses** by category and city, with phone, website, address and rating.
- **"Without website" filter:** businesses that have no website are direct leads for a website / digital-presence offer.

### How to use
1. **Business category / keywords:** up to 5, e.g. restaurant, hospital, furniture shop.
2. **Target audience** (optional): keeps businesses whose name or category mentions it. If nothing matches, all results are shown with a note.
3. **Website:** Any / **Without website (website leads)** / With website.
4. **Minimum rating:** 3, 3.5, 4 or 4.5. This applies to Google Places results only, because OpenStreetMap has no ratings.
5. **State** (required) and **City** (recommended; a whole state is slow).
6. **Sources:** OpenStreetMap is preselected. Google Places is enabled once its key is set.
7. **Search.** The page then shows:
   - a chip per source, with its error reason when it failed
   - "N hidden by your filters"
   - the number of results without a website
8. **What you can do with the results:**
   - **Deep Search** opens the business website to find email, phone and social links. Rows without a website are skipped.
   - **Export CSV** downloads the rows, including the `no_website` column.
   - **Save to Leads** saves them. Saving again creates no duplicate.

### Sources
| Source | Status | Data |
|---|---|---|
| OpenStreetMap | Free, no key | Name, phone, website, email and address, only where volunteers mapped them. Needs a state or city. |
| Google Places API | Needs `GOOGLE_PLACES_API_KEY` (free monthly quota; card needed) | The same data Google Maps shows: name, phone, website, address, rating, reviews, Maps link. Closed businesses are skipped. Up to 60 per keyword. |
| Google Maps page scraping | Not available | Against Google's terms and blocked quickly. Use the Places API instead. |

### Result rules
- **Duplicates:** removed across sources, matched by phone number, then website domain, then name + address.
- **Order:** results with a phone come first, then by rating and number of reviews.
- **Saved leads:**
  - source `Google Maps (<source>)` and lead type `Local Business`
  - the description includes the category, the rating, and "No website listed - website / digital presence opportunity" when there is no website
- **Errors:** a source that fails (e.g. a busy server) shows a clear reason, and the other sources still return.
- **Caching:** the same search is answered from saved results for `MAPS_CACHE_HOURS` (default 72 h). **Search live again** always goes live.

### Known limits
- **OpenStreetMap:** the public Overpass server is often busy. On 2026-11-12 it returned "at capacity" and timed out, so try again later. Many Indian shops on OSM have no phone or website.
- **Google Places** gives the best data but uses your quota. Set a budget alert in Google Cloud.

### Technical
| Item | Value |
|---|---|
| Backend | `maps_sources.py`, which reuses `crm_sources.search_osm` and `crm_sources.PLACES_FIELDS` |
| API (login required) | `GET /api/maps`, `POST /api/maps/search`, `POST /api/maps/save`; Deep Search via `POST /api/search-engine/deep` |
| Frontend | `GoogleMaps.js` (uses the shared `MiningForm`) |
| Tests | `test_maps_sources.py` (13 tests, in hourly CI) |

---

## ગુજરાતી

### હેતુ
- શહેર અને category પ્રમાણે **local businesses** શોધવા: phone, website, address અને rating સાથે.
- **"Without website" filter:** જેની website નથી એ દુકાનો / businesses તમારા માટે website બનાવવાના **સીધા leads** છે.

### કેવી રીતે વાપરવું
1. **Keywords:** 5 સુધી, જેમ કે restaurant, hospital, furniture shop.
2. **Target audience** (optional).
3. **Website:** Any / **Without website** / With website.
4. **Minimum rating:** ફક્ત Google Places માટે.
5. **State** ફરજિયાત છે, **City** ભરવાની સલાહ છે.
6. **Search** દબાવો. પછી **Deep Search**, **Export CSV** અને **Save to Leads** વાપરી શકાય.

### Sources
- **OpenStreetMap:** free. Phone કે website ફક્ત ત્યાં જ મળે જ્યાં લોકોએ map પર ઉમેર્યાં હોય.
- **Google Places API:** key જોઈએ (free quota, card જરૂરી). Google Maps જેવો જ data અને rating આપે છે.
- **Google Maps scraping:** ઉપલબ્ધ નથી, કારણ કે એ Google ના નિયમો વિરુદ્ધ છે.

### મર્યાદા
- OpenStreetMap નું server ઘણી વાર busy હોય છે. આજે (12 Nov) તે "at capacity" હતું, એટલે live result **UNVERIFIED** છે.
- Google Places key ઉમેર્યા પછી સૌથી સારો data મળશે.

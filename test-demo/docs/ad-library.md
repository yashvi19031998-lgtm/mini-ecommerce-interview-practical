# Scraping / Mining → Ad Library — Module Guide

**Status:**
- **QA passed:** UI, Deep Search, Save and unit tests. Ad-tag detection was checked live on 3 real websites.
- **UNVERIFIED:** live search-engine discovery (DuckDuckGo returned nothing today; needs a Brave / Serper key) and the Meta Ad Library API (no token).
- QA report: `reports/qa/2026-11-12-ad-library-whatsapp.md`. **Updated:** 2026-11-12.

---

## English

### Purpose
Find businesses that are **paying for ads right now**. They have a marketing budget, so they are hot leads.

### Sources
| Source | Status | How |
|---|---|---|
| **Ad tags on websites** | Free | The search engine finds business websites for the keyword + place. Each home page (at most 15 per search) is checked for **Meta Pixel, Google Ads, LinkedIn Insight and Microsoft Ads** tags. Only sites with one of these are listed. Google Tag Manager alone is shown as extra info but does not count as "running ads". |
| Meta Ad Library API | Needs `META_AD_LIBRARY_TOKEN` (free; Meta developer app + identity confirmation) | Official API. **For India Meta returns only political & social-issue ads** (Meta's rule outside the EU / UK), so it finds advertisers on those topics, not shops. Ads are grouped per Facebook page with count, start date and a "View ads" link. |
| Google Ads Transparency (via search engine) | Available | Advertiser pages found through the search engine; needs a Brave or Serper key for good results. |
| Meta Ad Library website | Not available | Needs a browser; automated access is against Meta's terms |
| Google Ads Transparency website | Not available | JavaScript-only, with no public API |

### How to use
1. Fill in **Business type / keywords** (e.g. coaching classes, dental clinic) and the optional **Target audience**.
2. Choose the **Search engine**, **State** (required) and **City**.
3. Click **Search**. Results show **ad-signal badges**, and a note says how many websites were checked and how many had no ad tags.
4. Use **Deep Search** for email / phone. Advertisers without a website are looked up by name.
5. **Export CSV** or **Save to Leads**. Saved leads get the lead type `Active Advertiser` and include the ad tags and the ads link.

### Safety
- Websites are opened with the guarded fetch: public addresses only, every redirect re-checked, our own User-Agent, and the HTML cache.
- Government sites are never treated as a company website.

### Technical
| Item | Value |
|---|---|
| Backend | `adlibrary_sources.py` (uses `search_engine`, `deep_search`, `html_cache_manager`) |
| API (login required) | `GET /api/adlibrary`, `POST /api/adlibrary/search`, `POST /api/adlibrary/save` |
| Frontend | `AdLibrary.js` (shared `MiningForm`) |
| Tests | `test_adlibrary_sources.py` (11 tests, in hourly CI) |

---

## ગુજરાતી

### હેતુ
જે businesses **અત્યારે ads પર પૈસા ખર્ચે છે** એ શોધવા. એમની પાસે marketing budget છે, એટલે એ hot leads છે.

### Sources
- **Websites પર ad tags (free):**
  - Search engine થી business websites શોધે છે.
  - પછી દરેક website પર Meta Pixel, Google Ads, LinkedIn કે Microsoft Ads ના tags તપાસે છે.
  - જે website પર tag મળે, એ જ list માં આવે છે.
- **Meta Ad Library API:** token જોઈએ. **India માટે Meta ફક્ત political / social-issue ads જ આપે છે.**
- **Google Ads Transparency:** search engine દ્વારા.
- **ઉપલબ્ધ નથી:** Meta અને Google ની websites scrape કરવી, કારણ કે એ terms વિરુદ્ધ છે અને ફક્ત JavaScript થી ચાલે છે.

### કેવી રીતે વાપરવું
Keyword, State અને City ભરો → **Search** → ad-signal badges જુઓ → **Deep Search** (email / phone) → **Save to Leads** (lead type: `Active Advertiser`).

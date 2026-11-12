# Scraping / Mining → Social Media — Module Guide

**Status:**
- **QA passed:** UI, privacy filter, Deep Search, Save and unit tests.
- **UNVERIFIED:** live discovery (DuckDuckGo returned nothing today; needs a Brave / Serper key).
- QA report: `reports/qa/2026-11-12-social-media.md`. **Updated:** 2026-11-12.

---

## English

### Purpose
Find **business pages** on Instagram, Facebook, LinkedIn, X and YouTube for a business type in a city. Many small businesses only have a social page and no website, so they are direct leads for website, marketing and app services.

### How it works
- **Data:** all of it comes from **search-engine results** (title, URL, snippet). The app **never opens** instagram.com, facebook.com, linkedin.com, x.com or youtube.com. Those sites need a login or block bots, and scraping them breaks their terms.
- **Which URLs are kept:** only real profile / page URLs.
  - Instagram `/<handle>/`, Facebook page or `profile.php?id=`, LinkedIn `/company/<slug>` (never `/in/`, which is a person), X `/<handle>`, YouTube `/@handle`, `/c/`, `/channel/` or `/user/`.
  - Posts, reels, groups, events, statuses and videos are dropped.
- **Fields:**
  - name (title cleaned), handle, profile link
  - followers, when the snippet shows "12.5K Followers"
  - email / phone from the snippet
  - website from the snippet (social links, link shorteners and link-in-bio pages are never used as the website)

### Privacy rule (DPDP Act 2023)
A result is kept only if it looks like a business:
- it is a LinkedIn company page or a YouTube channel, or
- it contains a business word (shop, studio, cafe, clinic, services, pvt, ltd… or the searched keyword), or
- it shows a phone, email or website.

Everything else is dropped as a probable private person, and the page says how many were skipped. Follower lists, comments and personal details are never collected.

### Sources
| Source | Status |
|---|---|
| Instagram, Facebook, LinkedIn (companies), X, YouTube | Available, via the search engine (a Brave or Serper key is recommended) |
| WhatsApp Business catalogs | Not available: catalogs are only visible inside the WhatsApp app |

### How to use
1. Enter **Business type / keywords** (e.g. bakery, interior designer), **State** (required), **City** and the **Search engine**.
2. Click **Search**, then use the **Network** filter (All / Instagram / Facebook / LinkedIn / X / YouTube).
3. **Deep Search** runs only on rows that list a website, and opens the business's own website, never the social profile.
4. **Export CSV** or **Save to Leads**.
   - Saved leads get the lead type `Social Media Business` and the source `Social Media (<network>)`.
   - The profile link is kept as the source link and **never as the website**.

### Technical
| Item | Value |
|---|---|
| Backend | `social_sources.py` (makes no HTTP requests of its own; uses `search_engine`) |
| API (login required) | `GET /api/social`, `POST /api/social/search`, `POST /api/social/save` |
| Frontend | `SocialMedia.js` (shared `MiningForm`) |
| Tests | `test_social_sources.py` (11 tests, in hourly CI; includes "no request to social sites") |

---

## ગુજરાતી

### હેતુ
Instagram, Facebook, LinkedIn, X અને YouTube પર **business pages** શોધવા. ઘણા નાના businesses પાસે ફક્ત social page હોય છે અને website નથી હોતી, એટલે એ website / marketing માટેના સીધા leads છે.

### કેવી રીતે કામ કરે છે
- બધો data **search engine ના results** માંથી આવે છે. App પોતે ક્યારેય Instagram કે Facebook ખોલતી નથી.
- **Privacy:** ફક્ત business pages રાખવામાં આવે છે. જે profile કોઈ વ્યક્તિનું લાગે એ નીકળી જાય છે (DPDP Act 2023), અને કેટલાં skip થયાં એ page પર દેખાય છે.
- **Deep Search:** ફક્ત જે rows માં website હોય તેના પર ચાલે છે.
- **Save:** social link ક્યારેય lead ની website તરીકે save નથી થતી.

### મર્યાદા
DuckDuckGo `site:` queries ignore કરે છે, એટલે સારાં results માટે **Brave કે Serper key** જોઈએ.

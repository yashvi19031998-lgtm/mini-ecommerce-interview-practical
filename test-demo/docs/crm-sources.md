# CRM Sources — Module Guide

**Module:** CRM Sources · **Status:** QA passed for directory sources; contact databases UNVERIFIED (no API keys yet) · see `reports/qa/2026-11-11-crm-sources.md` · **Updated:** 2026-11-11

---

## English

### Purpose
- Find **businesses** by category + city (business directories).
- Find **decision makers** (CEO, Founder, CTO…) from B2B contact databases.
- Save the chosen results as leads in the existing leads database.

### Where
- Sidebar → **4. CRM Sources** (after Dashboard, Job Portal Scraper, FollowUp History).

### How to use
1. **Business category / keywords**: type and press `Enter` or `,`. You can add up to 10, each at most 80 characters. Duplicates are ignored.
2. **Decision-maker titles** (optional): only the contact databases use these.
3. **State** (required) and **City** (optional). If you leave the city empty, the state's main city is used. The city may contain only letters, spaces and `.'-`, up to 60 characters.
4. **Sources**: pick one or more, or click **Select all available**. A greyed-out source shows the reason it can't be used.
5. Click **Search**. It usually takes 5–40 seconds. A chip for each source shows its count, `failed` or `skipped`. Hover over a chip to see the reason.
6. Tick the results you want and click **Save to Leads**. **Export CSV** downloads the rows currently visible.

### Sources
| Status | Sources |
|---|---|
| Available (no key) | GoodFirms (IT/software firms by city), OpenStreetMap (Overpass), Zaubacorp (MCA registered companies) |
| Needs API key in `.env` | Apollo.io `APOLLO_API_KEY` · Hunter.io `HUNTER_API_KEY` · Google Places `GOOGLE_PLACES_API_KEY` · Snov.io `SNOV_CLIENT_ID` + `SNOV_CLIENT_SECRET` · Lusha `LUSHA_API_KEY` · RocketReach `ROCKETREACH_API_KEY` |
| Not available | Justdial, Sulekha, IndiaMART, TradeIndia, Clutch, YellowPages.in, AmbitionBox, Google Maps scraping |

Why some sources are not available:
- **Blocked:** Justdial returns an empty page to automated requests, and Clutch is behind Cloudflare.
- **JavaScript only:** Sulekha, IndiaMART and TradeIndia load their listings only in a browser.
- **Other:** YellowPages.in did not respond, AmbitionBox ignores the city filter, and scraping Google Maps breaks Google's terms.
- We do **not** bypass captchas or blocks.

### Known limits
- **OpenStreetMap:** the public Overpass server is sometimes busy and returns HTTP 502. The chip then shows `failed`, and you can try again in a minute. During QA it was down, so OSM results are UNVERIFIED.
- **Zaubacorp:**
  - It checks only the ~90 most recently registered companies in that city.
  - The keyword is matched on the company **name** only, so a general word like "software" often finds 0.
  - It also stops early if the site rate-limits the search (HTTP 429), and keeps the partial results.
- **Lusha:** returns contact previews only. Full emails and phones need Lusha credits.
- **API sources:** every search uses your plan's credits or quota.

### Result rules
- Duplicates are removed across sources. Results that have an email or phone are listed first.
- Saved leads get the source `CRM Source (<name>)` and the lead type `Business Directory` or `B2B Contact`.
- Saving the same result again does not create a second lead; the message says "already saved".
- One save can include at most 500 results.

### Technical
| Item | Value |
|---|---|
| Backend module | `crm_sources.py` (sources run in parallel) |
| API | `GET /api/crm-sources`, `POST /api/crm-sources/search`, `POST /api/crm-sources/save` (login required) |
| Frontend | `frontend/components/CrmSources.js` |
| Tests | `test_crm_sources.py` (20 tests, also in the hourly CI) |
| Proxy timeout | `frontend/next.config.mjs` → `experimental.proxyTimeout: 120000`, so long searches are not cut off at 30 s |

---

## ગુજરાતી

### હેતુ
- શહેર અને category પ્રમાણે **businesses** શોધવા (business directories માંથી).
- B2B contact databases માંથી **decision makers** (CEO, Founder, CTO…) શોધવા.
- પસંદ કરેલા results ને leads database માં lead તરીકે save કરવા.

### ક્યાં છે
- Sidebar → **4. CRM Sources**.

### કેવી રીતે વાપરવું
1. **Business category / keywords** લખો અને `Enter` કે `,` દબાવો. વધુમાં વધુ 10 keywords ઉમેરી શકાય, દરેક 80 અક્ષર સુધી.
2. **Decision-maker titles** (optional): આ ફક્ત contact databases માટે વપરાય છે.
3. **State** ફરજિયાત છે, **City** optional છે. City ખાલી રાખો તો state નું મુખ્ય શહેર વપરાય છે. City માં ફક્ત અક્ષરો ચાલે છે.
4. **Sources** માંથી એક કે વધુ પસંદ કરો. Grey દેખાતા source પર તેનું કારણ લખેલું હોય છે.
5. **Search** દબાવો. સામાન્ય રીતે 5–40 સેકન્ડ લાગે છે. દરેક source ની chip પર count, `failed` કે `skipped` દેખાય છે.
6. જોઈતા results tick કરો અને **Save to Leads** દબાવો. **Export CSV** થી દેખાતી યાદી download થાય છે.

### Sources
- **Key વગર ચાલે છે:** GoodFirms, OpenStreetMap, Zaubacorp.
- **`.env` માં API key જોઈએ:** Apollo, Hunter, Google Places, Snov, Lusha, RocketReach. Key વગર તેઓ `skipped` બતાવે છે.
- **ઉપલબ્ધ નથી:** Justdial, Sulekha, IndiaMART, TradeIndia, Clutch, YellowPages, AmbitionBox, Google Maps. આ sites block કરે છે અથવા ફક્ત browser JavaScript માં જ listing બતાવે છે. અમે captcha કે block bypass કરતા નથી.

### મર્યાદાઓ
- **OpenStreetMap:** public server ક્યારેક busy હોય છે (HTTP 502). ત્યારે chip પર `failed` આવે છે, એક મિનિટ પછી ફરી try કરો. QA દરમિયાન server બંધ હતું, એટલે OSM UNVERIFIED છે.
- **Zaubacorp:** શહેરની ફક્ત છેલ્લી ~90 નવી registered companies તપાસે છે, અને keyword ફક્ત company ના **નામ** માં શોધે છે. એટલે "software" જેવા શબ્દ માટે ઘણી વાર 0 result આવે છે.
- **Lusha:** ફક્ત preview આપે છે. પૂરા email અને phone માટે credits જોઈએ.
- **API sources:** દરેક search માં plan ના credits વપરાય છે.

### Result ના નિયમો
- બધા sources ના duplicate results દૂર થાય છે. Email કે phone વાળા results પહેલાં દેખાય છે.
- Save થયેલી lead નો source `CRM Source (<name>)` રહે છે.
- એ જ result ફરી save કરો તો નવી lead બનતી નથી, "already saved" મેસેજ આવે છે.

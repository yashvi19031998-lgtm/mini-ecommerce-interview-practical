# Scraping / Mining → Ecommerce Platforms — Module Guide

**Status:**
- **QA passed:** UI flow, filters, Deep Search, Export CSV, Save to Leads, and automated unit tests (15/15).
- **Verified:** Backend validation, search execution logic, multi-engine footprint query building, deduplication with contact merging, rate-limit resilience, and API integration.
- **UNVERIFIED / Known Behavior:** Live results via DuckDuckGo without API key return 0 results (expected because DuckDuckGo drops complex `site:` and quoted search queries from automated clients; reliable live results require a `BRAVE_SEARCH_API_KEY` or `SERPER_API_KEY`).
- QA report: `reports/qa/2026-11-12-ecommerce-platforms.md`. **Date:** 2026-11-12.

---

## English

### Purpose
- Discover **online stores, direct-to-consumer (D2C) brands, and digital sellers** in India for specific product categories (e.g., "handmade jewellery", "organic tea", "kurti", "leather shoes").
- Identifies independent online sellers that need digital agency services: web development, mobile apps, digital marketing, SEO, conversion rate optimization, or catalog management.

### How to Use
1. **Product / category keywords:** Up to 5 keywords or product types (e.g. handmade jewellery, organic tea, kurti, ceramic tableware).
2. **Target audience (optional):** Keeps stores whose name, category, or snippet mentions the audience words. If nothing matches, all results are retained with an informational notice.
3. **Location:** State (required, select "All India" or a specific Indian state) and City (recommended to narrow geographic focus).
4. **Sources:**
   - **Shopify stores:** Queries myshopify.com footprints and verified public product feeds.
   - **WooCommerce stores:** Queries WordPress/WooCommerce cart and product category footprints.
   - **Instagram shops:** Queries active Indian Instagram business profiles taking orders via DM or WhatsApp.
5. **Search Engine:** Choose between "Auto (best available)", Brave Search, Serper (Google), or DuckDuckGo (free, no key).
6. **Actions with results:**
   - **Deep Search:** Crawls store websites to retrieve missing email addresses, phone numbers, and social links. Instagram profile-only rows without an external website are automatically skipped.
   - **Export CSV:** Exports all filtered rows to a UTF-8 BOM CSV, shielding spreadsheet formula injection on special characters (`=`, `+`, `-`, `@`).
   - **Save to Leads:** Saves selected stores to the master leads registry under lead type `"Ecommerce Store"`. Saving existing records updates contact information without creating duplicates.

### Sources
| Source | Kind | Status | Description |
|---|---|---|---|
| Shopify stores | Store platform | Available | Finds D2C Shopify stores using `site:myshopify.com` and `"powered by Shopify"` footprints. Checks `/products.json?limit=1` on up to 15 stores to verify Shopify catalog endpoints. |
| WooCommerce stores | Store platform | Available | Finds WordPress / WooCommerce shops using `"add to cart" "woocommerce"` and `inurl:product-category` footprints. |
| Instagram shops | Store platform | Available | Finds Indian Instagram business pages taking orders via DM / WhatsApp (`site:instagram.com` with shopping intent terms). Filters for clean profile URLs, discarding posts, reels, and stories. |
| Amazon.in sellers | Marketplace | Unavailable | Amazon blocks automated web scraping; seller details require an interactive browser. |
| Flipkart sellers | Marketplace | Unavailable | Flipkart blocks automated scraping and API access. |
| Meesho sellers | Marketplace | Unavailable | Meesho supplier/seller profiles require authenticated login. |

### Result & Deduplication Rules
- **Deduplication:** Deduped per store domain (`dom:<domain>`) or Instagram handle (`ig:<handle>`).
- **Contact Merging:** When a duplicate row contains contact fields (email, phone, website, Instagram, Facebook) that the retained row lacks, the missing fields are automatically copied over rather than dropped.
- **Ordering:** Results with verified email or phone numbers appear first, followed by results with accessible websites, ordered alphabetically by store name.
- **Lead Mapping:**
  - Source: `Ecommerce (<source name>)`
  - Lead Type: `Ecommerce Store`
  - Description includes the e-commerce platform, category, verification note, and social links.

### Known Limits
- **Search Engine Dependency:** DuckDuckGo's public HTML interface frequently returns zero results for quoted or `site:` operator queries. For dependable production use, configure a `BRAVE_SEARCH_API_KEY` (free tier) or `SERPER_API_KEY` in Settings.
- **Marketplaces Unavailable:** Closed marketplace platforms (Amazon, Flipkart, Meesho) aggressively block direct automated scraping; manual browser inspection is necessary for those sellers.

### Technical Details
| Item | Details |
|---|---|
| Backend | `ecommerce_sources.py` |
| API Endpoints | `GET /api/ecommerce`, `POST /api/ecommerce/search`, `POST /api/ecommerce/save` |
| Deep Search | Reuses `POST /api/search-engine/deep` via `deep_search.py` |
| Caching | SQLite-backed via `search_cache.py` (module `ecommerce`, 48-hour TTL) |
| Frontend | `frontend/components/Ecommerce.js` (uses shared `MiningForm`) |
| Test Suite | `test_ecommerce_sources.py` (15 unit tests, 100% mocked, zero network calls) |

---

## ગુજરાતી

### હેતુ
- ભારતમાં ચોક્કસ પ્રોડક્ટ કેટેગરી માટે **ઓનલાઈન સ્ટોર્સ, D2C બ્રાન્ડ્સ અને ડિજિટલ સેલર્સ** શોધવા (દા.ત. "handmade jewellery", "organic tea", "kurti", "handicrafts").
- આ એવા ઈ-કોમર્સ વેપારીઓ છે જેમને વેબસાઈટ રીડિઝાઇન, એપ ડેવલપમેન્ટ, ડિજિટલ માર્કેટિંગ અને SEO સર્વિસિસની જરૂર હોય છે.

### કેવી રીતે વાપરવું
1. **પ્રોડક્ટ / કેટેગરી કીવર્ડ્સ:** 1 થી 5 કીવર્ડ્સ દાખલ કરો (જેમ કે kurti, organic tea, wooden toys).
2. **ટાર્ગેટ ઓડિયન્સ (ઓપ્શનલ):** સ્ટોરના નામ કે વિગતોમાં ચોક્કસ શબ્દો ફિલ્ટર કરવા. જો કોઈ મેળ ન પડે તો બધા પરિણામો નોંધ સાથે દર્શાવવામાં આવે છે.
3. **રાજ્ય અને શહેર:** રાજ્ય પસંદ કરવું ફરજિયાત છે ("All India" અથવા ચોક્કસ રાજ્ય). શહેર લખવાથી પરિણામો વધુ સચોટ બને છે.
4. **સોર્સિસ (Sources):**
   - **Shopify stores:** શોપિફાઇ આધારિત ઓનલાઇન સ્ટોર્સ.
   - **WooCommerce stores:** વર્ડપ્રેસ / વુકૉમર્સ આધારિત સ્ટોર્સ.
   - **Instagram shops:** ઇન્સ્ટાગ્રામ પર DM કે વોટ્સએપ દ્વારા ઓર્ડર લેતા બિઝનેસ પેજીસ.
5. **સર્ચ એન્જિન:** Auto, Brave Search, Serper (Google), અથવા DuckDuckGo પસંદ કરો.
6. **પરિણામો પર ક્રિયાઓ:**
   - **Deep Search:** સ્ટોરની વેબસાઈટ ખોલીને ઇમેઇલ, ફોન અને સોશિયલ લિંક્સ શોધે છે (ઇન્સ્ટાગ્રામ-ઓન્લી રોઝ આપોઆપ સ્કીપ થાય છે).
   - **Export CSV:** સુરક્ષિત UTF-8 BOM ફોર્મેટમાં ડાઉનલોડ થાય છે.
   - **Save to Leads:** પસંદ કરેલા સ્ટોર્સને મુખ્ય લીડ રજિસ્ટ્રીમાં `"Ecommerce Store"` તરીકે સેવ કરે છે.

### સોર્સિસની વિગત
- **Shopify Stores:** ઉપલબ્ધ (myshopify ફૂટપ્રિન્ટ્સ અને વેરિફાઈડ પબ્લિક પ્રોડક્ટ ફીડ્સ).
- **WooCommerce Stores:** ઉપલબ્ધ (વુકૉમર્સ કાર્ટ અને કેટેગરી ફૂટપ્રિન્ટ્સ).
- **Instagram Shops:** ઉપલબ્ધ (ફક્ત પ્રોફાઇલ લિંક્સ સાચવવામાં આવે છે, પોસ્ટ્સ કે રીલ્સ નહીં).
- **Amazon, Flipkart, Meesho:** ઉપલબ્ધ નથી (આ માર્કેટપ્લેસિસ ઓટોમેટેડ એક્સેસ બ્લોક કરે છે અથવા લૉગિન માંગે છે).

### મર્યાદાઓ
- DuckDuckGo મફત સર્ચમાં ક્યારેક ક્વોટેડ કે `site:` સર્ચના પરિણામો આપતું નથી. ઉત્તમ પરિણામો માટે Settings માં Brave Search અથવા Serper ની API Key ઉમેરવી.


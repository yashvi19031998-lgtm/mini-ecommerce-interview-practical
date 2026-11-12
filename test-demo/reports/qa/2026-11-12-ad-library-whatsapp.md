# QA Report — Scraping / Mining → Ad Library + WhatsApp Groups

**Date:** 2026-11-12 · **Build:** uncommitted working tree on `master` · **Result:** PASSED, with the UNVERIFIED items listed in section 5.

## English

### 1. Research (live)
- **DuckDuckGo** ignored `site:adstransparency.google.com` and `site:chat.whatsapp.com`. It returned unrelated pages, which are filtered out, so both modules need a Brave or Serper key for discovery.
- **Ad-tag detection, checked live on real sites:**
  - **Bombay Shaving Company:** Meta Pixel + Google Ads + GTM
  - **Mokobara:** Google Ads + GTM
  - **Prakash Infotech:** no ad tags, so correctly not listed
- **Meta Ad Library API:** outside the EU / UK only political & social-issue ads are available. This limit is documented in the UI note and the docs.

### 2. Automated tests (Python, no network)
| Suite | Result |
|---|---|
| `test_adlibrary_sources.py` (new) | 11/11 |
| `test_whatsapp_sources.py` (new) | 10/10 |
| Full regression (23 suites) | **362/362** |

**Ad Library tests cover:**
- tag detection; GTM alone does not count
- junk / list-article / government result filters
- the 15-site budget
- Meta API params for India, grouping per page, a rejected token
- Transparency advertiser-only filter
- dedupe that merges the ads link
- per-source error isolation
- API with cache and save

**WhatsApp tests cover:**
- invite-code parsing and name cleaning
- only real `chat.whatsapp.com` results are kept
- directories never fetch whatsapp.com; the 5-page budget
- dedupe keeps the best name
- error isolation and the DuckDuckGo hint
- no phone field in leads
- the "Group members" source can never be selected
- API

### 3. Browser QA (Playwright, real backend) — 8/8 pass
| ID | Test | Result |
|---|---|---|
| AW01 | Menu: Ad Library and WhatsApp Groups live; only Social Media still "Soon" (Gemini is building it) | PASS |
| AW02 | Ad Library sources (3 groups, 3 disabled with reasons) + validation | PASS |
| AW03 | Ad-signal badges (rows seeded from the live tag check) + "3 website(s) checked, 1 without ad tags" note | PASS |
| AW04 | Deep Search on 2 advertisers (Found / Website only) + Save → 2 new `Active Advertiser` leads | PASS |
| AW05 | WhatsApp: privacy note, "Group members" disabled, 2 groups with Join links, no phone column | PASS* |
| AW06 | WhatsApp Save → 2 `WhatsApp Group (community)` leads with **no phone and no website**; CSV without phone columns | PASS |
| AW07 | Mobile 390 px | PASS |
| AW08 | No console errors | PASS |

\* WhatsApp rows were sample invite codes seeded through the search cache. The app never contacts WhatsApp, so the codes are never opened.

### 4. Bug found and fixed
**WhatsApp invite links and RERA register links became the lead's "website".**
- **Cause:** the lead normalizer fills an empty website from the source link, and these domains were not in its exclusion list.
- **Effect:** a fake website, and a risk of domain-based duplicate merges and outreach to wrong sites.
- **Fix:** `whatsapp.com`, `wa.me`, `gov.in` and `nic.in` were added to `lead_normalizer.INVALID_DOMAINS`, with a regression test.
- **Scope:** this also fixes Real Estate (RERA) saves.

### 5. UNVERIFIED
| Item | Why |
|---|---|
| Live website discovery for Ad Library / WhatsApp invite links | DuckDuckGo returned nothing today; needs `BRAVE_SEARCH_API_KEY` or `SERPER_API_KEY` |
| Meta Ad Library API | No `META_AD_LIBRARY_TOKEN` |
| Google Ads Transparency results | Depend on a working search engine |

### 6. Data safety
- `all_leads_master.csv` was restored after QA (md5 `963d94bc…` matches).
- SMTP, IMAP and Supabase were off during QA.

## ગુજરાતી
- **Ad Library:** live tapas ma websites par ad tags બરાબર મળ્યા (Bombay Shaving: Meta + Google Ads, Mokobara: Google Ads). Ad tag વગરની website list માં નથી આવતી.
- **WhatsApp Groups:** ફક્ત group નું નામ અને invite link. Members કે phone numbers ક્યારેય નહીં (WhatsApp ના નિયમો અને DPDP Act).
- **Bug fix:** WhatsApp invite link અને સરકારી RERA page lead ની "website" બની જતાં હતાં. હવે નહીં.
- **Tests:** 362/362, browser 8/8 pass. Live search Brave / Serper key ઉમેર્યા પછી ચકાસવું પડશે (**UNVERIFIED**).

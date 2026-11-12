# Scraping / Mining → WhatsApp Groups — Module Guide

**Status:**
- **QA passed:** UI, Save, CSV, the privacy rules and unit tests.
- **UNVERIFIED:** live discovery (DuckDuckGo ignores `site:chat.whatsapp.com`; needs a Brave / Serper key).
- QA report: `reports/qa/2026-11-12-ad-library-whatsapp.md`. **Updated:** 2026-11-12.

---

## English

### Purpose
Find **public WhatsApp group invite links** for a topic (e.g. real estate, startups, freelancers, wholesale), so you can join communities where your clients are.

### What is collected — and what is never collected
| Collected | Never collected |
|---|---|
| Group name (as the search engine shows it), the public invite link, the topic, the page it was found on | Group members, phone numbers, messages |

Why members are never collected:
- It needs joining groups with automation, and WhatsApp bans such numbers.
- Personal phone numbers are protected by **India's DPDP Act 2023**.

The app also **never requests chat.whatsapp.com / whatsapp.com itself**.

### Sources
| Source | How |
|---|---|
| Invite links (search engine) | `site:chat.whatsapp.com "<topic>"`. Only real invite URLs are kept, and the group name comes from the result title. |
| Group link directories | Public "WhatsApp group links" pages found through the search engine. Links come from the snippet and from up to 5 pages (guarded fetch, HTML cache, our own User-Agent). The group name comes from the link text or the heading above it. |
| Group members / phone numbers | **Not available** (reason above) |

### How to use
1. Enter **Topics** (up to 5). Target audience, State and City are optional.
2. Click **Search**. The results table shows group, topic, a **Join** link and where the link was found.
3. **Export CSV** or **Save to Leads**.
   - Groups are saved with the lead type `WhatsApp Group (community)`.
   - They are saved **without phone or website**; the invite link is kept as the source link.
   - The same group is never saved twice.

### Technical
| Item | Value |
|---|---|
| Backend | `whatsapp_sources.py` |
| API (login required) | `GET /api/whatsapp`, `POST /api/whatsapp/search`, `POST /api/whatsapp/save` |
| Frontend | `WhatsAppGroups.js` (shared `MiningForm`) |
| Tests | `test_whatsapp_sources.py` (10 tests, in hourly CI) |

---

## ગુજરાતી

### હેતુ
કોઈ topic (real estate, startup, freelancers…) માટે **public WhatsApp group invite links** શોધવા, જેથી જ્યાં તમારા clients છે એ communities માં જોડાઈ શકાય.

### શું મળે છે અને શું ક્યારેય નહીં
- **મળે છે:** group નું નામ, invite link અને topic.
- **ક્યારેય નહીં:** members, phone numbers કે messages.
  - Members કાઢવા માટે automation થી group માં જોડાવું પડે, અને WhatsApp એ number ban કરે છે.
  - India નો **DPDP Act 2023** લોકોના personal numbers ની સુરક્ષા કરે છે.
- App પોતે ક્યારેય WhatsApp ની site પર request મોકલતી નથી.

### મર્યાદા
DuckDuckGo `site:chat.whatsapp.com` ignore કરે છે, એટલે સારાં results માટે **Brave કે Serper key** જોઈએ.

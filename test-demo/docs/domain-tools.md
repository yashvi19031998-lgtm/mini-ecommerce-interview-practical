# Domain Tools — Module Guide

**Status:**
- **QA passed:** live (2026-11-12).
- QA report: `reports/qa/2026-11-12-domain-tools.md`. **Updated:** 2026-11-12.

---

## English

### Menus
| Menu | Input | Output | Source |
|---|---|---|---|
| **Domain Age & Expiry** | Up to 50 domains, websites or e-mail addresses (the domain is taken from each) | Registered date and age, expiry date and days left, registrar, nameservers, DNS host. Flags: **New (under 1 year)**, **Expires in N days** (≤ 60), Expired, On hold, Not registered. | **RDAP**: the registries' official JSON service, found through IANA's bootstrap list. Endings without RDAP (e.g. `.co`) fall back to DNS (registered yes / no, no dates). |
| **Email & DNS Checker** | Up to 50 domains | Mail provider (Google Workspace, Microsoft 365, Zoho, GoDaddy / Titan / Hostinger hosting mail…), MX hosts, SPF, DMARC policy, DNS host, website address. **Problems** and **pitches**: business e-mail setup, move from hosting mail, deliverability (SPF / DKIM / DMARC), website development. | Public DNS only |
| **New Domains Finder** | Up to 5 keywords (3+ letters), last 1 / 3 / 7 days, optional endings | Domains registered in those days that contain a keyword (hyphens ignored), newest first, up to 500 | **WhoisDS** free daily list. It covers gTLDs (.com, .net, .org, .online, .store, .shop…) and has **no `.in`**. Each day is downloaded once and kept for 10 days in the git-ignored cache. |
| **Domain Availability** | A name; endings (.com, .in, .co.in, .net, .org, .online, .store, .shop, .site, .tech, .co, .biz, .info, .app); optional variants | available / taken / unknown per name, with created / expiry / registrar for taken ones. Variants: hyphenated, get…, my…, …india, …online, …hq, the… (.com / .in). At most 30 checks. | RDAP (404 = available) or DNS |

### Save to Leads
Age, Email & DNS, and New Domains results can be saved:
- company = the domain, website = `https://domain`, source **Domain Tools**
- a one-line summary in **website_signals** ("Website check"), e.g. `Domain registered 2023-01-04 (3 yr 10 mo), expires 2033-01-04, registrar GoDaddy`

### Privacy and rules
- RDAP: only registrar, dates, status and nameservers are read. **Registrant / contact entities are ignored.**
- DNS: public records only; mail servers are never contacted.
- **crt.sh (certificate logs) is not used**: its robots.txt disallows automated access. WhoisDS downloads are checked against its robots.txt for the app's User-Agent.
- Every HTTP request goes through the URL guard (public addresses only), with an honest User-Agent and size limits (RDAP 1 MB, daily list 20 MB zip / 50 MB unpacked).
- **DNS retries:** a timed-out query is retried once after 1.5 s. Home routers often time out on the first lookup of a new name. The same fix was applied to the Bulk Email Verifier.

### Technical
| Item | Value |
|---|---|
| Backend | `domain_tools.py` |
| API (login required) | `GET /api/domain-tools`, `POST /api/domain-tools/{age,dns,new,available}`. Save: `/api/bulk-contacts/save` (kind `websites`). |
| Frontend | `DomainTools.js` (prop `tool`), sidebar group **Domain Tools** (`DOMAIN_ITEMS`) |
| Tests | `test_domain_tools.py` (9 tests, in hourly CI) |

---

## ગુજરાતી

### Menus
- **Domain Age & Expiry:** domain ક્યારે register થયું અને ક્યારે expire થાય છે. નવી companies (1 વર્ષથી ઓછી) અને જલ્દી expire થતાં domains ઓળખાય છે.
- **Email & DNS Checker:** company નું email કોણ ચલાવે છે (Google Workspace, Zoho, hosting mail), SPF / DMARC set છે કે નહીં. એના પરથી શું વેચી શકાય એ સૂચવાય છે.
- **New Domains Finder:** છેલ્લા દિવસોમાં register થયેલાં, તમારા keyword વાળાં નવાં domains. આ નવી શરૂ થયેલી businesses છે.
  - એમાં `.com`, `.org` જેવાં domains આવે છે; `.in` નથી આવતાં.
- **Domain Availability:** નામ `.com`, `.in`, `.co.in` વગેરેમાં ખાલી છે કે નહીં, અને નજીકનાં બીજાં નામ પણ સૂચવે છે.

### Privacy
Domain ના માલિકની અંગત માહિતી ક્યારેય વંચાતી નથી. ફક્ત registrar, તારીખો અને DNS જોવાય છે.

# QA Report — Domain Tools

**Date:** 2026-11-12 · **Build:** uncommitted working tree on `master` · **Result:** PASSED.

## English

### 1. Scope and sources (checked live before building)
| Source | Result |
|---|---|
| IANA RDAP bootstrap + registry RDAP | Works for .com (Verisign), .in / .co.in (NIXI), .org, .online / .store / .tech (Radix). An unregistered name gives 404. `.co` has no RDAP, so it falls back to DNS. |
| crt.sh (certificate logs) | robots.txt `Disallow: /` (and it returned 502) → **not used** |
| WhoisDS daily newly-registered-domains list | Allowed for the app's User-Agent (`*` only blocks /login/). About 70,000 gTLD domains per day; no .in. |
| DNS | dnspython, public records only |

### 2. Automated tests (Python, no network)
| Suite | Result |
|---|---|
| `test_domain_tools.py` (new) | 9/9 |
| Full regression (31 suites) | **483/483** |

**What the new tests cover:**
- **Input cleaning:** URL, e-mail, sub-domain → registrable domain (`.co.in` kept).
- **Age & expiry:**
  - age, expiry and the flags (new, expiring, not registered)
  - **registrant data never read**
  - rate limit; DNS fallback for `.co`
- **Availability:** taken / available, variants, limits, bad input.
- **DNS:** Google Workspace; GoDaddy hosting mail without SPF / DMARC → pitches; no MX / no A; open `?all` SPF; NXDOMAIN; **timeout → pause → retry**.
- **New domains:**
  - keyword (case and hyphens ignored); the endings filter
  - newest day first, no duplicates, a missing day noted
  - **the second run is served from the disk cache**
  - robots.txt refusal → nothing downloaded
- **API:** 401 / 400 / 404; save stores the source `Domain Tools` and the summary in website_signals.

### 3. Browser QA (Playwright, real backend, **live sources**) — 7/7 pass
| ID | Test | Result |
|---|---|---|
| DT01 | Sidebar group "Domain Tools" with 4 items; breadcrumb; validation. | PASS |
| DT02 | Age: mokobara.com (2018-10-23, Tucows, 345 days left), mokobara.in (GoDaddy, from a URL), google.co.in (from an e-mail, MarkMonitor), an unregistered name, invalid input skipped. Save → source `Domain Tools`, summary in website_signals. | PASS |
| DT03 | DNS: mokobara.com = Google Workspace, DMARC none, Cloudflare; example.com = no e-mail (null MX); infosys.com = own server, DMARC reject. | PASS |
| DT04 | New domains: "bakery" + "realty", 3 days → **102 new domains**. | PASS |
| DT05 | Availability "Mokobara": .com and .in taken (with dates), .co.in available; 13 of 15 names free. | PASS |
| DT06 | CSV export; mobile at 390 px, no sideways scroll. | PASS |
| DT07 | No console errors. | PASS |

### 4. Bugs found and fixed
1. **DNS "unknown" for every domain** in the first live run. The home router times out on the first MX lookup of a new name and answers the repeat from its cache. A retry now waits 1.5 s first. The same change was made to the Bulk Email Verifier.
2. **The retry pause could not be mocked** (a default argument bound at import time), so a test spent a real 1.5 s waiting. The pause is now resolved when it is called.
3. **The new-domain cache path was fixed at import time.** It now follows the cache folder setting, which also lets tests use a temporary folder.

### 5. Data safety
- `all_leads_master.csv` was restored after QA (md5 `963d94bc…` matches).
- The daily-list cache lives in the git-ignored `html_cache/nrd/`.
- SMTP, IMAP and Supabase were off during QA.

## ગુજરાતી
- **Tests:** browser QA 7/7 pass અને unit tests 483/483 pass.
- **Live પરિણામ:**
  - Domain ની ઉંમર અને expiry સાચી આવી (mokobara.com: 2018 માં register થયું).
  - Email checker એ Google Workspace ઓળખ્યું.
  - 3 દિવસમાં 102 નવાં domains મળ્યાં.
  - "Mokobara" નામ માટે .co.in ખાલી બતાવ્યું.
- **ઉપયોગ નથી કર્યો:** crt.sh, કારણ કે એનો robots.txt ના પાડે છે.
- **3 bugs fix થયા.** સૌથી મહત્ત્વનો: router નો ધીમો DNS, જે Bulk Email Verifier માં પણ સુધર્યો.

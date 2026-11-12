# QA Report — Utilities → Website Analyzer

**Date:** 2026-11-12 · **Build:** uncommitted working tree on `master` · **Result:** PASSED.

## English

### 1. Automated tests (Python, no network)
| Suite | Result |
|---|---|
| `test_website_analyzer.py` (new) | 10/10 |
| `test_website_signals.py` (existing) | 5/5 |
| Full regression (30 suites) | **474/474** |

**What the new tests cover:**
- **A good site:** Shopify, GA4 (gtag.js is not counted as GTM), Meta Pixel, WhatsApp chat, structured data, security headers, contacts, score ≥ 90, no payment pitch for Shopify.
- **A bad site:** no HTTPS, not mobile-friendly, slow, no description / H1 / sitemap, images without alt, only Universal Analytics, old jQuery, old copyright year. A **link to a blogspot site is not "built with Blogger"**. Each pitch is listed once.
- **Builder / SSL / indexing:** Wix builder, noindex, mixed content, SSL expiring soon, an untrusted SSL certificate.
- **Runner:** a private address blocked; robots.txt disallow reported; timeout; HTTP 503; duplicates; the limit of 5.
- **Redirect guard:** a redirect to a private address is **blocked** (`fetch_live`).
- **SSL:** an SSL connection error is handled.
- **API:** 401 / 400. Save stores the source and **website_signals** in the leads file.

### 2. Browser QA (Playwright, real backend, **live websites**) — 6/6 pass
| ID | Test | Result |
|---|---|---|
| WA01 | Sidebar group "Utilities" → Website Analyzer; breadcrumb; validation. | PASS |
| WA02 | 5 entries (mokobara.com twice, python.org, http://example.com, http://127.0.0.1/admin) → 3 analysed, average 70/100. **Sorted lowest first:** example.com 32 Poor. The private address is **blocked**; the duplicate is removed. | PASS |
| WA03 | mokobara.com details: Shopify, GTM, Clarity, Google Ads, Tailwind, Cloudflare; SSL valid until 2026-12-26 (Let's Encrypt); HSTS; the pitch list. | PASS |
| WA04 | Save example.com → source `Utilities (Website Analyzer)`, website_signals "Score 32/100 (Poor): No HTTPS…". | PASS |
| WA05 | CSV export (3 rows); mobile at 390 px, no sideways scroll. | PASS |
| WA06 | No console errors. | PASS |

**Live results:**
| Site | Score | Main findings |
|---|---|---|
| mokobara.com | 96 Good | No H1 |
| python.org | 82 Good | No sitemap; no analytics |
| example.com | 32 Poor | No HTTPS; not mobile-friendly; no description; and more |

### 3. Bugs found and fixed
1. **False "built with Blogger"** for python.org, because the page links to a blogspot blog. Fixed in the analyzer **and** in the shared `website_signals.py` (Weebly too), which also feeds the leads "Website check" field.
2. **"Old jquery 1.8"** lost its capitalisation.
3. **Payment-gateway pitch** was shown to Shopify stores, which have payments built in.
4. **The http → https check** was unclear; it is now a separate small request without following the redirect.

### 4. Data safety
- `all_leads_master.csv` was restored after QA (md5 `963d94bc…` matches).
- SMTP, IMAP and Supabase were off during QA.

## ગુજરાતી
- **Tests:** browser QA 6/6 pass અને unit tests 474/474 pass.
- **Live પરિણામ:** mokobara.com 96, python.org 82 અને example.com 32 (Poor) આવ્યા. List માં સૌથી ઓછા score વાળી site ઉપર આવે છે.
- **Suraksha:** private address (127.0.0.1) block થયું.
- **4 bugs fix થયા.** એમાં જૂના `website_signals.py` નો ખોટો "Blogger" પણ છે.

# Utilities → Website Analyzer — Module Guide

**Status:**
- **QA passed:** live (2026-11-12).
- QA report: `reports/qa/2026-11-12-website-analyzer.md`. **Updated:** 2026-11-12.

---

## English

### Purpose
Check a prospect's website **before the sales call**. You get a 0–100 health score, the problems found, and **what to pitch** (SSL, responsive redesign, SEO, speed, analytics, ads, WhatsApp chat, payment gateway, custom website).

### What is checked (home page, read like one visit)
| Section | Checks |
|---|---|
| **Overview** | Final address, redirects, HTTP status, response time (total and first byte), page size, server |
| **Technology** | CMS / site builder / shop platform, JS frameworks (with the jQuery version), analytics (GA4, old Universal Analytics, GTM, Clarity, Hotjar), ad pixels (Meta, Google Ads, LinkedIn, Microsoft), chat (WhatsApp, Tawk, Intercom…), Indian payment gateways (Razorpay, PayU, Paytm, CCAvenue) and Stripe |
| **SEO** | Title (and length), meta description (and length), H1, canonical, noindex, Open Graph, `lang`, images without alt text, structured data, robots.txt, sitemap |
| **Security** | HTTPS, http → https redirect, SSL certificate (expiry, issuer, trust), HSTS / CSP / X-Frame-Options / X-Content-Type-Options / Referrer-Policy, mixed content |
| **Mobile** | Viewport tag |
| **Contacts** | E-mails, phones, social links, WhatsApp link and contact-page link on the home page |
| **Old-site signals** | Old WordPress / jQuery, a copyright year 3+ years old, Flash (shared with `website_signals.py`) |

### Score
Starts at 100; each problem subtracts points. The biggest are: no HTTPS −20, not mobile-friendly −20, an SSL problem −15, noindex −15 and slow over 3 s −10.
- **Good:** 80 or more.
- **Needs work:** 55–79.
- **Poor:** below 55.

The list is sorted lowest score first, because those are the best prospects.

### Save to Leads
Selected sites are saved with the company name, website, e-mails, phones and social links.
- **Source:** `Utilities (Website Analyzer)`.
- **The problems found** go into the lead's **website_signals** ("Website check") field, e.g. `Score 32/100 (Poor): No HTTPS…`. The AI qualifier already reads that field.

### Rules
- **Light touch.** Only the home page is read: one visit, plus one small `http://` request to test the redirect, a sitemap check and the SSL handshake.
- **robots.txt** is obeyed; a disallowed home page is reported, not read.
- **Safety:** public addresses only, checked on every redirect hop and before the SSL check. At most 3 MB is read. An honest User-Agent is sent.
- **Limits:** up to 25 sites per run, sent 5 at a time (different sites in parallel). Duplicates (`www`, `http`) are analysed once.

### Shared fix
`website_signals.py` reported "built with Blogger" for any page that merely **links** to a blogspot site (and the same for Weebly). It now needs Blogger's own asset host or generator tag. This also corrects the "Website check" text on future leads.

### Technical
| Item | Value |
|---|---|
| Backend | `website_analyzer.py` (reuses `website_signals`, `adlibrary_sources.detect_ad_tags`, `web_crawler.page_contacts`, `robots_policy`) |
| API (login required) | `POST /api/utilities/website-analyzer` (`{urls}`, up to 5). Save: `/api/bulk-contacts/save` (kind `websites`, `website_signals` passed through). |
| Frontend | `WebsiteAnalyzer.js`, sidebar group **Utilities** (`UTILITY_ITEMS`; more utilities can be added there) |
| Tests | `test_website_analyzer.py` (10 tests, in hourly CI) |

---

## ગુજરાતી

### હેતુ
Sales call કરતાં પહેલાં prospect ની website તપાસવી. તમને મળે છે:
- 0–100 નો score
- website માં શું ખોટું છે
- **શું વેચી શકાય:** SSL, mobile redesign, SEO, speed, analytics, ads, WhatsApp chat વગેરે

### શું તપાસાય છે
- **Technology:** website કઈ technology પર છે (WordPress, Shopify, Wix…).
- **SEO:** title, description અને H1.
- **Security:** HTTPS અને SSL ક્યારે expire થાય છે.
- **Mobile:** site mobile-friendly છે કે નહીં.
- **Speed:** page કેટલી ઝડપથી ખૂલે છે.
- **Contacts:** home page પરના email, phone અને WhatsApp link.

### Save to Leads
Website ની problems lead ના **"Website check"** માં save થાય છે, અને AI qualifier એ વાંચે છે.

### નિયમો
- ફક્ત home page વંચાય છે.
- robots.txt માનવામાં આવે છે.
- ફક્ત public addresses ખૂલે છે.

# QA Report — Web Crawler

**Date:** 2026-11-12 · **Build:** uncommitted working tree on `master` · **Result:** PASSED.

## English

### 1. Scope
The owner chose four submenus: **Site Crawler**, **Link Harvester**, **Keyword Page Finder** and **Sitemap Explorer**.

### 2. Automated tests (Python, no network)
| Suite | Result |
|---|---|
| `test_web_crawler.py` (new) | 12/12 |
| Full regression (28 suites) | **449/449** |

**What the new tests cover:**
- **Validation:** every limit.
- **Same page:** `www` / no-`www` / trailing `/` are one page.
- **Crawl:**
  - robots.txt disallow obeyed and counted; files and `mailto:` links never fetched; other sites not crawled
  - depth limit; the time budget stops the run with a note; a pause between pages
  - contacts per page and per site; the site name
  - lead source label (an unknown label falls back)
- **Link harvesting:** generic "Visit website" text ignored; social sites and portals skipped; government sites flagged; "Next" pages followed.
- **Keywords:** counts, in-URL matches, whole-word snippets.
- **Sitemaps:** an index with children (other sites' sitemaps ignored), `&amp;` decoded, sections, newest / oldest dates, a missing default name not counted as an error, an **entity-expansion file not expanded**, the "no sitemap" note.
- **robots_policy:** rules, crawl-delay, `Sitemap:` lines, a 404 = allowed, a 500 = not allowed, a private address blocked.
- **API:** 401 / 400 / 404.

### 3. Browser QA (Playwright, real backend, **live websites**) — 7/7 pass
| ID | Test | Result |
|---|---|---|
| WC01 | Sidebar group "Web Crawler" with 4 items; breadcrumb; validation. | PASS |
| WC02 | Site Crawler: mokobara.com, 10 pages, depth 1 → several e-mails and 2 phones. Save → lead "**Mokobara**", source `Web Crawler (Site Crawler)`. | PASS |
| WC03 | Link Harvester: a GoodFirms list page → **49 company websites**. Get contacts for 2 → found on 2 of 2. | PASS |
| WC04 | Keyword Page Finder: mokobara.com, "warranty" + "franchise" → warranty on 10 pages (one has it in the URL, 9 mentions); franchise 0. | PASS |
| WC05 | Sitemap Explorer: mokobara.com → **436 pages** (collections 172, products 113, blogs 110, pages 39); the filter works. python.org → "No sitemap found". | PASS |
| WC06 | CSV export (436 rows); mobile at 390 px, no sideways scroll. | PASS |
| WC07 | No console errors. | PASS |

### 4. Bugs found and fixed during the build
1. **Duplicate pages.** `www.mokobara.com` and `mokobara.com` were crawled as two pages. Pages are now keyed without `www` or a trailing `/`, and redirect targets count as seen.
2. **Missing default sitemap names** (`/sitemap.xml` 404) were reported as "pages could not be opened". They no longer are.
3. **Company name** was the full page title. It is now the site's own name (JSON-LD / `og:site_name`), with the cleaned title as a fallback.
4. **Lead source** for crawler saves said "Bulk Contacts". It is now `Web Crawler (Site Crawler / Link Harvester)`, and only known labels are accepted.
5. **robots.txt for GST seller pages** was fetched without the URL guard. Both modules now use `robots_policy.py`, which fetches through the guard.

### 5. Data safety
- `all_leads_master.csv` was restored after QA (md5 `963d94bc…` matches).
- SMTP, IMAP and Supabase were off during QA.

## ગુજરાતી
- **Tests:** browser QA 7/7 pass અને unit tests 449/449 pass.
- **Live પરિણામ:**
  - Mokobara માંથી emails અને phones મળ્યા.
  - GoodFirms ની યાદીમાંથી 49 company websites મળી.
  - "warranty" શબ્દ 10 pages પર મળ્યો.
  - Sitemap માંથી 436 pages ની યાદી મળી.
- **5 bugs fix થયા.** એક સુરક્ષા સુધારો પણ છે: GST seller pages નો robots.txt હવે URL guard થી જ ખૂલે છે.

# HTML & Search Cache — Rules

**Status:** QA passed (unit tests; browser check of the "saved results" note) · **Updated:** 2026-11-12

## English

### Why
- **Fewer blocks:** the same site is not asked again and again.
- **Speed:** a repeated search answers in under a second.
- **Re-use:** saved HTML can be processed again later (GST number, Instagram link…) without downloading again.

### Rule 1 — Page cache (`html_cache_manager.py`, folder `html_cache/`)
| Rule | Value |
|---|---|
| A page younger than `HTML_CACHE_MAX_AGE_DAYS` (default 30) | Served from disk, no request |
| Older page | Downloaded again; if the site blocks or fails, the old copy is used |
| Captcha / "access denied" pages | **Never saved** |
| Pages older than 3× the max age | Deleted |
| Folder bigger than `HTML_CACHE_MAX_MB` (default 500) | Oldest pages deleted first |
| Every saved page | Recorded in `html_cache/index.sqlite` (url, domain, saved time, size) |

- Re-process saved HTML with `list_cached_pages("acme.in")` and `read_cached_html(url)`. These never go online.
- Pages saved before 2026-11-12 have no URL record. They still work as cache hits, but they can't be listed.

### Rule 2 — Search results cache (`search_cache.py`, `html_cache/search_results.sqlite`)
| Module | Same search answered from saved results for |
|---|---|
| Job Portal Scraper | `JOB_SEARCH_CACHE_HOURS` (default **6 hours**) — jobs change fast |
| CRM Sources | `CRM_SEARCH_CACHE_HOURS` (default **72 hours**) — directories change slowly |

- **"Same search"** means the same inputs, ignoring upper/lower case, order and extra spaces.
- **Saved only when complete:** if any source failed, or nothing was found, the search is **not** saved. A temporary block is never repeated from the cache.
- **The page says when results are saved:** "Showing saved results from 2 h ago", with a **Search live again** button that always goes to the live sites.
- **Clean-up:** saved searches older than `SEARCH_CACHE_KEEP_DAYS` (default 30) are deleted. Setting the hours to `0` turns the cache off for that module.

### Rule 3 — Storage
- `html_cache/` is in `.gitignore`, so it is **never committed**.
- On GitHub Actions the folder is kept between runs (actions/cache).
- The database files are never deleted by the clean-up.

## ગુજરાતી

### કેમ?
- એક જ site પર વારંવાર request નથી જતી, એટલે **block થવાનું ઓછું** થાય છે.
- એ જ search ફરી કરો તો **1 સેકન્ડથી ઓછા** સમયમાં જવાબ આવે છે.
- Save થયેલી HTML માંથી પછી પણ નવી માહિતી (GST, Instagram link) કાઢી શકાય છે, ફરી download કર્યા વગર.

### નિયમ 1 — Page cache
- **30 દિવસ સુધી:** page disk પરથી જ વંચાય છે, internet પર request નથી જતી.
- **જૂનું page:** ફરી download થાય છે. Site block કરે તો જૂની copy વપરાય છે.
- **Captcha / access denied page:** ક્યારેય save થતું નથી.
- **Size limit:** folder 500 MB થી મોટું થાય તો સૌથી જૂનાં pages પહેલાં delete થાય છે.
- **Index:** દરેક page નો URL, domain અને તારીખ `index.sqlite` માં નોંધાય છે.

### નિયમ 2 — Search results cache
- **Job Portal:** એ જ search 6 કલાક સુધી saved results માંથી આવે છે.
- **CRM Sources:** એ જ search 3 દિવસ સુધી saved results માંથી આવે છે.
- કોઈ source fail થયો હોય કે 0 results આવ્યાં હોય, તો એ search **save થતું નથી**.
- Page પર "Showing saved results from…" દેખાય છે. **Search live again** બટન દબાવવાથી હંમેશાં live search થાય છે.
- 30 દિવસથી જૂનાં saved searches આપોઆપ delete થાય છે.

### નિયમ 3 — Storage
- `html_cache/` folder GitHub પર ક્યારેય commit થતું નથી.

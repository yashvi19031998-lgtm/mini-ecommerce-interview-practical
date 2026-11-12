"""Utilities -> Website Analyzer: one report per website, written for selling web / IT services.

For each site (home page only, read like one browser visit):
  overview   final address, redirects, HTTP status, response time, page size, server
  technology CMS / site builder / shop platform, JS frameworks, analytics, ad pixels, chat widgets, payment gateways
  seo        title, description, H1, canonical, noindex, Open Graph, language, images without alt text,
             structured data, robots.txt and sitemap
  security   HTTPS, http -> https redirect, SSL certificate expiry, HSTS and other security headers, mixed content
  mobile     viewport tag
  contacts   e-mails, phones, social links, WhatsApp link, contact page link
  score      0-100 health score, the problems found, and "opportunities" (what to pitch)

Rules: robots.txt obeyed (robots_policy), public addresses only (checked on every redirect and before the SSL
check), honest User-Agent, at most 3 MB read per page, up to 5 sites per request (in parallel - different sites).
"""
import datetime
import re
import socket
import ssl
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

import adlibrary_sources
import deep_search
import html_cache_manager as hcm
import robots_policy
import search_engine as se
import web_crawler
import website_signals

MAX_SITES = 5
MAX_BYTES = 3 * 1024 * 1024
TIMEOUT = 15

# (name, category, regex on the lower-cased HTML)
TECH = [
    ("WordPress", "cms", r"wp-content/|wp-includes/|name=\"generator\" content=\"wordpress"),
    ("WooCommerce", "shop", r"woocommerce"),
    ("Shopify", "shop", r"cdn\.shopify\.com|shopify\.theme|myshopify\.com"),
    ("Magento", "shop", r"mage/cookies|magento|static/version\d+/frontend"),
    ("BigCommerce", "shop", r"cdn\d*\.bigcommerce\.com"),
    ("OpenCart", "shop", r"catalog/view/theme|route=product"),
    ("PrestaShop", "shop", r"prestashop"),
    ("Wix", "builder", r"wixstatic\.com|x-wix-|wix\.com website builder"),
    ("Squarespace", "builder", r"squarespace\.com|static1\.squarespace"),
    ("Webflow", "builder", r"webflow\.(?:com|io)|data-wf-page"),
    ("GoDaddy builder", "builder", r"godaddysites\.com|img1\.wsimg\.com"),
    ("Zoho Sites", "builder", r"zohositescontent|sites\.zoho"),
    # builders: only their own asset hosts / generator tags - a plain link to a blogspot / weebly site is not enough
    ("Blogger", "builder", r"www\.blogger\.com/static|content=['\"]blogger['\"]"),
    ("Weebly", "builder", r"editmysite\.com|weeblycloud\.com"),
    ("Joomla", "cms", r"/media/jui/|content=\"joomla"),
    ("Drupal", "cms", r"drupal-settings-json|/sites/default/files/|content=\"drupal"),
    ("Next.js", "framework", r"__next_data__|/_next/static/"),
    ("Nuxt", "framework", r"__nuxt__|/_nuxt/"),
    ("React", "framework", r"data-reactroot|react-dom(?:\.production)?(?:\.min)?\.js"),
    ("Vue.js", "framework", r"vue(?:\.runtime)?(?:\.global)?(?:\.prod)?(?:\.min)?\.js|data-v-[0-9a-f]{8}"),
    ("Angular", "framework", r"ng-version=|angular(?:\.min)?\.js"),
    ("jQuery", "framework", r"jquery[-.]?\d?[\d.]*(?:\.min)?\.js"),
    ("Bootstrap", "framework", r"bootstrap(?:\.bundle)?(?:\.min)?\.(?:css|js)"),
    ("Tailwind CSS", "framework", r"tailwind"),
    ("Google Analytics 4", "analytics", r"gtag/js\?id=g-|['\"]g-[a-z0-9]{6,}['\"]"),
    ("Universal Analytics (retired)", "analytics", r"['\"]ua-\d{4,}-\d+['\"]|google-analytics\.com/analytics\.js"),
    ("Google Tag Manager", "analytics", r"googletagmanager\.com/gtm\.js|gtm-[a-z0-9]{4,}"),
    ("Microsoft Clarity", "analytics", r"clarity\.ms"),
    ("Hotjar", "analytics", r"static\.hotjar\.com|hjid"),
    ("WhatsApp chat", "chat", r"wa\.me/|api\.whatsapp\.com/send|whatsapp\.com/send"),
    ("Tawk.to", "chat", r"embed\.tawk\.to"),
    ("Intercom", "chat", r"widget\.intercom\.io|intercomsettings"),
    ("Zendesk", "chat", r"static\.zdassets\.com|zopim"),
    ("Freshchat", "chat", r"wchat\.freshchat\.com|freshworks"),
    ("Crisp", "chat", r"client\.crisp\.chat"),
    ("Razorpay", "payments", r"checkout\.razorpay\.com|razorpay"),
    ("PayU", "payments", r"payu\.in|payumoney"),
    ("Paytm", "payments", r"securegw\.paytm\.in|paytm\.in/"),
    ("Stripe", "payments", r"js\.stripe\.com"),
    ("CCAvenue", "payments", r"ccavenue"),
    ("Cloudflare", "hosting", r"cdnjs\.cloudflare\.com|/cdn-cgi/"),
]
TECH_RE = [(n, c, re.compile(p)) for n, c, p in TECH]
SECURITY_HEADERS = {
    "strict-transport-security": "HSTS",
    "content-security-policy": "Content-Security-Policy",
    "x-frame-options": "X-Frame-Options",
    "x-content-type-options": "X-Content-Type-Options",
    "referrer-policy": "Referrer-Policy",
}


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------

def fetch_live(url: str) -> Dict[str, Any]:
    """GET with every redirect hop checked by the URL guard. Live (not cached): timing and headers matter here."""
    hops, t0 = [], time.time()
    for _ in range(6):
        deep_search.public_url_guard(url)
        r = requests.get(url, headers=deep_search.HEADERS, timeout=TIMEOUT, allow_redirects=False, stream=True)
        try:
            if r.is_redirect and r.headers.get("Location"):
                hops.append({"status": r.status_code, "url": url})
                url = urljoin(url, r.headers["Location"])
                continue
            first_byte = time.time() - t0
            body = b""
            for chunk in r.iter_content(65536):
                body += chunk
                if len(body) > MAX_BYTES:
                    break
            return {"url": url, "status": r.status_code, "headers": {k.lower(): v for k, v in r.headers.items()},
                    "html": body[:MAX_BYTES].decode(r.encoding or "utf-8", errors="replace"), "bytes": len(body),
                    "truncated": len(body) > MAX_BYTES, "ttfb": round(first_byte, 2), "seconds": round(time.time() - t0, 2),
                    "redirects": hops}
        finally:
            r.close()
    raise requests.TooManyRedirects("more than 5 redirects")


def ssl_info(host: str) -> Dict[str, Any]:
    """Certificate expiry + issuer. The host was already checked by the URL guard (public address)."""
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, 443), timeout=8) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as s:
                cert = s.getpeercert()
        expires = datetime.datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z")
        issuer = dict(x[0] for x in cert.get("issuer", ()))
        return {"valid": True, "expires": expires.strftime("%Y-%m-%d"),
                "days_left": (expires - datetime.datetime.utcnow()).days,
                "issuer": issuer.get("organizationName") or issuer.get("commonName") or ""}
    except ssl.SSLCertVerificationError as e:
        return {"valid": False, "error": f"certificate not trusted ({getattr(e, 'verify_message', '') or 'verification failed'})"}
    except (OSError, ssl.SSLError, ValueError, KeyError) as e:
        return {"valid": False, "error": f"no HTTPS certificate could be read ({e.__class__.__name__})"}


# ---------------------------------------------------------------------------
# Analysis (pure, given the fetched page)
# ---------------------------------------------------------------------------

def detect_tech(html_lower: str, headers: Dict[str, str]) -> Dict[str, List[str]]:
    found: Dict[str, List[str]] = {}
    for name, cat, rx in TECH_RE:
        if rx.search(html_lower):
            found.setdefault(cat, []).append(name)
    powered = headers.get("x-powered-by", "")
    if powered:
        found.setdefault("server", []).append(f"X-Powered-By: {powered[:40]}")
    if headers.get("server"):
        found.setdefault("server", []).append(headers["server"][:40])
    if "shop" in found and "WooCommerce" in found["shop"] and "WordPress" not in found.get("cms", []):
        found.setdefault("cms", []).append("WordPress")
    for tag in adlibrary_sources.detect_ad_tags(html_lower):
        found.setdefault("ads", []).append(tag)
    jq = re.search(r"jquery[-.]?(\d\.\d+)", html_lower)
    if jq and "jQuery" in found.get("framework", []):
        found["framework"] = [f"jQuery {jq.group(1)}" if x == "jQuery" else x for x in found["framework"]]
    return found


def seo_report(soup: BeautifulSoup, html_lower: str) -> Dict[str, Any]:
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    desc = soup.find("meta", attrs={"name": re.compile("^description$", re.I)})
    desc = (desc.get("content") or "").strip() if desc else ""
    robots = soup.find("meta", attrs={"name": re.compile("^robots$", re.I)})
    canonical = soup.find("link", rel=lambda v: v and "canonical" in (v if isinstance(v, list) else [v]))
    imgs = soup.find_all("img")
    no_alt = sum(1 for i in imgs if not (i.get("alt") or "").strip())
    ld_types = []
    for s in soup.find_all("script", type="application/ld+json"):
        ld_types += re.findall(r'"@type"\s*:\s*"([A-Za-z]+)"', s.string or "")
    html_tag = soup.find("html")
    return {"title": title[:200], "title_length": len(title), "description": desc[:300], "description_length": len(desc),
            "h1": [h.get_text(" ", strip=True)[:120] for h in soup.find_all("h1")][:5],
            "canonical": (canonical.get("href") or "") if canonical else "",
            "noindex": bool(robots and "noindex" in (robots.get("content") or "").lower()),
            "open_graph": bool(soup.find("meta", property="og:title")), "og_image": bool(soup.find("meta", property="og:image")),
            "lang": (html_tag.get("lang") or "") if html_tag else "", "images": len(imgs), "images_without_alt": no_alt,
            "structured_data": list(dict.fromkeys(ld_types))[:8], "favicon": "rel=\"icon\"" in html_lower or "shortcut icon" in html_lower}


def score_site(r: Dict[str, Any]) -> Tuple[int, List[str], List[Dict[str, str]]]:
    """-> (0-100, problems, opportunities [{pitch, why}])."""
    problems, opps = [], []
    pts = 100
    sec, seo, perf, tech = r["security"], r["seo"], r["overview"], r["technology"]

    def hit(points: int, problem: str, pitch: str = "", why: str = ""):
        nonlocal pts
        pts -= points
        problems.append(problem)
        if pitch:
            opps.append({"pitch": pitch, "why": why or problem})

    if not sec["https"]:
        hit(20, "No HTTPS - browsers mark the site 'Not secure'", "SSL / security setup", "site is not on HTTPS")
    elif not sec["redirects_http"]:
        hit(5, "http:// does not redirect to https://", "SSL / security setup")
    if sec.get("ssl", {}).get("valid") is False and sec["https"]:
        hit(15, f"SSL problem: {sec['ssl'].get('error', '')}", "SSL / security setup")
    elif sec.get("ssl", {}).get("days_left", 999) < 30:
        hit(5, f"SSL certificate expires in {sec['ssl']['days_left']} days", "SSL / maintenance plan")
    if sec["mixed_content"]:
        hit(5, f"{sec['mixed_content']} insecure (http://) resources on an https page", "Website maintenance")
    if not r["mobile"]["viewport"]:
        hit(20, "Not mobile-friendly (no viewport tag)", "Responsive redesign", "most visitors use phones")
    if perf["seconds"] > 3:
        hit(10, f"Slow: {perf['seconds']} s to load the page", "Speed optimisation")
    elif perf["seconds"] > 1.5:
        hit(4, f"Response time {perf['seconds']} s", "Speed optimisation")
    if perf["kb"] > 2048:
        hit(5, f"Heavy home page: {perf['kb']} KB of HTML", "Speed optimisation")
    if not seo["title"]:
        hit(8, "No page title", "SEO package")
    elif not 15 <= seo["title_length"] <= 70:
        hit(3, f"Title length {seo['title_length']} (best 15-70 characters)", "SEO package")
    if not seo["description"]:
        hit(6, "No meta description", "SEO package", "search results show random text")
    if not seo["h1"]:
        hit(4, "No H1 heading", "SEO package")
    if seo["noindex"]:
        hit(15, "Home page tells Google not to index it (noindex)", "SEO audit", "site hidden from Google")
    if not r["seo_files"]["sitemap"]:
        hit(3, "No sitemap found", "SEO package")
    if seo["images"] and seo["images_without_alt"] > seo["images"] / 2:
        hit(3, f"{seo['images_without_alt']} of {seo['images']} images have no alt text", "SEO package")
    if not seo["open_graph"]:
        hit(2, "No Open Graph tags (poor link previews on WhatsApp / social)", "Social media setup")
    if not tech.get("analytics"):
        hit(5, "No analytics - visitors are not measured", "Analytics & tracking setup")
    if "Universal Analytics (retired)" in tech.get("analytics", []) and "Google Analytics 4" not in tech.get("analytics", []):
        hit(4, "Only old Universal Analytics (stopped working in 2023)", "Analytics & tracking setup")
    if not tech.get("ads"):
        opps.append({"pitch": "Digital marketing / ads", "why": "no ad pixels (Meta / Google Ads) found"})
    if tech.get("builder"):
        hit(5, f"Built with {', '.join(tech['builder'])} (site builder)", "Custom website", "site-builder limits design and SEO")
    if not r["contacts"]["emails"] and not r["contacts"]["phones"]:
        hit(5, "No e-mail or phone visible on the home page", "Website content update")
    if not r["contacts"]["whatsapp"] and not tech.get("chat"):
        opps.append({"pitch": "WhatsApp / chat widget", "why": "no WhatsApp link or chat on the site"})
    hosted_checkout = {"Shopify", "BigCommerce"} & set(tech.get("shop", []))          # payments built in
    if not tech.get("payments") and tech.get("shop") and not hosted_checkout:
        opps.append({"pitch": "Payment gateway integration", "why": "online shop without an Indian payment gateway found"})
    for s in r["signals"]:
        if s.startswith(("old WordPress", "old jQuery", "copyright year", "uses Flash")):
            hit(5, s[:1].upper() + s[1:], "Website redesign / upgrade")
    seen, unique = set(), []
    for o in opps:
        if o["pitch"] not in seen:
            seen.add(o["pitch"])
            unique.append(o)
    return max(0, min(100, pts)), problems, unique


def analyze_page(page: Dict[str, Any], start_url: str, ssl_data: Optional[Dict[str, Any]], seo_files: Dict[str, Any]) -> Dict[str, Any]:
    html, headers = page["html"], page["headers"]
    lower = html.lower()
    soup = BeautifulSoup(html, "html.parser")
    final = page["url"]
    https = final.startswith("https://")
    c = web_crawler.page_contacts(html)
    links = [a.get("href", "") for a in soup.find_all("a", href=True)]
    mixed = len(re.findall(r"""(?:src|href)=["']http://(?!localhost)[^"']+\.(?:js|css|png|jpe?g|gif|webp|svg)""", lower)) if https else 0
    report = {
        "input": start_url, "domain": se.domain_of(final), "website": deep_search.site_root(final), "company": c["name"] or se.clean_title(c["title"]),
        "overview": {"final_url": final, "status": page["status"], "redirects": page["redirects"], "seconds": page["seconds"],
                     "ttfb": page["ttfb"], "kb": round(page["bytes"] / 1024), "truncated": page["truncated"],
                     "server": headers.get("server", "")[:60], "title": c["title"]},
        "technology": detect_tech(lower, headers),
        "seo": seo_report(soup, lower),
        "seo_files": seo_files,
        # http -> https: either this visit started on http:// and ended on https://, or a separate http:// request redirected
        "security": {"https": https, "redirects_http": https and (start_url.startswith("http://") or bool(seo_files.get("http_redirects"))),
                     "ssl": ssl_data or {}, "mixed_content": mixed,
                     "headers": {label: bool(headers.get(h)) for h, label in SECURITY_HEADERS.items()}},
        "mobile": {"viewport": bool(re.search(r"<meta[^>]+name=[\"']viewport[\"']", lower))},
        "contacts": {"emails": c["emails"][:5], "phones": c["phones"][:5], "socials": c["socials"],
                     "whatsapp": any("wa.me/" in l or "api.whatsapp.com" in l for l in links),
                     "contact_page": any(re.search(r"contact", l, re.I) for l in links)},
        "signals": website_signals.analyze_html(html, final),
    }
    report["score"], report["problems"], report["opportunities"] = score_site(report)
    report["grade"] = "Good" if report["score"] >= 80 else "Needs work" if report["score"] >= 55 else "Poor"
    return report


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def _http_redirects(host: str) -> bool:
    """Does http://host send visitors to https? (one small request, guarded, redirect not followed)."""
    try:
        deep_search.public_url_guard(f"http://{host}/")
        r = requests.get(f"http://{host}/", headers=deep_search.HEADERS, timeout=8, allow_redirects=False, stream=True)
        r.close()
        return r.is_redirect and r.headers.get("Location", "").startswith("https://")
    except (requests.RequestException, hcm.BlockedUrl):
        return False


def _sitemap_exists(root: str) -> bool:
    if robots_policy.sitemaps(root):
        return True
    try:
        status, text, _, _ = hcm.fetch_page(root.rstrip("/") + "/sitemap.xml", deep_search.HEADERS, deep_search.public_url_guard,
                                            timeout=10, max_bytes=200_000)
        return status == 200 and ("<urlset" in text[:2000].lower() or "<sitemapindex" in text[:2000].lower())
    except Exception:  # noqa: BLE001
        return False


def analyze_one(url: str) -> Dict[str, Any]:
    base = {"input": url, "domain": se.domain_of(url), "website": deep_search.site_root(url)}
    try:
        deep_search.public_url_guard(url)
    except hcm.BlockedUrl as e:
        return {**base, "status": "error", "error": f"Blocked: {e}"}
    if not robots_policy.allowed(url):
        return {**base, "status": "error", "error": "The site's robots.txt does not allow automated reading of this page"}
    try:
        page = fetch_live(url)
    except hcm.BlockedUrl as e:
        return {**base, "status": "error", "error": f"Blocked redirect: {e}"}
    except requests.Timeout:
        return {**base, "status": "error", "error": f"The site did not answer within {TIMEOUT} s"}
    except requests.RequestException as e:
        return {**base, "status": "error", "error": f"Could not open the site ({e.__class__.__name__})"}
    if page["status"] >= 400 or not page["html"].strip():
        return {**base, "status": "error", "error": f"The home page answered HTTP {page['status']}"}
    host = urlparse(page["url"]).hostname or ""
    with ThreadPoolExecutor(max_workers=3) as pool:
        f_ssl = pool.submit(ssl_info, host) if page["url"].startswith("https://") else None
        f_map = pool.submit(_sitemap_exists, deep_search.site_root(page["url"]))
        f_http = pool.submit(_http_redirects, host) if page["url"].startswith("https://") else None
        ssl_data = f_ssl.result() if f_ssl else None
        seo_files = {"robots_txt": robots_policy.parser_for(robots_policy._key(page["url"])) is not None,
                     "sitemap": f_map.result(), "http_redirects": f_http.result() if f_http else False}
    return {"status": "ok", **analyze_page(page, url, ssl_data, seo_files)}


def analyze(urls: Any) -> Dict[str, Any]:
    clean = web_crawler._urls(urls, "website", MAX_SITES)
    unique, seen = [], set()
    for u in clean:
        if se.domain_of(u) not in seen:
            seen.add(se.domain_of(u))
            unique.append(u)
    with ThreadPoolExecutor(max_workers=len(unique)) as pool:
        results = list(pool.map(analyze_one, unique))
    return {"results": results, "duplicates_skipped": len(clean) - len(unique)}


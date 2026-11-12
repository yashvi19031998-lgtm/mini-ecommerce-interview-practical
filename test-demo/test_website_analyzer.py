"""Tests for Utilities -> Website Analyzer (website_analyzer.py), no network.

python -m unittest test_website_analyzer -v
"""
import csv
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

import html_cache_manager as hcm
import robots_policy
import website_analyzer as wa
import website_signals

GOOD = """<html lang="en"><head><title>Acme Foods - Bakery in Ahmedabad</title>
<meta name="viewport" content="width=device-width"><meta name="description" content="Fresh cakes and breads baked daily in Ahmedabad since 1990.">
<meta property="og:title" content="Acme"><meta property="og:image" content="/og.png"><link rel="canonical" href="https://acme.in/">
<script src="https://cdn.shopify.com/s/files/theme.js"></script><script src="https://www.googletagmanager.com/gtag/js?id=G-ABC1234"></script>
<script>fbq('init', '123');</script><script type="application/ld+json">{"@type": "Organization", "name": "Acme Foods"}</script>
</head><body><h1>Acme Foods</h1><img src="a.png" alt="cake"><a href="/contact">Contact</a><a href="https://wa.me/919825012345">WhatsApp</a>
<p>sales@acmefoods.in</p><a href="tel:+919825012345">98250 12345</a><a href="https://www.instagram.com/acme">IG</a></body></html>"""
BAD = """<html><head><title>Home</title><script src="/js/jquery-1.8.2.min.js"></script>
<script>ga('create', 'UA-12345-1');</script></head><body><img src="a.jpg"><img src="b.jpg">
<a href="https://someblog.blogspot.com/">our friend's blog</a><p>&copy; 2015 Old Co</p></body></html>"""
WIX = '<html><head><title>Studio Name Here</title><meta name="viewport" content="x"></head><body><img src="https://static.wixstatic.com/a.png"></body></html>'


def page(html, url="https://acme.in/", seconds=0.4, headers=None, redirects=()):
    return {"url": url, "status": 200, "headers": headers or {}, "html": html, "bytes": len(html), "truncated": False,
            "ttfb": 0.2, "seconds": seconds, "redirects": list(redirects)}


SSL_OK = {"valid": True, "expires": "2027-01-01", "days_left": 200, "issuer": "Let's Encrypt"}
FILES_OK = {"robots_txt": True, "sitemap": True, "http_redirects": True}
SEC_HEADERS = {"strict-transport-security": "max-age=1", "x-content-type-options": "nosniff", "server": "nginx"}


class Analysis(unittest.TestCase):
    def test_good_site(self):
        r = wa.analyze_page(page(GOOD, headers=SEC_HEADERS), "https://acme.in", SSL_OK, FILES_OK)
        t = r["technology"]
        self.assertEqual((t["shop"], t["analytics"], t["ads"]), (["Shopify"], ["Google Analytics 4"], ["Meta Pixel"]))  # gtag.js is GA4, not a GTM container
        self.assertIn("WhatsApp chat", t["chat"])
        self.assertEqual((r["company"], r["seo"]["h1"], r["seo"]["structured_data"]), ("Acme Foods", ["Acme Foods"], ["Organization"]))
        self.assertTrue(r["security"]["redirects_http"] and r["security"]["headers"]["HSTS"])
        self.assertTrue(r["contacts"]["whatsapp"] and r["contacts"]["contact_page"])
        self.assertIn("sales@acmefoods.in", r["contacts"]["emails"])
        self.assertGreaterEqual(r["score"], 90)
        self.assertEqual(r["grade"], "Good")
        self.assertNotIn("Payment gateway integration", [o["pitch"] for o in r["opportunities"]])   # Shopify has payments

    def test_bad_site(self):
        r = wa.analyze_page(page(BAD, url="http://old.in/", seconds=4.2), "http://old.in", None,
                            {"robots_txt": False, "sitemap": False, "http_redirects": False})
        probs = " | ".join(r["problems"])
        for p in ("No HTTPS", "Not mobile-friendly", "Slow: 4.2 s", "No meta description", "No H1", "No sitemap",
                  "2 of 2 images have no alt", "Only old Universal Analytics", "Old jQuery 1.8", "Copyright year 2015"):
            self.assertIn(p, probs)
        self.assertNotIn("Blogger", probs)                                  # a link to a blogspot site is not a builder
        self.assertEqual(r["grade"], "Poor")
        pitches = [o["pitch"] for o in r["opportunities"]]
        for p in ("SSL / security setup", "Responsive redesign", "SEO package", "Speed optimisation", "Website redesign / upgrade"):
            self.assertIn(p, pitches)
        self.assertEqual(len(pitches), len(set(pitches)))                   # each pitch once

    def test_builder_mixed_content_noindex_ssl(self):
        html = WIX.replace("<body>", '<body><meta name="robots" content="noindex"><script src="http://cdn.x.in/a.js"></script>')
        r = wa.analyze_page(page(html), "https://studio.in", {"valid": True, "days_left": 10, "expires": "x", "issuer": "y"}, FILES_OK)
        probs = " | ".join(r["problems"])
        for p in ("Built with Wix", "noindex", "1 insecure", "expires in 10 days"):
            self.assertIn(p, probs)
        bad_ssl = wa.analyze_page(page(GOOD), "https://acme.in", {"valid": False, "error": "certificate not trusted"}, FILES_OK)
        self.assertIn("SSL problem", " ".join(bad_ssl["problems"]))

    def test_signals_builder_fix(self):
        self.assertNotIn("built with Blogger (site builder)", website_signals.analyze_html(BAD, "https://x.in"))
        self.assertIn("built with Blogger (site builder)",
                      website_signals.analyze_html('<script src="https://www.blogger.com/static/v1/w.js"></script>', "https://x.in"))


class Runner(unittest.TestCase):
    def test_blocked_robots_and_errors(self):
        self.assertIn("Blocked", wa.analyze_one("http://127.0.0.1/")["error"])
        with mock.patch.object(robots_policy, "allowed", return_value=False):
            self.assertIn("robots.txt", wa.analyze_one("https://acme.in")["error"])
        with mock.patch.object(robots_policy, "allowed", return_value=True), \
                mock.patch.object(wa.deep_search, "public_url_guard", return_value=None), \
                mock.patch.object(wa, "fetch_live", side_effect=wa.requests.Timeout()):
            self.assertIn("did not answer", wa.analyze_one("https://acme.in")["error"])
        with mock.patch.object(robots_policy, "allowed", return_value=True), \
                mock.patch.object(wa.deep_search, "public_url_guard", return_value=None), \
                mock.patch.object(wa, "fetch_live", return_value={**page(""), "status": 503}):
            self.assertIn("HTTP 503", wa.analyze_one("https://acme.in")["error"])

    def test_full_run_mocked(self):
        with mock.patch.object(robots_policy, "allowed", return_value=True), \
                mock.patch.object(robots_policy, "parser_for", return_value=object()), \
                mock.patch.object(wa.deep_search, "public_url_guard", return_value=None), \
                mock.patch.object(wa, "fetch_live", return_value=page(GOOD, headers=SEC_HEADERS)), \
                mock.patch.object(wa, "ssl_info", return_value=SSL_OK) as s, \
                mock.patch.object(wa, "_sitemap_exists", return_value=True), \
                mock.patch.object(wa, "_http_redirects", return_value=True):
            res = wa.analyze(["acme.in", "https://www.acme.in/", "beta.in"])
        self.assertEqual(res["duplicates_skipped"], 1)
        self.assertEqual([r["status"] for r in res["results"]], ["ok", "ok"])
        self.assertTrue(res["results"][0]["security"]["redirects_http"])
        self.assertEqual(s.call_args.args[0], "acme.in")
        with self.assertRaises(ValueError):
            wa.analyze([f"s{i}.in" for i in range(6)])

    def test_fetch_live_checks_every_redirect(self):
        hop = SimpleNamespace(is_redirect=True, headers={"Location": "http://10.0.0.1/admin"}, status_code=302, close=lambda: None)
        with mock.patch.object(wa.requests, "get", return_value=hop):
            with self.assertRaises(hcm.BlockedUrl):
                wa.fetch_live("https://example.com/")

    def test_ssl_info_error(self):
        with mock.patch.object(wa.socket, "create_connection", side_effect=OSError("refused")):
            self.assertFalse(wa.ssl_info("acme.in")["valid"])


class Api(unittest.TestCase):
    def setUp(self):
        import app as app_module
        self.app = app_module
        self.client = app_module.app.test_client()
        ok = SimpleNamespace(status_code=200, json=lambda: {"email": "owner@example.com"})
        self.tmp = tempfile.TemporaryDirectory()
        self.p = [mock.patch("api_auth.requests.get", return_value=ok), mock.patch("api_auth.ALLOWED_EMAILS", set()),
                  mock.patch.object(hcm, "CACHE_DIR", self.tmp.name),
                  mock.patch.object(self.app, "MASTER_PATH", os.path.join(self.tmp.name, "m.csv"))]
        for x in self.p:
            x.start()
        self.h = {"Authorization": "Bearer t"}

    def tearDown(self):
        for x in self.p:
            x.stop()
        self.tmp.cleanup()

    def test_endpoints_and_save_signals(self):
        self.assertEqual(self.client.post("/api/utilities/website-analyzer", json={}).status_code, 401)
        self.assertEqual(self.client.post("/api/utilities/website-analyzer", headers=self.h, json={}).status_code, 400)
        row = {"company": "Acme", "domain": "acme.in", "website": "https://acme.in/", "emails": ["sales@acme.in"], "phones": [],
               "socials": {}, "lead_source": "Utilities (Website Analyzer)", "website_signals": "Score 40/100 (Poor): No HTTPS"}
        sv = self.client.post("/api/bulk-contacts/save", headers=self.h, json={"kind": "websites", "rows": [row]}).get_json()
        self.assertEqual(sv["added"], 1)
        with open(os.path.join(self.tmp.name, "m.csv"), encoding="utf-8-sig") as fh:
            saved = list(csv.DictReader(fh))[0]
        self.assertEqual((saved["source"], saved["website_signals"]), ("Utilities (Website Analyzer)", "Score 40/100 (Poor): No HTTPS"))


if __name__ == "__main__":
    unittest.main()

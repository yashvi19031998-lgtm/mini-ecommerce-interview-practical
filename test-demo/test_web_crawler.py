"""Tests for Web Crawler (web_crawler.py) and robots_policy.py, no network (a fake web + fake robots.txt).

python -m unittest test_web_crawler -v
"""
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

import html_cache_manager as hcm
import robots_policy
import web_crawler as wc

HOME = """<html><head><title>Acme Foods | Home</title></head><body>
<a href="/about">About</a> <a href="/contact#form">Contact</a> <a href="https://www.acmefoods.in/about/">About again</a>
<a href="/brochure.pdf">PDF</a> <a href="mailto:x@y.in">mail</a> <a href="/private/secret">Secret</a>
<a href="https://www.instagram.com/acmefoods">IG</a></body></html>"""
CONTACT = """<html><head><title>Contact</title></head><body><p>Write to sales@acmefoods.in or call
<a href="tel:+919825012345">98250 12345</a></p><a href="/careers">Careers</a></body></html>"""
CAREERS = "<html><head><title>Careers</title></head><body><p>We are hiring. Careers at Acme: join our sales team.</p></body></html>"
ABOUT = "<html><head><title>About</title></head><body><p>Since 1990. Franchise enquiries welcome.</p></body></html>"
LIST = """<html><body><h1>Members</h1>
<a href="https://www.alpha-foods.in/">Alpha Foods Pvt Ltd</a> <a href="https://alpha-foods.in/products">Visit website</a>
<a href="http://beta-tools.com">Beta Tools</a> <a href="https://www.facebook.com/x">Facebook</a>
<a href="https://fonts.googleapis.com/css">font</a> <a href="https://gem.gov.in/">GeM</a> <a href="https://www.gujarat.gov.in/">Gujarat Govt</a>
<a href="/members?page=2">Next</a> <a href="/about">About us</a></body></html>"""
LIST2 = """<html><body><a href="https://gamma.co.in">Gamma Co</a></body></html>"""
SITEMAP_INDEX = """<?xml version="1.0"?><sitemapindex><sitemap><loc>https://acmefoods.in/sitemap_products.xml</loc></sitemap>
<sitemap><loc>https://acmefoods.in/sitemap_pages.xml</loc></sitemap><sitemap><loc>https://evil.example/sm.xml</loc></sitemap></sitemapindex>"""
SM_PRODUCTS = """<urlset><url><loc>https://acmefoods.in/products/cake?a=1&amp;b=2</loc><lastmod>2026-11-01</lastmod>
<priority>0.8</priority></url><url><loc>https://acmefoods.in/products/bread</loc></url></urlset>"""
SM_PAGES = """<urlset><url><loc>https://acmefoods.in/pages/about</loc><lastmod>2025-01-05</lastmod></url>
<url><loc>https://acmefoods.in/</loc></url></urlset>"""
BOMB = """<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY lol "lol"><!ENTITY lol2 "&lol;&lol;&lol;">]>
<urlset><url><loc>https://acmefoods.in/&lol2;</loc></url></urlset>"""

SITE = {
    "https://acmefoods.in": HOME, "https://acmefoods.in/about": ABOUT, "https://acmefoods.in/contact": CONTACT,
    "https://acmefoods.in/careers": CAREERS, "https://acmefoods.in/private/secret": "<html>secret</html>",
    "https://www.club.in/members": LIST, "https://www.club.in/members?page=2": LIST2,
    "https://acmefoods.in/sitemap_index.xml": SITEMAP_INDEX, "https://acmefoods.in/sitemap_products.xml": SM_PRODUCTS,
    "https://acmefoods.in/sitemap_pages.xml": SM_PAGES,
}


class FakeWeb:
    def __init__(self, pages):
        self.pages, self.calls = pages, []

    def __call__(self, url, headers, guard, timeout=20, **kw):
        self.calls.append(url)
        if url in self.pages:
            return 200, self.pages[url], url, False
        return 404, "", url, False


class Base(unittest.TestCase):
    def setUp(self):
        self.web = FakeWeb(SITE)
        self.sleeps = []
        self.p = [mock.patch.object(wc.hcm, "fetch_page", self.web),
                  mock.patch.object(robots_policy, "allowed", side_effect=lambda u: "/private/" not in u),
                  mock.patch.object(robots_policy, "crawl_delay", return_value=1.0),
                  mock.patch.object(robots_policy, "sitemaps", return_value=[])]
        for x in self.p:
            x.start()

    def tearDown(self):
        for x in self.p:
            x.stop()

    def session(self, budget=90.0, clock=None):
        return wc.Session(sleep=self.sleeps.append, clock=clock or (lambda: 0.0), budget=budget)


class Validation(unittest.TestCase):
    def test_rules(self):
        for fn, data, msg in ((wc.site_crawl, {"urls": []}, "at least one"), (wc.site_crawl, {"urls": ["a.in"] * 1 + [f"s{i}.in" for i in range(6)]}, "at most 5"),
                              (wc.site_crawl, {"urls": ["not a site"]}, "not a web address"),
                              (wc.site_crawl, {"urls": ["a.in"], "max_pages": 999}, "page limit"),
                              (wc.site_crawl, {"urls": ["a.in"], "depth": 9}, "depth"),
                              (wc.find_keywords, {"urls": ["a.in"], "keywords": []}, "keyword"),
                              (wc.find_keywords, {"urls": ["a.in"], "keywords": ["x"]}, "2-60"),
                              (wc.sitemap, {"urls": ["a.in", "b.in"]}, "at most 1"),
                              (wc.harvest_links, {"urls": ["a.in"], "follow_pages": 9}, "pages to follow")):
            with self.assertRaises(ValueError) as cm:
                fn(data, session=wc.Session(sleep=lambda s: None))
            self.assertIn(msg, str(cm.exception).lower(), data)

    def test_page_key(self):
        self.assertEqual(wc.page_key("https://www.acmefoods.in/about/"), wc.page_key("http://acmefoods.in/about"))
        self.assertNotEqual(wc.page_key("https://acmefoods.in/a?x=1"), wc.page_key("https://acmefoods.in/a"))


class SiteCrawl(Base):
    def test_crawl(self):
        res = wc.site_crawl({"urls": ["acmefoods.in"], "max_pages": 10, "depth": 2}, session=self.session())
        urls = [r["url"] for r in res["results"]]
        self.assertEqual(urls[0], "https://acmefoods.in")
        self.assertEqual(len(urls), len({wc.page_key(u) for u in urls}))                  # /about and www/about/ once
        self.assertNotIn("https://acmefoods.in/brochure.pdf", self.web.calls)               # files never fetched
        self.assertNotIn("https://acmefoods.in/private/secret", self.web.calls)             # robots.txt obeyed
        self.assertEqual(res["blocked"], 1)
        self.assertIn("https://acmefoods.in/careers", urls)                                 # depth 2 reached
        self.assertFalse(any("instagram" in u for u in urls))                               # other sites not crawled
        site = res["sites"][0]
        self.assertEqual((site["site"], site["status"]), ("acmefoods.in", "found"))
        self.assertIn("sales@acmefoods.in", site["emails"])
        self.assertTrue(any("98250" in p for p in site["phones"]))
        self.assertIn("instagram", site["socials"])
        self.assertEqual(site["company"], "Acme Foods")                                     # cleaned title when no JSON-LD / og name
        import bulk_contacts
        lead = bulk_contacts.website_rows_to_leads([{**site, "lead_source": "Web Crawler (Site Crawler)"}])[0]
        self.assertEqual(lead["source"], "Web Crawler (Site Crawler)")
        forged = bulk_contacts.website_rows_to_leads([{**site, "lead_source": "Anything=1"}])[0]
        self.assertEqual(forged["source"], "Bulk Contacts (Website Contacts)")              # only known labels
        self.assertTrue(self.sleeps)                                                        # pause between pages

    def test_depth_and_page_limits(self):
        res = wc.site_crawl({"urls": ["acmefoods.in"], "max_pages": 10, "depth": 1}, session=self.session())
        self.assertNotIn("https://acmefoods.in/careers", [r["url"] for r in res["results"]])
        times = iter(range(0, 1000, 50))
        res = wc.site_crawl({"urls": ["acmefoods.in"], "max_pages": 10, "depth": 3}, session=self.session(clock=lambda: next(times)))
        self.assertLess(len(res["results"]), 4)
        self.assertTrue(any("Stopped after" in n for n in res["notes"]))


class Links(Base):
    def test_harvest(self):
        res = wc.harvest_links({"urls": ["https://www.club.in/members"], "follow_pages": 2}, session=self.session())
        got = {r["domain"]: r for r in res["results"]}
        self.assertEqual(sorted(got), ["alpha-foods.in", "beta-tools.com", "gamma.co.in", "gujarat.gov.in"])
        self.assertEqual(got["alpha-foods.in"]["company"], "Alpha Foods Pvt Ltd")             # "Visit website" ignored
        self.assertEqual(got["alpha-foods.in"]["links"], 2)
        self.assertTrue(got["gujarat.gov.in"]["government"])                               # kept, but flagged; gem.gov.in is a known portal and skipped
        self.assertEqual(res["pages"], 2)                                                   # followed "Next"
        res1 = wc.harvest_links({"urls": ["https://www.club.in/members"], "follow_pages": 1}, session=self.session())
        self.assertNotIn("gamma.co.in", {r["domain"] for r in res1["results"]})


class Keywords(Base):
    def test_find(self):
        res = wc.find_keywords({"urls": ["acmefoods.in"], "keywords": ["Careers", "franchise", "tender"], "max_pages": 10, "depth": 2},
                               session=self.session())
        self.assertEqual(res["keywords"], {"careers": 2, "franchise": 1, "tender": 0})
        top = res["results"][0]
        self.assertEqual((top["url"], top["keyword"], top["in_url"]), ("https://acmefoods.in/careers", "careers", True))
        self.assertTrue(any("Franchise enquiries" in s for r in res["results"] for s in r["snippets"]))

    def test_snippets(self):
        n, sn = wc.snippets("a careers page; careerstation is not a match; Careers again", "careers", width=5)
        self.assertEqual(n, 2)
        self.assertTrue(sn[0].startswith("a careers"))


class Sitemaps(Base):
    def test_index_children_and_sections(self):
        res = wc.sitemap({"urls": ["https://acmefoods.in"]}, session=self.session())
        self.assertEqual(res["sitemaps"], ["https://acmefoods.in/sitemap_index.xml", "https://acmefoods.in/sitemap_products.xml",
                                           "https://acmefoods.in/sitemap_pages.xml"])
        self.assertNotIn("https://evil.example/sm.xml", self.web.calls)                     # other sites' sitemaps ignored
        self.assertIn("https://acmefoods.in/products/cake?a=1&b=2", [r["url"] for r in res["results"]])
        self.assertEqual({s["section"]: s["pages"] for s in res["sections"]}, {"products": 2, "pages": 1, "(home)": 1})
        self.assertEqual((res["newest"], res["oldest"]), ("2026-11-01", "2025-01-05"))
        self.assertEqual(res["failed"], 0)                                                  # missing /sitemap.xml is not an error

    def test_none_and_entities(self):
        self.assertEqual(wc.parse_sitemap("<html>not xml</html>"), ("", []))
        kind, rows = wc.parse_sitemap(BOMB)                                                 # entities are never expanded
        self.assertEqual((kind, rows[0]["loc"]), ("urlset", "https://acmefoods.in/&lol2;"))
        res = wc.sitemap({"urls": ["nothing.in"]}, session=self.session())
        self.assertIn("No sitemap found", res["notes"][0])


class Robots(unittest.TestCase):
    def setUp(self):
        robots_policy.parser_for.cache_clear()
        self.addCleanup(robots_policy.parser_for.cache_clear)

    def test_rules(self):
        txt = "User-agent: *\nDisallow: /private/\nCrawl-delay: 4\nSitemap: https://a.in/sm.xml\n"
        with mock.patch.object(robots_policy.hcm, "_guarded_get", return_value=(200, txt, "")):
            self.assertTrue(robots_policy.allowed("https://a.in/about"))
            self.assertFalse(robots_policy.allowed("https://a.in/private/x"))
            self.assertEqual(robots_policy.crawl_delay("https://a.in/"), 4.0)
            self.assertEqual(robots_policy.sitemaps("https://a.in/"), ["https://a.in/sm.xml"])

    def test_missing_error_and_blocked(self):
        with mock.patch.object(robots_policy.hcm, "_guarded_get", return_value=(404, "", "")):
            self.assertTrue(robots_policy.allowed("https://b.in/x"))
        with mock.patch.object(robots_policy.hcm, "_guarded_get", return_value=(500, "", "")):
            self.assertFalse(robots_policy.allowed("https://c.in/x"))
        self.assertFalse(robots_policy.allowed("http://127.0.0.1/x"))                       # guard: private address


class Api(unittest.TestCase):
    def setUp(self):
        import app as app_module
        self.client = app_module.app.test_client()
        ok = SimpleNamespace(status_code=200, json=lambda: {"email": "owner@example.com"})
        self.tmp = tempfile.TemporaryDirectory()
        self.p = [mock.patch("api_auth.requests.get", return_value=ok), mock.patch("api_auth.ALLOWED_EMAILS", set()),
                  mock.patch.object(hcm, "CACHE_DIR", self.tmp.name)]
        for x in self.p:
            x.start()
        self.h = {"Authorization": "Bearer t"}

    def tearDown(self):
        for x in self.p:
            x.stop()
        self.tmp.cleanup()

    def test_endpoints(self):
        self.assertEqual(self.client.get("/api/web-crawler").status_code, 401)
        for t in ("site", "links", "keywords", "sitemap"):
            self.assertEqual(self.client.post(f"/api/web-crawler/{t}", json={}).status_code, 401, t)
            self.assertEqual(self.client.post(f"/api/web-crawler/{t}", headers=self.h, json={}).status_code, 400, t)
        self.assertEqual(self.client.post("/api/web-crawler/nope", headers=self.h, json={}).status_code, 404)
        with mock.patch.object(wc.hcm, "fetch_page", FakeWeb(SITE)), \
                mock.patch.object(robots_policy, "allowed", return_value=True), \
                mock.patch.object(robots_policy, "crawl_delay", return_value=0.0), \
                mock.patch.object(robots_policy, "sitemaps", return_value=[]):
            r = self.client.post("/api/web-crawler/keywords", headers=self.h,
                                 json={"urls": ["acmefoods.in"], "keywords": ["careers"], "max_pages": 10, "depth": 2}).get_json()
        self.assertEqual(r["keywords"], {"careers": 2})
        self.assertNotIn("html", r["results"][0])                                         # page HTML never sent to the browser


if __name__ == "__main__":
    unittest.main()

"""Tests for Scraping / Mining -> Social Media (social_sources.py), no network.

python -m unittest test_social_sources -v
"""
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

import html_cache_manager as hcm
import search_engine as se
import social_sources as sm

BASE = {"keywords": ["bakery"], "state": "Gujarat", "city": "Ahmedabad", "sources": ["instagram"], "engine": "duckduckgo"}


def hit(title, url, snippet=""):
    return {"title": title, "url": url, "snippet": snippet}


class Validation(unittest.TestCase):
    def test_rules(self):
        for over, msg in (({"keywords": []}, "at least one business type"), ({"state": ""}, "select a state"),
                          ({"city": "Ahm3d"}, "letters only"), ({"sources": []}, "at least one source"),
                          ({"sources": ["tiktok"]}, "unknown source"), ({"sources": ["whatsapp_business"]}, "not available"),
                          ({"engine": "yahoo"}, "unknown search engine")):
            with self.assertRaises(ValueError) as cm:
                sm.validate_request({**BASE, **over})
            self.assertIn(msg, str(cm.exception).lower())
        with mock.patch.dict(os.environ, {"BRAVE_SEARCH_API_KEY": ""}), self.assertRaises(ValueError):
            sm.validate_request({**BASE, "engine": "brave"})

    def test_catalog(self):
        st = {s["id"]: s["status"] for s in sm.list_sources()}
        self.assertEqual(st["whatsapp_business"], "unavailable")
        self.assertEqual(sum(1 for v in st.values() if v == "available"), 5)


class UrlFilters(unittest.TestCase):
    def test_each_network(self):
        good = {"instagram": "https://www.instagram.com/sweetbakery.ahd/", "facebook": "https://m.facebook.com/profile.php?id=1000123",
                "linkedin": "https://in.linkedin.com/company/acme-infotech", "x": "https://twitter.com/acme_in",
                "youtube": "https://www.youtube.com/@AcmeChannel"}
        bad = {"instagram": ["https://instagram.com/p/abc/", "https://www.instagram.com/reel/x/", "https://www.instagram.com/explore/tags/cake/"],
               "facebook": ["https://www.facebook.com/groups/1", "https://www.facebook.com/events/2", "https://www.facebook.com/sharer/sharer.php"],
               "linkedin": ["https://www.linkedin.com/in/person", "https://www.linkedin.com/jobs/view/1"],
               "x": ["https://x.com/acme/status/1", "https://x.com/hashtag/cake", "https://x.com/i/flow"],
               "youtube": ["https://www.youtube.com/watch?v=1", "https://www.youtube.com/shorts/1", "https://www.youtube.com/playlist?list=1"]}
        for sid, url in good.items():
            self.assertIsNotNone(sm.profile_of(sid, url), url)
        for sid, urls in bad.items():
            for url in urls:
                self.assertIsNone(sm.profile_of(sid, url), url)
        self.assertEqual(sm.profile_of("x", "https://twitter.com/acme_in")[1], "https://x.com/acme_in")


class Fields(unittest.TestCase):
    def test_names_followers_website(self):
        self.assertEqual(sm.clean_name("Sweet Bakery (@sweetbakery.ahd) • Instagram photos and videos", "x"), "Sweet Bakery")
        self.assertEqual(sm.clean_name("Acme Infotech | LinkedIn", "acme"), "Acme Infotech")
        self.assertEqual(sm.clean_name("", "acme_in"), "acme_in")
        self.assertEqual(sm.followers_of("12.5K Followers, 300 Following"), "12.5K")
        self.assertEqual(sm.followers_of("1,234 followers"), "1,234")
        self.assertEqual((sm.followers_number("12.5K"), sm.followers_number("1,234"), sm.followers_number("2M")), (12500, 1234, 2_000_000))
        self.assertEqual(sm.website_in("Order at www.sweetbakery.in today"), "https://www.sweetbakery.in")
        self.assertEqual(sm.website_in("links: linktr.ee/sweet bit.ly/x https://instagram.com/x wa.me/91"), "")


class Search(unittest.TestCase):
    def run_with(self, hits, **over):
        with mock.patch.dict(se.ENGINE_FUNCS, {"duckduckgo": lambda *a: hits}), mock.patch.object(sm.time, "sleep"):
            return sm.search({**BASE, **over})

    def test_privacy_filter_and_counts(self):
        hits = [hit("Sweet Bakery (@sweetbakery.ahd) • Instagram photos and videos", "https://www.instagram.com/sweetbakery.ahd/", "12.5K Followers. Custom cakes"),
                hit("Riya Shah (@riya.s) • Instagram photos and videos", "https://www.instagram.com/riya.s/", "Traveller. Dreamer."),
                hit("Cake Studio", "https://www.instagram.com/cakestudio/", "Call 98250 11111"),
                hit("A post", "https://www.instagram.com/p/xyz/", "")]
        r = self.run_with(hits)
        self.assertEqual({x["handle"] for x in r["results"]}, {"sweetbakery.ahd", "cakestudio"})
        self.assertIn("personal-looking profile(s) skipped", " ".join(r["sources"]["instagram"]["errors"]))
        self.assertEqual(r["results"][0]["handle"], "cakestudio", "rows with a phone first")

    def test_dedupe_merges_and_followers_order(self):
        hits = [hit("Alpha Bakery", "https://www.instagram.com/alpha/", "1.2K followers bakery"),
                hit("Alpha Bakery", "https://instagram.com/alpha", "bakery www.alphabakery.in"),
                hit("Beta Bakery", "https://www.instagram.com/beta/", "45K followers bakery")]
        r = self.run_with(hits)
        self.assertEqual([x["handle"] for x in r["results"]], ["alpha", "beta"], "website first, then followers")
        alpha = r["results"][0]
        self.assertEqual((alpha["website"], alpha["followers"], alpha["kind"]), ("https://www.alphabakery.in", "1.2K", "website"))

    def test_off_target_and_audience(self):
        hits = [hit("Sweet Bakery cafe", "https://www.instagram.com/sweet/", "bakery and cafe"),
                hit("Wiki", "https://en.wikipedia.org/wiki/Bakery", "bakery"),
                hit("Bread Shop", "https://www.instagram.com/bread/", "bakery shop")]
        r = self.run_with(hits, audience=["Cafe / coffee"])
        self.assertEqual([x["handle"] for x in r["results"]], ["sweet"])
        r = self.run_with(hits, audience=["Automobile"])
        self.assertEqual(r["total"], 2)

    def test_rate_limit_error_isolation_and_hint(self):
        calls = []

        def limited(q, *a):
            calls.append(q)
            if len(calls) > 1:
                raise se.RateLimited("slow down")
            return [hit("Sweet Bakery", "https://www.instagram.com/sweet/", "bakery")]
        with mock.patch.dict(se.ENGINE_FUNCS, {"duckduckgo": limited}), mock.patch.object(sm.time, "sleep"):
            r = sm.search(BASE)
        self.assertEqual((r["total"], r["sources"]["instagram"]["status"]), (1, "ok"))

        def boom(sid, *a):
            if sid == "facebook":
                raise AttributeError("x")
            return []
        with mock.patch.object(sm, "search_network", side_effect=boom):
            r = sm.search({**BASE, "sources": ["instagram", "facebook"]})
        self.assertEqual(r["sources"]["facebook"]["status"], "error")
        self.assertEqual(r["sources"]["instagram"]["status"], "ok")
        self.assertIn("BRAVE_SEARCH_API_KEY", r["hint"])

    def test_never_requests_social_sites(self):
        def forbidden(*a, **k):
            raise AssertionError("social_sources must not make its own HTTP requests")
        hits = [hit("Sweet Bakery", "https://www.instagram.com/sweet/", "bakery www.sweetbakery.in")]
        with mock.patch.dict(se.ENGINE_FUNCS, {"duckduckgo": lambda *a: hits}), mock.patch.object(sm.time, "sleep"), \
                mock.patch("requests.Session.get", side_effect=forbidden), mock.patch("requests.get", side_effect=forbidden), \
                mock.patch.object(hcm, "_guarded_get", side_effect=forbidden):
            r = sm.search({**BASE, "sources": ["instagram", "facebook", "linkedin", "x", "youtube"]})
        self.assertEqual(r["total"], 1)

    def test_lead_mapping(self):
        r = sm.make_result("instagram", company="Sweet Bakery", handle="sweet", network="Instagram",
                           profile_url="https://www.instagram.com/sweet/", url="https://www.instagram.com/sweet/", followers="12.5K")
        lead = sm.result_to_raw_lead(r)
        self.assertEqual((lead["lead_type"], lead["source"], lead["source_url"]),
                         ("Social Media Business", "Social Media (Instagram)", "https://www.instagram.com/sweet/"))
        self.assertIn("12.5K followers", lead["description"])


class Api(unittest.TestCase):
    def setUp(self):
        import app as app_module
        self.app = app_module
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
        for m, u in (("get", "/api/social"), ("post", "/api/social/search"), ("post", "/api/social/save")):
            self.assertEqual(getattr(self.client, m)(u).status_code, 401, u)
        self.assertEqual(self.client.post("/api/social/search", headers=self.h, json={**BASE, "keywords": []}).status_code, 400)
        row = sm.make_result("instagram", company="Sweet Bakery", handle="sweet", network="Instagram",
                             profile_url="https://www.instagram.com/sweet/", url="https://www.instagram.com/sweet/")
        fake = {"query": {}, "results": [row], "total": 1, "engine": "duckduckgo", "hint": "",
                "sources": {"instagram": {"name": "x", "status": "ok", "count": 1, "seconds": 1, "errors": []}}}
        with mock.patch.object(sm, "search", return_value=fake) as live:
            self.client.post("/api/social/search", headers=self.h, json=BASE)
            r2 = self.client.post("/api/social/search", headers=self.h, json=BASE).get_json()
        self.assertEqual((live.call_count, r2["cache"]["hit"]), (1, True))
        with tempfile.TemporaryDirectory() as d, mock.patch.object(self.app, "MASTER_PATH", os.path.join(d, "m.csv")):
            a = self.client.post("/api/social/save", headers=self.h, json={"results": [row]}).get_json()
            b = self.client.post("/api/social/save", headers=self.h, json={"results": [row]}).get_json()
        self.assertEqual((a["added"], b["added"]), (1, 0))


if __name__ == "__main__":
    unittest.main()

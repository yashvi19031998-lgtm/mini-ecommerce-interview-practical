"""Tests for Scraping / Mining -> Ad Library (adlibrary_sources.py), no network.

python -m unittest test_adlibrary_sources -v
"""
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

import adlibrary_sources as ad
import html_cache_manager as hcm
import search_engine as se

BASE = {"keywords": ["coaching classes"], "state": "Gujarat", "city": "Ahmedabad", "sources": ["ad_pixels"],
        "engine": "duckduckgo"}
META_PIXEL = "<script>!function(f){}(window,document,'script','https://connect.facebook.net/en_US/fbevents.js');fbq('init','123');</script>"
GOOGLE_ADS = "<script async src='https://www.googletagmanager.com/gtag/js?id=AW-1234567890'></script>"
GTM_ONLY = "<script>(function(w,d,s,l,i){})(window,document,'script','dataLayer','GTM-ABCD12');</script>"


def resp(status, payload):
    return SimpleNamespace(status_code=status, json=lambda: payload, raise_for_status=lambda: None, text="")


class Catalog(unittest.TestCase):
    def test_statuses(self):
        with mock.patch.dict(os.environ, {"META_AD_LIBRARY_TOKEN": ""}):
            st = {s["id"]: s["status"] for s in ad.list_sources()}
        self.assertEqual(st, {"ad_pixels": "available", "meta_ad_library": "needs_key", "google_transparency": "available",
                              "meta_ad_library_web": "unavailable", "google_transparency_web": "unavailable"})
        note = next(s["note"] for s in ad.list_sources() if s["id"] == "meta_ad_library")
        self.assertIn("political", note.lower())


class Validation(unittest.TestCase):
    def bad(self, msg, **over):
        with self.assertRaises(ValueError) as cm:
            ad.validate_request({**BASE, **over})
        self.assertIn(msg.lower(), str(cm.exception).lower())

    def test_rejections(self):
        self.bad("at least one keyword", keywords=[])
        self.bad("select a state", state="")
        self.bad("letters only", city="Ahm3d")
        self.bad("at least one source", sources=[])
        self.bad("unknown source", sources=["tiktok"])
        self.bad("not available", sources=["meta_ad_library_web"])
        self.bad("unknown search engine", engine="yahoo")
        with mock.patch.dict(os.environ, {"META_AD_LIBRARY_TOKEN": ""}):
            self.bad("META_AD_LIBRARY_TOKEN", sources=["meta_ad_library"])
        with mock.patch.dict(os.environ, {"BRAVE_SEARCH_API_KEY": ""}):
            self.bad("BRAVE_SEARCH_API_KEY", engine="brave")


class AdTags(unittest.TestCase):
    def test_detect(self):
        self.assertEqual(ad.detect_ad_tags(META_PIXEL + GOOGLE_ADS), ["Meta Pixel", "Google Ads"])  # gtag.js?id=AW- is Ads, not a GTM container
        self.assertEqual(ad.detect_ad_tags(GTM_ONLY), ["Google Tag Manager"])
        self.assertEqual(ad.detect_ad_tags("<html>no ads</html>"), [])

    def run_pixels(self, hits, pages):
        with mock.patch.dict(se.ENGINE_FUNCS, {"duckduckgo": lambda *a: hits}), \
                mock.patch.object(ad.deep_search, "fetch", side_effect=lambda u: pages.get(u, "")), \
                mock.patch.object(ad.time, "sleep"):
            return ad.search(BASE)

    def test_only_strong_ad_tags_are_listed(self):
        hits = [{"title": "Alpha Classes | Home", "url": "https://alpha.in/courses", "snippet": "Call 98250 11111"},
                {"title": "Beta Academy", "url": "https://beta.in/", "snippet": ""},
                {"title": "Gamma Tutors", "url": "https://gamma.in/", "snippet": ""},
                {"title": "Top 10 coaching classes in Ahmedabad", "url": "https://list.in/top", "snippet": ""},
                {"title": "Classes - Wikipedia", "url": "https://en.wikipedia.org/wiki/Class", "snippet": ""},
                {"title": "Govt", "url": "https://gujarat.gov.in/x", "snippet": ""}]
        pages = {"https://alpha.in/": META_PIXEL, "https://beta.in/": GTM_ONLY, "https://gamma.in/": "<html></html>"}
        r = self.run_pixels(hits, pages)
        self.assertEqual([x["company"] for x in r["results"]], ["Alpha Classes"])
        alpha = r["results"][0]
        self.assertEqual((alpha["website"], alpha["ad_tags"], alpha["phone"]), ("https://alpha.in/", "Meta Pixel", "+91 98250 11111"))
        self.assertIn("3 website(s) checked, 2 without ad tags", r["sources"]["ad_pixels"]["errors"][0])
        self.assertEqual(r["sources"]["ad_pixels"]["status"], "ok", "the info note is not an error")

    def test_site_budget(self):
        hits = [{"title": f"Site {i}", "url": f"https://s{i}.in/", "snippet": ""} for i in range(30)]
        fetched = []
        with mock.patch.dict(se.ENGINE_FUNCS, {"duckduckgo": lambda *a: hits}), \
                mock.patch.object(ad.deep_search, "fetch", side_effect=lambda u: fetched.append(u) or GOOGLE_ADS), \
                mock.patch.object(ad.time, "sleep"):
            ad.search({**BASE, "keywords": ["a", "b"]})
        self.assertEqual(len(fetched), ad.AD_PIXEL_SITES)

    def test_duckduckgo_empty_hint(self):
        r = self.run_pixels([], {})
        self.assertIn("BRAVE_SEARCH_API_KEY", r["hint"])


class Meta(unittest.TestCase):
    def test_groups_ads_per_page_and_india_rule(self):
        data = {"data": [
            {"page_id": "11", "page_name": "Clean Ahmedabad Foundation", "ad_delivery_start_time": "2026-10-02",
             "publisher_platforms": ["facebook", "instagram"], "bylines": "Clean Ahmedabad Foundation"},
            {"page_id": "11", "page_name": "Clean Ahmedabad Foundation", "ad_delivery_start_time": "2026-09-01",
             "publisher_platforms": ["facebook"]},
            {"page_id": "", "page_name": "skip"}]}
        with mock.patch.dict(os.environ, {"META_AD_LIBRARY_TOKEN": "t"}), \
                mock.patch.object(ad.requests, "get", return_value=resp(200, data)) as g:
            out = ad.search_meta("cleanliness", {})
        params = g.call_args.kwargs["params"]
        self.assertEqual((params["ad_reached_countries"], params["ad_type"], params["search_terms"]),
                         ('["IN"]', "POLITICAL_AND_ISSUE_ADS", "cleanliness"))
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["ad_since"], "2026-09-01")
        self.assertIn("2 active ad(s)", out[0]["details"])
        self.assertIn("view_all_page_id=11", out[0]["ad_link"])

    def test_rejected_token(self):
        err = SimpleNamespace(status_code=400, json=lambda: {"error": {"message": "Invalid OAuth access token"}})
        with mock.patch.dict(os.environ, {"META_AD_LIBRARY_TOKEN": "bad"}), \
                mock.patch.object(ad.requests, "get", return_value=err), self.assertRaises(ad.PortalError) as cm:
            ad.search_meta("x", {})
        self.assertIn("Invalid OAuth", str(cm.exception))


class Transparency(unittest.TestCase):
    def test_only_advertiser_pages(self):
        hits = [{"title": "Acme Coaching - Google Ads Transparency Center", "url": "https://adstransparency.google.com/advertiser/AR123?region=IN"},
                {"title": "Help", "url": "https://adstransparency.google.com/faq"},
                {"title": "Unrelated", "url": "https://deepmind.google/x"}]
        req = ad.validate_request({**BASE, "sources": ["google_transparency"]})
        with mock.patch.dict(se.ENGINE_FUNCS, {"duckduckgo": lambda *a: hits}):
            out = ad.search_transparency("coaching", req)
        self.assertEqual([o["company"] for o in out], ["Acme Coaching"])


class Robustness(unittest.TestCase):
    def test_one_source_failing_and_dedupe(self):
        def boom(*a):
            raise AttributeError("x")
        hits = [{"title": "Alpha Classes", "url": "https://alpha.in/", "snippet": ""}]
        transparency = [ad.make_result("google_transparency", company="Alpha Classes", url="https://adstransparency.google.com/advertiser/AR1",
                                       ad_link="https://adstransparency.google.com/advertiser/AR1")]
        with mock.patch.dict(se.ENGINE_FUNCS, {"duckduckgo": lambda *a: hits}), \
                mock.patch.object(ad.deep_search, "fetch", return_value=GOOGLE_ADS), \
                mock.patch.object(ad, "search_transparency", return_value=transparency), \
                mock.patch.object(ad, "search_meta", side_effect=boom), \
                mock.patch.dict(os.environ, {"META_AD_LIBRARY_TOKEN": "t"}), mock.patch.object(ad.time, "sleep"):
            r = ad.search({**BASE, "sources": ["ad_pixels", "google_transparency", "meta_ad_library"]})
        self.assertEqual(r["sources"]["meta_ad_library"]["status"], "error")
        self.assertEqual(r["total"], 1, "same advertiser from two sources is one row")
        self.assertTrue(r["results"][0]["ad_link"], "the Google Ads link is merged into the website row")


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
        for m, u in (("get", "/api/adlibrary"), ("post", "/api/adlibrary/search"), ("post", "/api/adlibrary/save")):
            self.assertEqual(getattr(self.client, m)(u).status_code, 401, u)
        self.assertEqual(self.client.post("/api/adlibrary/search", headers=self.h, json={**BASE, "keywords": []}).status_code, 400)
        row = ad.make_result("ad_pixels", company="Alpha Classes", website="https://alpha.in/", url="https://alpha.in/",
                             ad_tags="Meta Pixel", details="Ad tags on website: Meta Pixel")
        fake = {"query": {}, "results": [row], "total": 1, "engine": "duckduckgo", "hint": "",
                "sources": {"ad_pixels": {"name": "x", "status": "ok", "count": 1, "seconds": 1, "errors": []}}}
        with mock.patch.object(ad, "search", return_value=fake) as live:
            r1 = self.client.post("/api/adlibrary/search", headers=self.h, json=BASE).get_json()
            r2 = self.client.post("/api/adlibrary/search", headers=self.h, json=BASE).get_json()
        self.assertEqual((live.call_count, r1["cache"]["hit"], r2["cache"]["hit"]), (1, False, True))
        with tempfile.TemporaryDirectory() as d, mock.patch.object(self.app, "MASTER_PATH", os.path.join(d, "m.csv")):
            a = self.client.post("/api/adlibrary/save", headers=self.h, json={"results": [row]}).get_json()
            b = self.client.post("/api/adlibrary/save", headers=self.h, json={"results": [row]}).get_json()
        self.assertEqual((a["added"], b["added"]), (1, 0))
        lead = ad.result_to_raw_lead(row)
        self.assertEqual((lead["lead_type"], lead["source"]), ("Active Advertiser", "Ad Library (Ad tags on websites)"))


if __name__ == "__main__":
    unittest.main()

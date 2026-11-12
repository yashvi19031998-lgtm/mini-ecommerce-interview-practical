"""Tests for Scraping / Mining -> Google Maps (maps_sources.py), no network.

python -m unittest test_maps_sources -v
"""
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

import requests

import html_cache_manager as hcm
import maps_sources as ms

BASE = {"keywords": ["restaurant"], "state": "Gujarat", "city": "Ahmedabad", "sources": ["osm"]}


def row(sid, company, phone="", website="", rating=None, reviews=0, category="", location="Ahmedabad", url=""):
    return ms.make_result(sid, company=company, phone=phone, website=website, rating=rating, reviews=reviews,
                          category=category, location=location, url=url or f"https://maps.example/{company}")


def resp(status, payload, text=""):
    return SimpleNamespace(status_code=status, text=text, json=lambda: payload, raise_for_status=lambda: None)


class Catalog(unittest.TestCase):
    def test_statuses_follow_keys(self):
        with mock.patch.dict(os.environ, {"GOOGLE_PLACES_API_KEY": ""}):
            st = {s["id"]: s["status"] for s in ms.list_sources()}
            self.assertEqual(st, {"osm": "available", "google_places": "needs_key", "google_maps": "unavailable"})
        with mock.patch.dict(os.environ, {"GOOGLE_PLACES_API_KEY": "k"}):
            self.assertEqual(ms.source_status("google_places"), "available")
        reason = next(s["reason"] for s in ms.list_sources() if s["id"] == "google_maps")
        self.assertIn("terms", reason)


class Validation(unittest.TestCase):
    def bad(self, msg, **over):
        with self.assertRaises(ValueError) as cm:
            ms.validate_request({**BASE, **over})
        self.assertIn(msg.lower(), str(cm.exception).lower())

    def test_ok_and_defaults(self):
        r = ms.validate_request({**BASE, "keywords": [" Restaurant ", "restaurant", "cafe"], "sources": ["osm", "osm"]})
        self.assertEqual((r["keywords"], r["sources"], r["website"], r["min_rating"]),
                         (["Restaurant", "cafe"], ["osm"], "any", 0.0))

    def test_rejections(self):
        self.bad("at least one keyword", keywords=[])
        self.bad("at most 5", keywords=[f"k{i}" for i in range(6)])
        self.bad("longer than 80", keywords=["x" * 81])
        self.bad("double quotes", keywords=['a"b'])
        self.bad("select a state", state="")
        self.bad("unknown state", state="Narnia")
        self.bad("letters only", city="Ahm3dabad")
        self.bad("at least one source", sources=[])
        self.bad("unknown source", sources=["bing"])
        self.bad("not available", sources=["google_maps"])
        self.bad("minimum rating", min_rating=2)
        self.bad("website filter", website="maybe")
        self.bad("target audience", audience=["y" * 61])
        with mock.patch.dict(os.environ, {"GOOGLE_PLACES_API_KEY": ""}):
            self.bad("GOOGLE_PLACES_API_KEY", sources=["google_places"])


class Search(unittest.TestCase):
    def run_with(self, osm=None, places=None, **over):
        funcs = {"osm": osm or (lambda *a: []), "google_places": places or (lambda *a: [])}
        with mock.patch.dict(ms.SEARCH_FUNCS, funcs), mock.patch.object(ms.time, "sleep"), \
                mock.patch.dict(os.environ, {"GOOGLE_PLACES_API_KEY": "k"}):
            return ms.search({**BASE, **over})

    def test_website_filter_and_counts(self):
        osm = lambda *a: [row("osm", "Has Site", "+91 98250 11111", "https://a.in"), row("osm", "No Site", "+91 98250 22222")]
        r = self.run_with(osm, website="without")
        self.assertEqual([x["company"] for x in r["results"]], ["No Site"])
        self.assertTrue(r["results"][0]["no_website"])
        self.assertEqual(r["hidden"]["website"], 1)
        r = self.run_with(osm, website="with")
        self.assertEqual([x["company"] for x in r["results"]], ["Has Site"])

    def test_min_rating_only_filters_rated_results(self):
        places = lambda *a: [row("google_places", "Low", "+91 98250 33333", rating=3.2),
                             row("google_places", "High", "+91 98250 44444", rating=4.6)]
        osm = lambda *a: [row("osm", "Unrated", "+91 98250 55555")]
        r = self.run_with(osm, places, sources=["osm", "google_places"], min_rating=4)
        self.assertEqual(sorted(x["company"] for x in r["results"]), ["High", "Unrated"])
        self.assertEqual(r["hidden"]["rating"], 1)

    def test_dedupe_across_sources_and_order(self):
        places = lambda *a: [row("google_places", "Acme Cafe", "+91 98250 66666", rating=4.1, reviews=50),
                             row("google_places", "Best Cafe", "+91 98250 77777", rating=4.8, reviews=900)]
        osm = lambda *a: [row("osm", "ACME CAFE", "098250 66666"), row("osm", "No Phone Cafe")]
        r = self.run_with(osm, places, sources=["google_places", "osm"])
        self.assertEqual([x["company"] for x in r["results"]], ["Best Cafe", "Acme Cafe", "No Phone Cafe"],
                         "phone first, then rating; the duplicate phone is removed")

    def test_audience_filter_with_fallback(self):
        osm = lambda *a: [row("osm", "Sunrise Hospital", category="amenity: hospital"),
                          row("osm", "City Cafe", category="amenity: cafe")]
        r = self.run_with(osm, audience=["Healthcare hospital"])
        self.assertEqual([x["company"] for x in r["results"]], ["Sunrise Hospital"])
        r = self.run_with(osm, audience=["Automobile"])
        self.assertEqual(len(r["results"]), 2)
        self.assertIn("target audience", r["sources"]["osm"]["errors"][0])

    def test_one_source_failing_does_not_stop_others(self):
        def slow(*a):
            raise requests.Timeout("slow")
        places = lambda *a: [row("google_places", "Ok Cafe", "+91 98250 88888")]
        r = self.run_with(slow, places, sources=["osm", "google_places"])
        self.assertEqual(r["sources"]["osm"]["status"], "error")
        self.assertIn("did not answer in time", r["sources"]["osm"]["errors"][0])
        self.assertEqual(r["sources"]["google_places"]["count"], 1)


class Places(unittest.TestCase):
    def test_parse_pages_and_skip_closed(self):
        page1 = {"places": [
            {"displayName": {"text": "Open Cafe"}, "nationalPhoneNumber": "098250 12345", "websiteUri": "https://open.in",
             "formattedAddress": "SG Highway, Ahmedabad", "primaryType": "coffee_shop",
             "googleMapsUri": "https://maps.google.com/?cid=1", "rating": 4.4, "userRatingCount": 120,
             "businessStatus": "OPERATIONAL"},
            {"displayName": {"text": "Closed Cafe"}, "businessStatus": "CLOSED_PERMANENTLY"}], "nextPageToken": "t"}
        page2 = {"places": [{"displayName": {"text": "Second"}, "googleMapsUri": "https://maps.google.com/?cid=2"}]}
        sess = mock.Mock()
        sess.post.side_effect = [resp(200, page1), resp(200, page2)]
        with mock.patch.dict(os.environ, {"GOOGLE_PLACES_API_KEY": "k"}), mock.patch.object(ms.time, "sleep"):
            out = ms.search_places(sess, "cafe", "Gujarat", "Ahmedabad")
        self.assertEqual([o["company"] for o in out], ["Open Cafe", "Second"])
        first = out[0]
        self.assertEqual((first["rating"], first["reviews"], first["category"], first["no_website"]),
                         (4.4, 120, "coffee shop", False))
        self.assertTrue(out[1]["no_website"])
        self.assertEqual(sess.post.call_args_list[0].kwargs["json"]["textQuery"], "cafe in Ahmedabad, India")
        self.assertEqual(sess.post.call_args_list[1].kwargs["json"]["pageToken"], "t")

    def test_rejected_key(self):
        sess = mock.Mock()
        sess.post.return_value = resp(403, {}, "API key not valid")
        with mock.patch.dict(os.environ, {"GOOGLE_PLACES_API_KEY": "bad"}), self.assertRaises(ms.PortalError):
            ms.search_places(sess, "cafe", "Gujarat", "")


class Leads(unittest.TestCase):
    def test_raw_lead(self):
        lead = ms.result_to_raw_lead(row("google_places", "Open Cafe", "098250 12345", rating=4.4, reviews=120,
                                         category="coffee shop"))
        self.assertEqual((lead["source"], lead["lead_type"]), ("Google Maps (Google Places API)", "Local Business"))
        self.assertIn("Google rating 4.4 (120 reviews)", lead["description"])
        self.assertIn("No website", lead["description"])


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

    def test_login_required(self):
        for m, u in (("get", "/api/maps"), ("post", "/api/maps/search"), ("post", "/api/maps/save")):
            self.assertEqual(getattr(self.client, m)(u).status_code, 401, u)

    def test_catalog_search_cache_save(self):
        body = self.client.get("/api/maps", headers=self.h).get_json()
        self.assertEqual(body["states"][0], "All India")
        self.assertEqual(self.client.post("/api/maps/search", headers=self.h,
                                          json={**BASE, "keywords": []}).status_code, 400)
        fake = {"query": {}, "results": [row("osm", "Acme Cafe", "+91 98250 12345")], "total": 1, "hidden": {},
                "sources": {"osm": {"name": "OpenStreetMap", "status": "ok", "count": 1, "seconds": 1, "errors": []}}}
        with mock.patch.object(ms, "search", return_value=fake) as live:
            r1 = self.client.post("/api/maps/search", headers=self.h, json=BASE).get_json()
            r2 = self.client.post("/api/maps/search", headers=self.h, json=BASE).get_json()
        self.assertEqual(live.call_count, 1)
        self.assertEqual((r1["cache"]["hit"], r2["cache"]["hit"]), (False, True))
        self.assertIn("in_leads", r2["results"][0])
        self.assertEqual(self.client.post("/api/maps/save", headers=self.h, json={"results": []}).status_code, 400)
        with tempfile.TemporaryDirectory() as d, mock.patch.object(self.app, "MASTER_PATH", os.path.join(d, "m.csv")):
            rw = row("osm", "Acme Cafe", "+91 98250 12345")
            a = self.client.post("/api/maps/save", headers=self.h, json={"results": [rw]}).get_json()
            b = self.client.post("/api/maps/save", headers=self.h, json={"results": [rw]}).get_json()
        self.assertEqual((a["added"], b["added"]), (1, 0))


if __name__ == "__main__":
    unittest.main()

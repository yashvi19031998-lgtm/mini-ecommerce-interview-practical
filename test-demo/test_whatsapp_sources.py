"""Tests for Scraping / Mining -> WhatsApp Groups (whatsapp_sources.py), no network.

python -m unittest test_whatsapp_sources -v
"""
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

import html_cache_manager as hcm
import search_engine as se
import whatsapp_sources as wa

BASE = {"keywords": ["real estate"], "state": "Gujarat", "city": "", "sources": ["invite_links"], "engine": "duckduckgo"}
CODE1 = "AbCdEfGhIjKlMnOpQrSt12"
CODE2 = "ZyXwVuTsRqPoNmLkJiHg98"


class Catalog(unittest.TestCase):
    def test_members_never_available(self):
        st = {s["id"]: s for s in wa.list_sources()}
        self.assertEqual(st["group_members"]["status"], "unavailable")
        self.assertIn("DPDP", st["group_members"]["reason"])
        with self.assertRaises(ValueError):
            wa.validate_request({**BASE, "sources": ["group_members"]})


class Validation(unittest.TestCase):
    def test_rules(self):
        r = wa.validate_request({k: v for k, v in BASE.items() if k != "state"})
        self.assertEqual(r["state"], "All India", "state is optional for groups")
        for over, msg in (({"keywords": []}, "at least one topic"), ({"city": "Ahm3d"}, "letters only"),
                          ({"sources": []}, "at least one source"), ({"engine": "yahoo"}, "unknown search engine")):
            with self.assertRaises(ValueError) as cm:
                wa.validate_request({**BASE, **over})
            self.assertIn(msg, str(cm.exception).lower())


class Parsing(unittest.TestCase):
    def test_codes_and_names(self):
        self.assertEqual(wa.codes_in(f"join https://chat.whatsapp.com/{CODE1} and chat.whatsapp.com/invite/{CODE2}"), [CODE1, CODE2])
        self.assertEqual(wa.codes_in("https://chat.whatsapp.com/short"), [])
        self.assertEqual(wa.clean_group_name("Ahmedabad Property Deals - WhatsApp Group Invite"), "Ahmedabad Property Deals")
        self.assertEqual(wa.clean_group_name("WhatsApp Group Invite"), "")

    def test_invite_links_only_from_whatsapp_results(self):
        hits = [{"title": "Ahmedabad Property Deals | WhatsApp Group Invite", "url": f"https://chat.whatsapp.com/{CODE1}", "snippet": "Buy sell rent"},
                {"title": "Business - Wikipedia", "url": "https://en.wikipedia.org/wiki/Business", "snippet": f"chat.whatsapp.com/{CODE2}"}]
        with mock.patch.dict(se.ENGINE_FUNCS, {"duckduckgo": lambda *a: hits}), mock.patch.object(wa.time, "sleep"):
            r = wa.search(BASE)
        self.assertEqual([(x["group_name"], x["url"]) for x in r["results"]],
                         [("Ahmedabad Property Deals", f"https://chat.whatsapp.com/{CODE1}")])

    def test_directories_read_pages_but_never_whatsapp(self):
        page = (f"<html><h3>Surat Realty Group</h3><a href='https://chat.whatsapp.com/{CODE2}'>Join</a>"
                f"<a href='https://chat.whatsapp.com/{CODE1}'>Gujarat Property Network</a></html>")
        hits = [{"title": "Real estate WhatsApp group links", "url": "https://groups-site.in/real-estate", "snippet": ""},
                {"title": "WhatsApp", "url": "https://www.whatsapp.com/x", "snippet": ""}]
        fetched = []
        with mock.patch.dict(se.ENGINE_FUNCS, {"duckduckgo": lambda *a: hits}), mock.patch.object(wa.time, "sleep"), \
                mock.patch.object(wa.deep_search, "fetch", side_effect=lambda u: fetched.append(u) or page):
            r = wa.search({**BASE, "sources": ["link_directories"]})
        self.assertEqual(fetched, ["https://groups-site.in/real-estate"])
        names = {x["group_name"] for x in r["results"]}
        self.assertEqual(names, {"Surat Realty Group", "Gujarat Property Network"})
        self.assertTrue(all(x["found_on"] == "https://groups-site.in/real-estate" for x in r["results"]))

    def test_directory_page_budget(self):
        hits = [{"title": f"Links {i}", "url": f"https://site{i}.in/", "snippet": ""} for i in range(9)]
        fetched = []
        with mock.patch.dict(se.ENGINE_FUNCS, {"duckduckgo": lambda *a: hits}), mock.patch.object(wa.time, "sleep"), \
                mock.patch.object(wa.deep_search, "fetch", side_effect=lambda u: fetched.append(u) or ""):
            wa.search({**BASE, "sources": ["link_directories"], "keywords": ["a", "b"]})
        self.assertEqual(len(fetched), wa.DIRECTORY_PAGES)


class SearchBehaviour(unittest.TestCase):
    def test_dedupe_keeps_best_name_and_errors_isolated(self):
        a = wa.make_result("link_directories", CODE1, "", "real estate", found_on="https://x.in")
        b = wa.make_result("invite_links", CODE1, "Ahmedabad Property Deals", "real estate")

        def boom(*args):
            raise AttributeError("x")
        with mock.patch.object(wa, "search_directories", return_value=[a]), \
                mock.patch.object(wa, "search_invites", return_value=[b]):
            r = wa.search({**BASE, "sources": ["link_directories", "invite_links"]})
        self.assertEqual(r["total"], 1)
        self.assertEqual((r["results"][0]["group_name"], r["results"][0]["found_on"]), ("Ahmedabad Property Deals", "https://x.in"))
        with mock.patch.object(wa, "search_invites", side_effect=boom), \
                mock.patch.object(wa, "search_directories", return_value=[a]):
            r = wa.search({**BASE, "sources": ["link_directories", "invite_links"]})
        self.assertEqual((r["sources"]["invite_links"]["status"], r["total"]), ("error", 1))

    def test_hint_and_no_phone_fields(self):
        with mock.patch.dict(se.ENGINE_FUNCS, {"duckduckgo": lambda *a: []}), mock.patch.object(wa.time, "sleep"):
            r = wa.search(BASE)
        self.assertIn("BRAVE_SEARCH_API_KEY", r["hint"])
        lead = wa.result_to_raw_lead(wa.make_result("invite_links", CODE1, "Group", "topic"))
        self.assertNotIn("mobile_number", lead)
        self.assertEqual(lead["lead_type"], "WhatsApp Group (community)")


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
        for m, u in (("get", "/api/whatsapp"), ("post", "/api/whatsapp/search"), ("post", "/api/whatsapp/save")):
            self.assertEqual(getattr(self.client, m)(u).status_code, 401, u)
        self.assertEqual(self.client.post("/api/whatsapp/search", headers=self.h, json={**BASE, "keywords": []}).status_code, 400)
        row = wa.make_result("invite_links", CODE1, "Ahmedabad Property Deals", "real estate")
        fake = {"query": {}, "results": [row], "total": 1, "engine": "duckduckgo", "hint": "",
                "sources": {"invite_links": {"name": "x", "status": "ok", "count": 1, "seconds": 1, "errors": []}}}
        with mock.patch.object(wa, "search", return_value=fake) as live:
            self.client.post("/api/whatsapp/search", headers=self.h, json=BASE)
            r2 = self.client.post("/api/whatsapp/search", headers=self.h, json=BASE).get_json()
        self.assertEqual((live.call_count, r2["cache"]["hit"]), (1, True))
        with tempfile.TemporaryDirectory() as d, mock.patch.object(self.app, "MASTER_PATH", os.path.join(d, "m.csv")):
            a = self.client.post("/api/whatsapp/save", headers=self.h, json={"results": [row]}).get_json()
            b = self.client.post("/api/whatsapp/save", headers=self.h, json={"results": [row]}).get_json()
        self.assertEqual((a["added"], b["added"]), (1, 0))


class SavedLeadFields(unittest.TestCase):
    """Bug 2026-11-12: the invite link / RERA register link became the lead's website."""

    def test_invite_and_government_links_are_never_the_website(self):
        from lead_normalizer import normalize_lead_record
        import realestate_sources as rs
        lead = normalize_lead_record(wa.result_to_raw_lead(wa.make_result("invite_links", CODE1, "G", "x")), "t")
        self.assertEqual(lead["website"], "")
        self.assertEqual(lead["source_url"], f"https://chat.whatsapp.com/{CODE1}")
        rera = rs.result_to_raw_lead(rs.make_result("karnataka_rera", company="Sidvin", url=rs.KARNATAKA_URL + "?promoter=Sidvin"))
        self.assertEqual(normalize_lead_record(rera, "t")["website"], "")
        real = normalize_lead_record({"company_name": "Acme", "source_url": "https://acme.in/contact"}, "t")
        self.assertEqual(real["website"], "https://acme.in/contact", "normal company links still become the website")


class RateLimitPartial(unittest.TestCase):
    def test_second_query_rate_limited_keeps_first_results(self):
        calls = []

        def limited(q, *a):
            calls.append(q)
            if len(calls) == 2:
                raise se.RateLimited("slow down")
            return [{"title": "Ahmedabad Property Deals", "url": f"https://chat.whatsapp.com/{CODE1}", "snippet": ""}]
        with mock.patch.dict(se.ENGINE_FUNCS, {"duckduckgo": limited}), mock.patch.object(wa.time, "sleep"):
            r = wa.search(BASE)
        self.assertEqual(r["total"], 1)


if __name__ == "__main__":
    unittest.main()

"""Tests for Scraping / Mining -> Real Estate (realestate_sources.py), no network.

python -m unittest test_realestate_sources -v
"""
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

import requests

import html_cache_manager as hcm
import realestate_sources as rs
import search_engine as se

BASE = {"keywords": ["builder"], "state": "Karnataka", "city": "", "sources": ["karnataka_rera"], "looking_for": "builders"}


def ka_row(ack, reg, project, promoter):
    return (f"var localObj = {{ appNo : '{ack}' }}; if (count < 10){{ applicationNameList .push('{ack}'); "
            f"applicationNameList2 .push('{reg}'); applicationNameList3 .push('{project}'); "
            f"applicationNameList4 .push('{promoter}'); }} applicationArray.push(localObj);")


KA_HTML = "<html><script>" + "".join([
    ka_row("ACK/1", "PRM/KA/RERA/1251/446/PR/071126/009091", "Floris &amp; Commercial", "Ananthay Properties Private Limited"),
    ka_row("ACK/2", "PRM/KA/RERA/1250/304/PR/061126/009086", "SIDVIN SERENITY 2", "Sidvin Urban Developers"),
    ka_row("ACK/3", "PRM/KA/RERA/1250/304/PR/061126/009000", "SIDVIN SERENITY", "Sidvin Urban Developers"),
    ka_row("ACK/4", "", "Prestige Lakeside", "PRESTIGE ESTATES PROJECTS LTD"),
    ka_row("ACK/5", "PRM/KA/RERA/1/1/PR/1/1", "Owner\\'s Nest", "D\\'Souza Builders"),
]) + "</script></html>"


def row(sid, company, **f):
    return rs.make_result(sid, company=company, **f)


class Catalog(unittest.TestCase):
    def test_statuses(self):
        with mock.patch.dict(os.environ, {"GOOGLE_PLACES_API_KEY": ""}):
            st = {s["id"]: s["status"] for s in rs.list_sources()}
        self.assertEqual(st["karnataka_rera"], "available")
        self.assertEqual(st["google_places"], "needs_key")
        for sid in ("maharera", "gujrera", "haryana_rera", "up_rera", "rajasthan_rera"):
            self.assertEqual(st[sid], "unavailable", sid)
        reasons = {s["id"]: s["reason"] for s in rs.list_sources()}
        self.assertIn("captcha", reasons["haryana_rera"].lower())


class Validation(unittest.TestCase):
    def bad(self, msg, **over):
        with self.assertRaises(ValueError) as cm:
            rs.validate_request({**BASE, **over})
        self.assertIn(msg.lower(), str(cm.exception).lower())

    def test_rejections(self):
        self.bad("at least one keyword", keywords=[])
        self.bad("select a state", state="")
        self.bad("unknown state", state="Narnia")
        self.bad("letters only", city="B3ngaluru")
        self.bad("looking for", looking_for="tenants")
        self.bad("at least one source", sources=[])
        self.bad("unknown source", sources=["nobroker"])
        self.bad("not available", sources=["maharera"])
        self.bad("unknown search engine", engine="yahoo")
        with mock.patch.dict(os.environ, {"GOOGLE_PLACES_API_KEY": ""}):
            self.bad("GOOGLE_PLACES_API_KEY", sources=["google_places"])
        with mock.patch.dict(os.environ, {"BRAVE_SEARCH_API_KEY": ""}):
            self.bad("BRAVE_SEARCH_API_KEY", sources=["property_portals"], engine="brave")

    def test_defaults(self):
        r = rs.validate_request({k: v for k, v in BASE.items() if k != "looking_for"})
        self.assertEqual((r["looking_for"], r["engine"]), ("both", "auto"))


class Karnataka(unittest.TestCase):
    def setUp(self):
        self.p = [mock.patch.object(rs.hcm, "fetch_or_get_cached_html", return_value=(KA_HTML, 1)),
                  mock.patch.object(rs.deep_search, "public_url_guard")]
        for x in self.p:
            x.start()

    def tearDown(self):
        for x in self.p:
            x.stop()

    def test_parse_unescapes(self):
        rows = rs.parse_karnataka(KA_HTML)
        self.assertEqual(len(rows), 5)
        self.assertEqual(rows[0]["project"], "Floris & Commercial")
        self.assertEqual(rows[4]["promoter"], "D'Souza Builders")
        self.assertEqual(rows[4]["project"], "Owner's Nest")

    def test_generic_keyword_lists_builders_grouped(self):
        out = rs.search_karnataka(None, "builder", rs.validate_request(BASE))
        names = [o["company"] for o in out]
        self.assertEqual(names[:2], ["Ananthay Properties Private Limited", "Sidvin Urban Developers"])
        self.assertEqual(len(out), 4, "Sidvin's two projects are grouped into one builder")
        sidvin = out[1]
        self.assertTrue(sidvin["details"].startswith("2 RERA project(s)"))
        prestige = next(o for o in out if "Prestige" in o["company"])
        self.assertEqual(prestige["company"], "Prestige Estates Projects Ltd", "ALL-CAPS names are title-cased")
        self.assertNotIn("()", prestige["details"], "empty registration numbers are not shown")
        self.assertEqual((sidvin["role"], sidvin["kind"]), ("builder", "listing"))

    def test_name_keyword_filters(self):
        out = rs.search_karnataka(None, "prestige", rs.validate_request(BASE))
        self.assertEqual([o["company"] for o in out], ["Prestige Estates Projects Ltd"])

    def test_skips_other_states_and_agents(self):
        r = rs.search({**BASE, "state": "Gujarat"})
        self.assertEqual(r["sources"]["karnataka_rera"]["status"], "skipped")
        r = rs.search({**BASE, "looking_for": "agents"})
        self.assertEqual(r["sources"]["karnataka_rera"]["status"], "skipped")

    def test_site_down(self):
        with mock.patch.object(rs.hcm, "fetch_or_get_cached_html", return_value=("", 0)):
            r = rs.search(BASE)
        self.assertEqual(r["sources"]["karnataka_rera"]["status"], "error")
        self.assertIn("did not answer", r["sources"]["karnataka_rera"]["errors"][0])


class QaFoundBugs(unittest.TestCase):
    """Found in browser QA 2026-11-12."""

    def test_each_builder_has_its_own_link_so_in_leads_is_not_shared(self):
        with mock.patch.object(rs.hcm, "fetch_or_get_cached_html", return_value=(KA_HTML, 1)), \
                mock.patch.object(rs.deep_search, "public_url_guard"):
            out = rs.search_karnataka(None, "builder", rs.validate_request(BASE))
        urls = [o["url"] for o in out]
        self.assertEqual(len(set(urls)), len(urls))
        self.assertTrue(all(u.startswith(rs.KARNATAKA_URL) for u in urls))
        from lead_normalizer import MasterLeadRegistry
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "m.csv")
            reg = MasterLeadRegistry(path)
            reg.add_lead(rs.result_to_raw_lead(out[0]))
            reg.save_master_safely()
            for o in out:
                o["in_leads"] = False   # the API route resets the flag the same way
            se.mark_existing(out, path)
        self.assertEqual([o["in_leads"] for o in out], [True] + [False] * (len(out) - 1))

    def test_deep_search_never_treats_a_government_register_as_the_website(self):
        import deep_search as ds
        self.assertTrue(ds.is_government(rs.KARNATAKA_URL))
        self.assertTrue(ds.is_government("https://www.mca.gov.in/x"))
        self.assertFalse(ds.is_government("https://prestigeconstructions.com"))
        with mock.patch.object(ds, "crawl_site") as crawl, mock.patch.object(ds, "find_website", return_value=None), \
                mock.patch.object(ds, "guess_email", return_value=""):
            out = ds.enrich({"url": rs.KARNATAKA_URL + "?promoter=x", "company": "Sidvin Urban Developers"}, "duckduckgo", False)
        crawl.assert_not_called()
        self.assertEqual((out["website"], out["status"]), ("", "none"))


class Portals(unittest.TestCase):
    def req(self, **over):
        return rs.validate_request({**BASE, "sources": ["property_portals"], "engine": "duckduckgo", "city": "Pune",
                                    "state": "Maharashtra", **over})

    def test_queries_and_off_target_filter(self):
        seen = []

        def fake(q, n, t, s):
            seen.append(q)
            return [{"title": "Kolte Patil Builders - 99acres", "url": "https://www.99acres.com/kolte-patil-builders", "snippet": "Call 98220 12345"},
                    {"title": "Unrelated", "url": "https://deepmind.google/x", "snippet": ""}]
        with mock.patch.dict(se.ENGINE_FUNCS, {"duckduckgo": fake}), mock.patch.object(rs.time, "sleep"):
            out = rs.search_portals(None, "apartment", self.req(looking_for="builders"))
        self.assertEqual(len(seen), 3)
        self.assertIn('site:99acres.com "apartment" builders Pune', seen)
        domains = {se.domain_of(o["url"]) for o in out}
        self.assertTrue(all(d.endswith("99acres.com") for d in domains), domains)
        self.assertEqual(out[0]["phone"], "+91 98220 12345")

    def test_rate_limit_keeps_partial(self):
        calls = []

        def fake(q, n, t, s):
            calls.append(q)
            if len(calls) == 2:
                raise se.RateLimited("slow down")
            return [{"title": "A Builders", "url": "https://www.99acres.com/a-builders", "snippet": ""}]
        with mock.patch.dict(se.ENGINE_FUNCS, {"duckduckgo": fake}), mock.patch.object(rs.time, "sleep"):
            out = rs.search_portals(None, "flat", self.req(looking_for="builders"))
        self.assertEqual(len(out), 1)

    def test_duckduckgo_empty_gives_hint(self):
        with mock.patch.dict(se.ENGINE_FUNCS, {"duckduckgo": lambda *a: []}), mock.patch.object(rs.time, "sleep"):
            r = rs.search({**BASE, "sources": ["property_portals"], "engine": "duckduckgo", "state": "Maharashtra", "city": "Pune"})
        self.assertIn("BRAVE_SEARCH_API_KEY", r["hint"])


class SearchBehaviour(unittest.TestCase):
    def run_with(self, funcs, **over):
        with mock.patch.dict(rs.SEARCH_FUNCS, funcs), mock.patch.object(rs.time, "sleep"), \
                mock.patch.dict(os.environ, {"GOOGLE_PLACES_API_KEY": "k"}):
            return rs.search({**BASE, "state": "Maharashtra", "city": "Pune", **over})

    def test_dedupe_merges_contacts_across_sources(self):
        osm = lambda *a: [row("osm", "Kolte Patil Developers", website="https://koltepatil.com", role="builder")]
        places = lambda *a: [row("google_places", "Kolte Patil Developers", phone="+91 98220 11111", website="https://www.koltepatil.com/",
                                 rating=4.3, reviews=500, role="builder")]
        r = self.run_with({"osm": osm, "google_places": places}, sources=["osm", "google_places"])
        self.assertEqual(r["total"], 1)
        self.assertEqual(r["results"][0]["phone"], "+91 98220 11111")

    def test_one_source_exception_isolated(self):
        def broken(*a):
            raise AttributeError("boom")

        def slow(*a):
            raise requests.Timeout()
        ok = lambda *a: [row("google_places", "Good Homes", phone="+91 98220 22222", role="agent")]
        r = self.run_with({"osm": broken, "google_places": ok, "property_portals": slow},
                          sources=["osm", "google_places", "property_portals"], engine="duckduckgo")
        self.assertEqual(r["sources"]["osm"]["status"], "error")
        self.assertIn("AttributeError", r["sources"]["osm"]["errors"][0])
        self.assertIn("did not answer in time", r["sources"]["property_portals"]["errors"][0])
        self.assertEqual(r["total"], 1)

    def test_audience_word_match_with_fallback(self):
        osm = lambda *a: [row("osm", "Luxury Villas Co", category="office: estate_agent"),
                          row("osm", "Budget Flats", category="office: estate_agent")]
        r = self.run_with({"osm": osm}, sources=["osm"], audience=["Luxury / premium"])
        self.assertEqual([x["company"] for x in r["results"]], ["Luxury Villas Co"])
        r = self.run_with({"osm": osm}, sources=["osm"], audience=["Commercial"])
        self.assertEqual(r["total"], 2)
        self.assertIn("target audience", r["sources"]["osm"]["errors"][0])


class Leads(unittest.TestCase):
    def test_raw_lead(self):
        lead = rs.result_to_raw_lead(row("karnataka_rera", "Sidvin Urban Developers", role="builder",
                                         details="2 RERA project(s): SIDVIN SERENITY", url=rs.KARNATAKA_URL))
        self.assertEqual(lead["source"], "Real Estate (Karnataka RERA)")
        self.assertEqual(lead["lead_type"], "Real Estate - Builder / Developer")
        self.assertIn("SIDVIN SERENITY", lead["description"])


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
        for m, u in (("get", "/api/realestate"), ("post", "/api/realestate/search"), ("post", "/api/realestate/save")):
            self.assertEqual(getattr(self.client, m)(u).status_code, 401, u)

    def test_catalog_search_cache_save(self):
        body = self.client.get("/api/realestate", headers=self.h).get_json()
        self.assertTrue(any(s["id"] == "karnataka_rera" for s in body["sources"]))
        self.assertEqual(self.client.post("/api/realestate/search", headers=self.h, json={**BASE, "keywords": []}).status_code, 400)
        fake = {"query": {}, "results": [row("karnataka_rera", "Sidvin Urban Developers", url=rs.KARNATAKA_URL, role="builder")],
                "total": 1, "engine": "duckduckgo", "hint": "",
                "sources": {"karnataka_rera": {"name": "Karnataka RERA", "status": "ok", "count": 1, "seconds": 1, "errors": []}}}
        with mock.patch.object(rs, "search", return_value=fake) as live:
            r1 = self.client.post("/api/realestate/search", headers=self.h, json=BASE).get_json()
            r2 = self.client.post("/api/realestate/search", headers=self.h, json=BASE).get_json()
        self.assertEqual(live.call_count, 1)
        self.assertEqual((r1["cache"]["hit"], r2["cache"]["hit"]), (False, True))
        self.assertIn("in_leads", r2["results"][0])
        with tempfile.TemporaryDirectory() as d, mock.patch.object(self.app, "MASTER_PATH", os.path.join(d, "m.csv")):
            rw = row("karnataka_rera", "Sidvin Urban Developers", url=rs.KARNATAKA_URL, role="builder", details="2 RERA project(s)")
            a = self.client.post("/api/realestate/save", headers=self.h, json={"results": [rw]}).get_json()
            b = self.client.post("/api/realestate/save", headers=self.h, json={"results": [rw]}).get_json()
        self.assertEqual((a["added"], b["added"]), (1, 0))


if __name__ == "__main__":
    unittest.main()

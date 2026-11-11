"""Tests for CRM Sources (crm_sources.py + /api/crm-sources/*). No network, no API keys.

    python -m unittest test_crm_sources -v
"""
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

import crm_sources as cs
import lead_normalizer as ln


def resp(status=200, data=None, text=""):
    return SimpleNamespace(status_code=status, json=lambda: data, text=text, raise_for_status=lambda: None)


class FakeSession:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def _next(self, method, url, kwargs):
        self.calls.append((method, url, kwargs))
        return self.responses.pop(0)

    def get(self, url, **kw):
        return self._next("GET", url, kw)

    def post(self, url, **kw):
        return self._next("POST", url, kw)


class Validation(unittest.TestCase):
    def test_ok(self):
        r = cs.validate_request([" software ", "Software", "hospital"], ["CEO"], "Gujarat", " Ahmedabad ", ["osm", "osm"])
        self.assertEqual((r["keywords"], r["city"], r["source_ids"]), (["software", "Software", "hospital"], "Ahmedabad", ["osm"]))

    def test_errors(self):
        cases = [([], [], "Gujarat", "", ["osm"], "at least one keyword"),
                 (["x"], "CEO", "Gujarat", "", ["osm"], "Titles must be a list"),
                 (["x"] * 1 + [f"k{i}" for i in range(10)], [], "Gujarat", "", ["osm"], "at most 10"),
                 (["x"], [], "Narnia", "", ["osm"], "valid state"),
                 (["x"], [], "Gujarat", "Ahmedabad<script>", ["osm"], "letters only"),
                 (["x"], [], "Gujarat", "", [], "at least one source"),
                 (["x"], [], "Gujarat", "", ["myspace"], "Unknown source")]
        for kw, tt, st, city, src, msg in cases:
            with self.subTest(msg=msg):
                with self.assertRaises(ValueError) as ctx:
                    cs.validate_request(kw, tt, st, city, src)
                self.assertIn(msg, str(ctx.exception))


class Catalog(unittest.TestCase):
    KEYS = ("APOLLO_API_KEY", "HUNTER_API_KEY", "GOOGLE_PLACES_API_KEY", "SNOV_CLIENT_ID", "SNOV_CLIENT_SECRET",
            "LUSHA_API_KEY", "ROCKETREACH_API_KEY")

    def test_statuses(self):
        with mock.patch.dict(os.environ, {k: "" for k in self.KEYS}):
            st = {s["id"]: s["status"] for s in cs.list_sources()}
        self.assertEqual({k for k, v in st.items() if v == "available"}, {"osm", "goodfirms", "zauba"})
        self.assertEqual({k for k, v in st.items() if v == "needs_key"},
                         {"apollo", "hunter", "google_places", "snov", "lusha", "rocketreach"})
        for k in ("justdial", "sulekha", "indiamart", "tradeindia", "clutch", "yellowpages", "ambitionbox", "google_maps"):
            self.assertEqual(st[k], "unavailable", k)

    def test_key_enables_source(self):
        with mock.patch.dict(os.environ, {"SNOV_CLIENT_ID": "a", "SNOV_CLIENT_SECRET": ""}):
            self.assertEqual(next(s for s in cs.list_sources() if s["id"] == "snov")["status"], "needs_key")
        with mock.patch.dict(os.environ, {"SNOV_CLIENT_ID": "a", "SNOV_CLIENT_SECRET": "b"}):
            self.assertEqual(next(s for s in cs.list_sources() if s["id"] == "snov")["status"], "available")


class Directories(unittest.TestCase):
    def test_osm(self):
        data = {"elements": [
            {"type": "node", "id": 1, "tags": {"name": "TatvaSoft", "office": "it", "website": "https://tatvasoft.com",
                                               "phone": "+91 96014 21472", "addr:city": "Ahmedabad"}},
            {"type": "way", "id": 2, "tags": {"name": "No Contact Ltd", "office": "company"}},
            {"type": "node", "id": 3, "tags": {"office": "it"}}]}  # unnamed -> skipped
        s = FakeSession(resp(data=data))
        out = cs.search_osm(s, "software companies", [], "Gujarat", "Ahmedabad")
        self.assertEqual([r["company"] for r in out], ["TatvaSoft", "No Contact Ltd"])  # contactable first
        self.assertEqual(out[0]["url"], "https://www.openstreetmap.org/node/1")
        q = s.calls[0][2]["data"]["data"]
        self.assertIn('"office"="it"', q)
        self.assertIn('"name"~"software",i', q)
        self.assertIn('area["name"="Ahmedabad"]', q)

    def test_osm_needs_area_and_retries_once(self):
        with self.assertRaises(cs.PortalError):
            cs.search_osm(FakeSession(), "software", [], cs.ALL_INDIA, "")
        with mock.patch.object(cs.time, "sleep"):
            with self.assertRaises(cs.PortalError) as ctx:
                cs.search_osm(FakeSession(resp(502), resp(502)), "software", [], "Gujarat", "")
        self.assertIn("busy", str(ctx.exception))
        with self.assertRaises(cs.PortalError):
            cs.search_osm(FakeSession(), "xyz", [], "Gujarat", "Surat")  # no category and no usable word

    def test_goodfirms(self):
        html = """<div class="firm-wrapper-item"><h3 class="firm-name"><a href="/company/acme">Acme Soft</a></h3>
                  <a href="https://acme.in/?utm_source=goodfirms.co">Visit</a><div class="firm-location">Ahmedabad, India</div></div>"""
        out = cs.search_goodfirms(FakeSession(resp(text=html)), "software", [], "Gujarat", "")
        self.assertEqual((out[0]["company"], out[0]["website"], out[0]["url"]),
                         ("Acme Soft", "https://acme.in/", "https://www.goodfirms.co/company/acme"))

    def _zauba(self, names):
        rows = "".join(f'''<div class="companies-list"><h2><a href="https://www.zaubacorp.com/{n}">{n}</a></h2>
            <div class="badge badge-success">Active</div><div class="badge"><img alt="CIN"/> U123</div>
            <div class="badge"><img alt="Address"/> GIDC, AHMEDABAD, Gujarat</div></div>''' for n in names)
        return resp(text=rows)

    def test_zauba_keyword_and_partial_on_rate_limit(self):
        s = FakeSession(self._zauba(["ALPHA SOFTWARE PRIVATE LIMITED", "MAYUR REEDS PRIVATE LIMITED"]), resp(429))
        with mock.patch.object(cs.time, "sleep"):
            out = cs.search_zauba(s, "software companies", [], "Gujarat", "Ahmedabad")
        self.assertEqual([r["company"] for r in out], ["Alpha Software Private Limited"])
        self.assertIn("CIN U123", out[0]["details"])
        self.assertEqual(s.calls[1][1], "https://www.zaubacorp.com/companies-list/city-AHMEDABAD/p-2")


class Databases(unittest.TestCase):
    def test_missing_key(self):
        with mock.patch.dict(os.environ, {"HUNTER_API_KEY": ""}):
            with self.assertRaises(cs.PortalError):
                cs.search_hunter(FakeSession(), "software", [], "Gujarat", "")

    def test_api_error_codes(self):
        for code, word in ((401, "rejected"), (402, "credits"), (429, "rate limit")):
            with self.assertRaises(cs.PortalError) as ctx:
                cs._api_error(resp(code), "X")
            self.assertIn(word, str(ctx.exception))

    def test_hunter(self):
        discover = {"data": [{"domain": "acme.in", "organization": "Acme", "emails_count": {"total": 12}}]}
        domain = {"data": {"emails": [{"value": "ceo@acme.in", "first_name": "Ravi", "last_name": "Shah",
                                       "position": "CEO", "linkedin": "https://linkedin.com/in/ravi"}]}}
        s = FakeSession(resp(data=discover), resp(data=domain))
        with mock.patch.dict(os.environ, {"HUNTER_API_KEY": "k"}), mock.patch.object(cs.time, "sleep"):
            out = cs.search_hunter(s, "software", [], "Gujarat", "Ahmedabad")
        body = s.calls[0][2]["json"]
        self.assertEqual(body["headquarters_location"]["include"][0], {"country": "IN", "city": "Ahmedabad"})
        self.assertEqual((out[0]["email"], out[0]["contact_name"], out[0]["contact_title"]), ("ceo@acme.in", "Ravi Shah", "CEO"))

    def test_google_places_paging_and_closed(self):
        p1 = {"places": [{"displayName": {"text": "City Hospital"}, "internationalPhoneNumber": "+91 79 1234 5678",
                          "websiteUri": "https://cityhospital.in", "formattedAddress": "Ahmedabad", "rating": 4.5,
                          "userRatingCount": 120, "businessStatus": "OPERATIONAL", "googleMapsUri": "https://maps.google.com/?cid=1"},
                         {"displayName": {"text": "Closed Clinic"}, "businessStatus": "CLOSED_PERMANENTLY"}],
              "nextPageToken": "t2"}
        p2 = {"places": [{"displayName": {"text": "Care Clinic"}, "businessStatus": "OPERATIONAL"}]}
        s = FakeSession(resp(data=p1), resp(data=p2))
        with mock.patch.dict(os.environ, {"GOOGLE_PLACES_API_KEY": "k"}), mock.patch.object(cs.time, "sleep"):
            out = cs.search_google_places(s, "hospital", [], "Gujarat", "Ahmedabad")
        self.assertEqual([r["company"] for r in out], ["City Hospital", "Care Clinic"])
        self.assertEqual(s.calls[0][2]["headers"]["X-Goog-Api-Key"], "k")
        self.assertIn("places.websiteUri", s.calls[0][2]["headers"]["X-Goog-FieldMask"])
        self.assertEqual(s.calls[0][2]["json"]["textQuery"], "hospital in Ahmedabad, Gujarat, India")
        self.assertEqual(s.calls[1][2]["json"]["pageToken"], "t2")
        self.assertIn("4.5", out[0]["details"])

    def test_snov_async(self):
        s = FakeSession(resp(data={"access_token": "tok"}), resp(data={"meta": {"task_hash": "h1"}}),
                        resp(data={"status": "in_progress"}),
                        resp(data={"status": "completed", "data": {"companies": [
                            {"name": "Acme", "domain": "acme.in", "location": "Ahmedabad", "industry": "Software", "size": "11-50"}]}}))
        with mock.patch.dict(os.environ, {"SNOV_CLIENT_ID": "a", "SNOV_CLIENT_SECRET": "b"}), mock.patch.object(cs.time, "sleep"):
            out = cs.search_snov(s, "software", [], "Gujarat", "Ahmedabad")
        self.assertEqual(s.calls[1][2]["headers"]["Authorization"], "Bearer tok")
        self.assertEqual(s.calls[2][1], "https://api.snov.io/v2/database-search/companies/result/h1")
        self.assertEqual((out[0]["company"], out[0]["website"]), ("Acme", "https://acme.in"))

    def test_lusha_previews(self):
        data = {"results": [{"firstName": "Asha", "lastName": "Patel", "jobTitle": {"title": "CTO"},
                             "company": {"name": "Acme", "domain": "acme.in"}, "location": {"city": "Ahmedabad", "country": "India"},
                             "socialLinks": {"linkedin": "https://linkedin.com/in/asha"}, "has": ["emails", "phones"]}]}
        s = FakeSession(resp(data=data))
        with mock.patch.dict(os.environ, {"LUSHA_API_KEY": "k"}):
            out = cs.search_lusha(s, "software", ["CTO"], "Gujarat", "")
        self.assertEqual(s.calls[0][2]["headers"], {"api_key": "k"})
        self.assertEqual(s.calls[0][2]["json"]["filters"]["contacts"]["include"]["jobTitles"], ["CTO"])
        self.assertEqual((out[0]["contact_name"], out[0]["email"]), ("Asha Patel", ""))
        self.assertIn("reveal", out[0]["details"])

    def test_rocketreach(self):
        data = [{"name": "Dev Mehta", "current_title": "Founder", "current_employer": "Acme",
                 "current_employer_domain": "acme.in", "city": "Ahmedabad", "region": "Gujarat",
                 "linkedin_url": "https://linkedin.com/in/dev"}]
        s = FakeSession(resp(201, data=data))
        with mock.patch.dict(os.environ, {"ROCKETREACH_API_KEY": "k"}):
            out = cs.search_rocketreach(s, "software", ["Founder"], "Gujarat", "Ahmedabad")
        self.assertEqual(s.calls[0][2]["headers"], {"Api-Key": "k"})
        self.assertEqual(s.calls[0][2]["json"]["query"]["geo"], ["Ahmedabad, Gujarat, IN"])
        self.assertEqual((out[0]["contact_name"], out[0]["website"]), ("Dev Mehta", "https://acme.in"))

    def test_apollo_reuses_existing_module(self):
        lead = {"full_name": "Neha Shah", "company_name": "Acme", "email": "neha@acme.in", "mobile_number": "+91 98",
                "website": "https://acme.in", "description": "CEO at Acme.", "source_url": "https://linkedin.com/in/neha",
                "location": "Ahmedabad, India"}
        with mock.patch.dict(os.environ, {"APOLLO_API_KEY": "k"}), \
                mock.patch("apollo_enricher.search_apollo_prospects", return_value=[lead]) as fn:
            out = cs.search_apollo(FakeSession(), "software", ["CEO"], "Gujarat", "Ahmedabad")
        self.assertEqual(fn.call_args.kwargs["api_key"], "k")
        self.assertEqual(fn.call_args.kwargs["locations"], ["Ahmedabad, Gujarat, India"])
        self.assertEqual((out[0]["contact_name"], out[0]["contact_title"], out[0]["linkedin"]),
                         ("Neha Shah", "CEO", "https://linkedin.com/in/neha"))


class SearchAndSave(unittest.TestCase):
    def test_orchestration(self):
        def ok(session, kw, titles, state, city):
            return [cs.make_result("goodfirms", company="Acme", website="https://acme.in"),
                    cs.make_result("goodfirms", company="Acme", website="https://acme.in")]  # duplicate
        with mock.patch.dict(cs.SOURCES["goodfirms"], {"search": ok}), mock.patch.object(cs.time, "sleep"):
            res = cs.search(["software"], [], "Gujarat", "Ahmedabad", ["goodfirms", "justdial", "hunter"])
        self.assertEqual(res["total"], 1)
        self.assertEqual(res["sources"]["justdial"]["status"], "skipped")
        self.assertEqual(res["sources"]["goodfirms"]["status"], "ok")

    def test_raw_lead_and_registry(self):
        r1 = cs.make_result("osm", company="TatvaSoft", phone="+91 96014 21472", url="https://www.openstreetmap.org/node/1",
                            category="office: it")
        r2 = cs.make_result("osm", company="Novus", url="https://www.openstreetmap.org/node/2")
        raw = cs.result_to_raw_lead(r1)
        self.assertEqual((raw["lead_type"], raw["source"]), ("Business Directory", "CRM Source (OpenStreetMap (Overpass))"))
        with tempfile.TemporaryDirectory() as d:
            reg = ln.MasterLeadRegistry(os.path.join(d, "m.csv"))
            self.assertEqual([reg.add_lead(cs.result_to_raw_lead(x))[0] for x in (r1, r2)], ["added", "added"])
        contact = cs.make_result("hunter", company="Acme", contact_name="Ravi", contact_title="CEO", email="ceo@acme.in")
        self.assertEqual(cs.result_to_raw_lead(contact)["lead_type"], "B2B Contact")


class Api(unittest.TestCase):
    def setUp(self):
        import app as app_module
        self.app = app_module
        self.client = app_module.app.test_client()
        ok = SimpleNamespace(status_code=200, json=lambda: {"email": "owner@example.com"})
        self.p = [mock.patch("api_auth.requests.get", return_value=ok), mock.patch("api_auth.ALLOWED_EMAILS", set())]
        for x in self.p:
            x.start()
        self.h = {"Authorization": "Bearer t"}

    def tearDown(self):
        for x in self.p:
            x.stop()

    def test_login_required(self):
        for m, u in (("get", "/api/crm-sources"), ("post", "/api/crm-sources/search"), ("post", "/api/crm-sources/save")):
            self.assertEqual(getattr(self.client, m)(u).status_code, 401)

    def test_catalog_search_save(self):
        body = self.client.get("/api/crm-sources", headers=self.h).get_json()
        self.assertEqual(body["states"][0], "All India")
        self.assertTrue(any(s["id"] == "osm" for s in body["sources"]))
        self.assertEqual(self.client.post("/api/crm-sources/search", headers=self.h,
                                          json={"keywords": [], "state": "Gujarat", "sources": ["osm"]}).status_code, 400)
        fake = {"results": [], "total": 0, "sources": {}, "query": {}}
        with mock.patch.object(cs, "search", return_value=fake) as s:
            r = self.client.post("/api/crm-sources/search", headers=self.h, json={
                "keywords": ["software"], "titles": ["CEO"], "state": "Gujarat", "city": "Surat", "sources": ["osm"]})
        self.assertEqual(r.status_code, 200)
        s.assert_called_once_with(["software"], ["CEO"], "Gujarat", "Surat", ["osm"])
        self.assertEqual(self.client.post("/api/crm-sources/save", headers=self.h, json={"results": []}).status_code, 400)
        self.assertEqual(self.client.post("/api/crm-sources/save", headers=self.h,
                                          json={"results": [{"company": "X"}]}).status_code, 400)  # no contact/link
        with tempfile.TemporaryDirectory() as d, mock.patch.object(self.app, "MASTER_PATH", os.path.join(d, "m.csv")):
            row = cs.make_result("osm", company="TatvaSoft", website="https://tatvasoft.com", url="https://www.openstreetmap.org/node/1")
            r1 = self.client.post("/api/crm-sources/save", headers=self.h, json={"results": [row]}).get_json()
            r2 = self.client.post("/api/crm-sources/save", headers=self.h, json={"results": [row]}).get_json()
        self.assertEqual((r1["added"], r2["added"]), (1, 0))


if __name__ == "__main__":
    unittest.main()

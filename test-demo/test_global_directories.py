"""Tests for Global Directories (global_directories.py + /api/global-directories/*).
No network, no external API keys.

    python -m unittest test_global_directories -v
"""

import os
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest import mock

import global_directories as gd
import lead_normalizer as ln


def resp(status=200, data=None, text=""):
    return SimpleNamespace(
        status_code=status,
        json=lambda: data,
        text=text,
        raise_for_status=lambda: None if status < 400 else (_ for _ in ()).throw(Exception(f"HTTP {status}"))
    )


class FakeSession:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def _next(self, method, url, kwargs):
        self.calls.append((method, url, kwargs))
        if not self.responses:
            raise IndexError(f"No mock response queued for {method} {url}")
        return self.responses.pop(0)

    def get(self, url, **kw):
        return self._next("GET", url, kw)

    def post(self, url, **kw):
        return self._next("POST", url, kw)


class Validation(unittest.TestCase):
    def test_valid_request(self):
        req = {
            "keywords": [" software ", "Software", "fintech"],
            "audience": ["IT / Software", "Startups"],
            "country": "GB",
            "region": "Greater London",
            "city": "London",
            "sources": ["osm", "osm", "goodfirms"]
        }
        clean = gd.validate_request(req)
        self.assertEqual(clean["keywords"], ["software", "fintech"])
        self.assertEqual(clean["audience"], ["IT / Software", "Startups"])
        self.assertEqual(clean["country"], "GB")
        self.assertEqual(clean["region"], "Greater London")
        self.assertEqual(clean["city"], "London")
        self.assertEqual(clean["sources"], ["osm", "goodfirms"])

    def test_validation_errors(self):
        cases = [
            ("not a dict", "Invalid request format"),
            ({"keywords": "software", "country": "GB", "sources": ["osm"]}, "Keywords must be a list"),
            ({"keywords": [], "country": "GB", "sources": ["osm"]}, "Enter at least one keyword"),
            ({"keywords": ['test"quote'], "country": "GB", "sources": ["osm"]}, 'Keywords cannot contain quotes (")'),
            ({"keywords": ["a" * 81], "country": "GB", "sources": ["osm"]}, "Each of the keywords must be 80 characters or less"),
            ({"keywords": [f"k{i}" for i in range(11)], "country": "GB", "sources": ["osm"]}, "Enter at most 10 keywords"),
            ({"keywords": ["soft"], "audience": "IT", "country": "GB", "sources": ["osm"]}, "Audience must be a list"),
            ({"keywords": ["soft"], "audience": [f"a{i}" for i in range(6)], "country": "GB", "sources": ["osm"]}, "Enter at most 5 audience targets"),
            ({"keywords": ["soft"], "audience": ["x" * 61], "country": "GB", "sources": ["osm"]}, "Each audience target must be 60 characters or less"),
            ({"keywords": ["soft"], "country": "", "sources": ["osm"]}, "Select a country"),
            ({"keywords": ["soft"], "country": "IN", "sources": ["osm"]}, "Select a country"),
            ({"keywords": ["soft"], "country": "XYZ", "sources": ["osm"]}, "Select a country"),
            ({"keywords": ["soft"], "country": "GB", "city": "London123", "sources": ["osm"]}, "City must be letters only (max 60 characters)"),
            ({"keywords": ["soft"], "country": "GB", "region": "Region#$", "sources": ["osm"]}, "Region must be letters only (max 60 characters)"),
            ({"keywords": ["soft"], "country": "GB", "sources": []}, "Select at least one source"),
            ({"keywords": ["soft"], "country": "GB", "sources": "osm"}, "Select at least one source"),
            ({"keywords": ["soft"], "country": "GB", "sources": ["invalid_source"]}, "Unknown source: invalid_source"),
        ]
        for data, expected_msg in cases:
            with self.subTest(msg=expected_msg):
                with self.assertRaises(ValueError) as ctx:
                    gd.validate_request(data)
                self.assertIn(expected_msg, str(ctx.exception))

    def test_sources_availability_check(self):
        # Needs key check
        with mock.patch.dict(os.environ, {"COMPANIES_HOUSE_API_KEY": ""}):
            with self.assertRaises(ValueError) as ctx:
                gd.validate_request({"keywords": ["soft"], "country": "GB", "sources": ["companies_house"]})
            self.assertIn("needs COMPANIES_HOUSE_API_KEY in .env", str(ctx.exception))

        with mock.patch.dict(os.environ, {"SEC_USER_AGENT": ""}):
            with self.assertRaises(ValueError) as ctx:
                gd.validate_request({"keywords": ["soft"], "country": "US", "sources": ["sec_edgar"]})
            self.assertIn("needs SEC_USER_AGENT in .env", str(ctx.exception))

        # Unavailable source check
        with self.assertRaises(ValueError) as ctx:
            gd.validate_request({"keywords": ["soft"], "country": "GB", "sources": ["clutch"]})
        self.assertIn("is not available", str(ctx.exception))


class Catalog(unittest.TestCase):
    def test_countries_list(self):
        # Check at least 24 countries, no India ("IN"), sorted by name
        self.assertGreaterEqual(len(gd.COUNTRIES), 24)
        ids = [c["id"] for c in gd.COUNTRIES]
        self.assertNotIn("IN", ids)
        for req_id in ["AE", "AU", "CA", "DE", "FR", "GB", "IE", "IL", "IT", "JP", "KE", "MY", "NG", "NL", "NZ", "PH", "QA", "SA", "SE", "SG", "ES", "CH", "US", "ZA"]:
            self.assertIn(req_id, ids)
        names = [c["name"] for c in gd.COUNTRIES]
        self.assertEqual(names, sorted(names))

    def test_catalog_status_flips_with_keys(self):
        with mock.patch.dict(os.environ, {"COMPANIES_HOUSE_API_KEY": "", "SEC_USER_AGENT": ""}):
            sources = {s["id"]: s for s in gd.list_sources()}
            self.assertEqual(sources["osm"]["status"], "available")
            self.assertEqual(sources["goodfirms"]["status"], "available")
            self.assertEqual(sources["companies_house"]["status"], "needs_key")
            self.assertEqual(sources["sec_edgar"]["status"], "needs_key")
            self.assertEqual(sources["clutch"]["status"], "unavailable")
            self.assertEqual(sources["opencorporates"]["status"], "unavailable")

        with mock.patch.dict(os.environ, {"COMPANIES_HOUSE_API_KEY": "uk_test_key", "SEC_USER_AGENT": "App user@test.com"}):
            sources = {s["id"]: s for s in gd.list_sources()}
            self.assertEqual(sources["companies_house"]["status"], "available")
            self.assertEqual(sources["sec_edgar"]["status"], "available")


class Parsers(unittest.TestCase):
    def test_osm_parser(self):
        sample = {
            "elements": [
                {
                    "type": "node", "id": 101,
                    "tags": {
                        "name": "Acme Tech UK",
                        "office": "it",
                        "website": "https://acmetech.co.uk",
                        "phone": "+44 20 7946 0912",
                        "email": "info@acmetech.co.uk",
                        "addr:city": "London",
                        "addr:street": "Baker Street"
                    }
                },
                {
                    "type": "way", "id": 102,
                    "tags": {
                        "name": "London Web Studio",
                        "office": "company"
                    }
                },
                {
                    "type": "node", "id": 103,
                    "tags": {"office": "it"}  # Unnamed node -> skipped
                }
            ]
        }
        s = FakeSession(resp(200, data=sample))
        out = gd.search_osm(s, "software", {"country": "GB", "city": "London"})
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0]["company"], "Acme Tech UK")
        self.assertEqual(out[0]["website"], "https://acmetech.co.uk")
        self.assertEqual(out[0]["phone"], "+44 20 7946 0912")
        self.assertEqual(out[0]["email"], "info@acmetech.co.uk")
        self.assertEqual(out[0]["url"], "https://www.openstreetmap.org/node/101")
        self.assertEqual(out[1]["company"], "London Web Studio")

    def test_osm_empty_and_errors(self):
        # Empty elements
        s = FakeSession(resp(200, data={"elements": []}))
        out = gd.search_osm(s, "software", {"country": "GB", "city": "London"})
        self.assertEqual(out, [])

        # Busy retry logic (502 -> retry -> busy exception)
        with mock.patch.object(gd.time, "sleep"):
            s_busy = FakeSession(resp(502), resp(504))
            with self.assertRaises(gd.PortalError) as ctx:
                gd.search_osm(s_busy, "software", {"country": "GB", "city": "London"})
            self.assertIn("busy", str(ctx.exception))

    def test_companies_house_parser(self):
        sample = {
            "items": [
                {
                    "company_name": "TECH SOLUTIONS LTD",
                    "company_number": "12345678",
                    "company_status": "active",
                    "registered_office_address": {
                        "address_line_1": "10 Downing St",
                        "locality": "London",
                        "postal_code": "SW1A 2AA"
                    },
                    "sic_codes": ["62012", "62020"]
                },
                {
                    "company_name": "",  # Empty name -> skipped
                    "company_number": "99999999"
                }
            ]
        }
        s = FakeSession(resp(200, data=sample))
        with mock.patch.dict(os.environ, {"COMPANIES_HOUSE_API_KEY": "test_key"}):
            out = gd.search_companies_house(s, "tech", {"country": "GB", "city": "London"})
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["company"], "Tech Solutions Ltd")
        self.assertIn("12345678", out[0]["details"])
        self.assertIn("SIC: 62012, 62020", out[0]["category"])
        self.assertEqual(out[0]["url"], "https://find-and-update.company-information.service.gov.uk/company/12345678")
        self.assertIn("London", out[0]["location"])

    def test_companies_house_errors(self):
        with mock.patch.dict(os.environ, {"COMPANIES_HOUSE_API_KEY": "bad_key"}):
            s = FakeSession(resp(401))
            with self.assertRaises(gd.PortalError) as ctx:
                gd.search_companies_house(s, "tech", {"country": "GB", "city": "London"})
            self.assertIn("Invalid or unauthorized COMPANIES_HOUSE_API_KEY", str(ctx.exception))

        with mock.patch.dict(os.environ, {"COMPANIES_HOUSE_API_KEY": "key"}):
            s2 = FakeSession(resp(429))
            with self.assertRaises(gd.PortalError) as ctx:
                gd.search_companies_house(s2, "tech", {"country": "GB", "city": "London"})
            self.assertIn("rate limit", str(ctx.exception))

    def test_sec_edgar_parser(self):
        sample_efts = {
            "hits": {
                "hits": [
                    {
                        "_source": {
                            "display_names": ["APPLE INC  (CIK 0000320193)"],
                            "ciks": ["0000320193"],
                            "biz_locations": ["Cupertino, CA"],
                            "biz_states": ["CA"],
                            "sics": ["3571"],
                            "form": "10-K"
                        }
                    }
                ]
            }
        }
        s = FakeSession(resp(200, data=sample_efts))
        with mock.patch.dict(os.environ, {"SEC_USER_AGENT": "MyApp admin@example.com"}):
            out = gd.search_sec_edgar(s, "apple", {"country": "US", "region": "CA"})
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["company"], "Apple Inc")
        self.assertIn("0000320193", out[0]["url"])
        self.assertIn("Cupertino, CA", out[0]["location"])
        self.assertIn("SIC: 3571", out[0]["category"])

    def test_sec_edgar_atom_fallback(self):
        atom_xml = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>ORACLE CORP</title>
    <link href="https://www.sec.gov/edgar/browse/?CIK=0001341439"/>
    <summary type="html">CIK: 0001341439, State: TX, SIC: PREPACKAGED SOFTWARE</summary>
    <content type="text/xml">
      <company-info>
        <addresses>
          <address type="business">
            <city>AUSTIN</city>
            <state>TX</state>
            <phone>512-555-0100</phone>
          </address>
        </addresses>
      </company-info>
    </content>
  </entry>
</feed>"""
        # First call fails (empty efts hits), second call returns atom xml
        s = FakeSession(resp(200, data={"hits": {"hits": []}}), resp(200, text=atom_xml))
        with mock.patch.dict(os.environ, {"SEC_USER_AGENT": "MyApp admin@example.com"}):
            out = gd.search_sec_edgar(s, "oracle", {"country": "US", "region": "TX"})
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["company"], "ORACLE CORP")
        self.assertEqual(out[0]["phone"], "512-555-0100")
        self.assertIn("AUSTIN, TX", out[0]["location"])

    def test_goodfirms_parser(self):
        html = """
        <div class="firm-wrapper-item">
          <div class="firm-name"><h3>Digital Agency London</h3></div>
          <a class="visit-website" href="https://digitalagency.co.uk?utm_source=goodfirms.co">Visit Website</a>
          <span class="firm-location">London, UK</span>
          <a class="firm-profile" href="/company/digital-agency-london">Profile</a>
        </div>
        """
        s = FakeSession(resp(200, text=html))
        out = gd.search_goodfirms(s, "software", {"country": "GB", "city": "London"})
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["company"], "Digital Agency London")
        self.assertEqual(out[0]["website"], "https://digitalagency.co.uk")
        self.assertEqual(out[0]["url"], "https://www.goodfirms.co/company/digital-agency-london")


class SkipRules(unittest.TestCase):
    def test_companies_house_skips_non_gb(self):
        req = {"keywords": ["soft"], "country": "US", "sources": ["companies_house"]}
        res = gd._run_source("companies_house", req)
        self.assertEqual(res["status"], "skipped")
        self.assertIn("only covers the United Kingdom (GB)", res["errors"][0])

    def test_sec_edgar_skips_non_us(self):
        req = {"keywords": ["soft"], "country": "GB", "sources": ["sec_edgar"]}
        res = gd._run_source("sec_edgar", req)
        self.assertEqual(res["status"], "skipped")
        self.assertIn("only covers the United States (US)", res["errors"][0])

    def test_osm_skips_without_city_or_region(self):
        req = {"keywords": ["soft"], "country": "GB", "city": "", "region": "", "sources": ["osm"]}
        res = gd._run_source("osm", req)
        self.assertEqual(res["status"], "skipped")
        self.assertIn("needs a city or region", res["errors"][0])

    def test_goodfirms_skips_without_city(self):
        req = {"keywords": ["soft"], "country": "GB", "city": "", "sources": ["goodfirms"]}
        res = gd._run_source("goodfirms", req)
        self.assertEqual(res["status"], "skipped")
        self.assertIn("needs a city", res["errors"][0])


class SearchBehaviour(unittest.TestCase):
    def test_audience_filtering_and_fallback(self):
        mock_results = [
            gd.make_result("osm", company="Fintech Ltd", category="office: it", details="financial tech"),
            gd.make_result("osm", company="Health Clinic", category="amenity: clinic", details="healthcare"),
        ]

        def fake_search(session, kw, req):
            return list(mock_results)

        # 1. Matching audience narrows results
        with mock.patch.dict(gd.SOURCES["osm"], {"search": fake_search}):
            res = gd._run_source("osm", {"keywords": ["tech"], "audience": ["Fintech"], "country": "GB", "city": "London"})
            self.assertEqual(len(res["results"]), 1)
            self.assertEqual(res["results"][0]["company"], "Fintech Ltd")

        # 2. Non-matching audience keeps all results and adds note to errors
        with mock.patch.dict(gd.SOURCES["osm"], {"search": fake_search}):
            res2 = gd._run_source("osm", {"keywords": ["tech"], "audience": ["Agriculture"], "country": "GB", "city": "London"})
            self.assertEqual(len(res2["results"]), 2)
            self.assertTrue(any("Audience filter" in e for e in res2["errors"]))

    def test_deduplication_and_sorting(self):
        raw = [
            gd.make_result("osm", company="Alpha Corp", website="https://alpha.com", phone="", email=""),
            gd.make_result("goodfirms", company="Alpha Corp", website="https://alpha.com", phone="+12345", email="alpha@test.com"),  # duplicate domain
            gd.make_result("osm", company="Beta LLC", website="", phone="+19876", email="", country="US"),
            gd.make_result("goodfirms", company="Beta LLC", website="", phone="", email="", country="US"),  # duplicate name+country
            gd.make_result("osm", company="Gamma Inc", website="https://gamma.com", phone="", email="gamma@test.com"),
        ]
        deduped = gd._dedupe(raw)
        # Should keep unique domains/names
        self.assertEqual(len(deduped), 3)

        # Ordering: results with email/phone/website first
        deduped.sort(key=lambda r: -(bool(r.get("email")) * 4 + bool(r.get("phone")) * 2 + bool(r.get("website"))))
        self.assertTrue(bool(deduped[0]["email"]))

    def test_fault_tolerance_one_source_fails(self):
        def ok_search(session, kw, req):
            return [gd.make_result("goodfirms", company="Good Co", website="https://good.com")]

        def fail_search(session, kw, req):
            raise gd.PortalError("Network connection reset")

        with mock.patch.dict(gd.SOURCES["goodfirms"], {"search": ok_search}), \
             mock.patch.dict(gd.SOURCES["osm"], {"search": fail_search}), \
             mock.patch.object(gd.time, "sleep"):
            res = gd.search({
                "keywords": ["software"],
                "country": "GB",
                "city": "London",
                "sources": ["goodfirms", "osm"]
            })
            self.assertEqual(res["total"], 1)
            self.assertEqual(res["sources"]["goodfirms"]["status"], "ok")
            self.assertEqual(res["sources"]["osm"]["status"], "error")


class ReviewFixes(unittest.TestCase):
    """Bugs found in code review (2026-11-12)."""

    def test_sec_fallback_keyword_is_url_encoded(self):
        s = FakeSession(resp(200, data={"hits": {"hits": []}}), resp(200, text="<feed></feed>"))
        with mock.patch.dict(os.environ, {"SEC_USER_AGENT": "MyApp admin@example.com"}):
            gd.search_sec_edgar(s, "software & cloud", {"country": "US", "region": ""})
        method, url, kw = s.calls[1]
        self.assertEqual(url, "https://www.sec.gov/cgi-bin/browse-edgar")
        self.assertEqual(kw["params"]["company"], "software & cloud")

    def test_audience_matches_words_not_whole_phrase(self):
        rows = [gd.make_result("goodfirms", company="ELEKS", category="Software development company"),
                gd.make_result("goodfirms", company="Bakery", category="Food")]
        with mock.patch.dict(gd.SOURCES["goodfirms"], {"search": lambda *a: list(rows)}):
            res = gd._run_source("goodfirms", {"keywords": ["x"], "audience": ["IT / Software"], "country": "GB",
                                               "city": "London"})
        self.assertEqual([r["company"] for r in res["results"]], ["ELEKS"])

    def test_unexpected_error_in_one_source_does_not_break_search(self):
        def broken(*a):
            raise AttributeError("'NoneType' object has no attribute 'get_text'")

        def slow(*a):
            raise gd.requests.Timeout("slow")
        with mock.patch.dict(gd.SOURCES["goodfirms"], {"search": broken}), \
                mock.patch.dict(gd.SOURCES["osm"], {"search": slow}), mock.patch.object(gd.time, "sleep"):
            res = gd.search({"keywords": ["software"], "country": "GB", "city": "London", "sources": ["goodfirms", "osm"]})
        self.assertEqual(res["sources"]["goodfirms"]["status"], "error")
        self.assertIn("AttributeError", res["sources"]["goodfirms"]["errors"][0])
        self.assertIn("did not answer in time", res["sources"]["osm"]["errors"][0])

    def test_dedupe_keeps_contact_details_from_duplicates(self):
        raw = [gd.make_result("osm", company="Alpha Corp", website="https://alpha.com"),
               gd.make_result("goodfirms", company="Alpha Corp", website="https://www.alpha.com/about",
                              phone="+12345", email="alpha@test.com"),
               gd.make_result("osm", company="Beta LLC", country="US"),
               gd.make_result("goodfirms", company="beta llc", country="US", website="https://beta.io", phone="+19876")]
        out = gd._dedupe(raw)
        self.assertEqual(len(out), 2)
        alpha, beta = out
        self.assertEqual((alpha["email"], alpha["phone"]), ("alpha@test.com", "+12345"))
        self.assertEqual((beta["website"], beta["phone"]), ("https://beta.io", "+19876"))


class LeadSaving(unittest.TestCase):
    def test_result_to_raw_lead(self):
        res = gd.make_result(
            "companies_house",
            source="UK Companies House",
            company="Global Tech Ltd",
            email="contact@globaltech.co.uk",
            phone="+44 20 1234 5678",
            website="https://globaltech.co.uk",
            location="London",
            country="GB",
            category="SIC: 62012",
            details="Company Number 09876543 · Status: active",
            url="https://find-and-update.company-information.service.gov.uk/company/09876543"
        )
        lead = gd.result_to_raw_lead(res)
        self.assertEqual(lead["company_name"], "Global Tech Ltd")
        self.assertEqual(lead["email"], "contact@globaltech.co.uk")
        self.assertEqual(lead["location"], "London, GB")
        self.assertEqual(lead["lead_type"], "Global Directory")
        self.assertEqual(lead["source"], "Global Directory (UK Companies House)")

        with tempfile.TemporaryDirectory() as d:
            reg = ln.MasterLeadRegistry(os.path.join(d, "test_leads.csv"))
            outcome, _ = reg.add_lead(lead)
            self.assertEqual(outcome, "added")
            outcome2, _ = reg.add_lead(lead)
            self.assertEqual(outcome2, "duplicate")


class Api(unittest.TestCase):
    def setUp(self):
        import app as app_module
        self.app = app_module
        self.client = app_module.app.test_client()
        ok_user = SimpleNamespace(status_code=200, json=lambda: {"email": "owner@example.com"})
        self.p = [
            mock.patch("api_auth.requests.get", return_value=ok_user),
            mock.patch("api_auth.ALLOWED_EMAILS", set())
        ]
        for x in self.p:
            x.start()
        self.h = {"Authorization": "Bearer test_token"}

    def tearDown(self):
        for x in self.p:
            x.stop()

    def test_login_required(self):
        for m, u in (("get", "/api/global-directories"),
                     ("post", "/api/global-directories/search"),
                     ("post", "/api/global-directories/save")):
            self.assertEqual(getattr(self.client, m)(u).status_code, 401)

    def test_catalog_endpoint(self):
        r = self.client.get("/api/global-directories", headers=self.h)
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertTrue(data["success"])
        self.assertTrue(any(s["id"] == "osm" for s in data["sources"]))
        self.assertTrue(any(c["id"] == "GB" for c in data["countries"]))

    def test_search_and_save_endpoints(self):
        # 1. Bad search input -> 400
        r_bad = self.client.post("/api/global-directories/search", headers=self.h, json={"keywords": []})
        self.assertEqual(r_bad.status_code, 400)

        # 2. Valid search
        with tempfile.TemporaryDirectory() as cache_d:
            with mock.patch("html_cache_manager.CACHE_DIR", cache_d):
                fake_res = {
                    "query": {"keywords": ["tech"], "country": "GB"},
                    "results": [
                        gd.make_result("osm", company="London Tech", website="https://londontech.com", url="https://osm.org/1")
                    ],
                    "total": 1,
                    "sources": {"osm": {"name": "OpenStreetMap (worldwide)", "status": "ok", "count": 1, "seconds": 0.5, "errors": []}}
                }
                with mock.patch.object(gd, "search", return_value=fake_res):
                    r_search = self.client.post("/api/global-directories/search", headers=self.h, json={
                        "keywords": ["tech"], "country": "GB", "city": "London", "sources": ["osm"]
                    })
                self.assertEqual(r_search.status_code, 200)
                self.assertTrue(r_search.get_json()["success"])

        # 3. Bad save inputs -> 400
        self.assertEqual(self.client.post("/api/global-directories/save", headers=self.h, json={"results": []}).status_code, 400)
        self.assertEqual(self.client.post("/api/global-directories/save", headers=self.h, json={"results": [{"company": "NoContact"}]}).status_code, 400)

        # 4. Valid save (adds lead, then marks duplicate)
        with tempfile.TemporaryDirectory() as d, mock.patch.object(self.app, "MASTER_PATH", os.path.join(d, "m.csv")):
            row = gd.make_result("osm", company="London Tech", website="https://londontech.com", url="https://osm.org/1")
            r1 = self.client.post("/api/global-directories/save", headers=self.h, json={"results": [row]}).get_json()
            r2 = self.client.post("/api/global-directories/save", headers=self.h, json={"results": [row]}).get_json()
            self.assertEqual((r1["added"], r2["added"]), (1, 0))
            self.assertEqual(r2["duplicate"], 1)


if __name__ == "__main__":
    unittest.main()


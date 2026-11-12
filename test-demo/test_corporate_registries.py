"""Tests for Data Extraction -> Corporate Registries (corporate_registries.py), no network.

Pages are small hand-made copies of ZaubaCorp / IndiaMART markup (checked live on 2026-11-12).
python -m unittest test_corporate_registries -v
"""
import csv
import json
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

import corporate_registries as cr
import html_cache_manager as hcm

CARD = """<div class="companies-list mb-3"><div class="companies-list-info"><h2><a href="https://www.zaubacorp.com/{slug}-{cin}">{name}</a></h2>
<div class="badge badge-success"><img alt="" src="ic_success_badge.svg"/> {status}</div></div>
<div class="companies-list-badge"><div class="badge badge-border"><img alt="CIN" src="ic_hashtag.svg"/> {cin}</div>
<div class="badge badge-border"><img alt="Address" src="ic_location.svg"/> {addr}</div>
<div class="badge badge-border"> ₹ 10,000</div></div></div>"""
SEARCH_CARD = """<div class="companies-list mb-3"><h2><a href="https://www.zaubacorp.com/{slug}-{cin}">{name}</a></h2>
<div class="badge badge-border"><img alt="" src="/assets/ic_hashtag.svg"/> {cin}</div>
<div class="badge badge-border"><img alt="" src="/assets/ic_location.svg"/> {addr}  Ahmedabad Gujarat 382424 India</div></div>"""


def card(name="SJ POLYCRAFT PRIVATE LIMITED", cin="U22190GJ2026PTC174865", status="Active",
         addr="210, Vitthal The Mall,,Koba,,Ahmedabad,Gujarat,382424-India", tpl=CARD):
    return tpl.format(name=name, cin=cin, status=status, addr=addr, slug=name.replace(" ", "-"))


def page(n, start=0, **kw):
    return "<html>" + "".join(card(name=f"CO {i} PRIVATE LIMITED", cin=f"U22190GJ2026PTC{174800 + i:06d}", **kw)
                               for i in range(start, start + n)) + "</html>"


COMPANY_PAGE = """<html><body><p>CIN: U22190GJ2026PTC174865</p><div>Company Status Active ROC ROC Ahmedabad Registration Number 174865
Company Category Company limited by shares Company Sub Category Non-government company Class of Company Private
Date of Incorporation 2026-03-13 Age of Company 0 years Activity NIC Code: 58190 NIC Description: Other publishing [Includes x]
Website www.sjpolycraft.in Address 210 Koba</div>
<table><tr><th>DIN</th><th>Director Name</th></tr><tr><td>0001</td><td>RAMESH PATEL</td></tr></table></body></html>"""


class FakeWeb:
    def __init__(self, pages):
        self.pages, self.calls = pages, []

    def __call__(self, url, headers, guard, timeout=20, **kw):
        self.calls.append(url)
        status, text = self.pages.get(url, (404, "not found"))
        return status, text, url, False


class Validation(unittest.TestCase):
    def ok(self, **over):
        return cr.validate_request({"mode": "company", "state": "Gujarat", "city": "Ahmedabad", "pages": 1, **over})

    def test_rules(self):
        for over, msg in (({"mode": "x"}, "unknown mode"), ({"city": "Ahm3d"}, "letters only"), ({"state": "Atlantis"}, "unknown state"),
                          ({"company_type": "ZZZ"}, "unknown company type"), ({"age": "Z"}, "unknown age"),
                          ({"industry": "Z"}, "unknown industry"), ({"pages": 9}, "unknown number of pages"),
                          ({"state": "All India", "city": ""}, "choose a state, city or industry"),
                          ({"industry": "K", "city": ""}, "industries per city")):
            with self.assertRaises(ValueError) as cm:
                self.ok(**over)
            self.assertIn(msg, str(cm.exception).lower(), over)

    def test_pvtltd_defaults(self):
        req = cr.validate_request({"mode": "pvtltd", "state": "Gujarat", "city": "", "company_type": "LLP", "pages": 1})
        self.assertEqual((req["company_type"], req["age"], req["status"]), ("PTC", "A", "Active"))

    def test_gst_rules(self):
        with self.assertRaises(ValueError):
            cr.validate_request({"mode": "gst_find", "keywords": [], "max_sellers": 10})
        with self.assertRaises(ValueError):
            cr.validate_request({"mode": "gst_find", "keywords": ["x"], "max_sellers": 7})
        with self.assertRaises(ValueError):
            cr.validate_request({"mode": "gst_check", "gstins": ["x"] * 101 and [f"G{i}" for i in range(101)]})
        req = cr.validate_request({"mode": "gst_check", "gstins": [" 24achpg0469j1zo ", "24ACHPG0469J1ZO"]})
        self.assertEqual(req["gstins"], ["24ACHPG0469J1ZO"])


class Urls(unittest.TestCase):
    def test_list_url_order_and_names(self):
        req = cr.validate_request({"mode": "pvtltd", "state": "Gujarat", "city": "New Delhi", "industry": "K", "pages": 1})
        self.assertEqual(cr.list_url(req, 2), "https://www.zaubacorp.com/companies-list/nic-K/city-NEW%20DELHI/"
                                              "companytype-PTC/status-Active/age-A/p-2-company.html")
        req = cr.validate_request({"mode": "company", "state": "Odisha", "city": "", "status": "", "pages": 1})
        self.assertEqual(cr.list_url(req), "https://www.zaubacorp.com/companies-list/state-ORISSA-company.html")
        req = cr.validate_request({"mode": "company", "state": "Jammu and Kashmir", "city": "", "pages": 1})
        self.assertIn("state-JAMMU%20&%20KASHMIR/status-Active", cr.list_url(req))


class Decoders(unittest.TestCase):
    def test_cin(self):
        self.assertEqual(cr.decode_cin("U22190GJ2026PTC174865"),
                         {"listed": "Unlisted", "nic_code": "22190", "cin_state": "Gujarat", "year": "2026",
                          "company_kind": "Private Limited", "type_code": "PTC"})
        self.assertEqual(cr.decode_cin("L85110KA1981PLC013115")["listed"], "Listed")
        self.assertEqual(cr.decode_cin("not a cin"), {})

    def test_gstin(self):
        ok = cr.decode_gstin("27AAACR5055K1Z7")                         # real, company
        self.assertEqual((ok["valid"], ok["state"], ok["entity"], ok["pan"]), (True, "Maharashtra", "Company", "AAACR5055K"))
        prop = cr.decode_gstin("24ACHPG0469J1ZO")                        # real, proprietor: PAN not shown on its own
        self.assertEqual((prop["valid"], prop["entity"], prop["pan"]), (True, "Proprietorship (individual)", ""))
        self.assertIn("check digit", cr.decode_gstin("24ACHPG0469J1ZX")["problem"].lower())
        self.assertIn("format", cr.decode_gstin("ABC")["problem"].lower())
        self.assertIn("state code", cr.decode_gstin("88ACHPG0469J1ZO")["problem"].lower())

    def test_gstins_in_page(self):
        html = "<p>GST No. 24ACHPG0469J1ZO</p><p>fake 24ACHPG0469J1ZX</p><script>27AAACR5055K1Z7</script>"
        self.assertEqual(cr.gstins_in(html), ["24ACHPG0469J1ZO"])        # scripts ignored, bad checksum dropped


class Parsers(unittest.TestCase):
    def test_list_card(self):
        r = cr.parse_company_list(card())[0]
        self.assertEqual((r["company"], r["status"], r["cin"], r["capital"], r["year"], r["company_kind"], r["nic_code"]),
                         ("SJ POLYCRAFT PRIVATE LIMITED", "Active", "U22190GJ2026PTC174865", "₹ 10,000", "2026", "Private Limited", "22190"))
        self.assertEqual(r["address"], "210, Vitthal The Mall, Koba, Ahmedabad, Gujarat, 382424-India")

    def test_search_card_without_alt_or_status(self):
        r = cr.parse_company_list(card(tpl=SEARCH_CARD))[0]
        self.assertEqual((r["cin"], r["status"]), ("U22190GJ2026PTC174865", ""))
        self.assertTrue(r["address"].endswith("382424-India"))

    def test_company_page(self):
        d = cr.parse_company_page(COMPANY_PAGE)
        self.assertEqual(d, {"incorporated": "2026-03-13", "roc": "ROC Ahmedabad", "category": "Company limited by shares",
                             "sub_category": "Non-government company", "class": "Private", "activity": "Other publishing",
                             "website": "https://www.sjpolycraft.in"})
        self.assertNotIn("RAMESH", json.dumps(d))                      # director names never collected


class Runs(unittest.TestCase):
    def search(self, web_pages, **data):
        web = FakeWeb(web_pages)
        with mock.patch.object(cr.idr.hcm, "fetch_page", web):
            return cr.search(data, sleep=lambda s: None), web

    def test_pages_stop_when_short(self):
        req = {"mode": "pvtltd", "state": "Gujarat", "city": "Ahmedabad", "pages": 3}
        u = cr.list_url(cr.validate_request(req))
        u2 = u.replace("-company.html", "/p-2-company.html")
        res, web = self.search({u: (200, page(30)), u2: (200, page(5, start=30))}, **req)
        self.assertEqual((res["total"], len(web.calls)), (35, 2))

    def test_no_match_message(self):
        res, _ = self.search({}, mode="company", state="Gujarat", city="Nowhere", pages=1)
        self.assertEqual(res["sources"]["zaubacorp"]["status"], "error")
        self.assertIn("No companies match", res["sources"]["zaubacorp"]["errors"][0])

    def test_industry_dropped_when_register_has_no_such_list(self):
        req = {"mode": "company", "state": "Gujarat", "city": "Ahmedabad", "industry": "K", "company_type": "LLP", "pages": 1}
        without = cr.list_url({**cr.validate_request(req), "industry": ""})
        llp = card(name="PROTEC PLUS LLP", cin="ACB-1234")
        res, web = self.search({without: (200, "<html>" + llp + "</html>")}, **req)
        self.assertEqual(len(web.calls), 2)                               # 404 with industry, then without
        self.assertEqual((res["results"][0]["cin"], res["results"][0]["company_kind"]), ("ACB-1234", "Limited Liability Partnership"))
        self.assertIn("without the industry filter", res["sources"]["zaubacorp"]["errors"][0])

    def test_name_search_filters_locally(self):
        pages = {"https://www.zaubacorp.com/companysearchresults/acme": (200, "<html>" + card(name="ACME FOODS PRIVATE LIMITED", tpl=SEARCH_CARD)
                                                                         + card(name="ACME LLP", cin="AAA-1234", tpl=SEARCH_CARD) + "</html>")}
        res, _ = self.search(pages, mode="pvtltd", keywords=["acme"], state="All India", city="")
        self.assertEqual([r["company"] for r in res["results"]], ["ACME FOODS PRIVATE LIMITED"])
        res, _ = self.search(pages, mode="company", keywords=["acme"], state="Kerala", city="")
        self.assertIn("none match the filters", res["sources"]["zaubacorp"]["errors"][0])

    def test_details(self):
        url = "https://www.zaubacorp.com/SJ-POLYCRAFT-PRIVATE-LIMITED-U22190GJ2026PTC174865"
        with mock.patch.object(cr.idr.hcm, "fetch_page", FakeWeb({url: (200, COMPANY_PAGE)})):
            out = cr.details([{"key": "a", "url": url}, {"key": "b", "url": "https://evil.example/U22190GJ2026PTC174865"}],
                             sleep=lambda s: None)["results"]
        self.assertEqual((out[0]["status"], out[0]["incorporated"]), ("ok", "2026-03-13"))
        self.assertEqual(out[1]["status"], "error")                      # only ZaubaCorp company pages are opened
        with self.assertRaises(ValueError):
            cr.details([{"url": url}] * 11)

    def test_gst_find(self):
        cat = "https://dir.indiamart.com/ahmedabad/bakery-products.html"
        rows = [{"CMP": "Shyam Bakers", "s_url": "https://www.indiamart.com/shyam/", "city": "Ahmedabad", "c_ct": "9876543210"},
                {"CMP": "No Gst Co", "s_url": "https://www.indiamart.com/nogst/", "city": "Ahmedabad"},
                {"CMP": "Blocked Co", "s_url": "https://www.indiamart.com/company/A/x/", "city": "Ahmedabad"}]
        listing = f"<script>window.__INITIAL_STATE__ = {json.dumps({'data': rows})};</script>"
        pages = {cat: (200, listing), "https://www.indiamart.com/shyam/": (200, "<p>GST 24ACHPG0469J1ZO</p>"),
                 "https://www.indiamart.com/nogst/": (200, "<p>no number</p>")}
        with mock.patch.object(cr, "robots_allowed", side_effect=lambda u: "/company/" not in u):
            res, web = self.search(pages, mode="gst_find", keywords=["bakery products"], state="Gujarat", city="Ahmedabad", max_sellers=10)
        got = {r["company"]: (r["gstin"], r["gst_state"], r["gst_problem"]) for r in res["results"]}
        self.assertEqual(got["Shyam Bakers"], ("24ACHPG0469J1ZO", "Gujarat", ""))
        self.assertIn("No GST number", got["No Gst Co"][2])
        self.assertNotIn("Blocked Co", got)
        self.assertNotIn("https://www.indiamart.com/company/A/x/", web.calls)
        self.assertTrue(any("robots.txt" in e for e in res["sources"]["indiamart_gst"]["errors"]))

    def test_gst_check_offline(self):
        with mock.patch.object(cr.idr.hcm, "fetch_page", side_effect=AssertionError("no network")):
            res = cr.search({"mode": "gst_check", "gstins": ["27AAACR5055K1Z7", "BAD"]})
        self.assertEqual([r["gst_valid"] for r in res["results"]], ["Valid", "Invalid"])


class Leads(unittest.TestCase):
    def test_mapping(self):
        r = cr.parse_company_list(card())[0]
        lead = cr.result_to_raw_lead(r)
        self.assertEqual((lead["source"], lead["source_url"], lead["website"]),
                         ("Corporate Registries (ZaubaCorp / MCA)", r["url"], ""))
        self.assertIn("CIN: U22190GJ2026PTC174865", lead["description"])
        self.assertEqual(lead["lead_type"], "New Company (under 1 year)")
        g = cr.result_to_raw_lead(cr.gst_row("24ACHPG0469J1ZO", source_id="indiamart_gst", company="Shyam", url="https://www.indiamart.com/shyam/", phone="9876543210"))
        self.assertEqual((g["lead_type"], g["mobile_number"]), ("GST Registered Business", "9876543210"))
        self.assertIn("GSTIN: 24ACHPG0469J1ZO", g["description"])


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
        for m, u in (("get", "/api/corporate-registries"), ("post", "/api/corporate-registries/search"),
                     ("post", "/api/corporate-registries/details"), ("post", "/api/corporate-registries/save")):
            self.assertEqual(getattr(self.client, m)(u).status_code, 401, u)
        cat = self.client.get("/api/corporate-registries", headers=self.h).get_json()
        self.assertEqual(len(cat["industries"]), 16)
        bad = self.client.post("/api/corporate-registries/search", headers=self.h, json={"mode": "company", "state": "All India"})
        self.assertEqual(bad.status_code, 400)
        chk = self.client.post("/api/corporate-registries/search", headers=self.h, json={"mode": "gst_check", "gstins": ["27AAACR5055K1Z7"]}).get_json()
        self.assertEqual((chk["total"], chk["cache"]["hit"]), (1, False))
        req = {"mode": "pvtltd", "state": "Gujarat", "city": "Ahmedabad", "pages": 1}
        row = cr.parse_company_list(card())[0]
        fake = {"query": {}, "results": [row], "total": 1,
                "sources": {"zaubacorp": {"name": "Z", "status": "ok", "count": 1, "seconds": 1, "errors": []}}}
        with mock.patch.object(cr, "search", return_value=fake) as live:
            self.client.post("/api/corporate-registries/search", headers=self.h, json=req)
            r2 = self.client.post("/api/corporate-registries/search", headers=self.h, json=req).get_json()
        self.assertEqual((live.call_count, r2["cache"]["hit"]), (1, True))
        self.assertEqual(self.client.post("/api/corporate-registries/details", headers=self.h, json={"items": []}).status_code, 400)
        with tempfile.TemporaryDirectory() as d, mock.patch.object(self.app, "MASTER_PATH", os.path.join(d, "m.csv")):
            a = self.client.post("/api/corporate-registries/save", headers=self.h, json={"results": [row]}).get_json()
            b = self.client.post("/api/corporate-registries/save", headers=self.h, json={"results": [row]}).get_json()
            with open(os.path.join(d, "m.csv"), encoding="utf-8-sig") as fh:
                saved = list(csv.DictReader(fh))
        self.assertEqual((a["added"], b["added"]), (1, 0))
        self.assertEqual(saved[0]["source"], "Corporate Registries (ZaubaCorp / MCA)")


if __name__ == "__main__":
    unittest.main()

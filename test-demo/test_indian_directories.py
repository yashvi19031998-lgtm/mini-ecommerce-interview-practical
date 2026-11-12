"""Tests for Data Extraction -> Indian Directories (indian_directories.py), no network.

Pages are small hand-made copies of each portal's real structure (checked live on 2026-11-12).
python -m unittest test_indian_directories -v
"""
import json
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

import html_cache_manager as hcm
import indian_directories as idr

BASE = {"keywords": ["bakery products"], "state": "Gujarat", "city": "Ahmedabad", "sources": ["indiamart"]}


def indiamart_page(rows, related=()):
    state = {"data": rows, "relCat": [{"GLCAT_MCAT_NAME": r} for r in related]}
    return f"<html><script>window.__INITIAL_STATE__ = {json.dumps(state)};</script></html>"


IM_ROW = {"CMP": "Shyam Sunder Bakers", "c_ct": "8047763186", "g_cn": "vgFCPplus with PNS(G)", "city": "Ahmedabad",
          "ad": "Maninagar", "p_nm": "Jeera Khari Puff", "wt_avg": 4.5, "tr_c": 15, "gst_v": 1, "m_sn": "22 yrs",
          "s_url": "https://www.indiamart.com/delifresh-bakes/"}


def sulekha_page(n=2):
    items = [{"@type": "ListItem", "position": i + 1, "item": {
        "@type": "LocalBusiness", "name": f"Studio {i}", "description": '"We design"', "telephone": f"0953337692{i}",
        "address": {"addressLocality": "Satellite", "addressRegion": "Ahmedabad", "postalCode": "380015"},
        "url": f"https://www.sulekha.com/profile/studio-{i}"}} for i in range(n)]
    ld = {"@context": "https://schema.org", "@graph": [{"@type": "Organization", "name": "Sulekha.com"},
                                                       {"@type": "ItemList", "itemListElement": items}]}
    return f'<html><script type="application/ld+json">{json.dumps(ld)}</script></html>'


def tradeindia_page(rows, cities=()):
    m = {"listing_data": {"listing_data": rows}, "related_search_data": [{"keyword": "Frozen Bakery Products"}],
         "list_city_data": [{"city_name": c, "url": f"/{c.lower()}/bakery-products-city-1.html"} for c in cities]}
    nd = {"props": {"pageProps": {"initialState": {"manufacturer": {"manufacturer_page": {"manufacturer_page_res": {"mcatData": m}}}}}}}
    return f'<html><script id="__NEXT_DATA__" type="application/json">{json.dumps(nd)}</script></html>'


TI_ROW = {"co_name": "Shanti Food Industries", "city": "Sonipat", "state": "Haryana", "profile_url": "/shanti-food-6924703/",
          "business_type": "Distributor | Supplier", "estd": 2010, "std_cert": "ISO 9001:2015", "product_name": "Yeast",
          "number_mask": True, "has_trust_stamp": True, "member_since": 12}

EI_PAGE = """<ul class="l3ClasFlistNew list_view">
<li><div class="l3Inn"><div class="clsProDet"><div class="inDataH"><h2><a href="https://www.exportersindia.com/product-detail/cake-1.htm">Pineapple Cake</a></h2>
<div class="_price" data-tooltip="Price - Rs 500 Per Piece"></div></div></div>
<div class="com_address"><a class="com_nam" href="https://www.exportersindia.com/yashvi-foods/">Yashvi Foods</a>
<div class="_address">Maninagar, Ahmedabad, Gujarat</div> 10 Years</div></div></li>
<li><div class="inDataH"><h2><a href="#">No seller</a></h2></div></li>
</ul>"""


def mlm_payload(cards, more=False):
    html = "".join(f"""<div class="bg-white rounded-xl border border-slate-200 p-4">
<h3>{c[0]}</h3><p><i class="fa-solid fa-location-dot"></i><span>{c[1]}</span></p>
<p><i class="fa-solid fa-building"></i><span>{c[2]}</span></p>
<p><i class="fa-solid fa-diagram-project"></i><span>{c[3]}</span></p>
<a href="https://mlmdiary.com/person-1">View Profile</a></div>""" for c in cards)
    return json.dumps({"status": "success", "html": html, "has_more": more})


class FakeWeb:
    """hcm.fetch_page stand-in: url -> (status, text, final_url)."""

    def __init__(self, pages):
        self.pages, self.calls = pages, []

    def __call__(self, url, headers, guard, timeout=20, **kw):
        self.calls.append(url)
        status, text, final = self.pages.get(url, (404, "not found", url))
        return status, text, final, False


class Validation(unittest.TestCase):
    def test_rules(self):
        for over, msg in (({"keywords": []}, "at least one"), ({"city": "Ahm3d"}, "letters only"),
                          ({"state": "Atlantis"}, "unknown state"), ({"sources": []}, "at least one source"),
                          ({"sources": ["yellowpages"]}, "unknown source"), ({"sources": ["justdial"]}, "bot protection"),
                          ({"sources": ["sulekha"], "city": ""}, "enter a city"),
                          ({"keywords": ["a" * 81]}, "longer than")):
            with self.assertRaises(ValueError) as cm:
                idr.validate_request({**BASE, **over})
            self.assertIn(msg, str(cm.exception).lower(), over)

    def test_mlmdiary_needs_no_keyword(self):
        req = idr.validate_request({**BASE, "keywords": [], "sources": ["mlmdiary"], "city": ""})
        self.assertEqual((req["keywords"], req["sources"]), ([], ["mlmdiary"]))

    def test_catalog(self):
        cat = {s["id"]: s for s in idr.list_sources()}
        self.assertEqual(list(cat), ["indiamart", "justdial", "sulekha", "tradeindia", "exportersindia", "mlmdiary"])
        self.assertEqual(cat["justdial"]["status"], "unavailable")
        self.assertTrue(cat["sulekha"]["needsCity"])
        self.assertFalse(cat["mlmdiary"]["needsKeyword"])

    def test_slugs(self):
        self.assertEqual(idr.slugify("Packers & Movers"), "packers-and-movers")
        self.assertEqual(idr.slug_variants("bakery products"), ["bakery-products", "bakery-product"])
        self.assertEqual(idr.slug_variants("tutor"), ["tutor", "tutors", "tutor-services"])


class Parsers(unittest.TestCase):
    def test_indiamart(self):
        rows, related = idr.parse_indiamart(indiamart_page([IM_ROW, {"CMP": ""}], ["Bread & Buns"]), "bakery products")
        self.assertEqual(len(rows), 1)
        r = rows[0]
        self.assertEqual((r["company"], r["phone"], r["phone_note"]), ("Shyam Sunder Bakers", "08047763186", "IndiaMART call-forwarding number"))
        self.assertEqual((r["location"], r["verified"], r["since"]), ("Maninagar, Ahmedabad", "GST verified", "22 yrs"))
        self.assertEqual(related, ["Bread & Buns"])
        mobile = idr.parse_indiamart(indiamart_page([{**IM_ROW, "c_ct": "9876543210", "g_cn": ""}]), "x")[0][0]
        self.assertEqual((mobile["phone"], mobile["phone_note"]), ("9876543210", ""))
        ext = idr.parse_indiamart(indiamart_page([{**IM_ROW, "c_ct": "8047625603,5093"}]), "x")[0][0]   # seen live
        self.assertEqual((ext["phone"], ext["phone_ext"]), ("08047625603", "5093"))
        self.assertIn("extension 5093", ext["phone_note"])
        self.assertEqual(idr.parse_indiamart("<html>no state</html>", "x"), ([], []))

    def test_sulekha(self):
        rows = idr.parse_sulekha(sulekha_page(2), "interior")
        self.assertEqual(len(rows), 2)
        self.assertEqual((rows[0]["company"], rows[0]["phone"], rows[0]["location"], rows[0]["details"]),
                         ("Studio 0", "09533376920", "Satellite, Ahmedabad, 380015", "We design"))

    def test_tradeindia(self):
        rows, related, cities = idr.parse_tradeindia(tradeindia_page([TI_ROW], ["Delhi"]), "bakery")
        r = rows[0]
        self.assertEqual((r["company"], r["location"], r["phone"], r["phone_note"]),
                         ("Shanti Food Industries", "Sonipat, Haryana", "", "Hidden by TradeIndia"))
        self.assertEqual(r["url"], "https://www.tradeindia.com/shanti-food-6924703/")
        self.assertIn("Est. 2010", r["details"])
        self.assertEqual((related, list(cities)), (["Frozen Bakery Products"], ["delhi"]))

    def test_exportersindia(self):
        rows = idr.parse_exportersindia(EI_PAGE, "bakery")
        self.assertEqual(len(rows), 1)
        r = rows[0]
        self.assertEqual((r["company"], r["location"], r["since"], r["product"], r["phone"]),
                         ("Yashvi Foods", "Maninagar, Ahmedabad, Gujarat", "10 yrs", "Pineapple Cake", ""))

    def test_mlmdiary_companies_only_no_person_names(self):
        payload = mlm_payload([("Ramesh Patel", "Pune, Maharashtra, India", "Zenvex", "Binary Plan, Royalty Plan"),
                               ("Sita Shah", "Surat, Gujarat, India", "ZENVEX", "Level Plan"),
                               ("Arun K", "Pune, Maharashtra, India", "1 World Network", "Binary Plan"),
                               ("No Company", "Delhi", "-", "")], more=True)
        cards, more = idr.parse_mlmdiary(payload)
        self.assertTrue(more)
        rows = idr.aggregate_mlm(cards)
        self.assertEqual([(r["company"], r["members"]) for r in rows], [("Zenvex", 2), ("1 World Network", 1)])
        self.assertEqual(rows[0]["location"], "Pune, Surat")
        dump = json.dumps(rows)
        for person in ("Ramesh", "Sita", "Arun", "person-1"):
            self.assertNotIn(person, dump)
        self.assertEqual(idr.parse_mlmdiary("not json"), ([], False))


class Runs(unittest.TestCase):
    def setUp(self):
        self.sleeps = []

    def run_source(self, sid, pages, **over):
        web = FakeWeb(pages)
        req = idr.validate_request({**BASE, "sources": [sid], **over})
        with mock.patch.object(idr.hcm, "fetch_page", web):
            out = idr._run_source(sid, req, sleep=self.sleeps.append)
        return out, web

    def test_wrong_category_tries_variants_then_explains(self):
        out, web = self.run_source("indiamart", {}, keywords=["tutor"])
        self.assertEqual(web.calls, ["https://dir.indiamart.com/ahmedabad/tutor.html", "https://dir.indiamart.com/ahmedabad/tutors.html",
                                     "https://dir.indiamart.com/ahmedabad/tutor-services.html"])
        self.assertEqual(out["status"], "error")
        self.assertIn("no category page named 'tutor'", out["errors"][0])

    def test_second_spelling_works_and_pauses_between_requests(self):
        url = "https://dir.indiamart.com/ahmedabad/bakery-product.html"
        out, web = self.run_source("indiamart", {url: (200, indiamart_page([IM_ROW]), url)})
        self.assertEqual((out["status"], len(out["rows"]), out["requests"]), ("ok", 1, 2))
        self.assertEqual(len(self.sleeps), 1)

    def test_all_india_page_without_city(self):
        url = "https://dir.indiamart.com/impcat/bakery-products.html"
        out, _ = self.run_source("indiamart", {url: (200, indiamart_page([IM_ROW]), url)}, city="", state="All India")
        self.assertEqual(len(out["rows"]), 1)

    def test_tradeindia_redirect_is_not_found_and_city_page_used(self):
        cat = "https://www.tradeindia.com/manufacturers/bakery-products.html"
        city = "https://www.tradeindia.com/ahmedabad/bakery-products-city-1.html"
        local = {**TI_ROW, "co_name": "Ahmedabad Bakes", "city": "Ahmedabad", "state": "Gujarat"}
        pages = {cat: (200, tradeindia_page([TI_ROW], ["Ahmedabad"]), cat), city: (200, tradeindia_page([local]), city),
                 "https://www.tradeindia.com/manufacturers/tutors.html": (200, "<html>generic</html>", "https://www.tradeindia.com/manufacturers/")}
        out, _ = self.run_source("tradeindia", pages)
        self.assertEqual([r["company"] for r in out["rows"]], ["Ahmedabad Bakes"])
        out, _ = self.run_source("tradeindia", pages, keywords=["tutors"])
        self.assertIn("no category page", out["errors"][0])

    def test_sulekha_second_page(self):
        base = "https://www.sulekha.com/interior-designers/ahmedabad"
        p1 = json.loads(sulekha_page(20).split('json">')[1].split("</script>")[0])
        page2 = sulekha_page(3).replace("studio-", "other-").replace("Studio ", "Other ")
        out, web = self.run_source("sulekha", {base: (200, sulekha_page(20), base), f"{base}?page=2": (200, page2, base)},
                                   keywords=["interior designers"])
        self.assertTrue(p1)
        self.assertEqual(len(out["rows"]), 23)

    def test_exportersindia_state_filter_on_all_india_page(self):
        url = "https://www.exportersindia.com/indian-suppliers/bakery-products.htm"
        out, _ = self.run_source("exportersindia", {url: (200, EI_PAGE, url)}, city="", state="Kerala")
        self.assertEqual(out["rows"], [])
        out, _ = self.run_source("exportersindia", {url: (200, EI_PAGE, url)}, city="", state="Gujarat")
        self.assertEqual(len(out["rows"]), 1)

    def test_mlmdiary_pages_and_crawl_delay(self):
        u = "https://mlmdiary.com/directory?country=India&state=Gujarat&page={}"
        pages = {u.format(1): (200, mlm_payload([("A", "Surat", "Zenvex", "Binary")], more=True), u.format(1)),
                 u.format(2): (200, mlm_payload([("B", "Rajkot", "Vestige", "Level")]), u.format(2))}
        out, web = self.run_source("mlmdiary", pages, keywords=[], city="")
        self.assertEqual(sorted(r["company"] for r in out["rows"]), ["Vestige", "Zenvex"])
        self.assertEqual(len(web.calls), 2)
        self.assertTrue(self.sleeps and self.sleeps[0] > 4)        # robots.txt crawl-delay 5 s
        out, _ = self.run_source("mlmdiary", pages, keywords=["vestige"], city="")
        self.assertEqual([r["company"] for r in out["rows"]], ["Vestige"])

    def test_network_error_is_isolated(self):
        def boom(*a, **k):
            raise idr.requests.ConnectionError()
        req = idr.validate_request(BASE)
        with mock.patch.object(idr.hcm, "fetch_page", boom):
            out = idr._run_source("indiamart", req, sleep=lambda s: None)
        self.assertEqual(out["status"], "error")
        self.assertIn("could not reach IndiaMART", out["errors"][0])


class SearchAndLeads(unittest.TestCase):
    def test_merge_keywords_audience_and_sort(self):
        def fake(sid, req, sleep):
            a = idr.make_result("indiamart", company="Acme Foods", location="Ahmedabad", product="Cake", url="u1")
            b = idr.make_result("indiamart", company="ACME FOODS", location="Ahmedabad", product="Bread", url="u1", phone="0801")
            c = idr.make_result("indiamart", company="Zed Pharma", location="Ahmedabad", product="Pills", url="u2", phone="0802")
            return {"rows": [a, b, c], "status": "ok", "errors": [], "seconds": 0, "requests": 1}
        with mock.patch.object(idr, "_run_source", side_effect=fake):
            res = idr.search({**BASE, "keywords": ["cake", "bread"]})
        self.assertEqual([(r["company"], r["product"], r["phone"]) for r in res["results"]],
                         [("Acme Foods", "Cake; Bread", "0801"), ("Zed Pharma", "Pills", "0802")])

    def test_audience_filter(self):
        url = "https://dir.indiamart.com/ahmedabad/bakery-products.html"
        rows = [IM_ROW, {**IM_ROW, "CMP": "Pharma Co", "p_nm": "Tablets", "ds": "pharma"}]
        with mock.patch.object(idr.hcm, "fetch_page", FakeWeb({url: (200, indiamart_page(rows), url)})):
            out = idr._run_source("indiamart", idr.validate_request({**BASE, "audience": ["Pharma"]}), sleep=lambda s: None)
        self.assertEqual([r["company"] for r in out["rows"]], ["Pharma Co"])

    def test_lead_mapping(self):
        r = idr.make_result("tradeindia", company="Acme", url="https://www.tradeindia.com/acme-1/", website="https://www.tradeindia.com/acme-1/",
                            location="Surat, Gujarat", product="Yeast", phone_note="Hidden by TradeIndia")
        lead = idr.result_to_raw_lead(r)
        phoned = idr.result_to_raw_lead(idr.make_result("sulekha", company="Studio", url="https://www.sulekha.com/profile/s", phone="09533376923"))
        self.assertEqual(phoned["mobile_number"], "09533376923")        # the key MasterLeadRegistry reads
        self.assertEqual((lead["website"], lead["source"], lead["source_url"]),
                         ("", "Indian Directories (TradeIndia)", "https://www.tradeindia.com/acme-1/"))
        self.assertIn("Product: Yeast", lead["description"])
        mlm = idr.result_to_raw_lead(idr.make_result("mlmdiary", company="Zenvex", url="https://mlmdiary.com/directory?company=Zenvex"))
        self.assertEqual(mlm["lead_type"], "MLM Company")


class FetchPage(unittest.TestCase):
    def test_redirected_page_not_cached(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(hcm, "CACHE_DIR", d), \
                mock.patch.object(hcm, "_index_add"), \
                mock.patch.object(hcm, "_guarded_get", return_value=(200, "x" * 30000, "https://a.in/other")):
            st, _, final, cached = hcm.fetch_page("https://a.in/page", {}, lambda u: None)
            self.assertEqual((st, final, cached, os.listdir(d)), (200, "https://a.in/other", False, []))
        with tempfile.TemporaryDirectory() as d, mock.patch.object(hcm, "CACHE_DIR", d), \
                mock.patch.object(hcm, "_index_add"), \
                mock.patch.object(hcm, "_guarded_get", return_value=(200, "y" * 30000, "https://a.in/page")) as g:
            hcm.fetch_page("https://a.in/page", {}, lambda u: None)
            st, text, _, cached = hcm.fetch_page("https://a.in/page", {}, lambda u: None)
            self.assertEqual((g.call_count, cached, text[:1]), (1, True, "y"))


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
        for m, u in (("get", "/api/indian-directories"), ("post", "/api/indian-directories/search"),
                     ("post", "/api/indian-directories/save")):
            self.assertEqual(getattr(self.client, m)(u).status_code, 401, u)
        cat = self.client.get("/api/indian-directories", headers=self.h).get_json()
        self.assertEqual(len(cat["sources"]), 6)
        self.assertEqual(self.client.post("/api/indian-directories/search", headers=self.h,
                                          json={**BASE, "sources": ["justdial"]}).status_code, 400)
        row = idr.make_result("indiamart", company="Acme Bakers", url="https://www.indiamart.com/acme/", phone="08047763186")
        fake = {"query": {}, "results": [row], "total": 1,
                "sources": {"indiamart": {"name": "IndiaMART", "status": "ok", "count": 1, "seconds": 1, "errors": []}}}
        with mock.patch.object(idr, "search", return_value=fake) as live:
            self.client.post("/api/indian-directories/search", headers=self.h, json=BASE)
            r2 = self.client.post("/api/indian-directories/search", headers=self.h, json=BASE).get_json()
        self.assertEqual((live.call_count, r2["cache"]["hit"]), (1, True))
        with tempfile.TemporaryDirectory() as d, mock.patch.object(self.app, "MASTER_PATH", os.path.join(d, "m.csv")):
            a = self.client.post("/api/indian-directories/save", headers=self.h, json={"results": [row]}).get_json()
            b = self.client.post("/api/indian-directories/save", headers=self.h, json={"results": [row]}).get_json()
            import csv
            with open(os.path.join(d, "m.csv"), encoding="utf-8-sig") as fh:
                saved = list(csv.DictReader(fh))
        self.assertEqual((a["added"], b["added"]), (1, 0))
        self.assertEqual(saved[0]["mobile_number"], "+91 80477 63186")  # phone really reaches the leads file

    def test_trunk_zero_numbers_are_kept(self):
        import lead_normalizer as ln
        self.assertEqual(ln.normalize_phone("09533376923"), "+91 95333 76923")      # Sulekha style
        self.assertEqual(ln.normalize_phone("02225551234"), "+91 2225551234")       # Mumbai landline
        self.assertEqual(ln.normalize_phone("07926543210"), "079-26543210")         # Ahmedabad (unchanged)
        self.assertEqual(ln.normalize_phone("9533376923"), "+91 95333 76923")       # unchanged
        self.assertEqual(ln.normalize_phone("00000000000"), "")


if __name__ == "__main__":
    unittest.main()

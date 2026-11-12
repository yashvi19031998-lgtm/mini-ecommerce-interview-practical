"""Tests for Scraping / Mining -> Ecommerce Platforms (ecommerce_sources.py), no network.

python -m unittest test_ecommerce_sources -v
"""
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

import requests

import ecommerce_sources as es
import html_cache_manager as hcm
import search_engine

BASE = {
    "keywords": ["organic tea"],
    "state": "Gujarat",
    "city": "Ahmedabad",
    "sources": ["shopify"],
    "engine": "duckduckgo",
}


def make_raw(title="Store Title", url="https://store.myshopify.com", snippet="Call us at +91 98250 12345 or email info@store.com"):
    return {"title": title, "url": url, "snippet": snippet}


def resp(status, payload, text=""):
    return SimpleNamespace(status_code=status, text=text, json=lambda: payload, raise_for_status=lambda: None)


class Catalog(unittest.TestCase):
    def test_sources_list(self):
        sources = es.list_sources()
        sids = {s["id"] for s in sources}
        self.assertIn("shopify", sids)
        self.assertIn("woocommerce", sids)
        self.assertIn("instagram_shops", sids)
        self.assertIn("amazon_in", sids)
        self.assertIn("flipkart", sids)
        self.assertIn("meesho", sids)

        for s in sources:
            if s["id"] in ("shopify", "woocommerce", "instagram_shops"):
                self.assertEqual(s["status"], "available")
                self.assertEqual(s["kind"], "store_platform")
            else:
                self.assertEqual(s["status"], "unavailable")
                self.assertEqual(s["kind"], "marketplace")
                self.assertTrue(s["reason"])


class Validation(unittest.TestCase):
    def bad(self, msg, **over):
        with self.assertRaises(ValueError) as cm:
            es.validate_request({**BASE, **over})
        self.assertIn(msg.lower(), str(cm.exception).lower())

    def test_ok_and_defaults(self):
        r = es.validate_request({
            **BASE,
            "keywords": [" Organic Tea ", "organic tea", "chai"],
            "sources": ["shopify", "shopify"],
            "engine": "duckduckgo"
        })
        self.assertEqual(r["keywords"], ["Organic Tea", "chai"])
        self.assertEqual(r["sources"], ["shopify"])
        self.assertEqual(r["engine_used"], "duckduckgo")

    def test_rejections(self):
        self.bad("at least one product or category", keywords=[])
        self.bad("at most 5", keywords=[f"k{i}" for i in range(6)])
        self.bad("longer than 80", keywords=["x" * 81])
        self.bad("double quotes", keywords=['tea"cup'])
        self.bad("select a state", state="")
        self.bad("unknown state", state="Narnia")
        self.bad("letters only", city="Ahmedabad123")
        self.bad("at least one source", sources=[])
        self.bad("unknown source", sources=["etsy"])
        self.bad("not available", sources=["amazon_in"])
        self.bad("unknown search engine", engine="yandex")
        self.bad("target audience", audience=["y" * 61])

    def test_engine_needing_key(self):
        with mock.patch.dict(os.environ, {"BRAVE_SEARCH_API_KEY": ""}):
            self.bad("needs brave_search_api_key", engine="brave")


class QueryBuildingAndExecution(unittest.TestCase):
    def test_query_building_and_filtering(self):
        calls = []

        def mock_engine(query, count, tf, session):
            calls.append(query)
            if "myshopify.com" in query:
                return [
                    make_raw("Valid Store", "https://valid.myshopify.com", "Contact: info@valid.com"),
                    make_raw("Junk Result", "https://wikipedia.org/wiki/Tea", "info"),
                    make_raw("Top 10 Stores in Ahmedabad", "https://blog.myshopify.com/list", "list"),
                    make_raw("Off Target", "https://otherdomain.com/page", "not myshopify"),
                ]
            elif "powered by Shopify" in query:
                return [
                    make_raw("Custom Domain Shopify", "https://customtea.in", "Tea shop"),
                    make_raw("Social Link", "https://facebook.com/customtea", "social"),
                ]
            return []

        funcs = {"duckduckgo": mock_engine}
        with mock.patch.dict(search_engine.ENGINE_FUNCS, funcs), \
                mock.patch.object(es.time, "sleep"), \
                mock.patch("deep_search.public_url_guard"):
            res = es.search({**BASE, "sources": ["shopify"]})

        self.assertEqual(len(calls), 2)
        self.assertIn('site:myshopify.com "organic tea"', calls[0])
        self.assertIn('"organic tea" "powered by Shopify" Ahmedabad', calls[1])

        # Filtered out Junk, Article, Off-target, and Platform domain
        companies = [r["company"] for r in res["results"]]
        self.assertIn("Valid Store", companies)
        self.assertIn("Custom Domain Shopify", companies)
        self.assertNotIn("Junk Result", companies)
        self.assertNotIn("Top 10 Stores in Ahmedabad", companies)
        self.assertNotIn("Off Target", companies)
        self.assertNotIn("Social Link", companies)

    def test_woocommerce_queries(self):
        calls = []

        def mock_engine(query, count, tf, session):
            calls.append(query)
            return [make_raw("Woo Store", "https://woostore.in/product-category/tea", "organic tea")]

        funcs = {"duckduckgo": mock_engine}
        with mock.patch.dict(search_engine.ENGINE_FUNCS, funcs), mock.patch.object(es.time, "sleep"):
            res = es.search({**BASE, "sources": ["woocommerce"]})

        self.assertEqual(len(calls), 2)
        self.assertIn('"organic tea" "add to cart" "woocommerce" Ahmedabad', calls[0])
        self.assertIn('"organic tea" inurl:product-category Ahmedabad', calls[1])
        self.assertEqual(res["results"][0]["platform"], "WooCommerce")

    def test_instagram_profile_filtering(self):
        def mock_engine(query, count, tf, session):
            return [
                make_raw("Tea Boutique (@teaboutique)", "https://www.instagram.com/teaboutique/", "DM to order"),
                make_raw("Post Link", "https://www.instagram.com/p/Cxyz123/", "Nice tea"),
                make_raw("Reel Link", "https://www.instagram.com/reel/Cabc789/", "Reel video"),
                make_raw("Explore Link", "https://www.instagram.com/explore/tags/tea/", "Tags"),
            ]

        funcs = {"duckduckgo": mock_engine}
        with mock.patch.dict(search_engine.ENGINE_FUNCS, funcs), mock.patch.object(es.time, "sleep"):
            res = es.search({**BASE, "sources": ["instagram_shops"]})

        self.assertEqual(len(res["results"]), 1)
        r = res["results"][0]
        self.assertEqual(r["platform"], "Instagram")
        self.assertEqual(r["url"], "https://www.instagram.com/teaboutique/")
        self.assertEqual(r["instagram"], "https://www.instagram.com/teaboutique/")
        self.assertEqual(r["website"], "")


class DeduplicationAndAudience(unittest.TestCase):
    def test_dedupe_merges_missing_contact_fields(self):
        # Two results for same store domain: first has website and phone; second has email and instagram
        items = [
            {"title": "Herbal Tea Co", "url": "https://herbaltea.in", "snippet": "Phone: +91 98250 11111"},
            {"title": "Herbal Tea Online", "url": "https://herbaltea.in/about", "snippet": "Email: support@herbaltea.in"},
        ]

        def mock_engine(query, count, tf, session):
            return items

        funcs = {"duckduckgo": mock_engine}
        with mock.patch.dict(search_engine.ENGINE_FUNCS, funcs), mock.patch.object(es.time, "sleep"):
            res = es.search({**BASE, "sources": ["woocommerce"]})

        self.assertEqual(len(res["results"]), 1)
        r = res["results"][0]
        self.assertIn("+91 98250 11111", r["phone"])
        self.assertIn("support@herbaltea.in", r["email"])

    def test_audience_word_matching_and_fallback(self):
        items = [
            {"title": "Ayurveda Wellness Teas", "url": "https://ayurtea.in", "snippet": "Holistic health & wellness drinks"},
            {"title": "Urban Modern Cafe", "url": "https://urbantea.in", "snippet": "Trendy lifestyle teas"},
        ]

        def mock_engine(query, count, tf, session):
            return items

        funcs = {"duckduckgo": mock_engine}
        with mock.patch.dict(search_engine.ENGINE_FUNCS, funcs), mock.patch.object(es.time, "sleep"):
            # "Health & Wellness" matches "wellness" by word
            r1 = es.search({**BASE, "audience": ["Health & Wellness"]})
            self.assertEqual(len(r1["results"]), 1)
            self.assertEqual(r1["results"][0]["company"], "Ayurveda Wellness Teas")

            # "Nonexistent Audience" matches nothing -> fallback keeps all results with a note
            r2 = es.search({**BASE, "audience": ["Automotive Engineering"]})
            self.assertEqual(len(r2["results"]), 2)
            self.assertIn("target audience", r2["sources"]["shopify"]["errors"][0])


class ResilienceAndShopifyVerify(unittest.TestCase):
    def test_rate_limit_keeps_partial_results(self):
        call_count = [0]

        def mock_engine(query, count, tf, session):
            call_count[0] += 1
            if call_count[0] == 1:
                return [make_raw("First Store", "https://first.myshopify.com", "info@first.com")]
            raise search_engine.RateLimited("slow down")

        funcs = {"duckduckgo": mock_engine}
        with mock.patch.dict(search_engine.ENGINE_FUNCS, funcs), mock.patch.object(es.time, "sleep"):
            res = es.search({**BASE, "sources": ["shopify"]})

        self.assertEqual(len(res["results"]), 1)
        self.assertEqual(res["sources"]["shopify"]["status"], "ok")
        self.assertTrue(any("slow down" in e for e in res["sources"]["shopify"]["errors"]))

    def test_source_exception_does_not_crash_other_sources(self):
        def broken_engine(query, count, tf, session):
            if "myshopify" in query:
                raise AttributeError("unexpected failure")
            return [make_raw("Woo Store", "https://woo.in", "phone: +91 98250 22222")]

        funcs = {"duckduckgo": broken_engine}
        with mock.patch.dict(search_engine.ENGINE_FUNCS, funcs), mock.patch.object(es.time, "sleep"):
            res = es.search({**BASE, "sources": ["shopify", "woocommerce"]})

        self.assertEqual(res["sources"]["shopify"]["status"], "error")
        self.assertIn("AttributeError", res["sources"]["shopify"]["errors"][0])
        self.assertEqual(res["sources"]["woocommerce"]["status"], "ok")
        self.assertEqual(len(res["results"]), 1)

    def test_shopify_verification_limit_and_non_json(self):
        # 20 distinct stores
        items = [make_raw(f"Store {i}", f"https://store{i}.myshopify.com", "") for i in range(20)]
        funcs = {"duckduckgo": lambda *a: items}

        req_count = [0]
        seen_headers = []

        # (reviewed 2026-11-12) verification goes through the guarded GET, not session.get
        def fake_guarded_get(url, headers, timeout, guard, max_bytes):
            req_count[0] += 1
            seen_headers.append(headers)
            if req_count[0] == 1:
                return 200, '{"products": [{"id": 1, "title": "Tea"}]}', url   # valid JSON
            if req_count[0] == 2:
                return 200, "<html>Not json</html>", url                       # non-JSON answer
            return 404, "", url

        with mock.patch.dict(search_engine.ENGINE_FUNCS, funcs), \
                mock.patch.object(es.hcm, "_guarded_get", side_effect=fake_guarded_get), \
                mock.patch.object(es.time, "sleep"):
            res = es.search({**BASE, "sources": ["shopify"]})

        # Maximum 15 verification calls made, never with a browser-impersonating User-Agent
        self.assertLessEqual(req_count[0], 15)
        self.assertTrue(all("Windows NT" not in h.get("User-Agent", "") for h in seen_headers))
        # First one verified
        verified = [r for r in res["results"] if r.get("details") == "Shopify store verified"]
        self.assertEqual(len(verified), 1)


class Leads(unittest.TestCase):
    def test_result_to_raw_lead(self):
        r = es.make_result(
            "shopify",
            source="Shopify stores",
            company="Organic Herbal Tea",
            email="owner@herbaltea.in",
            phone="+91 98250 12345",
            website="https://herbaltea.in",
            location="Ahmedabad",
            category="organic tea",
            platform="Shopify",
            url="https://herbaltea.in",
            details="Shopify store verified",
            instagram="https://instagram.com/herbaltea",
            facebook="https://facebook.com/herbaltea",
        )
        lead = es.result_to_raw_lead(r)
        self.assertEqual(lead["lead_type"], "Ecommerce Store")
        self.assertEqual(lead["company_name"], "Organic Herbal Tea")
        self.assertEqual(lead["source"], "Ecommerce (Shopify stores)")
        self.assertIn("Platform: Shopify", lead["description"])
        self.assertIn("Instagram: https://instagram.com/herbaltea", lead["description"])


class Api(unittest.TestCase):
    def setUp(self):
        import app as app_module
        self.app = app_module
        self.client = app_module.app.test_client()
        ok = SimpleNamespace(status_code=200, json=lambda: {"email": "owner@example.com"})
        self.tmp = tempfile.TemporaryDirectory()
        self.p = [
            mock.patch("api_auth.requests.get", return_value=ok),
            mock.patch("api_auth.ALLOWED_EMAILS", set()),
            mock.patch.object(hcm, "CACHE_DIR", self.tmp.name),
        ]
        for x in self.p:
            x.start()
        self.h = {"Authorization": "Bearer t"}

    def tearDown(self):
        for x in self.p:
            x.stop()
        self.tmp.cleanup()

    def test_login_required(self):
        for m, u in (("get", "/api/ecommerce"), ("post", "/api/ecommerce/search"), ("post", "/api/ecommerce/save")):
            self.assertEqual(getattr(self.client, m)(u).status_code, 401, u)

    def test_catalog_search_cache_save(self):
        # Catalog
        cat = self.client.get("/api/ecommerce", headers=self.h).get_json()
        self.assertTrue(cat["success"])
        self.assertEqual(cat["states"][0], "All India")
        self.assertEqual(cat["maxKeywords"], 5)

        # 400 on bad input
        self.assertEqual(
            self.client.post("/api/ecommerce/search", headers=self.h, json={**BASE, "keywords": []}).status_code,
            400
        )

        fake_res = {
            "query": BASE,
            "results": [es.make_result("shopify", company="Chai Store", email="tea@chai.com", website="https://chai.in")],
            "total": 1,
            "sources": {"shopify": {"name": "Shopify stores", "status": "ok", "count": 1, "seconds": 0.5, "errors": []}},
            "engine": "duckduckgo",
            "hint": "",
        }

        # Search cached on second call
        with mock.patch.object(es, "search", return_value=fake_res) as mock_search:
            r1 = self.client.post("/api/ecommerce/search", headers=self.h, json=BASE).get_json()
            r2 = self.client.post("/api/ecommerce/search", headers=self.h, json=BASE).get_json()

        self.assertEqual(mock_search.call_count, 1)
        self.assertEqual(r1["cache"]["hit"], False)
        self.assertEqual(r2["cache"]["hit"], True)
        self.assertIn("in_leads", r2["results"][0])

        # Save endpoint
        self.assertEqual(self.client.post("/api/ecommerce/save", headers=self.h, json={"results": []}).status_code, 400)

        with tempfile.TemporaryDirectory() as d, mock.patch.object(self.app, "MASTER_PATH", os.path.join(d, "m.csv")):
            item = es.make_result("shopify", company="Chai Store", email="tea@chai.com", website="https://chai.in")
            s1 = self.client.post("/api/ecommerce/save", headers=self.h, json={"results": [item]}).get_json()
            s2 = self.client.post("/api/ecommerce/save", headers=self.h, json={"results": [item]}).get_json()

        self.assertEqual(s1["added"], 1)
        self.assertEqual(s2["added"], 0)
        self.assertEqual(s2["duplicate"], 1)


class ReviewFixes(unittest.TestCase):
    """Code review 2026-11-12."""

    def test_shopify_verification_is_guarded_on_every_redirect(self):
        hops = [mock.Mock(is_redirect=True, headers={"Location": "http://127.0.0.1/admin"}, close=lambda: None)]
        seen = []

        def guard(u):
            seen.append(u)
            if "127.0.0.1" in u:
                raise es.hcm.BlockedUrl("private")
        with mock.patch.object(es.deep_search, "public_url_guard", side_effect=guard),                 mock.patch.object(es.hcm.requests, "get", side_effect=hops):
            self.assertFalse(es._verify_shopify("evil-store.com"))
        self.assertEqual(seen, ["https://evil-store.com/products.json?limit=1", "http://127.0.0.1/admin"])

    def test_shopify_verification_rejects_odd_domains(self):
        with mock.patch.object(es.hcm, "_guarded_get") as g:
            self.assertFalse(es._verify_shopify("localhost:5000"))
            self.assertFalse(es._verify_shopify(""))
        g.assert_not_called()


    def test_shopify_429_stops_further_verification(self):
        items = [make_raw(f"Store {i}", f"https://store{i}.myshopify.com", "") for i in range(10)]
        calls = []

        def blocked(url, headers, timeout, guard, max_bytes):
            calls.append(url)
            return 429, "local_rate_limited", url
        with mock.patch.dict(search_engine.ENGINE_FUNCS, {"duckduckgo": lambda *a: items}),                 mock.patch.object(es.hcm, "_guarded_get", side_effect=blocked), mock.patch.object(es.time, "sleep"):
            res = es.search({**BASE, "sources": ["shopify"]})
        self.assertEqual(len(calls), 1, "after the first 429 no more verification requests are sent")
        self.assertGreater(res["total"], 0)


if __name__ == "__main__":
    unittest.main()


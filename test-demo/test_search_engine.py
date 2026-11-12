"""Tests for Scraping / Mining -> Search Engines + Deep Search (no network).

python -m unittest test_search_engine -v
"""
import os
import socket
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

import deep_search as ds
import html_cache_manager as hcm
import search_engine as se

BASE = {"keywords": ["software company"], "mode": "companies", "state": "Gujarat", "city": "Ahmedabad",
        "engine": "duckduckgo", "time": "any", "max_results": 25}


def resp(status=200, payload=None, text="", headers=None):
    return SimpleNamespace(status_code=status, json=lambda: payload, text=text, headers=headers or {},
                           raise_for_status=lambda: None)


def public_dns(host, *a, **k):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]


class Validation(unittest.TestCase):
    def ok(self, **over):
        return se.validate_request({**BASE, **over})

    def bad(self, msg, **over):
        with self.assertRaises(ValueError) as cm:
            se.validate_request({**BASE, **over})
        self.assertIn(msg.lower(), str(cm.exception).lower())

    def test_valid_request_is_normalized(self):
        r = self.ok(keywords=["  software   company ", "Software Company", "CA firm"], exclude_sites=["https://www.JustDial.com/"])
        self.assertEqual(r["keywords"], ["software company", "CA firm"])
        self.assertEqual(r["exclude_sites"], ["justdial.com"])
        self.assertEqual(r["engine_used"], "duckduckgo")

    def test_rejections(self):
        self.bad("at least one keyword", keywords=[])
        self.bad("at least one keyword", keywords="software")
        self.bad("at most 5", keywords=[f"k{i}" for i in range(6)])
        self.bad("longer than 80", keywords=["x" * 81])
        self.bad("double quotes", keywords=['soft"ware'])
        self.bad("unknown search mode", mode="hack")
        self.bad("custom query", mode="custom", custom_query="  ")
        self.bad("longer than 300", mode="custom", custom_query="x" * 301)
        self.bad("unknown state", state="Narnia")
        self.bad("letters only", city="Ahm3dabad")
        self.bad("unknown search engine", engine="yahoo")
        self.bad("unknown time", time="decade")
        self.bad("max results", max_results=7)
        self.bad("not a website", exclude_sites=["not a site"])
        self.bad("at most 10", exclude_sites=[f"s{i}.com" for i in range(11)])

    def test_keyed_engine_needs_key(self):
        with mock.patch.dict(os.environ, {"BRAVE_SEARCH_API_KEY": "", "SERPER_API_KEY": "", "SEARXNG_URL": ""}):
            self.bad("BRAVE_SEARCH_API_KEY", engine="brave")
            self.bad("SEARXNG_URL", engine="searxng")
            self.assertEqual(se.resolve_engine("auto"), "duckduckgo")
        with mock.patch.dict(os.environ, {"BRAVE_SEARCH_API_KEY": "", "SERPER_API_KEY": "", "SEARXNG_URL": "http://localhost:8888"}):
            self.assertEqual(se.resolve_engine("auto"), "searxng")
        with mock.patch.dict(os.environ, {"BRAVE_SEARCH_API_KEY": "", "SERPER_API_KEY": "k"}):
            self.assertEqual(se.resolve_engine("auto"), "serper")
        with mock.patch.dict(os.environ, {"BRAVE_SEARCH_API_KEY": "k", "SERPER_API_KEY": "k"}):
            self.assertEqual(se.resolve_engine("auto"), "brave")
            self.assertEqual(self.ok(engine="auto")["engine_used"], "brave")


class Queries(unittest.TestCase):
    def test_templates_place_and_excludes(self):
        req = se.validate_request({**BASE, "mode": "b2b", "exclude_sites": ["justdial.com"]})
        qs = [q["query"] for q in se.build_queries(req)]
        self.assertEqual(len(qs), 3)
        self.assertTrue(qs[0].startswith('site:indiamart.com "software company" Ahmedabad'))
        self.assertTrue(all(q.endswith("-site:justdial.com") for q in qs))

    def test_target_audience_or_group(self):
        req = se.validate_request({**BASE, "audience": ["IT / Software", "Real Estate", "real estate", "Startups"],
                                   "exclude_sites": ["justdial.com"]})
        self.assertEqual(req["audience"], ["IT / Software", "Real Estate", "Startups"])
        q = se.build_queries(req)[0]["query"]
        self.assertIn('("IT Software" OR "Real Estate" OR Startups)', q)
        self.assertTrue(q.endswith("-site:justdial.com"))
        one = se.build_queries(se.validate_request({**BASE, "audience": ["Manufacturing"]}))[0]["query"]
        self.assertTrue(one.endswith(" Manufacturing"))
        self.assertNotIn("(", se.build_queries(se.validate_request(BASE))[0]["query"])

    def test_target_audience_rejections(self):
        for bad, msg in ((["a"] * 1 + [f"x{i}" for i in range(5)], "at most 5"), (["y" * 61], "longer than 60"),
                         (['"quoted"'], "double quotes"), ("Manufacturing", "must be a list")):
            with self.assertRaises(ValueError) as cm:
                se.validate_request({**BASE, "audience": bad})
            self.assertIn(msg, str(cm.exception))

    def test_place_falls_back_to_state_then_india(self):
        self.assertEqual(se.place_text("Gujarat", ""), "Gujarat")
        self.assertEqual(se.place_text("All India", ""), "India")

    def test_custom_placeholders(self):
        req = se.validate_request({**BASE, "mode": "custom", "keywords": ["a", "b"],
                                   "custom_query": '"{keyword}" {city} "contact us"'})
        self.assertEqual([q["query"] for q in se.build_queries(req)],
                         ['"a" Ahmedabad "contact us"', '"b" Ahmedabad "contact us"'])

    def test_every_mode_builds_queries(self):
        for mode in se.MODES:
            extra = {"custom_query": "x {keyword}"} if mode == "custom" else {}
            self.assertTrue(se.build_queries(se.validate_request({**BASE, "mode": mode, **extra})), mode)

    def test_site_operator_filter(self):
        sites = se.required_sites('site:linkedin.com/company "x" -site:justdial.com')
        self.assertEqual(sites, [("linkedin.com", "/company")])
        self.assertTrue(se.matches_required("https://in.linkedin.com/company/acme", sites))
        self.assertFalse(se.matches_required("https://linkedin.com/in/person", sites))
        self.assertFalse(se.matches_required("https://deepmind.google/x", sites))
        self.assertTrue(se.matches_required("https://anything.com", []))


class Search(unittest.TestCase):
    def run_search(self, fake, data=None, master=""):
        with mock.patch.dict(se.ENGINE_FUNCS, {"duckduckgo": fake}):
            return se.search({**BASE, **(data or {})}, master_path=master, sleep=lambda s: None)

    def test_dedupe_junk_platform_and_snippet_contacts(self):
        def fake(q, n, t, s):
            return [
                {"title": "Acme Infotech | Home", "url": "https://acme.in/", "snippet": "Call +91 98250 12345 or info@acme.in"},
                {"title": "Acme services", "url": "https://acme.in/services", "snippet": ""},   # same domain
                {"title": "Software - Wikipedia", "url": "https://en.wikipedia.org/wiki/Software", "snippet": ""},
                {"title": "Beta Soft - LinkedIn", "url": "https://in.linkedin.com/company/beta", "snippet": ""},
                {"title": "bad", "url": "javascript:alert(1)", "snippet": ""},
            ]
        r = self.run_search(fake)
        self.assertEqual([x["domain"] for x in r["results"]], ["acme.in", "in.linkedin.com"])
        acme, beta = r["results"]
        self.assertEqual((acme["company"], acme["email"], acme["phone"]), ("Acme Infotech", "info@acme.in", "+91 98250 12345"))
        self.assertEqual((beta["kind"], beta["website"], beta["company"]), ("listing", "", "Beta Soft"))
        self.assertEqual(r["engines"]["duckduckgo"]["status"], "ok")

    def test_list_articles_and_junk(self):
        fake = lambda q, n, t, s: [
            {"title": "Top 11 IT Companies in Ahmedabad (2025)", "url": "https://brandveda.in/top-it"},
            {"title": "Software Download", "url": "https://www.microsoft.com/download"},
            {"title": "Agile Infoways - Custom Software", "url": "https://agileinfoways.com"},
        ]
        r = self.run_search(fake)
        kinds = {x["domain"]: x["kind"] for x in r["results"]}
        self.assertEqual(kinds, {"agileinfoways.com": "website", "brandveda.in": "article"})
        self.assertEqual(r["results"][0]["domain"], "agileinfoways.com", "company websites first")
        self.assertEqual(r["results"][1]["website"], "", "an article is not the company's website")

    def test_off_target_results_dropped_for_site_queries(self):
        fake = lambda q, n, t, s: [{"title": "x", "url": "https://deepmind.google/x"},
                                   {"title": "Acme Traders - IndiaMART", "url": "https://www.indiamart.com/acme/"}]
        r = self.run_search(fake, {"mode": "b2b"})
        self.assertTrue(all("indiamart.com" in x["domain"] or "tradeindia" in x["domain"] for x in r["results"]))
        self.assertGreater(r["ignored_off_target"], 0)

    def test_rate_limit_keeps_partial_results(self):
        calls = []

        def fake(q, n, t, s):
            calls.append(q)
            if len(calls) == 2:
                raise se.RateLimited("DuckDuckGo: rate limit reached")
            return [{"title": "Acme", "url": "https://acme.in"}]
        r = self.run_search(fake)
        self.assertTrue(r["rate_limited"])
        self.assertEqual(r["total"], 1)
        self.assertEqual(r["engines"]["duckduckgo"]["status"], "partial")

    def test_all_queries_fail_is_error(self):
        def fake(q, n, t, s):
            raise se.EngineError("boom")
        r = self.run_search(fake)
        self.assertEqual(r["engines"]["duckduckgo"]["status"], "error")
        self.assertEqual(r["total"], 0)

    def test_empty_duckduckgo_gives_key_hint(self):
        r = self.run_search(lambda q, n, t, s: [])
        self.assertIn("BRAVE_SEARCH_API_KEY", r["hint"])

    def test_existing_leads_are_marked(self):
        from lead_normalizer import MasterLeadRegistry
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "m.csv")
            reg = MasterLeadRegistry(path)
            reg.add_lead({"company_name": "Acme", "website": "https://acme.in", "source": "test"})
            reg.save_master_safely()
            r = self.run_search(lambda q, n, t, s: [{"title": "Acme", "url": "https://acme.in/about"},
                                                    {"title": "Zeta", "url": "https://zeta.in"}], master=path)
        flags = {x["domain"]: x["in_leads"] for x in r["results"]}
        self.assertEqual(flags, {"acme.in": True, "zeta.in": False})
        self.assertEqual(r["results"][-1]["domain"], "acme.in", "already-saved results go last")


class EngineParsers(unittest.TestCase):
    def test_brave(self):
        sess = mock.Mock()
        sess.get.return_value = resp(200, {"web": {"results": [{"title": "A", "url": "https://a.in", "description": "<b>x</b>"}]}})
        with mock.patch.dict(os.environ, {"BRAVE_SEARCH_API_KEY": "k"}):
            out = se.search_brave("q", 10, "week", sess)
        self.assertEqual(out, [{"title": "A", "url": "https://a.in", "snippet": "x"}])
        params = sess.get.call_args.kwargs["params"]
        self.assertEqual((params["freshness"], params["country"]), ("pw", "IN"))
        self.assertEqual(sess.get.call_args.kwargs["headers"]["X-Subscription-Token"], "k")

    def test_serper(self):
        sess = mock.Mock()
        sess.post.return_value = resp(200, {"organic": [{"title": "A", "link": "https://a.in", "snippet": "s"}]})
        with mock.patch.dict(os.environ, {"SERPER_API_KEY": "k"}):
            out = se.search_serper("q", 10, "month", sess)
        self.assertEqual(out[0]["url"], "https://a.in")
        self.assertEqual(sess.post.call_args.kwargs["json"]["tbs"], "qdr:m")

    def test_searxng_no_key(self):
        sess = mock.Mock()
        page1 = resp(200, {"results": [{"title": "A", "url": "https://a.in", "content": "s"},
                                       {"title": "B", "url": "https://b.in", "content": None}]})
        page2 = resp(200, {"results": [{"title": "A", "url": "https://a.in", "content": "s"}]})  # repeats -> stop
        sess.get.side_effect = [page1, page2]
        with mock.patch.dict(os.environ, {"SEARXNG_URL": "http://localhost:8888/"}), mock.patch.object(se.time, "sleep"):
            out = se.search_searxng("q", 10, "year", sess)
        self.assertEqual(out, [{"title": "A", "url": "https://a.in", "snippet": "s"},
                               {"title": "B", "url": "https://b.in", "snippet": ""}])
        self.assertEqual(sess.get.call_args_list[0].args[0], "http://localhost:8888/search")
        params = sess.get.call_args_list[0].kwargs["params"]
        self.assertEqual((params["format"], params["time_range"], params["pageno"]), ("json", "year", 1))
        self.assertNotIn("X-API-KEY", sess.get.call_args.kwargs["headers"])     # no key is ever sent

    def test_searxng_setup_errors(self):
        sess = mock.Mock()
        with mock.patch.dict(os.environ, {"SEARXNG_URL": "file:///etc/passwd"}), self.assertRaises(se.EngineError):
            se.search_searxng("q", 10, "any", sess)
        sess.get.assert_not_called()
        with mock.patch.dict(os.environ, {"SEARXNG_URL": "http://localhost:8888"}):
            sess.get.return_value = resp(403, {})
            with self.assertRaisesRegex(se.EngineError, "json"):
                se.search_searxng("q", 10, "any", sess)
            sess.get.return_value = resp(429, {})
            with self.assertRaises(se.RateLimited):
                se.search_searxng("q", 10, "any", sess)
            sess.get.side_effect = se.requests.ConnectionError()
            with self.assertRaisesRegex(se.EngineError, "not running"):
                se.search_searxng("q", 10, "any", sess)

    def test_http_errors(self):
        sess = mock.Mock()
        for code, exc in ((429, se.RateLimited), (401, se.EngineError), (402, se.EngineError)):
            sess.get.return_value = resp(code, {})
            with self.assertRaises(exc):
                se.search_brave("q", 10, "any", sess)


class Fallback(unittest.TestCase):
    """Brave key + SearXNG together: a failing engine hands the query to the next one that is set up."""
    ENV = {"BRAVE_SEARCH_API_KEY": "k", "SERPER_API_KEY": "", "SEARXNG_URL": "http://localhost:8888"}

    def setUp(self):
        se.reset_cooldown()
        self.addCleanup(se.reset_cooldown)
        self.calls = []

    def fake(self, name, result):
        def run(*a):
            self.calls.append(name)
            if isinstance(result, Exception):
                raise result
            return result
        return run

    def funcs(self, brave, searx, ddg=()):
        return {"brave": self.fake("brave", brave), "serper": self.fake("serper", []),
                "searxng": self.fake("searxng", searx), "duckduckgo": self.fake("duckduckgo", list(ddg))}

    def test_chain_order_only_set_up_engines(self):
        with mock.patch.dict(os.environ, self.ENV):
            self.assertEqual(se.fallback_chain("brave"), ["brave", "searxng", "duckduckgo"])
            self.assertEqual(se.fallback_chain("searxng"), ["searxng", "duckduckgo"])
            self.assertEqual(se.fallback_chain("duckduckgo"), ["duckduckgo"])

    def test_brave_limit_goes_to_searxng_and_cools_down(self):
        hit = [{"title": "S", "url": "https://s.in", "snippet": ""}]
        with mock.patch.dict(os.environ, self.ENV),                 mock.patch.dict(se.RAW_ENGINE_FUNCS, self.funcs(se.RateLimited("Brave 429"), hit)):
            self.assertEqual(se.ENGINE_FUNCS["brave"]("q", 10, "any", None), hit)
            self.assertEqual(self.calls, ["brave", "searxng"])
            self.calls.clear()
            se.ENGINE_FUNCS["brave"]("q2", 10, "any", None)          # Brave is cooling: not asked again
            self.assertEqual(self.calls, ["searxng"])

    def test_searxng_down_goes_to_duckduckgo(self):
        hit = [{"title": "D", "url": "https://d.in", "snippet": ""}]
        with mock.patch.dict(os.environ, self.ENV),                 mock.patch.dict(se.RAW_ENGINE_FUNCS, self.funcs(se.EngineError("Brave: no credits (HTTP 402)"),
                                                                se.EngineError("SearXNG is not running"), hit)):
            self.assertEqual(se.ENGINE_FUNCS["brave"]("q", 10, "any", None), hit)
            self.assertEqual(self.calls, ["brave", "searxng", "duckduckgo"])

    def test_all_rate_limited_raises_rate_limited(self):
        with mock.patch.dict(os.environ, self.ENV),                 mock.patch.dict(se.RAW_ENGINE_FUNCS, self.funcs(se.RateLimited("b"), se.RateLimited("s"))):
            se.RAW_ENGINE_FUNCS["duckduckgo"] = self.fake("duckduckgo", se.RateLimited("d"))
            with self.assertRaises(se.RateLimited):
                se.ENGINE_FUNCS["brave"]("q", 10, "any", None)

    def test_success_does_not_fall_back(self):
        hit = [{"title": "B", "url": "https://b.in", "snippet": ""}]
        with mock.patch.dict(os.environ, self.ENV), mock.patch.dict(se.RAW_ENGINE_FUNCS, self.funcs(hit, [])):
            self.assertEqual(se.ENGINE_FUNCS["brave"]("q", 10, "any", None), hit)
            self.assertEqual(self.calls, ["brave"])


class Guard(unittest.TestCase):
    def check(self, url, ip="93.184.216.34"):
        with mock.patch.object(ds.socket, "getaddrinfo", return_value=[(2, 1, 6, "", (ip, 443))]):
            ds.public_url_guard(url)

    def test_blocks_private_and_odd_urls(self):
        for url, ip in (("http://localhost/", "127.0.0.1"), ("http://intranet/", "10.0.0.5"),
                        ("http://router/", "192.168.1.1"), ("http://meta/", "169.254.169.254"), ("http://v6/", "::1")):
            with self.assertRaises(hcm.BlockedUrl, msg=url):
                self.check(url, ip)
        for url in ("ftp://acme.in/", "http://acme.in:5000/", "javascript:alert(1)"):
            with self.assertRaises(hcm.BlockedUrl, msg=url):
                self.check(url)

    def test_allows_public_site(self):
        self.check("https://acme.in/contact")

    def test_redirect_to_private_is_blocked(self):
        hops = [SimpleNamespace(is_redirect=True, headers={"Location": "http://127.0.0.1/admin"}, close=lambda: None)]
        seen = []

        def guard(u):
            seen.append(u)
            if "127.0.0.1" in u:
                raise hcm.BlockedUrl("private")
        with tempfile.TemporaryDirectory() as d, mock.patch.object(hcm, "CACHE_DIR", d), \
                mock.patch.object(hcm.requests, "get", side_effect=hops):
            self.assertEqual(hcm.fetch_or_get_cached_html("https://acme.in/", guard=guard), ("", 0))
        self.assertEqual(seen, ["https://acme.in/", "http://127.0.0.1/admin"])


HOME = """<html><head><title>Acme Infotech | Software Company</title>
<script type="application/ld+json">{"@context":"https://schema.org","@graph":[{"@type":"Organization","name":"Acme Infotech",
"email":"mailto:Sales@Acme.in","telephone":"+91 98250 11111","sameAs":["https://www.linkedin.com/company/acme-infotech"],
"address":{"streetAddress":"12 SG Highway","addressLocality":"Ahmedabad","postalCode":"380054"}}]}</script></head>
<body><a href="/contact-us">Contact</a><a href="https://www.facebook.com/sharer/sharer.php?u=x">share</a>
<a href="https://www.instagram.com/acmeinfotech/">ig</a> logo@2x.png</body></html>"""
CONTACT = """<html><body><a href="mailto:info@acme.in">info@acme.in</a> Write to hr@gmail.com.
Call <a href="tel:+919825022222">us</a>. Order 1234567890123.</body></html>"""


class Extraction(unittest.TestCase):
    def test_socials_skip_share_links(self):
        s = ds.extract_socials(HOME)
        self.assertEqual(s, {"instagram": "https://www.instagram.com/acmeinfotech",
                             "linkedin": "https://www.linkedin.com/company/acme-infotech"})
        self.assertNotIn("facebook", s, "share buttons are not the company's page")

    def test_crawl_site(self):
        pages = {"https://acme.in/": HOME, "https://acme.in/contact-us": CONTACT}
        with mock.patch.object(ds, "fetch", side_effect=lambda u: pages.get(u, "")):
            out = ds.crawl_site("https://acme.in")
        self.assertEqual(out["emails"][:2], ["sales@acme.in", "info@acme.in"], "on-domain emails first")
        self.assertIn("hr@gmail.com", out["emails"])
        self.assertIn("+91 98250 11111", out["phones"])
        self.assertIn("+91 98250 22222", out["phones"])
        self.assertEqual(set(out["socials"]), {"instagram", "linkedin"})
        self.assertIn("Ahmedabad", out["address"])
        self.assertTrue(out["jsonld"])
        self.assertEqual(out["name"], "Acme Infotech")

    def test_phones_never_come_from_scripts(self):
        """Bug 2026-11-12: Shopify asset ids inside <script> became phone numbers and merged two companies."""
        page = ('<html><body><script>var cfg = {"id": 0145039034, "v": "4815527494"};</script>'
                '<p>Call us: <a href="tel:+919825033333">98250 33333</a></p>'
                '<style>.x{width:1782880009px}</style></body></html>')
        with mock.patch.object(ds, "fetch", side_effect=lambda u: page if u == "https://shop.in/" else ""):
            out = ds.crawl_site("https://shop.in")
        self.assertEqual(out["phones"], ["+91 98250 33333"])

    def test_foreign_site_numbers_not_made_indian(self):
        """Bug 2026-11-12: US numbers on .com sites (949-387-0117) became '+91 94938 70117'."""
        us = '<html><body><p>Call (949) 387-0117 or 626-965-9966. Irvine, CA</p></body></html>'
        with mock.patch.object(ds, "fetch", side_effect=lambda u: us if u == "https://weareenvoy.com/" else ""):
            self.assertEqual(ds.crawl_site("https://weareenvoy.com")["phones"], [])
        india = '<html><body><p>Call 98250 44444. Ahmedabad, Gujarat, India</p></body></html>'
        with mock.patch.object(ds, "fetch", side_effect=lambda u: india if u == "https://acmefoods.com/" else ""):
            self.assertEqual(ds.crawl_site("https://acmefoods.com")["phones"], ["+91 98250 44444"])
        tel = '<html><body><a href="tel:+919825055555">Call</a></body></html>'
        with mock.patch.object(ds, "fetch", side_effect=lambda u: tel if u == "https://acmetools.com/" else ""):
            self.assertEqual(ds.crawl_site("https://acmetools.com")["phones"], ["+91 98250 55555"])

    def test_unreachable_site(self):
        with mock.patch.object(ds, "fetch", return_value=""):
            self.assertEqual(ds.crawl_site("https://down.in")["error"], "website could not be opened")


class Waterfall(unittest.TestCase):
    def setUp(self):
        self.p = [mock.patch.object(ds.socket, "getaddrinfo", side_effect=public_dns),
                  mock.patch.object(ds, "guess_email", return_value="")]
        for x in self.p:
            x.start()

    def tearDown(self):
        for x in self.p:
            x.stop()

    def test_listing_finds_website_by_name_then_crawls(self):
        hits = [{"title": "x", "url": "https://www.linkedin.com/company/acme"},
                {"title": "Other", "url": "https://unrelated.com"},
                {"title": "Acme", "url": "https://www.acmeinfotech.in/about"}]
        crawl = {"emails": ["info@acmeinfotech.in"], "phones": [], "address": "", "socials": {}, "name": "Acme",
                 "pages": ["https://www.acmeinfotech.in/"], "error": "", "jsonld": False}
        with mock.patch.dict(se.ENGINE_FUNCS, {"duckduckgo": lambda *a: hits}), \
                mock.patch.object(ds, "crawl_site", return_value=crawl) as c:
            out = ds.enrich({"url": "https://linkedin.com/company/acme", "company": "Acme Infotech Pvt Ltd"}, "duckduckgo", False)
        c.assert_called_once_with("https://www.acmeinfotech.in/")
        self.assertEqual((out["website"], out["status"]), ("https://www.acmeinfotech.in/", "found"))

    def test_list_article_is_skipped(self):
        with mock.patch.object(ds, "crawl_site") as c:
            out = ds.enrich({"url": "https://brandveda.in/top-it", "company": "Top 11 IT Companies", "kind": "article"},
                            "duckduckgo", False)
        c.assert_not_called()
        self.assertIn("list article", out["steps"][0])

    def test_no_name_match_means_no_website(self):
        with mock.patch.dict(se.ENGINE_FUNCS, {"duckduckgo": lambda *a: [{"title": "x", "url": "https://other.com"}]}):
            out = ds.enrich({"url": "https://linkedin.com/company/acme", "company": "Acme Infotech"}, "duckduckgo", False)
        self.assertEqual((out["website"], out["status"]), ("", "none"))

    def test_zauba_hunter_and_guess_steps(self):
        empty = {"emails": [], "phones": [], "address": "", "socials": {}, "name": "", "pages": ["https://acme.in/"],
                 "error": "", "jsonld": False}
        zpage = "<html>Acme Infotech Private Limited CIN U72200GJ2010PTC123456 Email ID: acme.mca@gmail.com</html>"
        zhits = [{"title": "z", "url": "https://www.zaubacorp.com/company/ACME-INFOTECH/U72200GJ2010PTC123456"}]
        with mock.patch.object(ds, "crawl_site", return_value=empty), \
                mock.patch.dict(se.ENGINE_FUNCS, {"duckduckgo": lambda *a: zhits}), \
                mock.patch.object(ds, "fetch", return_value=zpage):
            out = ds.enrich({"website": "https://acme.in", "company": "Acme Infotech Private Limited"}, "duckduckgo", False)
        self.assertEqual((out["emails"], out["cin"]), (["acme.mca@gmail.com"], "U72200GJ2010PTC123456"))

        hunter = resp(200, {"data": {"emails": [{"value": "Ravi@acme.in", "first_name": "Ravi", "last_name": "S",
                                                 "position": "CEO", "confidence": 90}]}})
        with mock.patch.object(ds, "crawl_site", return_value=empty), \
                mock.patch.dict(os.environ, {"HUNTER_API_KEY": "k"}), mock.patch.object(ds.requests, "get", return_value=hunter):
            out = ds.enrich({"website": "https://acme.in", "company": "Acme"}, "duckduckgo", True)
        self.assertEqual(out["emails"], ["ravi@acme.in"])
        self.assertEqual(out["contacts"][0]["position"], "CEO")

        with mock.patch.object(ds, "crawl_site", return_value=empty), \
                mock.patch.object(ds, "guess_email", return_value="info@acme.in"):
            out = ds.enrich({"website": "https://acme.in", "company": "Acme"}, "duckduckgo", False)
        self.assertEqual((out["emails"], out["email_guess"], out["status"]), ([], "info@acme.in", "partial"))

    def test_private_website_is_not_crawled(self):
        with mock.patch.object(ds.socket, "getaddrinfo", return_value=[(2, 1, 6, "", ("127.0.0.1", 80))]), \
                mock.patch.object(ds, "crawl_site") as c:
            out = ds.enrich({"website": "http://localhost/", "company": "x"}, "duckduckgo", False)
        c.assert_not_called()
        self.assertEqual(out["website"], "")

    def test_batch_validation_and_isolation(self):
        with self.assertRaises(ValueError):
            ds.deep_search([], "duckduckgo")
        with self.assertRaises(ValueError):
            ds.deep_search([{"url": f"https://a{i}.in"} for i in range(11)], "duckduckgo")
        with self.assertRaises(ValueError):
            ds.deep_search([{"foo": 1}], "duckduckgo")
        with mock.patch.dict(os.environ, {"HUNTER_API_KEY": ""}), self.assertRaises(ValueError):
            ds.deep_search([{"url": "https://a.in"}], "duckduckgo", use_hunter=True)
        with mock.patch.object(ds, "enrich", side_effect=RuntimeError("boom")):
            out = ds.deep_search([{"key": "k1", "url": "https://a.in"}], "duckduckgo")
        self.assertEqual((out["results"][0]["key"], out["results"][0]["status"]), ("k1", "error"))


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
        for m, u in (("get", "/api/search-engine"), ("post", "/api/search-engine/search"),
                     ("post", "/api/search-engine/deep"), ("post", "/api/search-engine/save")):
            self.assertEqual(getattr(self.client, m)(u).status_code, 401, u)

    def test_old_live_search_endpoint_removed(self):
        self.assertEqual(self.client.post("/api/import/search", headers=self.h, json={"keyword": "x"}).status_code, 404)

    def test_options(self):
        body = self.client.get("/api/search-engine", headers=self.h).get_json()
        self.assertEqual([e["id"] for e in body["engines"]], ["auto", "brave", "serper", "searxng", "duckduckgo"])
        self.assertIn("custom", [m["id"] for m in body["modes"]])
        self.assertEqual(body["states"][0], "All India")

    def test_search_validation_cache_and_fresh_in_leads(self):
        self.assertEqual(self.client.post("/api/search-engine/search", headers=self.h,
                                          json={**BASE, "keywords": []}).status_code, 400)
        fake = {"results": [{"company": "Acme", "url": "https://acme.in", "website": "https://acme.in", "in_leads": True,
                             "match": "old"}], "total": 1, "query": {},
                "engines": {"duckduckgo": {"status": "ok", "count": 1}}}
        with mock.patch.object(se, "search", return_value=fake) as live, \
                mock.patch.object(se, "mark_existing") as mark:
            r1 = self.client.post("/api/search-engine/search", headers=self.h, json=BASE).get_json()
            r2 = self.client.post("/api/search-engine/search", headers=self.h, json=BASE).get_json()
        self.assertEqual(live.call_count, 1)
        self.assertEqual((r1["cache"]["hit"], r2["cache"]["hit"]), (False, True))
        self.assertEqual(mark.call_count, 2, "in_leads is re-checked on every response")
        self.assertFalse(r2["results"][0]["in_leads"])

    def test_deep_validation(self):
        r = self.client.post("/api/search-engine/deep", headers=self.h, json={"items": []})
        self.assertEqual(r.status_code, 400)

    def test_save_maps_and_never_sends_by_default(self):
        self.assertEqual(self.client.post("/api/search-engine/save", headers=self.h, json={"results": []}).status_code, 400)
        self.assertEqual(self.client.post("/api/search-engine/save", headers=self.h,
                                          json={"results": [{"company": "X"}]}).status_code, 400)
        done = {"success": True, "added": 1, "updated": 0, "duplicates": 0, "emails_sent": 0, "supabase_synced": False}
        row = {"company": "Acme", "url": "https://acme.in", "website": "https://acme.in", "email": "info@acme.in",
               "phone": "+91 98250 12345", "engine": "brave", "mode": "b2b", "location": "Ahmedabad",
               "socials": {"instagram": "https://instagram.com/acme"}, "address": "SG Highway"}
        with mock.patch.object(self.app.lead_importer, "commit_imported_leads", return_value=done) as commit:
            r = self.client.post("/api/search-engine/save", headers=self.h, json={"results": [row, {"company": "X"}]}).get_json()
        leads, = commit.call_args.args
        self.assertFalse(commit.call_args.kwargs["send_outreach_email"])
        self.assertEqual(len(leads), 1)
        lead = leads[0]
        self.assertEqual(lead["source"], "Search Engine (Brave Search)")
        self.assertTrue(lead["lead_type"].startswith("Search Engine - B2B portals"))
        self.assertIn("instagram", lead["description"])
        self.assertEqual((r["added"], r["skipped_invalid"]), (1, 1))

    def test_save_writes_master_without_duplicates(self):
        row = {"company": "Acme", "url": "https://acme.in", "website": "https://acme.in", "engine": "duckduckgo", "mode": "companies"}
        with tempfile.TemporaryDirectory() as d, mock.patch.object(self.app, "MASTER_PATH", os.path.join(d, "m.csv")), \
                mock.patch.object(self.app.lead_importer, "sync_to_supabase", None):
            r1 = self.client.post("/api/search-engine/save", headers=self.h, json={"results": [row]}).get_json()
            r2 = self.client.post("/api/search-engine/save", headers=self.h, json={"results": [row]}).get_json()
        self.assertEqual((r1["added"], r2["added"]), (1, 0))


if __name__ == "__main__":
    unittest.main()

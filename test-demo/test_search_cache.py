"""Tests for search_cache.py and its use in the search endpoints (no network)."""
import tempfile
import time
import unittest
from unittest import mock

import html_cache_manager as hcm
import search_cache as sc

OK = {"total": 2, "results": [{"company": "A"}, {"company": "B"}],
      "sources": {"goodfirms": {"status": "ok", "count": 2}}}
PARTIAL = {"total": 2, "results": [{"company": "A"}],
           "sources": {"goodfirms": {"status": "ok", "count": 2}, "osm": {"status": "error", "count": 0}}}
EMPTY = {"total": 0, "results": [], "sources": {"goodfirms": {"status": "ok", "count": 0}}}
PARAMS = {"keywords": ["Software", "IT"], "titles": [], "state": "Gujarat", "city": "Ahmedabad", "sources": ["goodfirms"]}


class TempCacheDir(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir_patch = mock.patch.object(hcm, "CACHE_DIR", self.tmp.name)
        self.dir_patch.start()

    def tearDown(self):
        self.dir_patch.stop()
        self.tmp.cleanup()


class SearchCacheTests(TempCacheDir):
    def run_search(self, result, params=PARAMS, refresh=False):
        calls = []

        def run():
            calls.append(1)
            return result
        out = sc.cached_search("crmsources", params, run, "sources", refresh=refresh)
        return out, len(calls)

    def test_second_identical_search_is_served_from_cache(self):
        out1, n1 = self.run_search(OK)
        out2, n2 = self.run_search(OK)
        self.assertEqual((n1, n2), (1, 0))
        self.assertFalse(out1["cache"]["hit"])
        self.assertTrue(out2["cache"]["hit"])
        self.assertEqual(out2["results"], OK["results"])

    def test_key_ignores_case_order_and_spaces(self):
        self.run_search(OK)
        same = {"keywords": [" it", "software "], "titles": [], "state": "gujarat", "city": "AHMEDABAD",
                "sources": ["goodfirms"]}
        _, n = self.run_search(OK, params=same)
        self.assertEqual(n, 0)
        _, n = self.run_search(OK, params={**PARAMS, "city": "Surat"})
        self.assertEqual(n, 1, "different inputs must not share a cache entry")

    def test_refresh_bypasses_cache(self):
        self.run_search(OK)
        out, n = self.run_search(OK, refresh=True)
        self.assertEqual(n, 1)
        self.assertFalse(out["cache"]["hit"])

    def test_partial_failure_is_not_cached(self):
        self.run_search(PARTIAL)
        _, n = self.run_search(PARTIAL)
        self.assertEqual(n, 1)

    def test_empty_result_is_not_cached(self):
        self.run_search(EMPTY)
        _, n = self.run_search(EMPTY)
        self.assertEqual(n, 1)

    def test_expired_entry_not_used(self):
        self.run_search(OK)
        later = time.time() + sc.TTL_HOURS["crmsources"] * 3600 + 5
        with mock.patch.object(sc.time, "time", return_value=later):
            _, n = self.run_search(OK)
        self.assertEqual(n, 1)

    def test_ttl_zero_disables_cache(self):
        with mock.patch.dict(sc.TTL_HOURS, {"crmsources": 0}):
            self.run_search(OK)
            _, n = self.run_search(OK)
        self.assertEqual(n, 1)

    def test_job_portals_status_key(self):
        res = {"total": 1, "jobs": [{"title": "x"}], "portals": {"shine": {"status": "error"}}}
        self.assertFalse(sc.is_cacheable(res, "portals"))
        res["portals"]["shine"]["status"] = "ok"
        self.assertTrue(sc.is_cacheable(res, "portals"))


class EndpointCacheTests(TempCacheDir):
    def setUp(self):
        super().setUp()
        import app as app_module
        self.app = app_module
        self.client = app_module.app.test_client()

    def post(self, path, body):
        return self.client.post(path, json=body, headers={"X-Demo-User": "true"},
                                environ_base={"REMOTE_ADDR": "127.0.0.1"})

    def test_crm_search_cached_then_refresh_goes_live(self):
        with mock.patch.object(self.app.crm_sources, "search", return_value=dict(OK)) as live:
            r1 = self.post("/api/crm-sources/search", PARAMS)
            if r1.status_code == 401:
                self.skipTest("demo login disabled in this environment")
            r2 = self.post("/api/crm-sources/search", PARAMS)
            r3 = self.post("/api/crm-sources/search", {**PARAMS, "refresh": True})
        self.assertEqual(live.call_count, 2)
        self.assertEqual([r.get_json()["cache"]["hit"] for r in (r1, r2, r3)], [False, True, False])

    def test_job_search_validation_error_still_400(self):
        with mock.patch.object(self.app.job_portals, "search_jobs", side_effect=ValueError("Enter at least one job title")):
            r = self.post("/api/job-portals/search", {"titles": [], "state": "Gujarat", "portals": ["shine"]})
        if r.status_code == 401:
            self.skipTest("demo login disabled in this environment")
        self.assertEqual(r.status_code, 400)


if __name__ == "__main__":
    unittest.main()

"""Tests for html_cache_manager.py (no network).   python -m unittest test_html_cache -v"""
import os
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest import mock

import requests

import html_cache_manager as hcm

REAL_PAGE = "<html><body>" + ("Contact us at info@acme.in. " * 1000) + "</body></html>"
CAPTCHA_PAGE = "<html><title>Attention Required! | Cloudflare</title><div class='cf-chl'>verify you are human</div></html>"


def _resp(status, text):
    return SimpleNamespace(status_code=status, text=text)


class HtmlCache(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir_patch = mock.patch.object(hcm, "CACHE_DIR", self.tmp.name)
        self.dir_patch.start()
        self.url = "https://acme.in/contact"
        self.path = os.path.join(self.tmp.name, hcm.get_url_hash(self.url))

    def tearDown(self):
        self.dir_patch.stop()
        self.tmp.cleanup()

    def _age_file(self, days):
        old = time.time() - days * 86400
        os.utime(self.path, (old, old))

    def test_first_fetch_saves_then_serves_from_cache(self):
        with mock.patch.object(hcm.requests, "get", return_value=_resp(200, REAL_PAGE)) as get:
            self.assertEqual(hcm.fetch_or_get_cached_html(self.url), (REAL_PAGE, 1))
            self.assertEqual(hcm.fetch_or_get_cached_html(self.url), (REAL_PAGE, 1))
        self.assertEqual(get.call_count, 1)  # second call came from disk
        self.assertTrue(os.path.exists(self.path))

    def test_old_copy_is_refreshed(self):
        with mock.patch.object(hcm.requests, "get", return_value=_resp(200, REAL_PAGE)):
            hcm.fetch_or_get_cached_html(self.url)
        self._age_file(40)
        new_page = REAL_PAGE.replace("info@acme.in", "sales@acme.in")
        with mock.patch.object(hcm.requests, "get", return_value=_resp(200, new_page)) as get:
            html, status = hcm.fetch_or_get_cached_html(self.url)
        get.assert_called_once()
        self.assertIn("sales@acme.in", html)

    def test_old_copy_used_when_site_blocks(self):
        with mock.patch.object(hcm.requests, "get", return_value=_resp(200, REAL_PAGE)):
            hcm.fetch_or_get_cached_html(self.url)
        self._age_file(40)
        for blocked in (_resp(403, "Forbidden"), _resp(429, "Slow down"), _resp(200, CAPTCHA_PAGE)):
            with mock.patch.object(hcm.requests, "get", return_value=blocked):
                self.assertEqual(hcm.fetch_or_get_cached_html(self.url), (REAL_PAGE, 1))
        with mock.patch.object(hcm.requests, "get", side_effect=requests.ConnectionError("down")):
            self.assertEqual(hcm.fetch_or_get_cached_html(self.url), (REAL_PAGE, 1))

    def test_captcha_page_never_cached(self):
        with mock.patch.object(hcm.requests, "get", return_value=_resp(200, CAPTCHA_PAGE)):
            self.assertEqual(hcm.fetch_or_get_cached_html(self.url), ("", 0))
        self.assertFalse(os.path.exists(self.path))

    def test_long_real_page_mentioning_captcha_is_cached(self):
        page = REAL_PAGE + "<form>protected by reCAPTCHA</form>"
        with mock.patch.object(hcm.requests, "get", return_value=_resp(200, page)):
            self.assertEqual(hcm.fetch_or_get_cached_html(self.url)[1], 1)
        self.assertTrue(os.path.exists(self.path))

    def test_no_cache_and_failure_returns_empty(self):
        with mock.patch.object(hcm.requests, "get", return_value=_resp(404, "nope")):
            self.assertEqual(hcm.fetch_or_get_cached_html(self.url), ("", 0))

    def test_prune_removes_only_very_old_pages(self):
        with mock.patch.object(hcm.requests, "get", return_value=_resp(200, REAL_PAGE)):
            hcm.fetch_or_get_cached_html(self.url)
        self.assertEqual(hcm.prune_cache(max_age_days=90), 0)
        self._age_file(100)
        self.assertEqual(hcm.prune_cache(max_age_days=90), 1)
        self.assertFalse(os.path.exists(self.path))


if __name__ == "__main__":
    unittest.main()

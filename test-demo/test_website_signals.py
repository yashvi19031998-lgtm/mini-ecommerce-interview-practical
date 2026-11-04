"""Tests for website_signals.py and how the signals reach the AI.   python -m unittest test_website_signals -v"""
import datetime
import json
import unittest
from types import SimpleNamespace
from unittest import mock

import lead_quality as lq
import website_signals as ws

THIS_YEAR = datetime.date.today().year

MODERN = f"""<html><head><meta name="viewport" content="width=device-width">
<meta name="generator" content="WordPress 6.6"><script src="/js/jquery-3.7.1.min.js"></script></head>
<body>© {THIS_YEAR} Acme</body></html>"""

OUTDATED = """<html><head><meta name="generator" content="WordPress 4.9.8">
<script src="https://code.jquery.com/jquery-1.12.4.min.js"></script></head>
<body>Copyright 2015-2019 Acme Traders</body></html>"""


class Analyze(unittest.TestCase):
    def test_modern_site_has_no_signals(self):
        self.assertEqual(ws.analyze_html(MODERN, "https://acme.in"), [])

    def test_outdated_site_signals(self):
        found = ws.analyze_html(OUTDATED, "http://acme.in")
        self.assertIn("no HTTPS", found)
        self.assertIn("not mobile-friendly (no viewport tag)", found)
        self.assertIn("old WordPress 4.9", found)
        self.assertIn("old jQuery 1.12", found)
        self.assertIn("copyright year 2019 (site not updated recently)", found)

    def test_site_builder(self):
        page = MODERN.replace("</body>", '<img src="https://static.wixstatic.com/a.png"></body>')
        self.assertIn("built with Wix (site builder)", ws.analyze_html(page, "https://acme.in"))

    def test_check_website_summary(self):
        with mock.patch.object(ws, "fetch_or_get_cached_html", return_value=(MODERN, 1)):
            self.assertEqual(ws.check_website("acme.in"), ws.NO_ISSUES)
        with mock.patch.object(ws, "fetch_or_get_cached_html", return_value=("", 0)):
            self.assertEqual(ws.check_website("acme.in"), ws.FETCH_FAILED)
        with mock.patch.object(ws, "fetch_or_get_cached_html", return_value=(OUTDATED, 1)) as f:
            self.assertIn("old jQuery 1.12", ws.check_website("acme.in"))
        f.assert_called_with("https://acme.in", timeout=10)


class ReachesAI(unittest.TestCase):
    def test_lead_text_shows_signals_and_missing_website(self):
        text = lq._lead_text({"company_name": "Acme", "website": "https://acme.in",
                              "website_signals": "not mobile-friendly (no viewport tag)"})
        self.assertIn("Website check: not mobile-friendly", text)
        local = lq._lead_text({"company_name": "Sharma Sweets", "source": "Google Maps (Ahmedabad)"})
        self.assertIn("Website: none found", local)
        reddit = lq._lead_text({"company_name": "Need an app", "source": "Reddit (r/startups)"})
        self.assertNotIn("Website:", reddit)  # a missing website is only meaningful for listed businesses
        self.assertIn("prospect_signal", lq.SYSTEM_PROMPT)
        self.assertIn("Website check", lq.SYSTEM_PROMPT)

    def test_website_checked_before_ai_call(self):
        lead = {"lead_id": "L1", "company_name": "Acme", "website": "https://acme.in"}
        payload = json.dumps({"category": "prospect_signal", "score": 6, "summary": "s", "requirement": "",
                              "tech_stack": "", "budget": "", "reason": "outdated site"})
        client = mock.MagicMock()
        client.beta.messages.create.return_value = SimpleNamespace(
            stop_reason="end_turn", content=[SimpleNamespace(type="text", text=payload)])
        registry = SimpleNamespace(leads=[lead])
        with mock.patch.object(lq, "_get_client", return_value=client), \
                mock.patch.object(lq.website_signals, "check_website", return_value="old jQuery 1.12") as check:
            lq.qualify_leads(registry)
        check.assert_called_once_with("https://acme.in")
        self.assertEqual(lead["website_signals"], "old jQuery 1.12")
        sent = client.beta.messages.create.call_args.kwargs["messages"][0]["content"]
        self.assertIn("Website check: old jQuery 1.12", sent)
        self.assertEqual(lead["ai_category"], "prospect_signal")


if __name__ == "__main__":
    unittest.main()

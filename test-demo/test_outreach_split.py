"""Scraping and e-mail run as separate jobs: --no-email scrapes without mailing, --email-only mails
without scraping (GitHub: auto_scraper_1hr.yml and outreach_mail.yml)."""
import os
import sys
import tempfile
import unittest
from unittest import mock

import run_all_scrapers as runner


class _Registry:
    def __init__(self, *_a, **_k):
        self.leads = []

    def load_master(self):
        pass

    def save_master_safely(self):
        return True

    def add_lead(self, raw, default_source=""):
        return "added", raw


class SplitTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        self.scraper = mock.Mock(return_value=[{"company_name": "Acme"}])
        self.patches = [
            mock.patch.object(runner, "MasterLeadRegistry", _Registry),
            mock.patch.object(runner, "SCRAPERS_CONFIG", [{"name": "fake", "func": self.scraper, "enabled": True}]),
            mock.patch.object(runner, "log_scraper_run"),
            mock.patch.object(runner, "lead_quality", None),
            mock.patch.object(runner, "sync_to_supabase", None),
            mock.patch.object(runner, "run_followup_step"),
            mock.patch.object(runner, "dispatch_pending_outreach_emails", return_value=0),
            mock.patch.object(runner, "AUTO_SEND_EMAIL", True),
            mock.patch.object(runner, "send_smtp_email", mock.Mock()),
            mock.patch.dict(os.environ, {"APOLLO_API_KEY": ""}),
            mock.patch.dict(sys.modules, {"website_contact_extractor": mock.Mock(run_website_enrichment=lambda **k: 0)}),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        os.chdir(self.old)
        self.tmp.cleanup()

    def test_no_email_scrapes_but_never_mails(self):
        runner.run_all_scrapers(send_email=False)
        self.scraper.assert_called_once()
        runner.dispatch_pending_outreach_emails.assert_not_called()
        runner.run_followup_step.assert_not_called()

    def test_default_run_still_scrapes_and_mails(self):  # PC scheduler keeps working as before
        runner.run_all_scrapers()
        self.scraper.assert_called_once()
        runner.run_followup_step.assert_called_once()
        runner.dispatch_pending_outreach_emails.assert_called_once()

    def test_email_only_mails_without_scraping(self):
        order = []
        runner.run_followup_step.side_effect = lambda r: order.append("gmail check")
        runner.dispatch_pending_outreach_emails.side_effect = lambda r, **k: order.append("outreach") or 0
        runner.run_outreach_only()
        self.scraper.assert_not_called()
        self.assertEqual(order, ["gmail check", "outreach"])  # a fresh bounce must be seen before mailing
        self.assertFalse(os.path.exists(runner.LOCK_FILE))

    def test_email_only_respects_auto_send_off(self):
        with mock.patch.object(runner, "AUTO_SEND_EMAIL", False):
            runner.run_outreach_only()
        runner.run_followup_step.assert_called_once()  # replies are still read
        runner.dispatch_pending_outreach_emails.assert_not_called()


class WorkflowTests(unittest.TestCase):
    def _read(self, name):
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".github", "workflows", name)
        with open(path, encoding="utf-8") as fh:
            return fh.read()

    def test_scraper_workflow_has_no_mail_login(self):
        wf = self._read("auto_scraper_1hr.yml")
        self.assertIn("run_all_scrapers.py --no-email", wf)
        self.assertNotIn("SMTP_PASS", wf)
        self.assertIn("group: lead-data", wf)

    def test_mail_workflow_keeps_the_safe_limits(self):
        wf = self._read("outreach_mail.yml")
        self.assertIn("run_all_scrapers.py --email-only", wf)
        self.assertIn("group: lead-data", wf)
        self.assertIn("datastore.py sync --required", wf)
        self.assertIn("MIN_AI_SCORE_FOR_AUTO_EMAIL: ${{ vars.MIN_AI_SCORE_FOR_AUTO_EMAIL || '7' }}", wf)
        self.assertIn("MAX_EMAILS_PER_DAY: ${{ vars.MAX_EMAILS_PER_DAY || '50' }}", wf)
        self.assertNotIn("AUTO_EMAIL_PROSPECT_SIGNALS", wf)


if __name__ == "__main__":
    unittest.main()

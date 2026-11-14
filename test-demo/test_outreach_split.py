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
        self.assertIn("MAX_PROSPECT_EMAILS_PER_DAY: ${{ vars.MAX_PROSPECT_EMAILS_PER_DAY || '15' }}", wf)


def _lead(i, category, score, email=None):
    return {"lead_id": f"L{i}", "company_name": f"Company {i}", "email": email or f"info@company{i}.in",
            "ai_category": category, "ai_score": str(score), "email_status": "NOT_SENT",
            "title": "Need a React developer for our web app", "description": "remote contract",
            "ai_requirement": "React web app development", "ai_tech_stack": "React"}


class ProspectMailTests(unittest.TestCase):
    """Option B: prospects get a short intro mail - after real buyers, with their own daily limit."""
    def setUp(self):
        self.env = mock.patch.dict(os.environ, {"AUTO_EMAIL_PROSPECT_SIGNALS": "true",
                                                "MIN_AI_SCORE_FOR_PROSPECT_EMAIL": "3",
                                                "MIN_AI_SCORE_FOR_AUTO_EMAIL": "7"})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_rules(self):
        import lead_quality as lq
        self.assertEqual(lq.outreach_block_reason(_lead(1, "prospect_signal", 3)), "")
        self.assertIn("score 2 below 3", lq.outreach_block_reason(_lead(1, "prospect_signal", 2)))
        self.assertIn("below 7", lq.outreach_block_reason(_lead(1, "client_project", 5)))  # buyers unchanged
        self.assertIn("not a buyer", lq.outreach_block_reason(_lead(1, "irrelevant", 9)))
        with mock.patch.dict(os.environ, {"AUTO_EMAIL_PROSPECT_SIGNALS": "false"}):
            self.assertIn("not a buyer", lq.outreach_block_reason(_lead(1, "prospect_signal", 9)))

    def test_prospect_filter_keeps_out_competitors_and_junk(self):
        import lead_quality as lq
        def p(company, email, source="", title=""):
            return {"company_name": company, "email": email, "source": source, "title": title,
                    "ai_category": "prospect_signal", "ai_score": "3", "email_status": "NOT_SENT"}
        ok = p("Shree Ganesh Textiles", "info@shreeganeshtextiles.in", "B2B Portal (IndiaMART)")
        self.assertEqual(lq.outreach_block_reason(ok), "")
        for lead in (p("OpenXcell", "sales@openxcell.com", "CRM Source (GoodFirms)"),
                     p("Hidden Brains InfoTech", "biz@hiddenbrains.com"),
                     p("Datagrid Solutions", "info@datagrid.co.in"),
                     p("Patel Traders", "info@pateltraders.in", "Search Engine (software development company)")):
            self.assertIn("competitor", lq.outreach_block_reason(lead), lead["company_name"])
        self.assertIn("article", lq.outreach_block_reason(p("How to Get Help in Windows 11", "a@kartikblog.com")))
        self.assertIn("article", lq.outreach_block_reason(p("The Definitive List: Best IT", "s@lists.com")))
        self.assertIn("large brand", lq.outreach_block_reason(p("Airbnb", "from@airbnb.com")))
        self.assertIn("large brand", lq.outreach_block_reason(p("Marvel", "x@corp.aol.com")))

    def _dispatch(self, leads, prospects_already=0, cap=2):
        sent = []
        reg = mock.Mock(leads=leads)
        with mock.patch.object(runner, "AUTO_SEND_EMAIL", True), \
                mock.patch.object(runner, "MAX_PROSPECT_EMAILS_PER_DAY", cap), \
                mock.patch.object(runner, "prospect_emails_sent_today", return_value=prospects_already), \
                mock.patch.object(runner, "can_receive_mail", return_value=True), \
                mock.patch.object(runner, "bounces_last_24h", return_value=0), \
                mock.patch.object(runner.followup_store, "safe_log") as log, \
                mock.patch("email_service.get_already_sent_emails", return_value=set()), \
                mock.patch.object(runner, "send_smtp_email",
                                  side_effect=lambda to, *a, **k: sent.append(to) or {"success": True}):
            runner.dispatch_pending_outreach_emails(reg, max_batch=0, delay_sec=0, daily_cap=50, sent_today=0)
        return sent, log

    def test_buyers_first_then_prospects_up_to_their_limit(self):
        leads = [_lead(1, "prospect_signal", 3), _lead(2, "prospect_signal", 4), _lead(3, "client_project", 8),
                 _lead(4, "prospect_signal", 5)]
        sent, log = self._dispatch(leads, cap=2)
        self.assertEqual(sent, ["info@company3.in", "info@company1.in", "info@company2.in"])
        self.assertEqual(leads[3]["email_status"], "NOT_SENT")  # over the prospect limit: tried another day
        sources = [c.kwargs["source"] for c in log.call_args_list]
        self.assertEqual(sources, ["auto outreach", runner.PROSPECT_SOURCE, runner.PROSPECT_SOURCE])

    def test_prospect_limit_counts_earlier_runs_today(self):
        sent, _ = self._dispatch([_lead(1, "prospect_signal", 3), _lead(2, "client_project", 8)],
                                 prospects_already=2, cap=2)
        self.assertEqual(sent, ["info@company2.in"])  # buyers still go out

    def test_prospect_mail_falls_back_to_the_prospect_template(self):
        bodies = []
        reg = mock.Mock(leads=[_lead(1, "prospect_signal", 3)])
        with mock.patch.dict(sys.modules, {"ai_email_generator": None}), \
                mock.patch.object(runner, "AUTO_SEND_EMAIL", True), \
                mock.patch.object(runner, "prospect_emails_sent_today", return_value=0), \
                mock.patch.object(runner, "can_receive_mail", return_value=True), \
                mock.patch.object(runner, "bounces_last_24h", return_value=0), \
                mock.patch.object(runner.followup_store, "safe_log"), \
                mock.patch("email_service.get_already_sent_emails", return_value=set()), \
                mock.patch.object(runner, "send_smtp_email",
                                  side_effect=lambda to, sub, body, **k: bodies.append((sub, body)) or {"success": True}):
            runner.dispatch_pending_outreach_emails(reg, max_batch=0, delay_sec=0, daily_cap=50, sent_today=0)
        self.assertEqual(len(bodies), 1)
        self.assertTrue(bodies[0][0].startswith("Software help for"))
        self.assertIn("I will not write again", bodies[0][1])


if __name__ == "__main__":
    unittest.main()

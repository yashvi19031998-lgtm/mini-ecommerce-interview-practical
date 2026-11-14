"""Freelance Scraper page: run_all_scrapers.py --group freelance runs only freelance sources, never e-mails."""
import os
import sys
import tempfile
import unittest
from unittest import mock

import app
import run_all_scrapers as runner

AUTH = {"X-Demo-User": "true"}


class Groups(unittest.TestCase):
    def test_freelance_group_has_every_freelance_source_and_nothing_else(self):
        names = [c["name"] for c in runner.scrapers_for("freelance")]
        self.assertEqual(len(names), len(runner.SCRAPER_GROUPS["freelance"]))  # each prefix matches a scraper
        self.assertTrue(any(n.startswith("freelancer_api_scraper.py") for n in names))
        for other in ("google_maps_scraper.py", "crm_sources.py", "b2b_portal_scraper.py", "job_portals.py"):
            self.assertFalse(any(n.startswith(other) for n in names), other)
        self.assertEqual(runner.scrapers_for(None), runner.SCRAPERS_CONFIG)
        with self.assertRaises(ValueError):
            runner.scrapers_for("nope")


class _Registry:
    def __init__(self, *_a, **_k):
        self.leads = []

    def load_master(self):
        pass

    def save_master_safely(self):
        return True

    def add_lead(self, raw, default_source=""):
        return "added", raw


class GroupRun(unittest.TestCase):
    def test_runs_only_the_group_skips_enrichment_and_mail(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        old = os.getcwd()
        os.chdir(tmp.name)
        self.addCleanup(os.chdir, old)
        free, other = mock.Mock(return_value=[{"company_name": "Need a React dev"}]), mock.Mock(return_value=[])
        configs = [{"name": "freelancer_api_scraper.py (x)", "func": free, "enabled": True},
                   {"name": "google_maps_scraper.py (y)", "func": other, "enabled": True}]
        extractor = mock.Mock(run_website_enrichment=mock.Mock(return_value=0))
        with mock.patch.object(runner, "SCRAPERS_CONFIG", configs), \
                mock.patch.object(runner, "MasterLeadRegistry", _Registry), \
                mock.patch.object(runner, "log_scraper_run"), \
                mock.patch.object(runner, "lead_quality", None), \
                mock.patch.object(runner, "sync_to_supabase", None), \
                mock.patch.object(runner, "run_email_steps") as mail, \
                mock.patch.dict(sys.modules, {"website_contact_extractor": extractor}), \
                mock.patch("builtins.print") as out:
            runner.run_all_scrapers(send_email=False, group="freelance")
        free.assert_called_once()
        other.assert_not_called()
        extractor.run_website_enrichment.assert_not_called()
        mail.assert_not_called()
        printed = " ".join(str(c.args[0]) for c in out.call_args_list if c.args)
        self.assertIn("RUN_RESULT new=1 collected=1", printed)


class StartEndpoint(unittest.TestCase):
    def setUp(self):
        self.client = app.app.test_client()

    def test_bad_mode_refused(self):
        r = self.client.post("/api/scraper/start", json={"mode": "everything"}, headers=AUTH)
        self.assertEqual(r.status_code, 400)

    def test_freelance_mode_command(self):
        started = {}

        class FakeThread:
            def __init__(self, target, daemon):
                started["target"] = target

            def start(self):
                pass

        with mock.patch.object(app, "scraper_process", None), mock.patch.object(app.threading, "Thread", FakeThread), \
                mock.patch.object(app.subprocess, "Popen") as popen:
            r = self.client.post("/api/scraper/start", json={"mode": "freelance"}, headers=AUTH)
            self.assertEqual(r.status_code, 200)
            popen.return_value.stdout = []
            popen.return_value.returncode = 0
            with mock.patch.object(app.sync_to_supabase, "sync", return_value=True):
                started["target"]()
        cmd = popen.call_args.args[0]
        self.assertEqual(cmd[1:], ["run_all_scrapers.py", "--group", "freelance", "--no-email"])
        kw = popen.call_args.kwargs  # emoji / Hindi in lead titles must not break the live log on Windows
        self.assertEqual((kw["encoding"], kw["errors"], kw["env"]["PYTHONIOENCODING"]), ("utf-8", "replace", "utf-8"))
        self.assertEqual(self.client.get("/api/scraper/status", headers=AUTH).get_json()["mode"], "freelance")


if __name__ == "__main__":
    unittest.main()

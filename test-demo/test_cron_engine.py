"""Cron engine safety (time limits, DB sync before mail, office hours, logs) and the contact finder."""
import datetime
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

import master_cron_runner as m
import website_contact_extractor as w
from lead_normalizer import normalize_email


class Engine(unittest.TestCase):
    def job(self, script="cron_job_email_outreach.py"):
        return m.ScheduledJob(name="Job", script_name=script, interval_sec=3600, description="d")

    def test_office_hours(self):
        tue = datetime.datetime(2026, 11, 17)
        self.assertTrue(m.in_outreach_window(tue.replace(hour=10)))
        self.assertFalse(m.in_outreach_window(tue.replace(hour=19)))
        self.assertFalse(m.in_outreach_window(tue.replace(hour=2)))
        self.assertFalse(m.in_outreach_window(datetime.datetime(2026, 11, 22, 12)))  # Sunday
        self.assertEqual(m.next_outreach_window(tue.replace(hour=22)), datetime.datetime(2026, 11, 18, 10))

    def test_outreach_waits_outside_hours_and_never_runs(self):
        j = self.job()
        with mock.patch.object(m, "in_outreach_window", return_value=False), \
                mock.patch.object(m, "run_logged") as run, mock.patch.object(m, "write_status"):
            self.assertFalse(j.execute())
        run.assert_not_called()
        self.assertIn("WAITING", j.last_status)

    def test_outreach_needs_the_database(self):
        j = self.job()
        with mock.patch.object(m, "in_outreach_window", return_value=True), \
                mock.patch.object(m, "sync_database", return_value=False) as sync, \
                mock.patch.object(m, "run_logged") as run, mock.patch.object(m, "write_status"):
            self.assertFalse(j.execute())
        sync.assert_called_once_with(required=True)
        run.assert_not_called()
        self.assertIn("no mail sent", j.last_status)

    def test_scraper_runs_even_if_sync_fails_and_reports_time_limit(self):
        j = self.job("cron_job_scrapers.py")
        with mock.patch.object(m, "sync_database", return_value=False), \
                mock.patch.object(m, "run_logged", return_value=124) as run, mock.patch.object(m, "write_status"):
            self.assertFalse(j.execute())
        self.assertEqual(run.call_args.args[2], m.JOB_TIMEOUTS["cron_job_scrapers.py"])
        self.assertEqual(j.last_status, "STOPPED (time limit)")

    def test_run_logged_keeps_output_and_stops_a_hung_job(self):
        with tempfile.TemporaryDirectory() as d:
            log = os.path.join(d, "x.log")
            self.assertEqual(m.run_logged([sys.executable, "-c", "print('hello ✓')"], log, 30), 0)
            self.assertIn("hello ✓", open(log, encoding="utf-8").read())
            self.assertEqual(m.run_logged([sys.executable, "-c", "import time; time.sleep(30)"], log, 2), 124)
            self.assertIn("time limit", open(log, encoding="utf-8").read())

    def test_status_file(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(m, "STATUS_FILE", os.path.join(d, "s.json")):
            m.write_status([self.job()])
            data = json.load(open(os.path.join(d, "s.json"), encoding="utf-8"))
        self.assertEqual(data["jobs"][0]["script"], "cron_job_email_outreach.py")


class Contacts(unittest.TestCase):
    HTML = """<html><head><script>var v="core@2.11.8"; var i="logo@2x.png"; var id="1234567890123";</script>
    <script type="application/ld+json">{"telephone": "+91 98250 12345", "email": "sales@acme.co.in"}</script></head>
    <body><a href="mailto:info@acme.co.in?subject=Hi">Mail us</a> <a href="tel:07926401234">Call</a>
    <a href="https://wa.me/919876543210">WhatsApp</a>
    <p>HR: hr [at] acme [dot] co [dot] in. Theme by theme@themeforest.net</p></body></html>"""

    def test_reliable_sources_first_and_no_code_junk(self):
        emails, phones = w.contacts_from_html(self.HTML)
        self.assertEqual(emails[0], "info@acme.co.in")
        self.assertIn("hr@acme.co.in", emails)
        self.assertNotIn("core@2.11.8", emails)
        self.assertFalse(any(e.endswith(".png") for e in emails))
        self.assertEqual(phones[:2], ["079-26401234", "+91 98765 43210"])

    def test_own_domain_first_and_third_parties_dropped(self):
        ranked = w.rank_emails(["devpriyanka.yadav@gmail.com", "care@hometown.in", "dev@kloc.com"], "hometown.in")
        self.assertEqual(ranked, ["care@hometown.in", "devpriyanka.yadav@gmail.com"])
        self.assertEqual(w.rank_emails(["hr@acme.co.in", "info@acme.co.in"], "www.acme.co.in")[0], "info@acme.co.in")
        self.assertEqual(w.rank_emails(["x@partner.com"], "acme.com"), ["x@partner.com"])  # nothing better: keep

    def test_fake_tlds_rejected(self):
        self.assertEqual(normalize_email("care@scale.throug, queries@scale.the, a@b.agency, i@acme.co.in"),
                         "a@b.agency, i@acme.co.in")

    def test_enrichment_skips_non_leads_and_recent_checks_and_saves(self):
        import csv
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "m.csv")
            rows = [
                {"lead_id": "L1", "website": "https://acme.in", "email": "", "mobile_number": "", "ai_category": "client_project", "first_seen_at": "2026-11-17"},
                {"lead_id": "L2", "website": "https://junk.in", "email": "", "mobile_number": "", "ai_category": "irrelevant", "first_seen_at": "2026-11-17"},
                {"lead_id": "L3", "website": "https://old.in", "email": "", "mobile_number": "", "ai_category": "prospect_signal", "first_seen_at": "2026-11-16"},
                {"lead_id": "L4", "website": "https://done.in", "email": "a@done.in", "mobile_number": "+91 98250 12345", "ai_category": "client_project", "first_seen_at": "2026-11-17"},
            ]
            with open(path, "w", newline="", encoding="utf-8-sig") as fh:
                wr = csv.DictWriter(fh, fieldnames=list(rows[0]))
                wr.writeheader()
                wr.writerows(rows)
            checks = os.path.join(d, "checks.json")
            json.dump({"old.in": datetime.date.today().isoformat()}, open(checks, "w"))
            with mock.patch.object(w, "CHECKS_FILE", checks), \
                    mock.patch.object(w, "extract_contacts_from_url", return_value=(["info@acme.in"], ["+91 98765 43210"])) as ex:
                self.assertEqual(w.run_website_enrichment(path, max_seconds=60, max_sites=10), 1)
            self.assertEqual([c.args[0] for c in ex.call_args_list], ["https://acme.in"])  # L2 junk, L3 checked, L4 full
            out = list(csv.DictReader(open(path, encoding="utf-8-sig")))
            self.assertEqual((out[0]["email"], out[0]["mobile_number"]), ("info@acme.in", "+91 98765 43210"))
            self.assertIn("acme.in", json.load(open(checks)))

    def test_enrichment_stops_at_the_site_limit(self):
        import csv
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "m.csv")
            with open(path, "w", newline="", encoding="utf-8-sig") as fh:
                wr = csv.DictWriter(fh, fieldnames=["lead_id", "website", "email", "mobile_number", "ai_category", "first_seen_at"])
                wr.writeheader()
                for i in range(5):
                    wr.writerow({"lead_id": f"L{i}", "website": f"https://s{i}.in", "email": "", "mobile_number": "",
                                 "ai_category": "client_project", "first_seen_at": "2026-11-17"})
            with mock.patch.object(w, "CHECKS_FILE", os.path.join(d, "c.json")), \
                    mock.patch.object(w, "extract_contacts_from_url", return_value=([], [])) as ex:
                w.run_website_enrichment(path, max_seconds=60, max_sites=2)
            self.assertEqual(ex.call_count, 2)


if __name__ == "__main__":
    unittest.main()

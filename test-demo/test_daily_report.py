"""Tests for the nightly report e-mail (daily_report.py). No network, no real files.

python -m unittest test_daily_report -v
"""
import datetime
import os
import unittest
from unittest import mock

import daily_report as dr

DAY = datetime.date(2026, 11, 13)
LEADS = [
    {"lead_id": "LEAD-00001", "company_name": "Acme Foods", "email": "ravi@acmefoods.in, sales@acmefoods.in",
     "source": "Reddit (r/forhire) | Search Engine", "ai_score": "9", "first_seen_at": "2026-11-13 09:00:00",
     "email_status": "SENT", "location": "Ahmedabad", "mobile_number": "+91 98250 12345", "ai_category": "client_project"},
    {"lead_id": "LEAD-00002", "company_name": "Kappa Traders", "email": "k@kappa.in", "source": "Google Maps",
     "ai_score": "7", "first_seen_at": "2026-11-12 09:00:00", "email_status": "FAILED"},
]
SENT = [
    {"email": "ravi@acmefoods.in", "sent_at": "2026-11-13 10:05:00", "subject": "Hello Acme"},
    {"email": "old@x.in", "sent_at": "2026-11-12 23:59:59", "subject": "yesterday"},
    {"email": "=cmd@evil.in", "sent_at": "2026-11-13 11:00:00", "subject": "+SUM(1)"},
]
ACTS = [
    {"type": "email_sent", "lead_id": "LEAD-00001", "lead_email": "ravi@acmefoods.in", "occurred_at": "2026-11-13 10:05:00",
     "source": "auto outreach", "summary": "Email sent: Hello Acme"},
    {"type": "email_sent", "lead_id": "LEAD-00002", "lead_email": "k@kappa.in", "occurred_at": "2026-11-13 15:00:00",
     "source": "followup sequence step 1", "summary": "Follow-up 1"},
    {"type": "reply", "lead_id": "LEAD-00001", "lead_email": "ravi@acmefoods.in", "occurred_at": "2026-11-13 18:00:00",
     "source": "gmail", "summary": "Interested"},
    {"type": "bounce", "lead_id": "", "lead_email": "nobody@gone.in", "occurred_at": "2026-11-13 19:00:00", "source": "gmail"},
    {"type": "reply", "lead_id": "LEAD-00002", "lead_email": "k@kappa.in", "occurred_at": "2026-11-14 00:00:01", "source": "gmail"},
]
RUNS = [
    {"run_id": "R1", "start_time": "2026-11-13 10:00:00", "scraper_name": "reddit_rss_scraper.py (Multi, Subreddit)",
     "status": "Success", "records_collected": "10", "new_leads_added": "2", "duplicates_detected": "8"},
    {"run_id": "R1", "start_time": "2026-11-13 10:01:00", "scraper_name": "google_maps_scraper.py (Maps)",
     "status": "Failed", "records_collected": "0", "new_leads_added": "", "duplicates_detected": "0", "error_summary": "timeout"},
    {"run_id": "R2", "start_time": "2026-11-13 11:00:00", "scraper_name": "reddit_rss_scraper.py (Multi, Subreddit)",
     "status": "Success", "records_collected": "x", "new_leads_added": "1", "duplicates_detected": "0"},
    {"run_id": "R0", "start_time": "2026-11-12 22:00:00", "scraper_name": "reddit_rss_scraper.py", "status": "Success",
     "records_collected": "99", "new_leads_added": "99"},
]
SETTINGS = {"autoSendEmail": True, "maxPendingEmailsPerRun": 0, "excludedCompanies": ["8dots"]}


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.r = dr.build_report(DAY, LEADS, SENT, ACTS, RUNS, SETTINGS)

    def test_day_after_midnight_is_the_day_that_ended(self):
        self.assertEqual(dr.report_day(datetime.datetime(2026, 11, 14, 0, 5, tzinfo=dr.IST)), DAY)
        self.assertEqual(dr.report_day(datetime.datetime(2026, 11, 13, 20, 0, tzinfo=dr.IST)), DAY)

    def test_counts_only_this_day(self):
        t = self.r["totals"]
        self.assertEqual((t["intro"], t["followups"], t["emails_sent"]), (2, 1, 3))
        self.assertEqual((t["replies"], t["bounced_or_opted_out"]), (1, 1))
        self.assertEqual((t["new_leads"], t["hourly_runs"], t["scraper_failures"], t["records_collected"]), (1, 2, 1, 10))

    def test_sent_rows_carry_lead_details(self):
        acme = [r for r in self.r["intro"] if r["email"] == "ravi@acmefoods.in"][0]
        self.assertEqual((acme["company"], acme["lead_id"], acme["source"], acme["how"]),
                         ("Acme Foods", "LEAD-00001", "Reddit", "Auto (hourly run)"))
        unknown = [r for r in self.r["intro"] if r["email"] == "=cmd@evil.in"][0]
        self.assertEqual(unknown["company"], "(not in leads list)")  # never dropped
        self.assertEqual(self.r["followups"][0]["company"], "Kappa Traders")

    def test_scrapers_grouped_by_script_with_commas_in_label(self):
        by = {s["scraper"]: s for s in self.r["scrapers"]}
        self.assertEqual((by["reddit_rss_scraper.py"]["runs"], by["reddit_rss_scraper.py"]["new"]), (2, 3))
        self.assertEqual((by["google_maps_scraper.py"]["failed"], by["google_maps_scraper.py"]["error"]), (1, "timeout"))

    def test_status_block(self):
        st = self.r["status"]
        self.assertEqual((st["per_run_limit"], st["leads_failed_status"], st["daily_cap_used"]), ("no limit", 1, 3))

    def test_test_mail_to_our_own_address_is_not_outreach(self):
        sent = SENT + [{"email": "info@sangeetainfotech.co.in", "sent_at": "2026-11-13 13:12:27", "subject": "[Test]"}]
        r = dr.build_report(DAY, LEADS, sent, ACTS, RUNS, {**SETTINGS, "email": "info@sangeetainfotech.co.in"})
        self.assertEqual((r["totals"]["intro"], r["status"]["test_mails_to_own_address"]), (2, 1))

    def test_empty_day_still_makes_a_report(self):
        r = dr.build_report(datetime.date(2020, 1, 1), [], [], [], [], {})
        subject, body, text = dr.render(r)
        self.assertIn("0 e-mails sent", subject)
        self.assertIn("No e-mail was sent on this day.", body)

    def test_html_is_escaped_and_csv_is_formula_safe(self):
        r = dr.build_report(DAY, [{"lead_id": "L9", "company_name": "<script>x</script>", "email": "a@b.in",
                                   "first_seen_at": "2026-11-13 01:00:00"}],
                            [{"email": "a@b.in", "sent_at": "2026-11-13 02:00:00", "subject": "<b>hi</b>"}], [], [], {})
        _, body, _ = dr.render(r)
        self.assertNotIn("<script>x", body)
        self.assertIn("&lt;script&gt;", body)
        csv_text = dr.sent_csv(self.r)
        self.assertTrue(csv_text.startswith("﻿"))
        self.assertIn("'=cmd@evil.in", csv_text)
        self.assertIn("'+SUM(1)", csv_text)

    def test_missing_files_are_empty_not_errors(self):
        self.assertEqual(dr.read_csv(os.path.join(os.path.dirname(__file__), "no", "such.csv")), [])

    def test_sending_needs_a_login_and_never_touches_the_sent_log(self):
        with mock.patch.dict(os.environ, {"SMTP_USER": "", "SMTP_PASS": ""}):
            with self.assertRaises(RuntimeError):
                dr.send("s", "<p>x</p>", "x", None, "me@x.in")
        fake = mock.MagicMock()
        with mock.patch.dict(os.environ, {"SMTP_USER": "me@gmail.com", "SMTP_PASS": "x"}), \
                mock.patch.object(dr.smtplib, "SMTP", return_value=fake), \
                mock.patch("email_service.record_email_sent", side_effect=AssertionError("report must not be logged")):
            dr.send("s", "<p>x</p>", "x", ("a.csv", "x"), "me@x.in")
        self.assertTrue(fake.sendmail.called)

    def test_main_dry_run_sends_nothing(self):
        with mock.patch.object(dr, "send", side_effect=AssertionError("dry run must not send")), \
                mock.patch.object(dr, "read_csv", return_value=[]), mock.patch.object(dr, "load_env"), \
                mock.patch("builtins.print"):
            self.assertEqual(dr.main(["--date", "2026-11-13", "--dry-run"]), 0)
            self.assertEqual(dr.main(["--date", "13-11-2026", "--dry-run"]), 2)


if __name__ == "__main__":
    unittest.main()

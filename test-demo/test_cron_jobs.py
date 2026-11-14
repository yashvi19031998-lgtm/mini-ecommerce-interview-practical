"""
Unit tests for the 4 Dedicated Production Cron Jobs:
- cron_job_scrapers.py (Multi-Source Business Scraper)
- cron_job_email_outreach.py (Dedicated AI Cold Email Outreach)
- cron_job_daily_report.py (Daily Operations & Pipeline Report)
- cron_job_freelance_scraper.py (Freelancing & Project Leads Scraper)
"""

import unittest
import os
import tempfile
from unittest import mock

import cron_job_scrapers
import cron_job_freelance_scraper
import cron_job_email_outreach
import cron_job_daily_report


class TestCronJobs(unittest.TestCase):

    def test_cron_job_scrapers_execution(self):
        with mock.patch("cron_job_scrapers.run_all_scrapers") as mock_run:
            with self.assertRaises(SystemExit) as cm:
                cron_job_scrapers.main()
            self.assertEqual(cm.exception.code, 0)
            mock_run.assert_called_once_with(send_email=False, group=None)

    def test_cron_job_freelance_scraper_execution(self):
        with mock.patch("cron_job_freelance_scraper.run_all_scrapers") as mock_run:
            with self.assertRaises(SystemExit) as cm:
                cron_job_freelance_scraper.main()
            self.assertEqual(cm.exception.code, 0)
            mock_run.assert_called_once_with(send_email=False, group="freelance")

    def test_cron_job_email_outreach_execution(self):
        with mock.patch("cron_job_email_outreach.run_outreach_only") as mock_outreach:
            with self.assertRaises(SystemExit) as cm:
                cron_job_email_outreach.main()
            self.assertEqual(cm.exception.code, 0)
            mock_outreach.assert_called_once()

    def test_cron_job_daily_report_generation_and_dispatch(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_report_dir = os.path.join(tmp_dir, "daily_reports")
            mock_metrics = {
                "date": "2026-11-14",
                "total_leads_in_db": 500,
                "new_leads_today": 25,
                "total_leads_with_email": 350,
                "total_leads_with_phone": 300,
                "email_enrichment_rate_pct": 70.0,
                "source_breakdown": {"Google Maps": 15, "Freelance Feeds": 10},
                "intent_breakdown": {"high": 12, "medium": 10, "low": 3},
                "outreach_emails_sent_today": 20,
                "sent_status_breakdown": {"SENT": 20}
            }

            with mock.patch("cron_job_daily_report.REPORTS_DIR", temp_report_dir), \
                 mock.patch("cron_job_daily_report.generate_daily_metrics", return_value=mock_metrics), \
                 mock.patch("cron_job_daily_report.send_smtp_email", return_value={"success": True}) as mock_send, \
                 mock.patch("cron_job_daily_report.load_settings", return_value={"companyName": "Sangeeta Infotech", "email": "admin@example.com"}):

                cron_job_daily_report.run_daily_report()

                # Verify email was dispatched to admin
                mock_send.assert_called_once()
                args, kwargs = mock_send.call_args
                self.assertEqual(args[0], "admin@example.com")
                self.assertIn("Daily Lead Generation & Outreach Summary", args[1])
                self.assertIn("Sangeeta Infotech", args[1])
                self.assertIn("25", args[2])

                # Verify snapshot file was written
                report_file = os.path.join(temp_report_dir, "report_2026-11-14.json")
                self.assertTrue(os.path.exists(report_file))


if __name__ == "__main__":
    unittest.main()


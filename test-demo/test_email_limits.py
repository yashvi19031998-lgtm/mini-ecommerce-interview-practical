"""Hourly-run e-mail limits: no per-run limit (0), daily Gmail cap, stop after repeated failures.

python -m unittest test_email_limits -v

No network and no real e-mail: send_smtp_email and the MX check are mocked; the registry is in memory.
"""
import csv
import datetime
import os
import shutil
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

import run_all_scrapers as runner


def lead(i):
    return {"lead_id": f"LEAD-{i:05d}", "company_name": f"Acme {i} Foods", "email": f"owner{i}@acme{i}.in",
            "email_status": "NOT_SENT", "status": "NEW", "location": "Ahmedabad"}


class DispatchLimitTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="email_limits_")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.calls = []
        patches = [
            mock.patch.object(runner, "AUTO_SEND_EMAIL", True),
            mock.patch.object(runner, "is_outreach_ready", lambda l: True),
            mock.patch.object(runner, "can_receive_mail", lambda e: True),
            mock.patch.object(runner, "load_settings", lambda: {"excludedCompanies": ["8dots"]}),
            mock.patch.object(runner, "format_signature", lambda s=None: ""),
            mock.patch.object(runner.followup_store, "safe_log", lambda *a, **k: None),
            mock.patch("email_service.get_already_sent_emails", return_value=set()),
            mock.patch.object(runner.os.path, "exists", lambda p: False if p == "leads_new.csv" else os.path.exists(p)),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def run_with(self, n_leads, result=None, **kw):
        reg = SimpleNamespace(leads=[lead(i) for i in range(1, n_leads + 1)])
        def fake_send(to, sub, body, bypass_duplicate_check=False, company_name=""):
            self.calls.append(to)
            return result(to) if result else {"success": True}
        with mock.patch.object(runner, "send_smtp_email", side_effect=fake_send):
            sent = runner.dispatch_pending_outreach_emails(reg, delay_sec=0, **kw)
        return sent, reg

    def test_zero_means_every_qualified_lead(self):
        sent, reg = self.run_with(40, max_batch=0, daily_cap=300, sent_today=0)
        self.assertEqual(sent, 40)
        self.assertTrue(all(l["email_status"] == "SENT" for l in reg.leads))

    def test_per_run_limit_still_works(self):
        sent, _ = self.run_with(40, max_batch=5, daily_cap=300, sent_today=0)
        self.assertEqual((sent, len(self.calls)), (5, 5))

    def test_daily_cap_counts_mail_already_sent_today(self):
        sent, _ = self.run_with(40, max_batch=0, daily_cap=300, sent_today=290)
        self.assertEqual(sent, 10)
        self.calls.clear()
        sent, _ = self.run_with(40, max_batch=0, daily_cap=300, sent_today=300)
        self.assertEqual((sent, self.calls), (0, []))

    def test_stops_after_three_failures_in_a_row(self):
        sent, reg = self.run_with(40, result=lambda to: {"success": False, "error": "Username and Password not accepted"},
                                  max_batch=0, daily_cap=300, sent_today=0)
        self.assertEqual((sent, len(self.calls)), (0, runner.MAX_CONSECUTIVE_SEND_FAILURES))
        self.assertEqual(sum(l["email_status"] == "FAILED" for l in reg.leads), runner.MAX_CONSECUTIVE_SEND_FAILURES)

    def test_a_success_resets_the_failure_count(self):
        pattern = iter([False, False, True] * 20)
        sent, _ = self.run_with(12, result=lambda to: {"success": next(pattern), "error": "x"},
                                max_batch=0, daily_cap=300, sent_today=0)
        self.assertEqual((sent, len(self.calls)), (4, 12))

    def test_do_not_contact_block_is_not_counted_as_a_failure(self):
        sent, reg = self.run_with(6, result=lambda to: {"success": False, "excluded": True, "error": "blacklist"},
                                  max_batch=0, daily_cap=300, sent_today=0)
        self.assertEqual(len(self.calls), 6)  # all tried: a block is not a broken login
        self.assertTrue(all(l["email_status"] == "EXCLUDED_COMPANY" for l in reg.leads))


class SentTodayTests(unittest.TestCase):
    def test_counts_only_todays_rows(self):
        tmp = tempfile.mkdtemp(prefix="sent_today_")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        path = os.path.join(tmp, "sent_emails.csv")
        today = datetime.date.today().strftime("%Y-%m-%d")
        with open(path, "w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["email", "sent_at", "subject"])
            w.writerows([["a@x.in", f"{today} 09:00:00", "s"], ["b@x.in", f"{today} 10:00:00", "s"],
                         ["c@x.in", "2020-01-01 10:00:00", "s"]])
        self.assertEqual(runner.emails_sent_today(path), 2)
        self.assertEqual(runner.emails_sent_today(os.path.join(tmp, "missing.csv")), 0)


if __name__ == "__main__":
    unittest.main()

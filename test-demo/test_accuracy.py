"""Tests for lead-accuracy features: full post text, post dates, ideal-client prompt, stale-lead cap.

    python -m unittest test_accuracy -v
"""
import csv
import datetime
import json
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

import lead_normalizer as ln
import lead_quality as lq
import slack_notifier as sn


def _days_ago(n):
    return (datetime.datetime.now() - datetime.timedelta(days=n)).strftime("%Y-%m-%d %H:%M:%S")


class DatesAndText(unittest.TestCase):
    def test_normalize_datetime_formats(self):
        self.assertEqual(ln.normalize_datetime("2026-10-20"), "2026-10-20 00:00:00")
        self.assertRegex(ln.normalize_datetime("Tue, 20 Oct 2026 10:00:00 +0000"), r"^2026-10-20 \d\d:\d\d:00$")
        self.assertRegex(ln.normalize_datetime("2026-10-20T10:00:00Z"), r"^2026-10-20 ")
        self.assertRegex(ln.normalize_datetime("1792483200000"), r"^2026-")  # epoch ms
        self.assertEqual(ln.normalize_datetime("not a date"), "")
        self.assertEqual(ln.normalize_datetime(None), "")

    def test_posted_at_from_source_fields(self):
        self.assertEqual(ln.normalize_lead_record({"company_name": "A", "Posted Date": "2026-10-01"})["posted_at"],
                         "2026-10-01 00:00:00")
        self.assertEqual(ln.normalize_lead_record({"company_name": "A", "Date": "2026-10-02 08:30:00"})["posted_at"],
                         "2026-10-02 08:30:00")
        self.assertEqual(ln.normalize_lead_record({"company_name": "A"})["posted_at"], "")

    def test_long_description_kept_for_ai(self):
        text = "Need a Flutter app. " * 60 + "Budget $4000, email cto@shop.in"
        r = ln.normalize_lead_record({"company_name": "A", "description": text})
        self.assertIn("Budget $4000", r["description"])  # the end of the post is no longer cut off

    def test_merge_fills_missing_post_date(self):
        with tempfile.TemporaryDirectory() as d:
            reg = ln.MasterLeadRegistry(os.path.join(d, "m.csv"))
            reg.add_lead({"company_name": "Acme", "email": "info@acme.in"})
            outcome, lead = reg.add_lead({"company_name": "Acme", "email": "info@acme.in", "posted_at": "2026-11-01"})
            self.assertEqual(lead["posted_at"], "2026-11-01 00:00:00")

    def test_lead_age_prefers_post_date(self):
        lead = {"posted_at": _days_ago(20), "first_seen_at": _days_ago(1)}
        self.assertAlmostEqual(ln.lead_age_days(lead), 20, delta=0.1)
        self.assertIsNone(ln.lead_age_days({}))


class PromptAndStaleRules(unittest.TestCase):
    def _write(self, path, rows):
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=ln.MASTER_FIELDNAMES)
            w.writeheader()
            for r in rows:
                w.writerow({k: r.get(k, "") for k in ln.MASTER_FIELDNAMES})

    def _fake_client(self, score):
        payload = json.dumps({"category": "client_project", "score": score, "summary": "Needs app",
                              "requirement": "App", "tech_stack": "", "budget": "", "reason": "clear need"})
        client = mock.MagicMock()
        client.beta.messages.create.return_value = SimpleNamespace(
            stop_reason="end_turn", content=[SimpleNamespace(type="text", text=payload)])
        return client

    def test_prompt_includes_ideal_client_date_and_post_age(self):
        lead = {"lead_id": "L1", "company_name": "Acme", "posted_at": _days_ago(3)}
        client = self._fake_client(8)
        lq.qualify_one(client, lead)
        kwargs = client.beta.messages.create.call_args.kwargs
        self.assertIn("Our ideal client:", kwargs["system"])
        self.assertIn(lq.IDEAL_CLIENT_PROFILE[:40], kwargs["system"])
        user_msg = kwargs["messages"][0]["content"]
        self.assertIn(f"Today's date: {datetime.date.today().isoformat()}", user_msg)
        self.assertIn("Posted: ", user_msg)
        self.assertIn("3 days ago", user_msg)

    def test_stale_lead_score_capped_and_not_contacted(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "m.csv")
            self._write(path, [
                {"lead_id": "LEAD-00001", "company_name": "Old", "email": "a@old.in", "posted_at": _days_ago(30)},
                {"lead_id": "LEAD-00002", "company_name": "Fresh", "email": "b@fresh.in", "posted_at": _days_ago(2)},
            ])
            with mock.patch.object(lq, "_get_client", return_value=self._fake_client(9)):
                stats = lq.run(path)
            leads = {l["lead_id"]: l for l in ln.MasterLeadRegistry(path).leads}
            self.assertEqual(leads["LEAD-00001"]["ai_score"], str(lq.STALE_SCORE_CAP))
            self.assertTrue(leads["LEAD-00001"]["ai_reason"].startswith("[Stale"))
            self.assertEqual(leads["LEAD-00002"]["ai_score"], "9")
            self.assertEqual(stats["outreach_ready"], 1)  # only the fresh lead

    def test_lead_that_goes_stale_later_is_not_emailed_or_alerted(self):
        lead = {"ai_category": "client_project", "ai_score": "9", "email": "a@b.in", "posted_at": _days_ago(20)}
        self.assertFalse(lq.is_outreach_ready(lead))
        self.assertFalse(sn.is_hot_lead(lead))
        lead["posted_at"] = _days_ago(1)
        self.assertTrue(lq.is_outreach_ready(lead))
        self.assertTrue(sn.is_hot_lead(lead))


if __name__ == "__main__":
    unittest.main()

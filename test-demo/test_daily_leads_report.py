"""Reports > Daily Leads & Mail: per day found / mailed / pending / no e-mail / blocked, with a score band."""
import datetime
import unittest
from unittest import mock

import app
import daily_leads_report as re_

AUTH = {"X-Demo-User": "true"}
NOW = datetime.datetime(2026, 11, 16, 12, 0, 0)


def lead(i, day, score="", email="", status="NOT_SENT", source="Reddit (r/forhire)"):
    return {"id": f"L{i}", "lead_id": f"L{i}", "company_name": f"Lead {i}", "email": email, "email_status": status,
            "ai_score": score, "first_seen_at": f"{day} 10:00:00", "source": source, "status": "NEW"}


LEADS = [
    lead(1, "2026-11-16", "8", "a@acme.in", "SENT"),         # mailed (status)
    lead(2, "2026-11-16", "9", "b@acme.in"),                 # mailed (only in the sent log)
    lead(3, "2026-11-16", "7", "c@acme.in"),                 # pending
    lead(4, "2026-11-16", "5"),                              # no e-mail
    lead(5, "2026-11-15", "2", "x@bad.in", "INVALID"),       # blocked
    lead(6, "2026-11-15", "", "d@acme.in"),                  # pending, not scored
    lead(7, "2026-10-01", "9", "old@acme.in"),               # outside the 7-day window
]
SENT = [{"email": "b@acme.in", "sent_at": "2026-11-16 09:00:00", "subject": "Hi"},
        {"email": "z@other.in", "sent_at": "2026-11-15 11:00:00", "subject": "Hi"}]


class Engine(unittest.TestCase):
    def test_per_day_counts(self):
        r = re_.daily_leads(LEADS, SENT, {"preset": "7d"}, now=NOW)
        rows = {x["day"]: x for x in r["rows"]}
        self.assertEqual(len(r["rows"]), 7)  # every day of the window, newest first
        self.assertEqual(r["rows"][0]["day"], "2026-11-16")
        d16, d15 = rows["2026-11-16"], rows["2026-11-15"]
        self.assertEqual((d16["found"], d16["mailed"], d16["pending"], d16["no_email"], d16["blocked"]), (4, 2, 1, 1, 0))
        self.assertEqual((d16["high"], d16["medium"]), (3, 1))
        self.assertEqual((d15["found"], d15["pending"], d15["blocked"], d15["unscored"], d15["low"]), (2, 1, 1, 1, 1))
        self.assertEqual((d16["mails_sent_that_day"], d15["mails_sent_that_day"]), (1, 1))
        self.assertEqual(r["totals"]["found"], 6)

    def test_score_band(self):
        r = re_.daily_leads(LEADS, SENT, {"preset": "7d"}, band="high", now=NOW)
        self.assertEqual((r["totals"]["found"], r["totals"]["mailed"], r["totals"]["pending"]), (3, 2, 1))
        r = re_.daily_leads(LEADS, SENT, {"preset": "7d"}, band="unscored", now=NOW)
        self.assertEqual(r["totals"]["found"], 1)
        with self.assertRaises(ValueError):
            re_.daily_leads(LEADS, SENT, {"preset": "7d"}, band="huge", now=NOW)

    def test_custom_dates_and_long_ranges(self):
        r = re_.daily_leads(LEADS, SENT, {"date_from": "2026-10-01", "date_to": "2026-10-01"}, now=NOW)
        self.assertEqual([x["day"] for x in r["rows"]], ["2026-10-01"])
        r = re_.daily_leads(LEADS, SENT, {"preset": "all"}, now=NOW)  # long range: only days with data
        self.assertEqual({x["day"] for x in r["rows"]}, {"2026-11-16", "2026-11-15", "2026-10-01"})

    def test_list(self):
        r = re_.daily_leads_list(LEADS, SENT, "2026-11-16", "mailed", {"preset": "7d"}, now=NOW)
        self.assertEqual([i["id"] for i in r["items"]], ["L2", "L1"])  # highest score first
        r = re_.daily_leads_list(LEADS, SENT, "2026-11-16", "pending", {}, band="high", now=NOW)
        self.assertEqual([(i["id"], i["mail"]) for i in r["items"]], [("L3", "pending")])
        with self.assertRaises(ValueError):
            re_.daily_leads_list(LEADS, SENT, "16-11-2026", "found", now=NOW)
        with self.assertRaises(ValueError):
            re_.daily_leads_list(LEADS, SENT, "2026-11-16", "lost", now=NOW)


class Endpoints(unittest.TestCase):
    def setUp(self):
        self.client = app.app.test_client()
        p = mock.patch.object(app, "_report_context", return_value=(LEADS, [], SENT, []))
        p.start()
        self.addCleanup(p.stop)

    def test_endpoints(self):
        r = self.client.get("/api/reports/daily-leads?date_from=2026-11-15&date_to=2026-11-16&band=high", headers=AUTH)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["totals"]["found"], 3)
        r = self.client.get("/api/reports/daily-leads/list?day=2026-11-15&state=blocked", headers=AUTH).get_json()
        self.assertEqual([i["id"] for i in r["items"]], ["L5"])
        self.assertEqual(self.client.get("/api/reports/daily-leads?band=x", headers=AUTH).status_code, 400)
        self.assertEqual(self.client.get("/api/reports/daily-leads/list?day=x", headers=AUTH).status_code, 400)


if __name__ == "__main__":
    unittest.main()

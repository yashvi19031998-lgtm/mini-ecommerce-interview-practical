"""Reports > Summary (report_summary.py) and its API."""
import datetime
import unittest
from unittest import mock

import report_summary as rs
from test_lead_status import lead, act

TODAY = datetime.date(2026, 11, 18)


def leads():
    return [
        lead(lead_id="A", email="a@acme.in", mobile_number="9825012345", ai_category="client_project", ai_score="8",
             first_seen_at="2026-11-10 10:00:00", source="Reddit (r/forhire)"),
        lead(lead_id="B", email="b@shop.in", ai_category="prospect_signal", ai_score="5", company_name="Need SEO and Google Ads",
             first_seen_at="2026-11-12 10:00:00", source="Google Maps"),
        lead(lead_id="C", ai_category="job_seeker", ai_score="2", first_seen_at="2026-11-15 10:00:00", source="Google Maps"),
        lead(lead_id="D", ai_category="hiring_developer", ai_score="9", first_seen_at="2026-09-01 10:00:00", status="WON"),
    ]


SENT = [{"email": "a@acme.in", "sent_at": "2026-11-11 10:00:00"}]
ACTS = [act("call", "2026-11-12 11:00:00", lead_id="A"), act("reply", "2026-11-13 09:00:00", lead_id="A")]


class Build(unittest.TestCase):
    def test_client_types(self):
        self.assertEqual([rs.client_type(l) for l in leads()], ["it_project", "digital", "other", "hiring"])

    def test_funnel_work_and_days(self):
        r = rs.build(leads(), SENT, ACTS, {"preset": "30d"}, today=TODAY)
        f = {x["key"]: x["count"] for x in r["funnel"]}
        self.assertEqual((f["found"], f["contacted"], f["phone"], f["replied"], f["won"]), (3, 1, 1, 1, 0))  # D found in Sept
        self.assertEqual((r["work"]["mails"], r["work"]["calls"], r["work"]["replies_received"]), (1, 1, 1))
        self.assertEqual(len(r["by_day"]), 30)
        day = next(d for d in r["by_day"] if d["day"] == "2026-11-12")
        self.assertEqual((day["found"], day["contacted"]), (1, 1))
        self.assertTrue(r["highlights"])

    def test_filters(self):
        r = rs.build(leads(), SENT, ACTS, {"preset": "all", "client_type": "hiring"}, today=TODAY)
        self.assertEqual(r["funnel"][0]["count"], 1)
        self.assertEqual(r["funnel"][-1]["count"], 1)  # won
        r = rs.build(leads(), SENT, ACTS, {"preset": "all", "source": "Google Maps", "band": "warm"}, today=TODAY)
        self.assertEqual(r["funnel"][0]["count"], 1)
        r = rs.build(leads(), SENT, ACTS, {"date_from": "2026-11-12", "date_to": "2026-11-15"}, today=TODAY)
        self.assertEqual(r["funnel"][0]["count"], 2)
        for bad in ({"client_type": "x"}, {"band": "x"}, {"date_from": "2026-11-20", "date_to": "2026-11-01"}, {"date_from": "junk"}):
            with self.assertRaises(ValueError):
                rs.build(leads(), [], [], bad, today=TODAY)

    def test_empty_period(self):
        r = rs.build([], [], [], {"preset": "today"}, today=TODAY)
        self.assertIn("No leads were found", r["highlights"][0])

    def test_insight_falls_back_to_rules(self):
        r = rs.build(leads(), SENT, ACTS, {"preset": "30d"}, today=TODAY)
        with mock.patch.dict("os.environ", {"ANTHROPIC_API_KEY": "", "ANTHROPIC_AUTH_TOKEN": "", "GEMINI_API_KEY": ""}):
            out = rs.insight(r)
        self.assertEqual(out["by"], "rules")
        self.assertTrue(out["text"].startswith("- "))

    def test_insight_sends_no_contact_details(self):
        r = rs.build(leads(), SENT, ACTS, {"preset": "30d"}, today=TODAY)
        seen = {}

        class Resp:
            status_code = 200
            def json(self):
                return {"candidates": [{"content": {"parts": [{"text": "- fine"}]}}]}

        def post(url, json=None, **k):
            seen["body"] = str(json)
            return Resp()
        with mock.patch.dict("os.environ", {"ANTHROPIC_API_KEY": "", "ANTHROPIC_AUTH_TOKEN": "", "GEMINI_API_KEY": "k"}):
            out = rs.insight(r, post=post)
        self.assertEqual(out["by"], "ai")
        self.assertNotIn("a@acme.in", seen["body"])
        self.assertNotIn("98250", seen["body"])


class Api(unittest.TestCase):
    def test_endpoint(self):
        import app
        app.app.config["TESTING"] = True
        c = app.app.test_client()
        c.environ_base["HTTP_X_DEMO_USER"] = "true"
        with mock.patch.object(app, "_report_context", return_value=(leads(), [], SENT, ACTS)):
            self.assertEqual(c.get("/api/reports/overview?preset=all").status_code, 200)
            self.assertEqual(c.get("/api/reports/overview?band=zz").status_code, 400)
            with mock.patch.dict("os.environ", {"ANTHROPIC_API_KEY": "", "ANTHROPIC_AUTH_TOKEN": "", "GEMINI_API_KEY": ""}):
                self.assertEqual(c.post("/api/reports/overview/insight", json={"preset": "all"}).get_json()["by"], "rules")


if __name__ == "__main__":
    unittest.main()

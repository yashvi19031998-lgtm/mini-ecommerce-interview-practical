"""Pending channels (email / call / whatsapp), the extra report filters, and a bulk e-mail that keeps going
when one lead fails."""
import unittest
from unittest import mock

import app
import lead_status as ls
from test_lead_status import lead, act


def pending(l, sent=(), acts=()):
    ctx = ls.build_context(list(sent), list(acts))
    return ls.pending_channels(l, ctx, ls.stage_of(l, ctx)["stage"])


class Pending(unittest.TestCase):
    def test_channels(self):
        self.assertEqual(pending(lead(email="a@acme.in", mobile_number="9825012345")), ["email", "call", "whatsapp"])
        sent = [{"email": "a@acme.in", "sent_at": "2026-11-16 10:00:00"}]
        self.assertEqual(pending(lead(email="a@acme.in", mobile_number="9825012345"), sent), ["call", "whatsapp"])
        self.assertEqual(pending(lead(email="a@acme.in", mobile_number="9825012345"), sent, [act("whatsapp", "2026-11-16 11:00:00")]), ["call"])
        self.assertEqual(pending(lead(email="a@acme.in", email_status="INVALID")), [])
        self.assertEqual(pending(lead(mobile_number="12345")), [])  # too short to be a phone
        self.assertEqual(pending(lead(email="a@acme.in", ai_category="job_seeker")), [])  # not a fit
        self.assertEqual(pending(lead(email="a@acme.in", status="LOST")), [])

    def test_annotate_carries_pending(self):
        out = ls.annotate([lead(email="a@acme.in")], [], [])
        self.assertEqual(out[0]["pending"], ["email"])


class ReportFilter(unittest.TestCase):
    leads = [
        lead(lead_id="A", email="a@acme.in", ai_score="8", location="Ahmedabad, Gujarat", source="Reddit (r/forhire)", ai_category="client_project"),
        lead(lead_id="B", mobile_number="9825012345", ai_score="3", location="Surat", source="Google Maps", ai_category="prospect_signal"),
        lead(lead_id="C", email="c@x.in", ai_score="5", location="Pune", source="Job Portal (Shine)", ai_category="hiring_developer"),
    ]

    def ids(self, **args):
        return [l["lead_id"] for l in app.report_lead_filter(self.leads, [], [], args)]

    def test_each_filter(self):
        self.assertEqual(self.ids(pending="email"), ["A", "C"])
        self.assertEqual(self.ids(pending="call"), ["B"])
        self.assertEqual(self.ids(temp="hot"), ["A"])
        self.assertEqual(self.ids(city="ahmedabad"), ["A"])
        self.assertEqual(self.ids(client_type="hiring"), ["C"])
        self.assertEqual(self.ids(next_step="call_pending"), ["B"])
        self.assertEqual(self.ids(source="Reddit,Google Maps"), ["A", "B"])
        self.assertEqual(self.ids(source="Reddit"), ["A", "B", "C"])  # one source: left to the report itself
        self.assertEqual(self.ids(), ["A", "B", "C"])
        for bad in ({"pending": "fax"}, {"temp": "x"}, {"client_type": "x"}, {"next_step": "x"}):
            with self.assertRaises(ValueError):
                app.report_lead_filter(self.leads, [], [], bad)

    def test_report_endpoint_uses_them(self):
        app.app.config["TESTING"] = True
        c = app.app.test_client()
        c.environ_base["HTTP_X_DEMO_USER"] = "true"
        with mock.patch.object(app, "read_leads", return_value=self.leads), \
                mock.patch.object(app.reports_engine, "load_sent", return_value=[]), \
                mock.patch.object(app.reports_engine, "load_activities", return_value=[]), \
                mock.patch.object(app.reports_engine, "load_runs", return_value=[]):
            all_rows = c.get("/api/reports/daily-leads?preset=all").get_json()["totals"]["found"]
            email = c.get("/api/reports/daily-leads?preset=all&pending=email").get_json()["totals"]["found"]
            self.assertEqual((all_rows, email), (3, 2))
            self.assertEqual(c.get("/api/reports/daily-leads?preset=all&pending=fax").status_code, 400)
            # /api/leads is not a report: the filter keys are ignored there
            self.assertEqual(len(c.get("/api/leads?pending=email").get_json()["leads"]), 3)


class BulkKeepsGoing(unittest.TestCase):
    def test_one_bad_lead_does_not_stop_the_rest(self):
        leads = [{"id": f"L{i}", "Email": f"x{i}@acme{i}.in", "Company Name": f"Acme {i}"} for i in range(4)]

        def send(to, *a, **k):
            if to.startswith("x1@"):
                raise RuntimeError("boom")
            return {"success": True}
        with mock.patch.object(app, "read_leads", return_value=leads), \
                mock.patch.object(app, "send_smtp_email", side_effect=send), \
                mock.patch.object(app, "update_lead_record", return_value=True), \
                mock.patch.object(app.followup_store, "safe_log"), \
                mock.patch.object(app, "load_settings", return_value={}), \
                mock.patch.object(app, "format_signature", return_value=""):
            job = {"job_id": "t", "total": 4, "processed": 0, "sent": 0, "failed": 0, "not_verified": 0, "skipped": 0,
                   "done": False, "stopped_reason": "", "results": []}
            import run_all_scrapers
            with mock.patch.object(run_all_scrapers, "emails_sent_today", return_value=0):
                app._run_bulk_job(job, [l["id"] for l in leads], "Hi {company}", "Hello", 0)
        self.assertTrue(job["done"])
        self.assertEqual((job["sent"], job["failed"], job["stopped_reason"]), (3, 1, ""))
        bad = next(r for r in job["results"] if r["id"] == "L1")
        self.assertIn("boom", bad["error"])


class BulkBlocked(unittest.TestCase):
    def test_company_rule_is_a_skip_not_a_failure_and_does_not_mark_sent(self):
        leads = [{"id": f"L{i}", "Email": f"x{i}@acme.in", "Company Name": "Acme"} for i in range(4)]
        updates = []
        with mock.patch.object(app, "read_leads", return_value=leads),                 mock.patch.object(app, "send_smtp_email", return_value={"success": False, "blocked": True, "error": "Not sent: company"}),                 mock.patch.object(app, "update_lead_record", side_effect=lambda lid, f: updates.append(f) or True),                 mock.patch.object(app.followup_store, "safe_log"),                 mock.patch.object(app, "load_settings", return_value={}),                 mock.patch.object(app, "format_signature", return_value=""):
            job = {"job_id": "t", "total": 4, "processed": 0, "sent": 0, "failed": 0, "not_verified": 0, "skipped": 0,
                   "done": False, "stopped_reason": "", "results": []}
            import run_all_scrapers
            with mock.patch.object(run_all_scrapers, "emails_sent_today", return_value=0):
                app._run_bulk_job(job, [l["id"] for l in leads], "Hi", "Hello", 0)
        self.assertEqual((job["sent"], job["failed"], job["skipped"], job["stopped_reason"]), (0, 0, 4, ""))
        self.assertEqual({r["reason"] for r in job["results"]}, {"blocked"})
        self.assertEqual(updates, [])  # never marked as sent


if __name__ == "__main__":
    unittest.main()

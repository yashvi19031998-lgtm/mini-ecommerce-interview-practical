"""Tests for FollowUp History (followup_store.py + /api/followups/* endpoints). No network.

    python -m unittest test_followups -v
"""
import csv
import datetime
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

import followup_store as fs

TS = "%Y-%m-%d %H:%M:%S"


def _day(offset_days, hour=10):
    d = datetime.datetime.now().replace(hour=hour, minute=0, second=0, microsecond=0)
    return (d + datetime.timedelta(days=offset_days)).strftime(TS)


class StoreTestCase(unittest.TestCase):
    """Points the store at a temporary activity file."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "logs", "followup_activity.csv")
        self.patch = mock.patch.object(fs, "ACTIVITY_FILE", self.path)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()


class Activities(StoreTestCase):
    def test_add_manual_activity(self):
        row = fs.add_activity("LEAD-1", "call", "  Spoke   to CTO  ", details="Wants a quote",
                              lead_name="Acme", lead_email="a@acme.in")
        self.assertEqual(row["summary"], "Spoke to CTO")
        self.assertTrue(row["activity_id"].startswith("ACT-"))
        saved = fs._read_all()
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0]["details"], "Wants a quote")

    def test_validation(self):
        cases = [
            (dict(lead_id="L", activity_type="fax", summary="x"), "Activity type"),
            (dict(lead_id="L", activity_type="email_sent", summary="x"), "Activity type"),  # system-only
            (dict(lead_id="L", activity_type="call", summary="   "), "Summary is required"),
            (dict(lead_id="", activity_type="call", summary="x"), "lead is required"),
            (dict(lead_id="L", activity_type="call", summary="x", details="d" * 2001), "Details"),
            (dict(lead_id="L", activity_type="call", summary="x", occurred_at="not a date"), "not valid"),
            (dict(lead_id="L", activity_type="call", summary="x", occurred_at=_day(2)), "future"),
        ]
        for kwargs, msg in cases:
            with self.subTest(msg=msg):
                with self.assertRaises(fs.FollowupError) as ctx:
                    fs.add_activity(**kwargs)
                self.assertIn(msg, str(ctx.exception))
        self.assertEqual(fs._read_all(), [])

    def test_summary_truncated(self):
        row = fs.add_activity("L", "note", "s" * 400)
        self.assertEqual(len(row["summary"]), fs.MAX_SUMMARY)

    def test_past_activity_date_kept(self):
        row = fs.add_activity("L", "meeting", "Demo done", occurred_at="2026-10-01 15:30")
        self.assertEqual(row["occurred_at"], "2026-10-01 15:30:00")

    def test_safe_log_never_raises(self):
        self.assertIsNotNone(fs.safe_log("L", "status_change", "Status: NEW → CONTACTED"))
        self.assertIsNone(fs.safe_log("L", "status_change", ""))  # invalid -> logged as None, no exception


class Followups(StoreTestCase):
    def test_schedule_and_buckets(self):
        # A follow-up planned 5 days ago for 2 days ago is overdue today (new ones can't be in the past)
        with mock.patch.object(fs, "_now", return_value=datetime.datetime.now() - datetime.timedelta(days=5)):
            fs.schedule_followup("L1", _day(-2), "Overdue one")
        fs.schedule_followup("L2", _day(0, hour=18), "Today")
        fs.schedule_followup("L3", _day(3), "Soon")
        fs.schedule_followup("L4", _day(30), "Later")
        rows = fs._read_all()
        self.assertEqual(len(rows), 4)
        buckets = {r["lead_id"]: r["bucket"] for r in fs.queue()}
        self.assertEqual(buckets, {"L1": "overdue", "L2": "today", "L3": "upcoming", "L4": "later"})
        self.assertEqual([r["lead_id"] for r in fs.queue("today")], ["L2"])
        s = fs.summary()
        self.assertEqual((s["overdue"], s["today"], s["upcoming"], s["later"], s["pending"]), (1, 1, 1, 1, 4))

    def test_past_due_rejected_by_validation(self):
        with mock.patch.object(fs, "_now", return_value=datetime.datetime.now() + datetime.timedelta(days=5)):
            with self.assertRaises(fs.FollowupError):
                fs.schedule_followup("L1", _day(0), "x")
        for bad in ("", "tomorrow-ish", _day(400)):
            with self.subTest(bad=bad):
                with self.assertRaises(fs.FollowupError):
                    fs.schedule_followup("L1", bad, "x")

    def test_date_only_defaults_to_10am(self):
        row = fs.schedule_followup("L1", _day(1)[:10], "x")
        self.assertTrue(row["due_at"].endswith("10:00:00"))

    def test_new_schedule_cancels_previous_pending(self):
        first = fs.schedule_followup("L1", _day(2), "first")
        second = fs.schedule_followup("L1", _day(5), "second")
        rows = {r["activity_id"]: r for r in fs._read_all()}
        self.assertEqual(rows[first["activity_id"]]["followup_status"], "cancelled")
        self.assertEqual(rows[second["activity_id"]]["followup_status"], "pending")
        self.assertEqual(len(fs.queue()), 1)

    def test_done_cancel_reschedule(self):
        a = fs.schedule_followup("L1", _day(1), "a")
        b = fs.schedule_followup("L2", _day(1), "b")
        c = fs.schedule_followup("L3", _day(1), "c")
        self.assertEqual(fs.update_followup(a["activity_id"], "done")["followup_status"], "done")
        self.assertEqual(fs.update_followup(b["activity_id"], "cancel")["followup_status"], "cancelled")
        moved = fs.update_followup(c["activity_id"], "reschedule", _day(9))
        self.assertEqual(moved["due_at"], _day(9))
        self.assertEqual([r["lead_id"] for r in fs.queue()], ["L3"])
        with self.assertRaises(fs.FollowupError):
            fs.update_followup(a["activity_id"], "done")  # already done
        with self.assertRaises(fs.FollowupError):
            fs.update_followup(c["activity_id"], "snooze")
        with self.assertRaises(fs.FollowupError):
            fs.update_followup(c["activity_id"], "reschedule", "")
        with self.assertRaises(LookupError):
            fs.update_followup("FUP-missing", "done")


class History(StoreTestCase):
    def test_filters_and_order(self):
        fs.add_activity("L1", "call", "Called Acme", occurred_at="2026-10-01 10:00", lead_name="Acme")
        fs.add_activity("L1", "note", "Budget 5 lakh", occurred_at="2026-10-03 10:00", lead_name="Acme")
        fs.add_activity("L2", "meeting", "Demo for Beta", occurred_at="2026-10-02 10:00", lead_name="Beta")
        fs.schedule_followup("L1", _day(2), "Send proposal")
        all_items = fs.history()["items"]
        self.assertEqual(all_items[0]["type"], "followup")  # newest first
        self.assertEqual([r["summary"] for r in fs.history(lead_id="L1", types=["call", "note"])["items"]],
                         ["Budget 5 lakh", "Called Acme"])
        self.assertEqual(fs.history(q="beta")["total"], 1)
        page = fs.history(limit=2, offset=1)
        self.assertEqual((len(page["items"]), page["total"]), (2, 4))
        with self.assertRaises(fs.FollowupError):
            fs.history(types=["bogus"])

    def test_last_contact(self):
        fs.add_activity("L1", "call", "old", occurred_at="2026-10-01 10:00")
        fs.add_activity("L1", "meeting", "new", occurred_at="2026-10-05 10:00")
        fs.schedule_followup("L1", _day(1), "ignored")
        self.assertEqual(fs.last_contact_by_lead()["L1"]["summary"], "new")

    def test_summary_counts_recent_activity(self):
        fs.add_activity("L1", "call", "this week")
        fs.add_activity("L1", "call", "long ago", occurred_at="2025-01-01 10:00")
        s = fs.summary()
        self.assertEqual((s["activities_7d"], s["activities_total"]), (1, 2))


class ImportSentEmails(StoreTestCase):
    def test_import_once_and_link_leads(self):
        log = os.path.join(self.tmp.name, "sent.csv")
        with open(log, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["email", "sent_at", "subject"])
            w.writerow(["Info@Acme.in", "2026-10-18 17:44:13", "Hello Acme"])
            w.writerow(["x@unknown.com", "2026-10-18 17:45:00", "Hello"])
            w.writerow(["", "2026-10-18 17:45:00", "no email"])
        leads = {"info@acme.in": {"id": "LEAD-7", "name": "Acme"}}
        first = fs.import_sent_emails(leads, log)
        self.assertEqual((first["imported"], first["matched_to_lead"], first["unmatched"]), (2, 1, 1))
        second = fs.import_sent_emails(leads, log)
        self.assertEqual((second["imported"], second["already_imported"]), (0, 2))
        rows = fs.history(lead_id="LEAD-7")["items"]
        self.assertEqual(rows[0]["summary"], "Email sent: Hello Acme")
        self.assertEqual(rows[0]["occurred_at"], "2026-10-18 17:44:13")

    def test_missing_log(self):
        self.assertEqual(fs.import_sent_emails({}, os.path.join(self.tmp.name, "nope.csv"))["imported"], 0)


class Api(StoreTestCase):
    LEADS = [
        {"id": "LEAD-1", "Company Name": "Acme", "Email": "info@acme.in, sales@acme.in", "Status": "NEW",
         "Source": "Job Portal (Shine.com)", "Mobile Number": ""},
        {"id": "LEAD-2", "Company Name": "Beta", "Email": "", "Status": "CONTACTED", "Source": "Reddit",
         "Mobile Number": "+91 99999 00000, +91 88888 11111, +91 77777 22222"},
    ]

    def setUp(self):
        super().setUp()
        import app as app_module
        self.app = app_module
        self.client = app_module.app.test_client()
        ok = SimpleNamespace(status_code=200, json=lambda: {"email": "owner@example.com"})
        self.patches = [
            mock.patch("api_auth.requests.get", return_value=ok),
            mock.patch("api_auth.ALLOWED_EMAILS", set()),
            mock.patch.object(app_module, "read_leads", return_value=[dict(l) for l in self.LEADS]),
        ]
        for p in self.patches:
            p.start()
        self.h = {"Authorization": "Bearer t"}

    def tearDown(self):
        for p in self.patches:
            p.stop()
        super().tearDown()

    def test_requires_login(self):
        for method, url in (("get", "/api/followups/summary"), ("get", "/api/followups/queue"),
                            ("get", "/api/followups/history"), ("post", "/api/followups/activities"),
                            ("post", "/api/followups/schedule"), ("patch", "/api/followups/FUP-1"),
                            ("post", "/api/followups/import-sent-emails"), ("get", "/api/leads/LEAD-1/timeline")):
            self.assertEqual(getattr(self.client, method)(url).status_code, 401, url)

    def test_add_activity_with_next_followup_and_timeline(self):
        r = self.client.post("/api/followups/activities", headers=self.h, json={
            "lead_id": "LEAD-1", "type": "call", "summary": "Discussed React project",
            "next_followup_at": _day(3), "next_followup_note": "Send proposal"})
        self.assertEqual(r.status_code, 200, r.get_json())
        body = r.get_json()
        self.assertEqual(body["activity"]["lead_name"], "Acme")
        self.assertEqual(body["followup"]["followup_status"], "pending")

        t = self.client.get("/api/leads/LEAD-1/timeline", headers=self.h).get_json()
        self.assertEqual(t["lead"]["name"], "Acme")
        self.assertEqual(len(t["items"]), 2)
        self.assertEqual(t["pending_followup"]["summary"], "Send proposal")

        q = self.client.get("/api/followups/queue?bucket=upcoming", headers=self.h).get_json()
        self.assertEqual(q["total"], 1)
        self.assertEqual(q["items"][0]["last_contact"]["summary"], "Discussed React project")
        self.assertTrue(q["items"][0]["lead_exists"])

    def test_timeline_shows_only_first_phone(self):
        """Regression: a lead with hundreds of scraped numbers flooded the timeline header."""
        fs.add_activity("LEAD-2", "note", "n")
        lead = self.client.get("/api/leads/LEAD-2/timeline", headers=self.h).get_json()["lead"]
        self.assertEqual(lead["phone"], "+91 99999 00000")

    def test_activity_validation(self):
        bad = [
            {"lead_id": "LEAD-404", "type": "call", "summary": "x"},
            {"lead_id": "LEAD-1", "type": "status_change", "summary": "x"},
            {"lead_id": "LEAD-1", "type": "call", "summary": ""},
            {"lead_id": "LEAD-1", "type": "call", "summary": "x", "next_followup_at": "2020-01-01"},
        ]
        for payload in bad:
            r = self.client.post("/api/followups/activities", headers=self.h, json=payload)
            self.assertEqual(r.status_code, 400, payload)
        r = self.client.post("/api/followups/activities", headers=self.h, data="x", content_type="application/json")
        self.assertEqual(r.status_code, 400)

    def test_schedule_update_flow(self):
        r = self.client.post("/api/followups/schedule", headers=self.h,
                             json={"lead_id": "LEAD-2", "due_at": _day(1), "note": "Call back"})
        fid = r.get_json()["followup"]["activity_id"]
        self.assertEqual(self.client.patch(f"/api/followups/{fid}", headers=self.h,
                                           json={"action": "reschedule", "due_at": _day(4)}).status_code, 200)
        self.assertEqual(self.client.patch(f"/api/followups/{fid}", headers=self.h,
                                           json={"action": "done"}).status_code, 200)
        self.assertEqual(self.client.patch(f"/api/followups/{fid}", headers=self.h,
                                           json={"action": "done"}).status_code, 400)
        self.assertEqual(self.client.patch("/api/followups/FUP-none", headers=self.h,
                                           json={"action": "done"}).status_code, 404)
        self.assertEqual(self.client.post("/api/followups/schedule", headers=self.h,
                                          json={"lead_id": "LEAD-404", "due_at": _day(1)}).status_code, 400)
        s = self.client.get("/api/followups/summary", headers=self.h).get_json()
        self.assertEqual(s["pending"], 0)

    def test_history_endpoint(self):
        fs.add_activity("LEAD-1", "note", "n1", lead_name="Old name")
        r = self.client.get("/api/followups/history?types=note&q=n1", headers=self.h).get_json()
        self.assertEqual(r["total"], 1)
        self.assertEqual(r["items"][0]["lead_name"], "Acme")  # current name from leads file
        self.assertEqual(self.client.get("/api/followups/history?types=bogus", headers=self.h).status_code, 400)
        self.assertEqual(self.client.get("/api/followups/queue?bucket=bogus", headers=self.h).status_code, 400)
        self.assertEqual(self.client.get("/api/leads/LEAD-404/timeline", headers=self.h).status_code, 404)

    def test_status_change_is_logged(self):
        with mock.patch.object(self.app, "update_lead_record", return_value=True):
            self.client.patch("/api/leads/LEAD-1/status", headers=self.h, json={"status": "MEETING"})
            self.client.patch("/api/leads/LEAD-1/status", headers=self.h, json={"status": "NEW"})  # unchanged
        items = fs.history(lead_id="LEAD-1")["items"]
        self.assertEqual([i["summary"] for i in items], ["Status: NEW → MEETING"])
        self.assertEqual(items[0]["type"], "status_change")

    def test_email_send_is_logged(self):
        with mock.patch.object(self.app, "send_smtp_email", return_value={"success": True}), \
                mock.patch.object(self.app, "update_lead_record", return_value=True):
            r = self.client.post("/api/leads/send-email", headers=self.h, json={
                "id": "LEAD-1", "to": "info@acme.in", "subject": "Proposal", "message": "Hi Acme"})
        self.assertEqual(r.status_code, 200)
        item = fs.history(lead_id="LEAD-1")["items"][0]
        self.assertEqual((item["type"], item["summary"], item["details"]), ("email_sent", "Email sent: Proposal", "Hi Acme"))

    def test_failed_email_not_logged(self):
        with mock.patch.object(self.app, "send_smtp_email", return_value={"success": False, "error": "smtp"}):
            self.client.post("/api/leads/send-email", headers=self.h, json={
                "id": "LEAD-1", "to": "info@acme.in", "subject": "Proposal", "message": "Hi"})
        self.assertEqual(fs.history()["total"], 0)

    def test_import_endpoint_matches_any_lead_email(self):
        log = os.path.join(self.tmp.name, "sent.csv")
        with open(log, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerows([["email", "sent_at", "subject"], ["sales@acme.in", "2026-10-18 10:00:00", "Hi"]])
        with mock.patch.object(fs, "SENT_LOG_FILE", log):
            r = self.client.post("/api/followups/import-sent-emails", headers=self.h).get_json()
        self.assertEqual((r["imported"], r["matched_to_lead"]), (1, 1))
        self.assertEqual(fs.history(lead_id="LEAD-1")["total"], 1)


if __name__ == "__main__":
    unittest.main()

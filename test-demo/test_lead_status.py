"""Lead Status stages (lead_status.py) and its API."""
import datetime
import unittest
from unittest import mock

import lead_status as ls

NOW = datetime.datetime(2026, 11, 17, 12, 0)


def lead(**kw):
    base = {"lead_id": "L1", "company_name": "Acme", "email": "", "mobile_number": "", "status": "NEW",
            "email_status": "NOT_SENT", "ai_category": "client_project", "ai_score": "7", "contact_channel": "none",
            "source": "Google Maps", "source_url": "", "first_seen_at": "2026-11-16 10:00:00", "posted_at": ""}
    base.update(kw)
    return base


def act(t, when, lead_id="L1", **kw):
    return {"lead_id": lead_id, "lead_email": "", "type": t, "occurred_at": when, "created_at": when,
            "due_at": "", "followup_status": "", **kw}


def stage(l, sent=(), acts=()):
    return ls.stage_of(l, ls.build_context(list(sent), list(acts)), NOW)["stage"]


class Stages(unittest.TestCase):
    def test_contact_channels(self):
        self.assertEqual(stage(lead(email="a@acme.in")), "mail_pending")
        self.assertEqual(stage(lead(mobile_number="+91 98250 12345")), "call_pending")
        self.assertEqual(stage(lead(email="bad@acme.in", email_status="INVALID", mobile_number="9825012345")), "call_pending")
        self.assertEqual(stage(lead(contact_channel="reddit", source_url="https://reddit.com/x")), "message_pending")
        self.assertEqual(stage(lead(contact_channel="reddit", first_seen_at="2026-10-01 10:00:00")), "old_post")
        self.assertEqual(stage(lead(source_url="https://maps.google.com/x")), "no_contact")

    def test_not_fit_and_closed(self):
        self.assertEqual(stage(lead(email="a@acme.in", ai_category="job_seeker")), "not_fit")
        self.assertEqual(stage(lead(email="a@acme.in", status="LOST")), "closed")
        self.assertEqual(stage(lead(email="a@acme.in"), acts=[act("opted_out", "2026-11-10 10:00:00")]), "closed")

    def test_after_contact(self):
        sent_recent = [{"email": "a@acme.in", "sent_at": "2026-11-16 10:00:00"}]
        sent_old = [{"email": "a@acme.in", "sent_at": "2026-11-01 10:00:00"}]
        self.assertEqual(stage(lead(email="a@acme.in"), sent=sent_recent), "waiting")
        self.assertEqual(stage(lead(email="a@acme.in"), sent=sent_old), "no_reply")
        self.assertEqual(stage(lead(email="a@acme.in", email_status="SENT")), "no_reply")  # sent, date unknown
        self.assertEqual(stage(lead(mobile_number="9825012345"), acts=[act("call", "2026-11-16 09:00:00")]), "waiting")

    def test_reply_and_followup(self):
        sent = [{"email": "a@acme.in", "sent_at": "2026-11-01 10:00:00"}]
        replied = [act("reply", "2026-11-05 10:00:00")]
        self.assertEqual(stage(lead(email="a@acme.in"), sent, replied), "replied")
        answered = replied + [act("email", "2026-11-06 10:00:00")]
        self.assertEqual(stage(lead(email="a@acme.in"), sent, answered), "waiting" if (NOW - datetime.datetime(2026, 11, 6, 10)).days < ls.WAIT_DAYS else "no_reply")
        due = [act("followup", "2026-11-01 10:00:00", due_at="2026-11-17 09:00:00", followup_status="pending")]
        self.assertEqual(stage(lead(email="a@acme.in"), sent, due), "followup_due")
        later = [act("followup", "2026-11-01 10:00:00", due_at="2026-11-20 09:00:00", followup_status="pending")]
        self.assertEqual(stage(lead(email="a@acme.in"), sent, later), "no_reply")

    def test_whatsapp_link(self):
        self.assertEqual(ls.whatsapp_link("98250 12345"), "https://wa.me/919825012345")
        self.assertEqual(ls.whatsapp_link("+1 415 555 0100"), "https://wa.me/14155550100")
        self.assertEqual(ls.whatsapp_link("12345"), "")

    def test_summary_and_list(self):
        leads = [lead(lead_id="A", email="a@acme.in", ai_score="9"), lead(lead_id="B", mobile_number="9825012345", ai_score="2"),
                 lead(lead_id="C", contact_channel="freelancer_bid", source_url="https://freelancer.com/p/1", ai_score="8")]
        res = ls.summary(leads, [], [], now=NOW)
        counts = {s["id"]: s["count"] for s in res["stages"]}
        self.assertEqual((counts["mail_pending"], counts["call_pending"], counts["message_pending"]), (1, 1, 1))
        self.assertEqual(res["todo"], 2)
        self.assertEqual(ls.summary(leads, [], [], band="high", now=NOW)["total"], 2)
        item = ls.stage_list(leads, [], [], "call_pending", now=NOW)["items"][0]
        self.assertEqual(item["id"], "B")
        self.assertTrue(item["whatsapp"].startswith("https://wa.me/919825012345?text="))
        self.assertEqual(ls.stage_list(leads, [], [], "message_pending", now=NOW)["items"][0]["platform"], "Freelancer.com")
        with self.assertRaises(ValueError):
            ls.stage_list(leads, [], [], "nope")
        with self.assertRaises(ValueError):
            ls.summary(leads, [], [], band="nope")


class ListAndToday(unittest.TestCase):
    def test_band_and_annotate(self):
        self.assertEqual([ls.band_of(lead(ai_score=s)) for s in ("9", "5", "1")], ["hot", "warm", "cold"])
        self.assertEqual(ls.band_of(lead(ai_score="", intent_score="")), "unscored")
        out = ls.annotate([lead(mobile_number="9825012345")], [], [], now=NOW)[0]
        self.assertEqual((out["next_action"], out["band"], out["last_contact"]), ("call_pending", "hot", ""))

    def test_today_lanes(self):
        leads = [lead(lead_id=f"P{i}", mobile_number="9825012345") for i in range(7)] + [lead(lead_id="M", email="a@acme.in")]
        res = ls.today(leads, [], [], per_lane=5, now=NOW)
        lane = next(l for l in res["lanes"] if l["id"] == "call_pending")
        self.assertEqual((lane["count"], len(lane["items"])), (7, 5))
        self.assertEqual([l["id"] for l in res["lanes"]], ls.TODO_STAGES)
        self.assertNotIn("mail_pending", ls.TODO_STAGES)


class Api(unittest.TestCase):
    def setUp(self):
        import app
        self.app = app
        app.app.config["TESTING"] = True
        self.client = app.app.test_client()
        self.client.environ_base["HTTP_X_DEMO_USER"] = "true"  # demo login, as in test_api_safety

    def test_endpoints(self):
        leads = [lead(lead_id="B", mobile_number="9825012345")]
        with mock.patch.object(self.app, "_report_context", return_value=(leads, [], [], [])):
            r = self.client.get("/api/reports/lead-status?band=all")
            self.assertEqual(r.status_code, 200, r.get_json())
            self.assertEqual(r.get_json()["todo"], 1)
            r = self.client.get("/api/reports/lead-status/list?stage=call_pending")
            self.assertEqual(r.get_json()["items"][0]["id"], "B")
            self.assertEqual(self.client.get("/api/reports/lead-status/list?stage=bad").status_code, 400)

    def test_leads_carry_next_action_and_today_has_goals(self):
        leads = [lead(lead_id="B", mobile_number="9825012345")]
        with mock.patch.object(self.app, "read_leads", return_value=leads),                 mock.patch.object(self.app, "_report_context", return_value=(leads, [], [], [])),                 mock.patch.object(self.app, "load_settings", return_value={"monthlyGoals": {"won": "3", "replied": "x", "meetings": 0}}):
            row = self.client.get("/api/leads").get_json()["leads"][0]
            self.assertEqual((row["next_action"], row["band"]), ("call_pending", "hot"))
            today = self.client.get("/api/today").get_json()
            self.assertEqual(today["goals"], {"won": 3})
            self.assertEqual(today["todo"], 1)

    def test_mark_done(self):
        with mock.patch.object(self.app, "_lead_info", return_value={"id": "B", "name": "Acme", "email": ""}), \
                mock.patch.object(self.app.followup_store, "add_activity", return_value={"activity_id": "X"}) as add:
            r = self.client.post("/api/reports/lead-status/done", json={"lead_id": "B", "action": "called"})
            self.assertEqual(r.status_code, 200, r.get_json())
            self.assertEqual(add.call_args.args[1], "call")
            self.assertEqual(self.client.post("/api/reports/lead-status/done", json={"lead_id": "B", "action": "x"}).status_code, 400)
        with mock.patch.object(self.app, "_lead_info", return_value=None):
            self.assertEqual(self.client.post("/api/reports/lead-status/done", json={"lead_id": "Z", "action": "called"}).status_code, 404)


if __name__ == "__main__":
    unittest.main()

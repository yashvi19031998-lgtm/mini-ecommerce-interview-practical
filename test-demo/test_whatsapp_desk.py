"""WhatsApp desk (new + follow-up list, daily limit) and the 'Chat on WhatsApp' link in mails."""
import datetime
import unittest
from unittest import mock

import settings_manager as sm
import whatsapp_desk as wd
from test_lead_status import lead, act

NOW = datetime.datetime(2026, 11, 18, 12, 0)  # a Wednesday, office hours


def leads():
    return [
        lead(lead_id="A", mobile_number="9825012345", ai_score="9"),                       # call pending
        lead(lead_id="B", email="b@acme.in", mobile_number="9825099999", ai_score="5"),    # mailed -> call
        lead(lead_id="C", mobile_number="9825011111", ai_score="8"),                       # already WhatsApped
        lead(lead_id="D", mobile_number="12", ai_score="9"),                               # not a phone
        lead(lead_id="E", mobile_number="9825022222", ai_score="9", status="LOST"),        # closed
        lead(lead_id="F", mobile_number="9825033333", ai_score="9", ai_category="job_seeker"),
    ]


SENT = [{"email": "b@acme.in", "sent_at": "2026-11-17 10:00:00"}]


class Queue(unittest.TestCase):
    def test_new_list_order_and_exclusions(self):
        acts = [act("whatsapp", "2026-11-17 11:00:00", lead_id="C")]
        q = wd.queue(leads(), SENT, acts, now=NOW)
        self.assertEqual([i["id"] for i in q["new"]], ["B", "A"])  # mailed-not-called first, then by score
        self.assertTrue(q["new"][0]["text"].startswith("Hi"))
        self.assertIn("sent you a short e-mail", q["new"][0]["text"])
        self.assertEqual(q["followup"], [])  # C was WhatsApped only 1 day ago

    def test_followup_after_three_days_once(self):
        acts = [act("whatsapp", "2026-11-14 11:00:00", lead_id="C")]
        q = wd.queue(leads(), [], acts, now=NOW)
        self.assertEqual([i["id"] for i in q["followup"]], ["C"])
        self.assertIn("following up", q["followup"][0]["text"])
        acts2 = acts + [act("whatsapp", "2026-11-15 11:00:00", lead_id="C")]
        self.assertEqual(wd.queue(leads(), [], acts2, now=NOW)["followup"], [])  # 2 sent: done
        acts3 = acts + [act("reply", "2026-11-15 09:00:00", lead_id="C")]
        self.assertEqual(wd.queue(leads(), [], acts3, now=NOW)["followup"], [])  # they answered

    def test_counts_limit_and_hours(self):
        acts = [act("whatsapp", "2026-11-18 10:00:00", lead_id=f"X{i}") for i in range(3)]
        q = wd.queue(leads(), [], acts, now=NOW)
        self.assertEqual((q["sent_today"], q["daily_limit"], q["left_today"]), (3, wd.DAILY_LIMIT, wd.DAILY_LIMIT - 3))
        self.assertTrue(q["office_hours"])
        self.assertFalse(wd.in_office_hours(datetime.datetime(2026, 11, 22, 12)))  # Sunday
        self.assertFalse(wd.in_office_hours(datetime.datetime(2026, 11, 18, 21)))

    def test_mark_sent_logs_and_plans_a_reminder_and_stops_at_the_limit(self):
        with mock.patch("followup_store.add_activity", return_value={"activity_id": "A1"}) as add, \
                mock.patch("followup_store.schedule_followup") as sched:
            wd.mark_sent({"id": "A", "name": "Acme"}, "Hi", "new", [], now=NOW)
            self.assertEqual(add.call_args.args[1], "whatsapp")
            sched.assert_called_once()
            wd.mark_sent({"id": "A", "name": "Acme"}, "Hi again", "followup", [], now=NOW)
            self.assertEqual(sched.call_count, 1)  # no reminder after the follow-up
            full = [act("whatsapp", "2026-11-18 10:00:00", lead_id=f"X{i}") for i in range(wd.DAILY_LIMIT)]
            with self.assertRaises(ValueError):
                wd.mark_sent({"id": "A", "name": "Acme"}, "Hi", "new", full, now=NOW)


class Api(unittest.TestCase):
    def test_endpoints(self):
        import app
        app.app.config["TESTING"] = True
        c = app.app.test_client()
        c.environ_base["HTTP_X_DEMO_USER"] = "true"
        with mock.patch.object(app, "_report_context", return_value=(leads(), [], SENT, [])):
            r = c.get("/api/whatsapp/desk").get_json()
            self.assertEqual(r["new"][0]["id"], "B")
            with mock.patch.object(app, "_lead_info", return_value={"id": "B", "name": "Acme", "email": ""}), \
                    mock.patch("whatsapp_desk.mark_sent", return_value={"activity_id": "A1"}):
                self.assertEqual(c.post("/api/whatsapp/sent", json={"lead_id": "B", "text": "Hi"}).status_code, 200)
            with mock.patch.object(app, "_lead_info", return_value=None):
                self.assertEqual(c.post("/api/whatsapp/sent", json={"lead_id": "Z"}).status_code, 404)


class MailLink(unittest.TestCase):
    def test_signature_gets_a_chat_on_whatsapp_link(self):
        s = {"signatureTemplate": "Regards,\n{companyName}", "companyName": "Acme", "whatsapp": "+91 98250 12345"}
        sig = sm.format_signature(s)
        self.assertIn("Chat on WhatsApp: https://wa.me/919825012345?text=", sig)
        self.assertNotIn("wa.me", sm.format_signature({**s, "whatsappCta": False}))
        self.assertNotIn("wa.me", sm.format_signature({**s, "whatsapp": "", "phone": ""}))
        twice = sm.format_signature({**s, "signatureTemplate": "Hi https://wa.me/91x"})
        self.assertEqual(twice.count("wa.me"), 1)  # a template that already has the link is left alone


if __name__ == "__main__":
    unittest.main()

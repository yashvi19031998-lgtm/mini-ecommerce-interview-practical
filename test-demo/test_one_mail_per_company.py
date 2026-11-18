"""One outreach mail per company, no mail to complaints / no-reply addresses, and the sent log refreshed
from the database before the app sends."""
import os
import tempfile
import unittest
from unittest import mock

import email_service as es
import lead_status as ls
from test_lead_status import lead


class Domains(unittest.TestCase):
    def test_company_domain(self):
        self.assertEqual(es.company_domain("info@mail.acme.co.in"), "acme.co.in")
        self.assertEqual(es.company_domain("a@sub.acme.com"), "acme.com")
        self.assertEqual(es.company_domain("me@gmail.com"), "")
        self.assertEqual(es.company_domain("x@in.experian.com"), "experian.com")

    def test_block_reasons(self):
        sent = {"support@cashify.in", "friend@gmail.com"}
        self.assertIn("one mail per company", es.outreach_block_reason("info@cashify.in", sent))
        self.assertEqual(es.outreach_block_reason("other@gmail.com", sent), "")  # free mail: a different person
        for role in ("grievanceofficer@x.in", "privacy-officer@x.in", "noreply@x.in", "press@x.in", "dmca@x.in"):
            self.assertIn("not a buyer", es.outreach_block_reason(role, set()), role)
        self.assertEqual(es.outreach_block_reason("hr@acme.in", set()), "")
        self.assertEqual(es.outreach_block_reason("sales@acme.in", set()), "")


class SendGate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.p = [mock.patch.object(es, "SENT_LOG_FILE", os.path.join(self.tmp, "sent.csv")),
                  mock.patch.dict(os.environ, {"SMTP_USER": "me@x.in", "SMTP_PASS": "p"})]
        for p in self.p:
            p.start()
        es.record_email_sent("support@cashify.in", "first")

    def tearDown(self):
        for p in self.p:
            p.stop()

    def test_second_address_of_a_company_is_blocked_before_any_network_call(self):
        with mock.patch("smtplib.SMTP") as smtp, mock.patch("email_checks.verify_mailbox") as verify:
            res = es.send_smtp_email("info@cashify.in", "Hi", "Body")
        self.assertFalse(res["success"])
        self.assertTrue(res["blocked"])
        verify.assert_not_called()
        smtp.assert_not_called()

    def test_follow_up_to_the_same_address_is_still_allowed(self):
        with mock.patch("smtplib.SMTP"), mock.patch("email_checks.verify_mailbox", return_value=("valid", "")):
            res = es.send_smtp_email("support@cashify.in", "Re: Hi", "Body", bypass_duplicate_check=True, verify=None)
        self.assertTrue(res.get("success"), res)


class Refresh(unittest.TestCase):
    def test_adds_addresses_sent_elsewhere(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(es, "SENT_LOG_FILE", os.path.join(d, "s.csv")):
            es.record_email_sent("a@acme.in")
            with mock.patch("datastore.configured", return_value=True), \
                    mock.patch("datastore.remote_sent_addresses", return_value={"a@acme.in", "b@other.in"}):
                res = es.refresh_sent_from_db()
            self.assertEqual((res["ok"], res["added"]), (True, 1))
            self.assertIn("b@other.in", es.get_already_sent_emails())
            with mock.patch("datastore.configured", return_value=True), \
                    mock.patch("datastore.remote_sent_addresses", side_effect=RuntimeError("down")):
                self.assertFalse(es.refresh_sent_from_db()["ok"])
            with mock.patch("datastore.configured", return_value=False):
                self.assertTrue(es.refresh_sent_from_db()["ok"])

    def test_app_refuses_to_send_when_the_database_cannot_be_checked(self):
        import app
        c = app.app.test_client()
        c.environ_base["HTTP_X_DEMO_USER"] = "true"
        app.app.config["TESTING"] = False
        try:
            with mock.patch("email_service.refresh_sent_from_db", return_value={"ok": False, "added": 0, "error": "down"}):
                r = c.post("/api/leads/bulk-email", json={"lead_ids": ["L1"], "subject": "s", "message": "m"})
            self.assertEqual(r.status_code, 503)
            self.assertIn("nothing was sent", r.get_json()["error"])
        finally:
            app.app.config["TESTING"] = True


class Queue(unittest.TestCase):
    def test_company_already_mailed_is_not_in_the_mail_queue(self):
        sent = [{"email": "support@cashify.in", "sent_at": "2026-11-10 10:00:00"}]
        ctx = ls.build_context(sent, [])
        other = lead(lead_id="X", email="info@cashify.in")
        self.assertNotEqual(ls.stage_of(other, ctx)["stage"], "mail_pending")
        self.assertNotIn("email", ls.pending_channels(other, ctx, "no_contact"))
        fresh = lead(lead_id="Y", email="info@newco.in")
        self.assertEqual(ls.stage_of(fresh, ctx)["stage"], "mail_pending")
        role = lead(lead_id="Z", email="grievance@newco2.in")
        self.assertNotEqual(ls.stage_of(role, ctx)["stage"], "mail_pending")


if __name__ == "__main__":
    unittest.main()

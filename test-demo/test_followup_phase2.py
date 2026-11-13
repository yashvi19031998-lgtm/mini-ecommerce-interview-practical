"""Tests for FollowUp Phase 2: sequence planning/sending, Gmail reply check, report, API. No network.

    python -m unittest test_followup_phase2 -v
"""
import datetime
import os
import tempfile
import unittest
from email.message import EmailMessage
from types import SimpleNamespace
from unittest import mock

import followup_sequence as seq
import followup_store as fs
import reply_checker as rc

TS = "%Y-%m-%d %H:%M:%S"
NOW = datetime.datetime(2026, 11, 20, 12, 0, 0)


def ago(days, hours=0):
    return (NOW - datetime.timedelta(days=days, hours=hours)).strftime(TS)


LEADS = {"L1": {"name": "Acme", "email": "info@acme.in", "status": "EMAIL_SENT"},
         "L2": {"name": "Beta", "email": "hi@beta.io", "status": "NEW"}}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.patches = [
            mock.patch.object(fs, "ACTIVITY_FILE", os.path.join(self.tmp.name, "logs", "act.csv")),
            mock.patch.object(rc, "STATE_FILE", os.path.join(self.tmp.name, "logs", "imap.json")),
            mock.patch.dict(os.environ, {"FOLLOWUP_SEQUENCE_DAYS": "3,7,14", "FOLLOWUP_AUTO_SEND": "false",
                                         "FOLLOWUP_MAX_AGE_DAYS": "30"}),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def first_email(self, lead="L1", when=None, email="info@acme.in", subject="Collaboration"):
        fs.add_event_once(f"E-{lead}-{when}", lead, "email_sent", f"Email sent: {subject}", occurred_at=when,
                          source="dashboard", lead_name=LEADS.get(lead, {}).get("name", ""), lead_email=email)

    def seq_email(self, step, when, lead="L1", email="info@acme.in"):
        fs.add_event_once(f"S-{lead}-{step}", lead, "email_sent", "Email sent: Re: x", occurred_at=when,
                          source=f"{seq.SEQUENCE_SOURCE}{step}", lead_email=email)


# ---------------------------------------------------------------- planning
class Planning(Base):
    def test_step_due_on_day_3_not_before(self):
        self.first_email(when=ago(2))
        self.assertEqual(seq.plan(LEADS, NOW)["due"], [])
        self.assertEqual(len(seq.plan(LEADS, NOW)["waiting"]), 1)
        self.first_email(lead="L2", when=ago(3), email="hi@beta.io")
        due = seq.plan(LEADS, NOW)["due"]
        self.assertEqual([(d["lead_id"], d["step"]) for d in due], [("L2", 1)])
        self.assertEqual(due[0]["original_subject"], "Collaboration")

    def test_steps_progress_and_finish(self):
        self.first_email(when=ago(7))
        self.seq_email(1, ago(4))
        self.assertEqual(seq.plan(LEADS, NOW)["due"][0]["step"], 2)
        self.seq_email(2, ago(0, 1))
        p = seq.plan(LEADS, NOW)
        self.assertEqual(p["due"], [])  # step 3 is on day 14
        self.seq_email(3, ago(0))
        p = seq.plan(LEADS, NOW + datetime.timedelta(days=30))
        self.assertEqual(p["due"] + p["waiting"], [])  # finished

    def test_min_gap_between_emails(self):
        self.first_email(when=ago(7))
        self.seq_email(1, ago(1))  # step 1 sent late, yesterday
        p = seq.plan(LEADS, NOW)
        self.assertEqual(p["due"], [])  # step 2 is due by date but must wait 2 days after the last email
        self.assertEqual(p["waiting"][0]["step"], 2)
        # earliest = last email (1 day ago) + 2 days = tomorrow, same time
        self.assertEqual(p["waiting"][0]["due_at"], (NOW + datetime.timedelta(days=1)).strftime(TS))

    def test_late_steps_are_skipped_not_burst(self):
        self.first_email(when=ago(20))  # step1 day3 (17 late), step2 day7 (13 late), step3 day14 (6 late)
        due = seq.plan(LEADS, NOW)["due"]
        self.assertEqual([d["step"] for d in due], [3])
        self.first_email(lead="L2", when=ago(25), email="hi@beta.io")  # every step > 7 days late
        self.assertNotIn("L2", [d["lead_id"] for d in seq.plan(LEADS, NOW)["due"]])

    def test_too_old_first_email_ignored(self):
        self.first_email(when=ago(40))
        p = seq.plan(LEADS, NOW)
        self.assertEqual(p["due"] + p["waiting"], [])

    def test_stop_conditions(self):
        for kind in ("reply", "bounce", "opted_out", "sequence_stopped"):
            with self.subTest(kind=kind):
                fs._write_all([])
                self.first_email(when=ago(5))
                fs.add_event_once(f"X-{kind}", "L1", kind, kind, occurred_at=ago(1))
                p = seq.plan(LEADS, NOW)
                self.assertEqual(p["due"], [])
                self.assertEqual(len(p["stopped"]), 1)
        fs._write_all([])
        self.first_email(when=ago(5))
        for status in ("MEETING", "WON", "replied"):
            leads = {"L1": {**LEADS["L1"], "status": status}}
            self.assertEqual(seq.plan(leads, NOW)["stopped"][0]["reason"], f"status is {status.upper()}")
        self.assertEqual(seq.plan({}, NOW)["stopped"][0]["reason"], "lead no longer in the database")

    def test_old_reply_before_first_email_does_not_stop(self):
        fs.add_event_once("R-old", "L1", "reply", "old reply", occurred_at=ago(30))
        self.first_email(when=ago(3))
        self.assertEqual(len(seq.plan(LEADS, NOW)["due"]), 1)

    def test_days_setting(self):
        with mock.patch.dict(os.environ, {"FOLLOWUP_SEQUENCE_DAYS": "5, 2, x"}):
            self.assertEqual(seq.sequence_days(), [3, 7, 14])  # invalid -> default
        with mock.patch.dict(os.environ, {"FOLLOWUP_SEQUENCE_DAYS": "10,2,5,20"}):
            self.assertEqual(seq.sequence_days(), [2, 5, 10])  # sorted, max 3 steps
        self.assertFalse(seq.config()["auto_send"])


# ---------------------------------------------------------------- render + send
class Sending(Base):
    def item(self, step=1):
        return {"lead_id": "L1", "lead_name": "Acme", "email": "info@acme.in", "step": step,
                "first_sent_at": "2026-11-08 10:00:00", "original_subject": "Collaboration"}

    def test_render(self):
        msg = seq.render(self.item(), signature="Team Sangeeta")
        self.assertEqual(msg["subject"], "Re: Collaboration")
        self.assertIn("08 Nov", msg["body"])
        self.assertIn("Acme", msg["body"])
        self.assertIn("Team Sangeeta", msg["body"])
        self.assertTrue(msg["body"].endswith(seq.OPT_OUT_LINE))
        self.assertIn("last note", seq.render(self.item(3))["body"])

    def test_company_name_that_is_a_post_title_is_not_used(self):
        """QA finding: lead names are often post titles ('Show HN: ...') and read badly in an email."""
        for bad in ("Show HN: Structured search for Who is hiring", "[Hiring] React dev", "Need app | Remote",
                    "Senior Developer needed for fintech startup in Pune"):
            self.assertEqual(seq.company_for_email(bad), "your team", bad)
        self.assertEqual(seq.company_for_email("Acme Infotech"), "Acme Infotech")
        body = seq.render({**self.item(3), "total_steps": 3, "lead_name": "Show HN: Autograph"})["body"]
        self.assertIn("Wishing your team all the best", body)

    def test_template_wording_follows_sent_count(self):
        # step 2 due but step 1 was skipped (too late): the first follow-up must not say "once more"
        first = seq.render({**self.item(2), "total_steps": 3, "followups_sent": 0})["body"]
        self.assertIn("Just following up", first)
        second = seq.render({**self.item(2), "total_steps": 3, "followups_sent": 1})["body"]
        self.assertIn("Checking in once more", second)
        last = seq.render({**self.item(3), "total_steps": 3, "followups_sent": 0})["body"]
        self.assertIn("last note", last)

    def test_send_logs_success_only(self):
        calls = []

        def fake_send(to, sub, body):
            calls.append(to)
            return {"success": to == "info@acme.in", "error": "smtp down"}
        items = [self.item(), {**self.item(), "lead_id": "L2", "email": "hi@beta.io"}]
        res = seq.send(items, fake_send)
        self.assertEqual((res["sent"], res["failed"]), (1, 1))
        logged = fs.history(types=["email_sent"])["items"]
        self.assertEqual(len(logged), 1)
        self.assertEqual(logged[0]["source"], "followup sequence #1")

    def test_send_limit_and_exception(self):
        def crash(*_):
            raise RuntimeError("smtp crashed")
        res = seq.send([self.item(), self.item(2)], crash, limit=1)
        self.assertEqual((res["sent"], res["failed"], len(res["results"])), (0, 1, 1))

    def test_stop(self):
        row = seq.stop("L1", "", "Acme", "info@acme.in")
        self.assertEqual(row["type"], "sequence_stopped")
        self.assertIn("Stopped by hand", row["summary"])


# ---------------------------------------------------------------- Gmail parsing
def make_mail(sender, subject, body, date="Fri, 20 Nov 2026 10:00:00 +0530", msg_id="<m1@x>", extra=None):
    m = EmailMessage()
    m["From"] = sender
    m["To"] = "us@gmail.com"
    m["Subject"] = subject
    m["Date"] = date
    m["Message-ID"] = msg_id
    for k, v in (extra or {}).items():
        m[k] = v
    m.set_content(body)
    return m.as_bytes()


class Classify(unittest.TestCase):
    contacted = {"info@acme.in"}

    def test_reply(self):
        ev = rc.classify(make_mail("Acme CTO <INFO@acme.in>", "Re: Collaboration", "Yes, let's talk Monday."), self.contacted)
        self.assertEqual((ev["type"], ev["email"]), ("reply", "info@acme.in"))
        self.assertEqual(ev["snippet"], "Yes, let's talk Monday.")
        self.assertTrue(ev["received_at"].startswith("2026-11-20"))

    def test_quoted_opt_out_line_is_not_an_opt_out(self):
        body = f"Sounds good, send details.\n\nOn Thu, someone wrote:\n> {seq.OPT_OUT_LINE}\n> reply STOP"
        self.assertEqual(rc.classify(make_mail("info@acme.in", "Re: x", body), self.contacted)["type"], "reply")

    def test_opt_out(self):
        for body in ("STOP", "Please unsubscribe me", "We are not interested, thanks", "Don't email us again"):
            with self.subTest(body=body):
                self.assertEqual(rc.classify(make_mail("info@acme.in", "Re: x", body), self.contacted)["type"], "opted_out")
        self.assertEqual(rc.classify(make_mail("info@acme.in", "Unsubscribe", "-"), self.contacted)["type"], "opted_out")

    def test_bounce(self):
        raw = make_mail("Mail Delivery Subsystem <mailer-daemon@googlemail.com>", "Delivery Status Notification (Failure)",
                        "Your message wasn't delivered to info@acme.in because the address couldn't be found.")
        ev = rc.classify(raw, self.contacted)
        self.assertEqual((ev["type"], ev["email"]), ("bounce", "info@acme.in"))
        raw2 = make_mail("mailer-daemon@x.com", "Undeliverable", "failed", extra={"X-Failed-Recipients": "nobody@else.com"})
        self.assertIsNone(rc.classify(raw2, self.contacted))  # bounce for an address we never emailed

    def test_unrelated_sender_ignored(self):
        self.assertIsNone(rc.classify(make_mail("news@shop.com", "Sale", "50% off"), self.contacted))

    def test_html_only_reply(self):
        m = EmailMessage()
        m["From"], m["Subject"], m["Message-ID"] = "info@acme.in", "Re: x", "<h@x>"
        m.set_content("<p>Interested! <b>Call me</b></p>", subtype="html")
        ev = rc.classify(m.as_bytes(), self.contacted)
        self.assertEqual(ev["type"], "reply")
        self.assertIn("Interested!", ev["snippet"])


class FakeImap:
    def __init__(self, messages, fail_login=False):
        self.messages = messages
        self.fail_login = fail_login
        self.readonly = None

    def __call__(self, host):
        return self

    def login(self, user, pw):
        if self.fail_login:
            raise rc.imaplib.IMAP4.error("AUTHENTICATIONFAILED")

    def select(self, box, readonly=False):
        self.readonly = readonly
        return "OK", [b"1"]

    def uid(self, cmd, *args):
        if cmd == "search":
            return "OK", [b" ".join(str(u).encode() for u in self.messages)]
        uid = int(args[0])
        return "OK", [(b"1 (BODY[] {10}", self.messages[uid])]

    def logout(self):
        pass


class FetchAndRecord(Base):
    def test_fetch_is_readonly_incremental_and_dedupes(self):
        msgs = {5: make_mail("info@acme.in", "Re: x", "Yes please", msg_id="<a@x>"),
                6: make_mail("other@x.com", "Hi", "spam", msg_id="<b@x>")}
        fake = FakeImap(msgs)
        with mock.patch.dict(os.environ, {"IMAP_USER": "u", "IMAP_PASSWORD": "p"}):
            events = rc.fetch_events({"info@acme.in"}, imap_factory=fake)
            self.assertTrue(fake.readonly)
            self.assertEqual([e["uid"] for e in events], [5])
            self.assertEqual(rc.fetch_events({"info@acme.in"}, imap_factory=fake), [])  # state: last_uid=6
        res = rc.record_events(events, {"info@acme.in": {"id": "L1", "name": "Acme"}})
        self.assertEqual((res["logged"], res["updates"]), (1, [{"lead_id": "L1", "status": "REPLIED"}]))
        again = rc.record_events(events, {"info@acme.in": {"id": "L1", "name": "Acme"}})
        self.assertEqual((again["logged"], again["skipped"]), (0, 1))
        self.assertEqual(fs.history(types=["reply"])["items"][0]["details"], "Yes please")

    def test_bounce_update(self):
        res = rc.record_events([{"type": "bounce", "email": "info@acme.in", "subject": "DSN", "snippet": "",
                                 "received_at": "2026-11-20 10:00:00", "message_id": "<z@x>"}],
                               {"info@acme.in": {"id": "L1", "name": "Acme"}})
        self.assertEqual(res["updates"], [{"lead_id": "L1", "email_status": "INVALID"}])

    def test_errors(self):
        with mock.patch.dict(os.environ, {"IMAP_USER": "", "IMAP_PASSWORD": "", "SMTP_USER": "", "SMTP_PASS": ""}):
            self.assertFalse(rc.is_configured())
            with self.assertRaises(RuntimeError):
                rc.fetch_events(set())
        with mock.patch.dict(os.environ, {"IMAP_USER": "u", "IMAP_PASSWORD": "bad"}):
            with self.assertRaises(RuntimeError) as ctx:
                rc.fetch_events(set(), imap_factory=FakeImap({}, fail_login=True))
            self.assertIn("login", str(ctx.exception).lower())

    def test_smtp_credentials_reused(self):
        with mock.patch.dict(os.environ, {"IMAP_USER": "", "IMAP_PASSWORD": "", "SMTP_USER": "a@g.com", "SMTP_PASS": "x"}):
            self.assertTrue(rc.is_configured())


# ---------------------------------------------------------------- report + import dedupe
class ReportAndImport(Base):
    def test_report(self):
        self.first_email("L1", ago(10))
        self.seq_email(1, ago(7))
        fs.add_event_once("R1", "L1", "reply", "Reply", occurred_at=ago(6))
        self.first_email("L2", ago(10), email="hi@beta.io")
        fs.add_event_once("B2", "L2", "bounce", "Bounce", occurred_at=ago(9))
        r = fs.report({"L1": "Reddit", "L2": "Job Portal"})
        o = r["overall"]
        self.assertEqual((o["contacted"], o["replied"], o["reply_rate_pct"], o["bounced"]), (2, 1, 50.0, 1))
        self.assertEqual((o["followups_sent"], o["replied_after_followup"]), (1, 1))
        self.assertEqual(r["by_source"][0]["source"], "Reddit")

    def test_import_skips_emails_already_logged_by_app(self):
        self.first_email("L1", "2026-11-08 10:00:30")
        log = os.path.join(self.tmp.name, "sent.csv")
        with open(log, "w", encoding="utf-8") as f:
            f.write("email,sent_at,subject\ninfo@acme.in,2026-11-08 10:00:31,Collaboration\nnew@x.com,2026-11-08 11:00:00,Hi\n")
        res = fs.import_sent_emails({}, log)
        self.assertEqual((res["imported"], res["already_imported"]), (1, 1))


# ---------------------------------------------------------------- API
class Api(Base):
    LEADS_ROWS = [{"id": "L1", "Company Name": "Acme", "Email": "info@acme.in", "Status": "EMAIL_SENT",
                   "Source": "Reddit (r/x)", "Mobile Number": ""},
                  {"id": "L2", "Company Name": "Beta", "Email": "hi@beta.io", "Status": "MEETING",
                   "Source": "Job Portal (Shine.com)", "Mobile Number": ""}]

    def setUp(self):
        super().setUp()
        import app as app_module
        self.app = app_module
        self.client = app_module.app.test_client()
        ok = SimpleNamespace(status_code=200, json=lambda: {"email": "owner@example.com"})
        self.api_patches = [mock.patch("api_auth.requests.get", return_value=ok),
                            mock.patch("api_auth.ALLOWED_EMAILS", set()),
                            mock.patch.object(app_module, "read_leads", return_value=[dict(r) for r in self.LEADS_ROWS])]
        for p in self.api_patches:
            p.start()
        self.h = {"Authorization": "Bearer t"}
        today = datetime.datetime.now()
        fs.add_event_once("E1", "L1", "email_sent", "Email sent: Collaboration",
                          occurred_at=(today - datetime.timedelta(days=4)).strftime(TS), lead_email="info@acme.in")

    def tearDown(self):
        for p in self.api_patches:
            p.stop()
        super().tearDown()

    def test_requires_login(self):
        for method, url in (("get", "/api/followups/sequence"), ("post", "/api/followups/sequence/send"),
                            ("post", "/api/followups/sequence/stop"), ("post", "/api/followups/check-replies"),
                            ("get", "/api/followups/report")):
            self.assertEqual(getattr(self.client, method)(url).status_code, 401, url)

    def test_sequence_preview_and_send(self):
        body = self.client.get("/api/followups/sequence", headers=self.h).get_json()
        self.assertFalse(body["config"]["auto_send"])
        self.assertEqual([d["lead_id"] for d in body["due"]], ["L1"])
        self.assertIn(seq.OPT_OUT_LINE, body["due"][0]["preview"]["body"])
        sent = []
        with mock.patch.object(self.app, "send_smtp_email",
                               side_effect=lambda to, s, b, bypass_duplicate_check=False, company_name="", verify="strict": sent.append(bypass_duplicate_check) or {"success": True}):
            r = self.client.post("/api/followups/sequence/send", headers=self.h, json={"lead_ids": ["L1", "L2"]})
        res = r.get_json()
        self.assertEqual((res["sent"], res["not_due"]), (1, 1))
        self.assertEqual(sent, [True])  # duplicate shield bypassed only for due follow-ups
        self.assertEqual(self.client.get("/api/followups/sequence", headers=self.h).get_json()["due"], [])
        self.assertEqual(self.client.post("/api/followups/sequence/send", headers=self.h,
                                          json={"lead_ids": ["L1"]}).status_code, 400)  # no longer due

    def test_send_validation(self):
        for payload in ({}, {"lead_ids": []}, {"lead_ids": "L1"}, {"lead_ids": [str(i) for i in range(51)]}):
            self.assertEqual(self.client.post("/api/followups/sequence/send", headers=self.h, json=payload).status_code, 400)

    def test_stop(self):
        self.assertEqual(self.client.post("/api/followups/sequence/stop", headers=self.h,
                                          json={"lead_id": "L1", "reason": "Asked by phone"}).status_code, 200)
        self.assertEqual(self.client.get("/api/followups/sequence", headers=self.h).get_json()["due"], [])
        self.assertEqual(self.client.post("/api/followups/sequence/stop", headers=self.h,
                                          json={"lead_id": "nope"}).status_code, 400)

    def test_check_replies(self):
        with mock.patch.object(rc, "is_configured", return_value=False):
            self.assertEqual(self.client.post("/api/followups/check-replies", headers=self.h).status_code, 400)
        events = [{"type": "reply", "email": "info@acme.in", "subject": "Re: Collaboration", "snippet": "Yes",
                   "received_at": "2026-11-11 10:00:00", "message_id": "<r@x>"},
                  {"type": "reply", "email": "hi@beta.io", "subject": "Re", "snippet": "ok",
                   "received_at": "2026-11-11 10:00:00", "message_id": "<r2@x>"}]
        with mock.patch.object(rc, "is_configured", return_value=True), \
                mock.patch.object(rc, "fetch_events", return_value=events), \
                mock.patch.object(self.app, "update_lead_record", return_value=True) as upd:
            res = self.client.post("/api/followups/check-replies", headers=self.h).get_json()
        self.assertEqual((res["new_events"], res["reply"], res["leads_updated"]), (2, 2, 1))
        upd.assert_called_once_with("L1", {"Status": "REPLIED"})  # L2 is MEETING: not downgraded
        with mock.patch.object(rc, "is_configured", return_value=True), \
                mock.patch.object(rc, "fetch_events", side_effect=RuntimeError("Gmail login/IMAP error")):
            self.assertEqual(self.client.post("/api/followups/check-replies", headers=self.h).status_code, 502)

    def test_report(self):
        fs.add_event_once("R", "L1", "reply", "Reply", occurred_at=ago(0), lead_email="info@acme.in")
        r = self.client.get("/api/followups/report", headers=self.h).get_json()
        self.assertEqual(r["overall"]["replied"], 1)
        self.assertEqual(r["by_source"][0]["source"], "Reddit")


# ---------------------------------------------------------------- hourly runner
class Runner(Base):
    def test_runner_applies_replies_and_respects_auto_send_off(self):
        import run_all_scrapers as runner
        lead_rows = [{"lead_id": "L1", "company_name": "Acme", "email": "info@acme.in", "status": "EMAIL_SENT",
                      "email_status": "SENT"}]
        registry = SimpleNamespace(leads=lead_rows, load_master=lambda: None, save_master_safely=mock.Mock(return_value=True))
        self.first_email("L1", (datetime.datetime.now() - datetime.timedelta(days=4)).strftime(TS))
        reply = [{"type": "reply", "email": "info@acme.in", "subject": "Re", "snippet": "yes",
                  "received_at": "2026-11-11 10:00:00", "message_id": "<q@x>"}]
        with mock.patch.object(rc, "is_configured", return_value=True), \
                mock.patch.object(rc, "fetch_events", return_value=reply), \
                mock.patch.object(runner, "send_smtp_email") as smtp:
            runner.run_followup_step(registry)
        self.assertEqual(lead_rows[0]["status"], "REPLIED")
        registry.save_master_safely.assert_called_once()
        smtp.assert_not_called()  # auto-send is OFF (and the lead replied anyway)

    def test_runner_auto_send_on(self):
        import run_all_scrapers as runner
        lead_rows = [{"lead_id": "L1", "company_name": "Acme", "email": "info@acme.in", "status": "EMAIL_SENT"}]
        registry = SimpleNamespace(leads=lead_rows, load_master=lambda: None, save_master_safely=mock.Mock(return_value=True))
        self.first_email("L1", (datetime.datetime.now() - datetime.timedelta(days=4)).strftime(TS))
        with mock.patch.object(rc, "is_configured", return_value=False), \
                mock.patch.dict(os.environ, {"FOLLOWUP_AUTO_SEND": "true"}), \
                mock.patch.object(runner, "send_smtp_email", return_value={"success": True}) as smtp:
            runner.run_followup_step(registry)
        smtp.assert_called_once()
        self.assertTrue(smtp.call_args.kwargs["bypass_duplicate_check"])
        self.assertEqual(fs.history(types=["email_sent"])["items"][0]["source"], "followup sequence #1")


if __name__ == "__main__":
    unittest.main()

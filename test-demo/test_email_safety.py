"""No bounces, no wrong recipients (2026-11-13: two Gmail accounts were blocked after
"Address not found" bounces, and auto-mail went to non-IT jobs, job seekers and a government office).

python -m unittest test_email_safety -v

No network: DNS and the mail-server conversation are mocked.
"""
import datetime
import os
import unittest
from types import SimpleNamespace
from unittest import mock

import email_checks as ec
import email_service
import lead_quality as lq
import run_all_scrapers as runner


class AddressRules(unittest.TestCase):
    def test_addresses_that_can_never_work(self):
        for a in ("noreply@acme.com", "no-reply@acme.com", "mailer-daemon@acme.com", "x@o75955.ingest.sentry.io",
                  "a@example.com", "abc", "0123456789abcdef0123@acme.com"):
            with self.subTest(a=a):
                self.assertTrue(ec.address_problem(a, policy=False))

    def test_policy_only_for_automatic_mail(self):
        for a in ("careers@neo.co", "jobs@sadservers.com", "hiring@stratirus.com", "hr@acme.in",
                  "wspierce@esd.wa.gov", "info@police.gov.in", "x@iitb.ac.in", "a@army.mil"):
            with self.subTest(a=a):
                self.assertTrue(ec.address_problem(a, policy=True))
                self.assertEqual(ec.address_problem(a, policy=False), "")

    def test_normal_addresses_pass(self):
        for a in ("contact@lightwitch-games.com", "iconstudiobiz@gmail.com", "ravi@acmefoods.in", "info@acme.co.uk"):
            self.assertEqual(ec.address_problem(a), "")


class MailboxCheck(unittest.TestCase):
    def setUp(self):
        ec._domain_catch_all.clear()
        ec._port25_blocked["value"] = None
        for p in (mock.patch.object(ec, "domain_accepts_mail", return_value=True),
                  mock.patch.object(ec, "_mx_hosts", return_value=["mx.acme.in"])):
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(ec._domain_catch_all.clear)
        self.addCleanup(lambda: ec._port25_blocked.update(value=None))

    def answer(self, real_code, random_code=550):
        return lambda mx, addrs, sender: {a: (real_code if not a.startswith("zz-") else random_code) for a in addrs}

    def test_confirmed_mailbox_is_valid(self):
        with mock.patch.object(ec, "_rcpt", side_effect=self.answer(250)):
            self.assertEqual(ec.verify_mailbox("ravi@acme.in")[0], ec.VALID)

    def test_rejected_mailbox_is_invalid(self):
        with mock.patch.object(ec, "_rcpt", side_effect=self.answer(550)):
            v, detail = ec.verify_mailbox("nobody@acme.in")
        self.assertEqual(v, ec.INVALID)
        self.assertIn("does not exist", detail)

    def test_domain_that_accepts_everything_is_catch_all(self):
        with mock.patch.object(ec, "_rcpt", side_effect=self.answer(250, random_code=250)):
            self.assertEqual(ec.verify_mailbox("ravi@acme.in")[0], ec.CATCH_ALL)

    def test_temporary_answer_is_unknown(self):
        with mock.patch.object(ec, "_rcpt", side_effect=self.answer(451)):
            self.assertEqual(ec.verify_mailbox("ravi@acme.in")[0], ec.UNKNOWN)

    def test_blocked_port_25_is_unknown_and_remembered(self):
        import socket
        with mock.patch.object(ec, "_rcpt", side_effect=socket.timeout()) as rcpt:
            self.assertEqual(ec.verify_mailbox("a@acme.in")[0], ec.UNKNOWN)
            self.assertEqual(ec.verify_mailbox("b@acme.in")[0], ec.UNKNOWN)
        self.assertEqual(rcpt.call_count, 1)  # no second slow attempt once the port is known to be blocked

    def test_domain_without_mail_server_is_invalid(self):
        with mock.patch.object(ec, "domain_accepts_mail", return_value=False):
            self.assertEqual(ec.verify_mailbox("a@no-such-domain-zz.in")[0], ec.INVALID)


class SendRefusesUnverified(unittest.TestCase):
    def setUp(self):
        for p in (mock.patch.dict(os.environ, {"SMTP_USER": "me@gmail.com", "SMTP_PASS": "x"}),
                  mock.patch.object(email_service, "get_already_sent_emails", return_value=set()),
                  mock.patch.object(email_service, "record_email_sent"),
                  mock.patch("settings_manager.load_settings", return_value={"excludedCompanies": []})):
            p.start()
            self.addCleanup(p.stop)

    def send(self, verdict, verify="strict"):
        fake = mock.MagicMock()
        with mock.patch.object(ec, "verify_mailbox", return_value=(verdict, "test")), \
                mock.patch.object(email_service.smtplib, "SMTP", return_value=fake):
            res = email_service.send_smtp_email("ravi@acme.in", "Hi", "Body", verify=verify)
        return res, fake.sendmail.called

    def test_strict_sends_only_to_confirmed_mailboxes(self):
        self.assertEqual(self.send(ec.VALID), ({"success": True}, True))
        for verdict in (ec.INVALID, ec.CATCH_ALL, ec.UNKNOWN):
            res, sent = self.send(verdict)
            self.assertFalse(res["success"] or sent, verdict)
            self.assertEqual(res["verify"], verdict)

    def test_lenient_allows_catch_all_but_never_a_missing_mailbox(self):
        self.assertTrue(self.send(ec.CATCH_ALL, "lenient")[1])
        self.assertFalse(self.send(ec.INVALID, "lenient")[1])
        self.assertFalse(self.send(ec.UNKNOWN, "lenient")[1])

    def test_no_check_for_follow_ups(self):
        with mock.patch.object(ec, "verify_mailbox", side_effect=AssertionError("must not be called")):
            fake = mock.MagicMock()
            with mock.patch.object(email_service.smtplib, "SMTP", return_value=fake):
                self.assertTrue(email_service.send_smtp_email("ravi@acme.in", "Hi", "Body", verify=None)["success"])


def lead(**kw):
    base = {"lead_id": "L1", "ai_category": "hiring_developer", "ai_score": "8", "email": "founder@acme.io",
            "first_seen_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "company_name": "Acme",
            "description": "Acme | Senior React Developer | Remote (Worldwide) | Contract. Need help building our web app."}
    base.update(kw)
    return base


class WhoGetsAutoMail(unittest.TestCase):
    """The leads judged by hand on 2026-11-13 (shortened)."""
    BLOCKED = {
        "non-IT job": lead(company_name="Native Mandarin speakers to record short lines from home",
                           description="Paid work from home: native Mandarin speakers wanted to record short scripted lines."),
        "job seeker": lead(company_name="Location: Dorset, UK", description="Location: Dorset, UK Remote: Yes Willing to "
                           "relocate: No Technologies: Python, Go Résumé/CV: https://x.co.uk Senior engineer, 15 years."),
        "sales role": lead(company_name="Strello Health", description="Strello Health | Toronto Clinic Sales & Onboarding "
                           "Lead | https://strello.health Strello is an AI front desk for clinics."),
        "US citizens only": lead(company_name="Lyra", description="Lyra | Full-Time | Applied AI Engineer | REMOTE (US "
                                 "Citizenship Required) | Building the AI that builds satellites."),
        "no agencies": lead(description="Stratirus | AI Developer | REMOTE (US only) | No agencies"),
        "UK or EU only": lead(company_name="SEEKING FREELANCER", description="SEEKING FREELANCER | Devops Engineer | "
                              "Remote - UK or EU getregistered is a better way to do event registration."),
        "on-site": lead(company_name="Pond AI", description="Pond AI | San Francisco | Onsite | https://joinpond.ai We "
                        "deliver custom AI agents."),
        "content creators": lead(company_name="3 Content Creators – $250/month",
                                 description="We're looking for 3 people to create short-form content for a mobile app."),
        "HR inbox": lead(email="careers@neo.co"),
        "government": lead(email="wspierce@esd.wa.gov"),
        "not a buyer": lead(ai_category="service_provider"),
        "low score": lead(ai_score="6"),
    }
    ALLOWED = {
        "website help": lead(company_name="Indie Game Studio Website Help (PAID)", email="contact@lightwitch-games.com",
                             description="Founder of a game studio. We are looking for a web developer to help with our "
                                         "website, a one time commission project."),
        "remote programmer": lead(company_name="Remote GameMaker Programmer for indie RTS", email="iconstudiobiz@gmail.com",
                                  description="iCon Studio TX is hiring a remote programmer to work on our upcoming game."),
        "standard": lead(),
    }

    def test_blocked(self):
        for name, l in self.BLOCKED.items():
            with self.subTest(name):
                self.assertTrue(lq.outreach_block_reason(l))
                self.assertFalse(lq.is_outreach_ready(l))

    def test_allowed(self):
        for name, l in self.ALLOWED.items():
            with self.subTest(name):
                self.assertEqual(lq.outreach_block_reason(l), "")


class HourlyRunHandlesChecks(unittest.TestCase):
    def setUp(self):
        self.calls = []
        for p in (mock.patch.object(runner, "AUTO_SEND_EMAIL", True),
                  mock.patch.object(runner, "is_outreach_ready", lambda l: True),
                  mock.patch.object(runner, "can_receive_mail", lambda e: True),
                  mock.patch.object(runner, "load_settings", lambda: {}),
                  mock.patch.object(runner, "format_signature", lambda s=None: ""),
                  mock.patch.object(runner.followup_store, "safe_log", lambda *a, **k: None),
                  mock.patch.object(runner, "bounces_last_24h", return_value=0),
                  mock.patch("email_service.get_already_sent_emails", return_value=set()),
                  mock.patch.object(runner.os.path, "exists",
                                    lambda p: False if p == "leads_new.csv" else os.path.exists(p))):
            p.start()
            self.addCleanup(p.stop)

    def run_with(self, results):
        reg = SimpleNamespace(leads=[{"lead_id": f"L{i}", "company_name": f"Acme {i}", "email": f"a{i}@acme{i}.in",
                                      "email_status": "NOT_SENT"} for i in range(len(results))])
        it = iter(results)
        def fake(to, sub, body, bypass_duplicate_check=False, company_name="", verify="strict"):
            self.calls.append(to)
            return next(it)
        with mock.patch.object(runner, "send_smtp_email", side_effect=fake):
            sent = runner.dispatch_pending_outreach_emails(reg, max_batch=0, delay_sec=0, daily_cap=50, sent_today=0)
        return sent, [l["email_status"] for l in reg.leads]

    def test_verdicts_set_the_right_status_and_are_not_send_failures(self):
        not_found = {"success": False, "verify": "invalid", "error": "does not exist"}
        catch_all = {"success": False, "verify": "catch_all", "error": "catch-all"}
        later = {"success": False, "verify": "unknown", "error": "timeout"}
        sent, statuses = self.run_with([not_found, not_found, not_found, catch_all, later, {"success": True}])
        self.assertEqual(sent, 1)                      # 3 rejected addresses did not stop the run
        self.assertEqual(statuses, ["INVALID", "INVALID", "INVALID", "UNVERIFIABLE", "NOT_SENT", "SENT"])

    def test_blocked_port_25_stops_the_run(self):
        blocked = {"success": False, "verify": "unknown", "error": "this computer cannot reach mail servers on port 25"}
        sent, _ = self.run_with([blocked, {"success": True}, {"success": True}])
        self.assertEqual((sent, len(self.calls)), (0, 1))

    def test_recent_bounces_pause_automatic_mail(self):
        with mock.patch.object(runner, "bounces_last_24h", return_value=runner.MAX_BOUNCES_PER_DAY):
            sent, _ = self.run_with([{"success": True}])
        self.assertEqual((sent, self.calls), (0, []))

    def test_daily_limit_default_is_low(self):
        self.assertLessEqual(runner.MAX_EMAILS_PER_DAY if not os.getenv("MAX_EMAILS_PER_DAY") else 50, 50)


class QuickScraperNeverMailsDirectly(unittest.TestCase):
    def test_flag(self):
        import scraper
        self.assertFalse(scraper.AUTO_SEND_EMAIL)


if __name__ == "__main__":
    unittest.main()


class BounceInboxIsTheSendingAccount(unittest.TestCase):
    def test_sending_account_first_and_other_inbox_too(self):
        import reply_checker as rc
        env = {"SMTP_USER": "sender@gmail.com", "SMTP_PASS": "a", "IMAP_USER": "other@gmail.com", "IMAP_PASSWORD": "b"}
        with mock.patch.dict(os.environ, env):
            users = [a["user"] for a in rc.imap_accounts()]
        self.assertEqual(users, ["sender@gmail.com", "other@gmail.com"])
        with mock.patch.dict(os.environ, {**env, "IMAP_USER": "Sender@gmail.com"}):
            self.assertEqual(len(rc.imap_accounts()), 1)   # same inbox is not read twice

    def test_one_broken_inbox_does_not_hide_bounces_from_the_other(self):
        import tempfile, reply_checker as rc
        tmp = tempfile.mkdtemp(prefix="imap_")
        bounce = (b"From: mailer-daemon@googlemail.com\r\nTo: sender@gmail.com\r\nSubject: Delivery Status Notification "
                  b"(Failure)\r\nMessage-ID: <dsn1@x>\r\n\r\nAddress not found: ravi@acme.in\r\n")

        class Imap:
            def __init__(self, host): self.user = None
            def login(self, user, pw):
                if user == "other@gmail.com":
                    raise rc.imaplib.IMAP4.error("bad password")
                self.user = user
            def select(self, *a, **k): return "OK", [b"1"]
            def uid(self, cmd, *args):
                if cmd == "search":
                    return "OK", [b"7"]
                return "OK", [(b"7 (BODY[] {1}", bounce)]
            def logout(self): pass

        env = {"SMTP_USER": "sender@gmail.com", "SMTP_PASS": "a", "IMAP_USER": "other@gmail.com", "IMAP_PASSWORD": "b"}
        with mock.patch.dict(os.environ, env), mock.patch.object(rc, "STATE_FILE", os.path.join(tmp, "s.json")), \
                mock.patch("builtins.print"):
            events = rc.fetch_events({"ravi@acme.in"}, imap_factory=Imap)
        self.assertEqual([(e["type"], e["email"], e["inbox"]) for e in events], [("bounce", "ravi@acme.in", "sender@gmail.com")])

    def test_old_state_file_keeps_its_position_for_the_old_inbox(self):
        import reply_checker as rc
        with mock.patch.dict(os.environ, {"IMAP_USER": "other@gmail.com", "SMTP_USER": "sender@gmail.com"}):
            uids = rc._uid_state({"last_uid": 50312})
        self.assertEqual(uids, {"other@gmail.com": 50312})   # the sending inbox starts from its own beginning

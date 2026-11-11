"""Tests for: editable follow-up templates, safer local-login bypass, HTML-escaped emails.

    python -m unittest test_followup_extras -v
"""
import email
import json
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

from flask import Flask, jsonify

import api_auth
import email_service
import followup_sequence as seq


class Templates(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.patch = mock.patch.object(seq, "TEMPLATES_FILE", os.path.join(self.tmp.name, "tpl.json"))
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def good(self):
        return [{"subject": "Re: {original_subject}", "body": f"Hi {{name}}, note {i} for {{company}} ({{first_date}})"}
                for i in range(3)]

    def test_defaults_when_nothing_saved(self):
        self.assertEqual(seq.load_templates(), seq.DEFAULT_TEMPLATES)
        self.assertFalse(seq.templates_customized())

    def test_save_load_reset(self):
        saved = seq.save_templates(self.good())
        self.assertEqual(seq.load_templates(), saved)
        self.assertTrue(seq.templates_customized())
        item = {"lead_id": "L1", "lead_name": "Acme", "email": "a@b.in", "step": 1, "total_steps": 3,
                "followups_sent": 0, "first_sent_at": "2026-11-08 10:00:00", "original_subject": "Hello"}
        msg = seq.render(item)
        self.assertEqual(msg["subject"], "Re: Hello")
        self.assertIn("note 0 for Acme (08 Nov)", msg["body"])
        self.assertEqual(seq.reset_templates(), seq.DEFAULT_TEMPLATES)
        self.assertFalse(seq.templates_customized())

    def test_validation(self):
        cases = [
            (self.good()[:2], "Exactly 3"),
            ("not a list", "Exactly 3"),
            ([*self.good()[:2], {"subject": "", "body": "x"}], "required"),
            ([*self.good()[:2], {"subject": "x" * 201, "body": "x"}], "200 characters"),
            ([*self.good()[:2], {"subject": "x", "body": "x" * 3001}], "3000 characters"),
            ([{"subject": "Hi {firstname}", "body": "x"}, *self.good()[1:]], "unknown placeholder {firstname}"),
            ([{"subject": "Hi", "body": "Price {0} off"}, *self.good()[1:]], "unknown placeholder"),
            ([{"subject": "Hi", "body": "Bad { brace"}, *self.good()[1:]], "unmatched"),
            ([{"subject": "Hi", "body": "{company.__class__}"}, *self.good()[1:]], "unknown placeholder"),
        ]
        for templates, msg in cases:
            with self.subTest(msg=msg):
                with self.assertRaises(seq.TemplateError) as ctx:
                    seq.save_templates(templates)
                self.assertIn(msg, str(ctx.exception))
        self.assertFalse(seq.templates_customized())

    def test_broken_file_falls_back_to_defaults(self):
        with open(seq.TEMPLATES_FILE, "w", encoding="utf-8") as f:
            f.write("{not json")
        self.assertEqual(seq.load_templates(), seq.DEFAULT_TEMPLATES)

    def test_api(self):
        import app as app_module
        client = app_module.app.test_client()
        ok = SimpleNamespace(status_code=200, json=lambda: {"email": "owner@example.com"})
        h = {"Authorization": "Bearer t"}
        with mock.patch("api_auth.requests.get", return_value=ok), mock.patch("api_auth.ALLOWED_EMAILS", set()):
            self.assertEqual(client.get("/api/followups/templates").status_code, 401)
            body = client.get("/api/followups/templates", headers=h).get_json()
            self.assertFalse(body["customized"])
            self.assertEqual(body["placeholders"], list(seq.PLACEHOLDERS))
            bad = client.put("/api/followups/templates", headers=h, json={"templates": [{"subject": "x"}]})
            self.assertEqual(bad.status_code, 400)
            good = client.put("/api/followups/templates", headers=h, json={"templates": self.good()})
            self.assertTrue(good.get_json()["customized"])
            reset = client.delete("/api/followups/templates", headers=h)
            self.assertFalse(reset.get_json()["customized"])


class LocalLoginBypass(unittest.TestCase):
    """The X-Demo-User shortcut must work only for a localhost server, from localhost."""

    def make(self, bind_host):
        app = Flask(__name__)
        with mock.patch.dict(os.environ, {"API_AUTH_DISABLED": ""}):
            api_auth.init_auth(app, bind_host)

        @app.route("/api/ping")
        def ping():
            return jsonify(ok=True)
        return app.test_client()

    def get(self, client, remote="127.0.0.1"):
        return client.get("/api/ping", headers={"X-Demo-User": "true"}, environ_base={"REMOTE_ADDR": remote}).status_code

    def test_allowed_on_local_server_from_local_machine(self):
        self.assertEqual(self.get(self.make("127.0.0.1")), 200)

    def test_blocked_when_server_is_exposed(self):
        client = self.make("0.0.0.0")
        self.assertEqual(self.get(client, "127.0.0.1"), 401)  # e.g. via a proxy on the same host
        self.assertEqual(self.get(client, "203.0.113.9"), 401)

    def test_blocked_from_other_machine(self):
        self.assertEqual(self.get(self.make("127.0.0.1"), "192.168.1.20"), 401)

    def test_can_be_switched_off(self):
        client = self.make("127.0.0.1")
        with mock.patch.dict(os.environ, {"LOCAL_DEMO_LOGIN": "false"}):
            self.assertEqual(self.get(client), 401)


class EmailHtmlEscaping(unittest.TestCase):
    def test_message_text_is_escaped_in_html_part(self):
        sent = {}

        class FakeSMTP:
            def __init__(self, *a, **k):
                pass

            def starttls(self):
                pass

            def login(self, *a):
                pass

            def sendmail(self, frm, to, raw):
                sent["raw"] = raw

            def quit(self):
                pass

        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(email_service, "SENT_LOG_FILE", os.path.join(d, "sent.csv")), \
                mock.patch.dict(os.environ, {"SMTP_USER": "u@gmail.com", "SMTP_PASS": "p"}), \
                mock.patch.object(email_service.smtplib, "SMTP", FakeSMTP):
            res = email_service.send_smtp_email("x@acme.in", "Hi", "Hello <Acme & Co>\n<script>x</script>",
                                                bypass_duplicate_check=True)
        self.assertTrue(res["success"])
        msg = email.message_from_string(sent["raw"])
        parts = {p.get_content_type(): p.get_payload(decode=True).decode() for p in msg.walk() if not p.is_multipart()}
        self.assertIn("Hello &lt;Acme &amp; Co&gt;", parts["text/html"])
        self.assertNotIn("<script>", parts["text/html"])
        self.assertIn("Hello <Acme & Co>", parts["text/plain"])  # plain text stays as written


if __name__ == "__main__":
    unittest.main()

"""Phone kit (WhatsApp text + call script) and the 'mailed - now call' step."""
import datetime
import unittest
from unittest import mock

import lead_status as ls
import phone_kit as pk
from test_lead_status import lead, act, stage, NOW


class Kit(unittest.TestCase):
    def test_template_without_any_key(self):
        with mock.patch.dict("os.environ", {"ANTHROPIC_API_KEY": "", "ANTHROPIC_AUTH_TOKEN": "", "GEMINI_API_KEY": ""}):
            kit = pk.phone_kit(lead(company_name="Need a Shopify store for my brand", full_name="Priya Shah"), mailed=True)
        self.assertEqual(kit["by"], "template")
        self.assertIn("Hi Priya,", kit["whatsapp"])
        self.assertIn("sent you a short e-mail", kit["whatsapp"])
        self.assertEqual(len(kit["questions"]), 3)
        self.assertGreaterEqual(len(kit["objections"]), 3)

    def test_handles_are_not_names(self):
        self.assertNotIn("bhalenduc", pk.template_kit(lead(full_name="bhalenduc"))["whatsapp"])

    def test_ai_answer_is_used_and_bad_ai_falls_back(self):
        class Resp:
            status_code = 200
            def json(self):
                return {"candidates": [{"content": {"parts": [{"text": '{"whatsapp": "Hi from AI?", "questions": ["Q1"], "objections": {"No": "OK"}}'}]}}]}
        with mock.patch.dict("os.environ", {"ANTHROPIC_API_KEY": "", "ANTHROPIC_AUTH_TOKEN": "", "GEMINI_API_KEY": "k"}):
            kit = pk.phone_kit(lead(), post=lambda *a, **k: Resp())
            self.assertEqual((kit["by"], kit["whatsapp"]), ("ai", "Hi from AI?"))
            self.assertTrue(kit["call_opening"])  # missing parts come from the template
            bad = pk.phone_kit(lead(), post=lambda *a, **k: type("R", (), {"status_code": 500})())
        self.assertEqual(bad["by"], "template")
        self.assertIn("Gemini", bad["note"])

    def test_whatsapp_link(self):
        self.assertEqual(pk.whatsapp_link("98250 12345", "Hi there"), "https://wa.me/919825012345?text=Hi%20there")
        self.assertEqual(pk.whatsapp_link("123"), "")


class CallAfterMail(unittest.TestCase):
    sent = [{"email": "a@acme.in", "sent_at": "2026-11-16 10:00:00"}]

    def test_mailed_lead_with_phone_needs_a_call(self):
        self.assertEqual(stage(lead(email="a@acme.in", mobile_number="9825012345"), self.sent), "call_after_mail")
        called = [act("call", "2026-11-16 12:00:00")]
        self.assertEqual(stage(lead(email="a@acme.in", mobile_number="9825012345"), self.sent, called), "waiting")
        self.assertEqual(stage(lead(email="a@acme.in"), self.sent), "waiting")  # no phone: mail is all we can do
        self.assertEqual(stage(lead(email="a@acme.in", mobile_number="9825012345", ai_category="job_seeker"), self.sent), "waiting")

    def test_list_item_has_whatsapp_text(self):
        res = ls.stage_list([lead(email="a@acme.in", mobile_number="9825012345")], self.sent, [], "call_after_mail", now=NOW)
        self.assertTrue(res["items"][0]["whatsapp"].startswith("https://wa.me/919825012345?text="))


if __name__ == "__main__":
    unittest.main()

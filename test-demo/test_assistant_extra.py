"""The assistant's guide, memory, extra look-up tools and the no-key answers."""
import datetime
import os
import tempfile
import unittest
from unittest import mock

import assistant_knowledge as kb
import chat_ai
import chat_assistant
import chat_rules_extra as rules
from test_lead_status import lead, act

TODAY = datetime.date(2026, 11, 18)
NO_KEYS = {"ANTHROPIC_API_KEY": "", "ANTHROPIC_AUTH_TOKEN": "", "GEMINI_API_KEY": ""}


def ctx():
    leads = [
        lead(lead_id="A", email="a@acme.in", mobile_number="9825012345", ai_score="8", first_seen_at="2026-11-10 10:00:00"),
        lead(lead_id="B", mobile_number="9825099999", ai_score="6", first_seen_at="2026-11-17 09:00:00", company_name="Need SEO help"),
        lead(lead_id="C", email="c@x.in", ai_score="9", first_seen_at="2026-11-17 11:00:00"),
    ]
    sent = [{"email": "a@acme.in", "sent_at": "2026-11-16 10:00:00"}]
    acts = [act("call", "2026-11-17 12:00:00", lead_id="B")]
    return {"leads": leads, "sent": sent, "acts": acts, "runs": [{"start_time": "2026-11-17 01:00:00", "status": "success"}],
            "settings": {}, "today": TODAY.isoformat()}


class Memory(unittest.TestCase):
    def setUp(self):
        self.p = mock.patch.object(kb, "MEMORY_FILE", os.path.join(tempfile.mkdtemp(), "m.json"))
        self.p.start()

    def tearDown(self):
        self.p.stop()

    def test_remember_forget_and_no_secrets(self):
        self.assertTrue(kb.remember("we never call before 11 am")["new"])
        self.assertFalse(kb.remember("We never call before 11 AM")["new"])  # no duplicates
        self.assertIn("never call before 11", kb.summary_for_prompt())
        with self.assertRaises(ValueError):
            kb.remember("api_key: AIzaSyAbcdefghijklmnopqrstu")
        self.assertEqual(kb.forget(1)["text"], "we never call before 11 am")
        with self.assertRaises(ValueError):
            kb.forget(5)

    def test_ratings_become_examples(self):
        kb.rate("aaje shu karu", "Call 3 leads", True)
        kb.rate("report", "bad answer", False)
        text = kb.examples_for_prompt()
        self.assertIn("Q: aaje shu karu", text)
        self.assertIn("NOT happy", text)

    def test_no_key_teach_and_list(self):
        c = ctx()
        self.assertIn("remember", rules.answer("remember: hot leads first", c, "en")["reply"])
        self.assertIn("hot leads first", rules.answer("what do you remember", c, "en")["reply"])
        self.assertIn("Bhuli", rules.answer("bhuli ja 1", c, "gu")["reply"])


class Guide(unittest.TestCase):
    def test_search_finds_the_right_section(self):
        self.assertEqual(kb.search("how does the mail flow work")[0]["title"], "Mail flow (who gets an e-mail and when)")
        self.assertTrue(kb.search("whatsapp call script")[0]["title"].startswith("Phone and WhatsApp"))
        self.assertEqual(kb.search(""), [])


class Dates(unittest.TestCase):
    def test_formats(self):
        self.assertEqual(rules.dates("from 1 nov to 15 nov", TODAY), ("2026-11-01", "2026-11-15"))
        self.assertEqual(rules.dates("2026-11-10 thi", TODAY), ("2026-11-10", "2026-11-18"))
        self.assertEqual(rules.dates("on 10/11", TODAY), ("2026-11-10", "2026-11-10"))
        self.assertEqual(rules.dates("10 dec", TODAY)[0], "2025-12-10")  # a future day means last year
        self.assertEqual(rules.dates("hot leads score 7-10", TODAY), (None, None))


class NoKeyAnswers(unittest.TestCase):
    def ask(self, q):
        with mock.patch.dict(os.environ, NO_KEYS), mock.patch.object(kb, "MEMORY_FILE", os.path.join(tempfile.mkdtemp(), "m.json")):
            return chat_assistant.answer(q, ctx)

    def test_flow_questions(self):
        self.assertIn("leads need you today", self.ask("What should I do today?")["reply"])
        self.assertIn("limit", self.ask("How does the mail flow work?")["reply"].lower())
        r = self.ask("Show mailed leads I have not called")
        self.assertEqual(r["table"]["rows"][0]["lead_id"], "A")
        self.assertIn("2026-11-17: 2 new leads", self.ask("What happened on 17 nov?")["reply"])
        self.assertIn("Report 2026-11-01 to 2026-11-18", self.ask("report from 1 nov")["reply"])
        self.assertIn("Hot, warm, cold", self.ask("lead hot kevi rite bane?")["reply"])
        self.assertIn("Next steps", self.ask("why is a lead in not a fit?")["reply"])


class AiTools(unittest.TestCase):
    def test_tools_registered_and_private(self):
        names = {t["name"] for t in chat_ai.TOOLS}
        self.assertTrue({"today_todo", "leads_by_next_step", "report", "mail_flow", "day_log", "how_it_works", "remember"} <= names)
        out = chat_ai.run_tool("leads_by_next_step", {"step": "call_after_mail"}, ctx())
        self.assertEqual(chat_ai._table_rows("leads_by_next_step", out)[0]["phone"], "9825012345")
        seen = str(chat_ai._for_model(chat_ai._strip(out)))
        self.assertNotIn("98250", seen)
        self.assertNotIn("a@acme.in", seen)
        self.assertIn("error", chat_ai.run_tool("leads_by_next_step", {"step": "nope"}, ctx()))
        self.assertEqual(chat_ai.run_tool("day_log", {"date": "2026-11-17"}, ctx())["new_leads"], 2)
        self.assertIn("sections", chat_ai.run_tool("how_it_works", {"question": "follow up"}, ctx()))

    def test_prompt_has_guide_and_facts(self):
        with mock.patch.object(kb, "MEMORY_FILE", os.path.join(tempfile.mkdtemp(), "m.json")):
            kb.remember("never mail on Sunday")
            sysmsg = chat_ai._system(ctx())
        self.assertIn("Mail flow", sysmsg)
        self.assertIn("never mail on Sunday", sysmsg)


class FeedbackApi(unittest.TestCase):
    def test_feedback(self):
        import app
        app.app.config["TESTING"] = True
        c = app.app.test_client()
        c.environ_base["HTTP_X_DEMO_USER"] = "true"
        with mock.patch.object(kb, "MEMORY_FILE", os.path.join(tempfile.mkdtemp(), "m.json")):
            self.assertEqual(c.post("/api/chat/feedback", json={"question": "q", "answer": "a", "helpful": True}).get_json()["examples"], 1)
            self.assertEqual(c.post("/api/chat/feedback", json={"question": "", "answer": "a"}).status_code, 400)


if __name__ == "__main__":
    unittest.main()

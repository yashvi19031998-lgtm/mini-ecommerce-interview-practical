"""AI chat engine: answers any question from read-only look-up tools; contact details never reach the AI."""
import json
import os
import unittest
from types import SimpleNamespace
from unittest import mock

import chat_ai
import chat_assistant as ca


def lead(i, **kw):
    base = {"lead_id": f"LEAD-{i:05d}", "company_name": f"Company {i}", "email": "", "mobile_number": "",
            "location": "Ahmedabad, India", "source": "Reddit (r/forhire)", "ai_category": "client_project",
            "ai_score": "5", "status": "NEW", "email_status": "NOT_SENT", "first_seen_at": "2026-11-16 09:00:00",
            "description": "Need a React app"}
    base.update(kw)
    return base


LEADS = [
    lead(1, company_name="Acme Clinic", email="info@acme.in", ai_score="9", mobile_number="+91 99999 11111"),
    lead(2, company_name="Beta Shop", email="hi@beta.in", ai_score="8", email_status="SENT"),
    lead(3, company_name="Gamma Labs", ai_score="3", source="Freelancer.com (API)", location="Pune"),
    lead(4, company_name="Delta Corp", email="x@delta.in", ai_score="", ai_category="prospect_signal",
         first_seen_at="2026-11-10 10:00:00"),
]
CTX = {"leads": LEADS, "runs": [{"scraper_name": "freelancer_api_scraper.py (x)", "start_time": "2026-11-16 08:00:00",
                                 "records_collected": "20", "new_leads_added": "4", "status": "Success"}],
       "sent": [{"email": "hi@beta.in", "sent_at": "2026-11-16 10:00:00", "subject": "Hello"}],
       "acts": [{"lead_id": "LEAD-00002", "type": "reply", "occurred_at": "2026-11-16 12:00:00",
                 "lead_email": "hi@beta.in", "summary": "Interested"}],
       "settings": {}, "today": "2026-11-16"}


class Tools(unittest.TestCase):
    def test_find_and_count(self):
        r = chat_ai.t_find_leads(CTX, min_score=7, limit=5)
        self.assertEqual([x["lead_id"] for x in r["rows"]], ["LEAD-00001", "LEAD-00002"])
        self.assertEqual(chat_ai.t_count_leads(CTX, source="freelancer")["total"], 1)
        self.assertEqual(chat_ai.t_count_leads(CTX, has_email=True)["total"], 3)
        self.assertEqual(chat_ai.t_count_leads(CTX, mail="pending")["total"], 2)
        self.assertEqual(chat_ai.t_count_leads(CTX, group_by="score_band")["groups"],
                         {"high": 2, "low": 1, "unscored": 1})
        self.assertEqual(chat_ai.t_count_leads(CTX, category="buyer", city="ahmedabad")["total"], 2)
        self.assertEqual(chat_ai.t_count_leads(CTX, found_from="2026-11-15")["total"], 3)

    def test_other_tools(self):
        self.assertEqual(chat_ai.t_email_stats(CTX, date_from="2026-11-16")["emails_sent"], 1)
        self.assertEqual(chat_ai.t_scraper_stats(CTX)["scrapers"]["freelancer_api_scraper.py"]["new_leads"], 4)
        self.assertEqual(chat_ai.t_get_lead(CTX, name="beta")["activities"][0]["type"], "reply")
        self.assertEqual(chat_ai.t_overview(CTX)["total_leads"], 4)
        self.assertIn("error", chat_ai.run_tool("find_leads", {"min_score": "abc"}, CTX))
        self.assertIn("error", chat_ai.run_tool("nope", {}, CTX))

    def test_contact_details_hidden_from_the_model(self):
        seen = json.dumps(chat_ai._for_model(chat_ai._strip(chat_ai.t_get_lead(CTX, name="acme"))))
        self.assertNotIn("info@acme.in", seen)
        self.assertNotIn("99999", seen)
        self.assertIn('"has_email": true', seen)
        self.assertNotIn("hi@beta.in", json.dumps(chat_ai._for_model(chat_ai.t_email_stats(CTX))))


def _block(**kw):
    return SimpleNamespace(**kw)


class ClaudeLoop(unittest.TestCase):
    def test_tool_loop_and_table(self):
        sent_payloads = []
        responses = [
            SimpleNamespace(stop_reason="tool_use", content=[
                _block(type="tool_use", id="t1", name="find_leads", input={"min_score": 7})]),
            SimpleNamespace(stop_reason="end_turn", content=[_block(type="text", text="2 hot leads: Acme and Beta.")]),
        ]
        client = mock.Mock()

        def create(**kw):
            sent_payloads.append(json.loads(json.dumps(kw["messages"], default=lambda o: o.__dict__)))
            return responses.pop(0)
        client.beta.messages.create.side_effect = create
        r = chat_ai.ask("show hot leads", CTX, claude_client=client)
        self.assertEqual(r["engine"], "claude")
        self.assertEqual(r["reply"], "2 hot leads: Acme and Beta.")
        self.assertEqual(r["table"]["rows"][0]["email"], "info@acme.in")      # the app's table keeps contacts
        tool_result = sent_payloads[1][-1]["content"][0]
        self.assertEqual(tool_result["tool_use_id"], "t1")
        self.assertNotIn("info@acme.in", tool_result["content"])             # ...the model never saw them
        kw = client.beta.messages.create.call_args.kwargs
        self.assertEqual(kw["fallbacks"], "default")

    def test_refusal_falls_back_to_rules(self):
        client = mock.Mock()
        client.beta.messages.create.return_value = SimpleNamespace(stop_reason="refusal", content=[])
        r = ca.answer("Aaje ketla nava leads?", lambda: dict(CTX), claude_client=client)
        self.assertEqual(r["engine"], "rules")
        self.assertIn("AI not available", r["note"])


class GeminiLoop(unittest.TestCase):
    def test_function_calling(self):
        bodies = []
        replies = [
            {"candidates": [{"content": {"parts": [{"functionCall": {"name": "count_leads", "args": {"source": "freelancer"}}}]}}]},
            {"candidates": [{"content": {"parts": [{"text": "1 lead from Freelancer.com."}]}}]},
        ]

        def post(url, json=None, headers=None, timeout=None):
            bodies.append(json)
            return mock.Mock(status_code=200, json=lambda: replies.pop(0))
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": "k", "ANTHROPIC_API_KEY": "", "ANTHROPIC_AUTH_TOKEN": ""}):
            r = ca.answer("Freelancer na ketla leads che?", lambda: dict(CTX), history=[{"role": "user", "text": "hi"}],
                          ai_post=post)
        self.assertEqual((r["engine"], r["reply"]), ("gemini", "1 lead from Freelancer.com."))
        fr = bodies[1]["contents"][-1]["parts"][0]["functionResponse"]
        self.assertEqual(fr["response"]["result"]["total"], 1)
        self.assertEqual(bodies[0]["contents"][0]["parts"][0]["text"], "hi")   # history goes along

    def test_no_key_means_rules(self):
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": "", "ANTHROPIC_API_KEY": "", "ANTHROPIC_AUTH_TOKEN": ""}):
            self.assertIsNone(chat_ai.ask("anything", dict(CTX)))
            r = ca.answer("what is the weather", lambda: dict(CTX))
        self.assertIn("GEMINI_API_KEY", r["note"])


if __name__ == "__main__":
    unittest.main()

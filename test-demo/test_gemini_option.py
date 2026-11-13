"""Free Gemini option for lead qualification (lead_quality.qualify_one_gemini / qualify_leads).

python -m unittest test_gemini_option -v

No network: requests.post is replaced by a fake that returns Gemini-shaped JSON.
"""
import json
import os
import unittest
from types import SimpleNamespace
from unittest import mock

import lead_quality as lq


class FakeResp:
    def __init__(self, status=200, payload=None, text=""):
        self.status_code, self._payload, self.text = status, payload, text

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


def answer(obj_or_text, status=200):
    text = obj_or_text if isinstance(obj_or_text, str) else json.dumps(obj_or_text)
    return FakeResp(status, {"candidates": [{"content": {"parts": [{"text": text}]}}]})


GOOD = {"category": "client_project", "score": 8, "summary": "Game studio needs a website.",
        "requirement": "Website", "tech_stack": "", "budget": "", "reason": "Clear paid web project"}
LEAD = {"lead_id": "L1", "company_name": "Indie Game Studio Website Help (PAID)",
        "description": "We are looking for a web developer to help with our website.", "email": "a@b.in"}


class OneCall(unittest.TestCase):
    def setUp(self):
        p = mock.patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"})
        p.start()
        self.addCleanup(p.stop)

    def test_request_shape_and_parsed_answer(self):
        post = mock.MagicMock(return_value=answer(GOOD))
        res = lq.qualify_one_gemini(LEAD, post=post)
        self.assertEqual((res["category"], res["score"]), ("client_project", 8))
        url, = post.call_args.args
        kw = post.call_args.kwargs
        self.assertIn(f"/models/{lq.GEMINI_MODEL}:generateContent", url)
        self.assertNotIn("test-key", url)                       # key goes in a header, never in the URL / logs
        self.assertEqual(kw["headers"]["x-goog-api-key"], "test-key")
        self.assertEqual(kw["json"]["generationConfig"]["responseMimeType"], "application/json")
        self.assertIn("Indie Game Studio", kw["json"]["contents"][0]["parts"][0]["text"])

    def test_json_inside_code_fences_and_score_clamped(self):
        res = lq.qualify_one_gemini(LEAD, post=lambda *a, **k: answer("```json\n" + json.dumps({**GOOD, "score": "14"}) + "\n```"))
        self.assertEqual(res["score"], 10)

    def test_bad_answers_raise(self):
        for bad in ("not json at all", json.dumps({**GOOD, "category": "buyer"}), json.dumps({**GOOD, "score": "high"})):
            with self.subTest(bad=bad[:30]):
                with self.assertRaises(ValueError):
                    lq.qualify_one_gemini(LEAD, post=lambda *a, **k: answer(bad))

    def test_limit_and_errors(self):
        for status in (429, 402):
            with self.assertRaises(lq.GeminiRateLimited):
                lq.qualify_one_gemini(LEAD, post=lambda *a, **k: FakeResp(status, {"error": {"status": "RESOURCE_EXHAUSTED"}}))
        with self.assertRaises(RuntimeError):
            lq.qualify_one_gemini(LEAD, post=lambda *a, **k: FakeResp(400, {"error": {"message": "bad model"}}))
        with self.assertRaises(RuntimeError):  # blocked prompt: no candidates
            lq.qualify_one_gemini(LEAD, post=lambda *a, **k: FakeResp(200, {"promptFeedback": {"blockReason": "SAFETY"}}))

    def test_no_key(self):
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
            with self.assertRaises(RuntimeError):
                lq.qualify_one_gemini(LEAD, post=mock.MagicMock())


class WhichEngine(unittest.TestCase):
    def run_qualify(self, env, gemini=None, claude=None):
        reg = SimpleNamespace(leads=[dict(LEAD, lead_id=f"L{i}", first_seen_at="2026-11-13 10:00:00") for i in range(4)])
        with mock.patch.dict(os.environ, env), \
                mock.patch.object(lq, "_get_client", return_value=claude), \
                mock.patch.object(lq, "qualify_one_gemini", side_effect=gemini or (lambda lead: dict(GOOD))) as g, \
                mock.patch.object(lq, "qualify_one", return_value=dict(GOOD, reason="claude")) as c, \
                mock.patch.object(lq, "GEMINI_DELAY_SEC", 0), mock.patch("builtins.print"):
            lq.qualify_leads(reg, limit=10)
        return reg.leads, g, c

    def test_claude_first_when_its_key_exists(self):
        leads, g, c = self.run_qualify({"GEMINI_API_KEY": "k"}, claude=object())
        self.assertEqual((c.call_count, g.call_count), (4, 0))

    def test_gemini_when_only_its_key_exists(self):
        leads, g, c = self.run_qualify({"GEMINI_API_KEY": "k"})
        self.assertEqual((g.call_count, c.call_count), (4, 0))
        self.assertTrue(all(l["ai_reason"] == GOOD["reason"] for l in leads))

    def test_rules_when_no_key(self):
        leads, g, c = self.run_qualify({"GEMINI_API_KEY": ""})
        self.assertEqual((g.call_count, c.call_count), (0, 0))
        self.assertTrue(all(l["ai_qualified_at"] for l in leads))   # still classified, by the rules

    def test_limit_switches_the_rest_of_the_run_to_rules(self):
        calls = iter([dict(GOOD), lq.GeminiRateLimited("limit")])
        def gem(lead):
            r = next(calls)
            if isinstance(r, Exception):
                raise r
            return r
        leads, g, c = self.run_qualify({"GEMINI_API_KEY": "k"}, gemini=gem)
        self.assertEqual(g.call_count, 2)                            # no more calls after the limit
        self.assertEqual(sum(l["ai_reason"] == GOOD["reason"] for l in leads), 1)
        self.assertTrue(all(l["ai_qualified_at"] for l in leads))

    def test_one_bad_answer_only_affects_that_lead(self):
        calls = iter([ValueError("bad json"), dict(GOOD), dict(GOOD), dict(GOOD)])
        def gem(lead):
            r = next(calls)
            if isinstance(r, Exception):
                raise r
            return r
        leads, g, c = self.run_qualify({"GEMINI_API_KEY": "k"}, gemini=gem)
        self.assertEqual(g.call_count, 4)
        self.assertEqual(sum(l["ai_reason"] == GOOD["reason"] for l in leads), 3)


if __name__ == "__main__":
    unittest.main()

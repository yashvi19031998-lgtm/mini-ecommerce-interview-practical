"""Reply Today: fresh buyer posts without e-mail, a ready reply for each, and 'replied' marking."""
import datetime
import os
import unittest
from types import SimpleNamespace
from unittest import mock

import app
import followup_store
import reply_today as rt

AUTH = {"X-Demo-User": "true"}
TODAY = datetime.date(2026, 11, 14)


def lead(i, **kw):
    base = {"id": f"L{i}", "Company Name": f"Need a React dashboard for our clinic {i}", "ai_category": "client_project",
            "ai_score": "8", "Email": "", "contact_channel": "reddit", "posted_at": "2026-11-13 10:00:00",
            "source_url": f"https://reddit.com/r/forhire/{i}", "Source": "Reddit (r/forhire)",
            "ai_requirement": "React admin dashboard with login and charts for a clinic", "ai_tech_stack": "React"}
    base.update(kw)
    return base


class BuildItems(unittest.TestCase):
    def test_only_fresh_untouched_buyers_without_email(self):
        leads = [lead(1), lead(2, ai_score="10"), lead(3, Email="a@b.com"), lead(4, ai_category="prospect_signal"),
                 lead(5, posted_at="2026-11-01"), lead(6), lead(7, Status="REPLIED"), lead(8, ai_score="")]
        items, counts = rt.build_items(leads, {"L6"}, days=3, today=TODAY)
        self.assertEqual([i["id"] for i in items], ["L2", "L1", "L8"])  # best score first, unscored last
        self.assertEqual(counts, {"total": 3, "by_channel": {"reddit": 3}})
        self.assertEqual(items[0]["url"], "https://reddit.com/r/forhire/2")

    def test_falls_back_to_first_seen(self):
        items, _ = rt.build_items([lead(1, posted_at="", first_seen_at="2026-11-14 09:00")], set(), today=TODAY)
        self.assertEqual(items[0]["posted"], "2026-11-14")


class Drafts(unittest.TestCase):
    def test_template_without_ai_key(self):
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "", "ANTHROPIC_AUTH_TOKEN": "", "GEMINI_API_KEY": ""}):
            d = rt.draft_reply(lead(1))
        self.assertEqual(d["by"], "template")
        self.assertIn("React admin dashboard", d["text"])
        self.assertIn("No AI key", d["note"])

    def test_template_per_channel_and_no_junk_titles(self):
        bid = rt.template_reply(lead(1, contact_channel="freelancer_bid"))
        self.assertTrue(bid.startswith("Hello, I have read your project"))
        junk = rt.template_reply(lead(2, **{"Company Name": "Thoughtworks | 11 Openings", "ai_requirement": "Software"}))
        self.assertNotIn("Thoughtworks", junk)
        self.assertNotIn("You need", junk)  # a short label is left out
        seo = rt.template_reply(lead(3, ai_requirement="SEO and Instagram ads for a bakery in Pune every month"))
        self.assertIn("SEO, social media", seo)

    def test_claude_reply(self):
        msg = SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text="Hi! A tailored reply.")])
        client = mock.Mock()
        client.beta.messages.create.return_value = msg
        d = rt.draft_reply(lead(1), client=client)
        self.assertEqual(d, {"text": "Hi! A tailored reply.", "by": "ai", "note": ""})
        kw = client.beta.messages.create.call_args.kwargs
        self.assertEqual(kw["fallbacks"], "default")
        self.assertIn("React admin dashboard", kw["messages"][0]["content"])

    def test_claude_refusal_falls_back_to_template(self):
        client = mock.Mock()
        client.beta.messages.create.return_value = SimpleNamespace(stop_reason="refusal", content=[])
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
            d = rt.draft_reply(lead(1), client=client)
        self.assertEqual(d["by"], "template")
        self.assertIn("declined", d["note"])


class Endpoints(unittest.TestCase):
    def setUp(self):
        self.client = app.app.test_client()
        mock.patch.object(app, "read_leads", return_value=[lead(1), lead(2, Email="x@y.com")]).start()
        mock.patch.object(followup_store, "_read_all", return_value=[]).start()
        self.addCleanup(mock.patch.stopall)

    def test_list_draft_done(self):
        with mock.patch.object(rt.datetime, "date", wraps=datetime.date) as d:
            d.today.return_value = TODAY
            r = self.client.get("/api/followups/reply-today?days=3", headers=AUTH).get_json()
        self.assertEqual([i["id"] for i in r["items"]], ["L1"])
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "", "ANTHROPIC_AUTH_TOKEN": "", "GEMINI_API_KEY": ""}):
            d = self.client.post("/api/followups/reply-draft", json={"lead_id": "L1"}, headers=AUTH).get_json()
        self.assertTrue(d["success"] and d["text"])
        with mock.patch.object(followup_store, "add_activity", return_value={"id": "A1"}) as add:
            r = self.client.post("/api/followups/reply-done", json={"lead_id": "L1", "text": d["text"]}, headers=AUTH)
        self.assertEqual(r.status_code, 200)
        args, kw = add.call_args
        self.assertEqual(args[:3], ("L1", "note", "Replied on Reddit comment or DM"))
        self.assertEqual(kw["source"], "reply today")

    def test_unknown_lead_and_bad_days(self):
        self.assertEqual(self.client.post("/api/followups/reply-draft", json={"lead_id": "nope"}, headers=AUTH).status_code, 404)
        self.assertEqual(self.client.get("/api/followups/reply-today?days=x", headers=AUTH).status_code, 400)


if __name__ == "__main__":
    unittest.main()

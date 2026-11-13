"""In-app assistant (chat_assistant.py) and website chatbot (website_chatbot.py + public routes).

python -m unittest test_chatbots -v

No network and no real data: small in-memory leads; the website lead "save" goes to a temporary file.
"""
import csv
import datetime
import json
import os
import shutil
import tempfile
import unittest
from unittest import mock

import app as app_module
import chat_assistant as ca
import website_chatbot as wb

NOW = datetime.datetime(2026, 11, 13, 15, 0, 0)
TODAY = "2026-11-13 10:00:00"


def L(i, **kw):
    base = {"lead_id": f"LEAD-{i:05d}", "id": f"LEAD-{i:05d}", "company_name": f"Company {i}", "email": "",
            "mobile_number": "", "website": "", "location": "", "source": "Reddit (r/forhire)", "ai_score": "3",
            "first_seen_at": "2026-10-01 10:00:00", "status": "NEW", "description": ""}
    base.update(kw)
    return base


LEADS = [
    L(1, location="Ahmedabad, Gujarat", website="", email="a@one.in", ai_score="8", first_seen_at=TODAY),
    L(2, location="Ahmedabad", website="https://two.in", first_seen_at=TODAY),
    L(3, location="Surat", ai_score="9", first_seen_at="2026-11-10 09:00:00", source="Google Maps"),
    L(4, location="Ahmedabad", website="N/A", mobile_number="+91 98250 12345"),
]
RUNS = [{"run_id": "R1", "start_time": TODAY, "end_time": TODAY, "scraper_name": "reddit_rss_scraper.py (A, B)",
         "status": "Success", "records_collected": "10", "new_leads_added": "3", "existing_leads_updated": "0",
         "duplicates_detected": "7", "error_summary": ""}]
SENT = [{"email": "a@one.in", "sent_at": TODAY, "subject": "Hi"}]


def ctx():
    return {"leads": [dict(l) for l in LEADS], "runs": RUNS, "sent": SENT, "acts": [], "settings": {}, "now": NOW}


class Assistant(unittest.TestCase):
    def ask(self, q):
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
            return ca.answer(q, ctx)

    def test_language_detection(self):
        self.assertEqual(ca._lang("Aaje ketla nava leads?"), "gu")
        self.assertEqual(ca._lang("આજે કેટલા લીડ્સ?"), "gu")
        self.assertEqual(ca._lang("How many leads today?"), "en")

    def test_counts_for_today(self):
        r = self.ask("Aaje ketla nava leads?")
        self.assertIn("2 nava leads", r["reply"])
        self.assertEqual(r["engine"], "rules")
        self.assertIn("2 new leads today", self.ask("How many new leads today?")["reply"])
        self.assertIn("1 mail", self.ask("Aaje ketla mail gaya?")["reply"])

    def test_list_with_filters(self):
        r = self.ask("Ahmedabad na website vagar na leads batavo")
        ids = {row["lead_id"] for row in r["table"]["rows"]}
        self.assertEqual(ids, {"LEAD-00001", "LEAD-00004"})          # N/A counts as no website
        self.assertEqual(self.ask("Leads in Ahmedabad without a website")["table"]["rows"][0]["lead_id"], "LEAD-00001")

    def test_hot_and_scrapers_and_sources(self):
        hot = self.ask("hot leads")
        self.assertEqual({r["lead_id"] for r in hot["table"]["rows"]}, {"LEAD-00001", "LEAD-00003"})
        sc = self.ask("Kayo scraper saro che?")
        self.assertEqual(sc["table"]["rows"][0]["scraper"], "reddit_rss_scraper.py")
        self.assertIn("Reddit", self.ask("kya thi leads aave che")["reply"])

    def test_gujarati_script(self):
        self.assertIn("2 nava leads", self.ask("આજે કેટલા લીડ્સ?")["reply"])

    def test_unknown_without_ai_gives_suggestions(self):
        r = self.ask("what is the weather")
        self.assertTrue(r["suggestions"])

    def test_unknown_with_gemini_uses_only_the_summary(self):
        captured = {}
        def post(url, json=None, headers=None, timeout=None):
            captured["body"] = json
            return mock.Mock(status_code=200, json=lambda: {"candidates": [{"content": {"parts": [{"text": "Two leads today."}]}}]})
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": "k"}):
            r = ca.answer("compare this week with last week please", ctx, gemini_post=post)
        self.assertEqual((r["engine"], r["reply"]), ("gemini", "Two leads today."))
        sent_text = captured["body"]["contents"][0]["parts"][0]["text"]
        self.assertNotIn("a@one.in", sent_text)                       # no lead contact details leave the app

    def test_input_limits(self):
        with self.assertRaises(ValueError):
            ca.answer("", ctx)
        with self.assertRaises(ValueError):
            ca.answer("x" * 600, ctx)


SETTINGS = {"companyName": "Sangeeta Infotech", "services": ["Web apps", "Mobile apps"], "email": "info@sgi.in",
            "phone": "+91 99999 00000", "address": "Ahmedabad, Gujarat, India", "website": "https://sgi.in"}


class WebsiteBot(unittest.TestCase):
    def setUp(self):
        wb.message_limiter.hits.clear()
        wb.lead_limiter.hits.clear()
        self.saved = []
        p = mock.patch.dict(os.environ, {"GEMINI_API_KEY": ""})
        p.start()
        self.addCleanup(p.stop)

    def save(self, lead):
        self.saved.append(dict(lead))
        return "LEAD-T"

    def chat(self, messages, ip="9.9.9.9"):
        st, out = {"lead": {}, "asked": ""}, []
        for msg in messages:
            r = wb.handle({"message": msg, "lead": st["lead"], "asked": st["asked"]}, SETTINGS, ip, self.save)
            st["lead"], st["asked"] = r["lead"], r.get("ask", "")
            out.append(r)
        return out

    def test_full_enquiry_is_saved_with_need_contact_and_name(self):
        out = self.chat(["Hello", "I need an ecommerce website for my clothing shop", "ravi@patelshop.in", "Ravi Patel"])
        self.assertTrue(out[2]["saved"])
        self.assertEqual(out[2]["ask"], "name")
        self.assertEqual(len(self.saved), 2)                               # saved, then the name filled in
        self.assertIn("ecommerce website", self.saved[0]["requirement"])
        self.assertEqual((self.saved[1]["name"], self.saved[1]["email"]), ("Ravi Patel", "ravi@patelshop.in"))

    def test_gujlish_price_question_and_phone(self):
        out = self.chat(["Kem cho, mare app banavvi che, kimat ketli?", "98250 12345"])
        self.assertIn("Kimat", out[0]["reply"])
        self.assertTrue(out[1]["saved"])
        self.assertIn("Aabhar", out[1]["reply"])          # still Gujarati after a reply that is only a number
        self.assertEqual(self.saved[0]["phone"], "98250 12345")

    def test_no_contact_no_save_and_bad_email_rejected(self):
        self.chat(["I need a website for my school"])
        self.assertEqual(self.saved, [])
        out = self.chat(["I need a mobile app", "noreply@acme.com"], ip="8.8.8.8")
        self.assertEqual(self.saved, [])
        self.assertIn("does not look right", out[1]["reply"])

    def test_answers_only_from_the_public_profile(self):
        r = wb.handle({"message": "What services do you provide?"}, SETTINGS, "7.7.7.7", self.save)
        self.assertIn("Web apps", r["reply"])
        r = wb.handle({"message": "where is your office"}, SETTINGS, "7.7.7.7", self.save)
        self.assertIn("Ahmedabad", r["reply"])

    def test_html_is_removed_from_input(self):
        out = self.chat(["I need a <script>alert(1)</script> website for my shop", "a@b-shop.in"], ip="6.6.6.6")
        self.assertNotIn("<script>", self.saved[0]["requirement"])

    def test_honeypot_and_rate_limits(self):
        r = wb.handle({"message": "hi", "hp": "http://spam"}, SETTINGS, "5.5.5.5", self.save)
        self.assertEqual(r["saved"], False)
        for _ in range(wb.MESSAGES_PER_WINDOW):
            wb.handle({"message": "hi"}, SETTINGS, "4.4.4.4", self.save)
        with self.assertRaises(PermissionError):
            wb.handle({"message": "hi"}, SETTINGS, "4.4.4.4", self.save)
        for i in range(wb.LEADS_PER_HOUR + 1):
            wb.handle({"message": f"I need a website for shop number {i}, mail me at x{i}@shop{i}.in"}, SETTINGS, "3.3.3.3", self.save)
        self.assertEqual(len(self.saved), wb.LEADS_PER_HOUR)


class PublicRoutes(unittest.TestCase):
    def setUp(self):
        wb.message_limiter.hits.clear()
        wb.lead_limiter.hits.clear()
        self.tmp = tempfile.mkdtemp(prefix="chatbot_")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.leads = os.path.join(self.tmp, "leads.csv")
        import lead_normalizer as ln
        with open(self.leads, "w", encoding="utf-8-sig", newline="") as fh:
            csv.DictWriter(fh, fieldnames=ln.MASTER_FIELDNAMES).writeheader()
        for p in (mock.patch.object(app_module, "MASTER_PATH", self.leads),
                  mock.patch.object(app_module, "LEADS_CSV", self.leads),
                  mock.patch.object(app_module, "load_settings", return_value=SETTINGS),
                  mock.patch.object(app_module.followup_store, "safe_log", lambda *a, **k: None),
                  mock.patch.object(app_module, "send_smtp_email", return_value={"success": True}),
                  mock.patch.dict(os.environ, {"GEMINI_API_KEY": "", "WIDGET_ALLOWED_ORIGINS": "https://sgi.in"})):
            p.start()
            self.addCleanup(p.stop)
        self.client = app_module.app.test_client()

    def post(self, body, origin="https://sgi.in"):
        return self.client.post("/public/chat", data=json.dumps(body), content_type="application/json",
                                headers={"Origin": origin} if origin else {})

    def test_allowed_site_gets_cors_and_unknown_site_is_refused(self):
        r = self.post({"message": "hello"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers.get("Access-Control-Allow-Origin"), "https://sgi.in")
        bad = self.post({"message": "hello"}, origin="https://evil.example")
        self.assertEqual(bad.status_code, 403)
        self.assertIsNone(bad.headers.get("Access-Control-Allow-Origin"))
        pre = self.client.open("/public/chat", method="OPTIONS", headers={"Origin": "https://sgi.in"})
        self.assertEqual(pre.status_code, 204)

    def test_no_login_needed_but_api_still_locked(self):
        self.assertEqual(self.post({"message": "hello"}).status_code, 200)
        self.assertEqual(self.client.post("/api/chat", json={"message": "hi"}).status_code, 401)

    def test_enquiry_becomes_a_lead_in_the_file(self):
        st = {"lead": {}, "asked": ""}
        for msg in ("I need an ecommerce website for my shop", "ravi@patelshop.in"):
            j = self.post({"message": msg, "lead": st["lead"], "asked": st["asked"]}).get_json()
            st["lead"], st["asked"] = j["lead"], j.get("ask", "")
        with open(self.leads, encoding="utf-8-sig", newline="") as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]["email"], rows[0]["source"]), ("ravi@patelshop.in", "Website Chatbot"))
        self.assertIn("ecommerce website", rows[0]["description"])

    def test_two_nameless_visitors_stay_two_leads(self):
        for email in ("one@shopone.in", "two@shoptwo.in"):
            wb.lead_limiter.hits.clear()
            st = {"lead": {}, "asked": ""}
            for msg in ("I need an ecommerce website for my shop", email):
                j = self.post({"message": msg, "lead": st["lead"], "asked": st["asked"],
                               "page": "https://sgi.in/contact"}).get_json()   # same page for both visitors
                st["lead"], st["asked"] = j["lead"], j.get("ask", "")
        with open(self.leads, encoding="utf-8-sig", newline="") as fh:
            emails = sorted(r["email"] for r in csv.DictReader(fh))
        self.assertEqual(emails, ["one@shopone.in", "two@shoptwo.in"])

    def test_bad_requests(self):
        self.assertEqual(self.post({"message": ""}).status_code, 400)
        self.assertEqual(self.post([1, 2]).status_code, 400)
        big = self.client.post("/public/chat", data="x" * 9000, content_type="application/json",
                               headers={"Origin": "https://sgi.in"})
        self.assertEqual(big.status_code, 413)

    def test_widget_script_and_demo(self):
        js = self.client.get("/widget/chatbot.js")
        self.assertEqual(js.status_code, 200)
        self.assertIn("javascript", js.headers["Content-Type"])
        self.assertIn("/public/chat", js.get_data(as_text=True))
        self.assertEqual(self.client.get("/widget/demo").status_code, 200)   # tests run bound to localhost

    def test_api_chat_answers_with_login(self):
        with mock.patch.object(app_module, "_chat_context", ctx):
            r = self.client.post("/api/chat", json={"message": "Aaje ketla nava leads?"}, headers={"X-Demo-User": "true"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("nava leads", r.get_json()["reply"])


if __name__ == "__main__":
    unittest.main()

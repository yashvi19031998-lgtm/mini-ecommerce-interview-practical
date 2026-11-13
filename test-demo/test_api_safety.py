"""Regression tests for the full-app QA of 2026-11-13 (API input safety, settings, auto scraper status).

python -m unittest test_api_safety -v

No network, no e-mail: the leads file, the settings file and the run log are temporary copies.
"""
import csv
import json
import os
import shutil
import tempfile
import unittest
from unittest import mock

import app as app_module
import search_cache
import settings_manager

AUTH = {"X-Demo-User": "true"}
FIELDS = ["lead_id", "company_name", "email", "status", "email_status", "email_sent_at", "last_updated_at"]


class ApiSafetyBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="api_safety_")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

        self.leads = os.path.join(self.tmp, "leads.csv")
        with open(self.leads, "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=FIELDS)
            w.writeheader()
            w.writerow({"lead_id": "LEAD-00001", "company_name": "Acme Foods", "email": "ravi@acmefoods.in", "status": "NEW"})
            w.writerow({"lead_id": "LEAD-00002", "company_name": "Kappa Traders", "email": "", "status": "NEW"})

        self.settings_file = os.path.join(self.tmp, "company_settings.json")
        with open(self.settings_file, "w", encoding="utf-8") as fh:
            json.dump({"companyName": "Sangeeta Infotech", "senderRole": "Client Solutions Specialist",
                       "services": ["Web", "Mobile"], "signatureTemplate": "Regards,\n{senderName}",
                       "whatsapp": "+91 9426738067", "delayBetweenEmailsMs": 1500}, fh)

        os.makedirs(os.path.join(self.tmp, "logs"))
        patches = [
            mock.patch.object(app_module, "LEADS_CSV", self.leads),
            mock.patch.object(app_module, "MASTER_PATH", self.leads),
            mock.patch.object(app_module, "BASE_DIR", self.tmp),
            mock.patch.object(settings_manager, "SETTINGS_FILE", self.settings_file),
            mock.patch.object(app_module.followup_store, "safe_log", lambda *a, **k: None),
            mock.patch.object(app_module, "send_smtp_email", side_effect=AssertionError("no e-mail in tests")),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        app_module._cached_leads_data.clear()
        self.addCleanup(app_module._cached_leads_data.clear)
        self.client = app_module.app.test_client()

    def statuses(self):
        with open(self.leads, encoding="utf-8-sig", newline="") as fh:
            return {r["lead_id"]: r["status"] for r in csv.DictReader(fh)}


class BadInputTests(ApiSafetyBase):
    WRITE_ROUTES = [
        ("PATCH", "/api/leads/LEAD-00001/status"), ("POST", "/api/leads/send-email"), ("POST", "/api/leads/bulk-email"),
        ("POST", "/api/import/raw-text"), ("POST", "/api/import/commit"), ("POST", "/api/job-portals/search"),
        ("POST", "/api/job-portals/save"), ("POST", "/api/search-engine/search"), ("POST", "/api/maps/search"),
        ("POST", "/api/bulk-contacts/phones"), ("POST", "/api/followups/activities"), ("PUT", "/api/followups/templates"),
        ("POST", "/api/lead-care/cleanup/apply"), ("POST", "/api/lead-care/enrichment/save"), ("POST", "/api/settings"),
    ]

    def test_json_that_is_not_an_object_is_a_clean_400(self):
        for method, path in self.WRITE_ROUTES:
            for body in ("[1, 2, 3]", "null", '"text"', "12", "this is not json"):
                with self.subTest(route=f"{method} {path}", body=body):
                    r = self.client.open(path, method=method, data=body, headers=AUTH, content_type="application/json")
                    self.assertEqual(r.status_code, 400)
                    self.assertTrue(r.is_json, "error must be JSON, not an HTML error page")
                    self.assertFalse(r.get_json()["success"])

    def test_wrong_value_types_never_crash(self):
        junk = {k: {"a": [None, {"b": "<script>alert(1)</script>"}]} for k in
                ("keywords", "keyword", "query", "titles", "state", "portals", "sources", "text", "leads", "jobs",
                 "lead_ids", "changes", "phones", "emails", "status", "to", "subject", "message", "templates")}
        for method, path in self.WRITE_ROUTES:
            if path == "/api/settings":
                continue
            with self.subTest(route=f"{method} {path}"):
                r = self.client.open(path, method=method, json=junk, headers=AUTH)
                self.assertLess(r.status_code, 500, r.get_data(as_text=True)[:200])
                self.assertTrue(r.is_json)

    def test_unknown_api_route_and_wrong_method_answer_in_json(self):
        r = self.client.get("/api/does-not-exist", headers=AUTH)
        self.assertEqual(r.status_code, 404)
        self.assertTrue(r.is_json)
        r = self.client.delete("/api/leads", headers=AUTH)
        self.assertEqual(r.status_code, 405)
        self.assertTrue(r.is_json)

    def test_search_cache_key_accepts_unhashable_items(self):
        key = search_cache.make_key("m", {"titles": [{"a": 1}, {"a": 1}, "React  Dev", "react dev"], 5: "x"})
        self.assertEqual(key, search_cache.make_key("m", {"titles": ["react dev", {"a": 1}], 5: "x"}))


class LeadStatusTests(ApiSafetyBase):
    def test_valid_status_is_saved_in_upper_case(self):
        r = self.client.patch("/api/leads/LEAD-00001/status", json={"status": "contacted"}, headers=AUTH)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.statuses(), {"LEAD-00001": "CONTACTED", "LEAD-00002": "NEW"})

    def test_unknown_status_is_refused_and_nothing_is_written(self):
        for bad in ("<script>alert(1)</script>", "DELETED", 12345, ["WON"]):
            with self.subTest(status=bad):
                r = self.client.patch("/api/leads/LEAD-00001/status", json={"status": bad}, headers=AUTH)
                self.assertEqual(r.status_code, 400)
        self.assertEqual(self.statuses(), {"LEAD-00001": "NEW", "LEAD-00002": "NEW"})

    def test_unknown_lead_is_404_not_a_silent_success(self):
        r = self.client.patch("/api/leads/LEAD-99999/status", json={"status": "WON"}, headers=AUTH)
        self.assertEqual(r.status_code, 404)

    def test_bulk_email_refuses_bad_lists_before_sending(self):
        for body in ({"lead_ids": "LEAD-00001", "subject": "s", "message": "m"},
                     {"lead_ids": ["LEAD-00001"] * (app_module.MAX_BULK_EMAILS + 1), "subject": "s", "message": "m"},
                     {"lead_ids": ["LEAD-00001"], "subject": 5, "message": "m"}):
            r = self.client.post("/api/leads/bulk-email", json=body, headers=AUTH)
            self.assertEqual(r.status_code, 400)  # send_smtp_email is mocked to fail the test if it is reached


class SettingsTests(ApiSafetyBase):
    def saved(self):
        with open(self.settings_file, encoding="utf-8") as fh:
            return json.load(fh)

    def test_save_merges_instead_of_replacing(self):
        r = self.client.post("/api/settings", json={"tagline": "New tagline", "companyName": "Sangeeta Infotech"}, headers=AUTH)
        self.assertEqual(r.status_code, 200)
        saved = self.saved()
        self.assertEqual(saved["tagline"], "New tagline")
        for kept in ("senderRole", "services", "signatureTemplate", "whatsapp", "delayBetweenEmailsMs"):
            self.assertIn(kept, saved, f"{kept} was wiped by a save that did not send it")

    def test_passwords_and_tokens_are_never_written(self):
        self.client.post("/api/settings", headers=AUTH, json={
            "tagline": "x", "smtp_pass": "hunter2", "smtpPassword": "hunter2", "api_key": "k", "accessToken": "t"})
        self.assertNotIn("hunter2", json.dumps(self.saved()))
        self.assertFalse({"smtp_pass", "smtpPassword", "api_key", "accessToken"} & set(self.saved()))

    def test_empty_save_is_refused_and_keeps_the_file(self):
        before = self.saved()
        self.assertEqual(self.client.post("/api/settings", json={}, headers=AUTH).status_code, 400)
        self.assertEqual(self.saved(), before)


class DoNotContactTests(ApiSafetyBase):
    """The Do-Not-Contact list (Settings -> excludedCompanies) - round 2 of the 2026-11-13 QA."""
    RULES = {"excludedCompanies": ["8dots"]}

    def excluded(self, company="", email="", website="", rules=None):
        return settings_manager.is_company_excluded(company, email, website, settings=rules or self.RULES)[0]

    def test_the_excluded_company_is_blocked_however_it_is_written(self):
        for company, email, website in [
                ("8dots", "", ""), ("8Dots Technology LLP", "", ""), ("8-Dots Pvt Ltd", "", ""), ("8 Dots Infotech", "", ""),
                ("", "hr@8dots.in", ""), ("", "x@mail.8dots.co.in", ""), ("", "8dots.hr@gmail.com", ""),
                ("", "", "https://www.8dots.com/contact"), ("", "", "8dotstech.com")]:
            with self.subTest(company=company, email=email, website=website):
                self.assertTrue(self.excluded(company, email, website))

    def test_a_fragment_of_the_rule_never_blocks_another_company(self):
        for company, email in [("Dots", "info@dots.io"), ("S", ""), ("D", "ceo@d.com"), ("8", ""), ("do", ""),
                               ("Eight Dots Studio", ""), ("Acme Corp", "sales@acme.com")]:
            with self.subTest(company=company):
                self.assertFalse(self.excluded(company, email))

    def test_a_short_rule_matches_whole_words_only(self):
        short = {"excludedCompanies": ["IT", "ab"]}
        self.assertFalse(self.excluded("Infinity Digital", "hello@infinity.com", rules=short))
        self.assertFalse(self.excluded("Kappa Traders", "ravi@abhitech.in", "https://kappa-habitat.in", rules=short))
        self.assertTrue(self.excluded("IT Solutions Hub", rules=short))
        self.assertTrue(self.excluded("", "sales@ab.com", rules=short))

    def test_list_may_be_text_or_broken_without_losing_the_default(self):
        self.assertTrue(self.excluded("Rival Agency", rules={"excludedCompanies": "8dots, rival agency"}))
        self.assertTrue(self.excluded("8dots", rules={"excludedCompanies": None}))
        self.assertFalse(self.excluded("Acme", rules={"excludedCompanies": ["", "  ", "--"]}))

    def test_shield_blocks_before_the_mail_login_and_never_touches_the_network(self):
        import email_service
        with mock.patch.object(email_service.smtplib, "SMTP", side_effect=AssertionError("network must not be reached")), \
                mock.patch.dict(os.environ, {"SMTP_USER": "", "SMTP_PASS": ""}):
            res = email_service.send_smtp_email("ravi@gmail.com", "Hi", "Body", company_name="8dots Technology LLP")
            self.assertTrue(res.get("excluded"), res)
        with mock.patch.object(email_service.smtplib, "SMTP", side_effect=AssertionError("network must not be reached")), \
                mock.patch.dict(os.environ, {"SMTP_USER": "me@example.com", "SMTP_PASS": "x"}), \
                mock.patch.object(settings_manager, "is_company_excluded", side_effect=RuntimeError("settings unreadable")):
            res = email_service.send_smtp_email("ravi@acme.com", "Hi", "Body", company_name="Acme")
            self.assertFalse(res["success"])       # the rule could not be checked -> refuse, never send
            self.assertIn("Do-not-contact check failed", res["error"])

    def test_dashboard_sends_pass_the_company_name_to_the_shield(self):
        import email_service
        with open(self.leads, "a", encoding="utf-8-sig", newline="") as fh:
            csv.DictWriter(fh, fieldnames=FIELDS).writerow(
                {"lead_id": "LEAD-00003", "company_name": "8dots Technology LLP", "email": "owner.personal@gmail.com", "status": "NEW"})
        app_module._cached_leads_data.clear()
        with mock.patch.object(app_module, "send_smtp_email", email_service.send_smtp_email), \
                mock.patch.object(email_service.smtplib, "SMTP", side_effect=AssertionError("network must not be reached")), \
                mock.patch.dict(os.environ, {"SMTP_USER": "me@example.com", "SMTP_PASS": "x"}), \
                mock.patch.object(settings_manager, "load_settings", return_value=dict(self.RULES)):
            single = self.client.post("/api/leads/send-email", headers=AUTH, json={
                "id": "LEAD-00003", "to": "owner.personal@gmail.com", "subject": "Hi", "message": "Body"})
            self.assertEqual(single.status_code, 403)
            self.assertTrue(single.get_json()["excluded"])
            bulk = self.client.post("/api/leads/bulk-email", headers=AUTH, json={
                "lead_ids": ["LEAD-00003"], "subject": "Hi {company}", "message": "Body", "delay_ms": 0}).get_json()
            self.assertEqual((bulk["sent"], bulk["failed"]), (0, 1))
            self.assertIn("blacklist", bulk["results"][0]["error"].lower())
        self.assertEqual(self.statuses()["LEAD-00003"], "NEW")   # a blocked send must not mark the lead as e-mailed


class OutreachWordingTests(ApiSafetyBase):
    """A scraped job-post title is never written into an e-mail as the company name (round 3)."""

    def test_names_for_real_companies_and_post_titles(self):
        import followup_sequence as seq
        self.assertEqual(seq.outreach_names("Acme Foods"), ("Acme Foods", "Acme Foods"))
        for title in ("Senior Paid Media Manager - Full Time - Remote (USA only) - $100k+/yr + benefits",
                      "[HIRING] LEAD AEM DEVELOPER CONTRACT", "Urgent Hiring : Senior DevOps", "", None,
                      "your company", "N/A"):
            with self.subTest(title=title):
                self.assertEqual(seq.outreach_names(title), ("there", "your team"))

    def test_bulk_email_text_uses_safe_names(self):
        with open(self.leads, "a", encoding="utf-8-sig", newline="") as fh:
            csv.DictWriter(fh, fieldnames=FIELDS).writerow({
                "lead_id": "LEAD-00004", "company_name": "[Hiring] Senior React dev - Remote (USA only)",
                "email": "jobs@otherco.com", "status": "NEW"})
        app_module._cached_leads_data.clear()
        sent = []
        fake = lambda to, sub, body, bypass_duplicate_check=False, company_name="": sent.append((to, sub, body, company_name)) or {"success": True}
        with mock.patch.object(app_module, "send_smtp_email", side_effect=fake), \
                mock.patch.object(app_module, "load_settings", return_value={}), \
                mock.patch.object(app_module, "format_signature", return_value=""):
            r = self.client.post("/api/leads/bulk-email", headers=AUTH, json={
                "lead_ids": ["LEAD-00001", "LEAD-00004"], "delay_ms": 0,
                "subject": "Tech team for {company}", "message": "Hi {name},\nI came across {company} in {location}."})
        self.assertEqual(r.get_json()["sent"], 2)
        by_to = {s[0]: s for s in sent}
        self.assertEqual(by_to["ravi@acmefoods.in"][1], "Tech team for Acme Foods")
        self.assertIn("Hi Acme Foods,", by_to["ravi@acmefoods.in"][2])
        post = by_to["jobs@otherco.com"]
        self.assertEqual(post[1], "Tech team for your team")
        self.assertIn("Hi there,", post[2])
        self.assertNotIn("Hiring", post[1] + post[2])
        self.assertEqual(post[3], "[Hiring] Senior React dev - Remote (USA only)")  # the shield still gets the real name


class AutoSendSwitchTests(unittest.TestCase):
    def state(self, env, setting):
        environ = {k: v for k, v in os.environ.items() if k != "AUTO_SEND_EMAIL"}
        if env is not None:
            environ["AUTO_SEND_EMAIL"] = env
        with mock.patch.dict(os.environ, environ, clear=True):
            return settings_manager.auto_send_state({"autoSendEmail": setting})[0]

    def test_env_false_is_a_hard_off_switch(self):
        for env in ("false", "0", "no", "off", "False"):
            self.assertFalse(self.state(env, True), f"AUTO_SEND_EMAIL={env} must stop auto e-mail even when Settings says on")

    def test_settings_toggle_decides_when_env_allows(self):
        self.assertTrue(self.state("true", True))
        self.assertFalse(self.state("true", False))
        self.assertTrue(self.state(None, True))
        self.assertFalse(self.state(None, False))
        self.assertTrue(self.state("", True))


class SchedulerStatusTests(ApiSafetyBase):
    HEADER = ["run_id", "start_time", "end_time", "scraper_name", "status", "records_collected", "new_leads_added",
              "existing_leads_updated", "duplicates_detected", "error_summary"]

    def write_runs(self, rows):
        with open(os.path.join(self.tmp, "logs", "scraper_runs.csv"), "w", encoding="utf-8-sig", newline="") as fh:
            csv.writer(fh).writerows([self.HEADER] + rows)

    def test_history_is_read_with_commas_in_names_and_header_skipped(self):
        self.write_runs([
            ["RUN-A", "2026-11-12 10:00:00", "2026-11-12 10:00:05", "scraper.py (Search, Deep)", "Success", "6", "2", "4", "0", ""],
            ["RUN-A", "2026-11-12 10:00:05", "2026-11-12 10:00:09", "feeds.py (WWR, Remotive)", "Failed", "0", "0", "0", "0", "timeout"],
            ["RUN-B", "2026-11-12 11:00:00", "2026-11-12 11:00:04", "scraper.py (Search, Deep)", "Success", "9", "3", "1", "5", ""],
        ])
        with mock.patch.dict(os.environ, {"AUTO_SEND_EMAIL": "false"}):
            data = self.client.get("/api/scheduler/status", headers=AUTH).get_json()
        self.assertEqual(len(data["runs"]), 3)
        self.assertEqual(data["runs"][0]["run_id"], "RUN-B")            # newest first
        self.assertEqual(data["runs"][1]["scraper_name"], "feeds.py (WWR, Remotive)")
        self.assertEqual(data["runs"][1]["error_summary"], "timeout")
        self.assertEqual((data["total_runs"], data["total_scraper_rows"], data["total_added"]), (2, 3, 5))
        self.assertEqual(data["last_run"], "2026-11-12 11:00:00")
        self.assertFalse(data["auto_send_email"])                       # the real switch, not just the Settings toggle
        self.assertIn("AUTO_SEND_EMAIL", data["auto_send_reason"])

    def test_no_log_yet_is_an_empty_history_not_an_error(self):
        data = self.client.get("/api/scheduler/status", headers=AUTH).get_json()
        self.assertTrue(data["success"])
        self.assertEqual((data["runs"], data["total_runs"], data["last_run"]), ([], 0, ""))

    def test_second_trigger_while_running_is_refused(self):
        open(os.path.join(self.tmp, ".scraper_runner.lock"), "w").close()
        with mock.patch.object(app_module.subprocess, "run", side_effect=AssertionError("must not start a run")):
            r = self.client.post("/api/scheduler/trigger", headers=AUTH)
        self.assertEqual(r.status_code, 409)


if __name__ == "__main__":
    unittest.main()

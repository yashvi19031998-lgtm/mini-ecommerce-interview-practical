"""Tests for the lead cleanup / AI qualification pipeline and the API auth guard.

    python -m unittest test_quality_and_auth -v
"""
import csv
import json
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

import lead_normalizer as ln
import lead_quality as lq


class NormalizerFixes(unittest.TestCase):
    def test_platform_url_is_not_company_website(self):
        r = ln.normalize_lead_record({"company_name": "X", "website": "https://www.reddit.com/r/forhire/abc"})
        self.assertEqual(r["website"], "")
        self.assertEqual(r["source_url"], "https://www.reddit.com/r/forhire/abc")

    def test_real_website_kept(self):
        r = ln.normalize_lead_record({"company_name": "X", "website": "https://acme.in/"})
        self.assertEqual(r["website"], "https://acme.in/")

    def test_placeholder_emails_dropped(self):
        r = ln.normalize_lead_record({"company_name": "X", "email": "you@company.com, info@acme.in, name@yourdomain.com"})
        self.assertEqual(r["email"], "info@acme.in")

    def test_status_and_ai_fields_survive(self):
        r = ln.normalize_lead_record({"company_name": "X", "Status": "meeting", "ai_score": "8", "ai_category": "client_project"})
        self.assertEqual(r["status"], "MEETING")
        self.assertEqual(r["ai_score"], "8")
        self.assertEqual(r["ai_category"], "client_project")

    def test_ad_urls_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            reg = ln.MasterLeadRegistry(os.path.join(d, "m.csv"))
            outcome, _ = reg.add_lead({"company_name": "Post a Job - Indeed", "URL": "https://www.bing.com/aclick?ld=abc&u=x"})
            self.assertEqual(outcome, "skipped_invalid")

    def test_status_persists_through_save_and_reload(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "m.csv")
            reg = ln.MasterLeadRegistry(path)
            reg.add_lead({"company_name": "Acme", "email": "info@acme.in"})
            reg.leads[0]["status"] = "WON"
            reg.leads[0]["ai_score"] = "9"
            self.assertTrue(reg.save_master_safely())
            reloaded = ln.MasterLeadRegistry(path)
            self.assertEqual(reloaded.leads[0]["status"], "WON")
            self.assertEqual(reloaded.leads[0]["ai_score"], "9")


class QualityPipeline(unittest.TestCase):
    def test_contact_channel(self):
        self.assertEqual(lq.derive_contact_channel({"email": "a@b.in"}), "email")
        self.assertEqual(lq.derive_contact_channel({"mobile_number": "+91 99999 99999"}), "phone")
        self.assertEqual(lq.derive_contact_channel({"source_url": "https://www.reddit.com/r/x"}), "reddit")
        self.assertEqual(lq.derive_contact_channel({}), "none")

    def test_outreach_ready_requires_buyer_score_and_email(self):
        good = {"ai_category": "client_project", "ai_score": "8", "email": "a@b.in"}
        self.assertTrue(lq.is_outreach_ready(good))
        self.assertFalse(lq.is_outreach_ready({**good, "ai_category": "service_provider"}))
        self.assertFalse(lq.is_outreach_ready({**good, "ai_score": "5"}))
        self.assertFalse(lq.is_outreach_ready({**good, "email": ""}))
        self.assertFalse(lq.is_outreach_ready({"email": "a@b.in"}))  # never qualified -> never emailed

    def _write_master(self, path, rows):
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=ln.MASTER_FIELDNAMES)
            w.writeheader()
            for r in rows:
                w.writerow({k: r.get(k, "") for k in ln.MASTER_FIELDNAMES})

    def test_run_cleans_and_qualifies_with_mocked_claude(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "m.csv")
            self._write_master(path, [
                {"lead_id": "LEAD-00001", "company_name": "Acme", "email": "info@acme.in",
                 "description": "Need a React web app for our clinic", "first_seen_at": "2026-11-01 10:00:00"},
                {"lead_id": "LEAD-00002", "company_name": "Post a Job - Indeed",
                 "source_url": "https://www.bing.com/aclick?ld=x&u=y"},
            ])
            fake_json = json.dumps({"category": "client_project", "score": 9, "summary": "Clinic needs a React app",
                                    "requirement": "React web app", "tech_stack": "React", "budget": "", "reason": "explicit need"})
            fake_resp = SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=fake_json)])
            fake_client = mock.MagicMock()
            fake_client.beta.messages.create.return_value = fake_resp

            with mock.patch.object(lq, "_get_client", return_value=fake_client):
                stats = lq.run(path, limit=10)

            self.assertEqual(stats["removed_ads"], 1)
            self.assertEqual(stats["qualified"], 1)
            self.assertEqual(stats["outreach_ready"], 1)
            kwargs = fake_client.beta.messages.create.call_args.kwargs
            self.assertEqual(kwargs["model"], "claude-opus-5-5")
            self.assertEqual(kwargs["output_config"]["format"]["type"], "json_schema")

            lead = ln.MasterLeadRegistry(path).leads[0]
            self.assertEqual(lead["ai_category"], "client_project")
            self.assertEqual(lead["ai_score"], "9")
            self.assertEqual(lead["contact_channel"], "email")
            self.assertTrue(lead["ai_qualified_at"])

    def test_run_without_api_key_only_cleans(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "m.csv")
            self._write_master(path, [{"lead_id": "LEAD-00001", "company_name": "Acme", "email": "info@acme.in"}])
            with mock.patch.object(lq, "_get_client", return_value=None):
                stats = lq.run(path)
            # When API key is absent, fallback heuristic NLP qualifier runs
            self.assertEqual(stats["qualified"], 1)
            self.assertEqual(stats["outreach_ready"], 0)

    def test_refusal_counts_as_failure(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "m.csv")
            self._write_master(path, [{"lead_id": "LEAD-00001", "company_name": "Acme", "email": "info@acme.in"}])
            fake_client = mock.MagicMock()
            fake_client.beta.messages.create.return_value = SimpleNamespace(stop_reason="refusal", content=[])
            with mock.patch.object(lq, "_get_client", return_value=fake_client), \
                 mock.patch.object(lq, "qualify_one_heuristic", return_value=None):
                stats = lq.run(path)
            self.assertEqual(stats["failed"], 1)
            self.assertEqual(ln.MasterLeadRegistry(path).leads[0]["ai_qualified_at"], "")


class SlackAlerts(unittest.TestCase):
    def _hot(self, **kw):
        base = {"lead_id": "LEAD-00001", "company_name": "Acme <Clinic> & Co", "ai_category": "client_project",
                "ai_score": "8", "ai_summary": "Needs app", "ai_requirement": "React app",
                "source_url": "https://www.reddit.com/r/forhire/abc", "first_seen_at": "2026-11-01"}
        base.update(kw)
        return base

    def test_hot_lead_rules(self):
        import slack_notifier as sn
        self.assertTrue(sn.is_hot_lead(self._hot()))  # no email needed: Reddit leads count
        self.assertFalse(sn.is_hot_lead(self._hot(ai_score="5")))
        self.assertFalse(sn.is_hot_lead(self._hot(ai_category="job_seeker")))

    def test_message_escapes_and_links(self):
        import slack_notifier as sn
        msg = json.dumps(sn.build_message(self._hot()))
        self.assertIn("Acme &lt;Clinic&gt; &amp; Co", msg)
        self.assertIn("<https://www.reddit.com/r/forhire/abc|Reddit post>", msg)

    def test_posts_once_and_marks_lead(self):
        import slack_notifier as sn
        leads = [self._hot(), self._hot(lead_id="LEAD-00002", ai_score="3")]
        ok = SimpleNamespace(status_code=200, text="ok", headers={})
        with mock.patch.object(sn, "SLACK_WEBHOOK_URL", "https://hooks.slack.com/services/T/B/X"),                 mock.patch.object(sn.requests, "post", return_value=ok) as post,                 mock.patch.object(sn.time, "sleep"):
            first = sn.notify_hot_leads(leads)
            second = sn.notify_hot_leads(leads)
        self.assertEqual(first["slack_posted"], 1)
        self.assertEqual(second["slack_posted"], 0)  # already notified -> not posted again
        self.assertEqual(post.call_count, 1)
        self.assertTrue(leads[0]["slack_notified_at"])
        self.assertEqual(leads[1].get("slack_notified_at", ""), "")

    def test_no_webhook_is_noop(self):
        import slack_notifier as sn
        with mock.patch.object(sn, "SLACK_WEBHOOK_URL", ""), mock.patch.object(sn.requests, "post") as post:
            self.assertEqual(sn.notify_hot_leads([self._hot()])["slack_posted"], 0)
        post.assert_not_called()

    def test_failed_post_not_marked(self):
        import slack_notifier as sn
        bad = SimpleNamespace(status_code=404, text="no_service", headers={})
        lead = self._hot()
        with mock.patch.object(sn, "SLACK_WEBHOOK_URL", "https://hooks.slack.com/services/T/B/X"),                 mock.patch.object(sn.requests, "post", return_value=bad):
            stats = sn.notify_hot_leads([lead])
        self.assertEqual(stats["slack_failed"], 1)
        self.assertEqual(lead.get("slack_notified_at", ""), "")


class ApiAuth(unittest.TestCase):
    def setUp(self):
        os.environ.pop("API_AUTH_DISABLED", None)
        import app as app_module
        self.app_module = app_module
        self.client = app_module.app.test_client()

    def test_api_rejects_missing_token(self):
        r = self.client.get("/api/leads")
        self.assertEqual(r.status_code, 401)

    def test_api_rejects_invalid_token(self):
        with mock.patch("api_auth.requests.get", return_value=SimpleNamespace(status_code=401, json=lambda: {})):
            r = self.client.get("/api/leads", headers={"Authorization": "Bearer bad-token"})
        self.assertEqual(r.status_code, 401)

    def test_api_accepts_valid_token(self):
        ok = SimpleNamespace(status_code=200, json=lambda: {"email": "owner@example.com"})
        with mock.patch("api_auth.requests.get", return_value=ok), mock.patch("api_auth.ALLOWED_EMAILS", set()):
            r = self.client.get("/api/leads", headers={"Authorization": "Bearer good-token"})
        self.assertEqual(r.status_code, 200)

    def test_allowlist_blocks_other_accounts(self):
        ok = SimpleNamespace(status_code=200, json=lambda: {"email": "stranger@example.com"})
        with mock.patch("api_auth.requests.get", return_value=ok), \
                mock.patch("api_auth.ALLOWED_EMAILS", {"owner@example.com"}):
            r = self.client.get("/api/leads", headers={"Authorization": "Bearer other-token"})
        self.assertEqual(r.status_code, 401)

    def test_disable_flag_refused_on_public_bind(self):
        import api_auth
        with mock.patch.dict(os.environ, {"API_AUTH_DISABLED": "true"}):
            self.assertFalse(api_auth.auth_disabled("0.0.0.0"))
            self.assertTrue(api_auth.auth_disabled("127.0.0.1"))


if __name__ == "__main__":
    unittest.main()

import unittest
from unittest.mock import patch, MagicMock
import os
import tempfile
import shutil

import settings_manager
import app

class TestAutoSchedulerAndSettings(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.orig_settings_file = settings_manager.SETTINGS_FILE
        settings_manager.SETTINGS_FILE = os.path.join(self.tmp_dir, "test_settings.json")
        self.app = app.app.test_client()
        self.auth_headers = {"X-Demo-User": "true"}

    def tearDown(self):
        settings_manager.SETTINGS_FILE = self.orig_settings_file
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_default_settings_contains_scheduler_and_company_profile(self):
        settings = settings_manager.load_settings()
        self.assertIn("companyDescription", settings)
        self.assertIn("defaultKeywords", settings)
        self.assertIn("defaultCity", settings)
        self.assertIn("defaultState", settings)
        self.assertIn("autoSendEmail", settings)
        self.assertIn("maxPendingEmailsPerRun", settings)
        self.assertIsInstance(settings["defaultKeywords"], list)
        self.assertIn("software company", settings["defaultKeywords"])
        self.assertEqual(settings["defaultCity"], "Ahmedabad")
        self.assertEqual(settings["defaultState"], "Gujarat")

    def test_save_settings_persists_targeting_and_drops_secrets(self):
        data = {
            "companyDescription": "Custom description for testing.",
            "defaultKeywords": ["cloud engineering", "devops"],
            "defaultCity": "Surat",
            "defaultState": "Gujarat",
            "autoSendEmail": False,
            "maxPendingEmailsPerRun": 10,
            "smtp_pass": "super_secret_password",
            "api_key": "secret_token_123"
        }
        saved = settings_manager.save_settings(data)
        self.assertEqual(saved["companyDescription"], "Custom description for testing.")
        self.assertEqual(saved["defaultCity"], "Surat")
        self.assertEqual(saved["defaultKeywords"], ["cloud engineering", "devops"])
        self.assertFalse(saved["autoSendEmail"])
        self.assertEqual(saved["maxPendingEmailsPerRun"], 10)
        self.assertNotIn("smtp_pass", saved)
        self.assertNotIn("api_key", saved)

        # Reload to ensure file persistence
        reloaded = settings_manager.load_settings()
        self.assertEqual(reloaded["companyDescription"], "Custom description for testing.")
        self.assertEqual(reloaded["defaultCity"], "Surat")
        self.assertFalse(reloaded["autoSendEmail"])

    def test_auto_send_state_respects_settings_and_env(self):
        # Settings toggle false
        with patch.dict(os.environ, {"AUTO_SEND_EMAIL": ""}, clear=False):
            enabled, reason = settings_manager.auto_send_state({"autoSendEmail": False})
            self.assertFalse(enabled)
            self.assertIn("turned off in settings", reason.lower())

            enabled_on, reason_on = settings_manager.auto_send_state({"autoSendEmail": True})
            self.assertTrue(enabled_on)

        # Hard env disable overrides settings
        with patch.dict(os.environ, {"AUTO_SEND_EMAIL": "false"}):
            enabled_env, reason_env = settings_manager.auto_send_state({"autoSendEmail": True})
            self.assertFalse(enabled_env)
            self.assertIn("environment", reason_env.lower())

    def test_format_signature_includes_company_description(self):
        settings = {
            "senderName": "Alice Smith",
            "senderRole": "Head of Engineering",
            "companyName": "Tech Corp",
            "tagline": "Building the future",
            "email": "alice@techcorp.com",
            "phone": "+91 9876543210",
            "whatsapp": "+91 9876543210",
            "website": "https://techcorp.com",
            "address": "Ahmedabad",
            "companyDescription": "Tech Corp is a modern tech consulting firm.",
            "signatureTemplate": "Best,\n{senderName} - {companyName}\n{companyDescription}\n{email}"
        }
        sig = settings_manager.format_signature(settings)
        self.assertIn("Alice Smith - Tech Corp", sig)
        self.assertIn("Tech Corp is a modern tech consulting firm.", sig)
        self.assertIn("alice@techcorp.com", sig)

    def test_api_scheduler_status_endpoint(self):
        response = self.app.get("/api/scheduler/status", headers=self.auth_headers)
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data.get("success"))
        self.assertIn("is_running", data)
        self.assertIn("cron", data)
        self.assertEqual(data.get("cron"), "23 * * * *")
        self.assertIn("default_keywords", data)
        self.assertIn("default_city", data)
        self.assertIn("runs", data)

    @patch("threading.Thread")
    def test_api_scheduler_trigger_endpoint_starts_job(self, mock_thread):
        mock_instance = MagicMock()
        mock_thread.return_value = mock_instance

        # Ensure lock is free
        app._scheduler_running = False

        response = self.app.post("/api/scheduler/trigger", headers=self.auth_headers)
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data.get("success"))
        self.assertIn("triggered successfully", data.get("message", "").lower())
        self.assertTrue(mock_instance.start.called)

        # Trigger again while running should reject with 409
        app._scheduler_running = True
        try:
            conflict_response = self.app.post("/api/scheduler/trigger", headers=self.auth_headers)
            self.assertEqual(conflict_response.status_code, 409)
            conflict_data = conflict_response.get_json()
            self.assertFalse(conflict_data.get("success"))
            self.assertIn("already executing", conflict_data.get("error", "").lower())
        finally:
            app._scheduler_running = False

    def test_excluded_companies_blocks_8dots_and_custom_companies(self):
        # 1. Check default settings contain 8dots
        settings = settings_manager.load_settings()
        self.assertIn("excludedCompanies", settings)
        self.assertIn("8dots", settings["excludedCompanies"])

        # 2. Check is_company_excluded matches exact and substring
        is_ex, reason = settings_manager.is_company_excluded(company_name="8dots")
        self.assertTrue(is_ex)
        self.assertIn("8dots", reason)

        is_ex_sub, reason_sub = settings_manager.is_company_excluded(company_name="8dots Technology LLP")
        self.assertTrue(is_ex_sub)

        is_ex_mail, reason_mail = settings_manager.is_company_excluded(email="contact@8dots.com")
        self.assertTrue(is_ex_mail)

        is_ex_web, reason_web = settings_manager.is_company_excluded(website="https://www.8dots.in")
        self.assertTrue(is_ex_web)

        # 3. Unrelated company should NOT be excluded
        is_ok, _ = settings_manager.is_company_excluded(company_name="Acme Corp", email="sales@acme.com", website="acme.com")
        self.assertFalse(is_ok)

        # 4. Multiple excluded companies can be saved and respected
        settings_manager.save_settings({"excludedCompanies": ["8dots", "competitor x", "rival agency"]})
        self.assertTrue(settings_manager.is_company_excluded(company_name="Competitor X")[0])
        self.assertTrue(settings_manager.is_company_excluded(company_name="Rival Agency Private Limited")[0])

    def test_email_service_send_smtp_blocks_excluded_company(self):
        import email_service
        # Must block without attempting any network connection
        res = email_service.send_smtp_email(to_email="test@8dots.com", subject="Hello", message_body="Test body", company_name="8dots")
        self.assertFalse(res.get("success"))
        self.assertTrue(res.get("excluded"))
        self.assertIn("blacklist", res.get("error", "").lower())


if __name__ == "__main__":
    unittest.main()

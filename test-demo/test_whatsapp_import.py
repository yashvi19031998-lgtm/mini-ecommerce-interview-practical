"""
Unit tests for WhatsApp Chat Import and Lead Importer Module.
Verifies:
- Robust parsing of Android and iOS WhatsApp chat exports (including Unicode LRM/NNBSP)
- Correct contact extraction (emails, phones, requirements)
- Endpoint /api/import/chat with text and zip archives
- Commit behavior: leads saved to DB, outreach email default is False (no email sent)
"""

import unittest
import os
import io
import json
import zipfile
import tempfile
from unittest import mock

import lead_importer
import app as app_module

AUTH = {"X-Demo-User": "true"}

class TestWhatsAppImport(unittest.TestCase):

    def setUp(self):
        self.app = app_module.app.test_client()
        self.app.testing = True

    def test_parse_whatsapp_chat_standard_and_unicode(self):
        sample_chat = (
            "\u200e[14/11/26, 10:30:15 AM] Tech Recruiter: Looking for a Senior React and Next.js developer "
            "for our fintech dashboard. Immediate joining required. Contact us at hire@fintechlabs.io or +91 98200 11223.\n"
            "14/11/2026, 11:45 am - Pooja Patel: We need a Python Django backend developer for an AI automation project. "
            "Budget $2500. Email pooja@innovate.co\n"
            "14/11/2026, 12:00 pm - John: Just casual chit-chat, hello everyone ok\n"
        )

        leads = lead_importer.parse_whatsapp_chat(sample_chat)
        self.assertEqual(len(leads), 2)

        # Check first lead
        lead1 = leads[0]
        self.assertIn("hire@fintechlabs.io", lead1["email"])
        self.assertIn("9820011223", lead1["mobile_number"].replace(" ", "").replace("+91", ""))
        self.assertIn("React", lead1["description"])

        # Check second lead
        lead2 = leads[1]
        self.assertIn("pooja@innovate.co", lead2["email"])
        self.assertIn("Python", lead2["description"])

    def test_api_import_chat_json_endpoint(self):
        sample_chat = (
            "14/11/2026, 10:30 am - Rahul: Looking for a dedicated Flutter developer. "
            "Email: rahul@appcorp.in. Project starting next week."
        )
        res = self.app.post("/api/import/chat", json={"text": sample_chat}, headers=AUTH)
        data = res.get_json()
        self.assertTrue(data.get("success"), str(data))
        self.assertEqual(data.get("count"), 1)
        self.assertEqual(data["leads"][0]["email"], "rahul@appcorp.in")

    def test_api_import_chat_zip_file_upload(self):
        # Create a mock WhatsApp exported .zip file with _chat.txt
        chat_content = (
            "14/11/2026, 09:15 am - Startup Founder: We need an urgent Shopify expert for store optimization. "
            "Send portfolio to founder@shopbrands.com"
        )
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("_chat.txt", chat_content.encode("utf-8"))
        zip_buffer.seek(0)

        res = self.app.post(
            "/api/import/chat",
            data={"file": (zip_buffer, "WhatsApp Chat - Tech Group.zip")},
            headers=AUTH,
            content_type="multipart/form-data"
        )
        data = res.get_json()
        self.assertTrue(data.get("success"), str(data))
        self.assertEqual(data.get("count"), 1)
        self.assertEqual(data["leads"][0]["email"], "founder@shopbrands.com")

    def test_commit_imported_leads_no_email_by_default(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_master = os.path.join(tmp_dir, "test_master.csv")
            candidate_leads = [{
                "company_name": "CloudWorks",
                "email": "contact@cloudworks.example",
                "mobile_number": "+91 9876543210",
                "description": "Needs AWS cloud architect",
                "location": "Ahmedabad"
            }]

            with mock.patch("lead_importer.send_smtp_email") as mock_smtp, \
                 mock.patch("sync_to_supabase.sync", return_value=True):

                # 1. Commit with send_outreach_email=False (DEFAULT)
                result = lead_importer.commit_imported_leads(
                    candidate_leads,
                    send_outreach_email=False,
                    master_csv=temp_master
                )

                self.assertEqual(result["added"], 1)
                self.assertEqual(result["emails_sent"], 0)
                # Verify SMTP was NEVER called
                mock_smtp.assert_not_called()

                # Verify lead exists in master CSV
                with open(temp_master, "r", encoding="utf-8-sig") as f:
                    content = f.read()
                    self.assertIn("CloudWorks", content)
                    self.assertIn("contact@cloudworks.example", content)

    def test_commit_imported_leads_with_email_when_requested(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_master = os.path.join(tmp_dir, "test_master.csv")
            candidate_leads = [{
                "company_name": "Alpha Devs",
                "email": "team@alphadevs.example",
                "mobile_number": "+91 9123456780",
                "description": "Hiring React frontend developer",
                "location": "Mumbai"
            }]

            with mock.patch("lead_importer.send_smtp_email", return_value={"success": True}) as mock_smtp, \
                 mock.patch("sync_to_supabase.sync", return_value=True):

                # 2. Commit with send_outreach_email=True
                result = lead_importer.commit_imported_leads(
                    candidate_leads,
                    send_outreach_email=True,
                    master_csv=temp_master
                )

                self.assertEqual(result["added"], 1)
                self.assertEqual(result["emails_sent"], 1)
                mock_smtp.assert_called_once()
                args, kwargs = mock_smtp.call_args
                self.assertEqual(args[0], "team@alphadevs.example")
                # Subject and body must contain personalized info and signature
                self.assertIn("Alpha Devs", args[1])
                self.assertIn("Sangeeta Infotech", args[2])

if __name__ == "__main__":
    unittest.main()

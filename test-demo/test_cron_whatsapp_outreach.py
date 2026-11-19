"""Unit tests for cron_job_whatsapp_outreach.py"""

import unittest
from cron_job_whatsapp_outreach import (
    normalize_whatsapp_number,
    format_whatsapp_message,
    select_pending_whatsapp_leads
)


class TestCronWhatsAppOutreach(unittest.TestCase):

    def test_normalize_whatsapp_number_indian_10_digits(self):
        self.assertEqual(normalize_whatsapp_number("9876543210"), "919876543210")
        self.assertEqual(normalize_whatsapp_number("+91 98765 43210"), "919876543210")
        self.assertEqual(normalize_whatsapp_number("09876543210"), "919876543210")

    def test_normalize_whatsapp_number_international(self):
        # US number (11 digits starting with 1)
        self.assertEqual(normalize_whatsapp_number("+1 415 555 2671"), "14155552671")
        # Invalid / short number
        self.assertIsNone(normalize_whatsapp_number("12345"))
        self.assertIsNone(normalize_whatsapp_number(""))

    def test_format_whatsapp_message_content(self):
        lead = {"company_name": "Acme Tech"}
        msg = format_whatsapp_message(lead)
        self.assertIn("Acme Tech", msg)
        self.assertIn("Sangeeta Infotech", msg)
        self.assertIn("₹450/- INR / hour", msg)
        self.assertIn("5+ years of experience", msg)
        self.assertIn("80+ clients", msg)
        self.assertIn("7-day risk-free trial", msg)
        self.assertIn("+91 9106060400", msg)

    def test_select_pending_whatsapp_leads(self):
        leads = select_pending_whatsapp_leads(max_batch=3)
        self.assertTrue(len(leads) <= 3)
        for l in leads:
            self.assertIsNotNone(l.get("phone"))
            self.assertNotEqual(l.get("phone"), "")


if __name__ == "__main__":
    unittest.main()

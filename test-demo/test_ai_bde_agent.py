"""Unit tests for Autonomous AI BDE Agent (ai_bde_agent.py)"""

import unittest
from app import app
from ai_bde_agent import (
    get_daily_bde_briefing,
    generate_lead_pitch,
    handle_inbound_negotiation,
    qualify_lead,
    is_excluded_company
)


class TestAIBDEAgent(unittest.TestCase):

    def setUp(self):
        self.client = app.test_client()

    def test_excluded_company_check(self):
        self.assertTrue(is_excluded_company("8dots Technology"))
        self.assertTrue(is_excluded_company("8dots"))
        self.assertFalse(is_excluded_company("Acme Corp"))

    def test_get_daily_bde_briefing_structure(self):
        briefing = get_daily_bde_briefing()
        self.assertIn("report_date", briefing)
        self.assertIn("pipeline_metrics", briefing)
        self.assertIn("service_breakdown", briefing)
        self.assertIn("top_hot_leads", briefing)
        self.assertIn("bde_action_plan", briefing)

    def test_generate_lead_pitch_maintenance(self):
        lead = {
            "company_name": "FastFashion Store",
            "description": "Website is slow and Core Web Vitals are failing. Looking for speed fixes and AMC.",
            "email": "ops@fastfashion.com"
        }
        pitch = generate_lead_pitch(lead)
        self.assertTrue(pitch["is_valid"])
        self.assertEqual(pitch["service_category"], "Website Maintenance & Speed Optimization")
        self.assertIn("₹450/- INR / hour", pitch["hourly_rate"])
        self.assertIn("7-Day Risk-Free Trial", pitch["trial_offer"])
        self.assertIn("FastFashion Store", pitch["email_pitch"]["body"])
        self.assertIn("Sangeeta Infotech", pitch["email_pitch"]["body"])

    def test_generate_lead_pitch_crm(self):
        lead = {
            "company_name": "Apex Logistics",
            "description": "Need custom CRM portal and automated Salesforce database sync.",
            "email": "lead@apexlogistics.com"
        }
        pitch = generate_lead_pitch(lead)
        self.assertTrue(pitch["is_valid"])
        self.assertEqual(pitch["service_category"], "Custom CRM & ERP Portals")
        self.assertIn("₹450/- INR / hour", pitch["email_pitch"]["body"])

    def test_generate_lead_pitch_excluded_shield(self):
        lead = {
            "company_name": "8dots Technology LLP",
            "description": "Looking for developers"
        }
        pitch = generate_lead_pitch(lead)
        self.assertFalse(pitch.get("is_valid", True))
        self.assertIn("excluded", pitch.get("error", "").lower())

    def test_handle_inbound_negotiation(self):
        res = handle_inbound_negotiation(
            client_message="What are your rates and do you have a trial period?",
            company_name="CloudNine",
            contact_name="James"
        )
        self.assertEqual(res["detected_intent"], "pricing_trial")
        self.assertIn("₹450/- INR / hour", res["suggested_response"]["body"])
        self.assertIn("7-Day Risk-Free Trial", res["suggested_response"]["body"])
        self.assertEqual(len(res["standard_retainers"]), 2)

    def test_qualify_lead(self):
        hot_lead = {
            "company_name": "Fintech Global",
            "email": "cto@fintech.com",
            "mobile_number": "919876543210",
            "website": "https://fintech.com",
            "description": "Urgent requirement: Need Laravel and Next.js developers team immediately."
        }
        qual = qualify_lead(hot_lead)
        self.assertEqual(qual["grade"], "HOT")
        self.assertTrue(qual["bde_score"] >= 8)

    def test_api_bde_briefing_endpoint(self):
        resp = self.client.get("/api/bde/briefing", headers={"X-Demo-User": "1"})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("pipeline_metrics", data)

    def test_api_bde_pitch_endpoint(self):
        payload = {
            "lead": {
                "company_name": "Beta Test Corp",
                "description": "Need React and Python full-stack developers for MVP"
            }
        }
        resp = self.client.post("/api/bde/pitch", json=payload, headers={"X-Demo-User": "1"})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data.get("is_valid"))
        self.assertIn("Beta Test Corp", data.get("email_pitch", {}).get("body", ""))

    def test_api_bde_negotiate_endpoint(self):
        payload = {
            "client_message": "Can you work in US EST timezone?",
            "company_name": "US Client Inc"
        }
        resp = self.client.post("/api/bde/negotiate", json=payload, headers={"X-Demo-User": "1"})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data.get("detected_intent"), "timezone")
        self.assertIn("US EST", data.get("suggested_response", {}).get("body", ""))

    def test_api_bde_qualify_endpoint(self):
        payload = {
            "company_name": "Enterprise Portal Ltd",
            "email": "contact@enterprise.com",
            "description": "Looking for web development partner"
        }
        resp = self.client.post("/api/bde/qualify", json=payload, headers={"X-Demo-User": "1"})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("bde_score", data)


if __name__ == "__main__":
    unittest.main()

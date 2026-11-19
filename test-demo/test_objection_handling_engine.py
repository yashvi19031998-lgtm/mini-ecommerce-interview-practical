"""Unit tests for objection_handling_engine.py"""

import unittest
from objection_handling_engine import (
    classify_objection,
    get_objection_response,
    MONTHLY_RETAINER_PACKAGES
)


class TestObjectionHandlingEngine(unittest.TestCase):

    def test_classify_objection_categories(self):
        self.assertEqual(classify_objection("Can you share your portfolio and live work samples?"), "portfolio")
        self.assertEqual(classify_objection("Are you an agency or a team of freelancers? Where is your office?"), "agency_model")
        self.assertEqual(classify_objection("Can you work in US EST timezone overlap?"), "timezone")
        self.assertEqual(classify_objection("How does the pricing and trial work?"), "pricing_trial")
        self.assertEqual(classify_objection("We are happy with our current developers."), "happy_with_current")
        self.assertEqual(classify_objection("unsubscribe"), "opt_out")
        self.assertEqual(classify_objection("stop"), "opt_out")

    def test_portfolio_response_content(self):
        subj, body = get_objection_response("portfolio", "Alex", "TechCorp", "mobile app development")
        self.assertIn("TechCorp", subj)
        self.assertIn("TechCorp", body)
        self.assertIn("Sangeeta Infotech", body)
        self.assertIn("mobile app development", body)

    def test_pricing_trial_response_content(self):
        subj, body = get_objection_response("pricing_trial", "Sarah", "GrowthLab", "Laravel CRM")
        self.assertIn("₹450/- INR / hour", body)
        self.assertIn("Part-Time Dedicated (80 hrs/month)", body)
        self.assertIn("Full-Time Dedicated (160 hrs/month)", body)
        self.assertIn("7-Day Risk-Free Trial", body)

    def test_happy_with_current_response(self):
        subj, body = get_objection_response("happy_with_current", "David", "SaaSWorks")
        self.assertIn("parallel capacity pod", body)
        self.assertIn("₹450/- INR / hour", body)

    def test_retainer_packages_data(self):
        self.assertEqual(len(MONTHLY_RETAINER_PACKAGES), 2)
        pt = MONTHLY_RETAINER_PACKAGES[0]
        self.assertEqual(pt["hours_per_month"], 80)
        self.assertEqual(pt["price_inr"], 36000)

        ft = MONTHLY_RETAINER_PACKAGES[1]
        self.assertEqual(ft["hours_per_month"], 160)
        self.assertEqual(ft["price_inr"], 72000)


if __name__ == "__main__":
    unittest.main()

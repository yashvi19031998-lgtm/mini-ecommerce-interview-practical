"""
Unit tests for AI Email Generator (ai_email_generator.py).
Verifies:
- Smart company and role extraction from noisy/scraped titles
- Tech stack and intent detection (React, Node, Python, Mobile, Ecommerce)
- High-conversion context-tailored email synthesis
- 100% guaranteed signature presence across all generated emails
"""

import unittest
from ai_email_generator import (
    clean_company_and_role,
    detect_tech_and_intent,
    synthesize_tailored_email,
    generate_personalized_email,
    format_signature,
    DEFAULT_SIGNATURE
)

class TestAiEmailGenerator(unittest.TestCase):

    def test_clean_company_and_role_patterns(self):
        # 1. Job post pattern: Role at Company
        comp, role = clean_company_and_role("Senior React Developer at Lemon.io")
        self.assertEqual(comp, "Lemon.io")
        self.assertEqual(role, "Senior React Developer")

        # 2. @ separator pattern
        comp, role = clean_company_and_role("Python Backend Engineer @ Scale AI Inc.")
        self.assertEqual(comp, "Scale AI")
        self.assertEqual(role, "Python Backend Engineer")

        # 3. Dash separator pattern
        comp, role = clean_company_and_role("Mobile App Developer - FinTech Labs LLC")
        self.assertEqual(comp, "FinTech Labs")
        self.assertEqual(role, "Mobile App Developer")

        # 4. Clean corporate legal suffixes
        comp, role = clean_company_and_role("AKSHAR SOFTWARE LLP")
        self.assertEqual(comp, "Akshar Software")

        comp, role = clean_company_and_role("Nexus Cloud Solutions Pvt Ltd")
        self.assertEqual(comp, "Nexus Cloud Solutions")

    def test_detect_tech_and_intent(self):
        # Lead with React & Next.js hiring need
        lead_react = {
            'Company Name': 'Frontend Guild',
            'ai_requirement': 'Looking for Senior Next.js and React developers to build dashboard',
            'ai_tech_stack': 'React, Next.js, TypeScript'
        }
        res = detect_tech_and_intent(lead_react)
        self.assertTrue(res['is_hiring'])
        self.assertIn('React / Next.js', res['tech_stack'])

        # Lead with Python & FastAPI
        lead_python = {
            'Company Name': 'DataCorp',
            'Notes': 'Needs Python backend developer experienced with FastAPI and PostgreSQL'
        }
        res_py = detect_tech_and_intent(lead_python)
        self.assertIn('Python', res_py['tech_stack'])

        # Lead with Shopify / Ecommerce
        lead_ecom = {
            'Company Name': 'Fashion Hub',
            'Description': 'Shopify ecommerce store looking for performance optimization',
            'lead_type': 'ecommerce'
        }
        res_ecom = detect_tech_and_intent(lead_ecom)
        self.assertTrue(res_ecom['is_ecommerce'])
        self.assertIn('E-Commerce (Shopify/WooCommerce)', res_ecom['tech_stack'])

        # Lead with Flutter / Mobile
        lead_mobile = {
            'Company Name': 'Appify',
            'Job Title': 'Senior Flutter iOS Android Developer'
        }
        res_mob = detect_tech_and_intent(lead_mobile)
        self.assertIn('Mobile Apps (Flutter/React Native)', res_mob['tech_stack'])

    def test_synthesize_tailored_email(self):
        lead = {
            'Company Name': 'Senior React Engineer at FinTech OS',
            'Address': 'Ahmedabad',
            'ai_requirement': 'React and TypeScript front-end engineer'
        }
        comp, role = clean_company_and_role(lead['Company Name'])
        intent_info = detect_tech_and_intent(lead)
        subject, body = synthesize_tailored_email(comp, role, intent_info, 'Ahmedabad', {})
        self.assertEqual(comp, 'FinTech OS')
        self.assertEqual(role, 'Senior React Engineer')
        self.assertIn('FinTech OS', subject)
        self.assertIn('React', body)
        self.assertIn('Sangeeta Infotech', body)

    def test_guaranteed_signature_presence(self):
        lead = {
            'Company Name': 'Alpha Technologies',
            'Email': 'contact@alphatech.example',
            'Address': 'Surat, Gujarat'
        }
        settings = {
            'company_name': 'Sangeeta Infotech',
            'contact_email': 'contact@sangeetainfotech.com',
            'phone': '+91 9106060400',
            'website': 'https://sangeetainfotech.com'
        }

        draft = generate_personalized_email(lead, settings)
        body = draft["body"]
        subject = draft["subject"]

        # Ensure complete signature is present
        self.assertIn('Warm regards,', body)
        self.assertIn('Sangeeta Infotech', body)
        self.assertIn('+91 9106060400', body)
        self.assertIn('https://sangeetainfotech.com', body)
        self.assertIn('Alpha', subject)

    def test_custom_signature_honored(self):
        lead = {'Company Name': 'Beta Corp', 'Email': 'hr@betacorp.example'}
        settings = {
            'signature': 'Cheers,\nExecutive Team @ Sangeeta\nDirect: +91 9999999999\nhttps://sangeetainfotech.com'
        }
        draft = generate_personalized_email(lead, settings)
        body = draft["body"]
        self.assertIn('Cheers,', body)
        self.assertIn('+91 9999999999', body)

    def test_clean_greeting_no_job_title_in_name(self):
        # When company name is "React Developer at Acme Corp", greeting must not be "Hi React Developer at Acme Corp"
        lead = {'Company Name': 'React Developer at Acme Corp'}
        comp, role = clean_company_and_role(lead['Company Name'])
        self.assertEqual(comp, 'Acme')
        draft = generate_personalized_email(lead)
        body = draft["body"]
        self.assertNotIn('Hi React Developer', body)
        self.assertIn('Acme', body)

if __name__ == '__main__':
    unittest.main()

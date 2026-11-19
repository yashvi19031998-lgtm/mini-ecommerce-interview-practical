"""Unit tests for email_pattern_discovery.py"""

import unittest
from email_pattern_discovery import (
    clean_domain,
    generate_email_patterns,
    extract_emails_from_html,
    domain_has_mail
)


class TestEmailPatternDiscovery(unittest.TestCase):

    def test_clean_domain(self):
        self.assertEqual(clean_domain("https://www.example.com/contact?ref=1"), "www.example.com")
        self.assertEqual(clean_domain("http://sangeetainfotech.co.in/"), "sangeetainfotech.co.in")
        self.assertEqual(clean_domain("ACME.ORG/team"), "acme.org")

    def test_generate_email_patterns(self):
        patterns = generate_email_patterns("John", "Doe", "acme.com")
        self.assertIn("john.doe@acme.com", patterns)
        self.assertIn("john@acme.com", patterns)
        self.assertIn("jdoe@acme.com", patterns)
        self.assertIn("j.doe@acme.com", patterns)
        self.assertTrue(len(patterns) >= 5)

    def test_extract_emails_from_html(self):
        sample_html = """
        <html>
            <body>
                <p>Contact founder at <a href="mailto:founder@acme.com">founder@acme.com</a></p>
                <p>Support: support@acme.com</p>
                <p>Third-party plugin: plugin@wordpress.org</p>
            </body>
        </html>
        """
        extracted = extract_emails_from_html(sample_html, "acme.com")
        self.assertIn("founder@acme.com", extracted)
        self.assertIn("support@acme.com", extracted)
        # External domain email should be filtered out
        self.assertNotIn("plugin@wordpress.org", extracted)

    def test_domain_has_mail_mocked(self):
        from unittest.mock import patch, MagicMock
        mock_proc = MagicMock()
        mock_proc.stdout = "Non-authoritative answer:\ngoogle.com mail exchanger = 10 aspmx.l.google.com.\n"
        with patch("subprocess.run", return_value=mock_proc):
            mx_records = domain_has_mail("google.com")
            self.assertTrue(len(mx_records) > 0)
            self.assertEqual(mx_records[0], "aspmx.l.google.com")


if __name__ == "__main__":
    unittest.main()

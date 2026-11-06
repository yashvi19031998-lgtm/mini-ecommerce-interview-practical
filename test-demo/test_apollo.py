"""
Unit Tests for Apollo.io Lead Enrichment & Harvester
====================================================
Verifies domain sanitization, cache management, fallback behavior,
and lead data enrichment flow.
"""

import os
import json
import tempfile
import unittest
from unittest.mock import patch, MagicMock

import apollo_enricher


class TestApolloEnricher(unittest.TestCase):

    def test_extract_clean_domain(self):
        """Test URL to domain extraction and blacklisting."""
        self.assertEqual(apollo_enricher.extract_clean_domain("https://www.acme-corp.com/about/contact"), "acme-corp.com")
        self.assertEqual(apollo_enricher.extract_clean_domain("http://techstart.io/"), "techstart.io")
        self.assertEqual(apollo_enricher.extract_clean_domain("subdomain.company.co.in"), "subdomain.company.co.in")
        
        # Ignored aggregators & social domains
        self.assertIsNone(apollo_enricher.extract_clean_domain("https://www.google.com/search?q=test"))
        self.assertIsNone(apollo_enricher.extract_clean_domain("https://reddit.com/r/forhire"))
        self.assertIsNone(apollo_enricher.extract_clean_domain("https://t.me/freelance"))
        self.assertIsNone(apollo_enricher.extract_clean_domain("invalid_url"))
        self.assertIsNone(apollo_enricher.extract_clean_domain(None))
        self.assertIsNone(apollo_enricher.extract_clean_domain(""))

    def test_cache_mechanism(self):
        """Test local domain caching saves credits."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_cache_path = os.path.join(tmpdir, "test_apollo_cache.json")
            with patch("apollo_enricher.APOLLO_CACHE_FILE", test_cache_path):
                # Initially empty
                cache = apollo_enricher._load_cache()
                self.assertEqual(cache, {})

                # Save an entry
                sample_entry = {
                    "found": True,
                    "data": {
                        "full_name": "Sarah Connor",
                        "email": "sarah@cyberdyne.com",
                        "title": "CTO"
                    }
                }
                cache["cyberdyne.com"] = sample_entry
                apollo_enricher._save_cache(cache)

                # Re-read
                reloaded = apollo_enricher._load_cache()
                self.assertIn("cyberdyne.com", reloaded)
                self.assertEqual(reloaded["cyberdyne.com"]["data"]["full_name"], "Sarah Connor")

    @patch("apollo_enricher.requests.post")
    def test_fetch_decision_maker_success(self, mock_post):
        """Test parsing successful Apollo mixed_people/search response."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "people": [
                {
                    "name": "Jane Doe",
                    "title": "Founder & CEO",
                    "email": "jane@apexsystems.com",
                    "phone_numbers": [{"raw_number": "+1 415 555 2671"}],
                    "linkedin_url": "https://linkedin.com/in/janedoe",
                    "organization": {"name": "Apex Systems"}
                }
            ]
        }
        mock_post.return_value = mock_resp

        with tempfile.TemporaryDirectory() as tmpdir:
            test_cache_path = os.path.join(tmpdir, "test_cache.json")
            with patch("apollo_enricher.APOLLO_CACHE_FILE", test_cache_path):
                result = apollo_enricher.fetch_decision_maker_by_domain(
                    domain="apexsystems.com",
                    company_name="Apex Systems",
                    api_key="mock_api_key_123"
                )

                self.assertIsNotNone(result)
                self.assertEqual(result["full_name"], "Jane Doe")
                self.assertEqual(result["title"], "Founder & CEO")
                self.assertEqual(result["email"], "jane@apexsystems.com")
                self.assertEqual(result["mobile_number"], "+1 415 555 2671")
                self.assertEqual(result["linkedin_url"], "https://linkedin.com/in/janedoe")

    def test_no_api_key_graceful_exit(self):
        """Verifies function returns None/0 without crashing when API key is missing."""
        with patch("apollo_enricher.APOLLO_API_KEY", ""):
            contact = apollo_enricher.fetch_decision_maker_by_domain("acme.com", api_key="")
            self.assertIsNone(contact)

            prospects = apollo_enricher.search_apollo_prospects(api_key="")
            self.assertEqual(prospects, [])


if __name__ == "__main__":
    unittest.main()

import unittest
from unittest import mock
import competitor_client_harvester as cch
import scraper_adapters


class TestCompetitorClientHarvester(unittest.TestCase):
    def test_clean_competitor_slug(self):
        self.assertEqual(cch._clean_competitor_slug("Hyperlink InfoSystem"), "hyperlinkinfosystem.com")
        self.assertEqual(cch._clean_competitor_slug("Radixweb"), "radixweb.com")

    def test_extract_domain(self):
        self.assertEqual(cch._extract_domain("https://www.example.com/portfolio"), "example.com")
        self.assertEqual(cch._extract_domain("http://clientapp.in/contact"), "clientapp.in")

    def test_is_client_url_filtering(self):
        # Excludes directories & platforms
        self.assertFalse(cch._is_client_url("https://www.linkedin.com/in/john", "Radixweb"))
        self.assertFalse(cch._is_client_url("https://clutch.co/profile/radixweb", "Radixweb"))
        # Excludes competitor's own domain
        self.assertFalse(cch._is_client_url("https://www.radixweb.com/case-studies", "Radixweb"))
        # Excludes 8dots blacklist
        self.assertFalse(cch._is_client_url("https://www.8dots.com", "Radixweb"))
        # Valid real client website passes
        self.assertTrue(cch._is_client_url("https://www.acmelogistics.com/home", "Radixweb"))

    def test_harvest_with_mocked_search(self):
        fake_hits = [
            {
                "url": "https://www.acmelogistics.com/about",
                "title": "Acme Logistics - Global Freight Solutions",
                "body": "Contact our office at info@acmelogistics.com or +91 9876543210. Designed & Developed by Radixweb."
            }
        ]
        with mock.patch.object(cch, "SEARCH_WEB_FUNC", return_value=fake_hits):
            leads = cch.harvest_competitor_clients(competitors=["Radixweb"], max_results_per_competitor=2)

        self.assertGreaterEqual(len(leads), 1)
        first = leads[0]
        self.assertEqual(first["company_name"], "Acme Logistics")
        self.assertEqual(first["website"], "https://acmelogistics.com")
        self.assertEqual(first["source"], "Competitor Client (Radixweb)")
        self.assertEqual(first["lead_type"], "Competitor Paying Client")
        self.assertEqual(first["intent_score"], "9")
        self.assertIn("info@acmelogistics.com", first["email"])

    def test_adapter_runs_cleanly(self):
        with mock.patch("competitor_client_harvester.harvest_competitor_clients", return_value=[{"company_name": "Test Client"}]):
            res = scraper_adapters.run_competitor_client_adapter()
            self.assertEqual(len(res), 1)
            self.assertEqual(res[0]["company_name"], "Test Client")


if __name__ == "__main__":
    unittest.main()

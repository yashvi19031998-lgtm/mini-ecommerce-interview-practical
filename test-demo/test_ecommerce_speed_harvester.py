"""Unit tests for ecommerce_speed_harvester.py"""

import unittest
from ecommerce_speed_harvester import (
    is_valid_store_url,
    score_store,
    check_store_speed
)


class TestEcommerceSpeedHarvester(unittest.TestCase):

    def test_is_valid_store_url(self):
        self.assertTrue(is_valid_store_url("https://fashionstore.myshopify.com"))
        self.assertTrue(is_valid_store_url("https://organicgrocerystore.com"))
        # Excluded platforms
        self.assertFalse(is_valid_store_url("https://community.shopify.com/t5/forums"))
        self.assertFalse(is_valid_store_url("https://reddit.com/r/shopify"))
        # Excluded 8dots blacklist
        self.assertFalse(is_valid_store_url("https://8dots.com"))

    def test_score_store_high_urgency(self):
        slow_metrics = {
            "performance_score": 0.25,
            "lcp_seconds": 5.2,
            "cls": 0.32,
            "tbt_ms": 750,
            "opportunities": [
                "Reduce initial server response time",
                "Eliminate render-blocking resources",
                "Properly size images"
            ]
        }
        score = score_store(slow_metrics)
        # Should be high intent (> 70)
        self.assertTrue(score >= 70)

    def test_score_store_fast_site(self):
        fast_metrics = {
            "performance_score": 0.92,
            "lcp_seconds": 1.2,
            "cls": 0.02,
            "tbt_ms": 50,
            "opportunities": []
        }
        score = score_store(fast_metrics)
        self.assertTrue(score <= 15)

    def test_check_store_speed_fallback(self):
        # Fallback probe should return expected dictionary keys
        result = check_store_speed("https://example.com")
        self.assertIn("performance_score", result)
        self.assertIn("lcp_seconds", result)
        self.assertIn("opportunities", result)


if __name__ == "__main__":
    unittest.main()

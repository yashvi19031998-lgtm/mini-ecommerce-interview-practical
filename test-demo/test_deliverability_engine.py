"""Unit tests for deliverability_engine.py"""

import unittest
from deliverability_engine import (
    check_spam_triggers,
    has_opt_out_mechanism,
    has_physical_address,
    validate_email_deliverability,
    calculate_safe_delay,
    PermanentSuppressionStore
)


class TestDeliverabilityEngine(unittest.TestCase):

    def test_spam_trigger_detection(self):
        spammy_text = "Get 100% FREE software today! ACT NOW for best price!!!"
        triggers = check_spam_triggers(spammy_text)
        self.assertTrue(len(triggers) >= 2)

    def test_opt_out_mechanism(self):
        text_with_optout = "If not interested, reply 'no' to opt out."
        self.assertTrue(has_opt_out_mechanism(text_with_optout))

        text_without = "Looking forward to your swift response."
        self.assertFalse(has_opt_out_mechanism(text_without))

    def test_physical_address(self):
        text_with_address = "Sangeeta Infotech, Ahmedabad, Gujarat, India"
        self.assertTrue(has_physical_address(text_with_address))

        text_without = "Thanks and regards."
        self.assertFalse(has_physical_address(text_without))

    def test_validate_email_deliverability_clean(self):
        subject = "Software engineering help for Acme Corp"
        body = (
            "Hi John,\n\n"
            "I noticed Acme Corp's web platform.\n\n"
            "At Sangeeta Infotech, our engineering team brings 5+ years of experience building software for 80+ clients. "
            "Our dedicated developers start from ₹450/- INR / hour.\n\n"
            "Would a quick 10-minute chat be useful? If not, just reply 'no' to opt out.\n\n"
            "Best,\nSangeeta Infotech, Ahmedabad, Gujarat, India"
        )
        res = validate_email_deliverability(subject, body, is_first_contact=True)
        self.assertTrue(res.is_valid)
        self.assertTrue(res.score >= 80)
        self.assertEqual(len(res.warnings), 0)

    def test_validate_email_deliverability_flagged(self):
        # Misleading Re: prefix and spammy trigger words
        subject = "Re: 100% FREE software deal ACT NOW!!!"
        body = "CLICK HERE for guaranteed profits!"
        res = validate_email_deliverability(subject, body, is_first_contact=True)
        self.assertFalse(res.is_valid)
        self.assertTrue(res.score < 50)
        self.assertTrue(len(res.warnings) >= 3)

    def test_calculate_safe_delay(self):
        delay = calculate_safe_delay("stable")
        self.assertTrue(90 <= delay <= 240)

    def test_permanent_suppression_store(self, tmp_path=None):
        import tempfile
        import os
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tf:
            temp_file = tf.name

        try:
            store = PermanentSuppressionStore(suppression_file=temp_file)
            store.add("bounced@bademail.com", reason="hard_bounce")
            store.add("spammer.com", reason="domain_block")

            self.assertTrue(store.is_suppressed("bounced@bademail.com"))
            self.assertTrue(store.is_suppressed("someone@spammer.com"))
            self.assertFalse(store.is_suppressed("valid@goodclient.com"))
        finally:
            if os.path.exists(temp_file):
                os.remove(temp_file)


if __name__ == "__main__":
    unittest.main()

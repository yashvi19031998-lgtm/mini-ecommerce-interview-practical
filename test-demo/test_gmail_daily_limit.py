"""The daily Gmail limit is a hard 50: it can be lowered, never raised or switched off."""
import unittest


class GmailDailyLimit(unittest.TestCase):
    def test_hard_limit(self):
        import run_all_scrapers as r
        f = r.daily_mail_limit
        self.assertEqual(f(None, None), 50)
        self.assertEqual(f(None, "500"), 50)   # never above 50
        self.assertEqual(f(0, None), 50)       # 0 / "unlimited" in the settings still means 50
        self.assertEqual(f("", ""), 50)
        self.assertEqual(f(None, "abc"), 50)
        self.assertEqual(f(None, "20"), 20)    # lower is allowed
        self.assertEqual(f(30, "10"), 30)      # the setting wins over the variable
        self.assertLessEqual(r.MAX_EMAILS_PER_DAY, 50)
        self.assertLessEqual(r.MAX_PROSPECT_EMAILS_PER_DAY, r.MAX_EMAILS_PER_DAY)

    def test_bulk_and_status_use_it(self):
        import app
        c = app.app.test_client()
        c.environ_base["HTTP_X_DEMO_USER"] = "true"
        self.assertLessEqual(app._daily_mail_limit(), 50)
        self.assertGreater(app._daily_mail_limit(), 0)


if __name__ == "__main__":
    unittest.main()

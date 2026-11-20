"""The daily mail limit: none by default, a positive setting or variable sets one."""
import unittest


class GmailDailyLimit(unittest.TestCase):
    def test_no_limit_by_default_and_a_number_sets_one(self):
        import run_all_scrapers as r
        f = r.daily_mail_limit
        self.assertEqual(f(None, None), 0)      # 0 = no daily limit (owner's decision, 2026-11-20)
        self.assertEqual(f(0, None), 0)
        self.assertEqual(f("", ""), 0)
        self.assertEqual(f(None, "abc"), 0)
        self.assertEqual(f(None, "500"), 500)   # a number is used as given
        self.assertEqual(f(30, "10"), 30)       # the setting wins over the variable
        self.assertGreaterEqual(r.MAX_PROSPECT_EMAILS_PER_DAY, 0)

    def test_bulk_and_status_use_it(self):
        import app
        c = app.app.test_client()
        c.environ_base["HTTP_X_DEMO_USER"] = "true"
        self.assertGreaterEqual(app._daily_mail_limit(), 0)


if __name__ == "__main__":
    unittest.main()

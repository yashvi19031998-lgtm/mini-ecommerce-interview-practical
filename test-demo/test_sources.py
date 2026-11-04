"""Tests for the new lead sources and advanced features (no network).

    python -m unittest test_sources -v
"""
import datetime
import os
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest import mock

import email_checks
import feedly_scraper as fs
import freelancer_api_scraper as fl
import hn_hiring_scraper as hn
import intent_feeds
import lead_normalizer as ln
import lead_quality as lq
import slack_notifier as sn
import source_report

NOW_RFC = datetime.datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0000")


class IntentFeeds(unittest.TestCase):
    def test_funding_group_keeps_funding_news_only(self):
        rss = f"""<rss><channel><title>Inc42</title>
        <item><title>HealthTech startup Medify raises $3 Mn seed round</title><description>x</description>
        <link>https://inc42.com/a</link><pubDate>{NOW_RFC}</pubDate></item>
        <item><title>Government announces new policy</title><description>y</description>
        <link>https://inc42.com/b</link><pubDate>{NOW_RFC}</pubDate></item></channel></rss>"""
        group = next(g for g in intent_feeds.FEED_GROUPS if g["name"] == "Startup funding news")
        opts = {k: group[k] for k in ("include", "exclude", "max_age_days", "source_prefix", "lead_type")}
        leads = fs.parse_feed_xml(rss, "https://inc42.com/feed/", **opts)
        self.assertEqual([l["source_url"] for l in leads], ["https://inc42.com/a"])
        self.assertEqual(leads[0]["lead_type"], "Funding News")
        self.assertEqual(leads[0]["source"], "Funding news (Inc42)")

    def test_reddit_group_skips_for_hire(self):
        group = intent_feeds.FEED_GROUPS[0]
        self.assertTrue(fs.is_lead_like("Looking for a developer to build my MVP", "", group["include"], group["exclude"]))
        self.assertFalse(fs.is_lead_like("[For Hire] developer available", "looking for a developer", group["include"], group["exclude"]))

    def test_429_is_retried(self):
        limited = SimpleNamespace(status_code=429, headers={"Retry-After": "1"}, text="", raise_for_status=lambda: None)
        ok = SimpleNamespace(status_code=200, headers={}, text="<rss/>", raise_for_status=lambda: None)
        with mock.patch.object(fs.requests, "get", side_effect=[limited, ok]) as get, mock.patch.object(fs.time, "sleep"):
            self.assertEqual(fs.fetch_feed_text("https://www.reddit.com/search.rss?q=x"), "<rss/>")
        self.assertEqual(get.call_count, 2)


class HackerNews(unittest.TestCase):
    THREAD = {"id": "500", "title": "Ask HN: Who is hiring? (November 2026)", "kind": "hiring"}

    def _hit(self, text, parent="500", oid="501"):
        return {"objectID": oid, "parent_id": int(parent), "comment_text": text, "author": "acme_cto",
                "created_at": "2026-11-02T16:00:00Z"}

    def test_keeps_only_contract_friendly_top_level_posts(self):
        contract = self._hit("Acme | Senior React dev | REMOTE | Contract<p>Email jobs@acme.io")
        fulltime = self._hit("Bigco | SRE | Onsite NYC | Full-time only", oid="502")
        self.assertTrue(hn.is_relevant(contract, "hiring"))
        self.assertFalse(hn.is_relevant(fulltime, "hiring"))
        with mock.patch.object(hn.requests, "get") as get:
            get.return_value = SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"hits": [
                contract, fulltime, self._hit("reply about contract", parent="501", oid="503")]})
            top = hn.fetch_top_level_comments("500")
        self.assertEqual([h["objectID"] for h in top], ["501", "502"])  # reply dropped

    def test_comment_to_lead(self):
        lead = hn.comment_to_lead(self._hit("Acme | Senior React dev | REMOTE | Contract<p>Email jobs@acme.io"), self.THREAD)
        self.assertEqual(lead["company_name"], "Acme")
        self.assertEqual(lead["email"], "jobs@acme.io")
        self.assertEqual(lead["source_url"], "https://news.ycombinator.com/item?id=501")
        self.assertEqual(lead["location"], "Remote")
        self.assertEqual(ln.normalize_datetime(lead["posted_at"])[:10], "2026-11-02")

    def test_freelancer_thread_needs_seeking_freelancer(self):
        self.assertTrue(hn.is_relevant(self._hit("SEEKING FREELANCER | Flutter app"), "freelancer"))
        self.assertFalse(hn.is_relevant(self._hit("SEEKING WORK | React dev"), "freelancer"))


class Freelancer(unittest.TestCase):
    def _project(self, **kw):
        p = {"id": 1, "title": "Build a Flutter delivery app", "seo_url": "mobile-app/flutter-delivery",
             "type": "fixed", "budget": {"minimum": 750, "maximum": 1500}, "description": "Need iOS+Android",
             "currency": {"code": "USD", "exchange_rate": 1.0}, "bid_stats": {"bid_count": 12},
             "time_submitted": int(time.time()) - 3600,
             "jobs": [{"name": "Flutter", "category": {"name": "Websites, IT & Software"}},
                      {"name": "Firebase", "category": {"name": "Websites, IT & Software"}}],
             "location": {"country": {"name": "Australia"}}}
        p.update(kw)
        return p

    def test_budget_conversion_and_filters(self):
        self.assertEqual(fl.budget_usd(self._project()), 1500)
        inr = self._project(budget={"minimum": 12500, "maximum": 37500}, currency={"code": "INR", "exchange_rate": 0.012})
        self.assertAlmostEqual(fl.budget_usd(inr), 450)
        self.assertTrue(fl.is_worthwhile(self._project()))
        self.assertFalse(fl.is_worthwhile(self._project(budget={"minimum": 10, "maximum": 30})))   # too small
        self.assertFalse(fl.is_worthwhile(self._project(bid_stats={"bid_count": 200})))           # too crowded
        self.assertFalse(fl.is_worthwhile(self._project(time_submitted=int(time.time()) - 10 * 86400)))  # old
        self.assertTrue(fl.is_worthwhile(self._project(type="hourly", budget={"minimum": 15, "maximum": 30})))

    def test_non_software_projects_skipped(self):
        it = {"category": {"name": "Websites, IT & Software"}}
        translation = {"category": {"name": "Translation & Languages"}}
        marketing = {"category": {"name": "Sales & Marketing"}}
        self.assertFalse(fl.is_worthwhile(self._project(jobs=[{"name": "Spanish", **translation}, {"name": "Translation", **translation}])))
        self.assertFalse(fl.is_worthwhile(self._project(jobs=[{"name": "SEO", **marketing}, {"name": "Marketing", **marketing},
                                                              {"name": "Website Optimization", **it}])))  # 1 of 3 software
        self.assertTrue(fl.is_worthwhile(self._project(jobs=[{"name": "WordPress", **it}])))
        self.assertFalse(fl.is_worthwhile(self._project(jobs=[])))

    def test_project_to_lead(self):
        lead = fl.project_to_lead(self._project())
        self.assertEqual(lead["source_url"], "https://www.freelancer.com/projects/mobile-app/flutter-delivery")
        self.assertIn("Budget: 750-1500 USD", lead["description"])
        self.assertIn("Flutter, Firebase", lead["description"])
        self.assertEqual(lead["location"], "Australia")


class PlatformDedupe(unittest.TestCase):
    def test_posts_on_same_platform_stay_separate_leads(self):
        """Regression: platform URLs used to be treated as company websites and merged by domain."""
        with tempfile.TemporaryDirectory() as d:
            reg = ln.MasterLeadRegistry(os.path.join(d, "m.csv"))
            a = reg.add_lead(fl.project_to_lead(Freelancer()._project()))
            b = reg.add_lead(fl.project_to_lead(Freelancer()._project(id=2, title="Laravel CRM", seo_url="php/laravel-crm")))
            c = reg.add_lead({"company_name": "Acme", "source_url": "https://news.ycombinator.com/item?id=1"})
            e = reg.add_lead({"company_name": "Beta", "source_url": "https://news.ycombinator.com/item?id=2"})
            self.assertEqual([x[0] for x in (a, b, c, e)], ["added"] * 4)
            self.assertEqual(reg.leads[0]["website"], "")


class EmailChecks(unittest.TestCase):
    def setUp(self):
        email_checks.domain_accepts_mail.cache_clear()

    def test_mx_present(self):
        mx = [SimpleNamespace(exchange="mx1.acme.in.")]
        with mock.patch.object(email_checks.dns.resolver, "resolve", return_value=mx):
            self.assertTrue(email_checks.can_receive_mail("info@acme.in"))

    def test_domain_missing(self):
        with mock.patch.object(email_checks.dns.resolver, "resolve", side_effect=email_checks.dns.resolver.NXDOMAIN):
            self.assertFalse(email_checks.can_receive_mail("info@no-such-domain-xyz.in"))

    def test_null_mx_rejected(self):
        with mock.patch.object(email_checks.dns.resolver, "resolve", return_value=[SimpleNamespace(exchange=".")]):
            self.assertFalse(email_checks.can_receive_mail("info@nomail.in"))

    def test_dns_timeout_does_not_block(self):
        with mock.patch.object(email_checks.dns.resolver, "resolve", side_effect=email_checks.dns.exception.Timeout):
            self.assertTrue(email_checks.can_receive_mail("info@slow.in"))

    def test_malformed_address(self):
        self.assertFalse(email_checks.can_receive_mail("not-an-email"))


class AdvancedScoring(unittest.TestCase):
    def test_seen_in_multiple_sources_shown_to_ai(self):
        text = lq._lead_text({"company_name": "Acme", "source": "Reddit (r/startups) | Hacker News (Nov) | Reddit (r/startups)"})
        self.assertIn("Seen in: 2 sources", text)
        self.assertNotIn("Seen in", lq._lead_text({"company_name": "Acme", "source": "Reddit"}))

    def test_prospect_signal_alerts_but_never_emails(self):
        lead = {"ai_category": "prospect_signal", "ai_score": "8", "email": "ceo@startup.in",
                "posted_at": (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")}
        self.assertTrue(sn.is_hot_lead(lead))
        self.assertFalse(lq.is_outreach_ready(lead))
        self.assertIn("prospect_signal", lq.AI_CATEGORIES)

    def test_contact_channels(self):
        self.assertEqual(lq.derive_contact_channel({"source_url": "https://www.freelancer.com/projects/x"}), "freelancer_bid")
        self.assertEqual(lq.derive_contact_channel({"source_url": "https://news.ycombinator.com/item?id=1"}), "hackernews")
        msg = sn._contact_line({"source_url": "https://www.freelancer.com/projects/x"})
        self.assertIn("Bid on Freelancer.com", msg)


class SourceReport(unittest.TestCase):
    def test_report_rates(self):
        leads = [
            {"source": "Reddit (r/forhire)", "email": "a@b.in", "ai_qualified_at": "x", "ai_category": "client_project", "ai_score": "8", "status": "WON"},
            {"source": "Reddit (r/startups) | Feedly", "ai_qualified_at": "x", "ai_category": "irrelevant", "ai_score": "1"},
            {"source": "DuckDuckGo Dork", "ai_qualified_at": "x", "ai_category": "irrelevant", "ai_score": "0"},
            {"source": "DuckDuckGo Dork"},
        ]
        rows = {r["source"]: r for r in source_report.build_report(leads)}
        self.assertEqual(rows["Reddit"]["leads"], 2)
        self.assertEqual(rows["Reddit"]["hot"], 1)
        self.assertEqual(rows["Reddit"]["hot_rate_pct"], 50)
        self.assertEqual(rows["Reddit"]["won"], 1)
        self.assertEqual(rows["DuckDuckGo Dork"]["hot_rate_pct"], 0)
        self.assertEqual(rows["DuckDuckGo Dork"]["ai_scored"], 1)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "logs", "sq.csv")
            source_report.write_report(leads, path)
            self.assertTrue(os.path.exists(path))


if __name__ == "__main__":
    unittest.main()

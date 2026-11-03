"""Tests for feedly_scraper.py (no network).   python -m unittest test_feedly -v"""
import datetime
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

import feedly_scraper as fs
import lead_normalizer as ln

NOW = datetime.datetime.now()
RFC822 = NOW.strftime("%a, %d %b %Y %H:%M:%S +0530")
OLD_ISO = (NOW - datetime.timedelta(days=60)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
NEW_ISO = NOW.astimezone().isoformat()

RSS = f"""<?xml version="1.0"?><rss version="2.0"><channel><title>Startup Board</title>
<item><title>Looking for a developer to build our clinic booking app</title>
<description>&lt;p&gt;Budget $3k. Email ceo@clinicapp.in&lt;/p&gt;</description>
<link>https://board.example/p/1</link><pubDate>{RFC822}</pubDate></item>
<item><title>10 tips for productivity</title><description>blog post</description>
<link>https://board.example/p/2</link><pubDate>{RFC822}</pubDate></item>
<item><title>[FOR HIRE] React developer available</title><description>hire me</description>
<link>https://board.example/p/3</link><pubDate>{RFC822}</pubDate></item>
</channel></rss>"""

ATOM = f"""<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><title>r/forhire</title>
<entry><title>[Hiring] Need a website for my bakery</title><content type="html">Need a website, DM me</content>
<link href="https://www.reddit.com/r/forhire/comments/abc"/><updated>{NEW_ISO}</updated></entry>
<entry><title>[Hiring] old post need developer</title><content>old</content>
<link href="https://www.reddit.com/r/forhire/comments/old"/><updated>{OLD_ISO}</updated></entry>
</feed>"""


class FeedParsing(unittest.TestCase):
    def test_rss_keeps_only_buyer_posts_and_extracts_email(self):
        leads = fs.parse_feed_xml(RSS)
        self.assertEqual(len(leads), 1)
        lead = leads[0]
        self.assertIn("clinic booking app", lead["company_name"])
        self.assertEqual(lead["email"], "ceo@clinicapp.in")
        self.assertEqual(lead["source"], "Feedly (Startup Board)")
        self.assertNotIn("<p>", lead["description"])

    def test_atom_filters_old_posts(self):
        leads = fs.parse_feed_xml(ATOM)
        self.assertEqual([l["source_url"] for l in leads], ["https://www.reddit.com/r/forhire/comments/abc"])

    def test_opml(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "f.opml")
            with open(p, "w", encoding="utf-8") as f:
                f.write('<opml version="1.0"><body><outline text="Jobs">'
                        '<outline type="rss" text="A" xmlUrl="https://a.example/rss"/>'
                        '<outline type="rss" text="B" xmlUrl="https://b.example/feed"/></outline></body></opml>')
            self.assertEqual(fs.read_opml(p), ["https://a.example/rss", "https://b.example/feed"])
            self.assertEqual(fs.read_opml(os.path.join(d, "missing.opml")), [])

    def test_feed_lead_flows_into_registry(self):
        with tempfile.TemporaryDirectory() as d:
            reg = ln.MasterLeadRegistry(os.path.join(d, "m.csv"))
            outcome, lead = reg.add_lead(fs.parse_feed_xml(ATOM)[0], default_source="feedly")
            self.assertEqual(outcome, "added")
            self.assertEqual(lead["website"], "")  # reddit link is not a company website
            self.assertEqual(lead["source_url"], "https://www.reddit.com/r/forhire/comments/abc")


class FeedlyApi(unittest.TestCase):
    def test_api_mode_paginates_and_filters(self):
        ms = int(NOW.timestamp() * 1000)
        page1 = {"items": [
            {"title": "Need a developer for SaaS MVP", "summary": {"content": "contact founder@saas.io"},
             "alternate": [{"href": "https://site.example/a"}], "published": ms, "origin": {"title": "Startups"}},
            {"title": "Market news", "summary": {"content": "nothing"}, "published": ms},
        ], "continuation": "c1"}
        page2 = {"items": [{"title": "Hiring Flutter dev", "canonicalUrl": "https://site.example/b", "published": ms}]}
        responses = [SimpleNamespace(status_code=200, json=lambda p=p: p, raise_for_status=lambda: None, headers={})
                     for p in (page1, page2)]
        with mock.patch.object(fs.requests, "get", side_effect=responses) as get:
            leads = fs.fetch_feedly_stream("feed/https://site.example/rss", token="tok")
        self.assertEqual([l["source_url"] for l in leads], ["https://site.example/a", "https://site.example/b"])
        self.assertEqual(leads[0]["email"], "founder@saas.io")
        first_call = get.call_args_list[0]
        self.assertEqual(first_call.kwargs["headers"]["Authorization"], "Bearer tok")
        self.assertEqual(get.call_args_list[1].kwargs["params"]["continuation"], "c1")

    def test_expired_token_message(self):
        with mock.patch.object(fs.requests, "get", return_value=SimpleNamespace(status_code=401, headers={})):
            with self.assertRaises(RuntimeError) as ctx:
                fs.fetch_feedly_stream("feed/x", token="old")
        self.assertIn("401", str(ctx.exception))

    def test_unconfigured_returns_empty(self):
        with mock.patch.object(fs, "FEEDLY_ACCESS_TOKEN", ""), mock.patch.object(fs, "FEEDLY_FEEDS", []), \
                mock.patch.object(fs, "FEEDLY_OPML_FILE", "does-not-exist.opml"):
            self.assertEqual(fs.run_feedly_adapter(), [])


if __name__ == "__main__":
    unittest.main()

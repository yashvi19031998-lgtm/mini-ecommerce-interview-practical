"""Tests for Domain Tools (domain_tools.py), no network (RDAP, DNS and the daily list are faked).

python -m unittest test_domain_tools -v
"""
import base64
import csv
import datetime
import io
import json
import os
import tempfile
import unittest
import zipfile
from types import SimpleNamespace
from unittest import mock

import dns.resolver

import domain_tools as dt
import html_cache_manager as hcm

BOOT = {"services": [[["com", "net"], ["https://rdap.verisign.com/com/v1/"]], [["in"], ["https://rdap.nixiregistry.in/rdap/"]]]}
RDAP = {
    "acme.com": {"events": [{"eventAction": "registration", "eventDate": "2018-10-23T07:05:29Z"},
                            {"eventAction": "expiration", "eventDate": "2026-12-01T07:05:29Z"}],
                 "entities": [{"roles": ["registrar"], "vcardArray": ["vcard", [["version", {}, "text", "4.0"], ["fn", {}, "text", "Tucows"]]]},
                              {"roles": ["registrant"], "vcardArray": ["vcard", [["fn", {}, "text", "PRIVATE PERSON"]]]}],
                 "nameservers": [{"ldhName": "JOAN.NS.CLOUDFLARE.COM"}], "status": ["client transfer prohibited"]},
    "newco.in": {"events": [{"eventAction": "registration", "eventDate": "2026-09-01T00:00:00Z"},
                            {"eventAction": "expiration", "eventDate": "2027-09-01T00:00:00Z"}],
                 "entities": [], "nameservers": [{"ldhName": "ns1.domaincontrol.com"}], "status": ["active"]},
}
TODAY = datetime.date(2026, 11, 12)


def fake_get_json(url, timeout=15):
    if url == dt.BOOTSTRAP_URL:
        return 200, BOOT
    name = url.rsplit("/", 1)[-1]
    if name in RDAP:
        return 200, RDAP[name]
    if name == "limited.com":
        return 429, None
    return 404, None


class Rdap(unittest.TestCase):
    def setUp(self):
        dt._boot.update(at=0.0, map={})
        self.p = mock.patch.object(dt, "_get_json", side_effect=fake_get_json)
        self.p.start()

    def tearDown(self):
        self.p.stop()
        dt._boot.update(at=0.0, map={})

    def test_input_cleaning(self):
        good, bad = dt.domain_list(["https://www.Acme.com/about", "ravi@newco.in", "shop.acme.co.in", "acme.com", "not a domain"])
        self.assertEqual(good, ["acme.com", "newco.in", "acme.co.in"])
        self.assertEqual(bad, ["not a domain"])
        with self.assertRaises(ValueError):
            dt.domain_list(["x"] * 1)
        with self.assertRaises(ValueError):
            dt.domain_list([f"d{i}.com" for i in range(51)])

    def test_age_report(self):
        with mock.patch.object(dt, "dns_exists", return_value=True):
            res = dt.age_report(["acme.com", "newco.in", "free-name.com", "limited.com", "example.co"], today=TODAY)
        r = {x["domain"]: x for x in res["results"]}
        a = r["acme.com"]
        self.assertEqual((a["created"], a["expires"], a["registrar"], a["dns_host"], a["days_left"]),
                         ("2018-10-23", "2026-12-01", "Tucows", "Cloudflare", 19))
        self.assertIn("Expires in 19 days", a["flags"])
        self.assertNotIn("PRIVATE PERSON", json.dumps(res))               # registrant data never read
        self.assertIn("New (under 1 year)", r["newco.in"]["flags"])
        self.assertEqual(r["newco.in"]["dns_host"], "GoDaddy")
        self.assertEqual(r["free-name.com"]["flags"], ["Not registered"])
        self.assertIn("rate limit", r["limited.com"]["note"])
        self.assertEqual((r["example.co"]["source"], r["example.co"]["registered"]), ("dns", True))   # no RDAP for .co

    def test_availability(self):
        with mock.patch.object(dt, "dns_exists", return_value=False):
            res = dt.availability({"name": "Acme", "tlds": ["com", "in", "co"], "variants": True})
        got = {r["domain"]: r["available"] for r in res["results"]}
        self.assertEqual((got["acme.com"], got["acme.in"], got["acme.co"]), ("taken", "available", "available"))
        self.assertTrue(res["results"][0]["requested"])
        self.assertIn("getacme.com", got)
        self.assertLessEqual(res["checked"], dt.MAX_AVAIL_CHECKS)
        for bad in ({"name": "x"}, {"name": "ok name", "tlds": ["zz"]}, {"name": "<script>"}):
            with self.assertRaises(ValueError):
                dt.availability(bad)

    def test_variants(self):
        v = dt.name_variants("Acme Bakes", ["com"], True)
        self.assertEqual(v[:2], ["acmebakes.com", "acme-bakes.com"])
        self.assertEqual(dt.name_variants("Acme", ["com", "in"], False), ["acme.com", "acme.in"])


class FakeResolver:
    def __init__(self, zones, flaky=()):
        self.zones, self.flaky, self.lifetime, self.calls = zones, set(flaky), 0, []

    def resolve(self, name, rtype):
        self.calls.append((name, rtype))
        if (name, rtype) in self.flaky:
            self.flaky.discard((name, rtype))
            raise dns.resolver.LifetimeTimeout(timeout=4, errors=[])
        if name.endswith("missing.com"):
            raise dns.resolver.NXDOMAIN()
        ans = self.zones.get((name, rtype))
        if ans is None:
            raise dns.resolver.NoAnswer()
        return ans


def mx(*hosts):
    return [SimpleNamespace(preference=i, exchange=h) for i, h in enumerate(hosts)]


def txt(*values):
    return [SimpleNamespace(strings=[v.encode()]) for v in values]


ZONES = {
    ("good.in", "MX"): mx("aspmx.l.google.com."), ("good.in", "TXT"): txt("v=spf1 include:_spf.google.com -all"),
    ("_dmarc.good.in", "TXT"): txt("v=DMARC1; p=reject"), ("good.in", "NS"): ["joan.ns.cloudflare.com."], ("good.in", "A"): ["1.2.3.4"],
    ("weak.in", "MX"): mx("smtp.secureserver.net."), ("weak.in", "TXT"): txt("google-site-verification=x"),
    ("weak.in", "NS"): ["ns1.domaincontrol.com."], ("weak.in", "A"): ["5.6.7.8"],
    ("nomail.in", "TXT"): txt("v=spf1 -all"), ("_dmarc.nomail.in", "TXT"): txt("v=DMARC1; p=none"),
}


class Dns(unittest.TestCase):
    def test_checks(self):
        r = FakeResolver(ZONES, flaky=[("good.in", "MX")])
        with mock.patch.object(dt, "_resolver", return_value=r), mock.patch.object(dt.time, "sleep") as sl:
            res = dt.dns_report(["good.in", "weak.in", "nomail.in", "missing.com"])
        got = {x["domain"]: x for x in res["results"]}
        g = got["good.in"]
        self.assertEqual((g["mail"], g["dmarc_policy"], g["dns_host"], g["problems"], g["pitches"]),
                         ("Google Workspace", "reject", "Cloudflare", [], []))
        self.assertTrue(sl.called)                                             # pause before the retry
        w = got["weak.in"]
        self.assertEqual(w["mail"], "GoDaddy mail")
        self.assertIn("No SPF record - mail is more likely to land in spam", w["problems"])
        self.assertTrue(any("Move from hosting mail" in p for p in w["pitches"]))
        self.assertTrue(any("deliverability" in p for p in w["pitches"]))
        n = got["nomail.in"]
        self.assertIn("No MX record - the domain cannot receive e-mail", n["problems"])
        self.assertIn("No website address (A record)", n["problems"])
        self.assertEqual(got["missing.com"]["status"], "missing")

    def test_spf_open(self):
        z = dict(ZONES)
        z[("good.in", "TXT")] = txt("v=spf1 include:x ?all")
        with mock.patch.object(dt, "_resolver", return_value=FakeResolver(z)):
            self.assertIn("SPF ends with ?all / +all - it protects nothing", dt.dns_check("good.in")["problems"])


def nrd_zip(domains):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("domain-names.txt", "\n".join(domains))
    return buf.getvalue()


class NewDomains(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.p = [mock.patch.object(hcm, "CACHE_DIR", self.tmp.name), mock.patch.object(dt.robots_policy, "allowed", return_value=True),
                  mock.patch.object(dt.deep_search, "public_url_guard", return_value=None)]
        for x in self.p:
            x.start()
        self.downloads = []

    def tearDown(self):
        for x in self.p:
            x.stop()
        self.tmp.cleanup()

    def fake_get(self, url, **kw):
        self.downloads.append(url)
        day = base64.b64decode(url.split("/")[-2]).decode()[:10]
        lists = {"2026-11-11": ["acme-bakery.com", "bestrealty.store", "x.xyz", "sunbakery.xyz"],
                 "2026-11-10": ["acme-bakery.com", "bakeryhub.net"]}
        if day not in lists:
            return SimpleNamespace(status_code=404, raw=io.BytesIO(b""), close=lambda: None)
        return SimpleNamespace(status_code=200, raw=SimpleNamespace(read=lambda n, decode_content=True: nrd_zip(lists[day])), close=lambda: None)

    def test_find_cache_and_filters(self):
        with mock.patch.object(dt.requests, "get", side_effect=self.fake_get):
            res = dt.new_domains({"keywords": ["Bakery", "realty"], "days": 3, "tlds": []}, today=TODAY)
            self.assertEqual([r["domain"] for r in res["results"]], ["acme-bakery.com", "bestrealty.store", "sunbakery.xyz", "bakeryhub.net"])
            self.assertEqual(res["results"][0]["registered_on"], "2026-11-11")             # newest day first, no duplicate
            self.assertTrue(any("not available" in n for n in res["notes"]))
            first = len(self.downloads)
            res2 = dt.new_domains({"keywords": ["bakery"], "days": 1, "tlds": ["com", "net"]}, today=TODAY)
        self.assertEqual(len(self.downloads), first)                                          # cached on disk
        self.assertEqual([r["domain"] for r in res2["results"]], ["acme-bakery.com"])
        for bad in ({"keywords": ["ab"]}, {"keywords": []}, {"keywords": ["bakery"], "days": 9}, {"keywords": ["bakery"], "tlds": ["in"]}):
            with self.assertRaises(ValueError):
                dt.new_domains(bad, today=TODAY)

    def test_robots_refusal(self):
        with mock.patch.object(dt.robots_policy, "allowed", return_value=False), mock.patch.object(dt.requests, "get") as g:
            res = dt.new_domains({"keywords": ["bakery"], "days": 1}, today=TODAY)
        g.assert_not_called()
        self.assertEqual(res["results"], [])


class Api(unittest.TestCase):
    def setUp(self):
        import app as app_module
        self.app = app_module
        self.client = app_module.app.test_client()
        ok = SimpleNamespace(status_code=200, json=lambda: {"email": "owner@example.com"})
        self.tmp = tempfile.TemporaryDirectory()
        self.p = [mock.patch("api_auth.requests.get", return_value=ok), mock.patch("api_auth.ALLOWED_EMAILS", set()),
                  mock.patch.object(hcm, "CACHE_DIR", self.tmp.name),
                  mock.patch.object(self.app, "MASTER_PATH", os.path.join(self.tmp.name, "m.csv"))]
        for x in self.p:
            x.start()
        self.h = {"Authorization": "Bearer t"}

    def tearDown(self):
        for x in self.p:
            x.stop()
        self.tmp.cleanup()

    def test_endpoints(self):
        self.assertEqual(self.client.get("/api/domain-tools").status_code, 401)
        for t in ("age", "dns", "new", "available"):
            self.assertEqual(self.client.post(f"/api/domain-tools/{t}", json={}).status_code, 401, t)
            self.assertEqual(self.client.post(f"/api/domain-tools/{t}", headers=self.h, json={}).status_code, 400, t)
        self.assertEqual(self.client.post("/api/domain-tools/zzz", headers=self.h, json={}).status_code, 404)
        row = {"company": "newco.in", "domain": "newco.in", "website": "https://newco.in", "emails": [], "phones": [], "socials": {},
               "lead_source": "Domain Tools", "website_signals": "Domain registered 2026-09-01"}
        self.client.post("/api/bulk-contacts/save", headers=self.h, json={"kind": "websites", "rows": [row]})
        with open(os.path.join(self.tmp.name, "m.csv"), encoding="utf-8-sig") as fh:
            saved = list(csv.DictReader(fh))[0]
        self.assertEqual((saved["source"], saved["website_signals"]), ("Domain Tools", "Domain registered 2026-09-01"))


if __name__ == "__main__":
    unittest.main()

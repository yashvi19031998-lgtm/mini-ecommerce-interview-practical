"""Tests for Bulk Contacts (bulk_contacts.py), no network (DNS and websites are faked).

python -m unittest test_bulk_contacts -v
"""
import csv
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

import dns.resolver

import bulk_contacts as bc
import html_cache_manager as hcm


class FakeResolver:
    """MX / A answers per domain; anything else is NXDOMAIN."""
    MX = {"acmefoods.in": [(10, "mx.acmefoods.in.")], "gmail.com": [(5, "gmail-smtp-in.l.google.com.")],
          "nullmx.com": [(0, ".")]}
    A_ONLY = {"aonly.in"}
    SLOW = {"slow.in"}

    def __init__(self):
        self.lifetime, self.calls = 0, []

    def resolve(self, domain, rtype):
        self.calls.append((domain, rtype))
        if domain in self.SLOW:
            raise dns.resolver.LifetimeTimeout(timeout=4, errors=[])
        if rtype == "MX":
            if domain in self.MX:
                return [SimpleNamespace(preference=p, exchange=h) for p, h in self.MX[domain]]
            if domain in self.A_ONLY:
                raise dns.resolver.NoAnswer()
        if rtype == "A" and domain in self.A_ONLY:
            return [SimpleNamespace(address="1.2.3.4")]
        raise dns.resolver.NXDOMAIN()


def master(rows):
    d = tempfile.mkdtemp()
    path = os.path.join(d, "m.csv")
    import lead_normalizer as ln
    reg = ln.MasterLeadRegistry(path)
    for r in rows:
        reg.add_lead(r, default_source="test")
    reg.save_master_safely()
    return path


class Emails(unittest.TestCase):
    def run_check(self, text, master_path=""):
        fake = FakeResolver()
        return bc.verify_emails(text, mx=bc._MxCache(fake, sleep=lambda s: None), master_path=master_path), fake

    def test_statuses(self):
        res, fake = self.run_check("ravi@acmefoods.in, info@acmefoods.in, x@gmial.com, t@mailinator.com, bad@@x, "
                                   "a@nowhere.in, RAVI@acmefoods.in, noreply@gmail.com, b@aonly.in, c@slow.in, d@nullmx.com")
        got = {r["input"]: (r["status"], r["reason"][:30]) for r in res["results"]}
        self.assertEqual(got["ravi@acmefoods.in"][0], "valid")
        self.assertEqual(got["info@acmefoods.in"][0], "risky")                 # role address
        self.assertEqual(got["x@gmial.com"][0], "invalid")
        self.assertEqual(res["results"][2]["suggestion"], "x@gmail.com")
        self.assertIn("Disposable", got["t@mailinator.com"][1])
        self.assertIn("Not a valid", got["bad@@x"][1])
        self.assertIn("does not exist", got["a@nowhere.in"][1])
        self.assertEqual(got["RAVI@acmefoods.in"][0], "duplicate")             # case-insensitive
        self.assertIn("no-reply", got["noreply@gmail.com"][1])
        self.assertEqual(got["b@aonly.in"][0], "risky")
        self.assertEqual(got["c@slow.in"][0], "unknown")
        self.assertIn("accepts no e-mail", res["results"][-1]["reason"])
        self.assertEqual(len([c for c in fake.calls if c[0] == "slow.in"]), 2)        # one retry on a timeout
        mx_calls = [c for c in fake.calls if c[0] == "acmefoods.in"]
        self.assertEqual(len(mx_calls), 1)                                      # one lookup per domain

    def test_in_leads_and_limits(self):
        path = master([{"company_name": "Acme", "email": "ravi@acmefoods.in"}])
        res, _ = self.run_check(["ravi@acmefoods.in"], master_path=path)
        self.assertTrue(res["results"][0]["in_leads"])
        for bad in ("", [], ["x"] * 501, 5):
            with self.assertRaises(ValueError):
                bc.verify_emails(bad, mx=bc._MxCache(FakeResolver(), sleep=lambda s: None))


class Phones(unittest.TestCase):
    def test_classify(self):
        cases = {
            "98250 12345": ("valid", "Mobile", "+919825012345"), "+91-98250-12345": ("valid", "Mobile", "+919825012345"),
            "09825012345": ("valid", "Mobile", "+919825012345"), "079-26543210": ("valid", "Landline", "+917926543210"),
            "(022) 2555 1234": ("valid", "Landline", "+912225551234"), "011 2345 6789": ("valid", "Landline", "+911123456789"),
            "1800 123 4567": ("valid", "Toll-free", "+9118001234567"), "+1 415 555 2671": ("valid", "International", "+14155552671"),
            "12345": ("invalid", "", ""), "9999999999": ("invalid", "", ""), "9876543210": ("invalid", "", ""),
        }
        for raw, (status, kind, e164) in cases.items():
            r = bc.classify_phone(raw)
            self.assertEqual((r["status"], r["type"], r["e164"]), (status, kind, e164), raw)

    def test_text_duplicates_and_leads(self):
        path = master([{"company_name": "Acme", "mobile_number": "9825012345"}])
        res = bc.clean_phones("Call 98250-12345 or 079-26543210\n09825012345\nhello\n", master_path=path)
        self.assertEqual([r["status"] for r in res["results"]], ["valid", "valid", "duplicate", "invalid"])
        self.assertTrue(res["results"][0]["in_leads"])
        self.assertEqual(res["counts"], {"valid": 2, "invalid": 1, "duplicate": 1, "in_leads": 1})
        with self.assertRaises(ValueError):
            bc.clean_phones("   ")


CSV_TEXT = ("Company Name,Contact Person,Email ID,Mobile,City,Website,Notes\n"
            "Acme Foods,Ravi,ravi@acmefoods.in,98250 12345,Ahmedabad,acmefoods.in,expo\n"
            "Beta Tools,,bad-email,,Surat,,\n"
            "Acme again,,RAVI@acmefoods.in,,Ahmedabad,,\n"
            ",,,,,,\n"
            "Known Co,,known@known.in,,Pune,,\n"
            "Nobody,,not an email,,,,\n")


class CsvImport(unittest.TestCase):
    def test_preview_guesses_columns(self):
        p = bc.preview_csv("﻿" + CSV_TEXT)
        self.assertEqual(p["mapping"], {"Company Name": "company_name", "Contact Person": "full_name", "Email ID": "email",
                                        "Mobile": "mobile_number", "City": "location", "Website": "website", "Notes": "description"})
        self.assertEqual(p["rows"], 6 - 1)                                      # the blank row is skipped

    def test_semicolon_file(self):
        p = bc.preview_csv("Firm;E-mail;Phone\nA;a@a.in;9825012345\n")
        self.assertEqual(p["mapping"], {"Firm": "company_name", "E-mail": "email", "Phone": "mobile_number"})

    def test_check_statuses(self):
        path = master([{"company_name": "Known Co", "email": "known@known.in"}])
        res = bc.check_csv(CSV_TEXT, bc.guess_mapping(CSV_TEXT.splitlines()[0].split(",")), "Expo list", master_path=path)
        st = {r["line"]: (r["status"], r["reason"][:25]) for r in res["results"]}
        self.assertEqual(st[2][0], "new")
        self.assertEqual(st[3], ("new", "E-mail not valid - kept t"))           # company kept, bad email reported
        self.assertEqual(st[4][0], "duplicate")
        self.assertEqual(st[6][0], "in_leads")
        self.assertEqual(st[7][0], "new")                                      # company name alone is usable
        self.assertNotIn(5, st)                                                 # line 5 is blank: numbering kept
        first = res["results"][0]
        self.assertEqual((first["email"], first["mobile_number"], first["source"]),
                         ("ravi@acmefoods.in", "+91 98250 12345", "Bulk Contacts (Expo list)"))

    def test_mapping_rules(self):
        for mapping, msg in (({"Email ID": "password"}, "unknown field"), ({"Email ID": "email", "Notes": "email"}, "two columns"),
                             ({"City": "location"}, "at least one")):
            with self.assertRaises(ValueError) as cm:
                bc.check_csv(CSV_TEXT, mapping)
            self.assertIn(msg, str(cm.exception).lower())

    def test_file_limits(self):
        for text, msg in (("", "empty"), ("only,header\n", "header row and at least one"),
                          ("a\n" + "x\n" * 5001, "at most 5000")):
            with self.assertRaises(ValueError) as cm:
                bc.preview_csv(text)
            self.assertIn(msg, str(cm.exception).lower())

    def test_save_and_no_double_save(self):
        d = tempfile.mkdtemp()
        path = os.path.join(d, "m.csv")
        rows = [r for r in bc.check_csv(CSV_TEXT, bc.guess_mapping(CSV_TEXT.splitlines()[0].split(",")), "Expo")["results"]
                if r["status"] == "new"]
        a = bc.save_rows(rows, path)
        b = bc.save_rows(rows, path)
        self.assertEqual((a["added"], b["added"]), (len(rows), 0))
        with open(path, encoding="utf-8-sig") as fh:
            saved = list(csv.DictReader(fh))
        self.assertEqual(saved[0]["source"], "Bulk Contacts (Expo)")
        self.assertEqual(saved[0]["lead_type"], "Imported Contact")


class Websites(unittest.TestCase):
    def test_batch(self):
        def crawl(url):
            if "down" in url:
                return {"error": "website could not be opened", "pages": []}
            return {"name": "Acme Foods", "emails": ["ravi@acmefoods.in"], "phones": ["+91 98250 12345"],
                    "address": "Ahmedabad", "socials": {"instagram": "https://instagram.com/acme"}, "pages": [1, 2]}
        with mock.patch.object(bc.deep_search, "crawl_site", side_effect=crawl) as c, \
                mock.patch.object(bc.deep_search, "public_url_guard", side_effect=lambda u: None):
            res = bc.website_contacts(["acmefoods.in", "https://www.acmefoods.in/contact", "down.in",
                                       "https://www.facebook.com/acme"])
        st = {r["domain"]: r["status"] for r in res["results"]}
        self.assertEqual(st, {"acmefoods.in": "found", "down.in": "error", "facebook.com": "skipped"})
        self.assertEqual(res["duplicates_skipped"], 1)
        self.assertEqual(c.call_count, 2)                                       # platform page never crawled
        leads = bc.website_rows_to_leads(res["results"])
        self.assertEqual(len(leads), 3)
        self.assertEqual((leads[0]["email"], leads[0]["source"]), ("ravi@acmefoods.in", "Bulk Contacts (Website Contacts)"))

    def test_private_address_blocked(self):
        res = bc.website_contacts(["http://127.0.0.1/admin"])
        self.assertEqual(res["results"][0]["status"], "error")
        self.assertIn("Blocked", res["results"][0]["error"])

    def test_limits(self):
        for bad in ([], ["x"] * 11, ["not a site"]):
            with self.assertRaises(ValueError):
                bc.website_contacts(bad)


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
        urls = ("/api/bulk-contacts/websites", "/api/bulk-contacts/emails", "/api/bulk-contacts/phones",
                "/api/bulk-contacts/import/preview", "/api/bulk-contacts/import/check", "/api/bulk-contacts/save")
        self.assertEqual(self.client.get("/api/bulk-contacts").status_code, 401)
        for u in urls:
            self.assertEqual(self.client.post(u, json={}).status_code, 401, u)
            self.assertEqual(self.client.post(u, headers=self.h, json={}).status_code, 400, u)
        ph = self.client.post("/api/bulk-contacts/phones", headers=self.h, json={"text": "98250 12345"}).get_json()
        self.assertEqual(ph["results"][0]["e164"], "+919825012345")
        pv = self.client.post("/api/bulk-contacts/import/preview", headers=self.h, json={"text": CSV_TEXT}).get_json()
        ck = self.client.post("/api/bulk-contacts/import/check", headers=self.h,
                              json={"text": CSV_TEXT, "mapping": pv["mapping"], "source": "Expo"}).get_json()
        new = [r for r in ck["results"] if r["status"] == "new"]
        sv = self.client.post("/api/bulk-contacts/save", headers=self.h, json={"kind": "import", "rows": new}).get_json()
        self.assertEqual(sv["added"], len(new))
        again = self.client.post("/api/bulk-contacts/import/check", headers=self.h,
                                 json={"text": CSV_TEXT, "mapping": pv["mapping"]}).get_json()
        self.assertEqual(again["counts"]["new"], 0)                             # now all in Leads
        big = self.client.post("/api/bulk-contacts/phones", headers=self.h, data="x" * (7 * 1024 * 1024),
                               content_type="application/json")
        self.assertEqual(big.status_code, 400)


if __name__ == "__main__":
    unittest.main()

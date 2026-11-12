"""Tests for Lead Care -> Lead Enrichment (lead_enrichment.py), no network (Deep Search and the website check are faked).

python -m unittest test_lead_enrichment -v
"""
import csv
import os
import shutil
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

import html_cache_manager as hcm
import lead_cleanup as lc
import lead_enrichment as le
import lead_normalizer as ln

FIELDS = ln.MASTER_FIELDNAMES
ROWS = [
    {"lead_id": "LEAD-00001", "company_name": "Acme Foods", "website": "https://acmefoods.in", "source": "IndiaMART",
     "last_updated_at": "2025-01-01 10:00:00"},
    {"lead_id": "LEAD-00002", "company_name": "Beta Tools", "website": "", "source": "Corporate Registries"},
    {"lead_id": "LEAD-00003", "company_name": "Gamma", "email": "a@gamma.in", "mobile_number": "+91 98250 12345",
     "website": "https://gamma.in", "website_signals": "no obvious issues"},                          # nothing missing
    {"lead_id": "LEAD-00004", "company_name": "Listing Only", "website": "https://www.indiamart.com/x/", "source": "IndiaMART"},
]


def write(path, rows):
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in FIELDS})


def read(path):
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def fake_deep(items, engine="auto", use_hunter=False, place=""):
    out = []
    for it in items:
        if it["key"] == "LEAD-00001":
            out.append({"key": it["key"], "website": "https://acmefoods.in/", "emails": ["sales@acmefoods.in"],
                        "phones": ["+91 98250 11111"], "pages_checked": 3, "status": "found", "steps": ["crawl: 3 page(s)"]})
        elif it["key"] == "LEAD-00002":
            out.append({"key": it["key"], "website": "https://betatools.co.in/", "emails": [], "phones": [],
                        "pages_checked": 1, "status": "partial", "steps": ["website: found via DuckDuckGo"]})
        else:
            out.append({"key": it["key"], "website": "", "emails": [], "phones": [], "status": "none", "steps": []})
    return {"results": out, "engine": "duckduckgo", "found": 1}


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "all_leads_master.csv")
        write(self.path, ROWS)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)


class Candidates(Base):
    def test_filters(self):
        r = le.candidates(self.path, {"needs": ["email", "mobile_number"], "limit": 10})
        self.assertEqual([x["lead_id"] for x in r["results"]], ["LEAD-00001", "LEAD-00002", "LEAD-00004"])
        r = le.candidates(self.path, {"needs": ["email"], "limit": 10, "only_with_website": True})
        self.assertEqual([x["lead_id"] for x in r["results"]], ["LEAD-00001"])            # a portal link is not a website
        r = le.candidates(self.path, {"needs": ["email"], "limit": 10, "source": "corporate"})
        self.assertEqual([x["lead_id"] for x in r["results"]], ["LEAD-00002"])
        for bad in ({"needs": []}, {"needs": ["password"]}, {"needs": ["email"], "limit": 7}):
            with self.assertRaises(ValueError):
                le.candidates(self.path, bad)


class Enrich(Base):
    def test_proposals_only_for_empty_fields_and_nothing_written(self):
        before = read(self.path)
        with mock.patch.object(le.deep_search, "deep_search", side_effect=fake_deep) as d, \
                mock.patch.object(le.website_signals, "check_website", return_value="not mobile-friendly (no viewport tag)"):
            r = le.enrich(self.path, ["LEAD-00001", "LEAD-00002", "LEAD-00003", "LEAD-00004"])
        props = {(p["lead_id"], p["field"]): p["new"] for p in r["proposals"]}
        self.assertEqual(props[("LEAD-00001", "email")], "sales@acmefoods.in")
        self.assertEqual(props[("LEAD-00001", "mobile_number")], "+91 98250 11111")
        self.assertNotIn(("LEAD-00001", "website"), props)                     # already filled
        self.assertEqual(props[("LEAD-00002", "website")], "https://betatools.co.in/")
        self.assertIn(("LEAD-00002", "website_signals"), props)                # checked on the found website
        self.assertNotIn(("LEAD-00003", "website_signals"), props)             # already has a check
        items = d.call_args.args[0]
        self.assertEqual(next(i for i in items if i["key"] == "LEAD-00004")["website"], "")   # portal never the website
        self.assertEqual(read(self.path), before)                              # enrich writes nothing
        for bad in ([], ["x"] * 6, None):
            with self.assertRaises(ValueError):
                le.enrich(self.path, bad)
        with self.assertRaises(ValueError):
            le.enrich(self.path, ["LEAD-00001"], steps=["delete"])


class Save(Base):
    def test_validated_fill_only_with_undo(self):
        changes = [
            {"lead_id": "LEAD-00001", "field": "email", "new": "Sales@AcmeFoods.in", "from": "Deep Search"},
            {"lead_id": "LEAD-00002", "field": "website", "new": "https://betatools.co.in/"},
            {"lead_id": "LEAD-00003", "field": "email", "new": "other@gamma.in"},              # already filled
            {"lead_id": "LEAD-00002", "field": "company_name", "new": "Hacked"},              # not fillable
            {"lead_id": "LEAD-00002", "field": "email", "new": "not an email"},              # invalid
            {"lead_id": "LEAD-00001", "field": "website_signals", "new": "line1\nline2"},
            {"lead_id": "LEAD-09999", "field": "email", "new": "x@y.in"},                    # unknown lead
            {"lead_id": "LEAD-00004", "field": "email", "new": "a@b.in"},
            {"lead_id": "LEAD-00002", "field": "mobile_number", "new": "12345"},              # invalid phone
        ]
        before = read(self.path)
        res = le.save(self.path, changes)
        after = read(self.path)
        self.assertEqual((res["applied"], res["skipped"], len(after)), (4, 5, len(before)))
        self.assertEqual(after[0]["email"], "sales@acmefoods.in")
        self.assertEqual(after[0]["website_signals"], "line1 line2")
        self.assertEqual(after[1]["website"], "https://betatools.co.in/")
        self.assertEqual(after[2]["email"], "a@gamma.in")                                    # untouched
        self.assertEqual(after[1]["company_name"], "Beta Tools")
        for i in range(len(before)):
            for k in FIELDS:
                if before[i][k] and k != "last_updated_at":
                    self.assertEqual(before[i][k], after[i][k])
        hist = lc.history(self.path)
        self.assertEqual(hist[0]["fixes"], ["enrichment"])
        lc.undo(self.path, res["log_id"])
        undone = read(self.path)
        for i in range(len(before)):                                                         # every old value back
            for k in FIELDS:
                if before[i][k]:
                    self.assertEqual(before[i][k], undone[i][k], (i, k))
        self.assertEqual((undone[0]["email"], undone[0]["website_signals"], undone[1]["website"]), ("", "", ""))

    def test_private_website_refused(self):
        res = le.save(self.path, [{"lead_id": "LEAD-00002", "field": "website", "new": "http://127.0.0.1/admin"}])
        self.assertEqual((res["applied"], res["skipped"]), (0, 1))
        with self.assertRaises(ValueError):
            le.save(self.path, [])


class Api(unittest.TestCase):
    def setUp(self):
        import app as app_module
        self.app = app_module
        self.client = app_module.app.test_client()
        ok = SimpleNamespace(status_code=200, json=lambda: {"email": "owner@example.com"})
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "m.csv")
        write(self.path, ROWS)
        self.p = [mock.patch("api_auth.requests.get", return_value=ok), mock.patch("api_auth.ALLOWED_EMAILS", set()),
                  mock.patch.object(hcm, "CACHE_DIR", self.tmp.name), mock.patch.object(self.app, "MASTER_PATH", self.path)]
        for x in self.p:
            x.start()
        self.h = {"Authorization": "Bearer t"}

    def tearDown(self):
        for x in self.p:
            x.stop()
        self.tmp.cleanup()

    def test_endpoints(self):
        for u in ("candidates", "run", "save"):
            self.assertEqual(self.client.post(f"/api/lead-care/enrichment/{u}", json={}).status_code, 401, u)
        c = self.client.post("/api/lead-care/enrichment/candidates", headers=self.h, json={"needs": ["email"], "limit": 10}).get_json()
        self.assertEqual(c["matching"], 3)
        self.assertEqual(self.client.post("/api/lead-care/enrichment/run", headers=self.h, json={}).status_code, 400)
        with mock.patch.object(le.deep_search, "deep_search", side_effect=fake_deep), \
                mock.patch.object(le.website_signals, "check_website", return_value="no obvious issues"):
            r = self.client.post("/api/lead-care/enrichment/run", headers=self.h, json={"lead_ids": ["LEAD-00001"]}).get_json()
        s = self.client.post("/api/lead-care/enrichment/save", headers=self.h, json={"changes": r["proposals"]}).get_json()
        self.assertEqual(s["applied"], 3)                                 # e-mail, phone, website check
        self.assertEqual(read(self.path)[0]["email"], "sales@acmefoods.in")


if __name__ == "__main__":
    unittest.main()

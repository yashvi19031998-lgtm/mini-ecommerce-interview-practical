"""Tests for Lead Care -> Data Cleanup (lead_cleanup.py) and the lossless leads-file round trip.

python -m unittest test_lead_cleanup -v
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
import lead_normalizer as ln

FIELDS = ln.MASTER_FIELDNAMES


def write(path, rows):
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in FIELDS})


def read(path):
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


ROWS = [
    {"lead_id": "LEAD-00001", "company_name": "Acme Foods", "email": "ravi@acmefoods.in", "website": "",
     "last_updated_at": "2025-01-01 10:00:00"},                                                                        # fill website
    {"lead_id": "LEAD-00002", "company_name": "Hiring: React dev", "email": "jobs@otherco.com", "website": "",
     "description": "Remote role"},                                                                                    # domain not in lead
    {"lead_id": "LEAD-00003", "company_name": "Freelancer A", "email": "x@gmail.com", "website": ""},                   # free mail
    {"lead_id": "LEAD-00004", "company_name": "Kappa Traders", "email": "", "mobile_number": "",
     "description": "Call 98250 12345 or write to info@kappa.co.in"},                                                  # email + phone from text
    {"lead_id": "LEAD-00005", "company_name": "Gov Portal", "website": "http://eportal.incometax.gov.in/",
     "mobile_number": "+91 66184 26838, 011-46710423, 2018-4337622"},                                                  # must stay as is
    {"lead_id": "LEAD-00006", "company_name": "Job A", "email": "jane@portal.io", "description": "portal.io job"},
    {"lead_id": "LEAD-00007", "company_name": "Job B", "email": "jane@portal.io", "description": "portal.io job"},
    {"lead_id": "LEAD-00008", "company_name": "Job C", "email": "jane@portal.io", "description": "portal.io job"},        # shared domain
    {"lead_id": "LEAD-00009", "company_name": "Filled Co", "email": "a@filled.in", "website": "https://filled.in"},
]


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "all_leads_master.csv")
        write(self.path, ROWS)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)


class RoundTrip(Base):
    def test_load_save_changes_nothing(self):
        before = read(self.path)
        ln.MasterLeadRegistry(self.path).save_master_safely()
        after = read(self.path)
        self.assertEqual(len(before), len(after))
        changed = [(i, k) for i in range(len(before)) for k in FIELDS if before[i][k] and before[i][k] != after[i][k]]
        self.assertEqual(changed, [])                                  # gov.in website and odd phone list untouched
        self.assertEqual(after[4]["website"], "http://eportal.incometax.gov.in/")

    def test_indexes_still_normalised(self):
        reg = ln.MasterLeadRegistry(self.path)
        self.assertEqual(reg.find_match({"email": "RAVI@acmefoods.in"}), 0)
        self.assertEqual(reg.find_match({"mobile_number": "+91 98250 12345"}), None)


class Scan(Base):
    def test_fixes(self):
        r = lc.scan(self.path)
        got = {f["id"]: [(c["lead_id"], c["new"]) for c in f["changes"]] for f in r["fixes"]}
        self.assertEqual(got["website_from_email"], [("LEAD-00001", "https://acmefoods.in")])
        self.assertEqual(got["email_from_text"], [("LEAD-00004", "info@kappa.co.in")])         # .co.in kept
        self.assertEqual(got["phone_from_text"], [("LEAD-00004", "+91 98250 12345")])
        shared = {(s["kind"], s["value"]) for s in r["shared_contacts"]}
        self.assertIn(("e-mail", "jane@portal.io"), shared)
        self.assertNotIn(("domain", "gmail.com"), shared)
        self.assertEqual(r["format_issues"][0]["lead_id"], "LEAD-00005")
        self.assertEqual(read(self.path), read(self.path))                 # scan writes nothing
        self.assertFalse(os.path.exists(lc.backups_dir(self.path)))


class ApplyUndo(Base):
    def test_apply_fills_only_blanks_with_backup_and_log(self):
        before = read(self.path)
        res = lc.apply(self.path, ["website_from_email", "email_from_text", "phone_from_text"])
        after = read(self.path)
        self.assertEqual((res["applied"], len(after)), (3, len(before)))                     # no row removed
        for i in range(len(before)):
            for k in FIELDS:
                if before[i][k] and k != "last_updated_at":
                    self.assertEqual(before[i][k], after[i][k], (i, k))                      # no filled value changed
        self.assertEqual(after[0]["website"], "https://acmefoods.in")
        self.assertEqual((after[3]["email"], after[3]["mobile_number"]), ("info@kappa.co.in", "+91 98250 12345"))
        self.assertEqual(read(os.path.join(lc.backups_dir(self.path), res["backup"])), before)  # full backup
        hist = lc.history(self.path)
        self.assertEqual((hist[0]["changes"], hist[0]["undone"]), (3, False))
        again = lc.apply(self.path, ["website_from_email"])
        self.assertEqual(again["applied"], 1)            # LEAD-00004 now has info@kappa.co.in -> its website
        self.assertEqual(read(self.path)[3]["website"], "https://kappa.co.in")
        self.assertEqual(lc.apply(self.path, ["website_from_email"])["applied"], 0)         # nothing left to fill

    def test_undo(self):
        res = lc.apply(self.path, ["website_from_email", "email_from_text"])
        rows = read(self.path)
        rows[3]["email"] = "owner-typed@kappa.co.in"                                          # changed by hand later
        write(self.path, rows)
        u = lc.undo(self.path, res["log_id"])
        after = read(self.path)
        self.assertEqual((u["reverted"], u["kept_newer"]), (1, 1))
        self.assertEqual(after[0]["website"], "")
        self.assertEqual(after[0]["last_updated_at"], ROWS[0].get("last_updated_at", ""))  # date put back too
        self.assertEqual(after[3]["email"], "owner-typed@kappa.co.in")                       # newer value kept
        self.assertEqual(len(after), len(ROWS))
        with self.assertRaises(ValueError):
            lc.undo(self.path, res["log_id"])
        for bad in ("../../etc", "", None, "20260101-000000-000000"):
            with self.assertRaises(ValueError):
                lc.undo(self.path, bad)

    def test_bad_fix_ids(self):
        for bad in ([], ["drop_rows"], "website_from_email", None):
            with self.assertRaises(ValueError):
                lc.apply(self.path, bad)

    def test_backups_pruned(self):
        with mock.patch.object(lc, "KEEP_BACKUPS", 2):
            for _ in range(3):
                write(self.path, ROWS)
                lc.apply(self.path, ["website_from_email"])
        backups = [f for f in os.listdir(lc.backups_dir(self.path)) if f.endswith(".csv")]
        self.assertEqual(len(backups), 2)


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
        self.assertEqual(self.client.get("/api/lead-care/cleanup").status_code, 401)
        self.assertEqual(self.client.post("/api/lead-care/cleanup/apply", json={}).status_code, 401)
        scan = self.client.get("/api/lead-care/cleanup", headers=self.h).get_json()
        self.assertEqual(scan["leads"], len(ROWS))
        self.assertEqual(self.client.post("/api/lead-care/cleanup/apply", headers=self.h, json={"fixes": ["x"]}).status_code, 400)
        res = self.client.post("/api/lead-care/cleanup/apply", headers=self.h, json={"fixes": ["website_from_email"]}).get_json()
        self.assertEqual(res["applied"], 1)
        u = self.client.post("/api/lead-care/cleanup/undo", headers=self.h, json={"log_id": res["log_id"]}).get_json()
        self.assertEqual(u["reverted"], 1)
        self.assertEqual(self.client.post("/api/lead-care/cleanup/undo", headers=self.h, json={"log_id": "nope"}).status_code, 400)


if __name__ == "__main__":
    unittest.main()

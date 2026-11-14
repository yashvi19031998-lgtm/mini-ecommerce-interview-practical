"""datastore.py: two-way merge of the local files with the single app_data table (fake in-memory DB)."""
import csv
import json
import os
import shutil
import tempfile
import unittest
from unittest import mock

import datastore


class FakeDB:
    def __init__(self):
        self.rows = {}          # (kind, key) -> {"data", "hash", "pos"}
        self.calls = 0

    def hashes(self, kind):
        self.calls += 1
        return {k: v["hash"] for (kd, k), v in self.rows.items() if kd == kind}

    def get(self, kind, keys):
        return {k: {"key": k, **self.rows[(kind, k)]} for k in keys if (kind, k) in self.rows}

    def upsert(self, kind, rows):
        for r in rows:
            self.rows[(kind, r["key"])] = {"data": json.loads(json.dumps(r["data"])), "hash": r["hash"], "pos": r["pos"]}

    def delete(self, kind, keys):
        for k in keys:
            self.rows.pop((kind, k), None)

    def set_lead(self, key, row, pos=0):
        self.rows[("lead", key)] = {"data": row, "hash": datastore._hash(row), "pos": pos}


COLS = ["lead_id", "company_name", "email", "status"]


def write_leads(path, rows, bom=True):
    with open(path, "w", encoding="utf-8-sig" if bom else "utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(COLS)
        for r in rows:
            w.writerow([r.get(c, "") for c in COLS])


def read_leads(path):
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def lead(i, **kw):
    return {"lead_id": f"L{i:03d}", "company_name": f"Co {i}", "email": f"a{i}@x.com", "status": "NEW", **kw}


class Machine:
    """One computer: its own folder + snapshot, sharing the FakeDB."""
    def __init__(self, db):
        self.dir = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.dir, "logs"))
        self.db = db

    def path(self, rel="all_leads_master.csv"):
        return os.path.join(self.dir, rel)

    def sync(self):
        with mock.patch.object(datastore, "BASE_DIR", self.dir), \
             mock.patch.object(datastore, "SNAPSHOT", os.path.join(self.dir, ".datastore", "snapshot.json")), \
             mock.patch.object(datastore, "STATUS_FILE", os.path.join(self.dir, ".datastore", "last.json")), \
             mock.patch.object(datastore, "configured", return_value=True), \
             mock.patch.object(datastore, "remote_hashes", self.db.hashes), \
             mock.patch.object(datastore, "remote_rows", self.db.get), \
             mock.patch.object(datastore, "upsert", self.db.upsert), \
             mock.patch.object(datastore, "delete", self.db.delete):
            return datastore.sync()


class DatastoreSyncTests(unittest.TestCase):
    def setUp(self):
        self.db = FakeDB()
        self.pc = Machine(self.db)
        self.addCleanup(shutil.rmtree, self.pc.dir, True)

    def new_machine(self):
        m = Machine(self.db)
        self.addCleanup(shutil.rmtree, m.dir, True)
        return m

    def test_first_sync_uploads_everything(self):
        write_leads(self.pc.path(), [lead(1), lead(2)])
        r = self.pc.sync()
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["kinds"]["lead"]["sent"], 2)
        self.assertEqual(self.db.rows[("lead", "L002")]["data"]["email"], "a2@x.com")
        self.assertEqual(self.db.rows[("meta", "columns:lead")]["data"]["columns"], COLS)
        self.assertEqual(self.pc.sync()["kinds"]["lead"]["sent"], 0)          # nothing new the 2nd time

    def test_fresh_machine_gets_identical_file(self):
        write_leads(self.pc.path(), [lead(1), lead(2, company_name='Comma, "quoted" Co')])
        with open(self.pc.path("logs/sent_emails.csv"), "w", encoding="utf-8", newline="") as fh:
            fh.write("email,sent_at,subject\na@x.com,2026-11-01 10:00:00,Hi\na@x.com,2026-11-01 10:00:00,Hi\n")
        self.pc.sync()
        runner = self.new_machine()
        self.assertTrue(runner.sync()["ok"])
        for rel in ("all_leads_master.csv", "logs/sent_emails.csv"):
            self.assertEqual(open(runner.path(rel), "rb").read(), open(self.pc.path(rel), "rb").read(), rel)

    def test_changes_flow_both_ways(self):
        write_leads(self.pc.path(), [lead(1), lead(2), lead(3)])
        self.pc.sync()
        runner = self.new_machine(); runner.sync()
        # runner sends an e-mail to L001 and finds L004; the PC changes L002
        rows = read_leads(runner.path()); rows[0]["status"] = "EMAIL_SENT"; rows.append(lead(4))
        write_leads(runner.path(), rows)
        runner.sync()
        rows = read_leads(self.pc.path()); rows[1]["status"] = "WON"
        write_leads(self.pc.path(), rows)
        r = self.pc.sync()
        self.assertEqual((r["kinds"]["lead"]["sent"], r["kinds"]["lead"]["received"]), (1, 2))
        got = {x["lead_id"]: x["status"] for x in read_leads(self.pc.path())}
        self.assertEqual(got, {"L001": "EMAIL_SENT", "L002": "WON", "L003": "NEW", "L004": "NEW"})
        runner.sync()
        self.assertEqual({x["lead_id"]: x["status"] for x in read_leads(runner.path())}, got)

    def test_same_lead_changed_on_both_sides_this_machine_wins(self):
        write_leads(self.pc.path(), [lead(1)])
        self.pc.sync()
        self.db.set_lead("L001", lead(1, status="LOST"))
        write_leads(self.pc.path(), [lead(1, status="WON")])
        self.pc.sync()
        self.assertEqual(self.db.rows[("lead", "L001")]["data"]["status"], "WON")

    def test_deletes_flow_both_ways(self):
        write_leads(self.pc.path(), [lead(i) for i in range(1, 11)])
        self.pc.sync()
        write_leads(self.pc.path(), [lead(i) for i in range(1, 10)])   # L010 removed here
        self.pc.sync()
        self.assertNotIn(("lead", "L010"), self.db.rows)
        self.db.delete("lead", ["L001"])                                  # removed elsewhere
        self.pc.sync()
        self.assertNotIn("L001", [x["lead_id"] for x in read_leads(self.pc.path())])

    def test_edit_beats_delete(self):
        write_leads(self.pc.path(), [lead(1), lead(2)])
        self.pc.sync()
        write_leads(self.pc.path(), [lead(2)])                            # deleted here...
        self.db.set_lead("L001", lead(1, status="REPLIED"))                # ...but replied meanwhile
        self.pc.sync()
        self.assertIn(("lead", "L001"), self.db.rows)
        self.assertIn("L001", [x["lead_id"] for x in read_leads(self.pc.path())])

    def test_truncated_file_never_wipes_the_database(self):
        write_leads(self.pc.path(), [lead(i) for i in range(1, 101)])
        self.pc.sync()
        write_leads(self.pc.path(), [lead(1)])                            # 99 rows gone at once
        r = self.pc.sync()
        self.assertEqual(len([k for k in self.db.rows if k[0] == "lead"]), 100)
        self.assertTrue(r["kinds"]["lead"]["notes"])

    def test_missing_file_is_rebuilt_not_deleted(self):
        write_leads(self.pc.path(), [lead(1), lead(2)])
        self.pc.sync()
        os.remove(self.pc.path())
        self.pc.sync()
        self.assertEqual(len(read_leads(self.pc.path())), 2)
        self.assertEqual(len([k for k in self.db.rows if k[0] == "lead"]), 2)

    def test_file_written_during_sync_is_not_overwritten(self):
        write_leads(self.pc.path(), [lead(1)])
        self.pc.sync()
        self.db.set_lead("L002", lead(2), pos=1)
        real_get = self.db.get

        def get_and_app_writes(kind, keys):          # the app saves a lead while we download
            out = real_get(kind, keys)
            if kind == "lead":
                write_leads(self.pc.path(), [lead(1, status="CONTACTED")])
                os.utime(self.pc.path(), (1, 1))
            return out
        self.db.get = get_and_app_writes
        r = self.pc.sync()
        self.assertEqual([x["status"] for x in read_leads(self.pc.path())], ["CONTACTED"])
        self.assertTrue(r["kinds"]["lead"]["notes"])
        self.db.get = real_get
        self.pc.sync()                                 # next round: both changes kept
        got = {x["lead_id"]: x["status"] for x in read_leads(self.pc.path())}
        self.assertEqual(got, {"L001": "CONTACTED", "L002": "NEW"})
        self.assertEqual(self.db.rows[("lead", "L001")]["data"]["status"], "CONTACTED")

    def test_settings_json_synced(self):
        json.dump({"company_name": "Sangeeta"}, open(self.pc.path("company_settings.json"), "w"))
        self.pc.sync()
        runner = self.new_machine(); runner.sync()
        self.assertEqual(json.load(open(runner.path("company_settings.json")))["company_name"], "Sangeeta")
        json.dump({"company_name": "New name"}, open(runner.path("company_settings.json"), "w"))
        runner.sync(); self.pc.sync()
        self.assertEqual(json.load(open(self.pc.path("company_settings.json")))["company_name"], "New name")

    def test_github_runner_never_overwrites_settings(self):
        json.dump({"company_name": "Owner"}, open(self.pc.path("company_settings.json"), "w"))
        self.pc.sync()
        runner = self.new_machine(); runner.sync()
        json.dump({"company_name": "Test junk"}, open(runner.path("company_settings.json"), "w"))
        json.dump({"mailbox_check": "works"}, open(runner.path("logs/mail_check_status.json"), "w"))
        with mock.patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}):
            runner.sync()
        self.assertEqual(self.db.rows[("state", "company_settings.json")]["data"]["company_name"], "Owner")
        self.assertEqual(json.load(open(runner.path("company_settings.json")))["company_name"], "Owner")
        self.assertEqual(self.db.rows[("state", "logs/mail_check_status.json")]["data"]["mailbox_check"], "works")

    def test_required_sync_stops_on_an_empty_database(self):
        runner = self.new_machine()                     # wrong key: the table looks empty
        with mock.patch.object(datastore, "BASE_DIR", runner.dir),              mock.patch.object(datastore, "SNAPSHOT", os.path.join(runner.dir, ".datastore", "s.json")),              mock.patch.object(datastore, "STATUS_FILE", os.path.join(runner.dir, ".datastore", "l.json")),              mock.patch.object(datastore, "configured", return_value=True),              mock.patch.object(datastore, "remote_hashes", self.db.hashes),              mock.patch.object(datastore, "remote_rows", self.db.get),              mock.patch.object(datastore, "upsert", self.db.upsert),              mock.patch.object(datastore, "delete", self.db.delete):
            with self.assertRaises(datastore.DatastoreError):
                datastore.sync(required=True)

    def test_not_configured_is_a_no_op(self):
        with mock.patch.object(datastore, "configured", return_value=False):
            r = datastore.sync()
        self.assertFalse(r["ok"])
        with mock.patch.object(datastore, "configured", return_value=False):
            with self.assertRaises(datastore.DatastoreError):
                datastore.sync(required=True)


class FilterTests(unittest.TestCase):
    def test_keys_with_quotes_spaces_and_slashes_are_escaped(self):
        from urllib.parse import unquote
        got = unquote(datastore._in(['"hire dev" Ahmedabad', "logs/x.json", "a,b", r"c\d"]))
        self.assertEqual(got, r'in.("\"hire dev\" Ahmedabad","logs/x.json","a,b","c\\d")')
        self.assertNotIn(" ", datastore._in(["a b"]))


class PlanTests(unittest.TestCase):
    def test_plan_cases(self):
        snap = {"a": "1", "b": "1", "c": "1", "d": "1"}
        local = {"a": "2", "b": "1", "d": "1", "n": "9"}           # a edited, c deleted, n new
        remote = {"a": "1", "b": "3", "c": "1", "d": "1", "m": "7"}  # b edited, m new
        push, dr, pull, dl = datastore.plan(local, remote, snap)
        self.assertEqual((sorted(push), dr, sorted(pull), dl), (["a", "n"], ["c"], ["b", "m"], []))


if __name__ == "__main__":
    unittest.main()

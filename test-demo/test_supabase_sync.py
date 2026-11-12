import unittest
from unittest import mock
import lead_importer, sync_to_supabase

class SupabaseSyncHonesty(unittest.TestCase):
    def test_missing_keys_returns_false(self):
        with mock.patch.object(sync_to_supabase, "SUPABASE_KEY", ""):
            self.assertIs(sync_to_supabase.sync(), False)

    def test_commit_reports_not_synced_without_keys(self):
        import tempfile, os
        with tempfile.TemporaryDirectory() as d, mock.patch.object(sync_to_supabase, "SUPABASE_KEY", ""):
            res = lead_importer.commit_imported_leads([{"company_name": "Acme", "website": "https://acme.in", "source": "t"}],
                                                      master_csv=os.path.join(d, "m.csv"))
        self.assertTrue(res["success"])
        self.assertFalse(res["supabase_synced"])

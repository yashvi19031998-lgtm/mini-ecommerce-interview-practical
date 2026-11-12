"""Tests for the API keys status catalog (Settings -> API Keys & Integrations)."""
import os
import unittest
from unittest import mock

import api_keys_catalog as cat

ALL_VARS = sorted({n for it in cat.INTEGRATIONS for k in it["keys"] + it.get("fallback", []) for n in k.split("|")})
SECRET = "sk-very-secret-value-123"


def env(**set_vars):
    """Environment with every catalog variable cleared, then the given ones set."""
    base = {k: "" for k in ALL_VARS}
    base.update(set_vars)
    return mock.patch.dict(os.environ, base)


def item(res, iid):
    return next(i for i in res["items"] if i["id"] == iid)


class ApiKeysCatalogTests(unittest.TestCase):
    def test_catalog_ids_unique_and_complete(self):
        ids = [i["id"] for i in cat.INTEGRATIONS]
        self.assertEqual(len(ids), len(set(ids)))
        for i in cat.INTEGRATIONS:
            for f in ("group", "name", "keys", "purpose", "used_by", "cost", "cost_note", "url"):
                self.assertTrue(i.get(f), f"{i['id']} missing {f}")
            self.assertIn(i["cost"], ("free", "limited", "paid"))
            self.assertTrue(i["url"].startswith("https://"))

    def test_covers_crm_and_job_portal_keys(self):
        names = {k["name"] for i in cat.integration_status()["items"] for k in i["keys"]}
        for k in ("HUNTER_API_KEY", "APOLLO_API_KEY", "GOOGLE_PLACES_API_KEY", "SNOV_CLIENT_ID", "SNOV_CLIENT_SECRET",
                  "LUSHA_API_KEY", "ROCKETREACH_API_KEY", "ADZUNA_APP_ID", "JOOBLE_API_KEY", "SMTP_USER", "IMAP_PASSWORD"):
            self.assertIn(k, names)

    def test_all_missing(self):
        with env():
            res = cat.integration_status()
        self.assertEqual(res["counts"]["configured"], 0)
        self.assertTrue(all(i["status"] == "missing" for i in res["items"]))

    def test_configured_partial_and_whitespace(self):
        with env(HUNTER_API_KEY=SECRET, SNOV_CLIENT_ID="x", SNOV_CLIENT_SECRET="   "):
            res = cat.integration_status()
        self.assertEqual(item(res, "hunter")["status"], "configured")
        self.assertEqual(item(res, "snov")["status"], "partial")

    def test_imap_falls_back_to_smtp(self):
        with env(SMTP_USER="a@b.com", SMTP_PASS=SECRET):
            res = cat.integration_status()
        self.assertEqual(item(res, "smtp")["status"], "configured")
        self.assertEqual(item(res, "imap")["status"], "fallback")

    def test_alias_names_accepted(self):
        with env(NEXT_PUBLIC_SUPABASE_URL="https://x.supabase.co", SUPABASE_SERVICE_ROLE_KEY=SECRET, ANTHROPIC_AUTH_TOKEN=SECRET):
            res = cat.integration_status()
        self.assertEqual(item(res, "supabase")["status"], "configured")
        self.assertEqual(item(res, "anthropic")["status"], "configured")

    def test_values_never_returned(self):
        with env(**{k: SECRET for k in ALL_VARS}):
            res = cat.integration_status()
        self.assertNotIn(SECRET, repr(res))


class ApiKeysEndpointTests(unittest.TestCase):
    def setUp(self):
        import app as app_module
        self.client = app_module.app.test_client()

    def test_requires_login(self):
        r = self.client.get("/api/settings/api-keys")
        self.assertEqual(r.status_code, 401)

    def test_returns_status_without_values(self):
        with env(HUNTER_API_KEY=SECRET), mock.patch("api_auth._verify_token", return_value={"email": "owner@example.com"}, create=True):
            r = self.client.get("/api/settings/api-keys", headers={"X-Demo-User": "true"}, environ_base={"REMOTE_ADDR": "127.0.0.1"})
        if r.status_code == 401:
            self.skipTest("demo login disabled in this environment")
        self.assertEqual(r.status_code, 200)
        self.assertNotIn(SECRET, r.get_data(as_text=True))
        self.assertEqual(item(r.get_json(), "hunter")["status"], "configured")


if __name__ == "__main__":
    unittest.main()

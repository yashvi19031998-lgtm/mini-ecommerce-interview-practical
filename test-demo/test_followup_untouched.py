"""'Not contacted yet' list: new leads with no e-mail sent and no activity logged, grouped by score."""
import unittest
from unittest import mock

import app
import followup_store

AUTH = {"X-Demo-User": "true"}


def lead(lid, score, status="NEW", email_status="PENDING", email="a@b.com", found="2026-11-10 10:00:00"):
    return {"id": lid, "Company Name": f"Co {lid}", "Email": email, "Status": status, "Email Status": email_status,
            "ai_score": score, "intent_score": "", "Source": "Test", "first_seen_at": found, "Mobile Number": "N/A"}


LEADS = [
    lead("L1", "9"),
    lead("L2", "5"),
    lead("L3", "2", email=""),
    lead("L4", "8", email_status="SENT"),           # already e-mailed
    lead("L5", "10"),                                # has a logged call
    lead("L6", "7", status="LOST"),                  # closed
    lead("L7", "", email="N/A"),                     # never scored
    lead("L8", "9", found="2026-11-12 10:00:00"),    # same score as L1, newer
]


class UntouchedLeadsTests(unittest.TestCase):
    def setUp(self):
        self.client = app.app.test_client()
        p1 = mock.patch.object(app, "read_leads", return_value=LEADS)
        p2 = mock.patch.object(followup_store, "_read_all", return_value=[{"lead_id": "L5", "type": "call"}])
        p1.start(); p2.start()
        self.addCleanup(mock.patch.stopall)

    def get(self, q=""):
        r = self.client.get(f"/api/followups/untouched{q}", headers=AUTH)
        return r.status_code, r.get_json()

    def test_only_uncontacted_open_leads_highest_score_first(self):
        code, j = self.get()
        self.assertEqual(code, 200)
        self.assertEqual([i["id"] for i in j["items"]], ["L8", "L1", "L2", "L3", "L7"])
        self.assertEqual(j["counts"], {"all": 5, "high": 2, "medium": 1, "low": 1, "unscored": 1})

    def test_band_filter(self):
        _, j = self.get("?band=high")
        self.assertEqual([i["id"] for i in j["items"]], ["L8", "L1"])
        _, j = self.get("?band=low")
        self.assertEqual([i["id"] for i in j["items"]], ["L3"])

    def test_has_email_filter_and_na_cleanup(self):
        _, j = self.get("?has_email=1")
        self.assertEqual({i["id"] for i in j["items"]}, {"L1", "L2", "L8"})
        _, j = self.get()
        self.assertEqual(next(i for i in j["items"] if i["id"] == "L7")["email"], "")

    def test_bad_band_rejected(self):
        code, j = self.get("?band=everything")
        self.assertEqual(code, 400)
        self.assertFalse(j["success"])


if __name__ == "__main__":
    unittest.main()

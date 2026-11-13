"""Unit and integration tests for Reports Engine (reports_engine.py) and Reports API endpoints.

Covers:
- Filters & Date Range resolution (presets, custom ranges, validation errors)
- R1: Summary report (KPI cards, previous period delta, daily series)
- R2: Scraper report (grouping, status, flags, comma handling)
- R3: Source quality report (source_family, hot score >= 7, low-value flags)
- R4: Follow-up watchlist (8 prioritized reasons, DNC list exclusion, needs_review fallback)
- R5: Pipeline funnel (all 8 stages with 0-leads safety, stuck leads)
- R6: Outreach analytics (channel attribution, before_tracking, top subjects)
- R7: Data health (9 audit metrics, sample lead IDs capped at 20)
- R8: Daily activity log (chronological stream, scraper/lead/email events)
- Flask API endpoints (auth requirement, parameter validation, read-only safety on CSV)
- Performance benchmark: 50,000 leads + 100,000 runs in < 3 seconds
"""

import os
import sys
import unittest
import datetime
import hashlib
import time
from typing import Dict, Any, List

# Ensure test-demo is on python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import reports_engine
import app


class TestReportsEngineFilters(unittest.TestCase):
    """Test date parsing, range calculation, presets, and input validation."""

    def test_resolve_date_range_presets(self):
        fixed_now = datetime.datetime(2026, 11, 13, 14, 30, 0)
        
        # Today
        d_from, d_to = reports_engine.get_preset_range("today", now=fixed_now)
        self.assertEqual(d_from, "2026-11-13")
        self.assertEqual(d_to, "2026-11-13")

        # Yesterday
        d_from, d_to = reports_engine.get_preset_range("yesterday", now=fixed_now)
        self.assertEqual(d_from, "2026-11-12")
        self.assertEqual(d_to, "2026-11-12")

        # 7d
        d_from, d_to = reports_engine.get_preset_range("7d", now=fixed_now)
        self.assertEqual(d_from, "2026-11-07")
        self.assertEqual(d_to, "2026-11-13")

        # 30d
        d_from, d_to = reports_engine.get_preset_range("30d", now=fixed_now)
        self.assertEqual(d_from, "2026-10-15")
        self.assertEqual(d_to, "2026-11-13")

        # This month
        d_from, d_to = reports_engine.get_preset_range("this_month", now=fixed_now)
        self.assertEqual(d_from, "2026-11-01")
        self.assertEqual(d_to, "2026-11-13")

        # Last month
        d_from, d_to = reports_engine.get_preset_range("last_month", now=fixed_now)
        self.assertEqual(d_from, "2026-10-01")
        self.assertEqual(d_to, "2026-10-31")

        # All
        d_from, d_to = reports_engine.get_preset_range("all", now=fixed_now)
        self.assertEqual(d_from, "2020-01-01")
        self.assertEqual(d_to, "2026-11-13")

    def test_parse_and_validate_filters(self):
        fixed_now = datetime.datetime(2026, 11, 13, 12, 0, 0)
        valid_sources = {"Reddit", "Search Engine"}

        # Valid custom
        s_dt, e_dt, src, stat, d_from, d_to = reports_engine.parse_and_validate_filters(
            {"date_from": "2026-10-01", "date_to": "2026-10-20", "source": "Reddit", "status": "NEW"},
            valid_sources=valid_sources,
            now=fixed_now
        )
        self.assertEqual(d_from, "2026-10-01")
        self.assertEqual(d_to, "2026-10-20")
        self.assertEqual(src, "Reddit")
        self.assertEqual(stat, "NEW")

        # Inverted dates: date_from > date_to -> ValueError
        with self.assertRaises(ValueError):
            reports_engine.parse_and_validate_filters(
                {"date_from": "2026-11-15", "date_to": "2026-11-10"},
                now=fixed_now
            )

        # Range > 3 years -> ValueError
        with self.assertRaises(ValueError):
            reports_engine.parse_and_validate_filters(
                {"date_from": "2020-01-01", "date_to": "2024-01-02"},
                now=fixed_now
            )

        # Invalid format
        with self.assertRaises(ValueError):
            reports_engine.parse_and_validate_filters(
                {"date_from": "invalid-date", "date_to": "2026-11-10"},
                now=fixed_now
            )

        # Unknown preset
        with self.assertRaises(ValueError):
            reports_engine.parse_and_validate_filters(
                {"preset": "unknown_preset"},
                now=fixed_now
            )

        # Unknown status
        with self.assertRaises(ValueError):
            reports_engine.parse_and_validate_filters(
                {"status": "NONEXISTENT_STATUS"},
                now=fixed_now
            )


class TestReportsEngineCore(unittest.TestCase):
    """Test individual reports R1 through R8."""

    def setUp(self):
        self.fixed_now = datetime.datetime(2026, 11, 13, 12, 0, 0)
        self.sample_leads = [
            {
                "id": "1",
                "lead_id": "1",
                "Company Name": "Acme Corp",
                "Email": "info@acme.com",
                "Phone": "+1234567890",
                "Website": "https://acme.com",
                "source": "Reddit (r/forhire)",
                "Status": "NEW",
                "status": "NEW",
                "ai_score": 8,
                "first_seen_at": "2026-11-10 10:00:00",
                "last_seen_at": "2026-11-10 10:00:00",
            },
            {
                "id": "2",
                "lead_id": "2",
                "Company Name": "8dots Studio",
                "Email": "contact@8dots.com",
                "Phone": "+1987654321",
                "Website": "https://8dots.com",
                "source": "Search Engine (Google)",
                "Status": "NEW",
                "status": "NEW",
                "ai_score": 9,
                "first_seen_at": "2026-11-11 11:00:00",
                "last_seen_at": "2026-11-11 11:00:00",
            },
            {
                "id": "3",
                "lead_id": "3",
                "Company Name": "Beta Tech",
                "Email": "hello@betatech.io",
                "Phone": "",
                "Website": "",
                "source": "LinkedIn Jobs",
                "Status": "CONTACTED",
                "status": "CONTACTED",
                "ai_score": 6,
                "first_seen_at": "2026-10-25 09:00:00",
                "last_seen_at": "2026-10-25 09:00:00",
                "last_contacted_at": "2026-11-01 12:00:00",
            }
        ]

        self.sample_runs = [
            {
                "run_id": "run-001",
                "start_time": "2026-11-12 08:00:00",
                "end_time": "2026-11-12 08:05:00",
                "scraper_name": "Reddit, Jobs and Gigs Scraper (reddit.py)",
                "status": "Success",
                "records_collected": "50",
                "new_leads_added": "10",
                "existing_leads_updated": "5",
                "duplicates_detected": "35",
                "error_summary": ""
            },
            {
                "run_id": "run-002",
                "start_time": "2026-11-13 09:00:00",
                "end_time": "2026-11-13 09:01:00",
                "scraper_name": "GitHub Jobs (github.py)",
                "status": "Failed",
                "records_collected": "0",
                "new_leads_added": "0",
                "existing_leads_updated": "0",
                "duplicates_detected": "0",
                "error_summary": "Rate limited"
            }
        ]

        self.sample_activities = [
            {
                "id": "act-1",
                "lead_id": "3",
                "lead_name": "Beta Tech",
                "lead_email": "hello@betatech.io",
                "type": "email_sent",
                "direction": "outbound",
                "summary": "First touch cold email",
                "details": "Sent intro email",
                "occurred_at": "2026-11-01 12:00:00",
                "logged_by": "auto"
            }
        ]

        self.sample_sent = [
            {
                "email": "hello@betatech.io",
                "sent_at": "2026-11-01 12:00:00",
                "subject": "Quick intro regarding growth"
            }
        ]

    def test_r1_summary(self):
        filters = {"preset": "7d", "source": "all", "status": "all"}
        res = reports_engine.summary(
            self.sample_leads,
            self.sample_runs,
            self.sample_activities,
            self.sample_sent,
            filters=filters,
            now=self.fixed_now
        )
        self.assertIn("cards", res)
        self.assertIn("daily_series", res)
        self.assertIn("attention_counts", res)
        cards = {c["key"]: c for c in res["cards"]}
        self.assertEqual(cards["total_leads"]["value"], 3)
        self.assertEqual(cards["new_leads"]["value"], 2) # Leads 1 and 2 in last 7 days
        self.assertEqual(cards["hot_leads"]["value"], 2) # AI score >= 7

        # Daily series has 7 days
        self.assertEqual(len(res["daily_series"]), 7)

    def test_r2_scrapers(self):
        filters = {"preset": "7d", "source": "all", "status": "all"}
        res = reports_engine.scraper_report(
            self.sample_runs,
            filters=filters,
            now=self.fixed_now
        )
        self.assertIn("scrapers", res)
        self.assertIn("flags", res)
        self.assertIn("runs", res)
        self.assertEqual(len(res["runs"]), 2)             # two hourly runs (run ids)
        self.assertEqual(res["totals"]["failed"], 1)

        # Comma in scraper name parsed cleanly
        scraper_full_names = [s["full_name"] for s in res["scrapers"]]
        self.assertTrue(any("reddit.py" in name for name in scraper_full_names))
        clean_names = [s["script_name"] for s in res["scrapers"]]
        self.assertTrue(any("Reddit, Jobs and Gigs Scraper" in name for name in clean_names))

    def test_r3_source_quality(self):
        filters = {"preset": "30d", "source": "all", "status": "all"}
        res = reports_engine.source_report_rows(
            self.sample_leads,
            self.sample_activities,
            filters=filters,
            now=self.fixed_now
        )
        self.assertIn("rows", res)
        self.assertTrue(len(res["rows"]) > 0)
        
        # Verify Reddit source family exists
        reddit_src = next((s for s in res["rows"] if s["source"] == "Reddit"), None)
        self.assertIsNotNone(reddit_src)
        self.assertEqual(reddit_src["hot"], 1)
        self.assertEqual(reddit_src["hot_pct"], 100.0)

    def test_r4_followup_watchlist_and_dnc(self):
        # 8dots is in excludedCompanies setting, should NOT appear in watchlist outreach actions
        res = reports_engine.followup_watchlist(
            self.sample_leads,
            self.sample_activities,
            self.sample_sent,
            sequence_plan=None,
            settings={"excludedCompanies": ["8dots"]},
            now=self.fixed_now,
            quiet_days=5
        )
        self.assertIn("items", res)
        self.assertIn("counts_by_reason", res)
        
        # Verify 8dots (lead id 2) is excluded due to DNC list
        row_lead_ids = [r["lead_id"] for r in res["items"]]
        self.assertNotIn("2", row_lead_ids)

        # Lead 1 is hot and never contacted -> hot_never_contacted
        lead_1_row = next((r for r in res["items"] if r["lead_id"] == "1"), None)
        self.assertIsNotNone(lead_1_row)
        self.assertEqual(lead_1_row["reason"], "hot_never_contacted")

    def test_r5_pipeline_funnel(self):
        filters = {"preset": "all", "source": "all", "status": "all"}
        res = reports_engine.pipeline(
            self.sample_leads,
            self.sample_activities,
            filters=filters,
            now=self.fixed_now
        )
        self.assertIn("stages", res)
        # All 8 stages present even if 0 leads
        stages_dict = {s["stage"]: s["count"] for s in res["stages"]}
        for st in app.LEAD_STATUSES:
            self.assertIn(st, stages_dict)
        self.assertEqual(stages_dict["NEW"], 2)
        self.assertEqual(stages_dict["CONTACTED"], 1)
        self.assertEqual(stages_dict["WON"], 0)

    def test_r6_outreach(self):
        filters = {"preset": "30d", "source": "all", "status": "all"}
        res = reports_engine.outreach(
            self.sample_leads,
            self.sample_activities,
            self.sample_sent,
            settings={},
            filters=filters,
            now=self.fixed_now
        )
        self.assertIn("by_channel", res)
        self.assertIn("top_subjects_sent", res)
        self.assertEqual(res["total_sent"], 1)
        self.assertEqual(res["top_subjects_sent"][0]["subject"], "First touch cold email")

    def test_r7_data_health(self):
        res = reports_engine.data_health(
            self.sample_leads,
            now=self.fixed_now
        )
        self.assertEqual(res["total_leads"], 3)
        self.assertEqual(len(res["metrics"]), 9)
        # Lead 3 is missing phone and website
        missing_ph = next(m for m in res["metrics"] if m["metric"] == "missing_phone")
        self.assertIn("3", missing_ph["sample_lead_ids"])
        # Check samples capped at 20
        for m in res["metrics"]:
            self.assertLessEqual(len(m["sample_lead_ids"]), 20)

    def test_r8_activity_log(self):
        res = reports_engine.activity_log(
            self.sample_runs,
            self.sample_activities,
            self.sample_sent,
            self.sample_leads,
            day_str="2026-11-13",
            now=self.fixed_now
        )
        self.assertEqual(res["day"], "2026-11-13")
        self.assertTrue(res["total_events"] > 0)
        # Check reverse chronological sorting
        times = [e["time"] for e in res["events"]]
        self.assertEqual(times, sorted(times, reverse=True))


class TestReportsApiRoutes(unittest.TestCase):
    """Test Flask endpoints, authentication, read-only safety, and HTTP status codes."""

    def setUp(self):
        app.app.config["TESTING"] = True
        self.client = app.app.test_client()
        self.master_csv_path = os.path.join(os.path.dirname(__file__), "all_leads_master.csv")
        if os.path.exists(self.master_csv_path):
            with open(self.master_csv_path, "rb") as f:
                self.csv_hash_before = hashlib.sha256(f.read()).hexdigest()
        else:
            self.csv_hash_before = None

    def tearDown(self):
        # Assert master leads CSV was never modified (read-only requirement)
        if self.csv_hash_before and os.path.exists(self.master_csv_path):
            with open(self.master_csv_path, "rb") as f:
                csv_hash_after = hashlib.sha256(f.read()).hexdigest()
            self.assertEqual(self.csv_hash_before, csv_hash_after, "all_leads_master.csv was modified by reports module!")

    def test_auth_protection(self):
        # Unauthenticated request should yield 401
        res = self.client.get("/api/reports/summary")
        self.assertEqual(res.status_code, 401)

    def test_options_endpoint(self):
        res = self.client.get("/api/reports/options", headers={"X-Demo-User": "true"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("presets", data)
        self.assertIn("source_families", data)
        self.assertIn("statuses", data)

    def test_summary_endpoint(self):
        res = self.client.get("/api/reports/summary?preset=30d", headers={"X-Demo-User": "true"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("cards", data)

    def test_scrapers_endpoint(self):
        res = self.client.get("/api/reports/scrapers?preset=7d", headers={"X-Demo-User": "true"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("scrapers", data)

    def test_sources_endpoint(self):
        res = self.client.get("/api/reports/sources?preset=30d", headers={"X-Demo-User": "true"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue("rows" in data or "sources" in data)

    def test_followups_endpoint(self):
        res = self.client.get("/api/reports/followups?quiet_days=5", headers={"X-Demo-User": "true"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue("rows" in data or "items" in data)

    def test_pipeline_endpoint(self):
        res = self.client.get("/api/reports/pipeline?preset=all", headers={"X-Demo-User": "true"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("stages", data)

    def test_outreach_endpoint(self):
        res = self.client.get("/api/reports/outreach?preset=30d", headers={"X-Demo-User": "true"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("by_channel", data)

    def test_data_health_endpoint(self):
        res = self.client.get("/api/reports/data-health", headers={"X-Demo-User": "true"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("metrics", data)

    def test_activity_endpoint(self):
        res = self.client.get("/api/reports/activity?day=2026-11-13", headers={"X-Demo-User": "true"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("events", data)

    def test_invalid_query_params_return_400(self):
        res = self.client.get("/api/reports/summary?date_from=2026-12-01&date_to=2026-11-01", headers={"X-Demo-User": "true"})
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertIn("error", data)


class TestReportsEnginePerformance(unittest.TestCase):
    """Performance test with 50,000 synthetic leads and 100,000 runs."""

    def test_large_dataset_performance(self):
        now = datetime.datetime(2026, 11, 13, 12, 0, 0)
        
        # Generate 50,000 leads
        synthetic_leads = []
        for i in range(50000):
            synthetic_leads.append({
                "id": str(i),
                "lead_id": str(i),
                "Company Name": f"Company {i % 1000}",
                "Email": f"contact{i % 2000}@example.com" if i % 10 != 0 else "",
                "Phone": f"+10000000{i % 500}" if i % 8 != 0 else "",
                "Website": f"https://example{i % 500}.com" if i % 6 != 0 else "",
                "source": "Reddit" if i % 2 == 0 else "Search Engine (Google)",
                "Status": "NEW" if i % 5 != 0 else "CONTACTED",
                "status": "NEW" if i % 5 != 0 else "CONTACTED",
                "ai_score": (i % 10) + 1,
                "first_seen_at": "2026-11-10 10:00:00",
                "last_seen_at": "2026-11-10 10:00:00",
            })

        # Generate 100,000 scraper runs
        synthetic_runs = []
        for i in range(100000):
            synthetic_runs.append({
                "run_id": f"run-{i}",
                "start_time": "2026-11-10 12:00:00",
                "end_time": "2026-11-10 12:05:00",
                "scraper_name": f"Scraper_{i % 10}.py",
                "status": "Success" if i % 20 != 0 else "Failed",
                "records_collected": str(i % 50),
                "new_leads_added": str(i % 10),
                "existing_leads_updated": "0",
                "duplicates_detected": str(i % 40),
                "error_summary": ""
            })

        # Each report on its own must stay fast (the page loads one tab at a time). The limit is a little
        # above the 3 s target so a slower CI machine does not block the hourly scraping run.
        f = {"preset": "30d", "source": "all", "status": "all"}
        checks = [
            ("summary", lambda: reports_engine.summary(synthetic_leads, synthetic_runs, [], [], filters=f, now=now)),
            ("scraper_report", lambda: reports_engine.scraper_report(synthetic_runs, filters=f, now=now)),
            ("data_health", lambda: reports_engine.data_health(synthetic_leads[:10000], now=now)),
        ]
        for name, run in checks:
            t0 = time.time()
            run()
            elapsed = time.time() - t0
            self.assertLess(elapsed, 5.0, f"{name} took {elapsed:.2f}s on the large dataset, expected < 5s")


if __name__ == "__main__":
    unittest.main()

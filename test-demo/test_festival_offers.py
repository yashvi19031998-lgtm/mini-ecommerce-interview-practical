"""
Unit tests for Festival & Digital Media Offers Engine
"""

import unittest
import os
import shutil
import tempfile
import settings_manager
import festival_offers_engine as engine
import cron_job_festival_dispatcher as cron

class TestFestivalOffersEngine(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.orig_data_dir = engine.DATA_DIR
        self.orig_clients_file = engine.CLIENTS_FILE
        self.orig_schedule_file = engine.SCHEDULE_FILE

        engine.DATA_DIR = self.test_dir
        engine.CLIENTS_FILE = os.path.join(self.test_dir, "test_clients.json")
        engine.SCHEDULE_FILE = os.path.join(self.test_dir, "test_schedules.json")
        engine._ensure_data_files()

    def tearDown(self):
        engine.DATA_DIR = self.orig_data_dir
        engine.CLIENTS_FILE = self.orig_clients_file
        engine.SCHEDULE_FILE = self.orig_schedule_file
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_offers_structure(self):
        offers = engine.OFFERS
        self.assertEqual(len(offers), 3)
        pack_500 = next((o for o in offers if o["id"] == "fest_10_pack"), None)
        self.assertIsNotNone(pack_500)
        self.assertEqual(pack_500["price_inr"], 500)

        pack_1000 = next((o for o in offers if o["id"] == "reels_3_pack"), None)
        self.assertIsNotNone(pack_1000)
        self.assertEqual(pack_1000["price_inr"], 1000)

        pack_1299 = next((o for o in offers if o["id"] == "combo_festive_booster"), None)
        self.assertIsNotNone(pack_1299)
        self.assertEqual(pack_1299["price_inr"], 1299)

    def test_festival_calendar(self):
        calendar = engine.FESTIVAL_CALENDAR
        self.assertGreaterEqual(len(calendar), 10)
        diwali = next((f for f in calendar if "diwali" in f["id"]), None)
        self.assertIsNotNone(diwali)
        self.assertIn("દિવાળી", diwali["gujarati_name"])

    def test_pitch_generator(self):
        sample_lead = {
            "company_name": "Radhe Krishna Sweets",
            "phone": "+91 9876543210",
            "email": "contact@radhekrishna.com"
        }
        pitch = engine.generate_offer_pitch(sample_lead)
        self.assertEqual(pitch["lead_name"], "Radhe Krishna Sweets")
        self.assertIn("₹500", pitch["whatsapp_pitch_gu"])
        self.assertIn("FREE", pitch["whatsapp_pitch_gu"])
        self.assertIn("Radhe Krishna Sweets", pitch["whatsapp_pitch_gu"])
        self.assertIn("https://wa.me/919876543210", pitch["whatsapp_url"])
        self.assertIn("Radhe Krishna Sweets", pitch["email_subject"])
        self.assertIn("YES", pitch["email_body"])
        self.assertIn("followups", pitch)
        for day in ("day1", "day3", "day6"):
            for lang in ("gu", "gujlish", "en"):
                self.assertTrue(pitch["followups"][day][lang])
                self.assertIn("https://wa.me/919876543210", pitch["followups"][day][f"wa_url_{lang}"])
        self.assertTrue(pitch["followups"]["day3"]["note"])          # attach a sample picture
        self.assertNotIn("Sweets ji", pitch["whatsapp_pitch_gujlish"])  # no "ji" after a shop name
        self.assertNotIn("₹1,000", pitch["email_body"])                # one offer per mail
        self.assertEqual(pitch["email_body"].count("FREE"), 1)
        with_owner = engine.generate_offer_pitch({**sample_lead, "contact_name": "Ramesh"})
        self.assertIn("Ramesh ji", with_owner["whatsapp_pitch_gujlish"])

    def test_client_crud(self):
        client_data = {
            "business_name": "Amdavad Fitness Hub",
            "owner_name": "Vikas Patel",
            "phone": "+91 9909012345",
            "email": "vikas@fitgym.com",
            "tagline": "Transform Your Life",
            "address": "Navrangpura, Ahmedabad",
            "pack": "fest_10_pack",
            "paid_amount": 500
        }
        saved = engine.save_client(client_data)
        self.assertTrue(saved["id"].startswith("fc_"))
        self.assertEqual(saved["status"], "PAID_ACTIVE")

        clients = engine.get_all_clients()
        self.assertEqual(len(clients), 1)
        self.assertEqual(clients[0]["business_name"], "Amdavad Fitness Hub")

        fetched = engine.get_client_by_id(saved["id"])
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched["owner_name"], "Vikas Patel")

    def test_generate_svg_creative(self):
        client = {
            "business_name": "Apex Dental Clinic",
            "tagline": "Painless Dentistry & Smiles",
            "phone": "+91 9825098250",
            "address": "Bopal, Ahmedabad",
            "website": "www.apexdental.in"
        }
        svg = engine.generate_festival_creative_svg(client, "diwali_new_year")
        self.assertIn("<svg", svg)
        self.assertIn("Apex Dental Clinic", svg)
        self.assertIn("Painless Dentistry & Smiles", svg)
        self.assertIn("+91 9825098250", svg)
        self.assertIn("Bopal, Ahmedabad", svg)
        self.assertIn("દિવાળી અને નૂતન વર્ષ", svg)
        self.assertIn("</svg>", svg)

    def test_schedule_and_cron_dispatch(self):
        client = engine.save_client({
            "business_name": "Gokul Dairy Parlour",
            "phone": "+91 9106060400",
            "address": "Maninagar, Ahmedabad",
            "status": "PAID_ACTIVE",
            "paid_amount": 500
        })
        from datetime import date
        today_str = date.today().isoformat()
        res = engine.schedule_festival_dispatch(client["id"], "holi_dhuleti", today_str)
        self.assertTrue(res["success"])
        schedules = engine.get_all_schedules()
        self.assertEqual(len(schedules), 1)
        self.assertEqual(schedules[0]["status"], "SCHEDULED")

        dispatched = cron.run_festival_daily_check()
        self.assertEqual(dispatched, 1)

        updated_schedules = engine.get_all_schedules()
        self.assertEqual(updated_schedules[0]["status"], "DISPATCHED")

    def test_stats(self):
        stats = engine.get_stats()
        self.assertEqual(stats["total_clients"], 0)
        self.assertEqual(stats["total_revenue_inr"], 0)
        self.assertGreaterEqual(stats["upcoming_festivals_count"], 10)

    def test_bde_strategy_loaded(self):
        strat = engine.get_bde_strategy()
        self.assertIn("Trojan Horse", strat.get("core_philosophy", {}).get("strategy_name", ""))
        self.assertEqual(len(strat.get("target_market_tiers", [])), 3)

    def test_it_company_shield(self):
        # Strict IT company exclusion test
        self.assertTrue(settings_manager.is_it_company("TatvaSoft Technologies")[0])
        self.assertTrue(settings_manager.is_it_company("Cybercom Creation Infotech")[0])
        self.assertTrue(settings_manager.is_it_company("Simform Solutions Pvt Ltd")[0])
        self.assertTrue(settings_manager.is_it_company("Citrusbug Technolabs")[0])
        self.assertTrue(settings_manager.is_it_company("Web Development Agency")[0])
        self.assertTrue(settings_manager.is_it_company("Fake Co", email="info@infolabz.in")[0])
        self.assertTrue(settings_manager.is_it_company("Fake Co", website="https://instanceit.com")[0])
        self.assertTrue(settings_manager.is_it_company("Fake Co", website="https://voygr.tech")[0])

        # Non-IT local SME businesses must NEVER be blocked
        self.assertFalse(settings_manager.is_it_company("Gokul Dairy Parlour")[0])
        self.assertFalse(settings_manager.is_it_company("Radhe Krishna Sweets")[0])
        self.assertFalse(settings_manager.is_it_company("Shreeji Jewellers")[0])
        self.assertFalse(settings_manager.is_it_company("Dr. Mehta Dental Clinic")[0])
        self.assertFalse(settings_manager.is_it_company("Amdavad Fitness Gym")[0])
        self.assertFalse(settings_manager.is_it_company("Apex Packaging Industries")[0])
        self.assertFalse(settings_manager.is_it_company("Shreeji Engineering Works")[0])
        self.assertFalse(settings_manager.is_it_company("Shree Packaging Solutions")[0])
        self.assertFalse(settings_manager.is_it_company("Patel Tax Consultancy")[0])
        self.assertFalse(settings_manager.is_it_company("Kapda Store", email="hi@kapda.myshopify.com")[0])

    def test_it_shield_is_off_for_the_main_outreach(self):
        # The main outreach sells developers to companies, many of them tech companies.
        self.assertFalse(settings_manager.DEFAULT_SETTINGS["excludeITCompanies"])
        self.assertFalse(settings_manager.is_company_excluded("TatvaSoft Technologies", settings={"excludedCompanies": ["8dots"]})[0])
        self.assertTrue(settings_manager.is_company_excluded("TatvaSoft Technologies", settings={"excludeITCompanies": True})[0])

    def test_sme_finder_rejects_other_businesses_websites(self):
        import cron_job_sme_outreach as sme
        # wrong sites a search engine returned in a live test (20 Nov 2026)
        self.assertFalse(sme.site_belongs_to("National Dental Supply Co.", "https://nationalinsurance.nic.co.in/"))
        self.assertFalse(sme.site_belongs_to("Shrey Aesthetica Dental", "https://www.shreysports.in/"))
        self.assertFalse(sme.site_belongs_to("Step 2 Well", "https://step.thehindu.com/"))
        self.assertFalse(sme.site_belongs_to("Universal Gym & Fitness Centre", "https://www.universalorlando.com/"))
        self.assertFalse(sme.site_belongs_to("Arti Farsan & Sweet Mart", "https://arti.org.in/"))
        self.assertFalse(sme.site_belongs_to("Vijay Sweets", "https://vijay.com/"))
        self.assertTrue(sme.site_belongs_to("Packwell Wood Works", "https://www.packwell.com/"))
        self.assertTrue(sme.site_belongs_to("Kanan Furniture Company", "https://www.kananfurniturecompany.com/"))
        self.assertTrue(sme.site_belongs_to("Akash Dental Poly Clinic", "https://akashdentalclinic.com/"))
        self.assertTrue(sme.site_belongs_to("Shreeji Jewellers", "https://www.shreejijewellers.co.in"))
        self.assertTrue(sme.email_belongs_to("info@akashdentalclinic.com", "https://akashdentalclinic.com"))
        self.assertTrue(sme.email_belongs_to("akashdental@gmail.com", "https://akashdentalclinic.com"))
        self.assertFalse(sme.email_belongs_to("hello@webdesignerxyz.com", "https://akashdentalclinic.com"))
        city, niches = sme.todays_search()
        self.assertIn(city, sme.CITIES)
        self.assertEqual(len(niches), sme.NICHES_PER_RUN)

    def test_sme_outreach_picks_only_local_non_it_leads(self):
        import tempfile, csv as _csv, os as _os
        from unittest.mock import patch
        import cron_job_sme_outreach as sme
        rows = [
            {"company_name": "Shreeji Jewellers", "email": "a@shreeji.in", "source": "Google Maps (Jewellers in Ahmedabad)", "location": "CG Road, Ahmedabad", "lead_type": "Registered Company"},
            {"company_name": "Pune Sweets", "email": "b@punesweets.in", "source": "Google Maps (Sweets in Pune)", "location": "Anand Park, Pune", "lead_type": ""},
            {"company_name": "Code Infotech", "email": "c@codeinfo.in", "source": "Google Maps (Software Development Company in Surat)", "location": "Surat", "lead_type": ""},
            {"company_name": "Acme Inc", "email": "d@acme.com", "source": "Hacker News (Who is hiring?)", "location": "Ahmedabad", "lead_type": "HN Hiring Post"},
            {"company_name": "Already Mailed", "email": "e@mailed.in", "source": "IndiaMART", "location": "Rajkot", "lead_type": ""},
            # a web search gave another company's site and address: never mailed
            {"company_name": "Surya Chavana & Sweet Mart", "email": "consumercare@surya.in", "website": "https://surya.co.in/",
             "source": "Indian Directories (Sulekha)", "location": "Maninagar, Ahmedabad", "lead_type": ""},
        ]
        for r in rows:
            r.setdefault("website", "")
        path = _os.path.join(tempfile.mkdtemp(), "leads.csv")
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = _csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        with patch.object(sme, "LEADS_MASTER", path), \
             patch.object(sme.email_service, "get_already_sent_emails", return_value={"e@mailed.in"}):
            got, skipped = sme.candidate_sme_leads("gujarat")
        self.assertEqual([c["company_name"] for c in got], ["Shreeji Jewellers"])
        self.assertEqual(skipped["already_mailed"], 1)
        self.assertEqual(skipped["it_company"], 1)
        self.assertEqual(skipped["email_not_theirs"], 1)

if __name__ == "__main__":
    unittest.main()

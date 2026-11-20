"""
Unit tests for Festival & Digital Media Offers Engine
"""

import unittest
import os
import shutil
import tempfile
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
        self.assertIn("₹1,000", pitch["whatsapp_pitch_gu"])
        self.assertIn("Radhe Krishna Sweets", pitch["whatsapp_pitch_gu"])
        self.assertIn("https://wa.me/919876543210", pitch["whatsapp_url"])
        self.assertIn("Radhe Krishna Sweets", pitch["email_subject"])
        self.assertIn("YES", pitch["email_body"])

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

if __name__ == "__main__":
    unittest.main()

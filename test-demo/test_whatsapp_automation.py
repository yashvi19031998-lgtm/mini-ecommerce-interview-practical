"""Unit tests for WhatsApp Meta Cloud API Automation"""

import unittest
from app import app
from whatsapp_state import get_state, save_state
from whatsapp_webhook import META_VERIFY_TOKEN
from whatsapp_gemini import get_whatsapp_reply
import whatsapp_service as ws


class TestWhatsAppAutomation(unittest.TestCase):

    def setUp(self):
        self.client = app.test_client()

    def test_webhook_get_verification_success(self):
        resp = self.client.get(
            f"/webhook?hub.mode=subscribe&hub.verify_token={META_VERIFY_TOKEN}&hub.challenge=test_challenge_12345"
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_data(as_text=True), "test_challenge_12345")

    def test_webhook_get_verification_invalid_token(self):
        resp = self.client.get(
            "/webhook?hub.mode=subscribe&hub.verify_token=wrong_token&hub.challenge=12345"
        )
        self.assertEqual(resp.status_code, 403)

    def test_webhook_post_incoming_text_hi(self):
        payload = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {
                                        "from": "919999988888",
                                        "type": "text",
                                        "text": {"body": "Hi Sangeeta Infotech"}
                                    }
                                ]
                            }
                        }
                    ]
                }
            ]
        }
        resp = self.client.post("/webhook", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data.get("status"), "processed")
        self.assertEqual(data.get("messages_handled"), 1)

    def test_webhook_post_interactive_hire_developers(self):
        payload = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {
                                        "from": "919999988888",
                                        "type": "interactive",
                                        "interactive": {
                                            "type": "list_reply",
                                            "list_reply": {"id": "hire_developers"}
                                        }
                                    }
                                ]
                            }
                        }
                    ]
                }
            ]
        }
        resp = self.client.post("/webhook", json=payload)
        self.assertEqual(resp.status_code, 200)
        state = get_state("919999988888")
        self.assertEqual(state.get("stage"), "awaiting_requirement")

    def test_webhook_post_requirement_submission_qualifies(self):
        save_state("919999988888", {"stage": "awaiting_requirement", "requirement": ""})
        payload = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {
                                        "from": "919999988888",
                                        "type": "text",
                                        "text": {"body": "We need a Laravel backend with Next.js web portal"}
                                    }
                                ]
                            }
                        }
                    ]
                }
            ]
        }
        resp = self.client.post("/webhook", json=payload)
        self.assertEqual(resp.status_code, 200)
        state = get_state("919999988888")
        self.assertEqual(state.get("stage"), "qualified")
        self.assertIn("Laravel", state.get("requirement", ""))

    def test_whatsapp_gemini_fallback(self):
        reply = get_whatsapp_reply("What is your hourly rate for dedicated developers?", {})
        self.assertIn("₹450", reply)

    def test_whatsapp_service_payload_simulation(self):
        res = ws.send_text("919106060400", "Test message")
        self.assertIn(res.get("status"), ["dry_run", "error", "success"])


if __name__ == "__main__":
    unittest.main()

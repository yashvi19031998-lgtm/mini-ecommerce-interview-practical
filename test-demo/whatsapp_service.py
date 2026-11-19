"""
WhatsApp Meta Cloud API Service
===============================
Provides outbound messaging, interactive lists, reply buttons, and hot lead alerts
via the official Meta WhatsApp Cloud API (v23.0).

Compliance:
- User-initiated messages enter a 24-hour free service window.
- Respects Meta Cloud API schema for text and interactive payloads.
"""

import os
import json
import logging
from typing import Dict, Any, Optional

try:
    import requests
except ImportError:
    requests = None

logger = logging.getLogger("whatsapp_service")

META_API_VERSION = os.getenv("META_API_VERSION", "v23.0")
META_PHONE_NUMBER_ID = os.getenv("META_PHONE_NUMBER_ID", "").strip()
META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN", "").strip()
ADMIN_WHATSAPP_NUMBER = os.getenv("ADMIN_WHATSAPP_NUMBER", "919106060400").strip()
ADMIN_TEMPLATE_NAME = os.getenv("ADMIN_TEMPLATE_NAME", "hot_lead_alert").strip()
CALENDLY_LINK = os.getenv("CALENDLY_LINK", "https://calendly.com/sangeetainfotech/15min").strip()
GOOGLE_MEET_LINK = os.getenv("GOOGLE_MEET_LINK", "https://meet.google.com").strip()

API_URL = f"https://graph.facebook.com/{META_API_VERSION}/{META_PHONE_NUMBER_ID}/messages" if META_PHONE_NUMBER_ID else ""
HEADERS = {
    "Authorization": f"Bearer {META_ACCESS_TOKEN}",
    "Content-Type": "application/json"
}


def send_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Sends payload to Meta Cloud API. If tokens missing or testing, logs safely."""
    if not META_ACCESS_TOKEN or not META_PHONE_NUMBER_ID or not requests:
        # Mock / Dry-run mode for local dev or tests
        return {
            "status": "dry_run",
            "message": "Meta Cloud API credentials not configured; payload simulated",
            "payload": payload
        }

    try:
        url = f"https://graph.facebook.com/{META_API_VERSION}/{META_PHONE_NUMBER_ID}/messages"
        resp = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {META_ACCESS_TOKEN}",
                "Content-Type": "application/json"
            },
            json=payload,
            timeout=15
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error(f"WhatsApp Cloud API send failed: {e}")
        return {"status": "error", "error": str(e)}


def send_text(to: str, body: str) -> Dict[str, Any]:
    """Sends a clean text message to the recipient."""
    clean_to = to.replace("+", "").strip()
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": clean_to,
        "type": "text",
        "text": {
            "preview_url": True,
            "body": body
        }
    }
    return send_payload(payload)


def send_main_menu(to: str) -> Dict[str, Any]:
    """Sends the official WhatsApp Interactive List main menu."""
    clean_to = to.replace("+", "").strip()
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": clean_to,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "header": {
                "type": "text",
                "text": "Sangeeta Infotech"
            },
            "body": {
                "text": (
                    "Welcome to *Sangeeta Infotech* 🚀\n\n"
                    "We provide dedicated software developers, web & mobile engineering, "
                    "CRM integrations, and website maintenance starting at *₹450/- INR / hour*."
                )
            },
            "footer": {
                "text": "Choose an option below to continue"
            },
            "action": {
                "button": "View Services",
                "sections": [
                    {
                        "title": "Our Core Services",
                        "rows": [
                            {
                                "id": "hire_developers",
                                "title": "Hire Developers (₹450/hr)",
                                "description": "Laravel, Next.js, Node, Flutter, PHP"
                            },
                            {
                                "id": "website_maintenance",
                                "title": "Website Maintenance",
                                "description": "Speed fixes, AMC, security updates"
                            },
                            {
                                "id": "portfolio",
                                "title": "View Portfolio",
                                "description": "80+ completed client projects"
                            },
                            {
                                "id": "book_call",
                                "title": "Book 10-Min Call",
                                "description": "Schedule a quick technical chat"
                            }
                        ]
                    }
                ]
            }
        }
    }
    return send_payload(payload)


def send_meeting_options(to: str) -> Dict[str, Any]:
    """Sends WhatsApp Interactive Reply Buttons for scheduling."""
    clean_to = to.replace("+", "").strip()
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": clean_to,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {
                "text": (
                    "Great! Would you like to schedule a quick 10-minute introductory call?\n\n"
                    "Pick a convenient option below:"
                )
            },
            "action": {
                "buttons": [
                    {
                        "type": "reply",
                        "reply": {
                            "id": "calendly",
                            "title": "Book via Calendly"
                        }
                    },
                    {
                        "type": "reply",
                        "reply": {
                            "id": "google_meet",
                            "title": "Join Google Meet"
                        }
                    },
                    {
                        "type": "reply",
                        "reply": {
                            "id": "main_menu",
                            "title": "Main Menu"
                        }
                    }
                ]
            }
        }
    }
    return send_payload(payload)


def send_admin_hot_lead_alert(sender: str, requirement: str, source: str = "WhatsApp inbound enquiry") -> Dict[str, Any]:
    """Sends a notification template to the admin number (+91 9106060400)."""
    clean_admin = ADMIN_WHATSAPP_NUMBER.replace("+", "").strip()
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": clean_admin,
        "type": "template",
        "template": {
            "name": ADMIN_TEMPLATE_NAME,
            "language": {
                "code": "en"
            },
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": sender},
                        {"type": "text", "text": source},
                        {"type": "text", "text": requirement[:900]}
                    ]
                }
            ]
        }
    }
    return send_payload(payload)

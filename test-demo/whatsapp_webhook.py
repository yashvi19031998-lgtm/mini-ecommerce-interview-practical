"""
WhatsApp Webhook Controller
===========================
Processes incoming Meta WhatsApp Cloud API webhooks (GET verification & POST message dispatcher).
"""

import os
import logging
from typing import Dict, Any, Tuple
from flask import Request, jsonify

from whatsapp_state import get_state, save_state
import whatsapp_service as ws
from whatsapp_gemini import get_whatsapp_reply

logger = logging.getLogger("whatsapp_webhook")

META_VERIFY_TOKEN = os.getenv("META_VERIFY_TOKEN", "sangeeta_infotech_verify_token_2026").strip()
CALENDLY_LINK = os.getenv("CALENDLY_LINK", "https://calendly.com/sangeetainfotech/15min").strip()
GOOGLE_MEET_LINK = os.getenv("GOOGLE_MEET_LINK", "https://meet.google.com").strip()


def verify_meta_webhook(req: Request) -> Tuple[Any, int]:
    """Handles GET verification from Meta Cloud API."""
    mode = req.args.get("hub.mode")
    token = req.args.get("hub.verify_token")
    challenge = req.args.get("hub.challenge")

    if mode == "subscribe" and token == META_VERIFY_TOKEN:
        return challenge, 200
    return "Forbidden", 403


def process_webhook_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Dispatches incoming WhatsApp events from Meta payload."""
    entries = payload.get("entry", [])
    processed_count = 0

    for entry in entries:
        for change in entry.get("changes", []):
            val = change.get("value", {})
            messages = val.get("messages", [])
            for msg in messages:
                _handle_single_message(msg)
                processed_count += 1

    return {"status": "processed", "messages_handled": processed_count}


def _handle_single_message(message: Dict[str, Any]):
    sender = message.get("from")
    msg_type = message.get("type")
    if not sender:
        return

    state = get_state(sender)

    if msg_type == "text":
        user_text = (message.get("text") or {}).get("body", "").strip()
        _handle_text_event(sender, user_text, state)
    elif msg_type == "interactive":
        _handle_interactive_event(sender, message, state)
    else:
        ws.send_text(
            sender,
            "Thanks for connecting with *Sangeeta Infotech*. Please select a service option below:"
        )
        ws.send_main_menu(sender)


def _handle_text_event(sender: str, text: str, state: Dict[str, Any]):
    normalized = text.lower().strip()

    # Main menu trigger words
    if any(k == normalized or k in normalized for k in ["menu", "start", "hi", "hello", "namaste", "kem cho"]):
        ws.send_main_menu(sender)
        return

    # Check if we were waiting for requirement details
    if state.get("stage") == "awaiting_requirement":
        state["requirement"] = text
        state["stage"] = "qualified"
        save_state(sender, state)

        ws.send_text(
            sender,
            "Thank you! We have logged your requirement. Our technical lead will review it immediately."
        )
        ws.send_meeting_options(sender)

        # Notify admin (+91 9106060400)
        try:
            ws.send_admin_hot_lead_alert(
                sender=sender,
                requirement=text,
                source="WhatsApp Inbound Enquiry"
            )
        except Exception:
            pass
        return

    # Conversational reply via Gemini / objection engine
    reply = get_whatsapp_reply(text, state)
    ws.send_text(sender, reply)


def _handle_interactive_event(sender: str, message: Dict[str, Any], state: Dict[str, Any]):
    interactive = message.get("interactive", {})
    itype = interactive.get("type")

    action_id = ""
    if itype == "button_reply":
        action_id = (interactive.get("button_reply") or {}).get("id", "")
    elif itype == "list_reply":
        action_id = (interactive.get("list_reply") or {}).get("id", "")

    if not action_id:
        ws.send_main_menu(sender)
        return

    if action_id == "hire_developers":
        state["stage"] = "awaiting_requirement"
        save_state(sender, state)
        ws.send_text(
            sender,
            "Awesome! Our dedicated developers start from *₹450/- INR / hour* with a *7-Day Risk-Free Trial*.\n\n"
            "Please briefly describe what you are looking to build:\n"
            "• Web platform (Laravel, Next.js, Node, PHP)\n"
            "• Mobile app (Flutter, React Native, iOS, Android)\n"
            "• Custom CRM / ERP integration\n"
            "• Website speed / bug fixing"
        )
    elif action_id == "website_maintenance":
        state["stage"] = "maintenance_interest"
        save_state(sender, state)
        ws.send_text(
            sender,
            "We provide 24/7 Website Maintenance & AMC Support starting from *₹450/- INR / hour*:\n"
            "• Core Web Vitals & Speed Optimization\n"
            "• WordPress, Laravel & PHP Bug Fixes\n"
            "• Security Patches, Backups & Uptime Monitoring"
        )
        ws.send_meeting_options(sender)
    elif action_id == "portfolio":
        ws.send_text(
            sender,
            "We have completed *80+ projects* across US, UK, UAE, and Indian clients with *5+ years of experience*.\n\n"
            "Please drop your website URL or project scope, and we'll share the closest live case studies!"
        )
    elif action_id == "book_call":
        ws.send_meeting_options(sender)
    elif action_id == "calendly":
        ws.send_text(
            sender,
            f"📅 Please pick a 10-minute slot that works best for you:\n{CALENDLY_LINK}"
        )
    elif action_id == "google_meet":
        ws.send_text(
            sender,
            f"📞 You can join an introductory Google Meet call here:\n{GOOGLE_MEET_LINK}"
        )
    elif action_id == "main_menu":
        ws.send_main_menu(sender)
    else:
        ws.send_main_menu(sender)

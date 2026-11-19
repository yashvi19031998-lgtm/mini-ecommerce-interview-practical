"""
WhatsApp Gemini AI Assistant
============================
Integrates Google Gemini API (gemini-3.1-flash-lite) to classify prospect intent,
answer questions, and handle objections in WhatsApp conversations.

Features:
- Concise, polite responses under 90 words.
- Multilingual support (matches the prospect's language: Gujarati, Hindi, English).
- Rule-based fallback to objection_handling_engine when API key is missing or offline.
"""

import os
import re
from typing import Dict, Any

try:
    import google.generativeai as genai
except ImportError:
    genai = None

from objection_handling_engine import classify_objection, get_objection_response

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
if genai and GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
    except Exception:
        pass

SYSTEM_PROMPT = """
You are the WhatsApp Sales Assistant for Sangeeta Infotech, an established software engineering agency in Ahmedabad, Gujarat, India.

Core Facts:
- We provide dedicated software developers starting from ₹450/- INR / hour (~$5.5 USD/hr).
- Core Stacks: Laravel, PHP, CodeIgniter, Next.js, Node.js, Angular, WordPress, Flutter, React Native, custom CRM/ERP, and Website Maintenance/AMC.
- Track record: 5+ years of experience, 80+ completed client projects.
- Leverages the latest AI tools and modern engineering architectures.
- Offers a 7-Day Risk-Free Trial Sprint for new projects.

Rules:
1. Always reply in the SAME language as the user (e.g. Gujarati if user writes Gujarati, Hindi if Hindi, English if English).
2. Keep every reply under 90 words. WhatsApp users prefer crisp, direct answers.
3. Be professional, warm, and helpful.
4. Do not invent fake client names, unrealistic guarantees, or impossible deadlines.
5. If the user asks about pricing, state clearly: dedicated developers start at ₹450/- INR / hour, with a 7-day risk-free trial.
6. If the user wants to see work, offer our portfolio and case studies.
7. If the user wants to schedule a call, offer the 10-minute meeting booking link.
8. If the user asks to stop, confirm immediately that they will not receive further messages.
"""


def get_whatsapp_reply(user_message: str, conversation_state: Dict[str, Any]) -> str:
    """
    Generates a contextual response using Google Gemini API or intelligent rule-based fallback.
    """
    clean_msg = user_message.strip()
    if not clean_msg:
        return "Thanks for reaching out to Sangeeta Infotech! How can our engineering team help you today?"

    # Check for direct opt-out first
    if re.search(r"^(stop|unsubscribe|remove|no)$", clean_msg, re.IGNORECASE):
        return "Understood. You will not receive further messages from Sangeeta Infotech. Wishing you all the best."

    # 1. Try Gemini API if configured
    if genai and GEMINI_API_KEY:
        try:
            model = genai.GenerativeModel(
                model_name="gemini-3.1-flash-lite",
                system_instruction=SYSTEM_PROMPT
            )
            context_str = (
                f"Stage: {conversation_state.get('stage', 'new')}\n"
                f"Prior requirement: {conversation_state.get('requirement', 'none')}\n"
                f"User message: {clean_msg}"
            )
            resp = model.generate_content(
                context_str,
                generation_config={
                    "temperature": 0.3,
                    "max_output_tokens": 200
                }
            )
            if resp and resp.text:
                return resp.text.strip()
        except Exception:
            pass

    # 2. Rule-based fallback via objection_handling_engine
    category = classify_objection(clean_msg)
    _, body = get_objection_response(
        category=category,
        contact_name="there",
        company_name="your team",
        specific_need="software and web operations",
        sender_name="Sangeeta Infotech Team"
    )

    # Trim to WhatsApp brevity
    paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]
    if len(paragraphs) > 2:
        return f"{paragraphs[0]}\n\n{paragraphs[1]}"
    return body.strip()

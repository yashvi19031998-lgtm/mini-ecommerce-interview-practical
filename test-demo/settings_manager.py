import os
import json

SETTINGS_FILE = "company_settings.json"

DEFAULT_SETTINGS = {
    "companyName": "Sangeeta Infotech",
    "tagline": "Engineering Intelligent Web & Mobile Solutions",
    "senderName": "Business Development Team",
    "senderRole": "Client Solutions Specialist",
    "email": "sangeetainfotech19@gmail.com",
    "phone": "+91 9106060400",
    "whatsapp": "+91 9426738067",
    "website": "https://sangeetainfotech.co.in",
    "address": "Ahmedabad, Gujarat, India",
    "services": [
        "Custom Web & Full-Stack Development (Python, React, Node)",
        "Mobile App Development (Flutter, React Native)",
        "AI & Process Automation",
        "Dedicated Software Developers & Cloud Systems"
    ],
    "signatureTemplate": (
        "Warm regards,\n"
        "{senderName} | {senderRole}\n"
        "{companyName} — {tagline}\n"
        "📧 Email: {email}\n"
        "📞 Phone/WhatsApp: {phone}\n"
        "🌐 Website: {website}\n"
        "📍 Location: {address}"
    ),
    "defaultSubject": "Web & Software Engineering Collaboration - Sangeeta Infotech",
    "defaultMessage": (
        "Hi {name},\n\n"
        "I came across {company} and your business presence in {location}.\n\n"
        "At Sangeeta Infotech, we specialize in high-performance web applications, mobile apps, and custom software systems. "
        "We help ambitious companies scale engineering velocity and launch features faster with dependable tech talent.\n\n"
        "Key expertise we offer:\n"
        "• Full-Stack Web Development & Modern Portals\n"
        "• Mobile Apps (iOS & Android)\n"
        "• AI Integrations & Automation Workflows\n\n"
        "Would you be open to a brief 10-minute call this week to explore how we can support your tech needs?"
    ),
    "delayBetweenEmailsMs": 1500
}

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {**DEFAULT_SETTINGS, **data}
        except Exception:
            pass
    return DEFAULT_SETTINGS

def save_settings(data):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return True

def format_signature(settings=None):
    if settings is None:
        settings = load_settings()
    tpl = settings.get("signatureTemplate", DEFAULT_SETTINGS["signatureTemplate"])
    return (
        tpl.replace("{senderName}", settings.get("senderName", ""))
           .replace("{senderRole}", settings.get("senderRole", ""))
           .replace("{companyName}", settings.get("companyName", ""))
           .replace("{tagline}", settings.get("tagline", ""))
           .replace("{email}", settings.get("email", ""))
           .replace("{phone}", settings.get("phone", ""))
           .replace("{whatsapp}", settings.get("whatsapp", ""))
           .replace("{website}", settings.get("website", ""))
           .replace("{address}", settings.get("address", ""))
    )

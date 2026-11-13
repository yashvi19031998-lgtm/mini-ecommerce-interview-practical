import os
import json
import re

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
    "companyDescription": "Sangeeta Infotech is an industry-leading software engineering company based in Ahmedabad, Gujarat, specializing in high-performance web applications, mobile apps, AI integrations, and dedicated engineering teams for global businesses.",
    "defaultKeywords": ["software company", "web development", "mobile app", "IT services"],
    "defaultCity": "Ahmedabad",
    "defaultState": "Gujarat",
    "autoSendEmail": True,
    "maxPendingEmailsPerRun": 5,
    "excludedCompanies": ["8dots"],
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
                if isinstance(data, dict):
                    return {**DEFAULT_SETTINGS, **data}
        except Exception:
            pass
    return dict(DEFAULT_SETTINGS)

# Never written to company_settings.json (the file is tracked by git). Mail logins live in .env only.
SECRET_KEY_PARTS = ("pass", "secret", "token", "apikey", "api_key")


def _is_secret_key(key):
    k = str(key).lower()
    return any(part in k for part in SECRET_KEY_PARTS)


def _stored_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            pass
    return {}


def save_settings(data):
    """Merge `data` into the saved settings. Keys that are not sent keep their saved value
    (so a form that only knows some fields cannot wipe the others), and secrets are dropped."""
    if not isinstance(data, dict):
        raise ValueError("Settings must be a JSON object.")
    merged = {k: v for k, v in _stored_settings().items() if not _is_secret_key(k)}
    merged.update({str(k): v for k, v in data.items() if not _is_secret_key(k)})
    tmp = SETTINGS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2)
    os.replace(tmp, SETTINGS_FILE)
    return merged


def auto_send_state(settings=None):
    """Whether the hourly run may e-mail leads, and why.

    AUTO_SEND_EMAIL=false in the environment is a hard off switch. Otherwise the Settings toggle
    (autoSendEmail, on by default) decides. Returns (enabled, reason)."""
    env = os.getenv("AUTO_SEND_EMAIL")
    if env is not None and env.strip() != "" and env.strip().lower() not in ("true", "1", "yes"):
        return False, "Turned off by the AUTO_SEND_EMAIL environment setting (.env / workflow variables)"
    if settings is None:
        settings = load_settings()
    if not bool(settings.get("autoSendEmail", True)):
        return False, "Turned off in Settings"
    return True, "On"

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
           .replace("{companyDescription}", settings.get("companyDescription", settings.get("company_description", "")))
    )


def _excluded_terms(settings):
    """The do-not-contact list as clean lower-case terms (accepts a list or comma-separated text)."""
    excluded = settings.get("excludedCompanies", ["8dots"])
    if isinstance(excluded, str):
        excluded = excluded.split(",")
    if not isinstance(excluded, (list, tuple, set)):
        excluded = ["8dots"]
    terms = []
    for ex in excluded:
        term = " ".join(str(ex).lower().split())
        if re.search(r"[a-z0-9]", term) and term not in terms:
            terms.append(term)
    return terms


def _squeeze(text):
    return re.sub(r"[^a-z0-9]", "", str(text or "").lower())


def _has_whole_term(text, term):
    """True when `term` appears in `text` as whole word(s): '8dots' is in '8dots Technology LLP' and
    '8-Dots Pvt Ltd', but 'it' is not in 'Infinity Digital' and 'dots' is not '8dots'."""
    text = str(text or "").lower()
    if not text.strip():
        return False
    words = [re.escape(w) for w in re.findall(r"[a-z0-9]+", term)]
    if not words:
        return False
    pattern = r"(?<![a-z0-9])" + r"[^a-z0-9]*".join(words) + r"(?![a-z0-9])"
    if re.search(pattern, text):
        return True
    # '8 Dots Infotech' / '8-dots' written apart, for a single-word rule of a useful length
    squeezed_term = _squeeze(term)
    if len(squeezed_term) >= 4 and len(words) == 1:
        tokens = re.findall(r"[a-z0-9]+", text)
        for i in range(len(tokens)):
            joined = ""
            for tok in tokens[i:i + 3]:
                joined += tok
                if joined == squeezed_term:
                    return True
    return False


def _host_of(value):
    """Domain part of an e-mail address or website, without scheme, path, port or 'www.'."""
    v = str(value or "").strip().lower()
    if "@" in v:
        v = v.rsplit("@", 1)[1]
    v = re.sub(r"^[a-z][a-z0-9+.-]*://", "", v)
    v = re.split(r"[/?#:]", v, maxsplit=1)[0]
    return v[4:] if v.startswith("www.") else v


def _host_matches(host, term):
    """A domain belongs to an excluded company when one of its labels is the term ('8dots.in',
    'mail.8dots.co.in'), or - for rules of 4+ characters - starts with it ('8dotstech.com')."""
    squeezed = _squeeze(term)
    if not host or not squeezed:
        return False
    for label in host.split("."):
        label = _squeeze(label)
        if label == squeezed or (len(squeezed) >= 4 and label.startswith(squeezed)):
            return True
    return False


def is_company_excluded(company_name: str = "", email: str = "", website: str = "", settings: dict = None) -> tuple[bool, str]:
    """
    Checks if a lead belongs to an excluded company (the Do-Not-Contact list in Settings).

    A rule matches the company name as whole word(s), or the domain of the e-mail / website.
    It never matches a mere fragment: the old substring test blocked 'Dots Inc', one-letter
    names and - for a short rule like 'IT' - every company with those letters anywhere.
    """
    if settings is None:
        settings = load_settings()

    email_text = str(email or "").strip().lower()
    local_part = email_text.rsplit("@", 1)[0] if "@" in email_text else ""
    email_host = _host_of(email_text) if "@" in email_text else ""
    web_host = _host_of(website)

    for term in _excluded_terms(settings):
        if _has_whole_term(company_name, term):
            return True, f"Company '{company_name}' matches excluded company rule '{term}'"
        if email_host and _host_matches(email_host, term):
            return True, f"Email '{email}' matches excluded company rule '{term}'"
        # e.g. 8dots.hr@gmail.com - only for rules long enough not to hit ordinary names
        if local_part and len(_squeeze(term)) >= 4 and _has_whole_term(local_part, term):
            return True, f"Email '{email}' matches excluded company rule '{term}'"
        if web_host and _host_matches(web_host, term):
            return True, f"Website '{website}' matches excluded company rule '{term}'"

    return False, ""

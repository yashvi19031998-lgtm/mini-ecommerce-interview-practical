"""Phone kit: what to say when you call or WhatsApp a lead.

A mail alone is often never read. A short WhatsApp or a call right after it is what gets a reply, so every
lead with a phone number gets:
  - a WhatsApp message (pre-filled in the wa.me link, one tap to send)
  - a call script: opening line, 3 questions, answers to the usual objections, a voicemail line

Written by AI (Claude, then Gemini) when a key is set, otherwise filled in from the lead's own data, so it
always works without any key. Contact details are never sent to the AI provider.
"""
import json
import os
import re
from typing import Any, Dict
from urllib.parse import quote

COMPANY = os.getenv("COMPANY_NAME", "Sangeeta Infotech")
CITY = os.getenv("COMPANY_CITY", "Ahmedabad")
AI_MODEL = os.getenv("AI_QUALIFY_MODEL", "claude-opus-5-5")

_DIGITAL = re.compile(r"\b(seo|social media|google ads|facebook ads|meta ads|instagram|ppc|digital marketing|marketing)\b", re.I)


def _t(v: Any) -> str:
    s = str(v if v is not None else "").strip()
    return "" if s.lower() in ("nan", "n/a", "none", "null") else s


def _first_name(lead) -> str:
    """A real first name ("Priya"), never a user handle ("bhalenduc", "dev_123") or a company word."""
    first = _t(lead.get("full_name")).split(" ")[0]
    return first if re.fullmatch(r"[A-Z][a-z]{1,14}", first) else ""


def _facts(lead: Dict[str, Any]) -> Dict[str, str]:
    title = re.sub(r"\s*(--\s*\d+|\|\s*freelancer)\s*$", "", _t(lead.get("company_name") or lead.get("Company Name")), flags=re.I)
    need = _t(lead.get("ai_requirement")).rstrip(".")
    text = f"{title} {need} {_t(lead.get('description'))[:600]}"
    return {
        "title": title.strip(),
        "person": _first_name(lead),
        "need": need if len(need) >= 25 and not re.match(r"(needs?|requires?)\b", need, re.I) else "",
        "tech": _t(lead.get("ai_tech_stack")),
        "digital": "yes" if _DIGITAL.search(text) else "",
        "source": _t(lead.get("source")).split("|")[-1].split("(")[0].strip(),
    }


def template_kit(lead: Dict[str, Any], mailed: bool = False) -> Dict[str, Any]:
    f = _facts(lead)
    hi = f"Hi {f['person']}," if f["person"] else "Hi,"
    about = f' about "{f["title"]}"' if len(f["title"].split()) >= 3 and "|" not in f["title"] else ""
    offer = ("SEO, social media and Google / Meta ads" if f["digital"] else
             "web and mobile apps, custom software and AI automation")
    need = f" You need {f['need'][0].lower()}{f['need'][1:]}." if f["need"] else ""
    mail_line = " I also sent you a short e-mail with the details." if mailed else ""
    whatsapp = (f"{hi} this is {COMPANY} from {CITY}. We saw your post{about}.{need} Our team does {offer}."
                f"{mail_line} Would a 10-minute call this week work to understand what you need?")
    return {
        "whatsapp": whatsapp,
        "call_opening": (f"Hello{(' ' + f['person']) if f['person'] else ''}, this is <your name> from {COMPANY} in {CITY}. "
                         f"I saw your post{about}{' on ' + f['source'] if f['source'] else ''}"
                         f"{' and sent you a mail' if mailed else ''}. Do you have two minutes?"),
        "questions": [
            "What is the main thing you want this project to do for you?",
            "Do you have a deadline or a launch date in mind?",
            "Have you already worked with a team on this, or are we starting fresh?",
        ],
        "objections": {
            "We already have someone": "Understood. Many clients keep us as a backup team for extra work or urgent fixes. Can I send our portfolio so you have it?",
            "Too expensive / what is the price?": "It depends on the scope. After a 10-minute call I can send a fixed price with milestones, so there are no surprises.",
            "Send me details on mail": "Sure, I will send a short mail today with two similar projects and a rough timeline. Which address is best?",
            "Not now": "No problem. When would be a better time to check back - next week or next month?",
        },
        "voicemail": f"Hi, this is <your name> from {COMPANY}. I saw your post{about} and we can help with it. "
                     f"I will send you a WhatsApp as well. Have a good day.",
        "by": "template",
        "note": "",
    }


KIT_SYSTEM = f"""You help a salesperson at {COMPANY}, a small software and digital marketing agency in {CITY}, India,
contact a lead by phone and WhatsApp. Write in simple, polite English that a busy business owner reads in 10 seconds.
Be specific to their need; never invent facts, prices or past clients. Use "<your name>" where the caller's name goes.
Return ONLY a JSON object with keys: whatsapp (max 60 words, ends with one clear question), call_opening (1-2 sentences),
questions (list of 3 short discovery questions), objections (object: 4 common objections -> 1-2 sentence answers),
voicemail (max 35 words)."""


def _prompt(lead, mailed):
    f = _facts(lead)
    lines = [f"Post or company: {f['title']}", f"What they need: {f['need'] or _t(lead.get('ai_summary'))}",
             f"Tech: {f['tech']}", f"Found on: {f['source']}", f"Budget: {_t(lead.get('ai_budget'))}",
             f"Location: {_t(lead.get('location'))}", f"We already sent them an e-mail: {'yes' if mailed else 'no'}",
             f"Post text: {_t(lead.get('description'))[:1500]}"]
    return "\n".join(l for l in lines if not l.rstrip().endswith(":"))


def _parse(text: str) -> Dict[str, Any]:
    m = re.search(r"\{.*\}", text, re.S)
    data = json.loads(m.group(0) if m else text)
    if not isinstance(data, dict) or not data.get("whatsapp"):
        raise ValueError("no whatsapp text in the AI answer")
    data["questions"] = [str(q) for q in (data.get("questions") or [])][:5]
    data["objections"] = {str(k): str(v) for k, v in (data.get("objections") or {}).items()}
    return data


def _claude(lead, mailed, client=None):
    if client is None:
        import anthropic
        client = anthropic.Anthropic()
    resp = client.beta.messages.create(
        model=AI_MODEL, max_tokens=1500, betas=["server-side-fallback-2026-07-01"], fallbacks="default",
        output_config={"effort": "low"}, system=KIT_SYSTEM,
        messages=[{"role": "user", "content": _prompt(lead, mailed)}])
    return _parse("".join(b.text for b in resp.content if b.type == "text"))


def _gemini(lead, mailed, post=None):
    import requests
    from lead_quality import GEMINI_URL, GEMINI_MODEL, gemini_key
    post = post or requests.post
    body = {"contents": [{"role": "user", "parts": [{"text": f"{KIT_SYSTEM}\n\n{_prompt(lead, mailed)}"}]}],
            "generationConfig": {"maxOutputTokens": 1500, "responseMimeType": "application/json"}}
    r = post(GEMINI_URL.format(model=GEMINI_MODEL), json=body, timeout=40,
             headers={"x-goog-api-key": gemini_key(), "Content-Type": "application/json"})
    if r.status_code != 200:
        raise RuntimeError(f"Gemini HTTP {r.status_code}")
    parts = (r.json().get("candidates") or [{}])[0].get("content", {}).get("parts", [])
    return _parse("".join(p.get("text", "") for p in parts if isinstance(p, dict)))


def phone_kit(lead: Dict[str, Any], mailed: bool = False, use_ai: bool = True, client=None, post=None) -> Dict[str, Any]:
    """{'whatsapp', 'call_opening', 'questions', 'objections', 'voicemail', 'by', 'note', 'whatsapp_url'} - never raises."""
    kit, errors = None, []
    if use_ai and (os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN") or client is not None):
        try:
            kit = {**_claude(lead, mailed, client), "by": "ai"}
        except Exception as e:  # noqa: BLE001
            errors.append(f"Claude: {e}")
    if kit is None and use_ai and (os.getenv("GEMINI_API_KEY") or "").strip():
        try:
            kit = {**_gemini(lead, mailed, post), "by": "ai"}
        except Exception as e:  # noqa: BLE001
            errors.append(f"Gemini: {e}")
    if kit is None:
        kit = template_kit(lead, mailed)
    base = template_kit(lead, mailed)
    for k in ("call_opening", "questions", "objections", "voicemail"):
        kit.setdefault(k, base[k])
    kit["note"] = "; ".join(errors)
    return kit


def whatsapp_link(phone: str, text: str = "") -> str:
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) == 10:
        digits = "91" + digits
    elif len(digits) == 11 and digits.startswith("0"):
        digits = "91" + digits[1:]
    if len(digits) < 11:
        return ""
    return f"https://wa.me/{digits}" + (f"?text={quote(text)}" if text else "")

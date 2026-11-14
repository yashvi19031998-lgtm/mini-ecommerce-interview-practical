"""
AI Email Generator Module
=========================
Generates hyper-targeted, contextual B2B sales outreach emails tailored to the
specific company and their exact requirements (technologies, hiring needs, project signals).

Features:
- Extracts genuine company names and requirements even from complex job titles or snippets.
- Supports Claude (Anthropic API) & Google Gemini (free/paid tier) when API keys are configured.
- Includes a robust, intelligent requirement-aware synthesizer fallback for zero-API/offline runs.
- STRICT GUARANTEE: The professional company signature is NEVER omitted or missing.
"""

import os
import re
import json
import time
import datetime
from typing import Dict, Any, Tuple, Optional

from settings_manager import load_settings, format_signature, DEFAULT_SETTINGS

DEFAULT_SIGNATURE = """Warm regards,
Business Development Team | Client Solutions Specialist
Sangeeta Infotech — Engineering Intelligent Web & Mobile Solutions
📧 Email: info@sangeetainfotech.co.in
📞 Phone/WhatsApp: +91 9106060400
🌐 Website: https://sangeetainfotech.co.in
📍 Location: Ahmedabad, Gujarat, India"""


def clean_company_and_role(title: str, comp_hint: str = "") -> Tuple[str, str]:
    """
    Extracts a clean, human-friendly company name and job/project role
    from messy titles like 'Senior React Developer at Acme' or 'AKSHAR SOFTWARE LLP'.
    """
    title = str(title or "").strip()
    company = str(comp_hint or "").strip()
    role = ""

    # 1. Patterns like 'Role at Company' or 'Role @ Company'
    m_at = re.search(r'^(.*?)\s+(?:at|@)\s+([A-Za-z0-9\s&.,\'_-]+)$', title, re.I)
    if m_at:
        role = m_at.group(1).strip()
        if not company:
            company = m_at.group(2).strip()
    else:
        # 2. Patterns like 'Role - Company' or 'Company - Role'
        m_dash = re.split(r'\s+[-|:]\s+', title)
        if len(m_dash) >= 2:
            tech_keywords = ['developer', 'engineer', 'hiring', 'looking for', 'need', 'designer', 'lead', 'architect', 'remote']
            if any(w in m_dash[0].lower() for w in tech_keywords):
                role = m_dash[0].strip()
                if not company:
                    company = m_dash[1].strip()
            elif any(w in m_dash[1].lower() for w in tech_keywords):
                role = m_dash[1].strip()
                if not company:
                    company = m_dash[0].strip()
            elif not company:
                company = m_dash[0].strip()
        elif not company:
            company = title

    # Clean corporate legal noise for natural conversational tone
    clean_comp = re.sub(
        r'\s+(?:pvt\.?\s*ltd\.?|private\s+limited|llp|llc|inc\.?|corp\.?|corporation|technologies|solutions|infotech)$',
        '', company, flags=re.I
    ).strip()

    if clean_comp and len(clean_comp) >= 2:
        company = clean_comp

    # If company was in ALL CAPS, convert to Title Case for natural email tone
    if company.isupper() and len(company) > 2:
        company = company.title()

    # Fallback if title was just a generic role without company
    if company.lower() in ("job posting", "potential lead", "client project", "unknown", "your company"):
        company = "your team"

    return company, role


def detect_tech_and_intent(lead: Dict[str, Any]) -> Dict[str, Any]:
    """Detects technologies, specific requirement signals, and intent from lead attributes."""
    combined_parts = []
    for k, v in lead.items():
        if isinstance(v, str):
            combined_parts.append(v)
    combined_text = " ".join(combined_parts).lower()

    detected_tech = []
    if any(w in combined_text for w in ["react", "next.js", "nextjs", "frontend"]):
        detected_tech.append("React / Next.js")
    if any(w in combined_text for w in ["node", "nodejs", "express", "nestjs"]):
        detected_tech.append("Node.js")
    if any(w in combined_text for w in ["python", "django", "fastapi", "flask"]):
        detected_tech.append("Python")
    if any(w in combined_text for w in ["flutter", "react native", "ios", "android", "mobile app"]):
        detected_tech.append("Mobile Apps (Flutter/React Native)")
    if any(w in combined_text for w in ["full stack", "fullstack", "full-stack"]):
        detected_tech.append("Full-Stack Web Development")
    if any(w in combined_text for w in ["shopify", "woocommerce", "ecommerce", "e-commerce", "cart"]):
        detected_tech.append("E-Commerce (Shopify/WooCommerce)")
    if any(w in combined_text for w in ["ai", "machine learning", "automation", "llm", "bot"]):
        detected_tech.append("AI & Process Automation")
    if any(w in combined_text for w in ["php", "laravel", "wordpress"]):
        detected_tech.append("PHP / Laravel")

    # Primary requirement label
    req_label = str(lead.get("ai_requirement", "")).strip()
    if not req_label:
        if detected_tech:
            req_label = f"{detected_tech[0]} engineering"
        elif "hiring" in combined_text or "developer" in combined_text:
            req_label = "dedicated software engineering talent"
        elif "ecommerce" in combined_text or "shopify" in combined_text:
            req_label = "e-commerce web performance & custom development"
        else:
            req_label = "scalable custom software development"

    is_hiring = any(w in combined_text for w in ["hiring", "developer", "engineer", "job", "recruiting", "opening"])
    is_ecommerce = any(w in combined_text for w in ["shopify", "woocommerce", "store", "ecommerce"])

    return {
        "tech_stack": detected_tech,
        "primary_tech": detected_tech[0] if detected_tech else "Full-Stack Web & Mobile",
        "requirement": req_label,
        "is_hiring": is_hiring,
        "is_ecommerce": is_ecommerce
    }


def synthesize_tailored_email(company: str, role: str, intent_info: Dict[str, Any],
                              loc: str, sender_settings: Dict[str, Any]) -> Tuple[str, str]:
    """
    Intelligent requirement-aware fallback synthesizer that crafts human,
    high-converting B2B emails tailored to the company and their exact tech need.
    """
    primary_tech = intent_info["primary_tech"]
    requirement = intent_info["requirement"]
    is_hiring = intent_info["is_hiring"]
    is_ecommerce = intent_info["is_ecommerce"]

    greeting = f"Hi Team {company}" if company not in ("your team", "your company") else "Hello"

    # Category 1: Developer Hiring / Technical Talent
    if is_hiring:
        tech_mention = role if role else (f"{primary_tech} developer" if "developer" not in primary_tech.lower() else primary_tech)
        subject = f"Dedicated {tech_mention} Talent for {company}"
        body = (
            f"{greeting},\n\n"
            f"I noticed {company}'s current focus on {requirement}. "
            f"Scaling engineering capacity and screening vetted developers often slows down product release cycles.\n\n"
            f"At Sangeeta Infotech, our senior engineers specialize in high-velocity {primary_tech} development, "
            f"modern web architectures, and seamless API integrations. We partner with technology teams to provide "
            f"pre-vetted, dedicated developers who integrate directly into your sprint workflows from day one—without "
            f"recruitment delays or hiring overhead.\n\n"
            f"Would you be open to a brief 10-minute introductory call this week to see if our developers could "
            f"support your current roadmap?"
        )

    # Category 2: E-Commerce Store (Shopify / WooCommerce)
    elif is_ecommerce:
        subject = f"Web Performance & Custom Engineering for {company}"
        body = (
            f"{greeting},\n\n"
            f"I came across {company}'s online storefront. In modern e-commerce, site speed, seamless checkout flows, "
            f"and custom backend automations directly influence customer conversion and retention.\n\n"
            f"At Sangeeta Infotech, we help growing digital brands enhance their web infrastructure—from custom "
            f"features and API integrations to performance optimization and mobile-responsive improvements.\n\n"
            f"Would you be open to a brief 10-minute chat to explore how we can support {company}'s technical roadmap?"
        )

    # Category 3: General Software / Business System Project
    else:
        subject = f"Custom Software & Web Engineering for {company}"
        body = (
            f"{greeting},\n\n"
            f"I came across {company}'s business presence in {loc or 'India'}. "
            f"As companies expand, having robust, dependable web applications and scalable software systems is critical "
            f"for operational velocity.\n\n"
            f"At Sangeeta Infotech, we specialize in end-to-end custom software development, modern web portals, and mobile apps. "
            f"Our team works closely with founders and business leaders to design, build, and maintain high-performance digital solutions "
            f"tailored to their unique workflows.\n\n"
            f"Would you be open to a quick 10-minute discovery call this week to explore potential collaboration?"
        )

    return subject, body


def generate_with_claude(lead_data: Dict[str, Any], company: str, requirement: str,
                         tech_stack: str, loc: str, api_key: str) -> Optional[Tuple[str, str]]:
    """Generates a personalized outreach email via Anthropic Claude API."""
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        prompt = f"""You are an elite B2B sales outreach copywriter for Sangeeta Infotech (a software engineering agency in Ahmedabad, India).
Draft a concise, warm, highly personalized cold outreach email to:
- Company Name: {company}
- Prospect Requirement / Need: {requirement}
- Tech Stack / Role: {tech_stack}
- Location: {loc}
- Additional Context: {lead_data.get('description', '')[:400]}

Rules:
1. Subject line: 4-8 words, specific to their requirement and company.
2. Opening: Greet naturally (e.g. 'Hi Team {company}', or person's name if provided). Directly acknowledge their specific requirement or tech stack in the very first sentence. NO generic 'I hope this finds you well' or 'I came across your company'.
3. Value proposition: Explain specifically how Sangeeta Infotech's senior software engineers accelerate delivery for this exact requirement.
4. Soft CTA: Ask for a 10-minute discovery call this week.
5. Tone: Human, crisp, zero corporate fluff. 70-110 words total.
6. DO NOT include the sender signature at the end (signature is appended automatically).

Respond ONLY with valid JSON in this exact structure:
{{"subject": "...", "body": "..."}}"""

        resp = client.messages.create(
            model=os.getenv("AI_QUALIFY_MODEL", "claude-opus-5-5"),
            max_tokens=400,
            temperature=0.3,
            messages=[{"role": "user", "content": prompt}]
        )
        content = resp.content[0].text.strip()
        data = json.loads(content[content.find("{"):content.rfind("}")+1])
        if data.get("subject") and data.get("body"):
            return data["subject"].strip(), data["body"].strip()
    except Exception as e:
        print(f"[AI Email Generator] Claude API notice: {e}")
    return None


def generate_with_gemini(lead_data: Dict[str, Any], company: str, requirement: str,
                         tech_stack: str, loc: str, api_key: str) -> Optional[Tuple[str, str]]:
    """Generates a personalized outreach email via Google Gemini API."""
    try:
        import requests
        gemini_model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{gemini_model}:generateContent?key={api_key}"
        prompt = f"""You are an elite B2B sales outreach copywriter for Sangeeta Infotech (a software engineering agency in Ahmedabad, India).
Draft a concise, warm, highly personalized cold outreach email to:
- Company: {company}
- Requirement: {requirement}
- Tech Stack: {tech_stack}
- Location: {loc}
- Description: {lead_data.get('description', '')[:350]}

Rules:
1. Subject: 4-8 words, tailored to {company} and their specific need.
2. Body: Greet warmly ('Hi Team {company}'), directly mention their requirement, explain how Sangeeta Infotech's senior engineers solve it, and ask for a 10-minute discovery call.
3. 70-110 words total. Zero spam cliches. Do not include signature.

Respond ONLY with valid JSON: {{"subject": "...", "body": "..."}}"""

        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.3, "maxOutputTokens": 450}
        }
        res = requests.post(url, json=body, timeout=25)
        if res.status_code == 200:
            data = res.json()
            candidates = data.get("candidates", [])
            if candidates:
                raw_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                parsed = json.loads(raw_text[raw_text.find("{"):raw_text.rfind("}")+1])
                if parsed.get("subject") and parsed.get("body"):
                    return parsed["subject"].strip(), parsed["body"].strip()
    except Exception as e:
        print(f"[AI Email Generator] Gemini API notice: {e}")
    return None


def generate_personalized_email(lead: Dict[str, Any], settings: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    """
    Main entry point: Generates a tailored, requirement-specific email for a lead.
    Guarantees that the company signature is 100% attached at the end of the email.

    Returns:
    {
        "subject": "...",
        "body": "... [with signature attached]",
        "company_name": "...",
        "requirement": "..."
    }
    """
    settings = settings or load_settings()
    raw_comp = lead.get("company_name") or lead.get("Company Name") or lead.get("full_name") or "your company"
    clean_company, role = clean_company_and_role(raw_comp)
    intent_info = detect_tech_and_intent(lead)
    loc = lead.get("location") or lead.get("Address") or lead.get("City") or "your region"

    # Prepare signature
    sig = ""
    if settings:
        if settings.get("signature"):
            sig = str(settings.get("signature")).strip()
        elif settings.get("signatureTemplate"):
            sig = format_signature(settings)
    if not sig:
        sig = format_signature(settings) if format_signature else ""
    if not sig or not sig.strip() or len(sig.strip()) < 15:
        sig = DEFAULT_SIGNATURE

    subject, body = None, None

    # 1. Try Claude if ANTHROPIC_API_KEY is configured
    claude_key = (os.getenv("ANTHROPIC_API_KEY") or "").strip()
    if claude_key:
        res = generate_with_claude(lead, clean_company, intent_info["requirement"],
                                   intent_info["primary_tech"], loc, claude_key)
        if res:
            subject, body = res

    # 2. Try Gemini if GEMINI_API_KEY is configured
    if not body:
        gemini_key = (os.getenv("GEMINI_API_KEY") or "").strip()
        if gemini_key:
            res = generate_with_gemini(lead, clean_company, intent_info["requirement"],
                                       intent_info["primary_tech"], loc, gemini_key)
            if res:
                subject, body = res

    # 3. Use intelligent requirement-aware synthesizer fallback
    if not body:
        subject, body = synthesize_tailored_email(clean_company, role, intent_info, loc, settings)

    # 4. STRICT SIGNATURE GUARANTEE: Never let an email leave without the signature!
    clean_body = body.rstrip()
    sig_clean = sig.strip()

    # Check if signature block is already appended
    has_sig = (sig_clean[:25].lower() in clean_body.lower()) or ("+91 9106060400" in clean_body and "warm regards" in clean_body.lower())

    if not has_sig:
        final_body = f"{clean_body}\n\n---\n{sig_clean}"
    else:
        final_body = clean_body

    return {
        "subject": subject,
        "body": final_body,
        "company_name": clean_company,
        "role": role,
        "requirement": intent_info["requirement"]
    }

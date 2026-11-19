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
Business Development Team | Client Solutions
Sangeeta Infotech — Engineering Intelligent Web & Mobile Solutions
Phone/WhatsApp: +91 9106060400
Email: info@sangeetainfotech.co.in
Website: https://sangeetainfotech.co.in
Ahmedabad, Gujarat, India"""


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
    # 1. Video Reels & Festival Creatives
    if any(w in combined_text for w in ["reel", "reels", "festival", "graphic design", "creative design", "social media manager", "instagram post", "video editing"]):
        detected_tech.append("Social Media Creatives & Video Reels")
    # 2. Website Maintenance & AMC
    if any(w in combined_text for w in ["maintenance", "website amc", "website support", "bug fix", "site update", "security patch", "speed optimization"]):
        detected_tech.append("Website Maintenance & 24/7 Support")
    # 3. WordPress & WooCommerce
    if any(w in combined_text for w in ["wordpress", "elementor", "divi", "woocommerce"]):
        detected_tech.append("WordPress & WooCommerce")
    # 4. PHP, Laravel & CodeIgniter
    if any(w in combined_text for w in ["laravel", "codeigniter", "php", "symfony"]):
        detected_tech.append("PHP / Laravel / CodeIgniter")
    # 5. Angular
    if any(w in combined_text for w in ["angular", "angularjs"]):
        detected_tech.append("Angular Frontend")
    # 6. React / Next.js
    if any(w in combined_text for w in ["next.js", "nextjs", "react", "frontend"]):
        detected_tech.append("React / Next.js")
    # 7. Node.js
    if any(w in combined_text for w in ["node", "nodejs", "express", "nestjs"]):
        detected_tech.append("Node.js Backend")
    # 8. Python
    if any(w in combined_text for w in ["python", "django", "fastapi", "flask"]):
        detected_tech.append("Python / AI")
    # 9. Mobile Apps (Flutter / React Native)
    if any(w in combined_text for w in ["flutter", "react native", "ios", "android", "mobile app", "app developer"]):
        detected_tech.append("Mobile App Development (Flutter/Native)")
    # 10. CRM & Business Portals
    if any(w in combined_text for w in ["crm", "erp", "salesforce", "hubspot", "zoho", "portal", "dashboard"]):
        detected_tech.append("Custom CRM & ERP Portals")
    # 11. E-Commerce
    if any(w in combined_text for w in ["shopify", "ecommerce", "e-commerce", "cart"]):
        detected_tech.append("E-Commerce (Shopify/WooCommerce)")
    # 12. Full-Stack
    if any(w in combined_text for w in ["full stack", "fullstack", "full-stack"]):
        detected_tech.append("Full-Stack Web Development")
    # 13. AI & Automation
    if any(w in combined_text for w in ["ai", "machine learning", "automation", "llm", "bot"]):
        detected_tech.append("AI & Process Automation")

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
                              loc: str, sender_settings: Dict[str, Any],
                              is_competitor_client: bool = False) -> Tuple[str, str]:
    """
    Intelligent requirement-aware fallback synthesizer that crafts human,
    high-converting B2B emails tailored to the company and their exact tech need.
    """
    primary_tech = intent_info["primary_tech"]
    requirement = intent_info["requirement"]
    is_hiring = intent_info["is_hiring"]
    is_ecommerce = intent_info["is_ecommerce"]
    tech_lower = primary_tech.lower()

    greeting = f"Hi Team {company}" if company not in ("your team", "your company") else "Hello"

    # Category 0: Active Competitor Agency Client
    if is_competitor_client:
        subject = f"Software development help for {company}"
        body = (
            f"{greeting},\n\n"
            f"I noticed {company}'s digital products and software operations.\n\n"
            f"At Sangeeta Infotech, our engineering team in Ahmedabad has 5+ years of experience building and maintaining web and mobile software for 80+ clients. "
            f"We help teams get development work done faster without the overhead of hiring or disrupting your existing setup.\n\n"
            f"Are you open to a quick 10-minute chat this week, or would you like to see a few live examples of our recent work?"
        )
        return subject, body

    # Category 1: Social Media Creatives, Reels & Festival Posts
    if "reels" in tech_lower or "social media" in tech_lower:
        subject = f"Creative reels & design for {company}"
        body = (
            f"{greeting},\n\n"
            f"I came across {company}'s brand presence.\n\n"
            f"At Sangeeta Infotech, our creative team has 5+ years of experience producing high-engagement video Reels, festival campaigns, and branded social posts for 80+ growing businesses. "
            f"We deliver ready-to-post creatives on predictable weekly schedules.\n\n"
            f"Are you open to a brief chat this week, or would you like to see a few live examples of our recent work?"
        )
        return subject, body

    # Category 2: Website Maintenance & 24/7 Support AMC
    if "maintenance" in tech_lower or "support" in tech_lower:
        subject = f"Website maintenance & support for {company}"
        body = (
            f"{greeting},\n\n"
            f"I came across {company}'s website.\n\n"
            f"At Sangeeta Infotech, our team has 5+ years of experience handling website uptime, speed, security patches, and regular bug fixes for 80+ businesses. "
            f"We take care of technical maintenance so your team can focus on business without hiring full-time developers.\n\n"
            f"Are you open to a quick 10-minute chat this week, or would you like to see how we handle website maintenance?"
        )
        return subject, body

    # Category 3: WordPress & WooCommerce
    if "wordpress" in tech_lower:
        subject = f"WordPress help for {company}"
        body = (
            f"{greeting},\n\n"
            f"I noticed your work on WordPress and WooCommerce.\n\n"
            f"At Sangeeta Infotech, our engineering team has 5+ years of experience building and maintaining custom WordPress stores for 80+ clients. "
            f"We help teams get development and site updates done quickly without the hassle of hiring.\n\n"
            f"Are you open to a quick 10-minute chat this week, or would you like to see a few live links of our recent work?"
        )
        return subject, body

    # Category 4: PHP, Laravel & CodeIgniter
    if "laravel" in tech_lower or "codeigniter" in tech_lower or "php" in tech_lower:
        subject = f"Laravel & PHP development for {company}"
        body = (
            f"{greeting},\n\n"
            f"I came across {company}'s backend systems and software platform.\n\n"
            f"At Sangeeta Infotech, our engineering team has 5+ years of experience building and scaling Laravel and PHP systems for 80+ clients. "
            f"We work directly inside your Git repositories to ship features and bug fixes quickly without hiring delays.\n\n"
            f"Are you open to a quick 10-minute chat this week, or would you like to see a few live examples of our recent work?"
        )
        return subject, body

    # Category 5: Angular, Next.js & Modern Frontend
    if "angular" in tech_lower or "next.js" in tech_lower or "react" in tech_lower:
        subject = f"Next.js & frontend help for {company}"
        body = (
            f"{greeting},\n\n"
            f"I noticed {company}'s web applications and product frontend.\n\n"
            f"At Sangeeta Infotech, our team has 5+ years of experience building fast, clean Next.js, React, and Angular web apps for 80+ clients. "
            f"We help teams clear their frontend backlog and ship new features without hiring delays.\n\n"
            f"Are you open to a quick 10-minute chat this week, or would you like to see a few live links of our recent work?"
        )
        return subject, body

    # Category 6: Custom CRM & ERP Business Portals
    if "crm" in tech_lower or "erp" in tech_lower:
        subject = f"Custom CRM & portal help for {company}"
        body = (
            f"{greeting},\n\n"
            f"I noticed {company}'s growing business operations.\n\n"
            f"At Sangeeta Infotech, our engineering team has 5+ years of experience building custom CRMs, internal portals, and workflow automations for 80+ businesses. "
            f"We help teams connect their tools and eliminate manual data entry.\n\n"
            f"Are you open to a quick 10-minute chat this week, or would you like to see a few live examples of our recent work?"
        )
        return subject, body

    # Category 7: Mobile App Development (Flutter, iOS, Android)
    if "mobile" in tech_lower or "flutter" in tech_lower or "app" in tech_lower:
        subject = f"Mobile app development for {company}"
        body = (
            f"{greeting},\n\n"
            f"I came across {company}'s mobile presence and digital products.\n\n"
            f"At Sangeeta Infotech, our engineering team has 5+ years of experience building smooth Flutter, iOS, and Android mobile apps for 80+ clients. "
            f"We handle everything from UI to App Store launches without recruiting overhead.\n\n"
            f"Are you open to a quick 10-minute chat this week, or would you like to see a few live app examples we have built?"
        )
        return subject, body

    # Category 8: Developer Hiring / Technical Talent
    if is_hiring:
        tech_mention = role if role else (f"{primary_tech} developer" if "developer" not in primary_tech.lower() else primary_tech)
        subject = f"{tech_mention} talent for {company}"
        body = (
            f"{greeting},\n\n"
            f"I noticed {company} has an active requirement for {tech_mention}.\n\n"
            f"At Sangeeta Infotech, our team in Ahmedabad has 5+ years of experience providing dedicated software developers to 80+ clients. "
            f"Our engineers plug directly into your daily standups and Git repositories from Day 1, with zero recruiting delays.\n\n"
            f"Are you open to a quick 10-minute chat this week to see if our developers could help with your current roadmap?"
        )
        return subject, body

    # Category 9: E-Commerce Store (Shopify / WooCommerce)
    elif is_ecommerce:
        subject = f"E-commerce development help for {company}"
        body = (
            f"{greeting},\n\n"
            f"I came across {company}'s online store.\n\n"
            f"At Sangeeta Infotech, our engineering team has 5+ years of experience building and optimizing custom e-commerce stores, checkout flows, and API integrations for 80+ brands. "
            f"We help businesses improve site speed and add custom features without hiring delays.\n\n"
            f"Are you open to a quick 10-minute chat this week, or would you like to see a few live examples of our recent work?"
        )
        return subject, body

    # Category 10: General Custom Software / Digital Engineering
    else:
        subject = f"Software development help for {company}"
        body = (
            f"{greeting},\n\n"
            f"I noticed {company}'s business presence in {loc or 'India'}.\n\n"
            f"At Sangeeta Infotech, our engineering team in Ahmedabad has 5+ years of experience building custom web and mobile software for 80+ clients. "
            f"We help teams get their development work done quickly and reliably without hiring delays.\n\n"
            f"Are you open to a quick 10-minute chat this week, or would you like to see a few live examples of our recent work?"
        )
        return subject, body


def generate_with_claude(lead_data: Dict[str, Any], company: str, requirement: str,
                         tech_stack: str, loc: str, api_key: str) -> Optional[Tuple[str, str]]:
    """Generates a personalized outreach email via Anthropic Claude API using simple, straightforward human language."""
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        prompt = f"""You are a software developer writing on behalf of Sangeeta Infotech (Ahmedabad, India).
Write a very short, simple, and straightforward cold outreach email to {company}.
Their need / interest: {requirement} ({tech_stack}).
Location: {loc}.
Context: {lead_data.get('description', '')[:300]}

Clear and Straightforward Rules:
1. Language: Use simple, plain, everyday words. Avoid complicated corporate buzzwords (no "bounded workstreams", "operational velocity", etc.).
2. Subject line: Short and direct (e.g. '{tech_stack} help for {company}' or '{tech_stack} development for {company}').
3. Opening: Greet naturally ('Hi Team {company}'). Directly mention you noticed their work or need for {tech_stack}.
4. Body:
   - State clearly that Sangeeta Infotech is an engineering team in Ahmedabad with 5+ years of experience building and maintaining {tech_stack} websites and applications for 80+ clients.
   - Mention we help teams get development work done quickly and reliably without the hiring hassle.
5. Soft CTA: Ask if they are open to a quick 10-minute chat this week, or if they would like to see a few live links/examples of our recent work.
6. Plain text only: NO asterisks (**), NO markdown bolding, NO pricing/rates in this introductory note.
7. Length: 50 to 75 words total. Do NOT include signature.

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
    """Generates a personalized outreach email via Google Gemini API using simple, straightforward human language."""
    try:
        import requests
        primary_model = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
        models_to_try = [primary_model] if primary_model != "gemini-3.1-flash-lite" else [
            "gemini-3.1-flash-lite", "gemini-3.8-flash", "gemini-3.5-flash", "gemini-flash-latest"
        ]
        prompt = f"""You are a software developer writing on behalf of Sangeeta Infotech (Ahmedabad, India).
Write a very short, simple, and straightforward cold outreach email to {company}.
Their need / interest: {requirement} ({tech_stack}).
Location: {loc}.
Context: {lead_data.get('description', '')[:300]}

Clear and Straightforward Rules:
1. Language: Use simple, plain, everyday words. Avoid complicated corporate buzzwords (no "bounded workstreams", "operational velocity", etc.).
2. Subject line: Short and direct (e.g. '{tech_stack} help for {company}' or '{tech_stack} development for {company}').
3. Opening: Greet naturally ('Hi Team {company}'). Directly mention you noticed their work or need for {tech_stack}.
4. Body:
   - State clearly that Sangeeta Infotech is an engineering team in Ahmedabad with 5+ years of experience building and maintaining {tech_stack} websites and applications for 80+ clients.
   - Mention we help teams get development work done quickly and reliably without the hiring hassle.
5. Soft CTA: Ask if they are open to a quick 10-minute chat this week, or if they would like to see a few live links/examples of our recent work.
6. Plain text only: NO asterisks (**), NO markdown bolding, NO pricing/rates in this introductory note.
7. Length: 50 to 75 words total. Do NOT include signature.

Respond ONLY with valid JSON: {{"subject": "...", "body": "..."}}"""

        for gemini_model in models_to_try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{gemini_model}:generateContent?key={api_key}"
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
            elif res.status_code == 404:
                continue  # try next model
            else:
                print(f"[AI Email Generator] Gemini API error ({res.status_code}): {res.text[:150]}")
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
        is_comp = "competitor" in str(lead.get("source", "")).lower()
        subject, body = synthesize_tailored_email(clean_company, role, intent_info, loc, settings, is_competitor_client=is_comp)

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

"""
AI BDE (Business Development Executive) Agent
=============================================
Autonomous sales engineering and business development agent for Sangeeta Infotech.

Core Responsibilities:
1. Daily BDE Morning Briefing: Analyzes pipeline, flags hot leads, and prioritizes due follow-ups.
2. Hyper-Personalized Deal Pitching: Generates tailored email & WhatsApp outreach based on client tech stack.
3. Inbound Objection Handling & Negotiation: Converts client replies into booked meetings and retainer agreements.
4. Lead Qualification & Scoring: Evaluates budget potential, urgency, and technical fit.

Agency Standards Enforced:
- Dedicated developers starting at ₹450/- INR / hour (~$5.5 USD/hr).
- 5+ years of delivery experience, 80+ completed client projects.
- Modern AI developer tools & latest tech stacks (Laravel, PHP, Next.js, Flutter, Node, CRM, AMC).
- 7-Day Risk-Free Trial Sprint.
- Strict Excluded Companies shield (e.g. 8dots).
"""

import os
import re
import csv
import json
import datetime
from typing import Dict, Any, List, Optional, Tuple

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MASTER_CSV = os.path.join(BASE_DIR, "all_leads_master.csv")

try:
    from settings_manager import load_settings
    _settings = load_settings()
except Exception:
    _settings = {}

EXCLUDED_COMPANIES = set(k.lower() for k in _settings.get("excludedCompanies", ["8dots"]))

from objection_handling_engine import (
    classify_objection,
    get_objection_response,
    MONTHLY_RETAINER_PACKAGES
)


def is_excluded_company(company_name: str) -> bool:
    """Checks if company matches excluded companies shield (e.g. 8dots)."""
    if not company_name:
        return False
    c_lower = company_name.lower().strip()
    return any(ex in c_lower for ex in EXCLUDED_COMPANIES)


def get_daily_bde_briefing(csv_path: str = MASTER_CSV) -> Dict[str, Any]:
    """
    Generates an executive morning briefing of sales pipeline, hot leads,
    and priority follow-up actions for Sangeeta Infotech.
    """
    now_dt = datetime.datetime.now()
    today_str = now_dt.strftime("%Y-%m-%d")

    total_leads = 0
    contacted_leads = 0
    hot_leads: List[Dict[str, Any]] = []
    leads_by_service: Dict[str, int] = {
        "Web & Full-Stack": 0,
        "Mobile App": 0,
        "Website Maintenance & AMC": 0,
        "Custom CRM & ERP": 0,
        "Other": 0
    }

    if os.path.exists(csv_path):
        try:
            with open(csv_path, mode="r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    total_leads += 1
                    comp = row.get("company_name") or ""
                    if is_excluded_company(comp):
                        continue

                    # Check contact status
                    email_status = (row.get("email_status") or "").upper()
                    wa_status = (row.get("whatsapp_status") or "").upper()
                    if email_status == "SENT" or wa_status == "SENT":
                        contacted_leads += 1

                    # Score check
                    try:
                        score = float(row.get("ai_score") or row.get("intent_score") or 5)
                    except Exception:
                        score = 5.0

                    # Service categorization
                    desc = (row.get("description") or "" + " " + (row.get("ai_requirement") or "")).lower()
                    if any(k in desc for k in ("maintenance", "support", "speed", "slow", "bug fix", "amc")):
                        leads_by_service["Website Maintenance & AMC"] += 1
                    elif any(k in desc for k in ("mobile", "flutter", "react native", "android", "ios", "app")):
                        leads_by_service["Mobile App"] += 1
                    elif any(k in desc for k in ("crm", "erp", "portal", "hubspot", "salesforce")):
                        leads_by_service["Custom CRM & ERP"] += 1
                    elif any(k in desc for k in ("laravel", "php", "next.js", "react", "node", "web", "angular")):
                        leads_by_service["Web & Full-Stack"] += 1
                    else:
                        leads_by_service["Other"] += 1

                    # Identify Hot Leads (Score >= 8) not yet won/lost
                    status = (row.get("status") or "").upper()
                    if score >= 8.0 and status not in ("WON", "LOST", "DISQUALIFIED"):
                        hot_leads.append({
                            "lead_id": row.get("\ufefflead_id") or row.get("lead_id"),
                            "company_name": comp,
                            "email": row.get("email"),
                            "phone": row.get("mobile_number"),
                            "score": score,
                            "tech": row.get("ai_tech_stack") or "Web Development",
                            "summary": row.get("ai_summary") or row.get("description", "")[:120],
                            "email_status": email_status
                        })
        except Exception:
            pass

    # Sort hot leads descending by score
    hot_leads.sort(key=lambda x: x["score"], reverse=True)

    # Check followups due
    due_followups_count = 0
    try:
        import followup_sequence
        due_items = followup_sequence.due()
        due_followups_count = len(due_items)
    except Exception:
        due_followups_count = 0

    # Formulate strategic BDE recommendations
    recommendations = []
    if hot_leads:
        top_lead = hot_leads[0]
        recommendations.append(
            f"High-Priority Outreach: Send tailored pitch to **{top_lead['company_name']}** (Score: {top_lead['score']}/10) for {top_lead['tech']}."
        )
    if due_followups_count > 0:
        recommendations.append(
            f"Follow-up Queue: **{due_followups_count} scheduled follow-ups** are due today. Dispatch them to keep conversations warm."
        )
    if leads_by_service.get("Website Maintenance & AMC", 0) > 0:
        recommendations.append(
            f"Maintenance Campaign: You have **{leads_by_service['Website Maintenance & AMC']} leads** needing site speed and AMC fixes. Pitch the ₹450/hr package."
        )

    return {
        "report_date": today_str,
        "agent_name": "Sangeeta Infotech Autonomous AI BDE",
        "pipeline_metrics": {
            "total_leads_in_registry": total_leads,
            "total_leads_contacted": contacted_leads,
            "hot_leads_available": len(hot_leads),
            "followups_due_today": due_followups_count
        },
        "service_breakdown": leads_by_service,
        "top_hot_leads": hot_leads[:5],
        "bde_action_plan": recommendations
    }


def generate_lead_pitch(lead: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generates a personalized BDE deal pitch for email and WhatsApp
    based on the lead's exact technical profile and pain points.
    """
    comp = (lead.get("company_name") or "there").strip()
    if is_excluded_company(comp):
        return {
            "error": f"Company '{comp}' is protected under the excluded company shield.",
            "is_valid": False
        }

    raw_text = (
        (lead.get("description") or "") + " " +
        (lead.get("ai_requirement") or "") + " " +
        (lead.get("ai_tech_stack") or "")
    ).lower()

    # Determine recommended angle & service
    if any(k in raw_text for k in ("maintenance", "speed", "slow", "core web vitals", "amc", "broken", "bug")):
        service_category = "Website Maintenance & Speed Optimization"
        angle = "Speed Optimization & 24/7 AMC Support"
        email_subject = f"Website maintenance & speed fixes for {comp}"
        pain_point = "website performance and routine maintenance"
        deal_package = "Part-Time Dedicated (80 hrs/mo) — ₹36,000/- INR / mo"
    elif any(k in raw_text for k in ("crm", "erp", "portal", "hubspot", "salesforce", "zoho")):
        service_category = "Custom CRM & ERP Portals"
        angle = "Custom Business Portal & Workflow Automation"
        email_subject = f"Custom CRM & portal development for {comp}"
        pain_point = "custom CRM workflows and business portal integrations"
        deal_package = "Full-Time Dedicated (160 hrs/mo) — ₹72,000/- INR / mo"
    elif any(k in raw_text for k in ("mobile", "flutter", "react native", "ios", "android", "app")):
        service_category = "Mobile App Development"
        angle = "Cross-Platform Flutter & React Native Engineering"
        email_subject = f"Mobile app engineering for {comp}"
        pain_point = "mobile application release and API sync"
        deal_package = "Full-Time Dedicated (160 hrs/mo) — ₹72,000/- INR / mo"
    elif any(k in raw_text for k in ("laravel", "php", "codeigniter", "backend")):
        service_category = "PHP & Laravel Backend"
        angle = "Senior Backend Architecture & API Scaling"
        email_subject = f"Laravel & backend engineering support for {comp}"
        pain_point = "backend systems and Laravel API architecture"
        deal_package = "Part-Time Dedicated (80 hrs/mo) — ₹36,000/- INR / mo"
    else:
        service_category = "Full-Stack Web Development"
        angle = "Senior Dedicated Developer Capacity"
        email_subject = f"Software development help for {comp}"
        pain_point = "digital platform and web engineering backlog"
        deal_package = "Dedicated Developer starting at ₹450/- INR / hour"

    # Draft email body (3 paragraphs, clean spacing, selective bolding)
    email_body = (
        f"Hi Team **{comp}**,\n\n"
        f"I came across **{comp}**'s software operations and digital presence.\n\n"
        f"At **Sangeeta Infotech**, our engineering team in Ahmedabad brings **5+ years of experience** building software for **80+ clients**. "
        f"We build with the **latest AI tools and modern technologies** to deliver clean, scalable solutions for {pain_point}.\n\n"
        f"Our dedicated developer packages start from just **₹450/- INR / hour** with a **7-day risk-free trial sprint**, giving you senior engineering speed without recruitment overhead.\n\n"
        f"Are you open to a quick **10-minute chat** this week, or would you like to see a few live examples of our recent work?\n\n"
        f"Warm regards,\n"
        f"Business Development Team\n"
        f"**Sangeeta Infotech** | +91 9106060400\n"
        f"https://sangeetainfotech.co.in"
    )

    # Draft WhatsApp pitch
    whatsapp_body = (
        f"Hi Team *{comp}*,\n\n"
        f"I came across {comp}'s software and tech operations.\n\n"
        f"At *Sangeeta Infotech* (Ahmedabad), our team brings *5+ years of experience* and *80+ completed projects* across modern web, mobile apps, and custom CRMs using the *latest AI tools*.\n\n"
        f"We offer dedicated developers starting at just *₹450/- INR / hour* with a *7-day risk-free trial*.\n\n"
        f"Would you be open to a quick 10-minute chat this week, or would you like to see a few live examples of our recent work?\n\n"
        f"Best regards,\n"
        f"Sangeeta Infotech | +91 9106060400"
    )

    return {
        "is_valid": True,
        "company_name": comp,
        "service_category": service_category,
        "sales_angle": angle,
        "recommended_package": deal_package,
        "hourly_rate": "₹450/- INR / hour (~$5.5 USD/hr)",
        "trial_offer": "7-Day Risk-Free Trial Sprint",
        "email_pitch": {
            "subject": email_subject,
            "body": email_body
        },
        "whatsapp_pitch": {
            "body": whatsapp_body
        }
    }


def handle_inbound_negotiation(
    client_message: str,
    contact_name: str = "there",
    company_name: str = "your team",
    specific_need: str = "software development"
) -> Dict[str, Any]:
    """
    BDE Objection Handler & Negotiator: Analyzes prospect's response,
    classifies objections, and drafts winning responses.
    """
    category = classify_objection(client_message)
    subject, body = get_objection_response(
        category=category,
        contact_name=contact_name,
        company_name=company_name,
        specific_need=specific_need,
        sender_name="Sangeeta Infotech BDE Team"
    )

    # Strategy advice for the user
    advice_map = {
        "portfolio": "Prospect wants proof. Share 2-3 relevant live links and offer a 1-page technical plan.",
        "agency_model": "Prospect is verifying credibility. Emphasize 5+ years of agency structure, named developer, and code ownership.",
        "timezone": "Prospect wants to know about working hours. Confirm 3-4 hour daily overlap with US/UK and Slack/Teams updates.",
        "pricing_trial": "Prospect is interested in budget. Highlight ₹450/hr and push the 7-Day Risk-Free Trial Sprint.",
        "happy_with_current": "Prospect has an existing team. Position Sangeeta Infotech as a 'Parallel Capacity Pod' for backlogs/AMC.",
        "opt_out": "Prospect opted out. Suppress immediately and do not contact again.",
        "general_inquiry": "General inquiry. Ask about current roadmap priorities and invite to a 10-minute call."
    }

    return {
        "detected_intent": category,
        "bde_strategy_advice": advice_map.get(category, "Respond warmly and propose a brief 10-minute call."),
        "suggested_response": {
            "subject": subject,
            "body": body
        },
        "standard_retainers": MONTHLY_RETAINER_PACKAGES
    }


def qualify_lead(lead_row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Scores and qualifies a lead for sales viability.
    Returns viability grade (HOT / WARM / COLD) and BDE action score.
    """
    comp = lead_row.get("company_name") or ""
    if is_excluded_company(comp):
        return {
            "grade": "EXCLUDED",
            "score": 0,
            "reason": "Company on exclusion blacklist."
        }

    score = 5
    signals = []

    # Has direct contact information
    if lead_row.get("email"):
        score += 2
        signals.append("Verified email available")
    if lead_row.get("mobile_number"):
        score += 2
        signals.append("Phone/WhatsApp available")

    # Has clear website
    if lead_row.get("website"):
        score += 1
        signals.append("Active website domain")

    # Has high intent keywords
    desc = (lead_row.get("description") or "").lower()
    if any(k in desc for k in ("urgent", "hire", "looking for", "need developer", "budget", "rfp", "migration")):
        score += 2
        signals.append("Strong buyer intent indicators")

    final_score = min(score, 10)
    grade = "HOT" if final_score >= 8 else ("WARM" if final_score >= 6 else "COLD")

    return {
        "company_name": comp,
        "bde_score": final_score,
        "grade": grade,
        "signals": signals,
        "recommended_action": "Immediate Outreach" if grade == "HOT" else "Standard Email Sequence"
    }

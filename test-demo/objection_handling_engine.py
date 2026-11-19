"""
Objection Handling & Conversion Engine
======================================
Provides structured, battle-tested response templates and monthly retainer packaging
for inbound prospect replies, turning questions into closed deals.

Supported Inbound Scenarios:
1. Portfolio / Case Study Requests
2. Agency Model & Team Location Inquiries
3. Timezone Coverage (US EST/PST & UK GMT Overlap)
4. Pricing, Retainer Packages & 7-Day Risk-Free Trial Sprints
5. "We are happy with our current team" (Parallel Capacity Pod positioning)
6. Opt-Out / Suppression handling
"""

import re
from typing import Dict, Any, Tuple, Optional, List

# Standard Retainer Packages
MONTHLY_RETAINER_PACKAGES = [
    {
        "id": "part-time-dedicated",
        "name": "Part-Time Dedicated Developer",
        "hours_per_month": 80,
        "hourly_rate_inr": 450,
        "price_inr": 36000,
        "price_usd": 435,
        "team": "1 Dedicated Senior Full-Stack Developer",
        "delivery": "Agile sprints, weekly demo, task tracking, source-code ownership",
        "communication": "Agreed overlap window and async updates (Slack/Teams/Jira)",
        "best_for": "Website maintenance, feature backlog, bug fixes, integrations, small MVPs",
        "trial_clause": (
            "7-Day Risk-Free Trial: Begin with a fixed-scope 7-day trial sprint covering one narrowly defined deliverable. "
            "If you are not satisfied with communication, code quality, or delivery progress by the end of the trial, "
            "you may discontinue with no further commitment. Work completed during the trial remains yours."
        )
    },
    {
        "id": "full-time-dedicated",
        "name": "Full-Time Dedicated Developer",
        "hours_per_month": 160,
        "hourly_rate_inr": 450,
        "price_inr": 72000,
        "price_usd": 870,
        "team": "1 Dedicated Senior Full-Stack Developer + Dedicated PM/QA",
        "delivery": "Sprint planning, weekly demos, backlog grooming, automated deployment",
        "communication": "Daily standup option, agreed daily overlap window, dedicated Slack/Teams channel",
        "best_for": "Ongoing product development, CRM/ERP builds, mobile apps, platform scaling",
        "trial_clause": (
            "7-Day Risk-Free Trial: Start with a one-week, fixed-scope trial sprint. We will deliver a defined milestone, "
            "provide a progress demo, and share all work in your repository. If the quality, communication, or delivery approach "
            "does not meet your expectations, you may end the engagement at the end of the trial with no further obligation."
        )
    }
]

OBJECTION_RULES = [
    (
        "portfolio",
        re.compile(r"(portfolio|case\s*stud|previous\s*work|examples|sample|live\s*work|show\s*me\s*work)", re.I)
    ),
    (
        "agency_model",
        re.compile(r"(agency|freelance|where\s*are\s*you\s*located|team\s*size|company|office|location)", re.I)
    ),
    (
        "timezone",
        re.compile(r"(timezone|time\s*zone|est|pst|gmt|cst|overlap|working\s*hours|hours\s*overlap)", re.I)
    ),
    (
        "pricing_trial",
        re.compile(r"(how\s*does\s*it\s*work|pricing|package|cost|rate|minimum|commitment|trial|contract|monthly)", re.I)
    ),
    (
        "happy_with_current",
        re.compile(r"(happy\s*with|already\s*have|existing\s*team|current\s*agency|current\s*dev|not\s*looking\s*to\s*switch)", re.I)
    ),
    (
        "opt_out",
        re.compile(r"^(unsubscribe|stop|remove|not\s*interested|no\s*thanks|no)$", re.I)
    )
]


def classify_objection(inbound_text: str) -> str:
    """Classifies incoming prospect reply into a known objection or question category."""
    text = inbound_text.strip()
    for cat, pattern in OBJECTION_RULES:
        if pattern.search(text):
            return cat
    return "general_inquiry"


def get_objection_response(
    category: str,
    contact_name: str = "there",
    company_name: str = "your company",
    specific_need: str = "web and software operations",
    sender_name: str = "Business Development Team"
) -> Tuple[str, str]:
    """
    Generates a personalized, high-converting response for the detected objection category.
    Returns (subject, body).
    """
    name = contact_name.strip() or "there"
    comp = company_name.strip() or "your company"
    need = specific_need.strip() or "web and software development"

    if category == "portfolio":
        subject = f"Relevant work examples for {comp}"
        body = (
            f"Hi {name},\n\n"
            f"Absolutely. Here are a few examples closest to **{comp}**'s needs:\n\n"
            f"- **Web & Cloud Applications:** Custom Laravel and Next.js business platforms with automated CI/CD pipelines.\n"
            f"- **High-Performance Mobile Apps:** Cross-platform Flutter and React Native apps with offline sync and sub-second API speeds.\n"
            f"- **CRM & ERP Systems:** End-to-end custom business portals integrating HubSpot, Salesforce, and custom database workflows.\n\n"
            f"For confidentiality reasons, certain client names are under NDA, but I can walk you through the technical architecture, delivery milestones, and code standards.\n\n"
            f"For your **{need}**, I can also prepare a short one-page technical plan showing exactly how we would approach it.\n\n"
            f"Would you like me to send that over?\n\n"
            f"Best regards,\n"
            f"{sender_name}\n"
            f"**Sangeeta Infotech**"
        )
        return subject, body

    elif category == "agency_model":
        subject = f"Our team and delivery model for {comp}"
        body = (
            f"Hi {name},\n\n"
            f"We are **Sangeeta Infotech**, an established software engineering agency based in Ahmedabad, Gujarat, India—not a marketplace of unvetted freelancers.\n\n"
            f"Our team brings **5+ years of experience** building software for **80+ clients**. We provide dedicated full-stack developers, QA engineers, and technical project coordinators under one transparent delivery model.\n\n"
            f"You get a named senior developer, weekly demos, clear written updates, and complete source-code ownership in your Git repository. We build using the **latest AI tools and modern technologies** to ensure fast, clean delivery.\n\n"
            f"To evaluate our communication and code quality with zero risk, we can start with a small fixed-scope milestone or pilot.\n\n"
            f"Would a brief 10-minute call to review your current roadmap be useful?\n\n"
            f"Best regards,\n"
            f"{sender_name}\n"
            f"**Sangeeta Infotech**"
        )
        return subject, body

    elif category == "timezone":
        subject = f"Time-zone coverage and overlap for {comp}"
        body = (
            f"Hi {name},\n\n"
            f"Yes, absolutely. We regularly align our working hours with **US EST/PST** and **UK GMT** business windows.\n\n"
            f"Our standard international collaboration framework includes:\n"
            f"- A mutually agreed **daily 3 to 4-hour live overlap window** for standups, syncs, and real-time pair programming.\n"
            f"- Structured async updates and task tracking via Slack, Microsoft Teams, Jira, or Linear.\n"
            f"- Weekly sprint demos and transparent milestone handovers directly in your repository.\n\n"
            f"For urgent production maintenance or bug fixes, we also provide priority SLA arrangements.\n\n"
            f"Would a quick 10-minute chat help us agree on a practical overlap schedule for your team?\n\n"
            f"Best regards,\n"
            f"{sender_name}\n"
            f"**Sangeeta Infotech**"
        )
        return subject, body

    elif category == "pricing_trial":
        subject = f"How our ₹450/hour dedicated model works for {comp}"
        body = (
            f"Hi {name},\n\n"
            f"Our dedicated developer model starts at **₹450/- INR / hour** (~$5.5 USD/hr) and is designed to give you senior engineering capacity without permanent hiring overhead.\n\n"
            f"We offer two standard transparent retainers:\n"
            f"1. **Part-Time Dedicated (80 hrs/month):** ₹36,000/- INR / month (~$435 USD) — Ideal for website maintenance, bug fixes, CRM integrations, and feature backlogs.\n"
            f"2. **Full-Time Dedicated (160 hrs/month):** ₹72,000/- INR / month (~$870 USD) — Ideal for active product builds, mobile app releases, and platform scaling.\n\n"
            f"**7-Day Risk-Free Trial:** We start with a fixed-scope 7-day trial sprint on a clearly defined deliverable. If our communication, code quality, or speed does not meet your expectations, you can walk away at the end of the trial with zero further commitment, and all code remains yours.\n\n"
            f"Would you like me to propose a trial scope for your **{need}**?\n\n"
            f"Best regards,\n"
            f"{sender_name}\n"
            f"**Sangeeta Infotech**"
        )
        return subject, body

    elif category == "happy_with_current":
        subject = f"A parallel capacity option for {comp}"
        body = (
            f"Hi {name},\n\n"
            f"That is great to hear—having a trusted, reliable development team is essential.\n\n"
            f"We would never suggest replacing an engineering team that is already performing well. Instead, we typically act as a **parallel capacity pod** for bounded work that creates an internal backlog, such as:\n"
            f"- Third-party API and CRM integrations.\n"
            f"- Performance and Core Web Vitals speed optimization.\n"
            f"- Mobile app feature extensions.\n"
            f"- Routine website maintenance, security updates, and bug fixes.\n\n"
            f"Your in-house team remains 100% focused on core roadmap items, while we clear the secondary backlog at our dedicated rate of just **₹450/- INR / hour**.\n\n"
            f"Would it be helpful to see a short one-page plan for a standalone workstream?\n\n"
            f"Best regards,\n"
            f"{sender_name}\n"
            f"**Sangeeta Infotech**"
        )
        return subject, body

    elif category == "opt_out":
        subject = f"Confirmation of removal — {comp}"
        body = (
            f"Hi {name},\n\n"
            f"Understood. You have been permanently removed from our outreach list, and we will not contact you again.\n\n"
            f"Wishing **{comp}** continued success.\n\n"
            f"Best regards,\n"
            f"{sender_name}\n"
            f"**Sangeeta Infotech**"
        )
        return subject, body

    else:
        subject = f"Software engineering support for {comp}"
        body = (
            f"Hi {name},\n\n"
            f"Thank you for getting back to me regarding **{comp}**.\n\n"
            f"At **Sangeeta Infotech**, our team brings **5+ years of experience** and **80+ completed projects** across modern web, mobile apps, and CRM integrations. We provide dedicated developers starting from **₹450/- INR / hour** with modern AI-accelerated workflows.\n\n"
            f"Could you share a few details on what you are currently prioritizing, or would you be open to a brief **10-minute chat** this week?\n\n"
            f"Best regards,\n"
            f"{sender_name}\n"
            f"**Sangeeta Infotech**"
        )
        return subject, body

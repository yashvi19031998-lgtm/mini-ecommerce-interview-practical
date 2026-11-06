"""
Outreach Dispatcher & WhatsApp / Email Lead Campaign Manager
============================================================
Targets Hot Leads (Score >= 7) from all_leads_master.csv:
1. Generates 1-Click WhatsApp Direct Chat links with pre-filled senior pitch.
2. Dispatches SMTP Cold Emails (with safety duplicate blocking) when credentials are provided.
3. Generates Direct Message links for Reddit / Platform buyers.
"""

import os
import re
import csv
import urllib.parse
from typing import List, Dict, Any

try:
    import env_loader
except ImportError:
    pass

import email_service
from lead_normalizer import MasterLeadRegistry

MASTER_CSV = "all_leads_master.csv"
HOT_LEAD_MIN_SCORE = 7


def load_hot_leads(master_csv: str = MASTER_CSV) -> List[Dict[str, Any]]:
    """Loads all leads with AI Score >= 7."""
    if not os.path.exists(master_csv):
        return []
    hot = []
    with open(master_csv, mode="r", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            score_str = str(row.get("ai_score") or "").strip()
            if score_str.isdigit() and int(score_str) >= HOT_LEAD_MIN_SCORE:
                hot.append(row)
    # Sort highest score first
    hot.sort(key=lambda r: int(r.get("ai_score", 0)), reverse=True)
    return hot


def clean_phone_for_whatsapp(phone_str: str) -> str:
    """Formats phone number into clean international digits for wa.me URL."""
    digits = re.sub(r"\D", "", phone_str)
    # If 10 digits Indian mobile, prepend 91
    if len(digits) == 10 and digits[0] in "6789":
        return "91" + digits
    if len(digits) == 11 and digits.startswith("0"):
        return "91" + digits[1:]
    return digits


def build_whatsapp_pitch(lead: Dict[str, Any]) -> str:
    """Generates a high-converting, professional WhatsApp pitch tailored to 8-9+ yrs experience."""
    name = lead.get("full_name") or lead.get("company_name") or "there"
    tech = lead.get("ai_tech_stack") or "Full-Stack Web & Mobile App Development"
    
    msg = (
        f"Hi {name}, I noticed your requirement regarding {tech}.\n\n"
        f"I'm reaching out from Sangeeta Infotech. Our senior engineering team brings 8–9+ years of experience "
        f"building scalable web architectures (Next.js/React, Node.js, Python), cross-platform mobile apps (Flutter), "
        f"and custom AI systems.\n\n"
        f"We'd love to help you deliver this with clean code and high velocity. Would you be open to a quick 5-min chat today?"
    )
    return msg


def generate_whatsapp_campaign(leads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filters leads with phone numbers and creates 1-click wa.me action links."""
    campaign = []
    for lead in leads:
        phones = str(lead.get("mobile_number") or "").split(",")
        for p in phones:
            cleaned = clean_phone_for_whatsapp(p.strip())
            if len(cleaned) >= 10:
                pitch = build_whatsapp_pitch(lead)
                encoded_msg = urllib.parse.quote(pitch)
                wa_link = f"https://wa.me/{cleaned}?text={encoded_msg}"
                campaign.append({
                    "lead_id": lead.get("lead_id"),
                    "company": lead.get("company_name") or "Client",
                    "phone": p.strip(),
                    "wa_link": wa_link,
                    "score": lead.get("ai_score"),
                    "tech": lead.get("ai_tech_stack") or "Software Engineering",
                    "pitch": pitch
                })
                break
    return campaign


def build_email_pitch(lead: Dict[str, Any]) -> tuple[str, str]:
    """Crafts personalized cold email subject & body."""
    company = lead.get("company_name") or "your project"
    tech = lead.get("ai_tech_stack") or "Software Engineering"
    name = lead.get("full_name") or "there"

    subject = f"Senior Engineering Support for {company} (Next.js / Node / Mobile)"
    body = (
        f"Hi {name},\n\n"
        f"I came across {company} and your current development requirements around {tech}.\n\n"
        f"At Sangeeta Infotech (Ahmedabad, India), we are a senior software development agency with 8–9+ years "
        f"of proven track record in end-to-end product engineering. We help founders and engineering teams scale fast with:\n"
        f"• High-performance Full-Stack Web Apps (Next.js 15, React, Node.js, Python/FastAPI)\n"
        f"• Mobile Apps (Flutter, React Native iOS & Android)\n"
        f"• Scalable Cloud Architecture & AI Integrations\n\n"
        f"We have dedicated senior developers and leads ready to contribute immediately with flexible engagement models.\n\n"
        f"Would you be open to a brief 10-minute discovery call this week to see if we're a good fit?\n\n"
        f"Warm regards,\n"
        f"Business Development Team | Sangeeta Infotech\n"
        f"📞 Phone/WhatsApp: +91 9106060400 / +91 9426738067\n"
        f"🌐 Website: https://sangeetainfotech.co.in\n"
        f"📍 Ahmedabad, Gujarat, India"
    )
    return subject, body


def run_email_outreach(batch_limit: int = 5) -> Dict[str, Any]:
    """Dispatches cold emails to uncontacted hot leads if SMTP is configured."""
    user = os.getenv("SMTP_USER", "").strip()
    passwd = os.getenv("SMTP_PASS", "").strip()

    if not user or not passwd:
        return {
            "status": "credentials_needed",
            "message": "SMTP_USER and SMTP_PASS are not configured in .env yet."
        }

    registry = MasterLeadRegistry(MASTER_CSV)
    hot_email_leads = [
        l for l in registry.leads 
        if str(l.get("ai_score") or "").isdigit() 
        and int(l.get("ai_score")) >= HOT_LEAD_MIN_SCORE 
        and l.get("email") 
        and str(l.get("email_status", "")).upper() != "SENT"
    ]

    sent_count = 0
    failed_count = 0

    print(f"[*] Starting Email Outreach (Found {len(hot_email_leads)} uncontacted Hot Leads, Batch Limit: {batch_limit})...")

    for lead in hot_email_leads[:batch_limit]:
        to_email = lead.get("email", "").split(",")[0].strip()
        subject, body = build_email_pitch(lead)

        res = email_service.send_smtp_email(to_email=to_email, subject=subject, message_body=body)
        if res.get("success"):
            sent_count += 1
            lead["email_status"] = "SENT"
            lead["email_sent_at"] = os.popen('python -c "import time; print(time.strftime(\'%Y-%m-%d %H:%M:%S\'))"').read().strip()
            lead["status"] = "CONTACTED"
            print(f"    [+] Sent to {to_email} ({lead.get('company_name')})")
        else:
            failed_count += 1
            print(f"    [-] Failed to send to {to_email}: {res.get('error')}")

    if sent_count > 0:
        registry.save_master_safely()

    return {
        "status": "success",
        "sent": sent_count,
        "failed": failed_count,
        "remaining": max(0, len(hot_email_leads) - sent_count)
    }


def export_outreach_html_report(output_file: str = "hot_leads_outreach.html"):
    """Creates a beautiful interactive HTML dashboard to launch WhatsApp & Email outreach with 1 click."""
    hot = load_hot_leads()
    wa_leads = generate_whatsapp_campaign(hot)
    email_leads = [l for l in hot if l.get("email")]

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Sangeeta Infotech - Hot Leads Outreach Hub</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 24px; }}
  .container {{ max-width: 1200px; margin: 0 auto; }}
  h1 {{ color: #38bdf8; margin-bottom: 6px; }}
  p.subtitle {{ color: #94a3b8; margin-top: 0; margin-bottom: 24px; font-size: 15px; }}
  .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-bottom: 28px; }}
  .stat-card {{ background: #1e293b; padding: 18px; border-radius: 10px; border: 1px solid #334155; }}
  .stat-val {{ font-size: 28px; font-weight: bold; color: #38bdf8; }}
  .stat-lbl {{ color: #94a3b8; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px; }}
  .section {{ background: #1e293b; border-radius: 12px; border: 1px solid #334155; padding: 20px; margin-bottom: 28px; }}
  h2 {{ color: #f1f5f9; font-size: 18px; border-bottom: 1px solid #334155; padding-bottom: 10px; margin-top: 0; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 14px; }}
  th {{ text-align: left; padding: 10px 12px; background: #0f172a; color: #94a3b8; font-weight: 600; }}
  td {{ padding: 12px; border-bottom: 1px solid #334155; vertical-align: middle; }}
  .badge-score {{ background: #0284c7; color: white; padding: 3px 8px; border-radius: 12px; font-weight: bold; font-size: 12px; }}
  .badge-score-10 {{ background: #10b981; }}
  .btn-wa {{ background: #22c55e; color: white; text-decoration: none; padding: 8px 14px; border-radius: 6px; font-weight: 600; display: inline-flex; align-items: center; gap: 6px; font-size: 13px; transition: background 0.2s; }}
  .btn-wa:hover {{ background: #16a34a; }}
  .btn-email {{ background: #6366f1; color: white; text-decoration: none; padding: 8px 14px; border-radius: 6px; font-weight: 600; font-size: 13px; }}
  .btn-email:hover {{ background: #4f46e5; }}
  .btn-reddit {{ background: #ff4500; color: white; text-decoration: none; padding: 6px 12px; border-radius: 6px; font-weight: 600; font-size: 12px; }}
</style>
</head>
<body>
<div class="container">
  <h1>Sangeeta Infotech - 119 Hot Leads Outreach Hub</h1>
  <p class="subtitle">High-Intent Senior Client Leads (Score 7 to 10) Ready for 1-Click WhatsApp & Email Outreach.</p>

  <div class="stats-grid">
    <div class="stat-card"><div class="stat-val">{len(hot)}</div><div class="stat-lbl">Total Hot Leads (Score 7-10)</div></div>
    <div class="stat-card"><div class="stat-val" style="color:#22c55e;">{len(wa_leads)}</div><div class="stat-lbl">1-Click WhatsApp Ready</div></div>
    <div class="stat-card"><div class="stat-val" style="color:#818cf8;">{len(email_leads)}</div><div class="stat-lbl">Verified Email Leads</div></div>
  </div>

  <!-- WhatsApp Outreach Section -->
  <div class="section">
    <h2>📱 WhatsApp Direct 1-Click Outreach ({len(wa_leads)} Leads)</h2>
    <table>
      <thead>
        <tr>
          <th>Score</th>
          <th>Lead / Company</th>
          <th>Phone</th>
          <th>Tech Stack / Scope</th>
          <th>Action</th>
        </tr>
      </thead>
      <tbody>
"""
    for l in wa_leads:
        score_cls = "badge-score-10" if int(l['score']) >= 9 else ""
        html_content += f"""        <tr>
          <td><span class="badge-score {score_cls}">{l['score']}/10</span></td>
          <td><strong>{l['company']}</strong></td>
          <td>{l['phone']}</td>
          <td>{l['tech']}</td>
          <td><a class="btn-wa" href="{l['wa_link']}" target="_blank">💬 Open WhatsApp Chat</a></td>
        </tr>\n"""

    html_content += """      </tbody>
    </table>
  </div>

  <!-- Email Outreach Section -->
  <div class="section">
    <h2>✉️ Verified Email Hot Leads</h2>
    <table>
      <thead>
        <tr>
          <th>Score</th>
          <th>Company</th>
          <th>Email Address</th>
          <th>Requirement / Summary</th>
          <th>Action</th>
        </tr>
      </thead>
      <tbody>
"""
    for l in email_leads[:25]:
        score_cls = "badge-score-10" if int(l.get('ai_score', 0)) >= 9 else ""
        subj, body = build_email_pitch(l)
        mailto = f"mailto:{l['email']}?subject={urllib.parse.quote(subj)}&body={urllib.parse.quote(body)}"
        html_content += f"""        <tr>
          <td><span class="badge-score {score_cls}">{l.get('ai_score')}/10</span></td>
          <td><strong>{l.get('company_name') or 'Client'}</strong></td>
          <td>{l.get('email')}</td>
          <td>{l.get('ai_summary') or l.get('ai_requirement') or 'Software Development'}</td>
          <td><a class="btn-email" href="{mailto}">✉️ Send Email</a></td>
        </tr>\n"""

    html_content += """      </tbody>
    </table>
  </div>
</div>
</body>
</html>
"""
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"[*] [OK] Generated interactive outreach dashboard at: '{output_file}'")
    return output_file


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Outreach Campaign Manager")
    parser.add_argument("--auto", action="store_true", help="Automatically dispatch cold emails to hot leads via SMTP")
    parser.add_argument("--batch", type=int, default=5, help="Batch limit per run (default: 5)")
    parser.add_argument("--report", action="store_true", help="Generate interactive HTML outreach dashboard")
    args = parser.parse_args()

    if args.auto:
        print("[*] Running Automated Cold Email Outreach for Hot Leads...")
        res = run_email_outreach(batch_limit=args.batch)
        print(f"[*] Result: {res}")
    else:
        report_path = export_outreach_html_report()
        print("[*] Outreach Hub Report Ready at 'hot_leads_outreach.html'!")
        print("[*] Tip: Run 'python outreach_manager.py --auto' to dispatch automated emails.")

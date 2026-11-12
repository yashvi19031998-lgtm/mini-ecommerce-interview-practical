"""
Lead Importer & Auto-Engine Module
==================================
Inspired by modern Next.js job/lead import engines:
1. Targeted Live Search Scraper (Keywords + Location + Target Types)
2. WhatsApp / Telegram Chat Export Parser (.txt / raw chat strings)
3. Raw Job & Project Description / URL Extractor (Deep crawler & contact finder)
4. Duplicate Prevention against all_leads_master.csv
5. Safe Commit to Master CSV + Instant Supabase Cloud Sync + Optional Outreach
"""

import os
import re
import time
import datetime
from typing import List, Dict, Any, Tuple
from urllib.parse import urlparse, urljoin
import requests
from bs4 import BeautifulSoup

from lead_normalizer import (
    MasterLeadRegistry,
    normalize_email,
    normalize_phone,
    canonicalize_domain,
    clean_text,
    clean_url,
    INVALID_DOMAINS
)

try:
    import sync_to_supabase
except ImportError:
    sync_to_supabase = None

try:
    from email_service import send_smtp_email
    from settings_manager import load_settings, format_signature
except ImportError:
    send_smtp_email = None
    load_settings = None
    format_signature = None


# Regex for Email, Phone, URLs
EMAIL_REGEX = re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+')
PHONE_REGEX = re.compile(r'(\+?\d[\d\s\-\(\)]{8,15}\d)')
URL_REGEX = re.compile(r'https?://[^\s<>"]+|www\.[^\s<>"]+')

# WhatsApp Timestamp Matchers (supports multiple formats: 12/10/24, 10:30 am - Name: ... or [12/10/24, 10:30:15] Name: ...)
WHATSAPP_LINE_REGEX = re.compile(
    r'^(?:\[?(\d{1,2}[\/.-]\d{1,2}[\/.-]\d{2,4}[,\s]+(?:\d{1,2}:\d{2}(?::\d{2})?\s*(?:[ap]m)?))\]?\s*[-–:]?\s*)'
    r'([^:]+):\s*(.*)$',
    re.IGNORECASE
)

# Generic chat date line without sender (e.g., system messages)
WHATSAPP_SYSTEM_REGEX = re.compile(
    r'^(?:\[?(\d{1,2}[\/.-]\d{1,2}[\/.-]\d{2,4}[,\s]+(?:\d{1,2}:\d{2}(?::\d{2})?\s*(?:[ap]m)?))\]?\s*[-–:]?\s*)(.*)$',
    re.IGNORECASE
)

# Client intent keywords vs chit-chat filters
CLIENT_INTENT_KEYWORDS = [
    'hiring', 'looking for', 'need a', 'need an', 'required', 'requirement',
    'developer', 'designer', 'freelancer', 'agency', 'budget', 'urgent',
    'project', 'full time', 'part time', 'contract', 'remote', 'work from home',
    'salary', 'experience', 'skills', 'react', 'python', 'flutter', 'node',
    'php', 'laravel', 'wordpress', 'shopify', 'mobile app', 'frontend', 'backend'
]

CHAT_IGNORE_PHRASES = [
    'messages and calls are end-to-end encrypted',
    'left the group', 'joined using this group\'s invite link',
    'changed the group description', 'changed this group\'s icon',
    '<media omitted>', 'image omitted', 'video omitted', 'sticker omitted',
    'good morning', 'good night', 'thanks', 'thank you', 'ok', 'okay', 'done'
]


def is_hiring_or_lead_message(text: str) -> bool:
    """Classifies whether a text message contains actual hiring intent or project lead."""
    t_lower = text.lower()
    if any(ig in t_lower for ig in CHAT_IGNORE_PHRASES) and len(text) < 60:
        return False
    # If it has client intent keywords or contact details
    has_kw = any(kw in t_lower for kw in CLIENT_INTENT_KEYWORDS)
    has_contact = bool(EMAIL_REGEX.search(text) or PHONE_REGEX.search(text))
    return (has_kw and len(text.split()) >= 4) or (has_contact and len(text.split()) >= 6)


def extract_contacts_from_text(text: str) -> Dict[str, str]:
    """Extracts cleaned email, phone, links from freeform text."""
    # Emails
    raw_emails = EMAIL_REGEX.findall(text)
    clean_emails = []
    for em in raw_emails:
        norm = normalize_email(em)
        if norm and not any(norm.endswith(ext) for ext in ('.png', '.jpg', '.jpeg', '.gif', '.webp')):
            clean_emails.append(norm)

    # Phones
    raw_phones = PHONE_REGEX.findall(text)
    clean_phones = []
    for ph in raw_phones:
        norm_ph = normalize_phone(ph)
        digits = re.sub(r'\D', '', norm_ph)
        if len(digits) >= 10:
            clean_phones.append(norm_ph)

    # URLs
    raw_urls = URL_REGEX.findall(text)
    clean_urls = []
    for u in raw_urls:
        if not u.startswith(('http://', 'https://')):
            u = 'https://' + u
        dom = canonicalize_domain(u)
        if dom and dom not in INVALID_DOMAINS:
            clean_urls.append(u)

    return {
        "email": ", ".join(sorted(set(clean_emails))),
        "phone": clean_phones[0] if clean_phones else "",
        "website": clean_urls[0] if clean_urls else ""
    }


def parse_whatsapp_chat(chat_text: str) -> List[Dict[str, Any]]:
    """
    Parses exported WhatsApp chat text (.txt or .zip string) into candidate lead records.
    Splits multi-line messages accurately and detects client requirements.
    """
    if isinstance(chat_text, str) and chat_text.startswith("PK\x03\x04"):
        import zipfile, io
        try:
            with zipfile.ZipFile(io.BytesIO(chat_text.encode("latin-1"))) as z:
                txt_files = [n for n in z.namelist() if n.lower().endswith(".txt")]
                if txt_files:
                    target = "_chat.txt" if "_chat.txt" in txt_files else max(txt_files, key=lambda n: z.getinfo(n).file_size)
                    chat_text = z.read(target).decode("utf-8", errors="ignore")
        except Exception:
            pass

    lines = chat_text.splitlines()
    messages = []
    current_msg = None

    for line in lines:
        line_clean = line.strip()
        if not line_clean:
            continue

        match = WHATSAPP_LINE_REGEX.match(line_clean)
        if match:
            # Save previous message
            if current_msg and is_hiring_or_lead_message(current_msg["text"]):
                messages.append(current_msg)

            timestamp, sender, text = match.groups()
            current_msg = {
                "timestamp": timestamp.strip(),
                "sender": sender.strip(),
                "text": text.strip()
            }
        else:
            # Continuation of previous message (capped at 5,000 chars to prevent regex stalling)
            if current_msg:
                if len(current_msg["text"]) < 5000:
                    current_msg["text"] += "\n" + line_clean
            else:
                if len(line_clean) < 5000:
                    current_msg = {
                        "timestamp": "",
                        "sender": "Unknown Sender",
                        "text": line_clean
                    }

    # Don't forget last message
    if current_msg and is_hiring_or_lead_message(current_msg["text"]):
        messages.append(current_msg)

    parsed_leads = []
    for idx, msg in enumerate(messages, start=1):
        text = msg["text"]
        contacts = extract_contacts_from_text(text)
        
        # Derive title from first line or snippet
        first_line = text.split("\n")[0].strip()
        title = first_line[:90] if len(first_line) > 10 else f"Client Requirement #{idx}"

        # Deduce company name
        company_candidate = msg["sender"]
        if re.match(r'^\+?\d[\d\s\-]+$', company_candidate):
            # Sender is just a phone number, extract company from text or use phone
            company_candidate = f"WhatsApp Client ({company_candidate[-10:]})"

        parsed_leads.append({
            "lead_id": f"IMPORT-WA-{int(time.time())}-{idx:02d}",
            "company_name": company_candidate,
            "full_name": msg["sender"],
            "title": title,
            "email": contacts["email"],
            "mobile_number": contacts["phone"] or (msg["sender"] if re.match(r'^\+?\d[\d\s\-]{8,}$', msg["sender"]) else ""),
            "website": contacts["website"],
            "description": text[:350].strip(),
            "source": f"WhatsApp Chat Export ({msg['timestamp']})" if msg['timestamp'] else "WhatsApp Chat Export",
            "source_url": "",
            "location": "Remote",
            "lead_type": "WhatsApp Client Requirement",
            "intent_score": "8"
        })

    return parsed_leads


def parse_raw_text(raw_text: str, crawl_urls: bool = True) -> List[Dict[str, Any]]:
    """
    Parses pasted text or URLs into structured leads.
    If links are present and crawl_urls is True, visits links to fetch titles & meta info.
    """
    leads = []
    # Check if input is a list of URLs (one per line)
    potential_urls = [line.strip() for line in raw_text.splitlines() if line.strip().startswith(('http://', 'https://', 'www.'))]

    if len(potential_urls) >= 1 and len(potential_urls) == len([l for l in raw_text.splitlines() if l.strip()]):
        # Batch of URLs
        for idx, u in enumerate(potential_urls, start=1):
            if not u.startswith(('http://', 'https://')):
                u = 'https://' + u
            
            title = canonicalize_domain(u).title()
            description = f"Imported lead from {u}"
            email = ""
            phone = ""

            if crawl_urls:
                try:
                    resp = requests.get(u, headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
                    if resp.status_code == 200:
                        soup = BeautifulSoup(resp.text, "html.parser")
                        if soup.title and soup.title.string:
                            title = soup.title.string.strip()[:90]
                        og_desc = soup.find("meta", property="og:description") or soup.find("meta", attrs={"name": "description"})
                        if og_desc and og_desc.get("content"):
                            description = og_desc["content"].strip()[:350]
                        
                        contacts = extract_contacts_from_text(resp.text)
                        email = contacts["email"]
                        phone = contacts["phone"]
                except Exception:
                    pass

            leads.append({
                "lead_id": f"IMPORT-URL-{int(time.time())}-{idx:02d}",
                "company_name": canonicalize_domain(u).title() or f"Company #{idx}",
                "title": title,
                "email": email,
                "mobile_number": phone,
                "website": u,
                "source": "Manual URL Import",
                "source_url": u,
                "description": description,
                "location": "Remote",
                "lead_type": "Imported Company URL",
                "intent_score": "7"
            })
    else:
        # Paragraph or multi-block pasted text
        blocks = re.split(r'\n\s*[-=_*]{3,}\s*\n|\n\s*\n\s*\n', raw_text)
        if len(blocks) == 1 and len(raw_text.splitlines()) > 5:
            # Try splitting by double newline
            blocks = raw_text.split("\n\n")

        for idx, block in enumerate(blocks, start=1):
            block_clean = block.strip()
            if len(block_clean) < 15:
                continue

            contacts = extract_contacts_from_text(block_clean)
            lines = [l.strip() for l in block_clean.splitlines() if l.strip()]
            first_line = lines[0] if lines else f"Pasted Requirement #{idx}"

            # Detect company or title
            comp_match = re.search(r'(?:at|company|client|firm)[:\s]+([A-Za-z0-9\s.,&-]{2,40})', block_clean, re.I)
            comp_name = comp_match.group(1).strip() if comp_match else ""
            if not comp_name:
                dom = canonicalize_domain(contacts["website"])
                comp_name = dom.title() if dom else f"Client #{idx}"

            leads.append({
                "lead_id": f"IMPORT-TXT-{int(time.time())}-{idx:02d}",
                "company_name": comp_name,
                "title": first_line[:90],
                "email": contacts["email"],
                "mobile_number": contacts["phone"],
                "website": contacts["website"],
                "source": "Pasted Description Import",
                "source_url": contacts["website"],
                "description": block_clean[:350].strip(),
                "location": "Remote",
                "lead_type": "Pasted Requirement Lead",
                "intent_score": "8"
            })

    return leads


# Live Search moved to search_engine.py (Scraping / Mining -> Search Engines).


MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_MASTER_CSV = os.path.join(MODULE_DIR, "all_leads_master.csv")

def check_duplicates_against_master(leads: List[Dict[str, Any]], master_csv: str = DEFAULT_MASTER_CSV) -> List[Dict[str, Any]]:
    """
    Checks each candidate lead against MasterLeadRegistry.
    Adds 'is_duplicate': True/False and 'match_reason': str to each lead dict.
    """
    if not os.path.isabs(master_csv) and not os.path.exists(master_csv):
        master_csv = os.path.join(MODULE_DIR, master_csv)
    registry = MasterLeadRegistry(master_csv)
    enriched_leads = []

    for lead in leads:
        match_idx = registry.find_match(lead)
        lead_copy = dict(lead)
        if match_idx is not None:
            existing = registry.leads[match_idx]
            lead_copy["is_duplicate"] = True
            lead_copy["match_reason"] = f"Duplicate: matches {existing.get('company_name', 'Lead')} (#{existing.get('lead_id', match_idx)})"
        else:
            lead_copy["is_duplicate"] = False
            lead_copy["match_reason"] = "New Unique Lead"

        enriched_leads.append(lead_copy)

    return enriched_leads


def commit_imported_leads(leads_to_commit: List[Dict[str, Any]], send_outreach_email: bool = False, master_csv: str = DEFAULT_MASTER_CSV) -> Dict[str, Any]:
    """
    Saves selected leads into all_leads_master.csv safely using MasterLeadRegistry,
    triggers direct sync to Supabase, and optionally dispatches emails immediately.
    """
    if not os.path.isabs(master_csv) and not os.path.exists(master_csv):
        master_csv = os.path.join(MODULE_DIR, master_csv)
    registry = MasterLeadRegistry(master_csv)
    added_count = 0
    updated_count = 0
    duplicates_count = 0
    emails_sent_count = 0

    settings = load_settings() if load_settings else {}
    sig = format_signature(settings) if format_signature else ""
    sub_tpl = settings.get("defaultSubject", "Web & Software Engineering Collaboration - {company}")
    msg_tpl = settings.get("defaultMessage", "Hi {name},\n\nI came across {company}...")

    for lead in leads_to_commit:
        outcome, lead_obj = registry.add_lead(lead, default_source="Import Leads Module")
        if outcome == "added":
            added_count += 1
            if send_outreach_email and send_smtp_email and isinstance(lead_obj, dict):
                raw_email = str(lead_obj.get("email", "")).split(",")[0].strip()
                if raw_email and "@" in raw_email and raw_email.upper() != "N/A":
                    comp_name = lead_obj.get("company_name") or "your company"
                    loc_name = lead_obj.get("location") or "your region"
                    custom_sub = sub_tpl.replace("{company}", comp_name).replace("{name}", comp_name).replace("{location}", loc_name)
                    custom_msg = msg_tpl.replace("{company}", comp_name).replace("{name}", comp_name).replace("{location}", loc_name)
                    if sig and sig.strip()[:20] not in custom_msg:
                        custom_msg = f"{custom_msg}\n\n---\n{sig.strip()}"

                    res = send_smtp_email(raw_email, custom_sub, custom_msg)
                    if res.get("success"):
                        lead_obj["email_status"] = "SENT"
                        lead_obj["email_sent_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        emails_sent_count += 1
                        import followup_store
                        followup_store.safe_log(lead_obj.get("lead_id", ""), "email_sent",
                                                f"Email sent: {custom_sub}", details=custom_msg,
                                                source="import outreach", lead_name=comp_name,
                                                lead_email=raw_email)
                    else:
                        lead_obj["email_status"] = "FAILED"
        elif outcome == "updated":
            updated_count += 1
        else:
            duplicates_count += 1

    # Save to Master CSV
    save_ok = registry.save_master_safely()

    # Sync to Supabase
    supabase_synced = False
    if sync_to_supabase:
        try:
            # sync() returns False when keys are missing or nothing was uploaded
            supabase_synced = sync_to_supabase.sync(csv_filepath=master_csv) is not False
        except Exception as e:
            print(f"[WARN] Supabase sync notice: {e}")

    return {
        "success": save_ok,
        "added": added_count,
        "updated": updated_count,
        "duplicates": duplicates_count,
        "emails_sent": emails_sent_count,
        "supabase_synced": supabase_synced,
        "total_leads": len(registry.leads)
    }

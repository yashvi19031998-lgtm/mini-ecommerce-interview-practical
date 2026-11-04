"""
Lead Normalizer, Validator, and Deduplicator Module
===================================================
Provides robust field normalization, priority-based deduplication,
merging logic, and persistent storage synchronization for all_leads_master.csv.
"""

import os
import re
import csv
import html
import datetime
from urllib.parse import urlparse
from typing import Dict, Any, List, Tuple, Optional, Set

from dateutil import parser as date_parser

# Master CSV Canonical Field Definition
MASTER_FIELDNAMES = [
    "lead_id",
    "full_name",
    "company_name",
    "email",
    "mobile_number",
    "website",
    "description",
    "source",
    "source_url",
    "location",
    "lead_type",
    "intent_score",
    "first_seen_at",
    "last_seen_at",
    "last_updated_at",
    "email_status",
    "email_sent_at",
    # When the original post/message was published (empty if the source gives no date)
    "posted_at",
    # CRM pipeline status (NEW, CONTACTED, REPLIED, MEETING, WON, LOST, ...) - set from the UI
    "status",
    # How to reach this lead: email / phone / reddit / telegram / website / none
    "contact_channel",
    # AI qualification (filled by lead_quality.py)
    "ai_category",
    "ai_score",
    "ai_summary",
    "ai_requirement",
    "ai_tech_stack",
    "ai_budget",
    "ai_reason",
    "ai_qualified_at",
    # When this lead was posted to Slack (empty = not yet)
    "slack_notified_at",
    # Website "needs work" signals (website_signals.py), e.g. "not mobile-friendly; old jQuery 1.12"
    "website_signals",
]

# Fields that are not derived from scraper output and must survive every re-save untouched
PASSTHROUGH_FIELDS = [
    "contact_channel", "ai_category", "ai_score", "ai_summary", "ai_requirement",
    "ai_tech_stack", "ai_budget", "ai_reason", "ai_qualified_at", "slack_notified_at",
    "website_signals",
]

# Template / placeholder emails copied from website themes ("you@company.com")
PLACEHOLDER_EMAIL_LOCALS = {
    "you", "your", "yourname", "youremail", "your.name", "name", "email", "user",
    "username", "someone", "example", "test", "john.doe", "johndoe", "firstname.lastname",
}
PLACEHOLDER_EMAIL_DOMAINS = {
    "company.com", "yourcompany.com", "yourdomain.com", "mydomain.com", "example.org",
    "example.net", "email.com", "website.com", "yoursite.com", "mysite.com",
}

# How much post text we keep. The AI qualifier reads this, and budgets / tech / contact
# details are often near the end of a post, so don't cut it short.
MAX_DESCRIPTION_CHARS = int(os.getenv("MAX_DESCRIPTION_CHARS", "2000"))


def normalize_datetime(value: Any) -> str:
    """Parses most date formats (RFC 822, ISO 8601, epoch ms/s, 'YYYY-MM-DD') to local 'YYYY-MM-DD HH:MM:SS'."""
    if value is None or str(value).strip() in ("", "None", "N/A", "nan"):
        return ""
    v = str(value).strip()
    try:
        if v.isdigit():  # epoch seconds or milliseconds
            ts = int(v) / (1000 if len(v) >= 13 else 1)
            return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
        dt = date_parser.parse(v)
        if dt.tzinfo is not None:
            dt = dt.astimezone().replace(tzinfo=None)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, OverflowError, OSError):
        return ""


def lead_age_days(lead: Dict[str, Any]) -> Optional[float]:
    """Age of the lead in days: from the post date if known, else from when we first saw it."""
    stamp = lead.get("posted_at") or lead.get("first_seen_at") or ""
    norm = normalize_datetime(stamp)
    if not norm:
        return None
    then = datetime.datetime.strptime(norm, "%Y-%m-%d %H:%M:%S")
    return max(0.0, (datetime.datetime.now() - then).total_seconds() / 86400)


# Paid-ad click-trackers are never leads
AD_URL_MARKERS = ("bing.com/aclick", "googleadservices.com", "doubleclick.net", "/aclk?")

# Blacklisted domain names (social media, search, aggregators, system)
INVALID_DOMAINS = {
    "google.com", "yahoo.com", "bing.com", "duckduckgo.com",
    "reddit.com", "twitter.com", "x.com", "facebook.com",
    "instagram.com", "youtube.com", "wikipedia.org", "w3schools.com",
    "geeksforgeeks.org", "softonic.com", "microsoft.com", "apple.com",
    "imdb.com", "netflix.com", "simplilearn.com", "computerhope.com",
    "techtarget.com", "britannica.com", "forms.gle", "docs.google.com",
    # Platforms / marketplaces / job boards / news: a post there is NOT the company's website.
    # (If these were treated as websites, domain-based dedupe would merge every post into one lead.)
    "linkedin.com", "freelancer.com", "upwork.com", "fiverr.com", "peopleperhour.com", "guru.com",
    "ycombinator.com", "indeed.com", "glassdoor.com", "ziprecruiter.com", "naukri.com",
    "weworkremotely.com", "remotive.com", "t.me", "telegram.me", "medium.com", "github.com",
    "quora.com", "producthunt.com", "inc42.com", "yourstory.com", "justdial.com",
    "indiamart.com", "tradeindia.com", "exportersindia.com",
}

EMAIL_BLACKLIST_DOMAINS = {
    "example.com", "domain.com", "test.com", "sentry.io",
    "wixpress.com", "wix.com", "googleapis.com", "schema.org",
    "cloudflare.com", "noreply.com", "google.com", "youtube.com",
    "reddit.com", "github.com", "netflix.com", "imdb.com"
}


def clean_text(text: Optional[str]) -> str:
    """Removes HTML tags, entities, and excess whitespace."""
    if not text or text == "None" or text == "N/A" or text == "Not Found":
        return ""
    # Strip HTML tags
    clean = re.sub(r"<[^>]+>", " ", str(text))
    # Unescape HTML entities
    clean = html.unescape(clean)
    # Collapse whitespace
    return " ".join(clean.split()).strip()


def normalize_email(email_str: Optional[str]) -> str:
    """Extracts, filters, and standardizes valid email addresses."""
    if not email_str or email_str in ("None", "N/A", "Not Found"):
        return ""

    raw_candidates = re.split(r"[,|;\s]+", str(email_str))
    valid_emails = set()

    email_regex = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z]{2,}$")

    for cand in raw_candidates:
        cand = cand.strip().lower()
        if not cand or "@" not in cand:
            continue
        # Check extensions
        if any(cand.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".css", ".js")):
            continue
        parts = cand.split("@")
        if len(parts) == 2 and parts[1] in EMAIL_BLACKLIST_DOMAINS:
            continue
        if len(parts) == 2 and (parts[0] in PLACEHOLDER_EMAIL_LOCALS or parts[1] in PLACEHOLDER_EMAIL_DOMAINS):
            continue
        if email_regex.match(cand):
            valid_emails.add(cand)

    return ", ".join(sorted(valid_emails))


def normalize_phone(phone_str: Optional[str]) -> str:
    """Extracts, cleans, and standardizes phone numbers (prioritizing Indian and standard 10-12 digits)."""
    if not phone_str or phone_str in ("None", "N/A", "Not Found"):
        return ""

    # Split multiple phones
    candidates = re.split(r"[,|;]+", str(phone_str))
    valid_phones = []

    for cand in candidates:
        cand = cand.strip()
        digits = re.sub(r"\D", "", cand)
        # Discard absurdly long / short digit strings (like 1377063225 from Microsoft/Wikipedia)
        if len(digits) < 10 or len(digits) > 13:
            continue
        # Discard repetitive patterns
        if len(set(digits)) <= 3:
            continue

        # Format STD Landlines (e.g. Ahmedabad 079)
        if digits.startswith("079") and len(digits) in (10, 11):
            valid_phones.append(f"079-{digits[3:]}")
        # Format standard 10-digit Indian Mobile starting with 6,7,8,9
        elif len(digits) == 10 and digits[0] in "6789":
            valid_phones.append(f"+91 {digits[:5]} {digits[5:]}")
        elif len(digits) == 12 and digits.startswith("91") and digits[2] in "6789":
            valid_phones.append(f"+91 {digits[2:7]} {digits[7:]}")
        elif 10 <= len(digits) <= 13 and (cand.startswith("+") or cand.startswith("00") or "-" in cand or "(" in cand):
            valid_phones.append(cand)

    # Deduplicate while preserving order
    seen = set()
    result = []
    for p in valid_phones:
        if p not in seen:
            seen.add(p)
            result.append(p)

    return ", ".join(result)


def url_host(url: Optional[str]) -> str:
    """Returns the bare host (no www / port) of a URL, or "" if unparsable."""
    if not url or url in ("None", "N/A", "Not Found"):
        return ""
    try:
        u = url.strip()
        if not u.startswith(("http://", "https://")):
            u = "http://" + u
        host = urlparse(u).netloc.lower().split(":")[0]
        return host[4:] if host.startswith("www.") else host
    except Exception:
        return ""


def is_invalid_domain(url: Optional[str]) -> bool:
    """True if the URL belongs to a platform/aggregator (or any subdomain of one)."""
    host = url_host(url)
    return any(host == d or host.endswith("." + d) for d in INVALID_DOMAINS)


def is_ad_url(url: Optional[str]) -> bool:
    u = (url or "").lower()
    return any(marker in u for marker in AD_URL_MARKERS)


def canonicalize_domain(url: Optional[str]) -> str:
    """Returns root domain without www or query parameters."""
    if not url or url in ("None", "N/A", "Not Found"):
        return ""
    try:
        url = url.strip()
        if not url.startswith(("http://", "https://")):
            url = "http://" + url
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        if ":" in domain:
            domain = domain.split(":")[0]
        # Ignore common platforms from being used as company domains
        if domain in INVALID_DOMAINS:
            return ""
        return domain
    except Exception:
        return ""


def clean_url(url: Optional[str]) -> str:
    """Normalizes URL without tracking parameters."""
    if not url or url in ("None", "N/A", "Not Found"):
        return ""
    u = url.strip()
    if u.startswith("//"):
        u = "https:" + u
    return u


def normalize_lead_record(raw: Dict[str, Any], default_source: str = "Unknown") -> Dict[str, str]:
    """
    Transforms any raw input dictionary from any of the 10 scrapers
    into the canonical master lead schema.
    """
    now_iso = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 1. Company Name / Title
    company = clean_text(
        raw.get("company_name") or
        raw.get("Company Name") or
        raw.get("Business Name") or
        raw.get("Business Name/Title") or
        raw.get("Title_Requirement") or
        raw.get("Title") or
        raw.get("Job Title / Requirement") or ""
    )

    # 2. Contact Name
    full_name = clean_text(
        raw.get("full_name") or
        raw.get("Sender Username") or
        raw.get("Client Name / Handle") or ""
    )

    # 3. Email
    raw_email = (
        raw.get("email") or
        raw.get("Email") or
        raw.get("Extracted_Emails") or
        raw.get("Extracted_Email_Contact") or
        raw.get("Emails") or ""
    )
    # Check if contact details text has email
    if not raw_email and "Contact_Details" in raw:
        em_match = re.search(r"Email:\s*([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z]{2,})", str(raw["Contact_Details"]))
        if em_match:
            raw_email = em_match.group(1)

    email = normalize_email(raw_email)

    # 4. Mobile / Phone
    raw_phone = (
        raw.get("mobile_number") or
        raw.get("Mobile Number") or
        raw.get("Phone") or
        raw.get("Mobile") or
        raw.get("Extracted_Phones") or
        raw.get("Phones") or ""
    )
    phone = normalize_phone(raw_phone)

    # 5. Website
    website = clean_url(
        raw.get("website") or
        raw.get("Website URL") or
        raw.get("Website") or
        raw.get("External_Website") or
        raw.get("Extracted_External_URL") or ""
    )
    # If website is a platform/aggregator (reddit, bing, ...), it is not the company's site.
    # (Previously compared canonicalize_domain() - which returns "" for these - so it never matched.)
    platform_url = website if is_invalid_domain(website) else ""
    if platform_url:
        website = ""

    # 6. Source URL
    source_url = clean_url(
        raw.get("source_url") or
        raw.get("URL") or
        raw.get("Google Maps URL") or
        raw.get("Direct_URL") or
        raw.get("Post_URL") or
        raw.get("Portal_URL") or
        raw.get("LinkedIn_URL") or
        raw.get("Direct URL") or ""
    ) or platform_url
    if not website and source_url and not is_invalid_domain(source_url):
        # Source itself is a company website
        website = source_url

    # 7. Source
    source = clean_text(
        raw.get("source") or
        raw.get("Source") or
        raw.get("Channel/Group") or
        raw.get("Portal_Source") or
        raw.get("Platform") or
        raw.get("Search Query") or
        raw.get("Search_Query") or
        default_source
    )

    # 8. Description / Snippet
    description = clean_text(
        raw.get("description") or
        raw.get("Message") or
        raw.get("Snippet") or
        raw.get("Description_Snippet") or ""
    )

    # 9. Location
    location = clean_text(
        raw.get("location") or
        raw.get("Address") or
        raw.get("City") or ""
    )
    if not location and "Ahmedabad" in source:
        location = "Ahmedabad"

    # 10. Lead Type & Intent
    lead_type = clean_text(
        raw.get("lead_type") or
        raw.get("Lead Type") or
        raw.get("Category") or "Potential Lead"
    )

    intent_score = clean_text(
        str(raw.get("intent_score") if raw.get("intent_score") is not None else
            raw.get("Lead Score") if raw.get("Lead Score") is not None else
            raw.get("Intent") or "")
    )

    # Timestamps
    first_seen = clean_text(raw.get("first_seen_at") or raw.get("Scraped At") or raw.get("Date Found") or now_iso)
    last_seen = clean_text(raw.get("last_seen_at") or now_iso)
    last_updated = clean_text(raw.get("last_updated_at") or now_iso)

    lead_id = clean_text(raw.get("lead_id") or raw.get("Lead ID") or "")
    email_status = clean_text(raw.get("email_status") or raw.get("Email Status") or "NOT_SENT")
    email_sent_at = clean_text(raw.get("email_sent_at") or raw.get("Email Sent At") or "")
    posted_at = normalize_datetime(
        raw.get("posted_at") or raw.get("Posted Date") or raw.get("published") or raw.get("Date") or ""
    )
    status = clean_text(raw.get("status") or raw.get("Status") or "NEW").upper()

    return {
        "lead_id": lead_id,
        "full_name": full_name,
        "company_name": company,
        "email": email,
        "mobile_number": phone,
        "website": website,
        "description": description[:MAX_DESCRIPTION_CHARS],
        "source": source,
        "source_url": source_url,
        "location": location,
        "lead_type": lead_type,
        "intent_score": intent_score,
        "first_seen_at": first_seen,
        "last_seen_at": last_seen,
        "last_updated_at": last_updated,
        "email_status": email_status,
        "email_sent_at": email_sent_at,
        "posted_at": posted_at,
        "status": status,
        **{k: str(raw.get(k) or "").strip() for k in PASSTHROUGH_FIELDS},
    }


class MasterLeadRegistry:
    """
    Manages loading, deduplication matching, safe enrichment merging,
    and safe atomic writes for all_leads_master.csv.
    """

    def __init__(self, master_filepath: str = "all_leads_master.csv"):
        self.master_filepath = master_filepath
        self.leads: List[Dict[str, str]] = []
        
        # Primary lookup indices
        self.email_index: Dict[str, int] = {}
        self.phone_index: Dict[str, int] = {}
        self.domain_index: Dict[str, int] = {}
        self.source_url_index: Dict[str, int] = {}
        self.name_loc_index: Dict[str, int] = {}

        self.load_master()

    def _index_lead(self, idx: int, lead: Dict[str, str]):
        """Adds lead attributes into lookup indices for fast deduplication."""
        # Index emails
        if lead.get("email"):
            for em in lead["email"].split(", "):
                em_clean = em.strip().lower()
                if em_clean:
                    self.email_index[em_clean] = idx

        # Index phones
        if lead.get("mobile_number"):
            for ph in lead["mobile_number"].split(", "):
                digits = re.sub(r"\D", "", ph)
                if len(digits) >= 10:
                    self.phone_index[digits[-10:]] = idx

        # Index website domain
        dom = canonicalize_domain(lead.get("website"))
        if dom:
            self.domain_index[dom] = idx

        # Index source URL
        s_url = lead.get("source_url", "").strip()
        if s_url:
            self.source_url_index[s_url] = idx

        # Index company name + location (only if company name is substantial)
        comp = re.sub(r"[^a-zA-Z0-9]", "", lead.get("company_name", "").lower())
        loc = re.sub(r"[^a-zA-Z0-9]", "", lead.get("location", "").lower())
        if len(comp) >= 5:
            key = f"{comp}::{loc}" if loc else comp
            self.name_loc_index[key] = idx

    def load_master(self):
        """Loads existing master file safely without data loss."""
        self.leads = []
        self.email_index.clear()
        self.phone_index.clear()
        self.domain_index.clear()
        self.source_url_index.clear()
        self.name_loc_index.clear()

        if not os.path.exists(self.master_filepath):
            return

        try:
            with open(self.master_filepath, mode="r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    norm = normalize_lead_record(row)
                    if not norm.get("lead_id"):
                        norm["lead_id"] = f"LEAD-{len(self.leads) + 1:05d}"
                    idx = len(self.leads)
                    self.leads.append(norm)
                    self._index_lead(idx, norm)
        except Exception as e:
            print(f"[WARN] Error reading existing master CSV: {e}")

    def find_match(self, lead: Dict[str, str]) -> Optional[int]:
        """
        Prioritized duplicate matching:
        1. Normalized email
        2. Normalized phone
        3. Canonical website domain
        4. Exact Source/Post URL
        5. Normalized Company Name + Location
        """
        # Match 1: Email
        if lead.get("email"):
            for em in lead["email"].split(", "):
                em_clean = em.strip().lower()
                if em_clean in self.email_index:
                    return self.email_index[em_clean]

        # Match 2: Phone
        if lead.get("mobile_number"):
            for ph in lead["mobile_number"].split(", "):
                digits = re.sub(r"\D", "", ph)
                if len(digits) >= 10 and digits[-10:] in self.phone_index:
                    return self.phone_index[digits[-10:]]

        # Match 3: Domain
        dom = canonicalize_domain(lead.get("website"))
        if dom and dom in self.domain_index:
            return self.domain_index[dom]

        # Match 4: Source URL
        s_url = lead.get("source_url", "").strip()
        if s_url and s_url in self.source_url_index:
            return self.source_url_index[s_url]

        # Match 5: Name + Location
        comp = re.sub(r"[^a-zA-Z0-9]", "", lead.get("company_name", "").lower())
        loc = re.sub(r"[^a-zA-Z0-9]", "", lead.get("location", "").lower())
        if len(comp) >= 5:
            key = f"{comp}::{loc}" if loc else comp
            if key in self.name_loc_index:
                return self.name_loc_index[key]

        return None

    def merge_and_enrich(self, existing_idx: int, new_lead: Dict[str, str]) -> bool:
        """
        Enriches an existing lead with new information without losing prior data.
        Returns True if meaningful new fields were added.
        """
        target = self.leads[existing_idx]
        modified = False
        now_iso = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 1. Enrich Email
        if new_lead.get("email"):
            existing_emails = set(target.get("email", "").split(", ")) - {""}
            new_emails = set(new_lead["email"].split(", ")) - {""}
            combined = existing_emails | new_emails
            if len(combined) > len(existing_emails):
                target["email"] = ", ".join(sorted(combined))
                modified = True

        # 2. Enrich Phone
        if new_lead.get("mobile_number"):
            existing_phones = set(target.get("mobile_number", "").split(", ")) - {""}
            new_phones = set(new_lead["mobile_number"].split(", ")) - {""}
            combined = existing_phones | new_phones
            if len(combined) > len(existing_phones):
                target["mobile_number"] = ", ".join(sorted(combined))
                modified = True

        # 3. Enrich Website
        if not target.get("website") and new_lead.get("website"):
            target["website"] = new_lead["website"]
            modified = True

        # 4. Enrich Full Name
        if not target.get("full_name") and new_lead.get("full_name"):
            target["full_name"] = new_lead["full_name"]
            modified = True

        # 5. Enrich Location
        if not target.get("location") and new_lead.get("location"):
            target["location"] = new_lead["location"]
            modified = True

        # 6. Append Source Attribution if new
        if new_lead.get("source") and new_lead["source"] not in target.get("source", ""):
            target["source"] = f"{target['source']} | {new_lead['source']}"
            modified = True

        # 7. Update Description if more comprehensive
        if len(new_lead.get("description", "")) > len(target.get("description", "")):
            target["description"] = new_lead["description"]
            modified = True

        # 7b. Fill in the original post date if we didn't have it
        if not target.get("posted_at") and new_lead.get("posted_at"):
            target["posted_at"] = new_lead["posted_at"]
            modified = True

        # 8. Update Intent Score if higher
        if new_lead.get("intent_score") and not target.get("intent_score"):
            target["intent_score"] = new_lead["intent_score"]
            modified = True

        # Always update last_seen_at
        target["last_seen_at"] = now_iso
        if modified:
            target["last_updated_at"] = now_iso

        return modified

    def add_lead(self, raw_lead: Dict[str, Any], default_source: str = "Unknown") -> Tuple[str, Any]:
        """
        Processes a single raw lead record:
        - If invalid, skips and returns ('skipped_invalid', False).
        - If duplicate, enriches existing and returns ('updated' or 'duplicate', existing_lead).
        - If new, appends and returns ('added', new_lead).
        """
        lead = normalize_lead_record(raw_lead, default_source)

        # Paid ads (e.g. Bing "Post a Job - Indeed") are never leads
        if is_ad_url(lead.get("source_url")) or is_ad_url(lead.get("website")):
            return "skipped_invalid", False

        # Basic validity: Must have at least a company name, website, source URL, or contact
        if not (lead.get("company_name") or lead.get("website") or lead.get("source_url") or lead.get("email") or lead.get("mobile_number")):
            return "skipped_invalid", False

        match_idx = self.find_match(lead)
        if match_idx is not None:
            updated = self.merge_and_enrich(match_idx, lead)
            return ("updated" if updated else "duplicate"), self.leads[match_idx]

        # Genuinely new lead
        lead["lead_id"] = f"LEAD-{len(self.leads) + 1:05d}"
        new_idx = len(self.leads)
        self.leads.append(lead)
        self._index_lead(new_idx, lead)
        return "added", lead

    def save_master_safely(self) -> bool:
        """
        Writes data safely using an atomic temporary file replacement
        to prevent file corruption during execution.
        """
        temp_file = f"{self.master_filepath}.tmp"
        try:
            with open(temp_file, mode="w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=MASTER_FIELDNAMES)
                writer.writeheader()
                for lead in self.leads:
                    # Ensure all fields exist
                    row = {k: lead.get(k, "") for k in MASTER_FIELDNAMES}
                    writer.writerow(row)

            # Atomic replace
            if os.path.exists(self.master_filepath):
                backup_file = f"{self.master_filepath}.bak"
                try:
                    os.replace(self.master_filepath, backup_file)
                except Exception:
                    pass

            os.replace(temp_file, self.master_filepath)
            return True
        except Exception as e:
            print(f"[FATAL] Failed to save master CSV: {e}")
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except Exception:
                    pass
            return False

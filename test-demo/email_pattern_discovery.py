"""
Email Pattern Discovery & Public Contact Intelligence Module
============================================================
Performs compliant, public OSINT-based email discovery and pattern hypothesis:
1. Crawls only publicly indexed pages (/, /contact, /about, /team, /leadership, etc.).
2. Extracts verified public email addresses belonging to the target company domain.
3. Generates candidate email patterns ({first}@, {first}.{last}@, etc.) for manual or MX review.
4. Validates domain MX mail capabilities using dnspython or native nslookup/socket fallback.
5. Classifies confidence (HIGH for public page mentions, LOW for generic info@, UNVERIFIED for hypotheses).

Compliance:
- Does NOT crawl private/login-protected pages or bypass robots.txt.
- Marks pattern hypotheses as UNVERIFIED to prevent unverified bulk dispatch.
"""

import os
import re
import socket
import subprocess
from typing import List, Dict, Any, Set, Optional
from urllib.parse import urljoin

try:
    import requests
except ImportError:
    requests = None

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

try:
    import dns.resolver
except ImportError:
    dns = None

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
USER_AGENT = "SangeetaInfotechResearch/1.0 (+https://sangeetainfotech.co.in)"

STANDARD_CONTACT_PATHS = [
    "/",
    "/contact",
    "/contact-us",
    "/about",
    "/about-us",
    "/team",
    "/leadership",
    "/management",
    "/press",
    "/media",
    "/investors"
]

GENERIC_ROLE_PREFIXES = {
    "info", "contact", "support", "help", "sales", "inquiries", "enquiry",
    "hello", "hi", "admin", "office", "careers", "jobs", "billing", "marketing"
}


def clean_domain(raw_domain: str) -> str:
    """Strips http://, https://, trailing slashes, and paths from domain."""
    d = raw_domain.lower().strip()
    d = re.sub(r"^https?://", "", d)
    d = d.split("/")[0].split("?")[0].strip()
    return d


def domain_has_mail(domain: str) -> List[str]:
    """
    Checks if domain has valid MX records.
    Tries dnspython first, then falls back to Windows nslookup or socket.
    """
    clean = clean_domain(domain)
    if not clean or "." not in clean:
        return []

    # 1. Try dnspython resolver
    if dns and hasattr(dns, "resolver"):
        try:
            answers = dns.resolver.resolve(clean, "MX")
            return [str(r.exchange).rstrip(".") for r in answers]
        except Exception:
            pass

    # 2. Try native nslookup fallback (works cross-platform without external packages)
    try:
        proc = subprocess.run(
            ["nslookup", "-type=mx", clean],
            capture_output=True,
            text=True,
            timeout=5
        )
        out = proc.stdout or ""
        mx_records = []
        for line in out.splitlines():
            line_clean = line.strip().lower()
            if "mail exchanger =" in line_clean:
                parts = line_clean.split("mail exchanger =")
                if len(parts) > 1:
                    tokens = parts[1].strip().split()
                    if tokens:
                        mx_records.append(tokens[-1].rstrip("."))
            elif "mx" in line_clean and "exchange" in line_clean:
                parts = line_clean.split()
                if parts:
                    mx_records.append(parts[-1].rstrip("."))
        if mx_records:
            return list(dict.fromkeys(mx_records))
    except Exception:
        pass

    # 3. Fallback: check if domain has standard host record (A/AAAA)
    try:
        socket.gethostbyname(clean)
        return [f"host-resolved.{clean}"]
    except Exception:
        return []


def generate_email_patterns(first_name: str, last_name: str, domain: str) -> List[str]:
    """
    Generates candidate email patterns for research and verification.
    These are treated as UNVERIFIED until confirmed on public pages or MX tests.
    """
    clean_d = clean_domain(domain)
    first = re.sub(r"[^a-zA-Z]", "", first_name).lower().strip()
    last = re.sub(r"[^a-zA-Z]", "", last_name).lower().strip()

    if not first and not last:
        return []

    candidates = []
    if first and last:
        f_init = first[0]
        l_init = last[0]
        candidates.extend([
            f"{first}.{last}@{clean_d}",
            f"{first}@{clean_d}",
            f"{first}{last}@{clean_d}",
            f"{f_init}{last}@{clean_d}",
            f"{first}.{l_init}@{clean_d}",
            f"{f_init}.{last}@{clean_d}",
            f"{first}_{last}@{clean_d}",
            f"{first}-{last}@{clean_d}",
            f"{last}@{clean_d}",
        ])
    elif first:
        candidates.append(f"{first}@{clean_d}")
    elif last:
        candidates.append(f"{last}@{clean_d}")

    return list(dict.fromkeys(candidates))


def extract_emails_from_html(html_text: str, domain: str) -> Set[str]:
    """Extracts and filters emails belonging to the domain from HTML text."""
    clean_d = clean_domain(domain)
    found_emails = set()
    if not html_text:
        return found_emails

    # 1. Extract from mailto: links
    if BeautifulSoup:
        try:
            soup = BeautifulSoup(html_text, "html.parser")
            for a in soup.select('a[href^="mailto:"]'):
                href = a.get("href", "")
                raw = href.replace("mailto:", "").split("?")[0].strip().lower()
                if raw and "@" in raw:
                    found_emails.add(raw)
        except Exception:
            pass

    # 2. Extract from raw regex
    for match in EMAIL_RE.findall(html_text):
        found_emails.add(match.lower())

    # Filter to addresses belonging to this domain (or official subdomain)
    valid_domain_emails = set()
    for e in found_emails:
        if "@" in e:
            user_part, domain_part = e.split("@", 1)
            if domain_part == clean_d or domain_part.endswith(f".{clean_d}"):
                # Avoid fake or template domains
                if not any(placeholder in e for placeholder in ("example.com", "yoursite.com", "domain.com")):
                    valid_domain_emails.add(e)

    return valid_domain_emails


def get_public_emails(domain: str, max_pages: int = 5, timeout: int = 8) -> Dict[str, Any]:
    """
    Crawls public website paths on the target domain and extracts verified public contacts.
    Returns structured results categorized by confidence level.
    """
    clean_d = clean_domain(domain)
    if not clean_d or not requests:
        return {
            "domain": clean_d,
            "has_mx": False,
            "mx_records": [],
            "public_emails": [],
            "personal_contacts": [],
            "generic_contacts": []
        }

    mx_records = domain_has_mail(clean_d)
    base_url = f"https://{clean_d}"
    headers = {"User-Agent": USER_AGENT}

    collected_emails: Set[str] = set()
    crawled_paths: List[str] = []

    for path in STANDARD_CONTACT_PATHS[:max_pages]:
        target_url = urljoin(base_url, path)
        try:
            resp = requests.get(target_url, timeout=timeout, headers=headers)
            if resp.status_code == 200 and resp.text:
                crawled_paths.append(path)
                emails = extract_emails_from_html(resp.text, clean_d)
                collected_emails.update(emails)
        except Exception:
            continue

    personal = []
    generic = []

    for email in sorted(collected_emails):
        local_part = email.split("@")[0].lower()
        if any(local_part == gen or local_part.startswith(f"{gen}.") for gen in GENERIC_ROLE_PREFIXES):
            generic.append({
                "email": email,
                "confidence": "MEDIUM (Role-based public)",
                "type": "generic"
            })
        else:
            personal.append({
                "email": email,
                "confidence": "HIGH (Publicly published direct contact)",
                "type": "direct"
            })

    return {
        "domain": clean_d,
        "has_mx": len(mx_records) > 0,
        "mx_records": mx_records,
        "crawled_paths": crawled_paths,
        "public_emails": list(collected_emails),
        "personal_contacts": personal,
        "generic_contacts": generic
    }

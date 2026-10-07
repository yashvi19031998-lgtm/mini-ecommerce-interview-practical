"""
Business Lead Collector - High-Accuracy Lead Scraper
===================================================
A Python demonstration tool for identifying and collecting publicly available
IT/software business leads, filtering out irrelevant content (dictionaries,
entertainment, social media, directories), detecting buyer intent vs service
providers, and scoring leads accurately.

Compliance & Ethics Note:
- Crawls only publicly available information on public web pages.
- Respects rate limits with courteous delays.
- Does not bypass CAPTCHA, authentication, or anti-bot protections.
- Operates within lawful, public demonstration boundaries.
"""

import re
import time
import json
import base64
import logging
from urllib.parse import urljoin, urlparse, unquote, quote_plus
from typing import List, Dict, Set, Optional, Tuple, Any

import requests
from bs4 import BeautifulSoup
import pandas as pd

# Optional import of googlesearch-python
try:
    from googlesearch import search as google_search
except ImportError:
    google_search = None


# ==============================================================================
# 1. CONFIGURATION
# ==============================================================================

# Search queries focused on businesses seeking IT / software services
SEARCH_QUERIES = [
    '"looking for software development company"',
    '"need software development company"',
    '"looking for web development company"',
    '"need web development company"',
    '"hire software development company"',
    '"looking for IT company"',
    '"need IT company"',
    '"hire software developer"',
    '"looking for software developer"',
    '"need mobile app development company"',
]

# Configurable search location (leave as "" if you do not want location filtering)
SEARCH_LOCATION = "Ahmedabad"

MAX_RESULTS_PER_QUERY = 10     # Max search results to evaluate per query
REQUEST_TIMEOUT = 10           # HTTP request timeout in seconds
REQUEST_DELAY = 1.5            # Polite delay between HTTP requests
MIN_LEAD_SCORE = 4             # Quality threshold: minimum score required for leads.csv

# Output file paths
LEADS_CSV = "leads.csv"
REJECTED_CSV = "rejected_leads.csv"

# Browser User-Agent header
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# Domains to exclude strictly
EXCLUDED_DOMAINS = {
    # Social Platforms
    "facebook.com", "instagram.com", "linkedin.com", "youtube.com",
    "twitter.com", "x.com", "tiktok.com", "reddit.com", "pinterest.com",
    # Search Engines
    "google.com", "bing.com", "yahoo.com", "duckduckgo.com",
    # Dictionaries & Educational Reference
    "dictionary.com", "cambridge.org", "collinsdictionary.com",
    "thesaurus.com", "merriam-webster.com", "usdictionary.com",
    "askdifference.com", "britannica.com", "wikipedia.org", "w3schools.com",
    "geeksforgeeks.org", "tutorialspoint.com", "thefreedictionary.com",
    "vocabulary.com", "perfectyourenglish.com", "prepedu.com",
    # Streaming & Media / Entertainment
    "hotstar.com", "netflix.com", "justwatch.com", "imdb.com", "primevideo.com",
    # Directories & Job Boards
    "justdial.com", "indiamart.com", "indianyellowpages.com", "yellowpages.com",
    "indeed.com", "glassdoor.com", "upwork.com", "fiverr.com", "freelancer.com",
    "toptal.com", "naukri.com", "shine.com", "monster.com", "clutch.co",
    "goodfirms.co", "techbehemoths.com", "f6s.com", "techreviewer.co",
    "itprofiles.com", "beststartup.in", "peoplemanagingpeople.com",
    "recruitment.com", "ambitionbox.com",
    # Tech giants & AI
    "microsoft.com", "apple.com", "amazon.com", "openai.com", "chatgpt.com",
    "github.com", "gitlab.com", "stackoverflow.com", "softonic.com"
}

# Keywords indicating intentional buying / hiring
INTENT_KEYWORDS = {
    "high": [
        "looking for software development company",
        "need software development company",
        "looking for web development company",
        "need web development company",
        "looking for it company",
        "need it company",
        "looking to hire",
        "need a developer",
        "need software development",
        "need web development",
        "need mobile app",
        "request for proposal",
        "rfp",
        "tender",
        "seeking development partner",
        "seeking software vendor",
        "wanted software developer"
    ],
    "medium": [
        "looking for",
        "need",
        "required",
        "hire",
        "hiring",
        "wanted",
        "seeking",
        "project requirement",
        "get a quote",
        "request a quote",
        "budget estimate",
        "post a project"
    ]
}

# Keywords indicating the site is an IT SERVICE PROVIDER (seller, not buyer)
SERVICE_PROVIDER_KEYWORDS = [
    "we provide software development",
    "we offer web development",
    "we are a software development company",
    "we are an it company",
    "our it services",
    "our software services",
    "our web development services",
    "our mobile app development services",
    "custom software development services",
    "hire our developers",
    "hire dedicated developers from us",
    "our technology stack",
    "our portfolio",
    "our case studies",
    "software development agency"
]

# Subpages to search for contact information
TARGET_SUBPAGE_KEYWORDS = ["contact", "contact-us", "contactus", "about", "about-us", "company"]

# Set up logging format
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s"
)
logger = logging.getLogger("LeadScraper")


# ==============================================================================
# 2. FILTERING & VALIDATION FUNCTIONS
# ==============================================================================

def get_domain(url: str) -> str:
    """Extracts cleaned domain name from URL (without www)."""
    try:
        netloc = urlparse(url).netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return netloc
    except Exception:
        return ""


def filter_search_result(url: str, title: str) -> Tuple[bool, str]:
    """
    Evaluates whether a search result is potentially a relevant business website.
    Returns (is_accepted, rejection_reason).
    """
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False, "Invalid URL scheme"

        domain = get_domain(url)
        if not domain:
            return False, "Malformed domain"

        # Check domain exclusion list
        for excluded in EXCLUDED_DOMAINS:
            if domain == excluded or domain.endswith("." + excluded):
                return False, f"Excluded domain ({excluded})"

        # Check path and title for dictionary / educational keywords
        url_lower = url.lower()
        title_lower = title.lower()

        dict_words = ["dictionary", "thesaurus", "grammar", "definition", "synonyms", "pronunciation"]
        if any(w in url_lower or w in title_lower for w in dict_words):
            return False, "Dictionary / reference content"

        # Check streaming / movies / TV
        media_words = ["streaming", "movie", "tv-show", "trailer", "episodes", "watch online"]
        if any(w in url_lower or w in title_lower for w in media_words):
            return False, "Entertainment / streaming media"

        return True, "Accepted"
    except Exception as e:
        return False, f"Validation error: {e}"


def fetch_page(url: str) -> Optional[str]:
    """Fetches HTML with timeout and error handling."""
    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True
        )
        if response.status_code == 200 and "text/html" in response.headers.get("Content-Type", ""):
            return response.text
        return None
    except requests.exceptions.Timeout:
        logger.debug(f"Timeout fetching {url}")
        return None
    except requests.exceptions.RequestException:
        return None
    except Exception:
        return None


# ==============================================================================
# 3. COMPANY NAME EXTRACTION
# ==============================================================================

def extract_company_name(soup: BeautifulSoup, url: str) -> str:
    """
    Extracts a clean, professional company name using OpenGraph, structured data,
    or title cleaning rather than raw search result snippets.
    """
    # 1. Try OpenGraph site_name
    og_site = soup.find("meta", property="og:site_name")
    if og_site and og_site.get("content"):
        name = og_site["content"].strip()
        if 2 <= len(name) <= 50:
            return clean_company_name_text(name)

    # 2. Try application-name
    app_name = soup.find("meta", attrs={"name": "application-name"})
    if app_name and app_name.get("content"):
        name = app_name["content"].strip()
        if 2 <= len(name) <= 50:
            return clean_company_name_text(name)

    # 3. Try JSON-LD Schema Organization name
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            if isinstance(data, dict):
                if data.get("@type") in ("Organization", "Corporation", "LocalBusiness") and data.get("name"):
                    return clean_company_name_text(str(data["name"]))
            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and item.get("@type") in ("Organization", "Corporation") and item.get("name"):
                        return clean_company_name_text(str(item["name"]))
        except Exception:
            pass

    # 4. Clean <title> tag
    if soup.title and soup.title.string:
        raw_title = soup.title.string.strip()
        # Common delimiters: |, -, —, :, •
        parts = re.split(r"[\s\|\-\—\:\•\»\–]+", raw_title)
        if parts:
            candidate = parts[0].strip()
            # If the first part is generic (like "Home" or "Welcome"), check the second part
            if candidate.lower() in ("home", "welcome", "about us", "contact us", "official website") and len(parts) > 1:
                candidate = parts[1].strip()
            if 2 <= len(candidate) <= 45:
                return clean_company_name_text(candidate)

    # 5. Fallback: formatted domain name
    domain = get_domain(url)
    base_name = domain.split(".")[0]
    return base_name.replace("-", " ").title()


def clean_company_name_text(text: str) -> str:
    """Strips unnecessary marketing suffixes from company names."""
    # Strip common phrases like "Official Website", "Web Designing Company", etc.
    patterns_to_remove = [
        r"(?i)\s*\|\s*Home.*",
        r"(?i)\s*\|\s*Services.*",
        r"(?i)\s*\|\s*Contact Us.*",
        r"(?i)\s*-\s*Official Website.*",
        r"(?i)\s*\|\s*Website Designing.*",
        r"(?i)\s*\|\s*Software Development.*",
        r"(?i)\s*Private Limited",
        r"(?i)\s*Pvt\.?\s*Ltd\.?"
    ]
    cleaned = text.strip()
    for pattern in patterns_to_remove:
        cleaned = re.sub(pattern, "", cleaned).strip()
    return cleaned if cleaned else text.strip()


# ==============================================================================
# 4. EMAIL & PHONE EXTRACTION (WITH STRICT INDIAN VALIDATION)
# ==============================================================================

def extract_clean_emails(html_text: str, soup: BeautifulSoup) -> List[str]:
    """
    Extracts and normalizes valid business emails.
    Filters out CSS/JS tokens, image files, tracking scripts, and fake addresses.
    """
    raw_emails: Set[str] = set()

    # 1. Search mailto: links
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.lower().startswith("mailto:"):
            val = href.split(":", 1)[1].split("?")[0].strip().lower()
            if val:
                raw_emails.add(val)

    # 2. Regex for emails with strict alpha domain TLD
    email_regex = r"\b[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z]{2,}\b"
    for match in re.findall(email_regex, html_text):
        raw_emails.add(match.strip().lower())

    # Blacklist of placeholder or system email domains
    ignored_keywords = [
        "example.com", "domain.com", "test.com", "sentry.io", "wixpress.com",
        "wix.com", "googleapis.com", "polyfill", "webpack", "schema.org",
        "ingest.sentry", "cloudflare", "noreply", "no-reply"
    ]
    invalid_extensions = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".css", ".js")

    cleaned_emails = []
    for email in raw_emails:
        if any(email.endswith(ext) for ext in invalid_extensions):
            continue
        if any(ign in email for ign in ignored_keywords):
            continue
        if len(email) < 6 or len(email) > 60:
            continue
        cleaned_emails.append(email)

    # Prioritize primary business contact emails (info@, contact@, hello@, sales@)
    def priority_sort(e: str) -> int:
        for prefix in ("info@", "contact@", "hello@", "sales@", "business@", "support@"):
            if e.startswith(prefix):
                return 0
        return 1

    return sorted(list(set(cleaned_emails)), key=priority_sort)[:3]


def extract_clean_indian_phones(html_text: str, soup: BeautifulSoup) -> List[str]:
    """
    Extracts and validates Indian mobile and landline numbers.
    Prevents false positives (CSS pixels, dates, random IDs, coordinates).
    """
    valid_phones: Set[str] = set()

    # 1. Scan tel: links
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.lower().startswith("tel:"):
            phone_val = href.split(":", 1)[1].split("?")[0].strip()
            norm = validate_and_normalize_indian_phone(phone_val)
            if norm:
                valid_phones.add(norm)

    # 2. Regex for Indian phone formats
    # Formats: +91 98765 43210, +91-9876543210, +919876543210, 9876543210, 079-40001234, 079 4000 1234
    patterns = [
        # Mobile with +91 or 91 or 0
        r"(?:\+91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}",
        # Landline with STD code (e.g., Ahmedabad 079, Mumbai 022, Delhi 011)
        r"(?:0[1-9]\d{1,3}[\s-]?)?[2-9]\d{6,7}"
    ]

    for pat in patterns:
        for match in re.findall(pat, html_text):
            norm = validate_and_normalize_indian_phone(match)
            if norm:
                valid_phones.add(norm)

    return sorted(list(valid_phones))[:2]


def validate_and_normalize_indian_phone(phone_str: str) -> Optional[str]:
    """
    Validates that a string is a legitimate Indian phone number and normalizes it.
    Rejects dates (2024, 2025), CSS values, timestamps, decimals, and random numbers.
    """
    # Remove all formatting characters except digits and leading plus
    cleaned = re.sub(r"[^\d+]", "", phone_str)
    digits = re.sub(r"\D", "", cleaned)

    # Reject if too few or too many digits
    if len(digits) < 10 or len(digits) > 12:
        return None

    # Reject repetitive single digits like 9999999999 or 0000000000
    if len(set(digits)) <= 3:
        return None

    # Case 1: Indian Mobile (10 digits starting with 6, 7, 8, or 9)
    if len(digits) == 10 and digits[0] in "6789":
        return f"+91 {digits[:5]} {digits[5:]}"
    elif len(digits) == 12 and digits.startswith("91") and digits[2] in "6789":
        return f"+91 {digits[2:7]} {digits[7:]}"
    elif len(digits) == 11 and digits.startswith("0") and digits[1] in "6789":
        return f"+91 {digits[1:6]} {digits[6:]}"

    # Case 2: Landline with STD code (e.g. 079-40001234)
    # Ahmedabad STD code is 079, length 10 or 11
    if digits.startswith("079") and len(digits) in (10, 11):
        return f"079-{digits[3:]}"
    elif len(digits) == 10 and digits.startswith("79"):
        return f"079-{digits[2:]}"

    # Standard 10-11 digit landlines
    if 10 <= len(digits) <= 11 and not digits.startswith(("19", "20")):
        return f"+91 {digits[-10:]}"

    return None


def discover_contact_links(soup: BeautifulSoup, base_url: str) -> List[str]:
    """Finds up to 2 public contact or about subpages from homepage navigation."""
    contact_urls: List[str] = []
    base_domain = get_domain(base_url)

    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        lower_href = href.lower()
        anchor_text = anchor.get_text(strip=True).lower()

        if any(kw in lower_href or kw in anchor_text for kw in TARGET_SUBPAGE_KEYWORDS):
            full_url = urljoin(base_url, href)
            if get_domain(full_url) == base_domain and full_url not in contact_urls:
                # Avoid mailto and fragment links
                if full_url.startswith("http") and "#" not in full_url:
                    contact_urls.append(full_url)
                    if len(contact_urls) >= 2:
                        break

    return contact_urls


# ==============================================================================
# 5. INTENT DETECTION & LEAD CLASSIFICATION
# ==============================================================================

def analyze_intent_and_type(text: str, title: str) -> Tuple[str, str, Dict[str, Any]]:
    """
    Analyzes page text to classify the website:
    - Lead Type: Potential Buyer vs IT Service Provider vs Directory vs Blog vs Unknown
    - Intent: High, Medium, or Low
    Returns (intent_level, lead_type, signals_dict)
    """
    text_lower = text.lower()
    title_lower = title.lower()

    signals: Dict[str, Any] = {
        "strong_buying_intent": False,
        "hiring_phrase": False,
        "tech_requirement": False,
        "business_website_detected": True,
        "is_service_provider": False,
        "lead_type": "Unknown"
    }

    # 1. Check for IT Service Provider signals (companies that SELL software services)
    provider_matches = sum(1 for kw in SERVICE_PROVIDER_KEYWORDS if kw in text_lower or kw in title_lower)
    if provider_matches >= 2:
        signals["is_service_provider"] = True
        signals["lead_type"] = "IT Service Provider"

    # 2. Check for Buying / Hiring Intent signals
    high_intent_matches = sum(1 for kw in INTENT_KEYWORDS["high"] if kw in text_lower or kw in title_lower)
    medium_intent_matches = sum(1 for kw in INTENT_KEYWORDS["medium"] if kw in text_lower)

    if high_intent_matches >= 1:
        signals["strong_buying_intent"] = True
        signals["hiring_phrase"] = True
        intent = "High"
    elif medium_intent_matches >= 2:
        signals["hiring_phrase"] = True
        intent = "Medium"
    else:
        intent = "Low"

    # 3. Classify Lead Type
    if signals["is_service_provider"]:
        lead_type = "IT Service Provider"
    elif signals["strong_buying_intent"]:
        lead_type = "Potential Buyer"
    elif intent == "Medium":
        lead_type = "Potential Buyer"
    else:
        # Check if generic business
        if any(w in text_lower for w in ["about us", "our services", "company", "solutions"]):
            lead_type = "Unknown"
        else:
            lead_type = "Blog/Article"

    signals["lead_type"] = lead_type
    return intent, lead_type, signals


def calculate_lead_score(signals: Dict[str, Any], has_email: bool, has_phone: bool) -> int:
    """
    Calculates final lead score based on evidence:
    +3 = strong buying-intent phrase
    +2 = hiring phrase
    +2 = software/web/mobile requirement
    +1 = business website detected
    +1 = public business email found
    +1 = valid phone found
    -5 = IT service provider
    -5 = directory
    -5 = blog/article
    """
    score = 0

    if signals.get("strong_buying_intent"):
        score += 3
    if signals.get("hiring_phrase"):
        score += 2
    if signals.get("tech_requirement") or signals.get("strong_buying_intent"):
        score += 2
    if signals.get("business_website_detected"):
        score += 1
    if has_email:
        score += 1
    if has_phone:
        score += 1

    lead_type = signals.get("lead_type")
    if lead_type == "IT Service Provider":
        score -= 5
    elif lead_type in ("Directory", "Job Board", "Blog/Article"):
        score -= 5

    return score


# ==============================================================================
# 6. SEARCH RUNNER WITH MULTI-ENGINE FALLBACK
# ==============================================================================

def decode_bing_redirect(href: str) -> str:
    """Decodes Bing tracking/redirect URL (&u=a1<base64>) into the original URL."""
    if "/ck/a?!" in href and "&u=" in href:
        m = re.search(r"[?&]u=([^&]+)", href)
        if m:
            u_val = m.group(1)
            if u_val.startswith("a1"):
                b64 = u_val[2:] + ("=" * (-len(u_val[2:]) % 4))
                try:
                    return base64.b64decode(b64).decode("utf-8", errors="ignore")
                except Exception:
                    pass
    return href


def search_public_engine(query: str, max_results: int) -> List[Dict[str, str]]:
    """
    Free public search via requests + BeautifulSoup (Yahoo & Bing).
    Does not require paid APIs or anti-bot circumvention.
    """
    results: List[Dict[str, str]] = []
    seen_urls: Set[str] = set()

    # Engine 1: Yahoo Search
    try:
        url = f"https://search.yahoo.com/search?p={quote_plus(query)}"
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            for a_tag in soup.select("div.compTitle a"):
                raw_href = a_tag.get("href", "")
                m = re.search(r"/RU=([^/]+)/", raw_href)
                if m:
                    actual_url = unquote(m.group(1))
                    is_ok, reason = filter_search_result(actual_url, a_tag.get_text())
                    if is_ok and actual_url not in seen_urls:
                        seen_urls.add(actual_url)
                        results.append({
                            "url": actual_url,
                            "title": a_tag.get_text(strip=True),
                            "query": query
                        })
                if len(results) >= max_results:
                    break
    except Exception as e:
        logger.debug(f"Yahoo fallback search notice: {e}")

    # Engine 2: Bing Search (supplementary)
    if len(results) < max_results:
        try:
            url = f"https://www.bing.com/search?q={quote_plus(query)}"
            resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                for li in soup.find_all("li", class_="b_algo"):
                    h2 = li.find("h2")
                    if not h2:
                        continue
                    a_tag = h2.find("a", href=True)
                    if not a_tag:
                        continue
                    actual_url = decode_bing_redirect(a_tag["href"])
                    is_ok, reason = filter_search_result(actual_url, a_tag.get_text())
                    if is_ok and actual_url not in seen_urls:
                        seen_urls.add(actual_url)
                        results.append({
                            "url": actual_url,
                            "title": a_tag.get_text(strip=True),
                            "query": query
                        })
                    if len(results) >= max_results:
                        break
        except Exception as e:
            logger.debug(f"Bing fallback search notice: {e}")

    return results


def search_web(query: str, max_results: int) -> List[Dict[str, str]]:
    """
    Search runner:
    Tries Google via googlesearch-python first. If Google rate-limits
    or presents an automated verification page, it logs a clean notice and
    switches to public search without attempting circumvention.
    """
    results = []

    if google_search:
        try:
            search_gen = google_search(
                query,
                num_results=max_results,
                advanced=True,
                sleep_interval=REQUEST_DELAY
            )
            for item in search_gen:
                url = item.url if hasattr(item, "url") else str(item)
                title = getattr(item, "title", "")
                is_ok, reason = filter_search_result(url, title)
                if is_ok:
                    results.append({"url": url, "title": title, "query": query})
                if len(results) >= max_results:
                    break
        except Exception:
            pass

    if not results:
        logger.info("Google search unavailable/rate limited. Using public search fallback...")
        results = search_public_engine(query, max_results)

    return results


# ==============================================================================
# 7. CRAWL & EVALUATION PIPELINE
# ==============================================================================

def crawl_and_evaluate(url: str, initial_title: str, query: str) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """
    Crawls target website, inspects contact info, identifies intent & lead type,
    and returns (lead_dict, rejection_info).
    """
    html = fetch_page(url)
    domain = get_domain(url)

    if not html:
        return None, {
            "Company Name": domain.title(),
            "Website URL": url,
            "Rejection Reason": "Website unreachable / timeout"
        }

    soup = BeautifulSoup(html, "html.parser")
    page_text = soup.get_text(separator=" ", strip=True)

    company_name = extract_company_name(soup, url)
    emails = set(extract_clean_emails(html, soup))
    phones = set(extract_clean_indian_phones(html, soup))

    # If contact info is missing, search contact / about subpages
    if not emails or not phones:
        subpages = discover_contact_links(soup, url)
        for sub_url in subpages:
            time.sleep(REQUEST_DELAY)
            sub_html = fetch_page(sub_url)
            if sub_html:
                sub_soup = BeautifulSoup(sub_html, "html.parser")
                page_text += " " + sub_soup.get_text(separator=" ", strip=True)
                emails.update(extract_clean_emails(sub_html, sub_soup))
                phones.update(extract_clean_indian_phones(sub_html, sub_soup))
                if emails and phones:
                    break

    # Analyze intent and classify lead type
    intent, lead_type, signals = analyze_intent_and_type(page_text, company_name)
    has_email = len(emails) > 0
    has_phone = len(phones) > 0

    score = calculate_lead_score(signals, has_email, has_phone)

    lead_record = {
        "Company Name": company_name,
        "Website URL": url,
        "Email": ", ".join(sorted(emails)) if emails else "N/A",
        "Mobile Number": ", ".join(sorted(phones)) if phones else "N/A",
        "Search Query": query,
        "Intent": intent,
        "Lead Type": lead_type,
        "Lead Score": score,
        "domain": domain
    }

    # Evaluate quality threshold
    if score >= MIN_LEAD_SCORE:
        return lead_record, {}
    else:
        rejection_reason = f"Score {score} below threshold {MIN_LEAD_SCORE} (Type: {lead_type})"
        return None, {
            "Company Name": company_name,
            "Website URL": url,
            "Rejection Reason": rejection_reason,
            "Lead Type": lead_type,
            "Score": score
        }


# ==============================================================================
# 8. MAIN ORCHESTRATOR
# ==============================================================================

def main():
    print("=" * 70)
    print("     IT & SOFTWARE HIRING - ACCURACY LEAD SCRAPER")
    print("=" * 70)
    print(f"Configured Queries:    {len(SEARCH_QUERIES)}")
    print(f"Location Filter:       {SEARCH_LOCATION if SEARCH_LOCATION else 'Global'}")
    print(f"Max Results Per Query: {MAX_RESULTS_PER_QUERY}")
    print(f"Min Lead Score:        {MIN_LEAD_SCORE}")
    print("=" * 70 + "\n")

    total_search_results = 0
    filtered_results_count = 0
    candidate_sites: List[Dict[str, str]] = []
    seen_domains: Set[str] = set()

    # Step 1: Execute Searches
    for raw_query in SEARCH_QUERIES:
        query = f"{raw_query} {SEARCH_LOCATION}".strip() if SEARCH_LOCATION else raw_query
        print(f'[SEARCH] Query: {query}')
        results = search_web(query, MAX_RESULTS_PER_QUERY)
        print(f'[SEARCH] Found: {len(results)} results\n')
        total_search_results += len(results)

        for res in results:
            url = res["url"]
            domain = get_domain(url)
            is_valid, reason = filter_search_result(url, res.get("title", ""))

            if not is_valid:
                print(f'[FILTER] {domain} -> REJECTED ({reason})')
                filtered_results_count += 1
                continue

            if domain not in seen_domains:
                seen_domains.add(domain)
                print(f'[FILTER] {domain} -> ACCEPTED')
                candidate_sites.append(res)
            else:
                filtered_results_count += 1

        time.sleep(REQUEST_DELAY)

    print(f"\n[INFO] {len(candidate_sites)} unique candidate websites ready for crawling.\n")

    # Step 2: Crawl Candidates & Evaluate
    accepted_leads: Dict[str, Dict[str, Any]] = {}  # keyed by domain for deduplication
    rejected_leads: List[Dict[str, Any]] = []

    count_buyers = 0
    count_providers = 0

    for idx, item in enumerate(candidate_sites, start=1):
        url = item["url"]
        domain = get_domain(url)
        print(f'[CRAWL] [{idx}/{len(candidate_sites)}] {url}')

        lead, rej = crawl_and_evaluate(url, item.get("title", ""), item["query"])

        if lead:
            if lead["Lead Type"] == "Potential Buyer":
                count_buyers += 1
            elif lead["Lead Type"] == "IT Service Provider":
                count_providers += 1

            print(f'  [NAME]   {lead["Company Name"]}')
            print(f'  [EMAIL]  {lead["Email"]}')
            print(f'  [PHONE]  {lead["Mobile Number"]}')
            print(f'  [INTENT] {lead["Intent"]}')
            print(f'  [TYPE]   {lead["Lead Type"]}')
            print(f'  [SCORE]  {lead["Lead Score"]}')
            print(f'  [SAVE]   {lead["Company Name"]}\n')

            # Deduplicate by domain; combine queries if already seen
            if domain in accepted_leads:
                existing_q = accepted_leads[domain]["Search Query"]
                if item["query"] not in existing_q:
                    accepted_leads[domain]["Search Query"] = f"{existing_q} | {item['query']}"
            else:
                accepted_leads[domain] = lead
        else:
            print(f'  [REJECT] {rej.get("Rejection Reason", "Disqualified")}\n')
            rejected_leads.append(rej)

        time.sleep(REQUEST_DELAY)

    # Step 3: Export leads.csv
    final_leads_list = list(accepted_leads.values())
    for i, lead in enumerate(final_leads_list, start=1):
        lead["No"] = i

    columns = [
        "No", "Company Name", "Website URL", "Email",
        "Mobile Number", "Search Query", "Intent", "Lead Type", "Lead Score"
    ]

    if final_leads_list:
        df_leads = pd.DataFrame(final_leads_list)
        # Ensure all columns exist
        for col in columns:
            if col not in df_leads.columns:
                df_leads[col] = "N/A"
        df_leads = df_leads[columns]
        df_leads.to_csv(LEADS_CSV, index=False, encoding="utf-8")
        print(f"[EXPORT] Saved {len(df_leads)} high-quality leads to '{LEADS_CSV}'.")
    else:
        # Create empty CSV with columns
        pd.DataFrame(columns=columns).to_csv(LEADS_CSV, index=False, encoding="utf-8")
        print(f"[EXPORT] No leads met threshold >= {MIN_LEAD_SCORE}. Created empty '{LEADS_CSV}'.")

    # Step 4: Export rejected_leads.csv
    if rejected_leads:
        df_rejected = pd.DataFrame(rejected_leads)
        df_rejected.to_csv(REJECTED_CSV, index=False, encoding="utf-8")
        print(f"[EXPORT] Saved {len(df_rejected)} rejected candidates to '{REJECTED_CSV}'.")

    # Step 5: Summary Output
    print("\n" + "=" * 40)
    print("SCRAPING SUMMARY")
    print("=" * 40)
    print(f"Search results:       {total_search_results}")
    print(f"Filtered:             {filtered_results_count}")
    print(f"Business websites:    {len(candidate_sites)}")
    print(f"Potential buyers:     {count_buyers}")
    print(f"Service providers:    {count_providers}")
    print(f"Rejected:             {len(rejected_leads)}")
    print(f"Final leads:          {len(final_leads_list)}")
    print("=" * 40 + "\n")


if __name__ == "__main__":
    main()

"""
Apollo.io Contact Enrichment & B2B Lead Harvester
=================================================
Fetches verified decision-maker details (Founder, CEO, CTO, Owners):
- Verified direct work email
- Direct phone / mobile number
- Full name & professional title
- LinkedIn profile & company intelligence

Features:
1. Lead Enrichment: Takes existing leads with domain/website and enriches missing contact info.
2. Direct B2B Search: Direct prospecting by title, location, and keywords.
3. Credit Safety & Caching: Caches enriched domains to prevent duplicate API credit usage.
4. Rate Limiting: Respects per-run limits (APOLLO_ENRICH_LIMIT_PER_RUN) to preserve quotas.
"""

import os
import re
import csv
import json
import time
import urllib.parse
from typing import Dict, Any, List, Optional, Tuple

import requests

try:
    import env_loader
except ImportError:
    pass

APOLLO_API_KEY = os.getenv("APOLLO_API_KEY", "").strip()
APOLLO_ENRICH_LIMIT_PER_RUN = int(os.getenv("APOLLO_ENRICH_LIMIT_PER_RUN", "15"))
APOLLO_CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "apollo_cache.json")

DEFAULT_TARGET_TITLES = [
    "founder",
    "co-founder",
    "ceo",
    "owner",
    "managing director",
    "cto",
    "chief technology officer",
    "vp of engineering",
    "head of it",
    "director of technology"
]

APOLLO_BASE_URL = "https://api.apollo.io/v1"


def get_target_titles() -> List[str]:
    raw = os.getenv("APOLLO_TARGET_TITLES", "")
    if raw.strip():
        return [t.strip().lower() for t in raw.split(",") if t.strip()]
    return DEFAULT_TARGET_TITLES


def _load_cache() -> Dict[str, Any]:
    if not os.path.exists(APOLLO_CACHE_FILE):
        return {}
    try:
        with open(APOLLO_CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_cache(cache: Dict[str, Any]) -> None:
    try:
        os.makedirs(os.path.dirname(APOLLO_CACHE_FILE), exist_ok=True)
        with open(APOLLO_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[WARN] Failed to save Apollo cache: {e}")


def extract_clean_domain(url_or_domain: str) -> Optional[str]:
    """Normalizes an arbitrary URL or string down to a clean primary domain (e.g. 'company.com')."""
    if not url_or_domain or not isinstance(url_or_domain, str):
        return None
    val = url_or_domain.strip().lower()
    if not val or val in ("none", "n/a", "null", "not available"):
        return None
    
    if not val.startswith("http://") and not val.startswith("https://"):
        val = "https://" + val
        
    try:
        parsed = urllib.parse.urlparse(val)
        netloc = parsed.netloc or parsed.path
        netloc = netloc.split("/")[0].split(":")[0].strip()
        if netloc.startswith("www."):
            netloc = netloc[4:]
            
        # Ignore common aggregators, search engines & social domains
        ignored = {
            "google.com", "bing.com", "yahoo.com", "duckduckgo.com",
            "facebook.com", "instagram.com", "twitter.com", "x.com",
            "linkedin.com", "reddit.com", "youtube.com", "github.com",
            "medium.com", "t.me", "telegram.org", "wikipedia.org",
            "forms.gle", "docs.google.com", "drive.google.com"
        }
        if netloc in ignored or any(netloc.endswith("." + ign) for ign in ignored):
            return None
            
        # Must have at least one period and valid TLD length
        if "." in netloc and len(netloc.split(".")[-1]) >= 2:
            return netloc
    except Exception:
        pass
    return None


def fetch_decision_maker_by_domain(
    domain: str, 
    company_name: Optional[str] = None, 
    api_key: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Queries Apollo.io to locate the highest-ranking decision maker for a given company/domain.
    Returns contact dictionary or None.
    """
    key = api_key or APOLLO_API_KEY
    if not key:
        return None

    clean_dom = extract_clean_domain(domain)
    if not clean_dom:
        return None

    # Check cache first to save credits
    cache = _load_cache()
    if clean_dom in cache:
        cached_entry = cache[clean_dom]
        if cached_entry.get("found"):
            return cached_entry.get("data")
        return None

    headers = {
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
        "X-Api-Key": key
    }

    titles = get_target_titles()

    # Search for decision-maker people at this domain
    payload = {
        "api_key": key,
        "q_organization_domains": clean_dom,
        "person_titles": titles,
        "page": 1,
        "per_page": 5
    }

    try:
        resp = requests.post(
            f"{APOLLO_BASE_URL}/mixed_people/search",
            headers=headers,
            json=payload,
            timeout=12
        )
        
        if resp.status_code == 401:
            print("[WARN] Apollo API: Invalid or expired API Key.")
            return None
        elif resp.status_code == 429:
            print("[WARN] Apollo API: Rate limit or credit quota reached.")
            return None
        elif resp.status_code != 200:
            # Fallback to direct people match endpoint if mixed_people endpoint is restricted
            return _fallback_people_match(clean_dom, company_name, key, cache)

        data = resp.json()
        people = data.get("people", [])
        
        best_contact = None
        for person in people:
            email = person.get("email")
            # Prefer person who has email or unlocked info
            name = person.get("name") or f"{person.get('first_name', '')} {person.get('last_name', '')}".strip()
            title = person.get("title", "")
            linkedin_url = person.get("linkedin_url", "")
            
            # Extract phone numbers
            phone = ""
            phone_numbers = person.get("phone_numbers") or []
            if phone_numbers and isinstance(phone_numbers, list):
                phone = phone_numbers[0].get("raw_number") or phone_numbers[0].get("sanitized_number") or ""
            elif person.get("sanitized_phone"):
                phone = person.get("sanitized_phone")

            if name or email:
                best_contact = {
                    "full_name": name,
                    "title": title,
                    "email": email or "",
                    "mobile_number": phone,
                    "linkedin_url": linkedin_url,
                    "company_name": (person.get("organization") or {}).get("name") or company_name or "",
                    "domain": clean_dom
                }
                break

        if best_contact:
            cache[clean_dom] = {"found": True, "data": best_contact, "timestamp": time.time()}
            _save_cache(cache)
            return best_contact
        else:
            # No decision maker found under these titles, cache negative result to save requests
            cache[clean_dom] = {"found": False, "timestamp": time.time()}
            _save_cache(cache)
            return None

    except requests.exceptions.RequestException as e:
        print(f"[WARN] Apollo API connection error for '{clean_dom}': {e}")
        return None


def _fallback_people_match(
    domain: str, 
    company_name: Optional[str], 
    key: str, 
    cache: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """Secondary match endpoint in case search requires specific tier."""
    headers = {
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
        "X-Api-Key": key
    }
    payload: Dict[str, Any] = {
        "api_key": key,
        "domain": domain,
        "reveal_personal_emails": False
    }
    if company_name:
        payload["organization_name"] = company_name

    try:
        resp = requests.post(f"{APOLLO_BASE_URL}/people/match", headers=headers, json=payload, timeout=12)
        if resp.status_code == 200:
            res = resp.json().get("person")
            if res:
                name = res.get("name") or f"{res.get('first_name', '')} {res.get('last_name', '')}".strip()
                contact = {
                    "full_name": name,
                    "title": res.get("title", ""),
                    "email": res.get("email") or "",
                    "mobile_number": res.get("sanitized_phone") or "",
                    "linkedin_url": res.get("linkedin_url", ""),
                    "company_name": (res.get("organization") or {}).get("name") or company_name or "",
                    "domain": domain
                }
                cache[domain] = {"found": True, "data": contact, "timestamp": time.time()}
                _save_cache(cache)
                return contact
    except Exception:
        pass
    
    cache[domain] = {"found": False, "timestamp": time.time()}
    _save_cache(cache)
    return None


def search_apollo_prospects(
    keywords: str = "software OR ecommerce OR web development",
    locations: Optional[List[str]] = None,
    titles: Optional[List[str]] = None,
    per_page: int = 15,
    api_key: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Directly searches Apollo for new prospective client leads based on target criteria.
    Returns normalized lead dictionaries ready to add to the Master Leads database.
    """
    key = api_key or APOLLO_API_KEY
    if not key:
        print("[INFO] Apollo API key not configured. Set APOLLO_API_KEY in .env to use Apollo prospecting.")
        return []

    target_titles = titles or get_target_titles()
    target_locs = locations or ["United States", "United Kingdom", "Canada", "Australia", "India"]

    headers = {
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
        "X-Api-Key": key
    }

    payload = {
        "api_key": key,
        "q_keywords": keywords,
        "person_titles": target_titles,
        "person_locations": target_locs,
        "page": 1,
        "per_page": min(per_page, 50)
    }

    leads: List[Dict[str, Any]] = []

    try:
        print(f"[*] Querying Apollo.io for new prospects (keywords='{keywords}')...")
        resp = requests.post(f"{APOLLO_BASE_URL}/mixed_people/search", headers=headers, json=payload, timeout=15)
        if resp.status_code != 200:
            print(f"[WARN] Apollo search error ({resp.status_code}): {resp.text[:150]}")
            return []

        data = resp.json()
        people = data.get("people", [])

        now_str = time.strftime("%Y-%m-%d %H:%M:%S")

        for p in people:
            name = p.get("name") or f"{p.get('first_name', '')} {p.get('last_name', '')}".strip()
            title = p.get("title", "")
            email = p.get("email") or ""
            org = p.get("organization") or {}
            company = org.get("name") or ""
            website = org.get("primary_domain") or org.get("website_url") or ""
            if website and not website.startswith("http"):
                website = "https://" + website

            phone = ""
            phone_numbers = p.get("phone_numbers") or []
            if phone_numbers and isinstance(phone_numbers, list):
                phone = phone_numbers[0].get("raw_number") or phone_numbers[0].get("sanitized_number") or ""
            elif p.get("sanitized_phone"):
                phone = p.get("sanitized_phone")

            city = p.get("city") or org.get("city") or ""
            country = p.get("country") or org.get("country") or ""
            location = f"{city}, {country}".strip(", ")

            linkedin = p.get("linkedin_url") or ""

            desc = f"{title} at {company}."
            if linkedin:
                desc += f" LinkedIn: {linkedin}"

            lead_record = {
                "full_name": name,
                "company_name": company,
                "email": email,
                "mobile_number": phone,
                "website": website,
                "description": desc,
                "source": "Apollo.io B2B Intelligence",
                "source_url": linkedin or website or "https://apollo.io",
                "location": location,
                "lead_type": "Potential Buyer",
                "intent_score": "8.0",
                "first_seen_at": now_str,
                "last_seen_at": now_str,
                "last_updated_at": now_str,
                "email_status": "NEW",
                "status": "NEW",
                "contact_channel": "email" if email else "website",
            }
            leads.append(lead_record)

        print(f"[*] Apollo.io fetched {len(leads)} verified prospective leads.")
        return leads

    except Exception as e:
        print(f"[WARN] Apollo prospect search failed: {e}")
        return []


def run_apollo_enrichment(
    master_csv_path: str = "all_leads_master.csv", 
    limit: Optional[int] = None
) -> int:
    """
    Enriches existing leads in the master CSV that have website/domain but lack 
    direct decision-maker contact details (name, email, phone).
    """
    key = os.getenv("APOLLO_API_KEY", "").strip()
    if not key:
        print("[INFO] Apollo Enrichment skipped: APOLLO_API_KEY not set in .env.")
        return 0

    if not os.path.exists(master_csv_path):
        print(f"[WARN] Master CSV not found at '{master_csv_path}'.")
        return 0

    max_calls = limit if limit is not None else APOLLO_ENRICH_LIMIT_PER_RUN
    if max_calls <= 0:
        return 0

    print(f"[*] Starting Apollo Contact Enrichment (Max budget this run: {max_calls} lookups)...")

    rows = []
    with open(master_csv_path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    if not rows or not fieldnames:
        return 0

    enriched_count = 0
    cache = _load_cache()

    for row in rows:
        if enriched_count >= max_calls:
            break

        website = row.get("website", "").strip()
        company = row.get("company_name", "").strip()
        current_email = row.get("email", "").strip()
        current_name = row.get("full_name", "").strip()
        current_phone = row.get("mobile_number", "").strip()

        # Target leads that have a website but are missing name, phone, or direct email
        needs_enrichment = False
        domain = extract_clean_domain(website)
        
        if domain:
            # If missing full name or missing phone or has only generic email
            is_generic_email = not current_email or any(current_email.lower().startswith(g) for g in ["info@", "contact@", "support@", "admin@", "sales@", "hello@"])
            if not current_name or not current_phone or is_generic_email:
                needs_enrichment = True

        if not needs_enrichment or not domain:
            continue

        # If already cached as not found, skip without counting against budget
        if domain in cache and not cache[domain].get("found"):
            continue

        contact = fetch_decision_maker_by_domain(domain, company_name=company, api_key=key)
        enriched_count += 1

        if contact:
            updated = False
            if contact.get("full_name") and not current_name:
                row["full_name"] = contact["full_name"]
                updated = True
            if contact.get("email") and (not current_email or is_generic_email):
                row["email"] = contact["email"]
                updated = True
            if contact.get("mobile_number") and not current_phone:
                row["mobile_number"] = contact["mobile_number"]
                updated = True
            if contact.get("title"):
                existing_desc = row.get("description", "")
                title_note = f"Contact: {contact.get('full_name')} ({contact.get('title')})"
                if contact.get("linkedin_url"):
                    title_note += f" | LinkedIn: {contact['linkedin_url']}"
                if title_note not in existing_desc:
                    row["description"] = (existing_desc + " " + title_note).strip()
                    updated = True

            if updated:
                row["last_updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                print(f"    [+] Enriched '{company or domain}': {contact.get('full_name')} ({contact.get('title')}) - {contact.get('email') or contact.get('mobile_number')}")

        # Sleep lightly between API calls to be polite to Apollo rate limit
        time.sleep(0.5)

    if enriched_count > 0:
        # Atomic rewrite of master CSV
        temp_csv = master_csv_path + ".tmp"
        try:
            with open(temp_csv, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            os.replace(temp_csv, master_csv_path)
            print(f"[*] [OK] Apollo enrichment finished: {enriched_count} leads processed and saved.")
        except Exception as e:
            if os.path.exists(temp_csv):
                os.remove(temp_csv)
            print(f"[ERROR] Failed to save enriched master CSV: {e}")

    return enriched_count


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Apollo.io Lead Enricher and Prospect Harvester")
    parser.add_argument("--enrich", action="store_true", help="Run contact enrichment on all_leads_master.csv")
    parser.add_argument("--search", type=str, help="Search Apollo for new prospects with keywords")
    parser.add_argument("--limit", type=int, default=15, help="Max lookups or prospects")
    args = parser.parse_args()

    if args.search:
        prospects = search_apollo_prospects(keywords=args.search, per_page=args.limit)
        print(f"Found {len(prospects)} leads.")
        for p in prospects[:5]:
            print(f"- {p['full_name']} ({p['company_name']}): {p['email']} | {p['mobile_number']}")
    elif args.enrich:
        run_apollo_enrichment(limit=args.limit)
    else:
        print("Usage:")
        print("  python apollo_enricher.py --enrich")
        print("  python apollo_enricher.py --search 'software development'")

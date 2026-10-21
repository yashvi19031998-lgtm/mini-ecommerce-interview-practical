import csv
import os
import re
import time
from typing import List, Tuple
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup

from lead_normalizer import normalize_email, normalize_phone, INVALID_DOMAINS, canonicalize_domain

MASTER_CSV = "all_leads_master.csv"

# Regex patterns for Email and Phone extraction
EMAIL_REGEX = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
PHONE_REGEX = r"(\+?\d[\d\s\-\(\)]{8,15}\d)"


def is_likely_valid_phone(phone_str: str) -> bool:
    """Verifies that the phone string has valid format and is not a timestamp or serial."""
    digits = re.sub(r"\D", "", phone_str)
    if len(digits) < 10 or len(digits) > 13:
        return False
    if len(set(digits)) <= 3:
        return False
    if phone_str.startswith("+91") or phone_str.startswith("079-"):
        return True
    if len(digits) == 10 and digits[0] in "6789":
        return True
    if phone_str.startswith("+"):
        return True
    return False


def extract_contacts_from_url(url: str) -> Tuple[List[str], List[str]]:
    """Visits a website and its contact/about pages to scrape emails and phones."""
    found_emails = set()
    found_phones = set()

    if not url or url.lower() in ("n/a", "none", "not available"):
        return [], []

    # Skip aggregator or blacklisted domains
    parsed_netloc = urlparse(url if "://" in url else "https://" + url).netloc.lower()
    if parsed_netloc.startswith("www."):
        parsed_netloc = parsed_netloc[4:]
    if ":" in parsed_netloc:
        parsed_netloc = parsed_netloc.split(":")[0]

    blocked_domains = INVALID_DOMAINS | {
        "youtube.com", "imdb.com", "netflix.com", "wikipedia.org", "reddit.com",
        "google.com", "linkedin.com", "twitter.com", "x.com", "facebook.com",
        "instagram.com", "w3schools.com", "microsoft.com", "apple.com", "amazon.com",
        "simplilearn.com", "computerhope.com", "techtarget.com", "britannica.com",
        "forms.gle", "docs.google.com"
    }
    if not parsed_netloc or parsed_netloc in blocked_domains or any(b in parsed_netloc for b in blocked_domains):
        return [], []

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }

    try:
        # Normalize URL
        if not url.startswith("http://") and not url.startswith("https://"):
            url = "https://" + url

        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return list(found_emails), list(found_phones)

        html_content = response.text

        # 1. Scan Homepage content
        emails = re.findall(EMAIL_REGEX, html_content)
        for e in emails:
            norm_e = normalize_email(e)
            if norm_e:
                found_emails.add(norm_e)

        phones = re.findall(PHONE_REGEX, html_content)
        for p in phones:
            norm_p = normalize_phone(p)
            if norm_p and is_likely_valid_phone(norm_p):
                found_phones.add(norm_p)

        # 2. Look for Contact Us / About Us subpages
        soup = BeautifulSoup(html_content, "html.parser")
        contact_links = set()

        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            text = a_tag.get_text().lower()
            if any(keyword in href.lower() or keyword in text for keyword in ["contact", "about", "reach", "support", "touch"]):
                full_link = urljoin(url, href)
                # Ensure it belongs to the same domain
                if urlparse(full_link).netloc == urlparse(url).netloc:
                    contact_links.add(full_link)

        # 3. Visit discovered subpages (limit to top 3 to keep it fast)
        for sub_url in list(contact_links)[:3]:
            try:
                sub_res = requests.get(sub_url, headers=headers, timeout=6)
                if sub_res.status_code == 200:
                    sub_html = sub_res.text

                    sub_emails = re.findall(EMAIL_REGEX, sub_html)
                    for e in sub_emails:
                        norm_e = normalize_email(e)
                        if norm_e:
                            found_emails.add(norm_e)

                    sub_phones = re.findall(PHONE_REGEX, sub_html)
                    for p in sub_phones:
                        norm_p = normalize_phone(p)
                        if norm_p and is_likely_valid_phone(norm_p):
                            found_phones.add(norm_p)
            except Exception:
                continue

    except Exception as err:
        print(f"       -> [WARN] Error crawling {url}: {err}")

    return sorted(list(found_emails)), sorted(list(found_phones))


def run_website_enrichment(master_csv_path: str = MASTER_CSV) -> int:
    """Reads master CSV, checks for missing emails/phones, crawls websites, and updates CSV safely."""
    if not os.path.exists(master_csv_path):
        print(f"[ERROR] Master CSV '{master_csv_path}' not found!")
        return 0

    print(f"[INFO] Loading master leads from '{master_csv_path}'...")
    rows = []
    fieldnames = []

    with open(master_csv_path, mode="r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = list(reader)

    print(f"[INFO] Total leads loaded: {len(rows)}")
    updated_count = 0

    for idx, row in enumerate(rows, start=1):
        website = (row.get("website") or "").strip()
        current_email = (row.get("email") or "").strip()
        current_phone = (row.get("mobile_number") or row.get("phone") or "").strip()

        # Check if website exists and if either email or phone is missing/N/A
        needs_email = not current_email or current_email.upper() in ["N/A", "NOT AVAILABLE", "NONE", ""]
        needs_phone = not current_phone or current_phone.upper() in ["N/A", "NOT AVAILABLE", "NONE", ""]

        if website and website.upper() not in ["N/A", "NONE", ""] and (needs_email or needs_phone):
            print(f"[{idx}/{len(rows)}] Crawling website for enrichment: {website}...")
            emails, phones = extract_contacts_from_url(website)

            changed = False
            if needs_email and emails:
                existing_set = set(current_email.split(", ")) - {""}
                new_set = existing_set | set(emails)
                row["email"] = ", ".join(sorted(new_set))
                print(f"       -> Found Emails: {row['email']}")
                changed = True

            if needs_phone and phones:
                primary_phone = phones[0]
                if "mobile_number" in row:
                    row["mobile_number"] = primary_phone
                else:
                    row["phone"] = primary_phone
                print(f"       -> Found Phone: {primary_phone}")
                changed = True

            if changed:
                row["last_updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                updated_count += 1

            time.sleep(1)  # Cooldown between requests

    # Save updated data back to master CSV safely using temporary file
    if updated_count > 0:
        print(f"\n[INFO] Saving {updated_count} enriched leads back to '{master_csv_path}'...")
        temp_file = f"{master_csv_path}.tmp"
        try:
            with open(temp_file, mode="w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            os.replace(temp_file, master_csv_path)
            print(f"[SUCCESS] Website Contact Extraction complete! Enriched {updated_count} records.")
        except Exception as e:
            print(f"[ERROR] Failed to save updated CSV: {e}")
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except Exception:
                    pass
    else:
        print("[INFO] No leads required enrichment.")

    return updated_count


if __name__ == "__main__":
    run_website_enrichment()

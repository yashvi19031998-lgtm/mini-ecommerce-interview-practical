"""
Lead Generation & Business Intelligence Engine (Deep Contact Enrichment)
------------------------------------------------------------------------
Features:
  1. Multi-Source: Reddit [Hiring] Clients, We Work Remotely, and Justdial.
  2. Deep Contact Extraction:
     - Justdial specific phone decoders (tel: tags, call buttons, data attributes).
     - Obfuscated email decoders (e.g., 'user [at] domain [dot] com', 'user(at)domain.com').
     - Deep Website Visitor: If a website is found, it crawls the website & /contact page to fetch real emails and phones!
  3. Deduplication & Master CSV storage.
"""

import csv
import datetime
import html
import os
import random
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Dict, List, Optional, Set
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


MASTER_CSV_FILE = "master_leads.csv"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]

CSV_HEADERS = [
    "Business Name/Title",
    "Source",
    "Category",
    "City",
    "Phone",
    "Email",
    "Telegram",
    "Website",
    "URL",
    "Snippet",
    "Scraped At",
]


@dataclass
class Lead:
    title: str
    source: str
    category: str
    city: str
    phone: str
    email: str
    telegram: str
    website: str
    url: str
    snippet: str
    scraped_at: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "Business Name/Title": self.title,
            "Source": self.source,
            "Category": self.category,
            "City": self.city,
            "Phone": self.phone,
            "Email": self.email,
            "Telegram": self.telegram,
            "Website": self.website,
            "URL": self.url,
            "Snippet": self.snippet,
            "Scraped At": self.scraped_at,
        }


class ContactExtractor:
    """Robust extraction for Emails, Obfuscated Emails, Telegrams, and Phone Numbers."""

    # Standard email regex
    EMAIL_REGEX = re.compile(
        r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", re.IGNORECASE
    )

    # Obfuscated emails: e.g. "john [at] gmail [dot] com", "dev(at)company.com"
    OBFUSCATED_EMAIL_REGEX = re.compile(
        r"([a-zA-Z0-9_.+-]+)\s*(?:\[at\]|\(at\)|@|\sat\s)\s*([a-zA-Z0-9-]+)\s*(?:\[dot\]|\(dot\)|\.|\sdot\s)\s*([a-zA-Z]{2,6})",
        re.IGNORECASE,
    )

    TELEGRAM_REGEX = re.compile(
        r"(?:https?:\/\/t\.me\/|@)([a-zA-Z0-9_]{5,32})\b", re.IGNORECASE
    )

    # Phone numbers: Indian (+91, 10-digit mobile, STD landline) and international formats
    PHONE_REGEX = re.compile(
        r"(?:(?:\+?91[\s-]?)?[6-9]\d{9}|0\d{2,4}[-\s]?\d{6,8}|\+?\d{1,3}[-.\s]\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4})",
        re.IGNORECASE,
    )

    @classmethod
    def clean_text(cls, raw_html: str) -> str:
        if not raw_html:
            return ""
        stripped = re.sub(r"<[^>]+>", " ", raw_html)
        return " ".join(html.unescape(stripped).split())

    @classmethod
    def extract_emails(cls, text: str) -> str:
        found = set()

        # 1. Standard emails
        for m in cls.EMAIL_REGEX.findall(text):
            clean = m.strip(".,;:?!'\"")
            if not re.search(r"\.(png|jpg|jpeg|gif|webp|svg|ico)$", clean, re.I):
                if not any(dummy in clean.lower() for dummy in ["example.com", "user@domain", "test@test", "wixpress"]):
                    found.add(clean.lower())

        # 2. Obfuscated emails (e.g. name [at] gmail.com)
        for user, domain, tld in cls.OBFUSCATED_EMAIL_REGEX.findall(text):
            candidate = f"{user}@{domain}.{tld}".lower()
            if not any(dummy in candidate for dummy in ["example.com", "test@"]):
                found.add(candidate)

        return ", ".join(sorted(found)) if found else "N/A"

    @classmethod
    def extract_telegram(cls, text: str) -> str:
        matches = cls.TELEGRAM_REGEX.findall(text)
        valid = set()
        for m in matches:
            if m.lower() not in ["gmail", "yahoo", "outlook", "channel", "group", "reddit", "here", "twitter"]:
                valid.add(f"@{m}")
        return ", ".join(sorted(valid)) if valid else "N/A"

    @classmethod
    def extract_phones(cls, text: str) -> str:
        matches = cls.PHONE_REGEX.findall(text)
        valid = set()
        for m in matches:
            digits = re.sub(r"\D", "", m)
            if 10 <= len(digits) <= 13:
                valid.add(m.strip())
        return ", ".join(sorted(valid)) if valid else "N/A"

    @classmethod
    def deep_crawl_website(cls, website_url: str, session: requests.Session) -> Dict[str, str]:
        """Crawls a company website homepage and /contact page to extract emails & phones."""
        contacts = {"email": "N/A", "phone": "N/A"}
        if not website_url or not website_url.startswith("http"):
            return contacts

        try:
            resp = session.get(website_url, timeout=7, headers={"User-Agent": random.choice(USER_AGENTS)})
            if resp.status_code == 200:
                html_text = resp.text
                emails = cls.extract_emails(html_text)
                phones = cls.extract_phones(html_text)

                if emails != "N/A":
                    contacts["email"] = emails
                if phones != "N/A":
                    contacts["phone"] = phones

                # If no email found on homepage, try /contact
                if contacts["email"] == "N/A":
                    soup = BeautifulSoup(html_text, "html.parser")
                    contact_link = None
                    for a in soup.find_all("a", href=True):
                        href = a["href"].lower()
                        if "contact" in href or "about" in href:
                            contact_link = urljoin(website_url, a["href"])
                            break

                    if contact_link:
                        c_resp = session.get(contact_link, timeout=5, headers={"User-Agent": random.choice(USER_AGENTS)})
                        if c_resp.status_code == 200:
                            c_emails = cls.extract_emails(c_resp.text)
                            c_phones = cls.extract_phones(c_resp.text)
                            if c_emails != "N/A":
                                contacts["email"] = c_emails
                            if c_phones != "N/A" and contacts["phone"] == "N/A":
                                contacts["phone"] = c_phones

        except Exception:
            pass

        return contacts


class LeadStore:
    def __init__(self, filename: str = MASTER_CSV_FILE):
        self.filename = filename
        self.seen_identifiers: Set[str] = set()
        self._initialize_storage()

    def _initialize_storage(self):
        if not os.path.exists(self.filename):
            with open(self.filename, mode="w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
                writer.writeheader()
        else:
            with open(self.filename, mode="r", newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    url = (row.get("URL") or "").strip()
                    title = (row.get("Business Name/Title") or "").strip().lower()
                    if url:
                        self.seen_identifiers.add(url)
                    if title:
                        self.seen_identifiers.add(title)

    def is_duplicate(self, title: str, url: str) -> bool:
        if url and url.strip() in self.seen_identifiers:
            return True
        if title and title.strip().lower() in self.seen_identifiers:
            return True
        return False

    def save_lead(self, lead: Lead) -> bool:
        if self.is_duplicate(lead.title, lead.url):
            return False

        with open(self.filename, mode="a", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
            writer.writerow(lead.to_dict())

        if lead.url:
            self.seen_identifiers.add(lead.url.strip())
        if lead.title:
            self.seen_identifiers.add(lead.title.strip().lower())
        return True


class RssLeadHarvester:
    """Captures client leads from public RSS/Atom feeds with deep post inspection."""

    def __init__(self, store: LeadStore):
        self.store = store
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": random.choice(USER_AGENTS)})

    def scrape_reddit_hiring(self, subreddit: str = "forhire", limit: int = 25) -> int:
        url = f"https://www.reddit.com/r/{subreddit}/new/.rss"
        print(f"\n[RSS] Fetching Reddit r/{subreddit}...")
        count = 0

        try:
            resp = self.session.get(url, timeout=15)
            if resp.status_code != 200:
                print(f"[WARN] Reddit status {resp.status_code}")
                return 0

            root = ET.fromstring(resp.content)
            namespace = {"atom": "http://www.w3.org/2005/Atom"}
            entries = root.findall("atom:entry", namespace)

            for entry in entries:
                if count >= limit:
                    break

                title_el = entry.find("atom:title", namespace)
                title = title_el.text if title_el is not None else ""
                title_lower = title.lower()

                # Strictly client hiring
                if "[for hire]" in title_lower or "[for-hire]" in title_lower:
                    continue
                if "[hiring]" not in title_lower and "hiring" not in title_lower:
                    continue

                link_el = entry.find("atom:link", namespace)
                post_url = link_el.attrib.get("href", "") if link_el is not None else ""

                content_el = entry.find("atom:content", namespace)
                raw_content = content_el.text if content_el is not None else ""
                clean_content = ContactExtractor.clean_text(raw_content)

                full_text = f"{title} {clean_content}"
                email = ContactExtractor.extract_emails(full_text)
                telegram = ContactExtractor.extract_telegram(full_text)
                phone = ContactExtractor.extract_phones(full_text)

                # Check if client provided external website / form
                website = "N/A"
                urls = re.findall(r'https?://[^\s<>"]+|www\.[^\s<>"]+', clean_content)
                for u in urls:
                    if "reddit.com" not in u and "redd.it" not in u:
                        website = u
                        break

                # If website exists and email is missing, crawl website
                if website != "N/A" and email == "N/A":
                    enriched = ContactExtractor.deep_crawl_website(website, self.session)
                    if enriched["email"] != "N/A":
                        email = enriched["email"]
                    if enriched["phone"] != "N/A" and phone == "N/A":
                        phone = enriched["phone"]

                lead = Lead(
                    title=title.replace("[Hiring]", "").replace("[HIRING]", "").strip(),
                    source=f"Reddit (r/{subreddit})",
                    category="Client Hiring",
                    city="Remote / Worldwide",
                    phone=phone,
                    email=email,
                    telegram=telegram,
                    website=website,
                    url=post_url,
                    snippet=clean_content[:250],
                    scraped_at=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                )

                if self.store.save_lead(lead):
                    count += 1
                    print(f"  [+] Client: {lead.title[:45]} | Email: {email} | Phone: {phone}")

        except Exception as e:
            print(f"[ERROR] Reddit harvester: {e}")

        return count

    def scrape_weworkremotely(self, limit: int = 15) -> int:
        category_url = "https://weworkremotely.com/categories/remote-programming-jobs.rss"
        print(f"\n[RSS] Fetching We Work Remotely...")
        count = 0

        try:
            resp = self.session.get(category_url, timeout=15)
            if resp.status_code != 200:
                return 0

            root = ET.fromstring(resp.content)
            items = root.findall(".//item")

            for item in items:
                if count >= limit:
                    break

                title = item.findtext("title", default="").strip()
                link = item.findtext("link", default="").strip()
                description = ContactExtractor.clean_text(item.findtext("description", default=""))

                combined = f"{title} {description}"
                email = ContactExtractor.extract_emails(combined)
                phone = ContactExtractor.extract_phones(combined)
                telegram = ContactExtractor.extract_telegram(combined)

                # WWR jobs link directly to hiring company
                website = link
                if email == "N/A":
                    enriched = ContactExtractor.deep_crawl_website(website, self.session)
                    if enriched["email"] != "N/A":
                        email = enriched["email"]
                    if enriched["phone"] != "N/A" and phone == "N/A":
                        phone = enriched["phone"]

                lead = Lead(
                    title=title,
                    source="WeWorkRemotely",
                    category="Remote Programming",
                    city="Remote",
                    phone=phone,
                    email=email,
                    telegram=telegram,
                    website=website,
                    url=link,
                    snippet=description[:250],
                    scraped_at=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                )

                if self.store.save_lead(lead):
                    count += 1
                    print(f"  [+] Job: {title[:40]} | Email: {email} | Phone: {phone}")

        except Exception as e:
            print(f"[ERROR] WWR: {e}")

        return count


class PlaywrightJustdialScraper:
    """Automates Justdial with phone unpacking and website enrichment."""

    def __init__(self, store: LeadStore):
        self.store = store
        self.session = requests.Session()

    def _extract_card_phone(self, card) -> str:
        # Check tel links
        for link in card.locator('a[href^="tel:"]').all():
            href = link.get_attribute("href")
            if href:
                digits = re.sub(r"[^\d+]", "", href.replace("tel:", ""))
                if len(digits) >= 8:
                    return digits

        # Check call buttons & attributes
        for sel in ['[class*="callcontent"]', '[class*="contact"]', '[class*="phone"]', '[class*="call"]', 'span[data-phone]']:
            for el in card.locator(sel).all():
                txt = el.inner_text().strip()
                match = re.search(r"(\+?\d[\d\s\-]{8,15}\d)", txt)
                if match:
                    return match.group(1).replace(" ", "").replace("-", "")

        return "N/A"

    def scrape(self, search_query: str = "Software-Developers", location: str = "Ahmedabad", max_results: int = 25, headless: bool = True) -> int:
        if not PLAYWRIGHT_AVAILABLE:
            print("[ERROR] Playwright not found. Run pip install playwright.")
            return 0

        url = f"https://www.justdial.com/{location}/{search_query}"
        print(f"\n[JUSTDIAL] Launching Playwright ({search_query} in {location})...")
        count = 0

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=headless,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
            )

            context = browser.new_context(
                user_agent=random.choice(USER_AGENTS),
                viewport={"width": 1366, "height": 768},
                locale="en-IN",
                timezone_id="Asia/Kolkata",
            )
            page = context.new_page()

            try:
                page.goto(url, timeout=60000, wait_until="domcontentloaded")
                time.sleep(3.5)

                # Close popups
                for close_btn in ['span[class*="icon_cross"]', 'button[class*="close"]', '.closebtn', '#login-close']:
                    try:
                        if page.locator(close_btn).first.is_visible(timeout=1000):
                            page.locator(close_btn).first.click()
                    except Exception:
                        pass

                scroll_cycles = 0
                while count < max_results and scroll_cycles < 15:
                    cards = page.locator('div[class*="resultbox"], div.store-details, div[class*="jsx-"][class*="card"]').all()

                    for card in cards:
                        if count >= max_results:
                            break

                        try:
                            name_el = card.locator('h2, [class*="resultbox_title"], [class*="store-name"]').first
                            if name_el.count() == 0:
                                continue
                            name = name_el.inner_text().strip()
                            if not name:
                                continue

                            link_el = card.locator("a[href*='/jd']").first
                            detail_url = link_el.get_attribute("href") if link_el.count() > 0 else url

                            if self.store.is_duplicate(name, detail_url):
                                continue

                            addr_el = card.locator('[class*="address"], [class*="resultbox_address"]').first
                            address = addr_el.inner_text().strip() if addr_el.count() > 0 else "N/A"

                            phone = self._extract_card_phone(card)

                            # Extract website if present on listing
                            website = "N/A"
                            for a in card.locator('a[href^="http"]').all():
                                h = a.get_attribute("href")
                                if h and "justdial.com" not in h and "google.com" not in h:
                                    website = h
                                    break

                            email = "N/A"
                            # If website exists, deep crawl to extract official email & phone
                            if website != "N/A":
                                enriched = ContactExtractor.deep_crawl_website(website, self.session)
                                if enriched["email"] != "N/A":
                                    email = enriched["email"]
                                if enriched["phone"] != "N/A" and phone == "N/A":
                                    phone = enriched["phone"]

                            lead = Lead(
                                title=name,
                                source="Justdial",
                                category=search_query.replace("-", " "),
                                city=location,
                                phone=phone,
                                email=email,
                                telegram="N/A",
                                website=website,
                                url=detail_url,
                                snippet=address.replace("\n", " "),
                                scraped_at=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            )

                            if self.store.save_lead(lead):
                                count += 1
                                print(f"  [+] Business: {name[:40]} | Phone: {phone} | Email: {email} | Web: {website[:30]}")

                        except Exception:
                            continue

                    page.mouse.wheel(0, random.randint(1200, 1600))
                    time.sleep(random.uniform(2.0, 3.0))
                    scroll_cycles += 1

            except Exception as e:
                print(f"[ERROR] Playwright: {e}")
            finally:
                browser.close()

        return count


def run_lead_pipeline():
    print("=" * 70)
    print("    MULTI-SOURCE LEAD GENERATION WITH DEEP CONTACT ENRICHMENT    ")
    print("=" * 70)

    store = LeadStore(MASTER_CSV_FILE)
    print(f"[*] Database: '{MASTER_CSV_FILE}' (Existing: {len(store.seen_identifiers)} leads)")

    # 1. Harvest RSS Feeds (Reddit Hiring Clients & We Work Remotely)
    rss = RssLeadHarvester(store)
    reddit_leads = rss.scrape_reddit_hiring(subreddit="forhire", limit=15)
    wwr_leads = rss.scrape_weworkremotely(limit=10)

    # 2. Harvest Justdial Local Businesses via Playwright
    jd_scraper = PlaywrightJustdialScraper(store)
    jd_leads = jd_scraper.scrape(
        search_query="Software-Developers",
        location="Ahmedabad",
        max_results=15,
        headless=True,
    )

    print("\n" + "=" * 70)
    print(f"[✔] Total New Leads Saved: {reddit_leads + wwr_leads + jd_leads}")
    print(f"[✔] Output File: {os.path.abspath(MASTER_CSV_FILE)}")
    print("=" * 70)


if __name__ == "__main__":
    run_lead_pipeline()

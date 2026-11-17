"""Finds the e-mail address and phone number of a lead from its own website.

Where contacts come from, most reliable first:
  1. mailto: / tel: / WhatsApp (wa.me) links and schema.org JSON-LD (email, telephone)
  2. Cloudflare-protected e-mails (data-cfemail) and written-out ones ("info [at] acme [dot] com")
  3. the visible page text - never scripts, styles or attributes, so version strings ("core@2.11.8"),
     image names ("logo@2x.png") and long IDs are not taken for contacts
Pages: the home page, then contact / about pages it links to, then /contact, /contact-us, /about-us.
E-mails on the site's own domain come first (auto-mail uses the first one); addresses of other companies
(theme authors, plugins, tracking services) are dropped when the site has its own.

run_website_enrichment() fills missing contacts in the master file. It skips leads that are not real buyers
or prospects (job boards, articles, irrelevant pages), does not re-crawl a site checked in the last
ENRICH_RECHECK_DAYS days, and stops after ENRICH_MAX_SECONDS so a scraper run stays short.
"""
import csv
import datetime
import json
import os
import re
import time
from typing import Dict, List, Optional, Tuple
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from lead_normalizer import INVALID_DOMAINS, normalize_email, normalize_phone

MASTER_CSV = "all_leads_master.csv"
CHECKS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "contact_checks.json")
MAX_SECONDS = int(os.getenv("ENRICH_MAX_SECONDS", "420"))
MAX_SITES = int(os.getenv("ENRICH_MAX_SITES", "150"))
RECHECK_DAYS = int(os.getenv("ENRICH_RECHECK_DAYS", "14"))
MAX_PAGES = 4

EMAIL_REGEX = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)*\.[a-zA-Z]{2,24}"
PHONE_REGEX = r"(\+?\d[\d\s\-\(\)\.]{8,16}\d)"
_OBFUSCATED = re.compile(r"([a-zA-Z0-9_.+-]+)\s*(?:\[at\]|\(at\)|\{at\}|\s+at\s+)\s*([a-zA-Z0-9-]+)"
                         r"\s*(?:\[dot\]|\(dot\)|\{dot\}|\s+dot\s+)\s*([a-zA-Z]{2,24}(?:\s*(?:\[dot\]|\(dot\)|\s+dot\s+)\s*[a-zA-Z]{2,6})?)",
                         re.I)
_DOT = re.compile(r"\s*(?:\[dot\]|\(dot\)|\s+dot\s+)\s*", re.I)
FREE_MAIL = {"gmail.com", "yahoo.com", "yahoo.co.in", "outlook.com", "hotmail.com", "rediffmail.com", "icloud.com",
             "live.com", "aol.com", "protonmail.com", "zoho.com", "ymail.com"}
CONTACT_WORDS = ("contact", "reach", "touch", "support", "enquir", "inquir", "about", "connect", "location")
FALLBACK_PATHS = ("/contact", "/contact-us", "/about-us")
BLOCKED_DOMAINS = INVALID_DOMAINS | {
    "youtube.com", "imdb.com", "netflix.com", "wikipedia.org", "reddit.com", "google.com", "linkedin.com",
    "twitter.com", "x.com", "facebook.com", "instagram.com", "w3schools.com", "microsoft.com", "apple.com",
    "amazon.com", "amazon.in", "simplilearn.com", "computerhope.com", "techtarget.com", "britannica.com",
    "forms.gle", "docs.google.com", "github.com", "medium.com", "quora.com", "indeed.com", "naukri.com",
    "glassdoor.com", "upwork.com", "freelancer.com", "fiverr.com", "ycombinator.com", "news.ycombinator.com",
    "rottentomatoes.com", "irctc.co.in", "gov.in", "nic.in", "telegram.org", "t.me", "wa.me", "bit.ly",
}
# leads that are not worth crawling (no buyer behind them)
SKIP_CATEGORIES = {"irrelevant", "job_board_or_directory", "job_seeker", "service_provider"}
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                         "Chrome/124.0.0.0 Safari/537.36"}


def is_likely_valid_phone(phone_str: str) -> bool:
    """Has the shape of a real phone number (not a timestamp, ID or serial)."""
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


def site_domain(url: str) -> str:
    net = urlparse(url if "://" in url else "https://" + url).netloc.lower().split(":")[0]
    return net[4:] if net.startswith("www.") else net


def _blocked(domain: str) -> bool:
    return not domain or any(domain == b or domain.endswith("." + b) for b in BLOCKED_DOMAINS)


def _fetch(url: str, timeout: int = 10) -> str:
    try:
        from html_cache_manager import fetch_or_get_cached_html
    except ImportError:
        fetch_or_get_cached_html = None
    try:
        if fetch_or_get_cached_html:
            html, ok = fetch_or_get_cached_html(url, headers=HEADERS, timeout=timeout)
            return html if ok == 1 and html else ""
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        return r.text if r.status_code == 200 else ""
    except Exception:
        return ""


def _cf_decode(hexstr: str) -> str:
    """Cloudflare e-mail protection: first byte is the XOR key."""
    try:
        key = int(hexstr[:2], 16)
        return "".join(chr(int(hexstr[i:i + 2], 16) ^ key) for i in range(2, len(hexstr), 2))
    except ValueError:
        return ""


def contacts_from_html(html: str) -> Tuple[List[str], List[str]]:
    """(emails, phones) found in one page, reliable sources first, each list without duplicates."""
    emails: List[str] = []
    phones: List[str] = []

    def add_email(raw):
        for e in normalize_email(raw).split(", "):
            if e and e not in emails:
                emails.append(e)

    def add_phone(raw):
        p = normalize_phone(raw)
        for one in (p.split(", ") if p else []):
            if one and is_likely_valid_phone(one) and one not in phones:
                phones.append(one)

    soup = BeautifulSoup(html or "", "html.parser")
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        low = href.lower()
        if low.startswith("mailto:"):
            add_email(unquote(href[7:].split("?")[0]))
        elif low.startswith("tel:"):
            add_phone(unquote(href[4:]))
        elif "wa.me/" in low or "api.whatsapp.com/send" in low:
            m = re.search(r"(?:wa\.me/|phone=)(\+?\d{10,13})", href)
            if m:
                add_phone("+" + m.group(1).lstrip("+"))
    for tag in soup.find_all(attrs={"data-cfemail": True}):
        add_email(_cf_decode(tag["data-cfemail"]))
    for a in soup.find_all("a", href=re.compile(r"/cdn-cgi/l/email-protection#")):
        add_email(_cf_decode(a["href"].split("#", 1)[1]))
    for s in soup.find_all("script", type="application/ld+json"):
        for m in re.finditer(r'"(email|telephone)"\s*:\s*"([^"]+)"', s.string or ""):
            (add_email if m.group(1) == "email" else add_phone)(m.group(2).replace("mailto:", ""))
    for t in soup(["script", "style", "noscript", "svg", "template"]):
        t.decompose()
    text = soup.get_text(" ")
    for m in _OBFUSCATED.finditer(text):
        tail = _DOT.sub(".", m.group(3))
        add_email(m.group(1) + "@" + m.group(2) + "." + tail)
    for e in re.findall(EMAIL_REGEX, text):
        add_email(e)
    for p in re.findall(PHONE_REGEX, text):
        add_phone(p)
    return emails, phones


def rank_emails(emails: List[str], domain: str) -> List[str]:
    """Own-domain addresses first (info@ / contact@ / sales@ ... before personal ones), then free-mail ones.
    Addresses of other companies are dropped when the site has one of its own (theme, plugin or partner)."""
    parts = domain.split(".")
    base = ".".join(parts[-3:]) if len(parts) >= 3 and len(parts[-1]) == 2 and parts[-2] in ("co", "org", "net", "com", "ac")         else ".".join(parts[-2:])

    def own(e):
        d = e.split("@")[-1]
        return d == base or d.endswith("." + base)
    prefer = ["info", "contact", "hello", "sales", "enquiry", "inquiry", "business", "support", "admin", "office"]
    mine = sorted((e for e in emails if own(e)),
                  key=lambda e: prefer.index(e.split("@")[0]) if e.split("@")[0] in prefer else len(prefer))
    free = [e for e in emails if e.split("@")[-1] in FREE_MAIL and e not in mine]
    others = [e for e in emails if e not in mine and e not in free]
    return mine + free if (mine or free) else others[:2]


def _contact_pages(html: str, url: str) -> List[str]:
    soup = BeautifulSoup(html or "", "html.parser")
    host = urlparse(url).netloc
    found: List[Tuple[int, str]] = []
    for a in soup.find_all("a", href=True):
        full = urljoin(url, a["href"]).split("#")[0]
        if urlparse(full).netloc != host or full.rstrip("/") == url.rstrip("/"):
            continue
        hay = (a["href"] + " " + a.get_text(" ")).lower()
        for rank, word in enumerate(CONTACT_WORDS):
            if word in hay:
                found.append((rank, full))
                break
    out = []
    for _, u in sorted(found):
        if u not in out:
            out.append(u)
    return out


def extract_contacts_from_url(url: str) -> Tuple[List[str], List[str]]:
    """Visits a website and its contact / about pages: (emails best first, phones best first)."""
    if not url or str(url).strip().lower() in ("n/a", "none", "not available"):
        return [], []
    url = str(url).strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    domain = site_domain(url)
    if _blocked(domain):
        return [], []
    home = _fetch(url, timeout=10)
    if not home:
        return [], []
    emails, phones = contacts_from_html(home)
    pages = _contact_pages(home, url)
    root = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
    pages += [root + p for p in FALLBACK_PATHS if root + p not in pages]
    visited = 0
    for page in pages:
        if visited >= MAX_PAGES - 1 or (emails and phones and visited >= 1):
            break
        html = _fetch(page, timeout=7)
        visited += 1
        if not html:
            continue
        e2, p2 = contacts_from_html(html)
        emails += [e for e in e2 if e not in emails]
        phones += [p for p in p2 if p not in phones]
    return rank_emails(emails, domain), phones[:3]


def _real(v: str) -> bool:
    return bool(v) and v.strip().upper() not in ("N/A", "NOT AVAILABLE", "NONE", "NAN", "")


def _load_checks() -> Dict[str, str]:
    try:
        with open(CHECKS_FILE, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def _save_checks(checks: Dict[str, str]) -> None:
    try:
        os.makedirs(os.path.dirname(CHECKS_FILE), exist_ok=True)
        cutoff = (datetime.date.today() - datetime.timedelta(days=RECHECK_DAYS * 3)).isoformat()
        with open(CHECKS_FILE, "w", encoding="utf-8") as fh:
            json.dump({k: v for k, v in checks.items() if v >= cutoff}, fh)
    except OSError:
        pass


def run_website_enrichment(master_csv_path: str = MASTER_CSV, max_seconds: Optional[int] = None,
                           max_sites: Optional[int] = None) -> int:
    """Fills missing e-mails / phones from the leads' websites. Newest leads first; skips non-leads, sites
    checked in the last RECHECK_DAYS days, and stops after max_seconds / max_sites. Returns leads updated."""
    if not os.path.exists(master_csv_path):
        print(f"[ERROR] Master CSV '{master_csv_path}' not found!")
        return 0
    max_seconds = MAX_SECONDS if max_seconds is None else max_seconds
    max_sites = MAX_SITES if max_sites is None else max_sites
    with open(master_csv_path, mode="r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = list(reader)

    checks = _load_checks()
    since = (datetime.date.today() - datetime.timedelta(days=RECHECK_DAYS)).isoformat()
    todo = []
    for row in rows:
        website = (row.get("website") or "").strip()
        if not _real(website) or _blocked(site_domain(website)):
            continue
        if (row.get("ai_category") or "").strip() in SKIP_CATEGORIES:
            continue
        needs_email = not _real(row.get("email") or "")
        needs_phone = not _real(row.get("mobile_number") or row.get("phone") or "")
        if not (needs_email or needs_phone):
            continue
        if checks.get(site_domain(website), "") >= since:
            continue
        todo.append(row)
    todo.sort(key=lambda r: r.get("first_seen_at") or "", reverse=True)  # newest leads first
    print(f"[INFO] Contact search: {len(todo)} leads need an e-mail / phone (of {len(rows)}); "
          f"checking up to {max_sites} sites in {max_seconds}s")

    started, updated, checked = time.time(), 0, 0
    for row in todo:
        if checked >= max_sites or time.time() - started > max_seconds:
            print(f"[INFO] Contact search stopped after {checked} sites (time / site limit); the rest go next run.")
            break
        website = row["website"].strip()
        checked += 1
        emails, phones = extract_contacts_from_url(website)
        checks[site_domain(website)] = datetime.date.today().isoformat()
        changed = False
        if not _real(row.get("email") or "") and emails:
            row["email"] = ", ".join(emails[:3])  # best first: auto-mail uses the first address
            changed = True
        phone_col = "mobile_number" if "mobile_number" in row else "phone"
        if not _real(row.get(phone_col) or "") and phones:
            row[phone_col] = phones[0]
            changed = True
        if changed:
            row["last_updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            updated += 1
            print(f"   [{checked}] {website[:60]} -> {row.get('email') or '-'} | {row.get(phone_col) or '-'}")

    _save_checks(checks)
    if updated:
        temp_file = f"{master_csv_path}.tmp"
        try:
            with open(temp_file, mode="w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(rows)
            os.replace(temp_file, master_csv_path)
        except Exception as e:
            print(f"[ERROR] Failed to save updated CSV: {e}")
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except OSError:
                    pass
            return 0
    print(f"[SUCCESS] Contact search: {checked} sites checked, {updated} leads got an e-mail or phone.")
    return updated


if __name__ == "__main__":
    run_website_enrichment()

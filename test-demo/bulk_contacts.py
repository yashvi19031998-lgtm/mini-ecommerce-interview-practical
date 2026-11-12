"""Bulk Contacts: four tools that work on lists the user already has.

  website_contacts  many website URLs -> email / phone / social links / address from each site
                    (deep_search.crawl_site: URL guard, HTML cache, honest User-Agent, homepage + contact pages)
  verify_emails     syntax, duplicates, typo hints (gmial.com), disposable / role / free-provider flags and a DNS MX
                    lookup of the domain. No SMTP "probing" of mailboxes: it is unreliable, and it gets the sending
                    IP blacklisted.
  clean_phones      Indian numbers -> +91 format, mobile / landline / toll-free / international, fake-looking and
                    duplicate numbers flagged, and "already in Leads" (offline, no network)
  import_csv        CSV upload -> column mapping -> normalise -> duplicates (inside the file and against Leads)
                    -> save the new ones as leads

Nothing here sends e-mails or messages. Excel files: save as CSV first (no extra library is needed then).
"""
import csv
import io
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional, Tuple

import dns.exception
import dns.resolver

import deep_search
import html_cache_manager as hcm
import lead_normalizer as ln
import search_engine as se

MAX_URLS_PER_CALL = 10
MAX_EMAILS = 500
MAX_PHONES = 1000
MAX_CSV_BYTES = 5 * 1024 * 1024
MAX_CSV_ROWS = 5000
MAX_SAVE_ROWS = 1000
DNS_TIMEOUT = 4.0

EMAIL_RE = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]{1,64}@([A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+)$")
ROLE_PREFIXES = {"info", "sales", "admin", "support", "contact", "hello", "hr", "careers", "jobs", "office", "enquiry",
                 "enquiries", "inquiry", "marketing", "accounts", "billing", "help", "team", "mail", "webmaster",
                 "noreply", "no-reply", "donotreply", "postmaster", "abuse", "service", "customercare", "care"}
NO_REPLY = {"noreply", "no-reply", "donotreply", "do-not-reply", "mailer-daemon", "postmaster"}
FREE_PROVIDERS = {"gmail.com", "yahoo.com", "yahoo.co.in", "yahoo.in", "outlook.com", "hotmail.com", "live.com",
                  "rediffmail.com", "icloud.com", "aol.com", "protonmail.com", "proton.me", "zoho.com", "ymail.com",
                  "gmx.com", "mail.com", "msn.com"}
DISPOSABLE = {"mailinator.com", "10minutemail.com", "guerrillamail.com", "guerrillamail.net", "sharklasers.com",
              "tempmail.com", "temp-mail.org", "yopmail.com", "throwawaymail.com", "trashmail.com", "getnada.com",
              "maildrop.cc", "dispostable.com", "fakeinbox.com", "mintemail.com", "mohmal.com", "emailondeck.com",
              "tempr.email", "discard.email", "spamgourmet.com", "mailnesia.com", "mytemp.email", "tempail.com",
              "burnermail.io", "inboxkitten.com", "moakt.com", "emailfake.com", "mailpoof.com", "tmpmail.org",
              "tmail.ws", "1secmail.com", "33mail.com", "spambox.us", "trbvm.com", "wegwerfmail.de", "mail7.io"}
TYPO_DOMAINS = {"gmial.com": "gmail.com", "gmal.com": "gmail.com", "gmaill.com": "gmail.com", "gamil.com": "gmail.com",
                "gnail.com": "gmail.com", "gmail.co": "gmail.com", "gmail.con": "gmail.com", "gmail.in": "gmail.com",
                "yaho.com": "yahoo.com", "yahooo.com": "yahoo.com", "yahoo.con": "yahoo.com", "hotmial.com": "hotmail.com",
                "hotmail.co": "hotmail.com", "outlok.com": "outlook.com", "outlook.co": "outlook.com",
                "rediffmail.co": "rediffmail.com", "redifmail.com": "rediffmail.com"}

# CSV header words -> lead field (first match wins)
COLUMN_GUESSES = [
    ("email", ("email", "e-mail", "mail id", "mail")),
    ("mobile_number", ("phone", "mobile", "contact no", "contact number", "whatsapp", "tel", "cell")),
    ("website", ("website", "web site", "url", "domain", "site")),
    ("company_name", ("company", "business", "organisation", "organization", "firm", "brand", "shop", "store")),
    ("full_name", ("contact person", "full name", "name", "person", "owner")),
    ("location", ("city", "location", "address", "area", "state", "place")),
    ("description", ("notes", "note", "description", "remarks", "comment", "category", "industry")),
]
LEAD_FIELDS = ["company_name", "full_name", "email", "mobile_number", "website", "location", "description"]


# ---------------------------------------------------------------------------
# 1. Bulk website contacts
# ---------------------------------------------------------------------------

def clean_url_list(urls: Any) -> List[str]:
    if not isinstance(urls, list) or not urls:
        raise ValueError("Enter at least one website")
    if len(urls) > MAX_URLS_PER_CALL:
        raise ValueError(f"At most {MAX_URLS_PER_CALL} websites per request")
    out = []
    for u in urls:
        u = str(u or "").strip()
        if not u:
            continue
        if not u.startswith(("http://", "https://")):
            u = "https://" + u
        if len(u) > 300 or not se.domain_of(u) or "." not in se.domain_of(u):
            raise ValueError(f"Not a website: {u[:60]}")
        out.append(u)
    if not out:
        raise ValueError("Enter at least one website")
    return out


def _one_site(url: str) -> Dict[str, Any]:
    row = {"input": url, "website": deep_search.site_root(url), "domain": se.domain_of(url), "company": "", "emails": [],
           "phones": [], "address": "", "socials": {}, "pages_checked": 0, "status": "none", "error": ""}
    if se.is_platform(url):
        row.update(status="skipped", error="A directory / social page, not a company website - use the matching menu")
        return row
    try:
        deep_search.public_url_guard(row["website"])
    except hcm.BlockedUrl as e:
        row.update(status="error", error=f"Blocked: {e}")
        return row
    try:
        c = deep_search.crawl_site(url)
    except Exception as e:  # noqa: BLE001 - one site must never fail the batch
        row.update(status="error", error=f"{e.__class__.__name__}: {str(e)[:100]}")
        return row
    row.update(company=c.get("name", ""), emails=c.get("emails", []), phones=c.get("phones", []),
               address=c.get("address", ""), socials=c.get("socials", {}), pages_checked=len(c.get("pages", [])))
    if c.get("error"):
        row.update(status="error", error=c["error"])
    else:
        row["status"] = "found" if (row["emails"] or row["phones"]) else "none"
    return row


def website_contacts(urls: Any) -> Dict[str, Any]:
    clean = clean_url_list(urls)
    seen, unique = set(), []
    for u in clean:
        d = se.domain_of(u)
        if d not in seen:
            seen.add(d)
            unique.append(u)
    with ThreadPoolExecutor(max_workers=min(4, len(unique))) as pool:      # different sites in parallel
        rows = list(pool.map(_one_site, unique))
    return {"results": rows, "duplicates_skipped": len(clean) - len(unique)}


# ---------------------------------------------------------------------------
# 2. Bulk email verifier
# ---------------------------------------------------------------------------

class _MxCache:
    def __init__(self, resolver=None):
        self.resolver = resolver or dns.resolver.Resolver()
        self.resolver.lifetime = DNS_TIMEOUT
        self.cache: Dict[str, Tuple[str, str]] = {}
        self.lock = threading.Lock()

    def check(self, domain: str) -> Tuple[str, str]:
        """-> (state, detail): state is mx | a_only | no_mail | missing | unknown."""
        with self.lock:
            if domain in self.cache:
                return self.cache[domain]
        out = self._lookup(domain)
        with self.lock:
            self.cache[domain] = out
        return out

    def _resolve(self, domain: str, rtype: str):
        """One retry on a timeout: home routers sometimes drop a query when many arrive at once."""
        try:
            return self.resolver.resolve(domain, rtype)
        except dns.exception.Timeout:
            return self.resolver.resolve(domain, rtype)

    def _lookup(self, domain: str) -> Tuple[str, str]:
        try:
            answers = self._resolve(domain, "MX")
            hosts = sorted((r.preference, str(r.exchange).rstrip(".")) for r in answers)
            if hosts and all(h in ("", ".") for _, h in hosts):
                return "no_mail", "the domain says it accepts no e-mail (null MX)"
            return "mx", ", ".join(h for _, h in hosts[:2])
        except dns.resolver.NXDOMAIN:
            return "missing", "the domain does not exist"
        except dns.resolver.NoAnswer:
            try:
                self._resolve(domain, "A")
                return "a_only", "no MX record - mail may still reach the domain's server"
            except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.NoNameservers):
                return "missing", "the domain has no mail or web server"
            except dns.exception.DNSException:
                return "unknown", "DNS did not answer in time"
        except dns.resolver.NoNameservers:
            return "unknown", "the domain's DNS servers did not answer"
        except dns.exception.DNSException:
            return "unknown", "DNS did not answer in time"


def _email_list(emails: Any) -> List[str]:
    if isinstance(emails, str):
        emails = re.split(r"[\s,;]+", emails)
    if not isinstance(emails, list):
        raise ValueError("Paste a list of e-mail addresses")
    items = [str(e).strip().strip("<>\"'").rstrip(".") for e in emails if str(e).strip()]
    if not items:
        raise ValueError("Paste at least one e-mail address")
    if len(items) > MAX_EMAILS:
        raise ValueError(f"Check at most {MAX_EMAILS} e-mail addresses at a time")
    return items


def verify_emails(emails: Any, mx: Optional[_MxCache] = None, master_path: str = "") -> Dict[str, Any]:
    items = _email_list(emails)
    mx = mx or _MxCache()
    rows, seen = [], {}
    for raw in items:
        email = raw.lower()
        row = {"input": raw, "email": email, "status": "invalid", "reason": "", "suggestion": "", "domain": "",
               "role": False, "free": False, "disposable": False, "mx": "", "in_leads": False, "duplicate_of": ""}
        m = EMAIL_RE.match(email)
        if not m or ".." in email:
            row["reason"] = "Not a valid e-mail address"
            rows.append(row)
            continue
        local, domain = email.split("@", 1)
        row["domain"] = domain
        if email in seen:
            row.update(status="duplicate", reason=f"Same as line {seen[email]}", duplicate_of=str(seen[email]))
            rows.append(row)
            continue
        seen[email] = len(rows) + 1
        row["role"] = local in ROLE_PREFIXES or local.split(".")[0] in ROLE_PREFIXES
        row["free"] = domain in FREE_PROVIDERS
        row["disposable"] = domain in DISPOSABLE
        if domain in TYPO_DOMAINS:
            row.update(suggestion=f"{local}@{TYPO_DOMAINS[domain]}", reason=f"Probably a typo of {TYPO_DOMAINS[domain]}")
            rows.append(row)
            continue
        if local in NO_REPLY:
            row["reason"] = "A no-reply address - nobody reads it"
            rows.append(row)
            continue
        if row["disposable"]:
            row["reason"] = "Disposable (temporary) mailbox"
            rows.append(row)
            continue
        rows.append(row)
    # DNS for each distinct domain once, a few at a time
    domains = sorted({r["domain"] for r in rows if r["domain"] and not r["reason"] and r["status"] == "invalid"})
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = dict(zip(domains, pool.map(mx.check, domains)))
    for r in rows:
        if r["reason"] or r["status"] == "duplicate" or not r["domain"]:
            continue
        state, detail = results[r["domain"]]
        r["mx"] = detail
        if state == "mx":
            r["status"], r["reason"] = ("risky", "Role address (info@, sales@…) - fine for B2B, lower reply rate") if r["role"] \
                else ("valid", "Domain accepts e-mail")
        elif state == "a_only":
            r["status"], r["reason"] = "risky", detail
        elif state == "unknown":
            r["status"], r["reason"] = "unknown", detail
        else:
            r["reason"] = detail.capitalize()
    if master_path:
        _mark_in_leads(rows, master_path, lambda r: {"email": r["email"]} if r["status"] in ("valid", "risky", "unknown") else None)
    counts = {s: sum(r["status"] == s for r in rows) for s in ("valid", "risky", "unknown", "invalid", "duplicate")}
    return {"results": rows, "counts": counts, "domains_checked": len(domains)}


# ---------------------------------------------------------------------------
# 3. Bulk phone cleaner
# ---------------------------------------------------------------------------

PHONE_CANDIDATE = re.compile(r"\+?\d[\d\s().-]{6,20}\d")


def classify_phone(raw: str) -> Dict[str, str]:
    text = (raw or "").strip()
    digits = re.sub(r"\D", "", text)
    out = {"input": text, "e164": "", "display": "", "type": "", "status": "invalid", "reason": ""}
    if text.startswith("+") and not digits.startswith("91"):
        if 8 <= len(digits) <= 15:
            out.update(e164=f"+{digits}", display=f"+{digits}", type="International", status="valid")
        else:
            out["reason"] = "Wrong length for an international number"
        return out
    if digits.startswith(("1800", "1860")) and len(digits) in (10, 11):
        out.update(e164=f"+91{digits}", display=f"{digits[:4]} {digits[4:7]} {digits[7:]}", type="Toll-free", status="valid")
        return out
    national = digits
    if len(digits) == 12 and digits.startswith("91"):
        national = digits[2:]
    elif len(digits) == 13 and digits.startswith("091"):
        national = digits[3:]
    elif len(digits) == 11 and digits.startswith("0"):
        national = digits[1:]
    if len(national) != 10:
        out["reason"] = f"{len(digits)} digits - an Indian number has 10 (plus 0 or +91)"
        return out
    if len(set(national)) <= 2 or national in ("1234567890", "9876543210", "0123456789"):
        out["reason"] = "Looks fake (repeated or sequential digits)"
        return out
    # "079-2654 3210", "(022) 2555 1234", "011 2345 6789": a separate 0 + STD code means a landline,
    # even when the code starts with 7 / 8 / 9 (Ahmedabad 79, Bengaluru 80...)
    std = re.match(r"^\s*\(?0(\d{2,4})\)?[\s-]", text)
    if national[0] in "6789" and not std and not digits.startswith("079"):
        out.update(type="Mobile", display=f"+91 {national[:5]} {national[5:]}")
    elif national[0] != "0":
        code = std.group(1) if std else ""
        out.update(type="Landline", display=f"+91 {code} {national[len(code):]}" if code else f"+91 {national}")
    else:
        out["reason"] = "Not a valid Indian number"
        return out
    out.update(e164=f"+91{national}", status="valid")
    return out


def _phone_list(text: Any) -> List[str]:
    if isinstance(text, list):
        text = "\n".join(str(t) for t in text)
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Paste at least one phone number")
    found = []
    for line in text.splitlines():
        parts = PHONE_CANDIDATE.findall(line)
        if parts:
            found += [p.strip() for p in parts]
        elif line.strip():
            found.append(line.strip()[:40])           # shown as invalid with the reason
    if len(found) > MAX_PHONES:
        raise ValueError(f"Clean at most {MAX_PHONES} numbers at a time")
    return found


def clean_phones(text: Any, master_path: str = "") -> Dict[str, Any]:
    rows, seen = [], {}
    for raw in _phone_list(text):
        r = classify_phone(raw)
        r.update(in_leads=False, duplicate_of="")
        if r["e164"] in seen:
            r.update(status="duplicate", reason=f"Same as line {seen[r['e164']]}", duplicate_of=str(seen[r["e164"]]))
        elif r["e164"]:
            seen[r["e164"]] = len(rows) + 1
        rows.append(r)
    if master_path:
        _mark_in_leads(rows, master_path, lambda r: {"mobile_number": r["e164"]} if r["status"] == "valid" and
                       r["type"] in ("Mobile", "Landline") else None)
    counts = {s: sum(r["status"] == s for r in rows) for s in ("valid", "invalid", "duplicate")}
    counts["in_leads"] = sum(1 for r in rows if r["in_leads"])
    return {"results": rows, "counts": counts}


# ---------------------------------------------------------------------------
# 4. CSV import + dedupe
# ---------------------------------------------------------------------------

def _read_csv(text: Any) -> Tuple[List[str], List[Tuple[int, List[str]]]]:
    """-> (headers, [(spreadsheet line number, cells)]) - blank rows are skipped but keep the numbering."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("The file is empty")
    if len(text.encode("utf-8", "ignore")) > MAX_CSV_BYTES:
        raise ValueError("The file is larger than 5 MB - split it into smaller files")
    text = text.lstrip("﻿")
    sample = text[:20000]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    reader = csv.reader(io.StringIO(text), dialect)
    rows = []
    for r in reader:
        if any(c.strip() for c in r):
            rows.append((reader.line_num, r))
        if len(rows) > MAX_CSV_ROWS + 1:
            raise ValueError(f"At most {MAX_CSV_ROWS} rows per file - split it into smaller files")
    if len(rows) < 2:
        raise ValueError("The file needs a header row and at least one data row")
    headers = [h.strip()[:60] or f"Column {i + 1}" for i, h in enumerate(rows[0][1])]
    return headers, rows[1:]


def guess_mapping(headers: List[str]) -> Dict[str, str]:
    """-> {header: lead field or ''}; each lead field is used once, the most specific words first."""
    mapping, used = {h: "" for h in headers}, set()
    for field, words in COLUMN_GUESSES:
        for h in headers:
            low = h.lower()
            if mapping[h] or field in used:
                continue
            if any(re.search(rf"(^|[^a-z]){re.escape(w)}([^a-z]|$)", low) for w in words):
                mapping[h] = field
                used.add(field)
    return mapping


def preview_csv(text: Any) -> Dict[str, Any]:
    headers, rows = _read_csv(text)
    return {"headers": headers, "sample": [r[:len(headers)] for _, r in rows[:5]], "rows": len(rows),
            "mapping": guess_mapping(headers), "fields": LEAD_FIELDS}


def _clean_mapping(mapping: Any, headers: List[str]) -> Dict[int, str]:
    if not isinstance(mapping, dict):
        raise ValueError("Choose which column is which")
    out, used = {}, set()
    for i, h in enumerate(headers):
        f = mapping.get(h, "")
        if not f:
            continue
        if f not in LEAD_FIELDS:
            raise ValueError(f"Unknown field: {str(f)[:30]}")
        if f in used and f != "description":
            raise ValueError(f"Two columns are mapped to {f} - choose one")
        used.add(f)
        out[i] = f
    if not used & {"email", "mobile_number", "website", "company_name"}:
        raise ValueError("Map at least one of: email, phone, website or company")
    return out


def check_csv(text: Any, mapping: Any, source: str = "", master_path: str = "") -> Dict[str, Any]:
    headers, rows = _read_csv(text)
    cols = _clean_mapping(mapping, headers)
    source = " ".join(str(source or "").split())[:60] or "CSV import"
    out, in_file = [], {}
    for n, r in rows:                                         # line numbers as in the spreadsheet
        raw: Dict[str, str] = {}
        for i, f in cols.items():
            v = r[i].strip() if i < len(r) else ""
            if v:
                raw[f] = f"{raw[f]}; {v}" if f == "description" and raw.get(f) else v
        lead = {"line": n, "company_name": raw.get("company_name", ""), "full_name": raw.get("full_name", ""),
                "email": ln.normalize_email(raw.get("email", "")), "mobile_number": ln.normalize_phone(raw.get("mobile_number", "")),
                "website": ln.clean_url(raw.get("website", "")), "location": raw.get("location", ""),
                "description": raw.get("description", ""), "source": f"Bulk Contacts ({source})",
                "status": "new", "reason": ""}
        if lead["website"] and se.domain_of(lead["website"]) in ln.INVALID_DOMAINS:
            lead["website"] = ""
        problems = [f"{label} not valid" for label, key in (("e-mail", "email"), ("phone", "mobile_number"))
                    if raw.get(key) and not lead[key]]
        if not (lead["email"] or lead["mobile_number"] or lead["website"] or lead["company_name"]):
            lead.update(status="invalid", reason="No usable e-mail, phone, website or company" +
                        (f" ({', '.join(problems)})" if problems else ""))
            out.append(lead)
            continue
        if problems:
            lead["reason"] = ", ".join(problems).capitalize() + " - kept the rest"
        keys = [k for k in (("e", lead["email"].split(",")[0]), ("p", lead["mobile_number"].split(",")[0]),
                            ("w", se.domain_of(lead["website"]))) if k[1]]
        first = next((in_file[k] for k in keys if k in in_file), None)
        if first:
            lead.update(status="duplicate", reason=f"Same contact as line {first} in this file")
        else:
            for k in keys:
                in_file[k] = n
        out.append(lead)
    if master_path:
        # company + city counts too here (the registry uses the same rule when saving)
        _mark_in_leads(out, master_path, lambda r: r if r["status"] == "new" else None,
                       keys=("email", "mobile_number", "website", "source_url", "company_name", "location"))
        for r in out:
            if r.get("in_leads"):
                r.update(status="in_leads", reason=f"Already in Leads ({r['match']})")
    counts = {s: sum(r["status"] == s for r in out) for s in ("new", "in_leads", "duplicate", "invalid")}
    return {"results": out, "counts": counts, "rows": len(rows)}


def save_rows(rows: Any, master_path: str) -> Dict[str, Any]:
    if not isinstance(rows, list) or not rows:
        raise ValueError("Select at least one contact to save")
    if len(rows) > MAX_SAVE_ROWS:
        raise ValueError(f"Save at most {MAX_SAVE_ROWS} contacts at a time")
    counts = {"added": 0, "updated": 0, "duplicate": 0, "skipped_invalid": 0}
    registry = ln.MasterLeadRegistry(master_path)
    for r in rows:
        if not isinstance(r, dict) or not any(r.get(k) for k in ("email", "mobile_number", "website", "company_name")):
            counts["skipped_invalid"] += 1
            continue
        raw = {k: str(r.get(k) or "")[:600] for k in LEAD_FIELDS}
        raw.update(source=str(r.get("source") or "Bulk Contacts")[:80], lead_type="Imported Contact",
                   source_url=str(r.get("source_url") or ""))
        outcome, _ = registry.add_lead(raw, default_source="Bulk Contacts")
        counts[outcome] = counts.get(outcome, 0) + 1
    if not registry.save_master_safely():
        raise IOError("Could not write the leads file")
    return counts


# ---------------------------------------------------------------------------
# Shared
# ---------------------------------------------------------------------------

def _mark_in_leads(rows: List[Dict[str, Any]], master_path: str, to_lead,
                   keys: Tuple[str, ...] = ("email", "mobile_number", "website", "source_url")) -> None:
    import os
    for r in rows:
        r.setdefault("in_leads", False)
        r.setdefault("match", "")
    if not os.path.exists(master_path):
        return
    reg = ln.MasterLeadRegistry(master_path)
    for r in rows:
        lead = to_lead(r)
        if not lead:
            continue
        idx = reg.find_match({k: v for k, v in lead.items() if k in keys})
        if idx is not None:
            r["in_leads"] = True
            r["match"] = reg.leads[idx].get("company_name", "") or reg.leads[idx].get("lead_id", "")


LEAD_SOURCES = {"Bulk Contacts (Website Contacts)", "Web Crawler (Site Crawler)", "Web Crawler (Link Harvester)"}


def _lead_source(v: Any) -> str:
    return v if v in LEAD_SOURCES else "Bulk Contacts (Website Contacts)"


def website_rows_to_leads(rows: Any) -> List[Dict[str, str]]:
    """Bulk website results chosen in the UI -> rows for save_rows."""
    out = []
    for r in rows if isinstance(rows, list) else []:
        if not isinstance(r, dict) or not r.get("website"):
            continue
        socials = r.get("socials") if isinstance(r.get("socials"), dict) else {}
        out.append({"company_name": str(r.get("company") or r.get("domain") or "")[:120],
                    "email": ", ".join(str(e) for e in (r.get("emails") or [])[:3]),
                    "mobile_number": ", ".join(str(p) for p in (r.get("phones") or [])[:3]),
                    "website": str(r["website"]), "location": str(r.get("address") or "")[:200],
                    "description": "; ".join(f"{k}: {v}" for k, v in list(socials.items())[:5]),
                    "source": _lead_source(r.get("lead_source")), "source_url": str(r["website"])})
    return out

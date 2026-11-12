"""Domain Tools: four free tools (no API key).

  age          Domain Age & Expiry - registration / expiry dates, registrar, nameservers and DNS host from RDAP,
               the registries' official JSON service (bootstrap list from IANA). Registrant contact data is never read.
  dns          Email & DNS Checker - who runs the domain's e-mail (MX), SPF and DMARC, DNS host, web server address.
  new          New Domains Finder - domains registered in the last days that contain a keyword, from WhoisDS's free
               daily "newly registered domains" list (gTLDs such as .com / .net / .org / .online / .store; no .in).
               Each day's list is downloaded once and kept on disk.
  available    Domain Availability - is name.tld registered? RDAP "not found" = available; TLDs without RDAP fall
               back to DNS. Suggests variants. (A registrar has the final word: premium / reserved names exist.)

crt.sh (certificate logs) is not used: its robots.txt disallows automated access.
Every request: URL guard (public addresses only), honest User-Agent, small pauses, size limits.
"""
import base64
import datetime
import io
import json
import os
import re
import threading
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional, Tuple

import dns.exception
import dns.resolver
import requests

import bulk_contacts as bc
import deep_search
import html_cache_manager as hcm
import robots_policy
import search_engine as se

MAX_DOMAINS = 50
MAX_NEW_KEYWORDS = 5
DAY_CHOICES = (1, 3, 7)
MAX_NEW_RESULTS = 500
MAX_AVAIL_CHECKS = 30
BOOTSTRAP_URL = "https://data.iana.org/rdap/dns.json"
NRD_URL = "https://www.whoisds.com//whois-database/newly-registered-domains/{b64}/nrd"
NRD_KEEP_DAYS = 10
RDAP_HEADERS = dict(deep_search.HEADERS, Accept="application/rdap+json, application/json")
DOMAIN_RE = re.compile(r"^(?=.{4,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
TWO_PART_SUFFIXES = {"co.in", "net.in", "org.in", "firm.in", "gen.in", "ind.in", "ac.in", "edu.in", "res.in", "gov.in",
                     "co.uk", "org.uk", "com.au", "co.nz", "com.sg", "co.za", "com.br"}
AVAIL_TLDS = ["com", "in", "co.in", "net", "org", "online", "store", "shop", "site", "tech", "co", "biz", "info", "app"]
NEW_TLDS = ["com", "net", "org", "online", "store", "shop", "site", "info", "app", "tech", "xyz", "pro", "co"]
MAIL_PROVIDERS = [
    (r"google\.com$|googlemail\.com$", "Google Workspace"), (r"outlook\.com$|protection\.outlook\.com$", "Microsoft 365"),
    (r"zoho\.(com|in|eu)$", "Zoho Mail"), (r"secureserver\.net$", "GoDaddy mail"), (r"titan\.email$", "Titan (hosting mail)"),
    (r"hostinger\.(com|in)$", "Hostinger mail"), (r"rediffmailpro\.com$|rediff\.com$", "Rediffmail Pro"),
    (r"yandex\.(net|ru)$", "Yandex"), (r"icloud\.com$", "iCloud"), (r"mimecast\.com$", "Mimecast"),
    (r"pphosted\.com$", "Proofpoint"), (r"messagelabs\.com$", "Symantec"), (r"emailsrvr\.com$", "Rackspace"),
    (r"amazonaws\.com$|awsapps\.com$", "Amazon WorkMail / SES"), (r"mailgun\.org$", "Mailgun"),
    (r"netcore|pepipost", "Netcore"), (r"bluehost\.com$", "Bluehost mail"), (r"hostgator", "HostGator mail"),
]
HOSTING_MAIL = {"GoDaddy mail", "Titan (hosting mail)", "Hostinger mail", "Bluehost mail", "HostGator mail"}
DNS_PROVIDERS = [
    (r"cloudflare\.com$", "Cloudflare"), (r"domaincontrol\.com$", "GoDaddy"), (r"awsdns", "Amazon Route 53"),
    (r"googledomains\.com$|google\.com$", "Google"), (r"dns-parking\.com$|hostinger", "Hostinger"),
    (r"bluehost\.com$", "Bluehost"), (r"hostgator", "HostGator"), (r"registrar-servers\.com$", "Namecheap"),
    (r"zoho\.com$", "Zoho"), (r"azure-dns", "Azure DNS"), (r"wixdns\.net$", "Wix"), (r"shopify\.com$", "Shopify"),
    (r"bigrock\.in$|resellerclub", "BigRock / ResellerClub"), (r"nsone\.net$", "NS1"), (r"digitalocean\.com$", "DigitalOcean"),
]


# ---------------------------------------------------------------------------
# Input
# ---------------------------------------------------------------------------

def clean_domain(value: Any) -> str:
    """Domain from a domain, URL or e-mail address ('' when it is not one)."""
    v = str(value or "").strip().lower()
    if "@" in v and "/" not in v:
        v = v.split("@")[-1]
    if "://" in v or v.startswith("www."):
        v = se.domain_of(v if "://" in v else "https://" + v)
    v = v.split("/")[0].split(":")[0].strip(".")
    try:
        v = v.encode("idna").decode("ascii")
    except UnicodeError:
        return ""
    v = v[4:] if v.startswith("www.") else v
    return v if DOMAIN_RE.match(v) else ""


def registrable(domain: str) -> str:
    parts = domain.split(".")
    if len(parts) >= 3 and ".".join(parts[-2:]) in TWO_PART_SUFFIXES:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def domain_list(values: Any, limit: int = MAX_DOMAINS) -> Tuple[List[str], List[str]]:
    if isinstance(values, str):
        values = re.split(r"[\s,;]+", values)
    if not isinstance(values, list):
        raise ValueError("Enter at least one domain")
    good, bad = [], []
    for v in values:
        if not str(v).strip():
            continue
        d = clean_domain(v)
        if d:
            d = registrable(d)
            if d not in good:
                good.append(d)
        else:
            bad.append(str(v)[:60])
    if not good:
        raise ValueError("Enter at least one domain (e.g. acme.in, https://www.acme.co.in or name@acme.in)")
    if len(good) > limit:
        raise ValueError(f"At most {limit} domains at a time")
    return good, bad


# ---------------------------------------------------------------------------
# RDAP
# ---------------------------------------------------------------------------

_boot: Dict[str, Any] = {"at": 0.0, "map": {}}
_boot_lock = threading.Lock()


def _get_json(url: str, timeout: int = 15) -> Tuple[int, Any]:
    status, text, _ = hcm._guarded_get(url, RDAP_HEADERS, timeout, deep_search.public_url_guard, 1024 * 1024)
    try:
        return status, json.loads(text) if text.strip() else None
    except ValueError:
        return status, None


def rdap_base(tld: str) -> Optional[str]:
    with _boot_lock:
        if time.time() - _boot["at"] > 86400 or not _boot["map"]:
            status, data = _get_json(BOOTSTRAP_URL)
            if status == 200 and isinstance(data, dict):
                m = {}
                for tlds, urls in data.get("services", []):
                    https = [u for u in urls if u.startswith("https://")] or urls
                    for t in tlds:
                        m[t.lower()] = https[0] if https[0].endswith("/") else https[0] + "/"
                _boot.update(at=time.time(), map=m)
        return _boot["map"].get(tld.lower())


def _vcard_name(entity: Dict[str, Any]) -> str:
    try:
        for item in entity.get("vcardArray", [None, []])[1]:
            if item[0] == "fn":
                return str(item[3])[:120]
    except (IndexError, TypeError):
        pass
    return ""


def parse_rdap(data: Dict[str, Any]) -> Dict[str, Any]:
    events = {e.get("eventAction"): (e.get("eventDate") or "")[:10] for e in data.get("events", []) if isinstance(e, dict)}
    registrar = ""
    for ent in data.get("entities", []) or []:
        if isinstance(ent, dict) and "registrar" in (ent.get("roles") or []):
            registrar = _vcard_name(ent) or str(ent.get("handle") or "")
    ns = [str(n.get("ldhName", "")).lower().rstrip(".") for n in data.get("nameservers", []) or [] if isinstance(n, dict)]
    return {"registered": True, "created": events.get("registration", ""), "expires": events.get("expiration", ""),
            "updated": events.get("last changed", ""), "registrar": registrar, "nameservers": ns[:4],
            "status": [str(s) for s in data.get("status", [])][:6]}


def dns_exists(domain: str, resolver: Optional[dns.resolver.Resolver] = None) -> Optional[bool]:
    r = resolver or _resolver()
    try:
        r.resolve(domain, "NS")
        return True
    except dns.resolver.NXDOMAIN:
        return False
    except dns.resolver.NoAnswer:
        return True
    except (dns.resolver.NoNameservers, dns.exception.DNSException):
        return None


def rdap_lookup(domain: str) -> Dict[str, Any]:
    tld = domain.rsplit(".", 1)[-1]
    base = rdap_base(tld)
    if not base:
        exists = dns_exists(domain)
        return {"domain": domain, "source": "dns", "registered": exists,
                "note": "No RDAP service for this ending - checked DNS only (no dates)"}
    try:
        status, data = _get_json(f"{base}domain/{domain}")
    except (requests.RequestException, hcm.BlockedUrl) as e:
        return {"domain": domain, "source": "rdap", "registered": None, "note": f"Registry did not answer ({e.__class__.__name__})"}
    if status == 404:
        return {"domain": domain, "source": "rdap", "registered": False}
    if status == 429:
        return {"domain": domain, "source": "rdap", "registered": None, "note": "Registry rate limit - try again in a minute"}
    if status != 200 or not isinstance(data, dict):
        return {"domain": domain, "source": "rdap", "registered": None, "note": f"Registry answered HTTP {status}"}
    return {"domain": domain, "source": "rdap", **parse_rdap(data)}


def dns_host(nameservers: List[str]) -> str:
    for ns in nameservers:
        for pat, name in DNS_PROVIDERS:
            if re.search(pat, ns):
                return name
    return nameservers[0].split(".", 1)[-1] if nameservers else ""


def _age(created: str, today: datetime.date) -> Tuple[str, Optional[int]]:
    try:
        d = datetime.date.fromisoformat(created[:10])
    except ValueError:
        return "", None
    days = (today - d).days
    years, months = divmod(days // 30, 12)
    return (f"{years} yr {months} mo" if years else f"{months} mo" if months else f"{days} days"), days


def age_report(domains: Any, today: Optional[datetime.date] = None) -> Dict[str, Any]:
    good, bad = domain_list(domains)
    today = today or datetime.date.today()
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(rdap_lookup, good))
    for r in rows:
        flags = []
        if r.get("registered"):
            r["age"], age_days = _age(r.get("created", ""), today)
            try:
                left = (datetime.date.fromisoformat(r["expires"][:10]) - today).days if r.get("expires") else None
            except ValueError:
                left = None
            r["days_left"] = left
            r["dns_host"] = dns_host(r.get("nameservers", []))
            if age_days is not None and age_days < 365:
                flags.append("New (under 1 year)")
            if left is not None and left < 0:
                flags.append("Expired")
            elif left is not None and left <= 60:
                flags.append(f"Expires in {left} days")
            if any("hold" in s or "redemption" in s or "pending delete" in s for s in r.get("status", [])):
                flags.append("On hold / redemption")
        elif r.get("registered") is False:
            flags.append("Not registered")
        r["flags"] = flags
    return {"results": rows, "invalid": bad}


# ---------------------------------------------------------------------------
# Email & DNS
# ---------------------------------------------------------------------------

def _resolver() -> dns.resolver.Resolver:
    r = dns.resolver.Resolver()
    r.lifetime = bc.DNS_TIMEOUT
    return r


RETRY_PAUSE = 1.5


def _q(r: dns.resolver.Resolver, name: str, rtype: str, sleep=None) -> Tuple[str, List[Any]]:
    """-> ("ok" | "none" | "nxdomain" | "error", answers).
    One retry on a timeout, after a short pause: home routers often time out on the first query for a new name
    while they look it up, then answer the repeat from their cache."""
    for attempt in (1, 2):
        if attempt == 2:
            (sleep or time.sleep)(RETRY_PAUSE)
        try:
            return "ok", list(r.resolve(name, rtype))
        except dns.resolver.NXDOMAIN:
            return "nxdomain", []
        except dns.resolver.NoAnswer:
            return "none", []
        except dns.exception.Timeout:
            if attempt == 2:
                return "error", []
        except (dns.resolver.NoNameservers, dns.exception.DNSException):
            return "error", []
    return "error", []


def _txt(ans: List[Any]) -> List[str]:
    out = []
    for a in ans:
        try:
            out.append(b"".join(a.strings).decode("utf-8", "replace"))
        except AttributeError:
            out.append(str(a).strip('"'))
    return out


def mail_provider(mx_hosts: List[str]) -> str:
    for h in mx_hosts:
        for pat, name in MAIL_PROVIDERS:
            if re.search(pat, h):
                return name
    return "Own / other mail server" if mx_hosts else ""


def dns_check(domain: str, resolver: Optional[dns.resolver.Resolver] = None) -> Dict[str, Any]:
    r = resolver or _resolver()
    out: Dict[str, Any] = {"domain": domain, "status": "ok"}
    st, mx = _q(r, domain, "MX")
    if st == "nxdomain":
        return {"domain": domain, "status": "missing", "problems": ["The domain does not exist"], "pitches": []}
    if st == "error":
        return {"domain": domain, "status": "unknown", "problems": ["DNS did not answer - try again"], "pitches": []}
    hosts = [str(m.exchange).rstrip(".").lower() for m in sorted(mx, key=lambda m: m.preference)]
    hosts = [h for h in hosts if h not in ("", ".")]
    out["mx"] = hosts[:4]
    out["mail"] = mail_provider(hosts)
    spf = [t for t in _txt(_q(r, domain, "TXT")[1]) if t.lower().startswith("v=spf1")]
    out["spf"] = spf[0][:300] if spf else ""
    dmarc = [t for t in _txt(_q(r, f"_dmarc.{domain}", "TXT")[1]) if t.lower().startswith("v=dmarc1")]
    out["dmarc"] = dmarc[0][:300] if dmarc else ""
    pol = re.search(r"\bp=(\w+)", out["dmarc"], re.I)
    out["dmarc_policy"] = pol.group(1).lower() if pol else ""
    out["nameservers"] = [str(n).rstrip(".").lower() for n in _q(r, domain, "NS")[1]][:4]
    out["dns_host"] = dns_host(out["nameservers"])
    out["web_ip"] = [str(a) for a in _q(r, domain, "A")[1]][:3]
    problems, pitches = [], []
    if not hosts:
        problems.append("No MX record - the domain cannot receive e-mail")
        pitches.append("Business e-mail setup (Google Workspace / Zoho / Microsoft 365)")
    elif out["mail"] in HOSTING_MAIL:
        pitches.append("Move from hosting mail to Google Workspace / Zoho / Microsoft 365")
    if hosts and not out["spf"]:
        problems.append("No SPF record - mail is more likely to land in spam")
    elif out["spf"] and re.search(r"[+?]all\b", out["spf"]):
        problems.append("SPF ends with ?all / +all - it protects nothing")
    if hosts and not out["dmarc"]:
        problems.append("No DMARC record - anyone can send mail as this domain")
    elif out["dmarc_policy"] == "none":
        problems.append("DMARC policy is p=none (monitoring only)")
    if any(p.startswith(("No SPF", "SPF ends", "No DMARC", "DMARC policy")) for p in problems):
        pitches.append("E-mail deliverability & security (SPF / DKIM / DMARC)")
    if not out["web_ip"]:
        problems.append("No website address (A record)")
        pitches.append("Website development")
    out["problems"], out["pitches"] = problems, pitches
    return out


def dns_report(domains: Any) -> Dict[str, Any]:
    good, bad = domain_list(domains)
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(dns_check, good))
    return {"results": rows, "invalid": bad}


# ---------------------------------------------------------------------------
# New domains (WhoisDS daily list)
# ---------------------------------------------------------------------------

def _nrd_dir() -> str:
    return os.path.join(hcm.CACHE_DIR, "nrd")                # inside the (git-ignored) HTML cache folder


def _nrd_path(day: datetime.date) -> str:
    return os.path.join(_nrd_dir(), f"{day.isoformat()}.txt")


def _prune_nrd(today: datetime.date) -> None:
    if not os.path.isdir(_nrd_dir()):
        return
    for f in os.listdir(_nrd_dir()):
        try:
            if (today - datetime.date.fromisoformat(f[:10])).days > NRD_KEEP_DAYS:
                os.remove(os.path.join(_nrd_dir(), f))
        except (ValueError, OSError):
            continue


def nrd_day(day: datetime.date) -> Optional[List[str]]:
    """Domains registered on `day` (one download per day, kept on disk). None = not published / not allowed."""
    path = _nrd_path(day)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            return fh.read().split()
    url = NRD_URL.format(b64=base64.b64encode(f"{day.isoformat()}.zip".encode()).decode())
    if not robots_policy.allowed(url):
        return None
    try:
        deep_search.public_url_guard(url)
        r = requests.get(url, headers=deep_search.HEADERS, timeout=60, stream=True, allow_redirects=False)
        data = r.raw.read(20 * 1024 * 1024 + 1, decode_content=True) if r.status_code == 200 else b""
        r.close()
    except (requests.RequestException, hcm.BlockedUrl):
        return None
    if not data or len(data) > 20 * 1024 * 1024:
        return None
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
        name = zf.namelist()[0]
        if zf.getinfo(name).file_size > 50 * 1024 * 1024:
            return None
        text = zf.read(name).decode("utf-8", "replace")
    except (zipfile.BadZipFile, IndexError, KeyError):
        return None
    domains = [d.strip().lower() for d in text.split() if DOMAIN_RE.match(d.strip().lower())]
    os.makedirs(_nrd_dir(), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(domains))
    return domains


def new_domains(data: Dict[str, Any], today: Optional[datetime.date] = None) -> Dict[str, Any]:
    kws = data.get("keywords")
    if isinstance(kws, str):
        kws = kws.split(",")
    if not isinstance(kws, list):
        raise ValueError("Enter at least one keyword")
    kws = list(dict.fromkeys(re.sub(r"[^a-z0-9]", "", str(k).lower()) for k in kws if str(k).strip()))
    kws = [k for k in kws if k]
    if not kws:
        raise ValueError("Enter at least one keyword (letters / numbers)")
    if len(kws) > MAX_NEW_KEYWORDS:
        raise ValueError(f"At most {MAX_NEW_KEYWORDS} keywords")
    if any(len(k) < 3 for k in kws):
        raise ValueError("Each keyword needs at least 3 letters")
    days = data.get("days", 3)
    if days not in DAY_CHOICES:
        raise ValueError("Unknown number of days")
    tlds = data.get("tlds") or []
    if not isinstance(tlds, list) or any(t not in NEW_TLDS for t in tlds):
        raise ValueError("Unknown domain ending")
    today = today or datetime.date.today()
    _prune_nrd(today)
    rows, notes, read = [], [], []
    for back in range(1, days + 2):              # the newest list is usually yesterday's; one extra day as a buffer
        if len(read) >= days:
            break
        day = today - datetime.timedelta(days=back)
        listing = nrd_day(day)
        if listing is None:
            notes.append(f"List for {day.isoformat()} is not available")
            continue
        read.append(day.isoformat())
        for d in listing:
            tld = d.rsplit(".", 1)[-1]
            if tlds and tld not in tlds:
                continue
            flat = d.replace("-", "")
            hit = next((k for k in kws if k in flat), None)
            if hit:
                rows.append({"domain": d, "registered_on": day.isoformat(), "tld": tld, "keyword": hit,
                             "website": f"https://{d}"})
    seen, unique = set(), []
    for r in rows:
        if r["domain"] not in seen:
            seen.add(r["domain"])
            unique.append(r)
    if len(unique) > MAX_NEW_RESULTS:
        notes.append(f"Showing the first {MAX_NEW_RESULTS} of {len(unique)} matches - use a more specific keyword")
        unique = unique[:MAX_NEW_RESULTS]
    notes.append("Source: WhoisDS free daily list (gTLDs such as .com / .net / .org / .online / .store - no .in)")
    return {"results": unique, "days_read": read, "notes": notes}


# ---------------------------------------------------------------------------
# Availability
# ---------------------------------------------------------------------------

def name_variants(name: str, tlds: List[str], with_variants: bool) -> List[str]:
    base = re.sub(r"[^a-z0-9-]", "", name.lower().replace(" ", "")).strip("-")
    out = [f"{base}.{t}" for t in tlds]
    if with_variants:
        words = [w for w in re.split(r"\s+", name.lower().strip()) if w]
        alts = [f"get{base}", f"my{base}", f"{base}india", f"{base}online", f"{base}hq", f"the{base}"]
        if len(words) > 1:
            alts.insert(0, "-".join(re.sub(r"[^a-z0-9]", "", w) for w in words))
        for a in alts:
            for t in ("com", "in"):
                out.append(f"{a}.{t}")
    return [d for d in dict.fromkeys(out) if DOMAIN_RE.match(d)][:MAX_AVAIL_CHECKS]


def availability(data: Dict[str, Any]) -> Dict[str, Any]:
    name = " ".join(str(data.get("name") or "").split())
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 -]{1,40}", name):
        raise ValueError("Enter a name of 2-40 letters / numbers (spaces and - allowed)")
    tlds = data.get("tlds") or ["com", "in", "co.in"]
    if not isinstance(tlds, list) or any(t not in AVAIL_TLDS for t in tlds):
        raise ValueError("Unknown domain ending")
    candidates = name_variants(name, tlds, bool(data.get("variants", True)))
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(rdap_lookup, candidates))
    for r in rows:
        r["available"] = "available" if r.get("registered") is False else "taken" if r.get("registered") else "unknown"
        r["requested"] = r["domain"].split(".", 1)[0] == re.sub(r"[^a-z0-9-]", "", name.lower().replace(" ", ""))
    rows.sort(key=lambda r: (not r["requested"], {"available": 0, "unknown": 1, "taken": 2}[r["available"]]))
    return {"results": rows, "checked": len(rows),
            "notes": ["'Available' = the registry has no record now. Premium or reserved names can still be refused "
                      "or cost more - confirm at a registrar."]}

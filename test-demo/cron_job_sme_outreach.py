"""
SME post-pack outreach: e-mails the '2 free sample posts, then 10 posts for ₹500' offer to local businesses.

Who gets it (all must hold):
- the lead came from a local-business source (Google Maps, IndiaMART, TradeIndia, Justdial, Indian
  directories) - never job posts, freelance projects, HN / Reddit posts or e-commerce stores abroad;
- it is in the target region (Gujarat by default, --region india for all of India);
- it is not a software / IT company (settings_manager.is_it_company, also on the Maps search words);
- it has an e-mail address that has never been mailed (send_smtp_email also keeps one mail per company,
  the Do-Not-Contact list and mailbox checks).

At most --limit mails a day in total (default 15), however often it runs.

Each run first FINDS new businesses (Sulekha + OpenStreetMap / Google Places listings for today's
niches and Gujarat city, then their website and e-mail) and saves them as leads, then MAILS.

Usage:
  python cron_job_sme_outreach.py --dry-run     # find + save leads, list who would get a mail, send nothing
  python cron_job_sme_outreach.py --dry-run --no-find   # only list, no searching
  python cron_job_sme_outreach.py               # send (max 15 today)
  python cron_job_sme_outreach.py --limit 5 --city Surat --niche gym --niche salon
"""

import argparse
import csv
import datetime
import json
import os
import re
import sys
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import email_service
import festival_offers_engine as offers_engine
import settings_manager

LEADS_MASTER = os.path.join(BASE_DIR, "all_leads_master.csv")
DAY_LOG = os.path.join(BASE_DIR, "logs", "sme_outreach_daily.json")  # {date: count}; not committed

LOCAL_SOURCES = re.compile(r"google maps|indiamart|tradeindia|justdial|sulekha|indian directories|directory", re.I)
NOT_LOCAL_TYPES = {"job posting", "freelance project", "developer requirement", "hn hiring post", "client hiring"}
REGIONS = {
    "gujarat": re.compile(r"\b(?:gujarat|ahmedabad|amdavad|surat|vadodara|baroda|rajkot|gandhinagar|bhavnagar|"
                          r"jamnagar|nadiad|mehsana|morbi|bharuch|vapi|navsari|junagadh)\b", re.I),
    "india": re.compile(r"\b(?:india|gujarat|maharashtra|mumbai|pune|delhi|bengaluru|bangalore|hyderabad|chennai|"
                        r"kolkata|jaipur|indore|lucknow|chandigarh|ahmedabad|surat|vadodara|rajkot)\b", re.I),
}


def _s(v):
    s = str(v if v is not None else "").strip()
    return "" if s.lower() in ("nan", "none", "n/a", "null") else s


# ---------------------------------------------------------------------------
# Step 1: find new local businesses and their e-mail
# ---------------------------------------------------------------------------

# Businesses that post a lot and can pay (see docs/SME_500_OFFER_PLAYBOOK.md). Two a day, in turn.
# In pairs: the first of each pair has listings on Sulekha, the second on IndiaMART or the maps sources
# (checked 20 Nov 2026), so each day has at least one source that answers.
NICHES = [
    "dentist", "furniture", "gym", "sweets", "restaurant", "jewellers", "real estate agent", "bakery",
    "physiotherapist", "salon", "sweet shop", "boutique", "yoga classes", "beauty parlour",
    "packers and movers", "cafe", "wedding planners", "optician",
]
CITIES = ["Ahmedabad", "Surat", "Vadodara", "Rajkot", "Gandhinagar"]
NICHES_PER_RUN = 2
MAX_LOOKUPS = 40   # website + e-mail look-ups per run (about 5 s each)


def todays_search(day=None):
    """(city, niches) for the day: the niches move on every day, the city after all niches had a turn."""
    n = (day or datetime.date.today()).toordinal()
    rounds = len(NICHES) // NICHES_PER_RUN
    start = (n % rounds) * NICHES_PER_RUN
    return CITIES[(n // rounds) % len(CITIES)], NICHES[start:start + NICHES_PER_RUN]


def _norm(name):
    return re.sub(r"[^a-z0-9]", "", str(name or "").lower())


# Words that say what a business is, not which one: they cannot identify its website on their own.
GENERIC_WORDS = {
    "the", "and", "dr", "co", "pvt", "ltd", "llp", "private", "limited", "company", "india", "indian", "national",
    "universal", "global", "new", "shree", "shri", "sri", "dental", "dentist", "clinic", "clinics", "care", "hospital",
    "health", "centre", "center", "gym", "fitness", "beauty", "parlour", "parlor", "salon", "spa", "studio", "shop",
    "store", "jewellers", "jewellery", "jewelers", "bakery", "cafe", "restaurant", "sweets", "classes", "coaching",
    "academy", "institute", "realty", "real", "estate", "properties", "furniture", "boutique", "designer", "designs",
    "interior", "interiors", "optician", "opticals", "yoga", "events", "caterers", "skin", "hair", "multispeciality",
    "ahmedabad", "surat", "vadodara", "baroda", "rajkot", "gandhinagar", "gujarat", "poly", "plus", "well",
}
NOT_A_BUSINESS_SITE = re.compile(r"(\.gov|\.nic|\.edu|\.ac)(\.|$)|thehindu|timesofindia|wikipedia|practo|justdial|"
                                 r"sulekha|indiamart|facebook|instagram|linkedin|youtube", re.I)
_SUFFIXES = {"com", "in", "co", "org", "net", "info", "biz", "online", "site", "store", "shop", "clinic", "health", "io"}


def _site_label(url_or_host):
    """'https://www.akashdental.co.in/x' -> 'akashdental' (the registered name, not a sub-domain)."""
    host = settings_manager._host_of(url_or_host)
    labels = [l for l in host.split(".") if l]
    while len(labels) > 1 and labels[-1] in _SUFFIXES:
        labels.pop()
    return re.sub(r"[^a-z0-9]", "", labels[-1]) if labels else ""


def site_belongs_to(company, website):
    """True when the website's name is (mostly) the business name: 'akashdentalclinic' for Akash Dental
    Poly Clinic, but not 'shreysports' for Shrey Aesthetica Dental or 'nationalinsurance' for National
    Dental Supply Co. A search engine often returns a different business with one word in common."""
    if not website or NOT_A_BUSINESS_SITE.search(settings_manager._host_of(website)):
        return False
    label = _site_label(website)
    words = [w for w in re.findall(r"[a-z0-9]+", str(company or "").lower()) if len(w) >= 2]
    distinctive = [w for w in words if w not in GENERIC_WORDS and len(w) >= 3]
    if not label or not distinctive or not any(w in label for w in distinctive):
        return False
    rest = label
    for w in sorted(set(words), key=len, reverse=True):
        rest = rest.replace(w, "", 1)
    return (len(label) - len(rest)) / len(label) >= 0.7


def email_belongs_to(email, website):
    """An e-mail found on the business's own site counts when it is on that domain or a free mailbox
    (many shops use Gmail) - not another company's domain, e.g. the web designer's in the footer."""
    if not (email and website and "@" in email):
        return False
    domain = email.split("@")[-1].lower()
    return domain in email_service.FREE_MAIL or _site_label(domain) == _site_label(website)


def _known_companies():
    if not os.path.exists(LEADS_MASTER):
        return set()
    with open(LEADS_MASTER, encoding="utf-8-sig", errors="ignore", newline="") as f:
        return {_norm(r.get("company_name")) for r in csv.DictReader(f)}


def _search_listings(city, niches):
    """Business listings from Sulekha, OpenStreetMap and (with a key) Google Places. A source that is
    down is reported and skipped. Returns [(raw_lead, category)]."""
    import indian_directories
    import maps_sources
    found, notes = [], []
    # Directories that answer automated requests (Justdial does not). None shows e-mails; IndiaMART shows
    # phones (its call-forwarding numbers), Sulekha mostly names. E-mails come from the business's own site.
    for sid in ("sulekha", "indiamart", "tradeindia", "exportersindia"):
        name = indian_directories.SOURCES[sid]["name"]
        try:
            res = indian_directories.search({"keywords": niches, "state": "Gujarat", "city": city, "sources": [sid]})
            found += [(indian_directories.result_to_raw_lead(r), r.get("category") or "") for r in res["results"]]
            notes.append(f"{name} {len(res['results'])}")
        except Exception as e:  # noqa: BLE001 - one source failing must not stop the run
            notes.append(f"{name} failed: {str(e)[:60]}")
    map_sources = ["osm"] + (["google_places"] if maps_sources.source_status("google_places") == "available" else [])
    try:
        res = maps_sources.search({"keywords": niches, "state": "Gujarat", "city": city, "sources": map_sources})
        found += [(maps_sources.result_to_raw_lead(r), r.get("category") or "") for r in res["results"]]
        for s in res["sources"].values():
            notes.append(f"{s['name']} {s['count']}" + (f" ({s['errors'][0][:60]})" if s["errors"] and not s["count"] else ""))
    except Exception as e:  # noqa: BLE001
        notes.append(f"Maps failed: {str(e)[:80]}")
    print(f"[*] Listings: {', '.join(notes)}")
    return found


def find_new_smes(city, niches, max_lookups=None, save=True):
    """Search listings, look up website + e-mail for businesses we do not have yet, save them as leads.
    Returns a summary dict."""
    import deep_search
    import search_engine
    from lead_normalizer import MasterLeadRegistry
    try:
        import run_all_scrapers
        if run_all_scrapers.run_lock_active():
            print("[*] A scraper run is writing the leads file now - finding skipped this time.")
            return {"listings": 0, "new": 0, "with_email": 0, "saved": 0, "status": "SCRAPER_RUNNING"}
    except Exception:  # noqa: BLE001 - the lock check is a courtesy
        pass

    print(f"[*] Finding: {', '.join(niches)} in {city}")
    known = _known_companies()
    new, seen = [], set()
    for raw, category in _search_listings(city, niches):
        key = _norm(raw.get("company_name"))
        if not key or key in known or key in seen:
            continue
        seen.add(key)
        if settings_manager.is_it_company(raw.get("company_name"), raw.get("email"), raw.get("website"), category)[0]:
            continue
        new.append(raw)

    max_lookups = MAX_LOOKUPS if max_lookups is None else max_lookups
    engine = search_engine.resolve_engine("auto")
    looked = with_email = wrong_site = 0
    for raw in new:
        if raw.get("email"):
            with_email += 1
            continue
        if looked >= max_lookups:
            break
        looked += 1
        try:
            out = deep_search.enrich({"company": raw["company_name"], "website": raw.get("website", "")}, engine, False, city)
        except Exception:  # noqa: BLE001 - one bad site must not stop the run
            continue
        site = raw.get("website") or out.get("website") or ""
        if not site_belongs_to(raw["company_name"], site):
            wrong_site += bool(site)
            continue        # another business's site: its phone and e-mail are not this lead's
        raw["website"] = site
        if out.get("phones") and not raw.get("mobile_number"):
            raw["mobile_number"] = out["phones"][0]
        own = [e for e in out.get("emails") or [] if email_belongs_to(e, site)]
        if own:
            raw["email"] = own[0]
            with_email += 1
    print(f"[+] {len(new)} new businesses, {looked} looked up, {wrong_site} wrong websites ignored, "
          f"{with_email} with their own e-mail")

    # A name and an area alone cannot be contacted: keep only leads with a phone, e-mail or own website.
    reachable = [r for r in new if r.get("email") or r.get("mobile_number") or r.get("website")]
    saved = 0
    if save and reachable:
        registry = MasterLeadRegistry(LEADS_MASTER)
        for raw in reachable:
            outcome, _ = registry.add_lead(raw, default_source="SME finder")
            saved += outcome == "added"
        if not registry.save_master_safely():
            print("[ERROR] Could not write the leads file; nothing saved.")
            saved = 0
    return {"listings": len(seen), "new": len(new), "with_email": with_email, "saved": saved, "status": "OK"}


def _first_email(value):
    for part in re.split(r"[,;\s]+", _s(value)):
        if "@" in part and "." in part.split("@")[-1]:
            return part.strip().lower()
    return ""


def candidate_sme_leads(region="gujarat"):
    """Local SME leads that may get the offer, in file order. Returns (candidates, skipped_counts)."""
    sent = {e.lower() for e in email_service.get_already_sent_emails()}
    region_rx = REGIONS.get(region, REGIONS["gujarat"])
    skipped = {"not_local_source": 0, "other_region": 0, "it_company": 0, "no_email": 0, "already_mailed": 0}
    out, seen = [], set()
    if not os.path.exists(LEADS_MASTER):
        return out, skipped
    with open(LEADS_MASTER, encoding="utf-8-sig", errors="ignore", newline="") as f:
        for r in csv.DictReader(f):
            source = _s(r.get("source"))
            if not LOCAL_SOURCES.search(source) or _s(r.get("lead_type")).lower() in NOT_LOCAL_TYPES:
                skipped["not_local_source"] += 1
                continue
            if not region_rx.search(f"{_s(r.get('location'))} {source}"):
                skipped["other_region"] += 1
                continue
            company = _s(r.get("company_name"))
            email = _first_email(r.get("email"))
            website = _s(r.get("website"))
            # The Maps search words count too: 'Software Development Company in Vadodara'.
            is_it, _ = settings_manager.is_it_company(company, email, website, category=source)
            if is_it:
                skipped["it_company"] += 1
                continue
            if not email:
                skipped["no_email"] += 1
                continue
            if email in sent or email in seen:
                skipped["already_mailed"] += 1
                continue
            seen.add(email)
            out.append({"company_name": company, "email": email, "phone": _s(r.get("mobile_number")),
                        "contact_name": _s(r.get("full_name")), "website": website, "source": source})
    return out, skipped


def _sent_today():
    try:
        with open(DAY_LOG, encoding="utf-8") as f:
            return int(json.load(f).get(datetime.date.today().isoformat(), 0))
    except (OSError, ValueError, AttributeError):
        return 0


def _add_sent_today(n):
    try:
        with open(DAY_LOG, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        data = {}
    today = datetime.date.today().isoformat()
    data = {today: int(data.get(today, 0)) + n}  # keep only today
    os.makedirs(os.path.dirname(DAY_LOG), exist_ok=True)
    with open(DAY_LOG, "w", encoding="utf-8") as f:
        json.dump(data, f)


def run_sme_automated_dispatch(limit: int = 15, dry_run: bool = False, region: str = "gujarat",
                               find: bool = False, city: str = "", niches=None):
    print("=" * 70)
    print(f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] SME post-pack outreach | region={region} | "
          f"daily limit={limit} | {'DRY RUN (no mail is sent)' if dry_run else 'LIVE'}")
    print("=" * 70)

    found = None
    if find:
        day_city, day_niches = todays_search()
        found = find_new_smes(city or day_city, niches or day_niches)

    candidates, skipped = candidate_sme_leads(region)
    print(f"[+] {len(candidates)} local SME leads can get the offer. Not eligible: {skipped}")
    left = max(0, limit - (0 if dry_run else _sent_today()))
    if not candidates:
        print("[*] No local SME leads with an e-mail. Find more with Google Maps (Gujarat SME presets);")
        print("    leads with only a phone go through the WhatsApp desk.")
        return {"dispatched": 0, "failed": 0, "eligible": 0, "skipped": skipped, "found": found, "status": "NO_LEADS"}
    if left == 0:
        print(f"[*] Today's limit of {limit} is already used. Next run tomorrow.")
        return {"dispatched": 0, "failed": 0, "eligible": len(candidates), "skipped": skipped, "found": found, "status": "LIMIT_REACHED"}

    dispatched = failed = 0
    for lead in candidates:
        if dispatched >= left:
            break
        name = lead["company_name"] or "your business"
        pitch = offers_engine.generate_offer_pitch(lead)
        if dry_run:
            print(f"       [DRY RUN] {name} | {lead['source'][:60]}")
            dispatched += 1
            continue
        res = email_service.send_smtp_email(
            to_email=lead["email"], subject=pitch["email_subject"], message_body=pitch["email_body"],
            company_name=lead["company_name"], website=lead["website"], verify="strict",
        )
        if res.get("success"):
            print(f"       [SENT] {name}")
            dispatched += 1
            _add_sent_today(1)
            time.sleep(1.5)
        else:
            why = "blocked (same company / do-not-contact)" if res.get("blocked") else res.get("error")
            print(f"       [NOT SENT] {name}: {why}")
            failed += 1

    print(f"[*] Done. {'Would send' if dry_run else 'Sent'}: {dispatched} | not sent: {failed}")
    return {"dispatched": dispatched, "failed": failed, "eligible": len(candidates), "skipped": skipped,
            "found": found, "status": "DRY_RUN" if dry_run else "COMPLETED"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="E-mail the ₹500 post-pack offer to local SMEs")
    parser.add_argument("--limit", type=int, default=15, help="most mails per day (default 15)")
    parser.add_argument("--dry-run", action="store_true", help="only list who would get a mail")
    parser.add_argument("--region", choices=sorted(REGIONS), default="gujarat")
    parser.add_argument("--no-find", action="store_true", help="skip finding new businesses; only mail")
    parser.add_argument("--city", default="", help="city to search (default: today's turn)")
    parser.add_argument("--niche", action="append", help="business type to search, e.g. --niche dentist (repeatable)")
    args = parser.parse_args()
    run_sme_automated_dispatch(limit=args.limit, dry_run=args.dry_run, region=args.region,
                               find=not args.no_find, city=args.city, niches=args.niche)

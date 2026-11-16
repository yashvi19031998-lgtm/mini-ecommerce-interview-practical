"""Reports > Daily Leads & Mail: per day - leads found that day, how many got an e-mail, how many are pending,
have no e-mail or are blocked - with the report's period / source / stage filters and a score band.
Read-only; uses the date / filter helpers of reports_engine."""
import datetime
from typing import Any, Dict, List, Optional, Set

from reports_engine import DATE_FORMAT, _parse_ts, get_lead_date, lead_matches, parse_and_validate_filters

SCORE_BANDS = {"high": (7, 10), "medium": (4, 6), "low": (0, 3)}
BAND_IDS = ("all", "high", "medium", "low", "unscored")
MAIL_STATES = ("mailed", "pending", "no_email", "blocked")
NOT_MAILABLE = {"INVALID", "INVALID_DOMAIN", "UNVERIFIABLE", "EXCLUDED_COMPANY", "BOUNCED", "OPTED_OUT"}
MAX_FILLED_DAYS = 92  # longer ranges list only the days that have leads


def lead_score(lead: Dict[str, Any]) -> Optional[int]:
    """AI score 0-10 (falls back to the scraper's intent score); None when never scored."""
    for key in ("ai_score", "intent_score"):
        try:
            return max(0, min(10, int(round(float(str(lead.get(key, "")).strip())))))
        except ValueError:
            continue
    return None


def score_band(score: Optional[int]) -> str:
    if score is None:
        return "unscored"
    return next(b for b, (lo, hi) in SCORE_BANDS.items() if lo <= score <= hi)


def _first_email(lead: Dict[str, Any]) -> str:
    e = str(lead.get("email") or lead.get("Email") or "").split(",")[0].strip().lower()
    return e if "@" in e and e not in ("n/a", "nan") else ""


def mail_state(lead: Dict[str, Any], sent_emails: Set[str]) -> str:
    """mailed (an e-mail went out), pending (has an e-mail, not sent yet), no_email, or blocked
    (the address is invalid / unverifiable / on the do-not-contact list)."""
    email = _first_email(lead)
    em_stat = str(lead.get("email_status") or lead.get("Email Status") or "").strip().upper()
    if em_stat == "SENT" or (email and email in sent_emails):
        return "mailed"
    if not email:
        return "no_email"
    if em_stat in NOT_MAILABLE:
        return "blocked"
    return "pending"


def _empty_day(day: str) -> Dict[str, Any]:
    return {"day": day, "found": 0, **{s: 0 for s in MAIL_STATES},
            **{b: 0 for b in BAND_IDS if b != "all"}, "mails_sent_that_day": 0}


def _scope(leads, sent, filters, band, now):
    band = str(band or "all").strip().lower()
    if band not in BAND_IDS:
        raise ValueError(f"Unknown score band '{band}'. Allowed: {', '.join(BAND_IDS)}.")
    start_dt, end_dt, source_f, status_f, d_from, d_to = parse_and_validate_filters(filters, now=now)
    sent_emails = {s["email"] for s in sent if s.get("email")}
    picked = []
    for lead in leads:
        if not lead_matches(lead, start_dt, end_dt, source_f, status_f):
            continue
        b = score_band(lead_score(lead))
        if band != "all" and b != band:
            continue
        picked.append((lead, b))
    return picked, sent_emails, start_dt, end_dt, d_from, d_to, band


def daily_leads(leads: List[Dict[str, Any]], sent: List[Dict[str, str]], filters: Optional[Dict[str, Any]] = None,
                band: str = "all", now: Optional[datetime.datetime] = None) -> Dict[str, Any]:
    """One row per day (newest first). A lead counts on the day it was found (first_seen_at).
    mails_sent_that_day counts every e-mail the app sent that day, whatever day the lead was found."""
    picked, sent_emails, start_dt, end_dt, d_from, d_to, band = _scope(leads, sent, filters, band, now)
    days: Dict[str, Dict[str, Any]] = {}
    if (end_dt.date() - start_dt.date()).days < MAX_FILLED_DAYS:
        d = start_dt.date()
        while d <= end_dt.date():
            days[d.strftime(DATE_FORMAT)] = _empty_day(d.strftime(DATE_FORMAT))
            d += datetime.timedelta(days=1)
    for lead, b in picked:
        day = get_lead_date(lead).strftime(DATE_FORMAT)
        row = days.setdefault(day, _empty_day(day))
        row["found"] += 1
        row[b] += 1
        row[mail_state(lead, sent_emails)] += 1
    for s in sent:
        dt = _parse_ts(s.get("sent_at"))
        if dt and start_dt <= dt <= end_dt:
            day = dt.strftime(DATE_FORMAT)
            days.setdefault(day, _empty_day(day))["mails_sent_that_day"] += 1
    rows = sorted(days.values(), key=lambda r: r["day"], reverse=True)
    totals = _empty_day("total")
    for r in rows:
        for k in totals:
            if k != "day":
                totals[k] += r[k]
    return {"rows": rows, "totals": totals, "band": band, "filters_applied": {"date_from": d_from, "date_to": d_to}}


def daily_leads_list(leads: List[Dict[str, Any]], sent: List[Dict[str, str]], day: str, state: str = "found",
                     filters: Optional[Dict[str, Any]] = None, band: str = "all", limit: int = 500,
                     now: Optional[datetime.datetime] = None) -> Dict[str, Any]:
    """The leads behind one number of the daily table (day + found / mailed / pending / no_email / blocked)."""
    try:
        datetime.datetime.strptime(str(day), DATE_FORMAT)
    except ValueError:
        raise ValueError(f"Invalid day '{day}'. Format must be YYYY-MM-DD.")
    state = str(state or "found").strip().lower()
    if state not in ("found",) + MAIL_STATES:
        raise ValueError(f"Unknown state '{state}'. Allowed: found, {', '.join(MAIL_STATES)}.")
    filters = {**(filters or {}), "preset": "", "date_from": day, "date_to": day}
    picked, sent_emails, *_rest, band = _scope(leads, sent, filters, band, now)
    items = []
    for lead, b in picked:
        st = mail_state(lead, sent_emails)
        if state != "found" and st != state:
            continue
        items.append({
            "id": str(lead.get("id") or lead.get("lead_id") or ""),
            "name": str(lead.get("company_name") or lead.get("Company Name") or lead.get("full_name") or "")[:160],
            "email": _first_email(lead),
            "score": lead_score(lead), "band": b, "mail": st,
            "source": str(lead.get("source") or lead.get("Source") or "")[:80],
            "found_at": str(lead.get("first_seen_at") or "")[:16],
            "sent_at": str(lead.get("email_sent_at") or "")[:16],
        })
    items.sort(key=lambda i: i["score"] if i["score"] is not None else -1, reverse=True)
    return {"items": items[:limit], "total": len(items), "day": day, "state": state, "band": band}

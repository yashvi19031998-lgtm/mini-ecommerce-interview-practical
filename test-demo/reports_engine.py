"""
Reports Engine for LeadsGen AI
==============================
Pure reporting and analytics logic (read-only, no Flask, no disk side-effects).
Processes leads, scraper runs, outreach, follow-ups, pipeline stages, and data health.
"""

import csv
import datetime
import functools
import os
import re
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple, Set

import followup_sequence
import followup_store
import lead_quality
import settings_manager
import source_report

TS_FORMAT = "%Y-%m-%d %H:%M:%S"
DATE_FORMAT = "%Y-%m-%d"

ALL_STAGES = [
    "NEW",
    "CONTACTED",
    "EMAIL_SENT",
    "REPLIED",
    "MEETING",
    "WON",
    "LOST",
    "DISQUALIFIED",
]

PRESETS = [
    {"id": "today", "label": "Today"},
    {"id": "yesterday", "label": "Yesterday"},
    {"id": "7d", "label": "Last 7 days"},
    {"id": "30d", "label": "Last 30 days"},
    {"id": "this_month", "label": "This month"},
    {"id": "last_month", "label": "Last month"},
    {"id": "all", "label": "All time"},
]


# ---------------------------------------------------------------------------
# File loading helpers (read-only, return [] if file missing or unreadable)
# ---------------------------------------------------------------------------

def load_runs(path: str) -> List[Dict[str, str]]:
    """Reads scraper runs from CSV safely using csv.DictReader."""
    if not path or not os.path.exists(path):
        return []
    runs = []
    try:
        with open(path, "r", encoding="utf-8-sig", newline="", errors="replace") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if not row or not row.get("run_id"):
                    continue
                runs.append({k: (v or "").strip() for k, v in row.items()})
    except Exception:
        return []
    return runs


def load_sent(path: str) -> List[Dict[str, str]]:
    """Reads sent emails from CSV."""
    if not path or not os.path.exists(path):
        return []
    sent = []
    try:
        with open(path, "r", encoding="utf-8-sig", newline="", errors="replace") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if not row or not row.get("email"):
                    continue
                sent.append({
                    "email": (row.get("email") or "").strip().lower(),
                    "sent_at": (row.get("sent_at") or "").strip(),
                    "subject": (row.get("subject") or "").strip(),
                })
    except Exception:
        return []
    return sent


def load_activities(path: str) -> List[Dict[str, str]]:
    """Reads followup activity log."""
    if not path or not os.path.exists(path):
        return []
    try:
        return followup_store._read_all(path)
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Date and Filter Helpers
# ---------------------------------------------------------------------------

def _parse_ts(val: Any) -> Optional[datetime.datetime]:
    if not val:
        return None
    return _parse_ts_text(str(val))


@functools.lru_cache(maxsize=65536)
def _parse_ts_text(text: str) -> Optional[datetime.datetime]:
    """Cached: the logs repeat the same timestamps many times, and strptime is slow."""
    s = text.strip()
    # Fast path for the usual 'YYYY-MM-DD HH:MM:SS' / 'YYYY-MM-DD' / ISO forms
    if len(s) >= 10 and s[4:5] == "-" and s[7:8] == "-":
        try:
            dt = datetime.datetime.fromisoformat(s[:19].replace("T", " "))
            return dt.replace(tzinfo=None)
        except ValueError:
            pass
    if not s or s.lower() in ("none", "null", "n/a"):
        return None
    # ISO T format or standard space
    s = s.replace("T", " ")
    if len(s) > 19:
        s = s[:19]
    for fmt in (TS_FORMAT, DATE_FORMAT, "%Y/%m/%d %H:%M:%S", "%Y/%m/%d", "%d-%m-%Y %H:%M:%S", "%d/%m/%Y"):
        try:
            return datetime.datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def get_preset_range(preset: str, now: Optional[datetime.datetime] = None) -> Tuple[str, str]:
    now = now or datetime.datetime.now().replace(microsecond=0)
    today = now.date()

    if preset == "today":
        return today.strftime(DATE_FORMAT), today.strftime(DATE_FORMAT)
    elif preset == "yesterday":
        yest = today - datetime.timedelta(days=1)
        return yest.strftime(DATE_FORMAT), yest.strftime(DATE_FORMAT)
    elif preset in ("7d", "last_7_days"):
        start = today - datetime.timedelta(days=6)
        return start.strftime(DATE_FORMAT), today.strftime(DATE_FORMAT)
    elif preset in ("30d", "last_30_days"):
        start = today - datetime.timedelta(days=29)
        return start.strftime(DATE_FORMAT), today.strftime(DATE_FORMAT)
    elif preset in ("this_month", "month"):
        start = today.replace(day=1)
        return start.strftime(DATE_FORMAT), today.strftime(DATE_FORMAT)
    elif preset == "last_month":
        first_this = today.replace(day=1)
        last_prev = first_this - datetime.timedelta(days=1)
        first_prev = last_prev.replace(day=1)
        return first_prev.strftime(DATE_FORMAT), last_prev.strftime(DATE_FORMAT)
    elif preset in ("all", "all_time"):
        return "2020-01-01", today.strftime(DATE_FORMAT)
    else:
        raise ValueError(f"Unknown preset: '{preset}'. Choose from: today, yesterday, 7d, 30d, this_month, last_month, all")


def parse_and_validate_filters(
    filters: Optional[Dict[str, Any]],
    valid_sources: Optional[Set[str]] = None,
    now: Optional[datetime.datetime] = None
) -> Tuple[datetime.datetime, datetime.datetime, str, str, str, str]:
    """
    Validates query filters.
    Returns: (start_dt, end_dt, source_filter, status_filter, date_from_str, date_to_str)
    """
    now = now or datetime.datetime.now().replace(microsecond=0)
    filters = filters or {}

    preset = str(filters.get("preset") or "").strip().lower()
    date_from_str = str(filters.get("date_from") or "").strip()
    date_to_str = str(filters.get("date_to") or "").strip()

    if preset:
        date_from_str, date_to_str = get_preset_range(preset, now)
    elif not date_from_str and not date_to_str:
        # Default: last 30 days
        date_from_str, date_to_str = get_preset_range("30d", now)
    elif not date_from_str or not date_to_str:
        raise ValueError("Both date_from and date_to must be provided when not using a preset.")

    try:
        d_from = datetime.datetime.strptime(date_from_str, DATE_FORMAT)
    except ValueError:
        raise ValueError(f"Invalid date_from '{date_from_str}'. Format must be YYYY-MM-DD.")

    try:
        d_to = datetime.datetime.strptime(date_to_str, DATE_FORMAT)
    except ValueError:
        raise ValueError(f"Invalid date_to '{date_to_str}'. Format must be YYYY-MM-DD.")

    if d_from > d_to:
        raise ValueError(f"Start date ({date_from_str}) cannot be after end date ({date_to_str}).")

    # The 3-year cap is for hand-typed ranges; the "All time" preset is allowed to be longer.
    if preset not in ("all", "all_time") and (d_to - d_from).days > (3 * 366):
        raise ValueError("Date range cannot exceed 3 years.")

    start_dt = d_from.replace(hour=0, minute=0, second=0, microsecond=0)
    end_dt = d_to.replace(hour=23, minute=59, second=59, microsecond=999999)

    source_filter = str(filters.get("source") or "all").strip()
    if source_filter.lower() != "all" and valid_sources is not None:
        if source_filter not in valid_sources and source_filter.lower() not in {s.lower() for s in valid_sources}:
            raise ValueError(f"Unknown source '{source_filter}'.")

    status_filter = str(filters.get("status") or "all").strip().upper()
    if status_filter != "ALL" and status_filter not in ALL_STAGES:
        raise ValueError(f"Unknown status '{status_filter}'. Allowed: ALL, {', '.join(ALL_STAGES)}.")

    return start_dt, end_dt, source_filter, status_filter, date_from_str, date_to_str


def get_lead_date(lead: Dict[str, Any]) -> Optional[datetime.datetime]:
    """Resolution priority: first_seen_at -> posted_at -> last_updated_at -> None."""
    for field in ("first_seen_at", "First Seen At", "posted_at", "Posted At", "last_updated_at", "Last Updated At"):
        val = lead.get(field)
        dt = _parse_ts(val)
        if dt:
            return dt
    return None


def lead_matches(
    lead: Dict[str, Any],
    start_dt: Optional[datetime.datetime],
    end_dt: Optional[datetime.datetime],
    source_filter: str = "all",
    status_filter: str = "all",
    apply_date: bool = True
) -> bool:
    if source_filter and source_filter.lower() != "all":
        fam = source_report.source_family(lead)
        if fam.lower() != source_filter.lower():
            return False

    if status_filter and status_filter.upper() != "ALL":
        st = str(lead.get("Status") or lead.get("status") or "NEW").strip().upper()
        if st != status_filter.upper():
            return False

    if apply_date and start_dt and end_dt:
        ldt = get_lead_date(lead)
        if not ldt or not (start_dt <= ldt <= end_dt):
            return False

    return True


# ---------------------------------------------------------------------------
# R1: Summary Report
# ---------------------------------------------------------------------------

def summary(
    leads: List[Dict[str, Any]],
    runs: List[Dict[str, Any]],
    activities: List[Dict[str, Any]],
    sent: List[Dict[str, Any]],
    filters: Optional[Dict[str, Any]] = None,
    now: Optional[datetime.datetime] = None
) -> Dict[str, Any]:
    now = now or datetime.datetime.now().replace(microsecond=0)
    valid_sources = {source_report.source_family(l) for l in leads}
    start_dt, end_dt, src_f, stat_f, d_from_str, d_to_str = parse_and_validate_filters(filters, valid_sources, now)

    period_days = (end_dt.date() - start_dt.date()).days + 1
    prev_end_dt = (start_dt - datetime.timedelta(seconds=1))
    prev_start_dt = (prev_end_dt - datetime.timedelta(days=period_days) + datetime.timedelta(seconds=1))
    is_all_time = (filters or {}).get("preset") == "all" or d_from_str <= "2020-01-01"

    # Pre-index emails sent in periods
    sent_cur = 0
    sent_prev = 0
    for s in sent:
        dt = _parse_ts(s.get("sent_at"))
        if dt:
            if start_dt <= dt <= end_dt:
                sent_cur += 1
            elif not is_all_time and prev_start_dt <= dt <= prev_end_dt:
                sent_prev += 1

    sent_times = {s.get("sent_at") for s in sent}
    for a in activities:
        if a.get("type") in ("email_sent", "email"):
            dt = _parse_ts(a.get("occurred_at"))
            if dt:
                # Avoid double counting if already in sent_emails.csv with same timestamp
                already_logged = a.get("occurred_at") in sent_times
                if start_dt <= dt <= end_dt and not already_logged:
                    sent_cur += 1
                elif not is_all_time and prev_start_dt <= dt <= prev_end_dt and not already_logged:
                    sent_prev += 1

    # Runs in periods
    runs_cur = 0
    runs_prev = 0
    failed_cur = 0
    failed_prev = 0
    seen_run_cur = set()
    seen_run_prev = set()

    for r in runs:
        dt = _parse_ts(r.get("start_time"))
        st = (r.get("status") or "").lower()
        rid = r.get("run_id") or ""
        if dt:
            if start_dt <= dt <= end_dt:
                if rid:
                    seen_run_cur.add(rid)
                runs_cur += 1
                if st == "failed":
                    failed_cur += 1
            elif not is_all_time and prev_start_dt <= dt <= prev_end_dt:
                if rid:
                    seen_run_prev.add(rid)
                runs_prev += 1
                if st == "failed":
                    failed_prev += 1

    # Total leads all time (respecting source/status if chosen)
    total_leads_all_time = sum(1 for l in leads if lead_matches(l, None, None, src_f, stat_f, apply_date=False))

    # Leads in cur and prev period
    new_cur = 0
    new_prev = 0
    hot_cur = 0
    hot_prev = 0
    contacted_cur = 0
    contacted_prev = 0
    replied_cur = 0
    replied_prev = 0
    meetings_cur = 0
    meetings_prev = 0
    won_cur = 0
    won_prev = 0
    lost_cur = 0
    lost_prev = 0

    daily_map = {
        (start_dt.date() + datetime.timedelta(days=i)).strftime(DATE_FORMAT): {"new_leads": 0, "emails_sent": 0}
        for i in range(period_days)
    }

    for l in leads:
        # Match source and status
        if not lead_matches(l, None, None, src_f, stat_f, apply_date=False):
            continue

        ldt = get_lead_date(l)
        score_val = float(l.get("ai_score") or l.get("Ai Score") or 0)
        status_val = str(l.get("Status") or l.get("status") or "NEW").strip().upper()
        em_stat = str(l.get("email_status") or l.get("Email Status") or "").strip().upper()

        if ldt:
            d_str = ldt.strftime(DATE_FORMAT)
            if start_dt <= ldt <= end_dt:
                new_cur += 1
                if d_str in daily_map:
                    daily_map[d_str]["new_leads"] += 1
                if score_val >= 7:
                    hot_cur += 1
                if status_val in ("CONTACTED", "EMAIL_SENT") or em_stat == "SENT":
                    contacted_cur += 1
                if status_val == "REPLIED":
                    replied_cur += 1
                if status_val == "MEETING":
                    meetings_cur += 1
                if status_val == "WON":
                    won_cur += 1
                if status_val in ("LOST", "DISQUALIFIED"):
                    lost_cur += 1
            elif not is_all_time and prev_start_dt <= ldt <= prev_end_dt:
                new_prev += 1
                if score_val >= 7:
                    hot_prev += 1
                if status_val in ("CONTACTED", "EMAIL_SENT") or em_stat == "SENT":
                    contacted_prev += 1
                if status_val == "REPLIED":
                    replied_prev += 1
                if status_val == "MEETING":
                    meetings_prev += 1
                if status_val == "WON":
                    won_prev += 1
                if status_val in ("LOST", "DISQUALIFIED"):
                    lost_prev += 1

    # Map daily emails sent
    for s in sent:
        dt = _parse_ts(s.get("sent_at"))
        if dt and start_dt <= dt <= end_dt:
            d_str = dt.strftime(DATE_FORMAT)
            if d_str in daily_map:
                daily_map[d_str]["emails_sent"] += 1

    for a in activities:
        if a.get("type") in ("email_sent", "email"):
            dt = _parse_ts(a.get("occurred_at"))
            if dt and start_dt <= dt <= end_dt and a.get("occurred_at") not in sent_times:
                d_str = dt.strftime(DATE_FORMAT)
                if d_str in daily_map:
                    daily_map[d_str]["emails_sent"] += 1

    daily_series = [{"date": d, **v} for d, v in sorted(daily_map.items())]

    # Overdue follow-ups is strictly as of 'now'
    overdue_count = 0
    today_dt = now.replace(hour=0, minute=0, second=0, microsecond=0)
    for a in activities:
        if a.get("type") == followup_store.FOLLOWUP and a.get("followup_status") == "pending":
            due = _parse_ts(a.get("due_at"))
            if due and due < today_dt:
                overdue_count += 1

    def make_card(key: str, label: str, cur: int, prev: int, title: str) -> Dict[str, Any]:
        chg = None if is_all_time else (cur - prev)
        return {
            "key": key,
            "label": label,
            "value": cur,
            "prev_value": None if is_all_time else prev,
            "change": chg,
            "title": title
        }

    cards = [
        make_card("total_leads", "Total Leads", total_leads_all_time, total_leads_all_time, "All unique leads discovered to date"),
        make_card("new_leads", "New Leads", new_cur, new_prev, "New leads first discovered in selected date range"),
        make_card("hot_leads", "Hot Leads", hot_cur, hot_prev, "Leads with AI Score >= 7 in selected range"),
        make_card("contacted", "Contacted", contacted_cur, contacted_prev, "Leads moved to Contacted or Email Sent status"),
        make_card("replied", "Replied", replied_cur, replied_prev, "Leads that replied to our outreach in this range"),
        make_card("meetings", "Meetings", meetings_cur, meetings_prev, "Leads moved to Meeting status"),
        make_card("won", "Deals Won", won_cur, won_prev, "Leads successfully converted to Won clients"),
        make_card("lost", "Lost / Disqualified", lost_cur, lost_prev, "Leads marked as Lost or Disqualified"),
        make_card("emails_sent", "Emails Sent", sent_cur, sent_prev, "Cold outreach & sequence emails dispatched in this range"),
        make_card("scraper_runs", "Scraper Executions", runs_cur, runs_prev, "Individual scraper executions in this range"),
        make_card("failed_scrapers", "Scraper Failures", failed_cur, failed_prev, "Scraper runs that reported an error or failure"),
        make_card("overdue_followups", "Overdue Follow-ups", overdue_count, 0, "Follow-ups currently pending whose scheduled due date has passed (calculated as of now)")
    ]

    return {
        "period": {
            "date_from": d_from_str,
            "date_to": d_to_str,
            "days": period_days,
            "is_all_time": is_all_time,
            "prev_date_from": prev_start_dt.strftime(DATE_FORMAT) if not is_all_time else None,
            "prev_date_to": prev_end_dt.strftime(DATE_FORMAT) if not is_all_time else None,
        },
        "filters": {
            "source": src_f,
            "status": stat_f,
        },
        "cards": cards,
        "daily_series": daily_series,
        "attention_counts": {
            "overdue_followups": overdue_count,
            "failed_scrapers": failed_cur,
        }
    }


# ---------------------------------------------------------------------------
# R2: Scraper Report
# ---------------------------------------------------------------------------

def scraper_report(
    runs: List[Dict[str, Any]],
    filters: Optional[Dict[str, Any]] = None,
    now: Optional[datetime.datetime] = None
) -> Dict[str, Any]:
    now = now or datetime.datetime.now().replace(microsecond=0)
    start_dt, end_dt, _, _, d_from_str, d_to_str = parse_and_validate_filters(filters, None, now)

    # Filter runs in period
    filtered_runs = []
    skipped_rows = 0

    for r in runs:
        st_time = _parse_ts(r.get("start_time"))
        if not st_time:
            skipped_rows += 1
            continue
        if start_dt <= st_time <= end_dt:
            filtered_runs.append(r)

    # Group runs by script name (everything before first " (")
    scraper_groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    full_labels: Dict[str, str] = {}

    for r in filtered_runs:
        raw_name = (r.get("scraper_name") or "unknown_scraper.py").strip()
        script = raw_name.split(" (")[0].strip() or "unknown_scraper.py"
        scraper_groups[script].append(r)
        if script not in full_labels or len(raw_name) > len(full_labels[script]):
            full_labels[script] = raw_name

    scrapers_table = []
    tot_runs = 0
    tot_success = 0
    tot_failed = 0
    tot_records = 0
    tot_new = 0
    tot_updated = 0
    tot_dupes = 0

    for script, s_runs in scraper_groups.items():
        # Sort s_runs by start_time ascending
        s_runs_sorted = sorted(s_runs, key=lambda x: x.get("start_time") or "")
        latest = s_runs_sorted[-1]

        def _int(k, row):
            try:
                return int(float(row.get(k) or 0))
            except ValueError:
                return 0

        times_run = len(s_runs)
        success_count = sum(1 for r in s_runs if (r.get("status") or "").lower() == "success")
        fail_count = sum(1 for r in s_runs if (r.get("status") or "").lower() == "failed")
        records = sum(_int("records_collected", r) for r in s_runs)
        new_leads = sum(_int("new_leads_added", r) for r in s_runs)
        updated = sum(_int("existing_leads_updated", r) for r in s_runs)
        dupes = sum(_int("duplicates_detected", r) for r in s_runs)

        tot_runs += times_run
        tot_success += success_count
        tot_failed += fail_count
        tot_records += records
        tot_new += new_leads
        tot_updated += updated
        tot_dupes += dupes

        dupe_pct = round(100.0 * dupes / records, 1) if records > 0 else 0.0
        yield_pct = round(100.0 * new_leads / records, 1) if records > 0 else 0.0

        # Days since it last added a new lead (from all runs in history for this scraper)
        days_since_new: Optional[int] = None
        for r in reversed(s_runs_sorted):
            if _int("new_leads_added", r) > 0:
                t = _parse_ts(r.get("start_time"))
                if t:
                    days_since_new = max(0, (now.date() - t.date()).days)
                    break

        scrapers_table.append({
            "script_name": script,
            "full_name": full_labels.get(script, script),
            "times_run": times_run,
            "successful": success_count,
            "failed": fail_count,
            "records_collected": records,
            "new_leads_added": new_leads,
            "existing_leads_updated": updated,
            "duplicates_detected": dupes,
            "duplicate_pct": dupe_pct,
            "yield_pct": yield_pct,
            "last_run_time": latest.get("start_time") or "",
            "last_status": latest.get("status") or "Unknown",
            "last_error": latest.get("error_summary") or "",
            "days_since_new_lead": days_since_new,
        })

    # Sort scrapers by new leads desc, then times_run desc
    scrapers_table.sort(key=lambda x: (x["new_leads_added"], x["times_run"]), reverse=True)

    totals = {
        "script_name": "Total / Aggregate",
        "full_name": "All Scrapers Combined",
        "times_run": tot_runs,
        "successful": tot_success,
        "failed": tot_failed,
        "records_collected": tot_records,
        "new_leads_added": tot_new,
        "existing_leads_updated": tot_updated,
        "duplicates_detected": tot_dupes,
        "duplicate_pct": round(100.0 * tot_dupes / tot_records, 1) if tot_records > 0 else 0.0,
        "yield_pct": round(100.0 * tot_new / tot_records, 1) if tot_records > 0 else 0.0,
        "last_run_time": "",
        "last_status": "OK" if tot_failed == 0 else f"{tot_failed} Failures",
        "last_error": "",
        "days_since_new_lead": None,
    }

    # Per-run table (grouped by run_id)
    runs_by_id: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in filtered_runs:
        rid = r.get("run_id") or "UNKNOWN_RUN"
        runs_by_id[rid].append(r)

    runs_table = []
    for rid, r_items in runs_by_id.items():
        starts = [_parse_ts(r.get("start_time")) for r in r_items if _parse_ts(r.get("start_time"))]
        ends = [_parse_ts(r.get("end_time")) for r in r_items if _parse_ts(r.get("end_time"))]
        min_start = min(starts) if starts else None
        max_end = max(ends) if ends else (max(starts) if starts else None)

        dur_min = 0.0
        if min_start and max_end:
            dur_min = round(max(0.0, (max_end - min_start).total_seconds() / 60.0), 1)

        def _val(k):
            return sum(int(float(r.get(k) or 0)) for r in r_items if str(r.get(k) or "").strip().replace(".", "").isdigit())

        fails = sum(1 for r in r_items if (r.get("status") or "").lower() == "failed")

        runs_table.append({
            "run_id": rid,
            "start_time": min_start.strftime(TS_FORMAT) if min_start else (r_items[0].get("start_time") or ""),
            "end_time": max_end.strftime(TS_FORMAT) if max_end else (r_items[-1].get("end_time") or ""),
            "duration_minutes": dur_min,
            "scrapers_count": len(r_items),
            "failed_scrapers_count": fails,
            "total_records": _val("records_collected"),
            "total_new_leads": _val("new_leads_added"),
        })

    runs_table.sort(key=lambda r: r["start_time"], reverse=True)

    # Flags analysis (across all known runs in history for accuracy)
    all_by_script: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in runs:
        script = (r.get("scraper_name") or "").split(" (")[0].strip()
        if script:
            all_by_script[script].append(r)

    failed_last_run = []
    not_producing = []
    stale_scrapers = []

    for script, history in all_by_script.items():
        hist_sorted = sorted(history, key=lambda x: x.get("start_time") or "")
        if not hist_sorted:
            continue
        last = hist_sorted[-1]
        last_st = (last.get("status") or "").lower()

        # 1. Failed last run
        if last_st == "failed":
            failed_last_run.append({
                "script": script,
                "status": last.get("status") or "Failed",
                "error": last.get("error_summary") or "Unspecified error",
                "time": last.get("start_time") or ""
            })

        # 2. Not producing (0 new leads in last 10 runs)
        last_10 = hist_sorted[-10:]
        if len(last_10) >= 3:  # at least 3 runs to evaluate
            added_sum = sum(int(float(x.get("new_leads_added") or 0)) for x in last_10 if str(x.get("new_leads_added") or "").isdigit())
            if added_sum == 0:
                not_producing.append({
                    "script": script,
                    "runs_checked": len(last_10),
                    "new_leads_added": 0,
                    "last_run": last.get("start_time") or ""
                })

        # 3. Stale scraper (> 24 hours since last run)
        last_dt = _parse_ts(last.get("start_time"))
        if last_dt and (now - last_dt).total_seconds() > (24 * 3600):
            hours_ago = round((now - last_dt).total_seconds() / 3600.0, 1)
            stale_scrapers.append({
                "script": script,
                "last_run": last.get("start_time") or "",
                "hours_ago": hours_ago
            })

    return {
        "period": {"date_from": d_from_str, "date_to": d_to_str},
        "scrapers": scrapers_table,
        "totals": totals,
        "runs": runs_table,
        "skipped_rows": skipped_rows,
        "flags": {
            "failed_last_run": failed_last_run,
            "not_producing": not_producing,
            "stale_scrapers": stale_scrapers,
            "total_flags": len(failed_last_run) + len(not_producing) + len(stale_scrapers)
        }
    }


# ---------------------------------------------------------------------------
# R3: Source Quality Report
# ---------------------------------------------------------------------------

def source_report_rows(
    leads: List[Dict[str, Any]],
    activities: List[Dict[str, Any]],
    filters: Optional[Dict[str, Any]] = None,
    now: Optional[datetime.datetime] = None
) -> Dict[str, Any]:
    now = now or datetime.datetime.now().replace(microsecond=0)
    valid_sources = {source_report.source_family(l) for l in leads}
    start_dt, end_dt, src_f, stat_f, d_from_str, d_to_str = parse_and_validate_filters(filters, valid_sources, now)

    # Filter leads
    matched_leads = [
        l for l in leads
        if lead_matches(l, start_dt, end_dt, src_f, stat_f, apply_date=True)
    ]

    # Pre-index replies and activity by lead_id
    replied_leads = set()
    for a in activities:
        lid = a.get("lead_id")
        if lid and a.get("type") == "reply":
            replied_leads.add(lid)

    groups = defaultdict(list)
    for lead in matched_leads:
        fam = source_report.source_family(lead)
        groups[fam].append(lead)

    rows = []
    for fam, items in groups.items():
        total = len(items)
        with_email = sum(1 for l in items if (l.get("email") or l.get("Email")))
        with_phone = sum(1 for l in items if (l.get("mobile_number") or l.get("Phone")))
        with_contact = sum(1 for l in items if (l.get("email") or l.get("Email") or l.get("mobile_number") or l.get("Phone")))

        scored_leads = []
        for l in items:
            raw_s = l.get("ai_score") or l.get("Ai Score")
            if raw_s is not None and str(raw_s).strip() != "":
                try:
                    scored_leads.append((l, float(raw_s)))
                except ValueError:
                    pass

        avg_score = round(sum(s for _, s in scored_leads) / len(scored_leads), 1) if scored_leads else None
        # Rule matching dashboard: score >= 7 is hot
        hot_count = sum(1 for _, s in scored_leads if s >= 7)
        hot_pct = round(100.0 * hot_count / len(scored_leads), 1) if scored_leads else 0.0

        contacted = sum(
            1 for l in items
            if str(l.get("Status") or l.get("status") or "").upper() in ("CONTACTED", "EMAIL_SENT")
            or str(l.get("email_status") or "").upper() == "SENT"
        )
        replied = sum(
            1 for l in items
            if str(l.get("Status") or l.get("status") or "").upper() == "REPLIED"
            or str(l.get("id") or l.get("lead_id")) in replied_leads
        )
        reply_rate = round(100.0 * replied / contacted, 1) if contacted > 0 else 0.0

        meetings = sum(1 for l in items if str(l.get("Status") or l.get("status") or "").upper() == "MEETING")
        won = sum(1 for l in items if str(l.get("Status") or l.get("status") or "").upper() == "WON")
        stale_count = sum(1 for l in items if lead_quality.is_stale(l))

        low_val = total >= 20 and hot_count == 0

        rows.append({
            "source": fam,
            "leads": total,
            "with_email_pct": round(100.0 * with_email / total, 1),
            "with_phone_pct": round(100.0 * with_phone / total, 1),
            "with_contact_pct": round(100.0 * with_contact / total, 1),
            "ai_scored": len(scored_leads),
            "avg_ai_score": avg_score,
            "hot": hot_count,
            "hot_pct": hot_pct,
            "contacted": contacted,
            "replied": replied,
            "reply_rate_pct": reply_rate,
            "meetings": meetings,
            "won": won,
            "stale": stale_count,
            "low_value": low_val
        })

    rows.sort(key=lambda r: (r["hot"], r["leads"]), reverse=True)

    return {
        "period": {"date_from": d_from_str, "date_to": d_to_str},
        "total_sources": len(rows),
        "rows": rows
    }


# ---------------------------------------------------------------------------
# R4: Follow-up Watchlist ("No Lead Missed")
# ---------------------------------------------------------------------------

def followup_watchlist(
    leads: List[Dict[str, Any]],
    activities: List[Dict[str, Any]],
    sent: List[Dict[str, Any]],
    sequence_plan: Optional[Dict[str, Any]] = None,
    settings: Optional[Dict[str, Any]] = None,
    now: Optional[datetime.datetime] = None,
    quiet_days: int = 5
) -> Dict[str, Any]:
    now = now or datetime.datetime.now().replace(microsecond=0)
    settings = settings or settings_manager.load_settings()
    quiet_days = max(1, min(int(quiet_days or 5), 60))
    today_dt = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Index activities by lead_id and email
    act_by_lead: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for a in activities:
        lid = str(a.get("lead_id") or "").strip()
        if lid:
            act_by_lead[lid].append(a)

    # Pre-index sent emails by clean lowercase email
    sent_by_email: Dict[str, List[datetime.datetime]] = defaultdict(list)
    for s in sent:
        em = (s.get("email") or "").strip().lower()
        dt = _parse_ts(s.get("sent_at"))
        if em and dt:
            sent_by_email[em].append(dt)

    seq_due_ids = {str(item.get("lead_id")) for item in (sequence_plan or {}).get("due", []) if item.get("lead_id")}

    watchlist = []
    dnc_blocked_count = 0
    counts_by_reason: Dict[str, int] = defaultdict(int)

    for l in leads:
        lid = str(l.get("id") or l.get("lead_id") or "").strip()
        comp = (l.get("Company Name") or l.get("company_name") or l.get("name") or "").strip()
        em = (l.get("Email") or l.get("email") or "").split(",")[0].strip()
        phone = (l.get("Phone") or l.get("mobile_number") or "").split(",")[0].strip()
        web = (l.get("Website") or l.get("website") or "").strip()
        source = source_report.source_family(l)
        score_val = float(l.get("ai_score") or l.get("Ai Score") or 0)
        status_val = str(l.get("Status") or l.get("status") or "NEW").strip().upper()
        em_stat = str(l.get("email_status") or l.get("Email Status") or "").strip().upper()

        # Check Do-Not-Contact blacklist once using passed settings
        is_dnc, _ = settings_manager.is_company_excluded(company_name=comp, email=em, website=web, settings=settings)
        if is_dnc:
            dnc_blocked_count += 1

        l_acts = act_by_lead.get(lid, [])
        l_acts_sorted = sorted(l_acts, key=lambda x: x.get("occurred_at") or "")

        # Find latest non-followup contact
        last_contact_type = ""
        last_contact_dt: Optional[datetime.datetime] = None
        for a in reversed(l_acts_sorted):
            if a.get("type") != followup_store.FOLLOWUP:
                last_contact_type = a.get("type") or "contact"
                last_contact_dt = _parse_ts(a.get("occurred_at"))
                break

        # Check sent_emails.csv if no activity record
        if not last_contact_dt and em.lower() in sent_by_email:
            last_contact_type = "email_sent"
            last_contact_dt = max(sent_by_email[em.lower()])

        # Next due follow-up
        pending_fu = next((a for a in l_acts if a.get("type") == followup_store.FOLLOWUP and a.get("followup_status") == "pending"), None)
        next_due_dt = _parse_ts(pending_fu.get("due_at")) if pending_fu else None

        reason = None
        days_waiting = 0

        # Evaluate reasons in exact priority order:
        # 1. overdue_followup
        if pending_fu and next_due_dt and next_due_dt < today_dt:
            reason = "overdue_followup"
            days_waiting = (today_dt.date() - next_due_dt.date()).days

        # 2. replied_no_answer
        elif any(a.get("type") == "reply" for a in l_acts):
            # check if there is an outbound contact after the latest reply
            replies = [a for a in l_acts if a.get("type") == "reply"]
            latest_reply_dt = max([_parse_ts(a.get("occurred_at")) for a in replies if _parse_ts(a.get("occurred_at"))] or [now])
            outbounds_after = [
                a for a in l_acts
                if a.get("type") in ("email_sent", "email", "call", "whatsapp", "meeting")
                and _parse_ts(a.get("occurred_at")) and _parse_ts(a.get("occurred_at")) > latest_reply_dt
            ]
            if not outbounds_after:
                reason = "replied_no_answer"
                days_waiting = (now.date() - latest_reply_dt.date()).days

        # 3. due_today
        elif pending_fu and next_due_dt and today_dt <= next_due_dt < (today_dt + datetime.timedelta(days=1)):
            reason = "due_today"
            days_waiting = 0

        # 4. sequence_due
        elif lid in seq_due_ids:
            reason = "sequence_due"
            days_waiting = 0

        # 5. meeting_no_next_step
        elif status_val == "MEETING" and not (pending_fu and next_due_dt and next_due_dt >= today_dt):
            reason = "meeting_no_next_step"
            days_waiting = (now.date() - last_contact_dt.date()).days if last_contact_dt else 1

        # 6. contacted_gone_quiet (Leads on DNC never get this)
        elif not is_dnc and (last_contact_dt or em_stat == "SENT") and status_val not in ("WON", "LOST", "DISQUALIFIED", "REPLIED", "MEETING"):
            contact_date = last_contact_dt or get_lead_date(l)
            if contact_date:
                diff_days = (now.date() - contact_date.date()).days
                if diff_days >= quiet_days and not pending_fu:
                    reason = "contacted_gone_quiet"
                    days_waiting = diff_days

        # 7. hot_never_contacted (Leads on DNC never get this)
        elif not is_dnc and score_val >= 7 and (em or phone) and not last_contact_dt and em_stat != "SENT" and status_val == "NEW":
            reason = "hot_never_contacted"
            ldt = get_lead_date(l)
            days_waiting = (now.date() - ldt.date()).days if ldt else 0

        # 8. stale_open
        elif lead_quality.is_stale(l) and status_val in ("NEW", "CONTACTED", "EMAIL_SENT"):
            reason = "stale_open"
            ldt = get_lead_date(l)
            days_waiting = (now.date() - ldt.date()).days if ldt else 0

        if reason:
            counts_by_reason[reason] += 1
            reason_labels = {
                "overdue_followup": "Overdue Follow-up",
                "replied_no_answer": "Replied - Needs Answer",
                "due_today": "Follow-up Due Today",
                "sequence_due": "Sequence Step Due",
                "meeting_no_next_step": "Meeting Without Next Step",
                "contacted_gone_quiet": f"Contacted >{quiet_days}d Ago (Quiet)",
                "hot_never_contacted": "Hot Lead Never Contacted",
                "stale_open": "Stale Lead Still Open",
                "needs_review": "Needs Review"
            }
            watchlist.append({
                "lead_id": lid,
                "company": comp or "Unnamed Company",
                "email": em,
                "phone": phone,
                "source": source,
                "ai_score": score_val,
                "status": status_val,
                "reason": reason,
                "reason_label": reason_labels.get(reason, reason),
                "days_waiting": days_waiting,
                "last_contact_type": last_contact_type,
                "last_contact_date": last_contact_dt.strftime(DATE_FORMAT) if last_contact_dt else "",
                "next_due_date": next_due_dt.strftime(DATE_FORMAT) if next_due_dt else "",
                "note": pending_fu.get("summary") if pending_fu else ""
            })

    # Priority sorting order for watchlist rows
    priority_map = {
        "overdue_followup": 1,
        "replied_no_answer": 2,
        "due_today": 3,
        "sequence_due": 4,
        "meeting_no_next_step": 5,
        "contacted_gone_quiet": 6,
        "hot_never_contacted": 7,
        "stale_open": 8,
        "needs_review": 9
    }
    watchlist.sort(key=lambda x: (priority_map.get(x["reason"], 99), -x["days_waiting"]))

    return {
        "total": len(watchlist),
        "counts_by_reason": dict(counts_by_reason),
        "blocked_by_dnc_count": dnc_blocked_count,
        "quiet_days_parameter": quiet_days,
        "items": watchlist
    }


# ---------------------------------------------------------------------------
# R5: Pipeline / Funnel Report
# ---------------------------------------------------------------------------

def pipeline(
    leads: List[Dict[str, Any]],
    activities: List[Dict[str, Any]],
    filters: Optional[Dict[str, Any]] = None,
    now: Optional[datetime.datetime] = None
) -> Dict[str, Any]:
    now = now or datetime.datetime.now().replace(microsecond=0)
    valid_sources = {source_report.source_family(l) for l in leads}
    start_dt, end_dt, src_f, _, d_from_str, d_to_str = parse_and_validate_filters(filters, valid_sources, now)

    # Filter leads in period (status filter is not applied to funnel stages so full pipeline is visible)
    matched_leads = [
        l for l in leads
        if lead_matches(l, start_dt, end_dt, src_f, status_filter="all", apply_date=True)
    ]

    total_leads = len(matched_leads)
    stage_counts = {st: 0 for st in ALL_STAGES}

    for l in matched_leads:
        st = str(l.get("Status") or l.get("status") or "NEW").strip().upper()
        if st in stage_counts:
            stage_counts[st] += 1
        else:
            stage_counts["NEW"] += 1

    stages_data = []
    for st in ALL_STAGES:
        c = stage_counts[st]
        pct = round(100.0 * c / total_leads, 1) if total_leads > 0 else 0.0
        stages_data.append({
            "stage": st,
            "count": c,
            "percentage": pct
        })

    # Conversions between consecutive progression stages
    progression = ["NEW", "CONTACTED", "REPLIED", "MEETING", "WON"]
    conversions = []
    for i in range(len(progression) - 1):
        s_from = progression[i]
        s_to = progression[i + 1]
        c_from = stage_counts[s_from]
        c_to = stage_counts[s_to]
        conv_rate = round(100.0 * c_to / c_from, 1) if c_from > 0 else None
        conversions.append({
            "from_stage": s_from,
            "to_stage": s_to,
            "from_count": c_from,
            "to_count": c_to,
            "conversion_pct": conv_rate
        })

    # Stuck leads (> 14 days without activity)
    stuck_by_stage = {st: 0 for st in ALL_STAGES}
    fourteen_days_ago = now - datetime.timedelta(days=14)

    act_by_lead = defaultdict(list)
    for a in activities:
        lid = a.get("lead_id")
        if lid:
            act_by_lead[lid].append(a)

    for l in matched_leads:
        lid = str(l.get("id") or l.get("lead_id") or "")
        st = str(l.get("Status") or l.get("status") or "NEW").strip().upper()
        l_acts = act_by_lead.get(lid, [])
        latest_act = None
        for a in l_acts:
            dt = _parse_ts(a.get("occurred_at"))
            if dt and (not latest_act or dt > latest_act):
                latest_act = dt

        last_date = latest_act or get_lead_date(l)
        if last_date and last_date < fourteen_days_ago:
            if st in stuck_by_stage:
                stuck_by_stage[st] += 1

    return {
        "period": {"date_from": d_from_str, "date_to": d_to_str},
        "total_leads": total_leads,
        "stages": stages_data,
        "conversions": conversions,
        "stuck_leads": {
            "threshold_days": 14,
            "counts": stuck_by_stage,
            "total_stuck": sum(stuck_by_stage.values())
        }
    }


# ---------------------------------------------------------------------------
# R6: Outreach Report
# ---------------------------------------------------------------------------

def outreach(
    leads: List[Dict[str, Any]],
    activities: List[Dict[str, Any]],
    sent: List[Dict[str, Any]],
    settings: Optional[Dict[str, Any]] = None,
    filters: Optional[Dict[str, Any]] = None,
    now: Optional[datetime.datetime] = None
) -> Dict[str, Any]:
    now = now or datetime.datetime.now().replace(microsecond=0)
    settings = settings or settings_manager.load_settings()
    valid_sources = {source_report.source_family(l) for l in leads}
    start_dt, end_dt, src_f, stat_f, d_from_str, d_to_str = parse_and_validate_filters(filters, valid_sources, now)

    # Classify sends
    by_channel = {
        "auto": 0,
        "manual": 0,
        "bulk": 0,
        "sequence": 0,
        "other": 0,
        "before_tracking": 0
    }
    subject_sends: Dict[str, int] = defaultdict(int)
    subject_replies: Dict[str, int] = defaultdict(int)

    tracked_stamps = set()
    bounces = 0
    opt_outs = 0
    replies = 0

    for a in activities:
        dt = _parse_ts(a.get("occurred_at"))
        atype = a.get("type")
        src = (a.get("source") or "").lower()
        sub = (a.get("summary") or "").replace("Email sent: ", "").strip()

        if dt and start_dt <= dt <= end_dt:
            if atype in ("email_sent", "email"):
                tracked_stamps.add((a.get("lead_email", "").lower(), a.get("occurred_at", "")[:16]))
                if "auto" in src or "scraper" in src:
                    by_channel["auto"] += 1
                elif "bulk" in src:
                    by_channel["bulk"] += 1
                elif "sequence" in src:
                    by_channel["sequence"] += 1
                elif "dashboard" in src or "manual" in src:
                    by_channel["manual"] += 1
                else:
                    by_channel["other"] += 1

                if sub:
                    subject_sends[sub[:80]] += 1

            elif atype == "reply":
                replies += 1
                if sub:
                    subject_replies[sub[:80]] += 1
            elif atype == "bounce":
                bounces += 1
            elif atype == "opted_out":
                opt_outs += 1

    # Check older sent_emails.csv
    for s in sent:
        dt = _parse_ts(s.get("sent_at"))
        if dt and start_dt <= dt <= end_dt:
            em = s.get("email", "").lower()
            stamp_key = (em, s.get("sent_at", "")[:16])
            if stamp_key not in tracked_stamps:
                by_channel["before_tracking"] += 1
                sub = (s.get("subject") or "").strip()
                if sub:
                    subject_sends[sub[:80]] += 1

    total_sent = sum(by_channel.values())
    reply_rate = round(100.0 * replies / total_sent, 1) if total_sent > 0 else 0.0

    # Count DNC blocked leads
    dnc_blocked = 0
    for l in leads:
        comp = (l.get("Company Name") or l.get("company_name") or "").strip()
        em = (l.get("Email") or l.get("email") or "").split(",")[0].strip()
        web = (l.get("Website") or l.get("website") or "").strip()
        is_dnc, _ = settings_manager.is_company_excluded(company_name=comp, email=em, website=web, settings=settings)
        if is_dnc:
            dnc_blocked += 1

    top_subjects_sent = [
        {"subject": k, "count": v}
        for k, v in sorted(subject_sends.items(), key=lambda x: x[1], reverse=True)[:10]
    ]
    top_subjects_replied = [
        {"subject": k, "count": v}
        for k, v in sorted(subject_replies.items(), key=lambda x: x[1], reverse=True)[:10]
    ]

    return {
        "period": {"date_from": d_from_str, "date_to": d_to_str},
        "total_sent": total_sent,
        "by_channel": by_channel,
        "performance": {
            "replies": replies,
            "reply_rate_pct": reply_rate,
            "bounces": bounces,
            "opt_outs": opt_outs
        },
        "dnc_blocked_leads": dnc_blocked,
        "top_subjects_sent": top_subjects_sent,
        "top_subjects_replied": top_subjects_replied
    }


# ---------------------------------------------------------------------------
# R7: Data Health Report
# ---------------------------------------------------------------------------

def data_health(
    leads: List[Dict[str, Any]],
    now: Optional[datetime.datetime] = None
) -> Dict[str, Any]:
    now = now or datetime.datetime.now().replace(microsecond=0)
    total_leads = len(leads)

    missing_email_ids = []
    missing_phone_ids = []
    missing_website_ids = []
    missing_all_ids = []
    no_score_ids = []
    stale_ids = []
    post_title_company_ids = []

    email_counts = defaultdict(list)
    company_counts = defaultdict(list)

    for l in leads:
        lid = str(l.get("id") or l.get("lead_id") or "")
        em = (l.get("Email") or l.get("email") or "").strip()
        ph = (l.get("Phone") or l.get("mobile_number") or "").strip()
        web = (l.get("Website") or l.get("website") or "").strip()
        raw_score = l.get("ai_score") or l.get("Ai Score")
        comp = (l.get("Company Name") or l.get("company_name") or l.get("full_name") or "").strip()

        has_em = bool(em and em.lower() not in ("none", "n/a", "null"))
        has_ph = bool(ph and ph.lower() not in ("none", "n/a", "null"))
        has_web = bool(web and web.lower() not in ("none", "n/a", "null"))

        if not has_em:
            missing_email_ids.append(lid)
        else:
            for single_em in em.split(","):
                clean_em = single_em.strip().lower()
                if clean_em and "@" in clean_em:
                    email_counts[clean_em].append(lid)

        if not has_ph:
            missing_phone_ids.append(lid)
        if not has_web:
            missing_website_ids.append(lid)
        if not has_em and not has_ph and not has_web:
            missing_all_ids.append(lid)

        if raw_score is None or str(raw_score).strip() in ("", "None", "null"):
            no_score_ids.append(lid)

        if lead_quality.is_stale(l):
            stale_ids.append(lid)

        if comp:
            norm_comp = re.sub(r"[^\w\s]", "", comp).strip().lower()
            if norm_comp and len(norm_comp) >= 3:
                company_counts[norm_comp].append(lid)
            # Check post title marker
            if followup_sequence.company_for_email(comp) == "your team":
                post_title_company_ids.append(lid)

    duplicate_email_ids = []
    for em, lids in email_counts.items():
        if len(lids) > 1:
            duplicate_email_ids.extend(lids)
    duplicate_email_ids = list(dict.fromkeys(duplicate_email_ids))

    duplicate_company_ids = []
    for cname, lids in company_counts.items():
        if len(lids) > 1:
            duplicate_company_ids.extend(lids)
    duplicate_company_ids = list(dict.fromkeys(duplicate_company_ids))

    def make_metric(name: str, label: str, ids: List[str], severity: str, desc: str) -> Dict[str, Any]:
        count = len(ids)
        pct = round(100.0 * count / total_leads, 1) if total_leads > 0 else 0.0
        return {
            "metric": name,
            "label": label,
            "count": count,
            "percentage": pct,
            "severity": severity,
            "description": desc,
            "sample_lead_ids": ids[:20]
        }

    metrics = [
        make_metric("missing_email", "Missing Email Address", missing_email_ids, "high", "Leads without any direct email address for cold outreach."),
        make_metric("missing_phone", "Missing Phone Number", missing_phone_ids, "medium", "Leads without direct phone or WhatsApp contact."),
        make_metric("missing_website", "Missing Website Domain", missing_website_ids, "low", "Leads without an online company website."),
        make_metric("missing_all_three", "Missing Email, Phone & Website", missing_all_ids, "high", "Completely uncontactable leads lacking all channels."),
        make_metric("no_ai_score", "Unqualified (No AI Score)", no_score_ids, "medium", "Leads pending AI evaluation and classification."),
        make_metric("stale", "Stale (>14 Days Old)", stale_ids, "medium", "Leads posted or discovered over 14 days ago."),
        make_metric("duplicate_emails", "Duplicate Email Addresses", duplicate_email_ids, "high", "Multiple leads sharing identical email addresses."),
        make_metric("duplicate_companies", "Duplicate Company Names", duplicate_company_ids, "medium", "Leads with normalized identical company names."),
        make_metric("post_title_as_company", "Job Post Title As Company Name", post_title_company_ids, "low", "Scraped names containing job keywords or brackets.")
    ]

    return {
        "total_leads": total_leads,
        "metrics": metrics
    }


# ---------------------------------------------------------------------------
# R8: Daily Activity Log
# ---------------------------------------------------------------------------

def activity_log(
    runs: List[Dict[str, Any]],
    activities: List[Dict[str, Any]],
    sent: List[Dict[str, Any]],
    leads: List[Dict[str, Any]],
    day_str: Optional[str] = None,
    now: Optional[datetime.datetime] = None
) -> Dict[str, Any]:
    now = now or datetime.datetime.now().replace(microsecond=0)
    day_str = (day_str or now.strftime(DATE_FORMAT)).strip()

    try:
        target_day = datetime.datetime.strptime(day_str, DATE_FORMAT).date()
    except ValueError:
        raise ValueError(f"Invalid day '{day_str}'. Format must be YYYY-MM-DD.")

    events = []

    # 1. Scraper runs on day
    for r in runs:
        dt = _parse_ts(r.get("start_time"))
        if dt and dt.date() == target_day:
            new_c = r.get("new_leads_added") or "0"
            rec_c = r.get("records_collected") or "0"
            st = r.get("status") or "Success"
            script = (r.get("scraper_name") or "").split(" (")[0].strip()
            events.append({
                "time": dt.strftime(TS_FORMAT),
                "type": "scraper_run",
                "badge": "SCRAPER",
                "title": f"Scraper Run: {script}",
                "description": f"Status: {st} · Records: {rec_c} · New Leads Added: {new_c}",
                "lead_id": "",
                "lead_name": "",
            })

    # 2. Leads added on day
    for l in leads:
        dt = get_lead_date(l)
        if dt and dt.date() == target_day:
            lid = str(l.get("id") or l.get("lead_id") or "")
            comp = (l.get("Company Name") or l.get("company_name") or "Unnamed").strip()
            src = source_report.source_family(l)
            events.append({
                "time": dt.strftime(TS_FORMAT),
                "type": "lead_added",
                "badge": "LEAD",
                "title": f"New Lead Discovered: {comp}",
                "description": f"Source: {src} · ID: {lid}",
                "lead_id": lid,
                "lead_name": comp,
            })

    # 3. Follow-up activities on day
    for a in activities:
        dt = _parse_ts(a.get("occurred_at"))
        if dt and dt.date() == target_day:
            atype = a.get("type") or "activity"
            events.append({
                "time": dt.strftime(TS_FORMAT),
                "type": atype,
                "badge": atype.upper(),
                "title": a.get("summary") or f"Activity: {atype}",
                "description": a.get("details") or f"Recorded on {a.get('lead_name') or 'lead'}",
                "lead_id": a.get("lead_id") or "",
                "lead_name": a.get("lead_name") or "",
            })

    # 4. Sent emails on day (skip if already captured in activity)
    act_stamps = {(a.get("lead_email", "").lower(), a.get("occurred_at", "")[:16]) for a in activities}
    for s in sent:
        dt = _parse_ts(s.get("sent_at"))
        if dt and dt.date() == target_day:
            em = s.get("email", "").lower()
            if (em, s.get("sent_at", "")[:16]) not in act_stamps:
                events.append({
                    "time": dt.strftime(TS_FORMAT),
                    "type": "email_sent",
                    "badge": "EMAIL",
                    "title": f"Email Sent to {em}",
                    "description": f"Subject: {s.get('subject') or 'Cold Outreach'}",
                    "lead_id": "",
                    "lead_name": em,
                })

    events.sort(key=lambda x: x["time"], reverse=True)

    return {
        "day": day_str,
        "total_events": len(events),
        "events": events
    }


# ---------------------------------------------------------------------------
# Filter Options Endpoint
# ---------------------------------------------------------------------------

def get_filter_options(leads: List[Dict[str, Any]]) -> Dict[str, Any]:
    sources = sorted(list({source_report.source_family(l) for l in leads if source_report.source_family(l)}))
    now = datetime.datetime.now().replace(microsecond=0)
    d_from, d_to = get_preset_range("30d", now)

    return {
        "presets": PRESETS,
        "sources": ["all"] + sources,
        "stages": ["ALL"] + ALL_STAGES,
        # names the Reports page reads for its Source and Stage dropdowns
        "source_families": sources,
        "statuses": list(ALL_STAGES),
        "default_range": {
            "preset": "30d",
            "date_from": d_from,
            "date_to": d_to
        }
    }


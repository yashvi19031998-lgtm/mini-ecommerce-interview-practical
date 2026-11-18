"""Reports > Summary: one report a client can read in a minute.

For the leads FOUND in the chosen period (and the chosen client type, temperature and source):
  - funnel: found -> contacted -> reached by phone -> replied -> meeting -> won, with the share at each step
  - work done in the period: mails sent, calls, WhatsApps, post replies, replies received
  - by day: leads found and leads contacted per day
  - by source and by client type: found, hot, contacted, replied, reply rate
  - highlights: plain-sentence findings computed from the numbers (no key needed)
  - insight(): the same numbers handed to Claude / Gemini for a short analysis (numbers only, no contact data)
"""
import datetime
import json
import os
import re
from typing import Any, Dict, List, Optional

import lead_status

CLIENT_TYPES = {
    "it_project": "IT project",
    "hiring": "Hiring developers",
    "digital": "Digital marketing",
    "prospect": "Business prospect",
    "other": "Not a fit / unknown",
}
PRESETS = {"today": 0, "7d": 6, "30d": 29, "90d": 89}
_DIGITAL = re.compile(r"\b(seo|social media|google ads|facebook ads|meta ads|instagram|ppc|digital marketing|marketing)\b", re.I)


def _s(v: Any) -> str:
    s = str(v if v is not None else "").strip()
    return "" if s.lower() in ("nan", "n/a", "none", "null") else s


def client_type(lead: Dict[str, Any]) -> str:
    cat = _s(lead.get("ai_category")).lower()
    if cat in lead_status.NOT_FIT or not cat:
        return "other"
    text = f"{_s(lead.get('company_name'))} {_s(lead.get('ai_requirement'))} {_s(lead.get('description'))[:600]}"
    if _DIGITAL.search(text):
        return "digital"
    return {"client_project": "it_project", "hiring_developer": "hiring", "prospect_signal": "prospect"}.get(cat, "other")


def source_family(lead: Dict[str, Any]) -> str:
    return _s(lead.get("source")).split("|")[-1].split("(")[0].replace('"', "").strip() or "Unknown"


def _day(v) -> Optional[datetime.date]:
    s = _s(v)[:10]
    try:
        return datetime.date.fromisoformat(s)
    except ValueError:
        return None


def period(filters: Dict[str, Any], today: Optional[datetime.date] = None):
    """(start, end) dates from preset (today, 7d, 30d, 90d, month, last_month, all) or date_from / date_to."""
    today = today or datetime.date.today()
    preset = _s(filters.get("preset")) or ("" if filters.get("date_from") else "30d")
    if preset in PRESETS:
        return today - datetime.timedelta(days=PRESETS[preset]), today
    if preset == "month":
        return today.replace(day=1), today
    if preset == "last_month":
        end = today.replace(day=1) - datetime.timedelta(days=1)
        return end.replace(day=1), end
    if preset == "all":
        return datetime.date(2000, 1, 1), today
    start, end = _day(filters.get("date_from")), _day(filters.get("date_to")) or today
    if not start:
        raise ValueError("Pick a period, or a valid start date (YYYY-MM-DD).")
    if start > end:
        raise ValueError("The start date is after the end date.")
    return start, end


def _pct(a, b):
    return round(100 * a / b) if b else 0


def build(leads: List[Dict[str, Any]], sent: List[Dict[str, str]], activities: List[Dict[str, str]],
          filters: Optional[Dict[str, Any]] = None, today: Optional[datetime.date] = None) -> Dict[str, Any]:
    filters = filters or {}
    start, end = period(filters, today)
    ctype, band, source = _s(filters.get("client_type")), _s(filters.get("band")), _s(filters.get("source"))
    if ctype and ctype not in CLIENT_TYPES:
        raise ValueError(f"Unknown client type '{ctype}'.")
    if band and band not in ("hot", "warm", "cold", "unscored"):
        raise ValueError(f"Unknown temperature '{band}'.")
    ctx = lead_status.build_context(sent, activities)
    now = datetime.datetime.combine(end, datetime.time(23, 59))

    def keep(l):
        if ctype and client_type(l) != ctype:
            return False
        if band and lead_status.band_of(l) != band:
            return False
        if source and source_family(l) != source:
            return False
        return True

    in_scope = [l for l in leads if keep(l)]
    cohort = [l for l in in_scope if (d := _day(l.get("first_seen_at"))) and start <= d <= end]
    ids = {lead_status.lead_id_of(l) for l in in_scope}
    emails = {e for l in in_scope if (e := lead_status._first_email(l))}

    funnel = {"found": 0, "contacted": 0, "phone": 0, "replied": 0, "meeting": 0, "won": 0}
    groups: Dict[str, Dict[str, Dict[str, int]]] = {"source": {}, "client_type": {}}
    days = {}
    d = start
    while d <= end and len(days) < 400:
        days[d.isoformat()] = {"day": d.isoformat(), "found": 0, "contacted": 0}
        d += datetime.timedelta(days=1)
    stage_counts: Dict[str, int] = {}

    for l in cohort:
        st = lead_status.stage_of(l, ctx, now)
        info = {**ctx["by_email"].get(lead_status._first_email(l), {}), **ctx["by_id"].get(lead_status.lead_id_of(l), {})}
        status = _s(l.get("status")).upper()
        contacted = bool(st["last_contact"]) or status in ("CONTACTED", "EMAIL_SENT", "REPLIED", "MEETING", "WON")
        replied = bool(info.get("reply")) or status in ("REPLIED", "MEETING", "WON")
        row = {"found": 1, "hot": int(lead_status.band_of(l) == "hot"), "contacted": int(contacted),
               "phone": int(bool(info.get("phone"))), "replied": int(replied),
               "meeting": int(status in ("MEETING", "WON")), "won": int(status == "WON")}
        for k in funnel:
            funnel[k] += row.get(k, 0)
        for gk, key in (("source", source_family(l)), ("client_type", CLIENT_TYPES[client_type(l)])):
            g = groups[gk].setdefault(key, {"name": key, "found": 0, "hot": 0, "contacted": 0, "replied": 0, "won": 0})
            for k in ("found", "hot", "contacted", "replied", "won"):
                g[k] += row[k]
        stage_counts[st["stage"]] = stage_counts.get(st["stage"], 0) + 1
        day = _day(l.get("first_seen_at")).isoformat()
        if day in days:
            days[day]["found"] += 1

    # Work done in the period (for the leads in scope, whenever they were found)
    work = {"mails": 0, "calls": 0, "whatsapps": 0, "post_replies": 0, "replies_received": 0}
    contacted_days: Dict[str, set] = {}
    for s in sent:
        dd = _day(s.get("sent_at"))
        if dd and start <= dd <= end and s.get("email") in emails:
            work["mails"] += 1
            contacted_days.setdefault(dd.isoformat(), set()).add(s.get("email"))
    kinds = {"call": "calls", "whatsapp": "whatsapps", "message": "post_replies", "reply": "replies_received", "email": "mails"}
    for a in activities:
        dd = _day(a.get("occurred_at"))
        if not dd or not (start <= dd <= end) or a.get("lead_id") not in ids:
            continue
        k = kinds.get(a.get("type"))
        if k:
            work[k] += 1
        if a.get("type") in ("call", "whatsapp", "message", "email"):
            contacted_days.setdefault(dd.isoformat(), set()).add(a.get("lead_id"))
    for day, who in contacted_days.items():
        if day in days:
            days[day]["contacted"] = len(who)

    def table(g):
        rows = sorted(g.values(), key=lambda r: -r["found"])
        for r in rows:
            r["hot_pct"], r["contacted_pct"], r["reply_rate"] = _pct(r["hot"], r["found"]), _pct(r["contacted"], r["found"]), _pct(r["replied"], r["contacted"])
        return rows

    by_source, by_type = table(groups["source"]), table(groups["client_type"])
    steps = [("found", "Leads found"), ("contacted", "Contacted"), ("phone", "Reached by phone / WhatsApp"),
             ("replied", "Replied"), ("meeting", "Meeting"), ("won", "Won")]
    funnel_rows = [{"key": k, "label": lbl, "count": funnel[k], "pct": _pct(funnel[k], funnel["found"])} for k, lbl in steps]
    todo = sum(v for k, v in stage_counts.items() if lead_status.STAGE_INFO.get(k, {}).get("group") == "todo")
    res = {
        "period": {"from": start.isoformat(), "to": end.isoformat(), "days": (end - start).days + 1},
        "filters": {"client_type": ctype, "band": band, "source": source},
        "funnel": funnel_rows, "work": work, "by_day": list(days.values()) if len(days) <= 120 else [],
        "by_source": by_source[:15], "by_client_type": by_type,
        "next_steps": [{**lead_status.STAGE_INFO[k], "count": stage_counts.get(k, 0)} for k in lead_status.STAGE_IDS if stage_counts.get(k)],
        "todo": todo,
        "options": {"client_types": [{"id": k, "label": v} for k, v in CLIENT_TYPES.items()],
                    "sources": sorted({source_family(l) for l in leads})},
    }
    res["highlights"] = highlights(res)
    return res


def highlights(r: Dict[str, Any]) -> List[str]:
    """Plain findings from the numbers - always available, no AI needed."""
    f = {x["key"]: x for x in r["funnel"]}
    out = []
    found = f["found"]["count"]
    if not found:
        return ["No leads were found in this period with these filters. Try a longer period or fewer filters."]
    out.append(f"{found:,} leads found in {r['period']['days']} days; {f['contacted']['pct']}% have been contacted "
               f"and {f['replied']['count']} replied.")
    not_phoned = next((x["count"] for x in r["next_steps"] if x["id"] == "call_after_mail"), 0)
    if not_phoned:
        out.append(f"{not_phoned:,} leads got a mail but were never called or WhatsApped, although they have a phone "
                   f"number. A short call after the mail gets it read - see Today > Mailed – now call.")
    if f["found"]["count"] and f["contacted"]["pct"] < 30:
        out.append(f"Only {f['contacted']['pct']}% of new leads were contacted. {r['todo']:,} of them are waiting on the to-do list.")
    srcs = [s for s in r["by_source"] if s["found"] >= 5]
    if srcs:
        best = max(srcs, key=lambda s: (s["hot_pct"], s["found"]))
        out.append(f"Best source for hot leads: {best['name']} ({best['hot_pct']}% hot of {best['found']}).")
        replied = [s for s in srcs if s["replied"]]
        if replied:
            top = max(replied, key=lambda s: (s["reply_rate"], s["replied"]))
            out.append(f"Most replies come from {top['name']} ({top['replied']} replies, {top['reply_rate']}% of contacted).")
        weak = [s for s in srcs if s["hot_pct"] == 0 and s["found"] >= 10]
        if weak:
            out.append(f"No hot leads from {', '.join(s['name'] for s in weak[:3])} - consider running them less often.")
    types = [t for t in r["by_client_type"] if t["name"] != CLIENT_TYPES["other"]]
    if types:
        top = max(types, key=lambda t: t["found"])
        out.append(f"Most leads are {top['name'].lower()} ({top['found']:,}).")
    other = next((t for t in r["by_client_type"] if t["name"] == CLIENT_TYPES["other"]), None)
    if other and other["found"] and _pct(other["found"], found) >= 30:
        out.append(f"{_pct(other['found'], found)}% of leads are not a fit (job seekers, agencies, directories).")
    return out


# ---------------------------------------------------------------------------------------------
# AI analysis of the numbers (optional; numbers only, never names, e-mails or phones)
# ---------------------------------------------------------------------------------------------
INSIGHT_SYSTEM = """You are the sales analyst of a small software and digital marketing agency in India.
You get one lead-generation report as JSON (numbers only). Write for the business owner in plain English:
first 3-5 short bullet findings with their numbers, then 3 concrete actions for this week, each starting with a verb.
Only use the numbers given; do not invent any. No markdown headings, no bold; plain lines starting with "- "."""


def _compact(r):
    return {k: r[k] for k in ("period", "filters", "funnel", "work", "by_client_type", "next_steps")} | {"by_source": r["by_source"][:8]}


def insight(report: Dict[str, Any], client=None, post=None) -> Dict[str, Any]:
    """{'text', 'by': 'ai'|'rules', 'note'} - never raises."""
    data = json.dumps(_compact(report), ensure_ascii=False)
    errors = []
    if os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN") or client is not None:
        try:
            if client is None:
                import anthropic
                client = anthropic.Anthropic()
            resp = client.beta.messages.create(
                model=os.getenv("AI_QUALIFY_MODEL", "claude-opus-5-5"), max_tokens=1200,
                betas=["server-side-fallback-2026-07-01"], fallbacks="default", output_config={"effort": "low"},
                system=INSIGHT_SYSTEM, messages=[{"role": "user", "content": data}])
            text = "".join(b.text for b in resp.content if b.type == "text").strip()
            if text:
                return {"text": text, "by": "ai", "note": ""}
        except Exception as e:  # noqa: BLE001
            errors.append(f"Claude: {e}")
    if (os.getenv("GEMINI_API_KEY") or "").strip():
        try:
            import requests
            from lead_quality import GEMINI_URL, GEMINI_MODEL, gemini_key
            body = {"contents": [{"role": "user", "parts": [{"text": f"{INSIGHT_SYSTEM}\n\n{data}"}]}],
                    "generationConfig": {"maxOutputTokens": 1200}}
            r = (post or requests.post)(GEMINI_URL.format(model=GEMINI_MODEL), json=body, timeout=40,
                                        headers={"x-goog-api-key": gemini_key(), "Content-Type": "application/json"})
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}")
            parts = (r.json().get("candidates") or [{}])[0].get("content", {}).get("parts", [])
            text = "".join(p.get("text", "") for p in parts if isinstance(p, dict)).strip()
            if text:
                return {"text": text, "by": "ai", "note": "; ".join(errors)}
        except Exception as e:  # noqa: BLE001
            errors.append(f"Gemini: {e}")
    return {"text": "\n".join(f"- {h}" for h in report.get("highlights", [])), "by": "rules", "note": "; ".join(errors)}

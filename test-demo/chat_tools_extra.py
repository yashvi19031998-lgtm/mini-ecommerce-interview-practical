"""More look-up tools for the in-app assistant (used by chat_ai with an AI key, and by the built-in
rules in chat_assistant without one): today's to-do, leads by next step, the Summary report for any period
and filters, the mail flow, one day's log, how the system works, and teaching it facts."""
import datetime
import os
from collections import Counter
from typing import Any, Dict

import assistant_knowledge as kb
import lead_status
import report_summary


def _s(v: Any) -> str:
    s = str(v if v is not None else "").strip()
    return "" if s.lower() in ("nan", "n/a", "none", "null") else s


def _today(ctx) -> datetime.date:
    try:
        return datetime.date.fromisoformat(ctx.get("today") or "")
    except ValueError:
        return datetime.date.today()


def _row(item: Dict[str, Any], step: str = "") -> Dict[str, Any]:
    """A table row (the app shows it; the AI provider sees it without e-mail / phone)."""
    return {"lead_id": item.get("id"), "company": item.get("name"), "email": item.get("email", ""),
            "phone": item.get("phone", ""), "location": "", "source": item.get("source", ""),
            "score": item.get("score"), "status": lead_status.STAGE_INFO.get(step, {}).get("label", step)}


def t_today_todo(ctx):
    """What to do today: count per to-do step and the best 3 leads of each."""
    res = lead_status.today(ctx["leads"], ctx.get("sent", []), ctx.get("acts", []), per_lane=3)
    lanes = [{"step": l["id"], "label": l["label"], "what_to_do": l["action"], "count": l["count"],
              "top": [{"lead_id": i["id"], "name": i["name"], "score": i["score"]} for i in l["items"]]} for l in res["lanes"]]
    others = {s["id"]: s["count"] for s in res["stages"] if s["group"] != "todo"}
    return {"todo_total": res["todo"], "lanes": lanes, "other_steps": others}


def t_leads_by_next_step(ctx, step, limit=10, band="", source=""):
    """Leads in one next step (call_after_mail, call_pending, replied, ...), best score first."""
    if step not in lead_status.STAGE_INFO:
        return {"error": f"unknown step; use one of {', '.join(lead_status.STAGE_IDS)}"}
    res = lead_status.stage_list(ctx["leads"], ctx.get("sent", []), ctx.get("acts", []), step,
                                 band=band or "all", source=source, limit=max(1, min(int(limit or 10), 25)))
    rows = [_row(i, step) for i in res["items"]]
    return {"step": res["stage"]["label"], "what_to_do": res["stage"]["action"], "total_matching": res["total"], "rows": rows}


def t_report(ctx, preset="", date_from="", date_to="", client_type="", band="", source=""):
    """The Summary report (funnel, work done, by client type / source, highlights) for a period and filters."""
    rep = report_summary.build(ctx["leads"], ctx.get("sent", []), ctx.get("acts", []),
                               {"preset": preset, "date_from": date_from, "date_to": date_to,
                                "client_type": client_type, "band": band, "source": source}, today=_today(ctx))
    by_day = [d for d in rep["by_day"] if d["found"] or d["contacted"]]
    return {"period": rep["period"], "filters": rep["filters"], "funnel": {f["label"]: f"{f['count']} ({f['pct']}%)" for f in rep["funnel"]},
            "work_done": rep["work"], "by_client_type": rep["by_client_type"], "top_sources": rep["by_source"][:8],
            "next_steps": {s["label"]: s["count"] for s in rep["next_steps"]}, "highlights": rep["highlights"],
            "days_with_activity": by_day[-31:]}


def _int_env(name, default):
    try:
        return int(os.getenv(name) or default)
    except ValueError:
        return default


def t_mail_flow(ctx, date_from="", date_to=""):
    """How the automatic mail works now: limits, schedule, sent per day, today's count, the queue."""
    today = _today(ctx)
    date_to = date_to or today.isoformat()
    date_from = date_from or (today - datetime.timedelta(days=6)).isoformat()
    per_day = Counter()
    for s in ctx.get("sent", []):
        d = _s(s.get("sent_at"))[:10]
        if date_from <= d <= date_to:
            per_day[d] += 1
    replies = sum(1 for a in ctx.get("acts", []) if a.get("type") == "reply" and date_from <= _s(a.get("occurred_at"))[:10] <= date_to)
    bounces = sum(1 for a in ctx.get("acts", []) if a.get("type") == "bounce" and date_from <= _s(a.get("occurred_at"))[:10] <= date_to)
    queue = lead_status.stage_list(ctx["leads"], ctx.get("sent", []), ctx.get("acts", []), "mail_pending", limit=5)
    st = ctx.get("settings") or {}
    cap = _int_env("MAX_EMAILS_PER_DAY", 50)
    sent_today = sum(1 for s in ctx.get("sent", []) if _s(s.get("sent_at"))[:10] == today.isoformat())
    return {
        "range": {"from": date_from, "to": date_to},
        "mails_sent_per_day": dict(sorted(per_day.items())), "mails_sent_in_range": sum(per_day.values()),
        "replies_in_range": replies, "bounces_in_range": bounces,
        "sent_today": sent_today, "daily_limit": cap, "left_today": max(0, cap - sent_today),
        "prospect_daily_limit": _int_env("MAX_PROSPECT_EMAILS_PER_DAY", 15),
        "min_ai_score_for_auto_mail": _int_env("MIN_AI_SCORE_FOR_AUTO_EMAIL", 7),
        "auto_send_setting": st.get("autoSendEmail"),
        "schedule": "GitHub 'Outreach Mail' job every hour at :45; the PC cron engine sends only Mon-Sat 10:00-19:00.",
        "in_queue_now": queue["total"], "next_in_queue": [{"lead_id": i["id"], "name": i["name"], "score": i["score"]} for i in queue["items"]],
        "mailed_but_not_called": lead_status.stage_list(ctx["leads"], ctx.get("sent", []), ctx.get("acts", []), "call_after_mail", limit=1)["total"],
    }


def t_day_log(ctx, date=""):
    """Everything on one day: new leads by source, mails, calls, WhatsApps, replies, scraper runs."""
    day = date or _today(ctx).isoformat()
    try:
        datetime.date.fromisoformat(day)
    except ValueError:
        return {"error": "date must be YYYY-MM-DD"}
    new = [l for l in ctx["leads"] if _s(l.get("first_seen_at"))[:10] == day]
    acts = Counter(a.get("type") for a in ctx.get("acts", []) if _s(a.get("occurred_at"))[:10] == day)
    runs = [r for r in ctx.get("runs", []) if _s(r.get("start_time"))[:10] == day]
    return {"date": day, "new_leads": len(new),
            "new_by_source": dict(Counter(report_summary.source_family(l) for l in new).most_common(10)),
            "new_hot": sum(1 for l in new if lead_status.band_of(l) == "hot"),
            "mails_sent": sum(1 for s in ctx.get("sent", []) if _s(s.get("sent_at"))[:10] == day),
            "activities": dict(acts), "scraper_runs": len(runs),
            "scraper_failures": sum(1 for r in runs if _s(r.get("status")).lower() == "failed")}


def t_how_it_works(ctx, question):
    """How the system works (flows, rules, schedules, screens) from the built-in guide and taught facts."""
    hits = kb.search(question, k=3)
    return {"sections": hits} if hits else {"sections": [], "note": "Nothing in the guide matches; answer from the data tools or say you do not know."}


def t_remember(ctx, fact):
    """Store a fact the owner teaches; it is used in every later answer."""
    return kb.remember(fact)


def _schema(props, required=()):
    return {"type": "object", "properties": props, "required": list(required)}


STEP_ENUM = list(lead_status.STAGE_IDS)
DATE = {"type": "string", "description": "YYYY-MM-DD"}
EXTRA_TOOLS = [
    {"name": "today_todo", "fn": t_today_todo,
     "description": "What to do today: the to-do steps (reply, follow-up due, call/WhatsApp, mailed-now-call, reply on post, no reply) with counts and top leads.",
     "schema": _schema({})},
    {"name": "leads_by_next_step", "fn": t_leads_by_next_step,
     "description": "List leads in one next step, best score first. Steps: " + ", ".join(STEP_ENUM),
     "schema": _schema({"step": {"type": "string", "enum": STEP_ENUM}, "limit": {"type": "integer"},
                        "band": {"type": "string", "enum": ["hot", "warm", "cold", "unscored"]}, "source": {"type": "string"}}, ["step"])},
    {"name": "report", "fn": t_report,
     "description": "Summary report for leads found in a period: funnel, work done, by client type and source, highlights. "
                    "preset: today, 7d, 30d, 90d, month, last_month, all - or date_from/date_to. client_type: it_project, hiring, digital, prospect, other.",
     "schema": _schema({"preset": {"type": "string"}, "date_from": DATE, "date_to": DATE,
                        "client_type": {"type": "string"}, "band": {"type": "string"}, "source": {"type": "string"}})},
    {"name": "mail_flow", "fn": t_mail_flow,
     "description": "How automatic mail works and what it did: schedule, limits, sent per day in a range (default last 7 days), today's count, the queue, mailed-but-not-called.",
     "schema": _schema({"date_from": DATE, "date_to": DATE})},
    {"name": "day_log", "fn": t_day_log,
     "description": "Everything that happened on one date: new leads by source, mails, calls, WhatsApps, replies, scraper runs.",
     "schema": _schema({"date": DATE})},
    {"name": "how_it_works", "fn": t_how_it_works,
     "description": "Explains how the system works: daily flow, mail flow, phone/WhatsApp, next steps, scores, follow-ups, screens, reports, AI keys.",
     "schema": _schema({"question": {"type": "string"}}, ["question"])},
    {"name": "remember", "fn": t_remember,
     "description": "Save a fact the owner asks you to remember (never passwords or keys).",
     "schema": _schema({"fact": {"type": "string"}}, ["fact"])},
]

"""WhatsApp desk: the day's WhatsApp list, sent one by one from your own WhatsApp (1-click, no bot).

Why not a bot: WhatsApp bans numbers that send automated messages to people who did not ask for them, and
the official API may only start chats with people who opted in. So the app picks who to message, writes the
text and opens WhatsApp with it typed; you press Send. That keeps the number safe.

queue():  'new'       leads with a phone number that never got a WhatsApp (mailed-but-not-called first,
                      then call-or-WhatsApp, then no-reply), best score first
          'followup'  one WhatsApp sent FOLLOWUP_AFTER_DAYS+ days ago, no reply since -> one short follow-up
          A lead gets at most 2 WhatsApps from this desk. Closed, not-a-fit and replied leads never appear.
mark_sent(): logs the WhatsApp (activity type "whatsapp") and plans a follow-up reminder.
Daily limit (WHATSAPP_DAILY_LIMIT, default 25) and office hours (Mon-Sat 10-19) keep it looking human.
"""
import datetime
import os
from typing import Any, Dict, List, Optional

import lead_status
import phone_kit

DAILY_LIMIT = max(1, min(int(os.getenv("WHATSAPP_DAILY_LIMIT", "25") or 25), 60))
FOLLOWUP_AFTER_DAYS = 3
MAX_PER_LEAD = 2
STAGE_ORDER = {"replied": 9, "call_after_mail": 0, "call_pending": 1, "followup_due": 2, "no_reply": 3, "waiting": 4,
               "mail_pending": 5}
SKIP_STAGES = {"closed", "not_fit", "replied"}


def _now(now=None) -> datetime.datetime:
    return now or datetime.datetime.now()


def in_office_hours(now=None) -> bool:
    now = _now(now)
    return now.weekday() < 6 and 10 <= now.hour < 19


def _wa_history(activities: List[Dict[str, str]]) -> Dict[str, Dict[str, Any]]:
    """lead_id -> {'count', 'last', 'reply'} for WhatsApps we sent and replies we got."""
    out: Dict[str, Dict[str, Any]] = {}
    for a in activities:
        lid = (a.get("lead_id") or "").strip()
        if not lid:
            continue
        when = lead_status._parse_ts(a.get("occurred_at") or a.get("created_at"))
        if not when:
            continue
        h = out.setdefault(lid, {"count": 0, "last": None, "reply": None})
        if a.get("type") == "whatsapp":
            h["count"] += 1
            if not h["last"] or when > h["last"]:
                h["last"] = when
        elif a.get("type") == "reply" and (not h["reply"] or when > h["reply"]):
            h["reply"] = when
    return out


def followup_text(lead: Dict[str, Any]) -> str:
    f = phone_kit._facts(lead)
    hi = f"Hi {f['person']}," if f["person"] else "Hi,"
    about = f' about "{f["title"]}"' if len(f["title"].split()) >= 3 and "|" not in f["title"] else ""
    return (f"{hi} just following up on my message{about}. If it is still open, I would be glad to help - "
            f"would a quick 10-minute call this week work? If not, no problem at all.")


def sent_today(activities, now=None) -> int:
    day = _now(now).strftime("%Y-%m-%d")
    return sum(1 for a in activities if a.get("type") == "whatsapp" and str(a.get("occurred_at") or "")[:10] == day)


def queue(leads, sent, activities, limit: int = 25, now=None) -> Dict[str, Any]:
    now = _now(now)
    ctx = lead_status.build_context(sent, activities)
    hist = _wa_history(activities)
    new, follow = [], []
    for lead in leads:
        phone = lead_status.phone_of(lead)
        if not phone or not phone_kit.whatsapp_link(phone):
            continue
        st = lead_status.stage_of(lead, ctx, now)
        stage = st["stage"]
        if stage in SKIP_STAGES:
            continue
        lid = lead_status.lead_id_of(lead)
        h = hist.get(lid, {"count": 0, "last": None, "reply": None})
        if h["count"] >= MAX_PER_LEAD:
            continue
        if h["count"] == 0:
            if stage not in STAGE_ORDER:
                continue
            kind, text = "new", phone_kit.template_kit(lead, mailed=st["last_contact_type"] in ("email_sent", "email"))["whatsapp"]
        else:
            if h["reply"] and h["last"] and h["reply"] > h["last"]:
                continue
            if not h["last"] or (now - h["last"]).days < FOLLOWUP_AFTER_DAYS:
                continue
            kind, text = "followup", followup_text(lead)
        item = {
            "id": lid, "kind": kind, "stage": stage,
            "stage_label": lead_status.STAGE_INFO.get(stage, {}).get("label", stage),
            "name": (lead_status._s(lead.get("company_name")) or lead_status._s(lead.get("full_name")) or "(no name)")[:160],
            "about": (lead_status._s(lead.get("ai_requirement")) or lead_status._s(lead.get("ai_summary"))
                      or lead_status._s(lead.get("description")))[:240],
            "phone": phone, "score": lead_status.lead_score(lead), "band": lead_status.band_of(lead),
            "source": lead_status._s(lead.get("source")).split("|")[-1].split("(")[0].strip()[:60],
            "found_at": lead_status._s(lead.get("first_seen_at"))[:10], "post": lead_status.post_link(lead),
            "last_whatsapp": h["last"].strftime("%Y-%m-%d") if h["last"] else "",
            "text": text,
        }
        (new if kind == "new" else follow).append(item)
    key = lambda i: (STAGE_ORDER.get(i["stage"], 8), -(i["score"] if i["score"] is not None else -1), i["found_at"])
    new.sort(key=key)
    follow.sort(key=key)
    done = sent_today(activities, now)
    lim = max(1, min(int(limit or 25), 200))
    return {"new": new[:lim], "followup": follow[:lim], "counts": {"new": len(new), "followup": len(follow)},
            "sent_today": done, "daily_limit": DAILY_LIMIT, "left_today": max(0, DAILY_LIMIT - done),
            "office_hours": in_office_hours(now)}


def mark_sent(lead: Dict[str, Any], text: str, kind: str, activities, now=None) -> Dict[str, Any]:
    """Logs one WhatsApp you sent and plans a reminder. Raises ValueError at the daily limit."""
    import followup_store
    if sent_today(activities, now) >= DAILY_LIMIT:
        raise ValueError(f"Daily WhatsApp limit of {DAILY_LIMIT} reached - more looks like spam to WhatsApp. "
                         f"The rest can go tomorrow.")
    summary = "WhatsApp follow-up sent" if kind == "followup" else "WhatsApp sent"
    act = followup_store.add_activity(lead["id"], "whatsapp", summary, details=str(text or "")[:2000],
                                      source="whatsapp desk", lead_name=lead.get("name", ""),
                                      lead_email=lead.get("email", ""))
    if kind != "followup":  # a reminder to check for an answer
        due = (_now(now) + datetime.timedelta(days=FOLLOWUP_AFTER_DAYS)).replace(hour=10, minute=0, second=0)
        try:
            followup_store.schedule_followup(lead["id"], due.strftime("%Y-%m-%d %H:%M:%S"),
                                             "Check for a WhatsApp answer; send the follow-up if none",
                                             lead_name=lead.get("name", ""), lead_email=lead.get("email", ""))
        except Exception:  # noqa: BLE001 - the message is logged; the reminder is a nice-to-have
            pass
    return act

"""Lead Status: one clear "what next" stage for every lead.

Built only from data that already exists (lead row, sent-mail log, follow-up activity log), so it is
always up to date and needs no extra column. Read-only, except mark_done() which logs one activity.

Stage order (the first one that matches wins):
  closed          WON / LOST / DISQUALIFIED, or they asked to stop
  replied         they answered and nobody has written back since       -> answer them
  followup_due    a follow-up you planned is due today or overdue        -> do the follow-up
  not_fit         AI says it is not a buyer (job seeker, other agency...) -> ignore
  waiting         mailed / called / messaged in the last WAIT_DAYS days  -> wait
  no_reply        contacted earlier, no answer                           -> follow up
  mail_pending    has a usable e-mail, never contacted                   -> auto-mail sends it
  call_pending    no usable e-mail but a phone number                    -> call / WhatsApp
  (call_after_mail sits before waiting: mailed, has a phone, never called -> call / WhatsApp)
  message_pending only reachable on the platform (Reddit, Freelancer...) -> message there
  old_post        only reachable on a post older than POST_FRESH_DAYS    -> too late, skip
  no_contact      nothing to contact them with
"""
import datetime
import os
import re
from typing import Any, Dict, List, Optional

from daily_leads_report import NOT_MAILABLE, _first_email, lead_score, score_band, BAND_IDS
from reports_engine import _parse_ts

WAIT_DAYS = int(os.getenv("LEAD_STATUS_WAIT_DAYS", "4") or 4)
# A Reddit / Freelancer / HN post older than this has usually been filled - a reply is too late.
POST_FRESH_DAYS = int(os.getenv("LEAD_STATUS_POST_FRESH_DAYS", "14") or 14)

STAGES = [
    # id, label, what to do, group (todo = your work, auto = the system does it, wait, done)
    ("replied", "Replied", "They answered - write back today", "todo"),
    ("followup_due", "Follow-up due", "A follow-up you planned is due", "todo"),
    ("call_pending", "Call / WhatsApp pending", "No e-mail - call or WhatsApp them", "todo"),
    ("call_after_mail", "Mailed - now call", "Mail sent; a call or WhatsApp makes sure it is read", "todo"),
    ("message_pending", "Message pending", "Reply on their post (Reddit, Freelancer, HN...)", "todo"),
    ("no_reply", "No reply - follow up", f"Contacted over {WAIT_DAYS} days ago, no answer", "todo"),
    ("mail_pending", "Mail pending", "Has an e-mail - auto-mail will send it", "auto"),
    ("waiting", "Waiting for reply", f"Contacted in the last {WAIT_DAYS} days", "wait"),
    ("old_post", "Post too old", f"Only reachable on a post older than {POST_FRESH_DAYS} days", "done"),
    ("no_contact", "No contact found", "No e-mail, phone or post to reply to", "done"),
    ("not_fit", "Not a fit", "Job seeker, agency or directory - skip", "done"),
    ("closed", "Closed", "Won, lost or asked to stop", "done"),
]
STAGE_IDS = [s[0] for s in STAGES]
STAGE_INFO = {s[0]: {"id": s[0], "label": s[1], "action": s[2], "group": s[3]} for s in STAGES}

NOT_FIT = {"irrelevant", "job_seeker", "service_provider", "job_board_or_directory"}
CLOSED_STATUSES = {"WON", "LOST", "DISQUALIFIED", "CLOSED", "NOT_INTERESTED"}
OUTBOUND = {"email_sent", "call", "whatsapp", "email", "meeting", "message"}
PLATFORMS = {
    "reddit": "Reddit", "freelancer_bid": "Freelancer.com", "hackernews": "Hacker News",
    "telegram": "Telegram", "website": "their website",
}
DONE_TYPES = {  # mark_done action -> (activity type, summary)
    "called": ("call", "Called"),
    "whatsapp": ("whatsapp", "Sent a WhatsApp message"),
    "messaged": ("message", "Replied on their post"),
    "mailed": ("email", "Sent an e-mail by hand"),
}


def _s(v: Any) -> str:
    v = str(v if v is not None else "").strip()
    return "" if v.lower() in ("nan", "n/a", "none", "null") else v


def lead_id_of(lead: Dict[str, Any]) -> str:
    return _s(lead.get("id") or lead.get("lead_id"))


def phone_of(lead: Dict[str, Any]) -> str:
    raw = _s(lead.get("mobile_number") or lead.get("phone") or lead.get("Phone"))
    first = re.split(r"[,;/|]", raw)[0].strip()
    return first if len(re.sub(r"\D", "", first)) >= 8 else ""


def whatsapp_link(phone: str) -> str:
    digits = re.sub(r"\D", "", phone)
    if len(digits) == 10:          # Indian mobile without country code
        digits = "91" + digits
    elif len(digits) == 11 and digits.startswith("0"):
        digits = "91" + digits[1:]
    return f"https://wa.me/{digits}" if len(digits) >= 11 else ""


def post_link(lead: Dict[str, Any]) -> str:
    url = _s(lead.get("source_url") or lead.get("url"))
    return url if url.startswith("http") else ""


def _wa_with_text(lead, phone, mailed):
    """wa.me link with a ready message (template, no AI call, so lists stay fast)."""
    if not phone:
        return ""
    import phone_kit
    return phone_kit.whatsapp_link(phone, phone_kit.template_kit(lead, mailed)["whatsapp"])


def build_context(sent: List[Dict[str, str]], activities: List[Dict[str, str]]) -> Dict[str, Any]:
    """Per lead: last outbound contact, last reply, pending follow-up due dates, asked-to-stop."""
    by_id: Dict[str, Dict[str, Any]] = {}
    by_email: Dict[str, Dict[str, Any]] = {}

    def slot(row):
        lid, em = _s(row.get("lead_id")), _s(row.get("lead_email")).lower()
        if lid:
            return by_id.setdefault(lid, {})
        if em:
            return by_email.setdefault(em, {})
        return None

    for a in activities:
        st = slot(a)
        if st is None:
            continue
        t = _s(a.get("type"))
        when = _parse_ts(a.get("occurred_at") or a.get("created_at"))
        if t == "followup":
            if _s(a.get("followup_status")) == "pending":
                due = _parse_ts(a.get("due_at"))
                if due and (not st.get("due") or due < st["due"]):
                    st["due"] = due
            continue
        if not when:
            continue
        st.setdefault("types", set()).add(t)  # every kind of contact this lead ever had
        if t in ("call", "whatsapp", "meeting") and when > st.get("phone", datetime.datetime.min):
            st["phone"] = when  # reached by phone: needed before a mailed lead counts as fully contacted
        if t in OUTBOUND and when > st.get("out", datetime.datetime.min):
            st["out"], st["out_type"] = when, t
        elif t == "reply" and when > st.get("reply", datetime.datetime.min):
            st["reply"] = when
        elif t in ("opted_out", "bounce"):
            st[t] = when
    sent_at: Dict[str, datetime.datetime] = {}
    for s in sent:
        em, when = _s(s.get("email")).lower(), _parse_ts(s.get("sent_at"))
        if em and when and when > sent_at.get(em, datetime.datetime.min):
            sent_at[em] = when
    return {"by_id": by_id, "by_email": by_email, "sent_at": sent_at}


def stage_of(lead: Dict[str, Any], ctx: Dict[str, Any], now: Optional[datetime.datetime] = None) -> Dict[str, Any]:
    """{'stage', 'last_contact', 'last_contact_type', 'due'} for one lead."""
    now = now or datetime.datetime.now()
    email = _first_email(lead)
    info = {**ctx["by_email"].get(email, {}), **ctx["by_id"].get(lead_id_of(lead), {})} if email else \
        dict(ctx["by_id"].get(lead_id_of(lead), {}))
    status = _s(lead.get("status") or lead.get("Status")).upper()
    em_stat = _s(lead.get("email_status") or lead.get("Email Status")).upper()

    out, out_type = info.get("out"), info.get("out_type", "")
    mailed = ctx["sent_at"].get(email) if email else None
    if not mailed and em_stat == "SENT":
        mailed = _parse_ts(lead.get("email_sent_at")) or datetime.datetime(2000, 1, 1)
    if mailed and (not out or mailed > out):
        out, out_type = mailed, "email_sent"
    res = {"last_contact": out.strftime("%Y-%m-%d %H:%M") if out and out.year > 2000 else ("yes" if out else ""),
           "last_contact_type": out_type, "due": info["due"].strftime("%Y-%m-%d") if info.get("due") else ""}

    if status in CLOSED_STATUSES or info.get("opted_out") or em_stat == "OPTED_OUT":
        return {**res, "stage": "closed"}
    reply = info.get("reply")
    if reply and (not out or reply > out) or (status == "REPLIED" and not reply):
        return {**res, "stage": "replied"}
    end_of_today = now.replace(hour=23, minute=59, second=59)
    if info.get("due") and info["due"] <= end_of_today:
        return {**res, "stage": "followup_due"}
    # A mail alone is often never read: a mailed lead with a phone number is only fully contacted after a
    # call or WhatsApp as well.
    if out and out_type in ("email_sent", "email") and phone_of(lead) and not info.get("phone")             and _s(lead.get("ai_category")).lower() not in NOT_FIT:
        return {**res, "stage": "call_after_mail"}
    if out:
        if out.year > 2000 and (now - out).days < WAIT_DAYS:
            return {**res, "stage": "waiting"}
        return {**res, "stage": "no_reply"}
    if status in ("CONTACTED", "EMAIL_SENT", "MEETING"):
        return {**res, "stage": "no_reply"}
    if _s(lead.get("ai_category")).lower() in NOT_FIT:
        return {**res, "stage": "not_fit"}
    if email and em_stat not in NOT_MAILABLE and not info.get("bounce"):
        return {**res, "stage": "mail_pending"}
    if phone_of(lead):
        return {**res, "stage": "call_pending"}
    if _s(lead.get("contact_channel")).lower() in PLATFORMS:
        found = _parse_ts(lead.get("posted_at")) or _parse_ts(lead.get("first_seen_at"))
        if found and (now - found).days > POST_FRESH_DAYS:
            return {**res, "stage": "old_post"}
        return {**res, "stage": "message_pending"}
    return {**res, "stage": "no_contact"}


def _matches(lead, band, source, q):
    if band != "all" and score_band(lead_score(lead)) != band:
        return False
    if source and _s(lead.get("source")).lower() != source.lower():
        return False
    if q:
        hay = " ".join(_s(lead.get(k)) for k in ("company_name", "full_name", "email", "mobile_number", "description",
                                                   "source", "location")).lower()
        if q.lower() not in hay:
            return False
    return True


def _check_band(band: str) -> str:
    band = str(band or "all").strip().lower()
    if band not in BAND_IDS:
        raise ValueError(f"Unknown score band '{band}'. Allowed: {', '.join(BAND_IDS)}.")
    return band


def summary(leads, sent, activities, band="all", source="", q="", now=None) -> Dict[str, Any]:
    """Count of leads per stage, plus the list of sources for the filter."""
    band = _check_band(band)
    ctx = build_context(sent, activities)
    counts = {s: 0 for s in STAGE_IDS}
    sources: Dict[str, int] = {}
    total = 0
    for lead in leads:
        src = _s(lead.get("source"))
        if src:
            sources[src] = sources.get(src, 0) + 1
        if not _matches(lead, band, source, q):
            continue
        counts[stage_of(lead, ctx, now)["stage"]] += 1
        total += 1
    stages = [{**STAGE_INFO[s], "count": counts[s]} for s in STAGE_IDS]
    todo = sum(counts[s] for s in STAGE_IDS if STAGE_INFO[s]["group"] == "todo")
    return {"stages": stages, "total": total, "todo": todo, "band": band, "wait_days": WAIT_DAYS,
            "sources": sorted(sources, key=lambda k: -sources[k])}


def stage_list(leads, sent, activities, stage, band="all", source="", q="", limit=300, now=None) -> Dict[str, Any]:
    """The leads in one stage, best score first, with the contact details needed to act."""
    stage = str(stage or "").strip().lower()
    if stage not in STAGE_INFO:
        raise ValueError(f"Unknown stage '{stage}'. Allowed: {', '.join(STAGE_IDS)}.")
    band = _check_band(band)
    ctx = build_context(sent, activities)
    items = []
    for lead in leads:
        if not _matches(lead, band, source, q):
            continue
        st = stage_of(lead, ctx, now)
        if st["stage"] != stage:
            continue
        phone = phone_of(lead)
        channel = _s(lead.get("contact_channel")).lower()
        items.append({
            "id": lead_id_of(lead),
            "name": (_s(lead.get("company_name")) or _s(lead.get("full_name")) or "(no name)")[:160],
            "person": _s(lead.get("full_name"))[:80],
            "about": (_s(lead.get("ai_requirement")) or _s(lead.get("ai_summary")) or _s(lead.get("description")))[:220],
            "email": _first_email(lead), "phone": phone,
            "whatsapp": _wa_with_text(lead, phone, stage == "call_after_mail"),
            "link": post_link(lead), "website": _s(lead.get("website"))[:200],
            "platform": PLATFORMS.get(channel, ""),
            "score": lead_score(lead), "source": _s(lead.get("source"))[:80],
            "found_at": _s(lead.get("first_seen_at"))[:10],
            "last_contact": st["last_contact"], "last_contact_type": st["last_contact_type"], "due": st["due"],
        })
    items.sort(key=lambda i: (i["score"] if i["score"] is not None else -1, i["found_at"]), reverse=True)
    return {"stage": STAGE_INFO[stage], "items": items[:max(1, min(int(limit or 300), 1000))], "total": len(items)}


# ---------------------------------------------------------------------------------------------
# Used by the lead list and the Today page
# ---------------------------------------------------------------------------------------------
BANDS = (("hot", 7, 10), ("warm", 4, 6), ("cold", 0, 3))


def band_of(lead: Dict[str, Any]) -> str:
    """hot (score 7-10), warm (4-6), cold (0-3) or unscored."""
    score = lead_score(lead)
    if score is None:
        return "unscored"
    return next(b for b, lo, hi in BANDS if lo <= score <= hi)


# Leads that are not worth contacting on any channel
_NO_CONTACT_STAGES = {"closed", "not_fit", "replied"}


def pending_channels(lead: Dict[str, Any], ctx: Dict[str, Any], stage: str) -> List[str]:
    """Channels not used yet for this lead: 'email' (usable address, never mailed), 'call' (phone, never
    called), 'whatsapp' (mobile number, never WhatsApped). Empty for closed / not-a-fit / replied leads."""
    if stage in _NO_CONTACT_STAGES:
        return []
    email = _first_email(lead)
    info = {**ctx["by_email"].get(email, {}), **ctx["by_id"].get(lead_id_of(lead), {})} if email else \
        dict(ctx["by_id"].get(lead_id_of(lead), {}))
    types = info.get("types", set())
    em_stat = _s(lead.get("email_status") or lead.get("Email Status")).upper()
    status = _s(lead.get("status") or lead.get("Status")).upper()
    out = []
    mailed = (email and email in ctx["sent_at"]) or em_stat == "SENT" or status == "EMAIL_SENT" or \
        bool(types & {"email_sent", "email"})
    if email and not mailed and em_stat not in NOT_MAILABLE and not info.get("bounce"):
        out.append("email")
    phone = phone_of(lead)
    if phone and not types & {"call", "meeting"}:
        out.append("call")
    if phone and whatsapp_link(phone) and "whatsapp" not in types:
        out.append("whatsapp")
    return out


def annotate(leads, sent, activities, now=None) -> List[Dict[str, Any]]:
    """Copies of the leads with next_action (a stage id), band, last_contact and pending channels added."""
    ctx = build_context(sent, activities)
    out = []
    for lead in leads:
        st = stage_of(lead, ctx, now)
        out.append({**lead, "next_action": st["stage"], "band": band_of(lead),
                    "last_contact": st["last_contact"], "followup_due": st["due"],
                    "pending": pending_channels(lead, ctx, st["stage"])})
    return out


TODO_STAGES = [s for s in STAGE_IDS if STAGE_INFO[s]["group"] == "todo"]


def today(leads, sent, activities, per_lane=5, now=None) -> Dict[str, Any]:
    """The Today page: count per stage and the best few leads of every to-do stage."""
    res = summary(leads, sent, activities, now=now)
    lanes = []
    for stage in TODO_STAGES:
        lst = stage_list(leads, sent, activities, stage, limit=per_lane, now=now)
        lanes.append({**STAGE_INFO[stage], "count": lst["total"], "items": lst["items"]})
    return {"stages": res["stages"], "todo": res["todo"], "total": res["total"], "lanes": lanes}

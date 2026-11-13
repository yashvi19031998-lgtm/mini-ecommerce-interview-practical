"""
In-app chat assistant ("Ask LeadsGen") - answers questions about the leads, scrapers, e-mails and
follow-ups from the app's own data. Read-only: it never changes a file or sends anything.

Two engines:
  rules   - always available, free: recognises the common questions (counts for a period, hot leads,
            e-mails sent, replies, follow-ups, scrapers, sources, lead lists with filters, company search)
            in English, Gujlish ("aaje ketla hot leads?") and Gujarati script.
  gemini  - only when GEMINI_API_KEY is set: questions the rules do not recognise are answered by Gemini
            from a small summary of the same data (it is told not to invent anything).

POST /api/chat  {"message": "..."}  ->  {"reply", "table"?, "suggestions", "engine"}
"""

import datetime
import json
import os
import re
from typing import Any, Callable, Dict, List, Optional

MAX_MESSAGE = 500
MAX_ROWS = 25

SUGGESTIONS_EN = ["How many new leads today?", "Hot leads this week", "Emails sent today",
                  "Which scraper works best?", "Leads in Ahmedabad without a website", "Follow-ups due"]
SUGGESTIONS_GU = ["Aaje ketla nava leads?", "Aa week na hot leads", "Aaje ketla mail gaya?",
                  "Kayo scraper saro che?", "Ahmedabad na website vagar na leads", "Follow-up baki"]

_GUJLISH = re.compile(r"\b(ketla|ketlu|ketli|aaje|aje|kale|gaikale|kaya|kayo|kai|kon|batav\w*|che|chhe|nathi|"
                      r"vagar|vina|ma|na|ni|nu|mahine|athvadiya|aa week|baki|shodh\w*|malya|gaya|aavya)\b", re.I)
_GUJ_SCRIPT = re.compile(r"[઀-૿]")

CITIES = ["ahmedabad", "surat", "vadodara", "baroda", "rajkot", "gandhinagar", "mumbai", "pune", "bengaluru",
          "bangalore", "hyderabad", "delhi", "noida", "gurgaon", "gurugram", "chennai", "kolkata", "indore",
          "jaipur", "chandigarh", "london", "dubai", "uae", "usa", "united states", "uk", "canada", "australia",
          "remote", "india", "gujarat", "maharashtra", "karnataka"]


def _lang(msg: str) -> str:
    return "gu" if (_GUJ_SCRIPT.search(msg) or _GUJLISH.search(msg)) else "en"


def _t(lang: str, en: str, gu: str) -> str:
    return gu if lang == "gu" else en


# ---------------------------------------------------------------------------
# Understanding the question
# ---------------------------------------------------------------------------
def _period(msg: str) -> Dict[str, str]:
    m = msg.lower()
    if re.search(r"\b(yesterday|kale|gaikale|gai kale)\b|ગઈકાલે|કાલે", m):
        return {"preset": "yesterday", "label_en": "yesterday", "label_gu": "gai kale"}
    if re.search(r"\b(today|aaje|aje|aaj)\b|આજે", m):
        return {"preset": "today", "label_en": "today", "label_gu": "aaje"}
    if re.search(r"\b(this week|week|7 days|last 7|athvadiya|athvadiye|saptah)\b|અઠવાડિય", m):
        return {"preset": "7d", "label_en": "in the last 7 days", "label_gu": "chhella 7 divas ma"}
    if re.search(r"\b(this month|month|30 days|mahine|mahina|maheene)\b|મહિન", m):
        return {"preset": "30d", "label_en": "in the last 30 days", "label_gu": "chhella 30 divas ma"}
    return {"preset": "all", "label_en": "in total", "label_gu": "kul"}


def _has(m: str, *patterns: str) -> bool:
    return any(re.search(p, m) for p in patterns)


def _intent(msg: str) -> str:
    m = msg.lower()
    if _has(m, r"\bhelp\b", r"\bmadad\b", r"what can you", r"su kari shake", r"^\s*(hi|hello|hey|namaste|kem cho)\b"):
        return "help"
    if _has(m, r"scraper", r"harvester", r"\bsources? (work|best)\b", r"સ્ક્રેપર"):
        return "scrapers"
    if _has(m, r"\bsource", r"kya thi", r"kyathi", r"where.*(leads|come)", r"ક્યાંથી", r"સોર્સ"):
        return "sources"
    if _has(m, r"follow.?up", r"followup", r"overdue", r"baki", r"ફોલો", r"બાકી"):
        return "followups"
    if _has(m, r"\brepl(y|ies|ied)\b", r"jawab", r"જવાબ", r"રિપ્લાય"):
        return "replies"
    if _has(m, r"bounce", r"બાઉન્સ"):
        return "bounces"
    if _has(m, r"\b(e-?mails?|mails?)\b", r"મેઇલ", r"મેલ", r"ઈમેલ", r"ઇમેઇલ") and \
            _has(m, r"sent|send|gaya|gayo|moklya|mokl|dispatch|ketla|how many", r"ગયા", r"મોકલ", r"કેટલા"):
        return "emails"
    list_words = _has(m, r"\b(show|list|give|display|find)\b", r"batav", r"shodh", r"aap\b", r"joi", r"બતાવ", r"શોધ")
    filters = _filters(m)
    if list_words or any(filters.get(k) for k in ("city", "no_website", "no_email", "with_email", "with_phone")):
        return "list"
    if _has(m, r"\bhot\b", r"garam", r"હોટ"):
        return "hot"
    if _has(m, r"\bleads?\b", r"\blead\b", r"લીડ"):
        return "leads_count"
    if _has(m, r"\b(company|about|details?|vigat)\b"):
        return "search"
    return "unknown"


def _filters(m: str) -> Dict[str, Any]:
    f: Dict[str, Any] = {}
    for c in CITIES:
        if re.search(r"\b" + re.escape(c) + r"\b", m):
            f["city"] = c
            break
    if _has(m, r"(no|without|vagar|vina|nathi)\W+(a\W+)?website", r"website\W+(vagar|vina|nathi|na hoy)",
            r"વેબસાઇટ\s*(વગર|વિના)"):
        f["no_website"] = True
    if _has(m, r"(no|without|vagar|vina)\W+(an?\W+)?e-?mail", r"e-?mail\W+(vagar|vina|nathi)"):
        f["no_email"] = True
    elif _has(m, r"(with|vala|wala|sathe)\W+e-?mail", r"e-?mail\W+(vala|wala|che|hoy)", r"has e-?mail"):
        f["with_email"] = True
    if _has(m, r"(with|vala|wala)\W+(phone|mobile|number|whatsapp)", r"(phone|mobile|whatsapp)\W+(vala|wala)"):
        f["with_phone"] = True
    if _has(m, r"\bhot\b", r"garam", r"હોટ"):
        f["hot"] = True
    return f


# ---------------------------------------------------------------------------
# Answers from the data
# ---------------------------------------------------------------------------
def _score(lead: Dict[str, Any]) -> float:
    try:
        return float(lead.get("ai_score") or 0)
    except (TypeError, ValueError):
        return 0.0


def _real(v: Any) -> bool:
    s = str(v or "").strip()
    return bool(s) and s.upper() != "N/A"


def _lead_rows(leads: List[Dict[str, Any]]) -> Dict[str, Any]:
    cols = ["lead_id", "company", "email", "phone", "location", "source", "score", "status"]
    rows = []
    for l in leads[:MAX_ROWS]:
        rows.append({
            "lead_id": l.get("lead_id") or l.get("id", ""),
            "company": str(l.get("company_name") or l.get("Company Name") or "")[:80],
            "email": str(l.get("email") or "").split(",")[0].strip(),
            "phone": str(l.get("mobile_number") or "").split(",")[0].strip(),
            "location": str(l.get("location") or "")[:40],
            "source": str(l.get("source") or "").split("|")[0].split(" (")[0].strip(),
            "score": l.get("ai_score", ""),
            "status": l.get("status") or l.get("Status", ""),
        })
    return {"columns": cols, "rows": rows}


def _cards(ctx: Dict[str, Any], preset: str) -> Dict[str, int]:
    import reports_engine as r
    s = r.summary(ctx["leads"], ctx["runs"], ctx["acts"], ctx["sent"], {"preset": preset}, now=ctx.get("now"))
    return {c["key"]: c["value"] for c in s["cards"]}


def _rules_answer(msg: str, ctx: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    import reports_engine as r
    lang = _lang(msg)
    intent = _intent(msg)
    p = _period(msg)
    when = p["label_gu"] if lang == "gu" else p["label_en"]
    m = msg.lower()

    if intent == "help":
        return {"reply": _t(lang,
                "I can answer questions about your leads, e-mails, follow-ups and scrapers. Try one of these:",
                "Hu tamara leads, mail, follow-up ane scrapers vishe jawab aapi shaku. Aa puchho:"),
                "suggestions": SUGGESTIONS_GU if lang == "gu" else SUGGESTIONS_EN}

    if intent in ("leads_count", "hot", "emails", "replies"):
        c = _cards(ctx, p["preset"])
        if intent == "leads_count":
            if p["preset"] == "all":
                return {"reply": _t(lang, f"There are {c['total_leads']:,} leads in total.",
                                    f"Kul {c['total_leads']:,} leads che.")}
            return {"reply": _t(lang, f"{c['new_leads']:,} new leads {when} (total {c['total_leads']:,}).",
                                f"{when.capitalize()} {c['new_leads']:,} nava leads aavya (kul {c['total_leads']:,}).")}
        if intent == "hot":
            hot = sorted((l for l in ctx["leads"] if _score(l) >= 7 and _in_period(l, p["preset"], ctx)),
                         key=_score, reverse=True)
            return {"reply": _t(lang, f"{len(hot):,} hot leads (AI score 7+) {when}.",
                                f"{when.capitalize()} {len(hot):,} hot leads (AI score 7+) che."),
                    "table": _lead_rows(hot) if hot else None}
        if intent == "emails":
            return {"reply": _t(lang, f"{c['emails_sent']:,} e-mails sent {when}.",
                                f"{when.capitalize()} {c['emails_sent']:,} mail gaya.")}
        return {"reply": _t(lang, f"{c['replied']:,} replies {when}.", f"{when.capitalize()} {c['replied']:,} reply aavya.")}

    if intent == "bounces":
        n = sum(1 for a in ctx["acts"] if a.get("type") == "bounce" and _act_in_period(a, p["preset"], ctx))
        return {"reply": _t(lang, f"{n} e-mails bounced {when}.", f"{when.capitalize()} {n} mail bounce thaya.")}

    if intent == "followups":
        fw = r.followup_watchlist(ctx["leads"], ctx["acts"], ctx["sent"], None, ctx.get("settings") or {}, quiet_days=5)
        counts = fw["counts_by_reason"]
        names = {"overdue_followup": ("overdue", "samay vitel"), "replied_no_answer": ("replied, not answered", "reply aavyo, jawab baki"),
                 "due_today": ("due today", "aaje karvana"), "sequence_due": ("sequence step due", "sequence nu step baki"),
                 "meeting_no_next_step": ("meeting without next step", "meeting pachhi next step nathi"),
                 "contacted_gone_quiet": ("contacted, no answer for 5+ days", "mail gayo, 5+ divas thi jawab nathi"),
                 "hot_never_contacted": ("hot lead never contacted", "hot lead ne haju contact nathi karyo"),
                 "stale_open": ("old lead still open", "junu lead haju khulu"), "needs_review": ("needs review", "jovanu baki")}
        parts = [f"{(names.get(k, (k, k))[1] if lang == 'gu' else names.get(k, (k, k))[0])}: {v}"
                 for k, v in sorted(counts.items(), key=lambda kv: -kv[1]) if v]
        reply = _t(lang, f"{fw['total']} leads need attention.", f"{fw['total']} leads par dhyan aapvanu che.")
        if parts:
            reply += " " + "; ".join(parts) + "."
        reply += _t(lang, " Full list: Reports -> Follow-up Watchlist.", " Puri yadi: Reports -> Follow-up Watchlist.")
        return {"reply": reply}

    if intent == "scrapers":
        preset = p["preset"] if p["preset"] != "all" else "7d"
        sc = r.scraper_report(ctx["runs"], {"preset": preset}, now=ctx.get("now"))
        rows = [{"scraper": s["script_name"], "runs": s["times_run"], "records": s["records_collected"],
                 "new_leads": s["new_leads_added"], "failed": s["failed"]} for s in sc["scrapers"][:MAX_ROWS]]
        if not rows:
            return {"reply": _t(lang, "No scraper ran in that period.", "Te samay ma koi scraper chalyo nathi.")}
        best = rows[0]
        label = when if p["preset"] != "all" else _t(lang, "in the last 7 days", "chhella 7 divas ma")
        return {"reply": _t(lang, f"Best scraper {label}: {best['scraper']} ({best['new_leads']} new leads from "
                                  f"{best['records']} records).",
                            f"{label.capitalize()} sauthi saro scraper: {best['scraper']} ({best['records']} records "
                            f"mathi {best['new_leads']} nava leads)."),
                "table": {"columns": ["scraper", "runs", "records", "new_leads", "failed"], "rows": rows}}

    if intent == "sources":
        src = r.source_report_rows(ctx["leads"], ctx["acts"], {"preset": p["preset"]}, now=ctx.get("now"))
        rows = [{"source": s["source"], "leads": s["leads"], "hot": s["hot"], "with_contact_pct": s["with_contact_pct"]}
                for s in src["rows"][:MAX_ROWS]]
        if not rows:
            return {"reply": _t(lang, "No leads in that period.", "Te samay ma koi lead nathi.")}
        top = rows[0]
        return {"reply": _t(lang, f"Top source {when}: {top['source']} ({top['leads']} leads, {top['hot']} hot).",
                            f"{when.capitalize()} sauthi vadhu leads {top['source']} thi ({top['leads']} leads, {top['hot']} hot)."),
                "table": {"columns": ["source", "leads", "hot", "with_contact_pct"], "rows": rows}}

    if intent == "list":
        f = _filters(m)
        found = [l for l in ctx["leads"] if _in_period(l, p["preset"], ctx) and _matches(l, f)]
        found.sort(key=_score, reverse=True)
        desc = _describe(f, lang)
        if not found:
            return {"reply": _t(lang, f"No leads found{desc} {when}.", f"{when.capitalize()}{desc} koi lead nathi malyo.")}
        more = _t(lang, f" Showing the top {MAX_ROWS}.", f" Upar na {MAX_ROWS} batavu chhu.") if len(found) > MAX_ROWS else ""
        return {"reply": _t(lang, f"{len(found):,} leads{desc} {when}.{more}",
                            f"{when.capitalize()}{desc} {len(found):,} leads malya.{more}"),
                "table": _lead_rows(found)}

    if intent == "search":
        q = re.sub(r"\b(company|about|details?|vigat|of|for|ni|nu|na|show|batav\w*)\b", " ", m)
        q = " ".join(w for w in q.split() if len(w) > 2)
        if q:
            hits = [l for l in ctx["leads"] if q in str(l.get("company_name") or "").lower() or q in str(l.get("email") or "").lower()]
            if hits:
                return {"reply": _t(lang, f"{len(hits)} matching leads.", f"{len(hits)} leads malya."), "table": _lead_rows(hits)}
    return None


def _matches(l: Dict[str, Any], f: Dict[str, Any]) -> bool:
    if f.get("city") and f["city"] not in str(l.get("location") or "").lower() + " " + str(l.get("description") or "").lower()[:300]:
        return False
    if f.get("no_website") and _real(l.get("website")):
        return False
    if f.get("no_email") and _real(l.get("email")):
        return False
    if f.get("with_email") and not _real(l.get("email")):
        return False
    if f.get("with_phone") and not _real(l.get("mobile_number")):
        return False
    if f.get("hot") and _score(l) < 7:
        return False
    return True


def _describe(f: Dict[str, Any], lang: str) -> str:
    bits = []
    if f.get("hot"):
        bits.append(_t(lang, "hot", "hot"))
    if f.get("city"):
        bits.append(_t(lang, f"in {f['city'].title()}", f"{f['city'].title()} na"))
    if f.get("no_website"):
        bits.append(_t(lang, "without a website", "website vagar na"))
    if f.get("no_email"):
        bits.append(_t(lang, "without e-mail", "mail vagar na"))
    if f.get("with_email"):
        bits.append(_t(lang, "with e-mail", "mail vala"))
    if f.get("with_phone"):
        bits.append(_t(lang, "with phone", "phone vala"))
    return (" " + " ".join(bits)) if bits else ""


def _date_of(value: Any) -> Optional[datetime.date]:
    s = str(value or "").strip()[:10]
    try:
        return datetime.date.fromisoformat(s)
    except ValueError:
        return None


def _range(preset: str, ctx: Dict[str, Any]):
    today = (ctx.get("now") or datetime.datetime.now()).date()
    if preset == "today":
        return today, today
    if preset == "yesterday":
        y = today - datetime.timedelta(days=1)
        return y, y
    if preset == "7d":
        return today - datetime.timedelta(days=6), today
    if preset == "30d":
        return today - datetime.timedelta(days=29), today
    return None, None


def _in_period(l: Dict[str, Any], preset: str, ctx: Dict[str, Any]) -> bool:
    start, end = _range(preset, ctx)
    if start is None:
        return True
    d = _date_of(l.get("first_seen_at") or l.get("posted_at"))
    return d is not None and start <= d <= end


def _act_in_period(a: Dict[str, Any], preset: str, ctx: Dict[str, Any]) -> bool:
    start, end = _range(preset, ctx)
    if start is None:
        return True
    d = _date_of(a.get("occurred_at"))
    return d is not None and start <= d <= end


# ---------------------------------------------------------------------------
# Optional Gemini for questions the rules do not know
# ---------------------------------------------------------------------------
def _snapshot(ctx: Dict[str, Any]) -> Dict[str, Any]:
    import reports_engine as r
    snap = {"today": _cards(ctx, "today"), "last_7_days": _cards(ctx, "7d"), "all_time": _cards(ctx, "all")}
    try:
        snap["top_sources_all_time"] = [{k: s[k] for k in ("source", "leads", "hot")}
                                        for s in r.source_report_rows(ctx["leads"], ctx["acts"], {"preset": "all"})["rows"][:8]]
        snap["scrapers_last_7_days"] = [{k: s[k] for k in ("script_name", "times_run", "records_collected", "new_leads_added", "failed")}
                                        for s in r.scraper_report(ctx["runs"], {"preset": "7d"})["scrapers"][:10]]
    except Exception:
        pass
    return snap


def _gemini_answer(msg: str, ctx: Dict[str, Any], post=None) -> Optional[Dict[str, Any]]:
    key = (os.getenv("GEMINI_API_KEY") or "").strip()
    if not key:
        return None
    import requests
    post = post or requests.post
    model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
    prompt = ("You are the assistant inside LeadsGen AI, a lead-generation app of a software agency. Answer the "
              "owner's question ONLY from the JSON data below. If the data does not contain the answer, say so "
              "briefly and suggest a question you can answer. Never invent numbers, names or e-mail addresses. "
              "Reply in the same language and script as the question (English, Gujarati, or Gujarati written in "
              "English letters). At most 4 short sentences.\n\nDATA:\n"
              + json.dumps(_snapshot(ctx), ensure_ascii=False) + "\n\nQUESTION:\n" + msg)
    try:
        resp = post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                    json={"contents": [{"role": "user", "parts": [{"text": prompt}]}],
                          "generationConfig": {"maxOutputTokens": 400}},
                    headers={"x-goog-api-key": key, "Content-Type": "application/json"}, timeout=30)
        if resp.status_code != 200:
            return None
        parts = resp.json()["candidates"][0]["content"]["parts"]
        text = "".join(p.get("text", "") for p in parts if isinstance(p, dict)).strip()
    except Exception:
        return None
    return {"reply": text[:1200], "engine": "gemini"} if text else None


# ---------------------------------------------------------------------------
def answer(message: Any, load_context: Callable[[], Dict[str, Any]], gemini_post=None) -> Dict[str, Any]:
    msg = " ".join(str(message or "").split())
    if not msg:
        raise ValueError("Type a question.")
    if len(msg) > MAX_MESSAGE:
        raise ValueError(f"Keep the question under {MAX_MESSAGE} characters.")
    ctx = load_context()
    lang = _lang(msg)
    res = _rules_answer(msg, ctx)
    if res is not None:
        res.setdefault("engine", "rules")
    else:
        res = _gemini_answer(msg, ctx, post=gemini_post)
        if res is None:
            res = {"reply": _t(lang,
                   "I didn't understand that yet. I can answer questions like these:",
                   "Aa savaal hu haju samjto nathi. Aava savalo puchho:"), "engine": "rules"}
            res["suggestions"] = SUGGESTIONS_GU if lang == "gu" else SUGGESTIONS_EN
    res.setdefault("suggestions", [])
    res.setdefault("table", None)
    return res

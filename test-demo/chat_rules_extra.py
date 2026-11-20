"""Built-in answers that need no AI key: teach / forget facts, today's to-do, leads by next step, the mail
flow, a report for any period or dates, one day's log, and "how does X work" from the built-in guide.
chat_assistant._rules_answer() calls answer() first; None means "not one of these questions"."""
import datetime
import re
from typing import Any, Dict, Optional, Tuple

import assistant_knowledge as kb
import chat_tools_extra as tools

MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
_MON = r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*"


def _date_at(text: str, today: datetime.date) -> list:
    """Every date in the text, in order: 2026-11-10, 10/11/2026, 10-11, 10 nov, nov 10."""
    found = []
    for m in re.finditer(rf"(\d{{4}})-(\d{{1,2}})-(\d{{1,2}})|(\d{{1,2}})[/.](\d{{1,2}})(?:[/.](\d{{2,4}}))?|(\d{{1,2}})(?:st|nd|rd|th)?\s+{_MON}|{_MON}\s+(\d{{1,2}})", text):
        try:
            if m.group(1):
                d = datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            elif m.group(4):
                y = int(m.group(6)) if m.group(6) else today.year
                d = datetime.date(y + 2000 if y < 100 else y, int(m.group(5)), int(m.group(4)))  # day/month (India)
            elif m.group(7):
                d = datetime.date(today.year, MONTHS[m.group(8)[:3]], int(m.group(7)))
            else:
                d = datetime.date(today.year, MONTHS[m.group(9)[:3]], int(m.group(10)))
        except (ValueError, KeyError, TypeError):
            continue
        if d > today and not m.group(1) and not (m.group(6)):
            d = d.replace(year=d.year - 1)  # "10 dec" asked in November means last December
        found.append((m.start(), d))
    return [d for _, d in sorted(found)]


def dates(text: str, today: datetime.date) -> Tuple[Optional[str], Optional[str]]:
    """(date_from, date_to) from the question; a single date counts as from that date to today,
    unless it is clearly one day ("on 10 nov", "10 nov na divse")."""
    ds = _date_at(text.lower(), today)
    if not ds:
        return None, None
    if len(ds) >= 2:
        a, b = sorted(ds[:2])
        return a.isoformat(), b.isoformat()
    return ds[0].isoformat(), (ds[0].isoformat() if re.search(r"\bon\b|\bna divse\b|\bdivse\b|\bthat day\b", text.lower()) else today.isoformat())


def _preset(text: str) -> str:
    m = text.lower()
    for pat, p in ((r"\b(today|aaje|aje|aaj)\b", "today"), (r"last month|gaya mahin|pachhla mahin", "last_month"),
                   (r"this month|aa mahin", "month"), (r"\b(week|7 days|athvadi)", "7d"), (r"\b90 days|3 months|3 mahin", "90d"),
                   (r"\b(30 days|month|mahin)", "30d"), (r"\b(all time|total|kul|badha)\b", "all")):
        if re.search(pat, m):
            return p
    return ""


CLIENT_WORDS = {"digital": r"digital|seo|marketing|ads", "hiring": r"hiring|developer job|hire", "it_project": r"\bit\b|project|software|app",
                "prospect": r"prospect|business"}


def _has(m, *p):
    return any(re.search(x, m) for x in p)


def answer(msg: str, ctx: Dict[str, Any], lang: str) -> Optional[Dict[str, Any]]:
    m = msg.lower().strip()
    today = datetime.date.fromisoformat(ctx.get("today") or datetime.date.today().isoformat())
    gu = lang == "gu"

    def t(en, g):
        return g if gu else en

    # Teach / forget / list
    taught = re.match(r"^\s*(?:please\s+)?(?:remember|yaad\s*rakh(?:jo|je)?|yad\s*rakh(?:jo|je)?|note\s*kar(?:i\s*le)?)\s*[:,-]?\s*(.+)$", msg, re.I)
    if taught:
        try:
            r = kb.remember(taught.group(1))
        except ValueError as e:
            return {"reply": str(e)}
        return {"reply": t(f"Got it, I will remember that. ({r['count']} facts saved.)", f"Saru, aa yaad rakhish. (kul {r['count']} vato yaad che.)")}
    gone = re.match(r"^\s*(?:forget|bhuli\s*ja|bhuli\s*jaa)\s*(\d+)", m)
    if gone:
        try:
            f = kb.forget(int(gone.group(1)))
        except ValueError as e:
            return {"reply": str(e)}
        return {"reply": t(f"Forgotten: {f['text']}", f"Bhuli gayo: {f['text']}")}
    if _has(m, r"what do you remember", r"shu yaad", r"su yaad", r"yaad che", r"taught you", r"memory"):
        facts = kb.load()["facts"]
        if not facts:
            return {"reply": t("You have not taught me anything yet. Say 'remember: ...' to teach me a fact.",
                               "Haju tame mane kai shikhvadyu nathi. 'yaad rakh: ...' lakho.")}
        return {"reply": t("This is what you taught me:\n", "Tame shikhvadeli vato:\n") + "\n".join(f"{i}. {f['text']}" for i, f in enumerate(facts, 1))}

    d_from, d_to = dates(msg, today)

    # One day
    if (d_from and d_from == d_to) or (_has(m, r"what happened", r"shu thayu", r"su thayu", r"\blog\b") and (d_from or _has(m, r"today|aaje|yesterday|kale"))):
        day = d_from or (today - datetime.timedelta(days=1) if _has(m, r"yesterday|gai ?kale|\bkale\b") else today).isoformat()
        r = tools.t_day_log(ctx, date=str(day))
        acts = r["activities"]
        return {"reply": t(
            f"{r['date']}: {r['new_leads']} new leads ({r['new_hot']} hot), {r['mails_sent']} mails sent, "
            f"{acts.get('call', 0)} calls, {acts.get('whatsapp', 0)} WhatsApps, {acts.get('reply', 0)} replies, "
            f"{r['scraper_runs']} scraper runs ({r['scraper_failures']} failed).",
            f"{r['date']}: {r['new_leads']} nava leads ({r['new_hot']} hot), {r['mails_sent']} mail gaya, "
            f"{acts.get('call', 0)} call, {acts.get('whatsapp', 0)} WhatsApp, {acts.get('reply', 0)} reply, "
            f"{r['scraper_runs']} scraper run ({r['scraper_failures']} fail)."),
            "table": {"columns": ["source", "new_leads"], "rows": [{"source": k, "new_leads": v} for k, v in r["new_by_source"].items()]} if r["new_by_source"] else None}

    # Mail flow
    if _has(m, r"mail ?flow", r"mail.*(kyare|when|limit|queue|kem|how|kevi|flow|schedule|rule)", r"(kyare|when).*mail", r"\bqueue\b", r"daily limit"):
        r = tools.t_mail_flow(ctx, date_from=d_from or "", date_to=d_to or "")
        days = ", ".join(f"{k[5:]}: {v}" for k, v in r["mails_sent_per_day"].items()) or t("none", "ek pan nahi")
        return {"reply": t(
            f"Mail flow: {r['schedule']} {'No daily limit' if r['daily_limit'] == 'no limit' else 'Limit ' + str(r['daily_limit']) + ' a day'} ({r['prospect_daily_limit']} a day for prospects), "
            f"minimum AI score {r['min_ai_score_for_auto_mail']}. Today {r['sent_today']} sent{'' if r['left_today'] == 'no limit' else ', ' + str(r['left_today']) + ' left'}. "
            f"{r['in_queue_now']} leads are in the queue. {r['range']['from']} to {r['range']['to']}: {r['mails_sent_in_range']} sent "
            f"({days}), {r['replies_in_range']} replies, {r['bounces_in_range']} bounces. "
            f"{r['mailed_but_not_called']} mailed leads have a phone but were never called - call or WhatsApp them (Today > Mailed – now call).",
            f"Mail flow: {r['schedule']} {'Roj ni koi limit nathi' if r['daily_limit'] == 'no limit' else 'Roj ni limit ' + str(r['daily_limit'])} ({r['prospect_daily_limit']} prospect mate), "
            f"AI score ochha ma ochho {r['min_ai_score_for_auto_mail']}. Aaje {r['sent_today']} gaya{'' if r['left_today'] == 'no limit' else ', ' + str(r['left_today']) + ' baki'}. "
            f"Queue ma {r['in_queue_now']} leads che. {r['range']['from']} thi {r['range']['to']}: {r['mails_sent_in_range']} mail ({days}), "
            f"{r['replies_in_range']} reply, {r['bounces_in_range']} bounce. {r['mailed_but_not_called']} leads ne mail gayo pan phone nathi thayo - "
            f"Today > Mailed – now call ma thi call/WhatsApp karo.")}

    # To-do
    if _has(m, r"what should i do", r"shu karu", r"su karu", r"su karvanu", r"shu karvanu", r"\bto-?do\b", r"aaje.*kaam", r"today.*(work|do)"):
        r = tools.t_today_todo(ctx)
        lines = [f"{l['label']}: {l['count']}" + (f" (best: {', '.join(x['name'][:40] for x in l['top'][:2])})" if l["top"] else "")
                 for l in r["lanes"] if l["count"]]
        return {"reply": t(f"{r['todo_total']} leads need you today:\n", f"Aaje {r['todo_total']} leads tamari rah jue che:\n") + "\n".join(lines)
                + t("\nOpen Today to work through them.", "\nToday page kholi ne ek ek kari ne karo.")}

    # "Why / how does / explain" questions are about the system, not counts: answer from the guide
    if re.match(r"^\s*(why|how (does|do|is|are|can|to)|what (is|are|does) (a |an |the )?(lead|step|score|hot|flow|report|outcome)|explain|where)\b", m) \
            or re.search(r"\b(kem|kevi rite|samjav)", m):
        g = guide(msg)
        if g:
            return g

    # Leads by next step
    steps = [(r"mailed.*call|mail.*(pan|but).*call|call nathi", "call_after_mail"), (r"\b(call|phone|whatsapp)\b", "call_pending"),
             (r"reply on post|post par|reddit|freelancer", "message_pending"), (r"no reply|reply nathi|javab nathi", "no_reply"),
             (r"follow.?up due|followup baki", "followup_due"), (r"repl(y|ied) now|reply aavyo|reply aavya", "replied"),
             (r"in (the )?queue|queue ma", "mail_pending")]
    if _has(m, r"\b(show|list|which|kon|kaya|batav|give)\b", r"leads?\b"):
        for pat, step in steps:
            if re.search(pat, m):
                band = next((b for b in ("hot", "warm", "cold") if re.search(rf"\b{b}\b", m)), "")
                r = tools.t_leads_by_next_step(ctx, step, limit=15, band=band)
                return {"reply": t(f"{r['total_matching']} leads: {r['step']} - {r['what_to_do']}.",
                                   f"{r['total_matching']} leads: {r['step']} - {r['what_to_do']}."),
                        "table": {"columns": ["lead_id", "company", "email", "phone", "source", "score", "status"], "rows": r["rows"]} if r["rows"] else None}

    # Report for a period / dates / client type
    if _has(m, r"report", r"summary", r"saransh", r"hisab", r"performance", r"kevu chalyu", r"how (are|did) we"):
        ctype = next((k for k, p in CLIENT_WORDS.items() if re.search(p, m)), "")
        band = next((b for b in ("hot", "warm", "cold") if re.search(rf"\b{b}\b", m)), "")
        r = tools.t_report(ctx, preset="" if d_from else (_preset(msg) or "30d"), date_from=d_from or "", date_to=d_to or "",
                           client_type=ctype, band=band)
        f = r["funnel"]
        head = t(f"Report {r['period']['from']} to {r['period']['to']}", f"Report {r['period']['from']} thi {r['period']['to']}")
        if ctype or band:
            head += f" ({', '.join(x for x in (ctype, band) if x)})"
        return {"reply": head + ":\n" + "\n".join(f"{k}: {v}" for k, v in f.items()) + "\n\n" + "\n".join(f"- {h}" for h in r["highlights"])
                + t("\n\nFull report with charts: Reports > Summary.", "\n\nAakho report chart sathe: Reports > Summary.")}

    return None


def guide(msg: str) -> Optional[Dict[str, Any]]:
    """'How does X work' from the built-in guide - asked only when no data rule matched."""
    m = msg.lower()
    if _has(m, r"\b(how|why|where|what is|what are|explain)\b", r"\bkem\b", r"kevi rite", r"shu che", r"su che", r"samjav", r"kya (che|male)", r"kyare", r"\bflow\b"):
        hits = kb.search(msg, k=2)
        if hits:
            return {"reply": "\n\n".join(f"{h['title']}: {h['text']}" for h in hits)}
    return None

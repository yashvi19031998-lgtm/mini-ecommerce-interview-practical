"""AI engine for the in-app chat: answers any question about the owner's own data.

The model never sees the whole database. It calls small read-only tools (find leads, count/group leads,
e-mail / reply stats, scraper stats, one lead's details, app overview) and answers only from what the
tools return, so numbers and names are real. Claude is used when ANTHROPIC_API_KEY is set, otherwise
Gemini (GEMINI_API_KEY, free tier). Without a key, chat_assistant falls back to its keyword rules.
"""
import datetime
import json
import os
import re
from collections import Counter
from typing import Any, Callable, Dict, List, Optional

MAX_TOOL_ROUNDS = 6
MAX_ROWS = 25
CLAUDE_MODEL = os.getenv("CHAT_AI_MODEL", "claude-opus-5-5")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
NOT_MAILABLE = {"INVALID", "INVALID_DOMAIN", "UNVERIFIABLE", "EXCLUDED_COMPANY", "BOUNCED", "OPTED_OUT"}

SYSTEM = """You are the assistant inside LeadsGen AI, the lead-generation app of Sangeeta Infotech (a software and \
digital-marketing agency in Ahmedabad). The owner asks you about their own data: leads, scores, e-mails sent, \
replies, follow-ups, scrapers and sources.

Rules:
- Use the tools to look things up. Answer only from tool results; never invent numbers, names, e-mails or dates.
  If the tools cannot answer it, say so in one line and say what you can answer instead.
- For "how many" questions use count_leads; for "show / list / which / top" questions use find_leads.
- Dates: today is {today}. "This week" = last 7 days, "this month" = from the 1st of this month.
- Reply in the same language and script as the question: English, Gujarati, or Gujarati written in English
  letters ("Aaje ketla leads aavya?" -> answer in that style). Be short: a direct answer first, then at most a
  few lines. Do not paste long lists - the app shows the rows of the last find_leads call as a table.
- Plain text only: no markdown (no **, #, tables); a short numbered list is fine.
- Score bands: hot 7-10, warm 4-6, cold 0-3. "Pending" = has an e-mail but no mail sent yet.
- Pick the right tool: "what should I do / aaje shu karu" -> today_todo; leads waiting for a call, reply,
  follow-up etc. -> leads_by_next_step; a report, numbers for a period, how a source or client type performs ->
  report; anything about the mail flow, limits, when mails go, the queue -> mail_flow; "what happened on <date>"
  -> day_log; "how does X work / why / where do I find" -> how_it_works. Combine tools when the question needs it,
  and give a short analysis with a clear recommendation, not only numbers.
- Turn dates in any form ("10 nov", "10/11", "last Monday", "from 1st to 15th") into YYYY-MM-DD yourself.
- When the owner says "remember ..." / "yaad rakh ..." call remember. Follow every taught fact below.

How the system works:
{knowledge}

{examples}"""

# ------------------------------------------------------------------ data helpers


def _s(v: Any) -> str:
    s = str(v if v is not None else "").strip()
    return "" if s.lower() in ("nan", "n/a", "none") else s


def _email(l):
    e = _s(l.get("email") or l.get("Email")).split(",")[0].strip().lower()
    return e if "@" in e else ""


def _score(l) -> Optional[int]:
    for k in ("ai_score", "intent_score"):
        try:
            return max(0, min(10, int(round(float(_s(l.get(k)))))))
        except ValueError:
            continue
    return None


def _band(sc):
    return "unscored" if sc is None else "high" if sc >= 7 else "medium" if sc >= 4 else "low"


def _date(v) -> str:
    m = re.match(r"(\d{4}-\d{2}-\d{2})", _s(v))
    return m.group(1) if m else ""


def _found(l) -> str:
    return _date(l.get("first_seen_at")) or _date(l.get("posted_at"))


def _mail_state(l, sent):
    e = _email(l)
    st = _s(l.get("email_status") or l.get("Email Status")).upper()
    if st == "SENT" or (e and e in sent):
        return "mailed"
    if not e:
        return "no_email"
    return "blocked" if st in NOT_MAILABLE else "pending"


def _company(l):
    return _s(l.get("company_name") or l.get("Company Name") or l.get("full_name"))


def _source(l):
    return _s(l.get("source") or l.get("Source")).split("|")[0].strip()


def _row(l, sent):
    return {"lead_id": _s(l.get("lead_id") or l.get("id")), "company": _company(l)[:90], "email": _email(l),
            "phone": _s(l.get("mobile_number") or l.get("Mobile Number")).split(",")[0].strip(),
            "location": _s(l.get("location"))[:40], "source": _source(l)[:50], "score": _score(l),
            "category": _s(l.get("ai_category")), "status": _s(l.get("status") or l.get("Status")) or "NEW",
            "mail": _mail_state(l, sent), "found": _found(l)}


PRIVATE = ("email", "phone", "mobile_number", "Email", "Mobile Number")


def _for_model(obj):
    """What the AI provider sees: contact details replaced by has_email / has_phone flags. The app shows the
    real e-mail / phone from its own data in the result table."""
    if isinstance(obj, list):
        return [_for_model(o) for o in obj]
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k in PRIVATE:
                if k in ("email", "Email"):
                    out["has_email"] = bool(v)
                else:
                    out["has_phone"] = bool(v)
            elif k in ("to", "lead") and isinstance(v, str) and "@" in v:
                out[k] = "(e-mail hidden)"
            else:
                out[k] = _for_model(v)
        return out
    return obj


def _sent_set(ctx):
    return {s["email"] for s in ctx.get("sent", []) if s.get("email")}


FILTER_PROPS = {
    "text": {"type": "string", "description": "Words to look for in company / title / requirement / description / tech"},
    "source": {"type": "string", "description": "Part of the source name, e.g. 'reddit', 'freelancer', 'job portal', 'google maps'"},
    "city": {"type": "string", "description": "Part of the location, e.g. 'Ahmedabad'"},
    "category": {"type": "string", "enum": ["client_project", "hiring_developer", "prospect_signal", "irrelevant",
                                            "service_provider", "job_seeker", "job_board_or_directory", "buyer"],
                 "description": "AI category. 'buyer' = client_project or hiring_developer"},
    "score_band": {"type": "string", "enum": ["high", "medium", "low", "unscored"]},
    "min_score": {"type": "integer"},
    "has_email": {"type": "boolean"},
    "mail": {"type": "string", "enum": ["mailed", "pending", "no_email", "blocked"]},
    "status": {"type": "string", "description": "Pipeline stage: NEW, CONTACTED, EMAIL_SENT, REPLIED, MEETING, WON, LOST, DISQUALIFIED"},
    "found_from": {"type": "string", "description": "YYYY-MM-DD, leads found on or after this day"},
    "found_to": {"type": "string", "description": "YYYY-MM-DD, leads found on or before this day"},
}


def _match(l, f, sent):
    if f.get("text"):
        hay = " ".join(_s(l.get(k)) for k in ("company_name", "Company Name", "full_name", "description",
                                               "ai_requirement", "ai_summary", "ai_tech_stack", "title")).lower()
        if not all(w in hay for w in str(f["text"]).lower().split()):
            return False
    if f.get("source") and str(f["source"]).lower() not in _s(l.get("source") or l.get("Source")).lower():
        return False
    if f.get("city") and str(f["city"]).lower() not in _s(l.get("location")).lower():
        return False
    cat = _s(l.get("ai_category"))
    if f.get("category"):
        if f["category"] == "buyer":
            if cat not in ("client_project", "hiring_developer"):
                return False
        elif cat != f["category"]:
            return False
    sc = _score(l)
    if f.get("score_band") and _band(sc) != f["score_band"]:
        return False
    if f.get("min_score") is not None and (sc is None or sc < int(f["min_score"])):
        return False
    if f.get("has_email") is not None and bool(_email(l)) != bool(f["has_email"]):
        return False
    if f.get("mail") and _mail_state(l, sent) != f["mail"]:
        return False
    if f.get("status") and (_s(l.get("status") or l.get("Status")) or "NEW").upper() != str(f["status"]).upper():
        return False
    d = _found(l)
    if f.get("found_from") and (not d or d < f["found_from"]):
        return False
    if f.get("found_to") and (not d or d > f["found_to"]):
        return False
    return True


# ------------------------------------------------------------------ tools


def t_find_leads(ctx, sort_by="score", limit=10, **f):
    sent = _sent_set(ctx)
    hits = [l for l in ctx["leads"] if _match(l, f, sent)]
    if sort_by == "newest":
        hits.sort(key=_found, reverse=True)
    else:
        hits.sort(key=lambda l: (_score(l) if _score(l) is not None else -1, _found(l)), reverse=True)
    limit = max(1, min(MAX_ROWS, int(limit or 10)))
    return {"total_matching": len(hits), "rows": [_row(l, sent) for l in hits[:limit]]}


GROUPS = {
    "source": _source, "category": lambda l: _s(l.get("ai_category")) or "not scored",
    "status": lambda l: _s(l.get("status") or l.get("Status")) or "NEW", "score_band": lambda l: _band(_score(l)),
    "day_found": _found, "city": lambda l: _s(l.get("location")).split(",")[0].strip() or "unknown",
}


def t_count_leads(ctx, group_by=None, **f):
    sent = _sent_set(ctx)
    hits = [l for l in ctx["leads"] if _match(l, f, sent)]
    out = {"total": len(hits), "with_email": sum(1 for l in hits if _email(l)),
           "by_mail": dict(Counter(_mail_state(l, sent) for l in hits))}
    if group_by in GROUPS or group_by == "mail":
        key = (lambda l: _mail_state(l, sent)) if group_by == "mail" else GROUPS[group_by]
        c = Counter(key(l) for l in hits)
        out["groups"] = dict(sorted(c.items(), reverse=True)[:40]) if group_by == "day_found" else dict(c.most_common(25))
    return out


def t_email_stats(ctx, date_from=None, date_to=None):
    rows = [s for s in ctx.get("sent", []) if (not date_from or _date(s.get("sent_at")) >= date_from)
            and (not date_to or (_date(s.get("sent_at")) and _date(s.get("sent_at")) <= date_to))]
    acts = [a for a in ctx.get("acts", []) if (not date_from or _date(a.get("occurred_at")) >= date_from)
            and (not date_to or (_date(a.get("occurred_at")) and _date(a.get("occurred_at")) <= date_to))]
    per_day = Counter(_date(s.get("sent_at")) or "unknown date" for s in rows)
    replies = [a for a in acts if a.get("type") == "reply"]
    return {"emails_sent": len(rows), "per_day": dict(sorted(per_day.items(), reverse=True)[:31]),
            "activity_counts": dict(Counter(a.get("type") for a in acts)),
            "latest_replies": [{"when": a.get("occurred_at"), "lead": a.get("lead_name") or a.get("lead_email"),
                                "summary": _s(a.get("summary"))[:120]} for a in sorted(replies, key=lambda a: a.get("occurred_at", ""), reverse=True)[:10]],
            "latest_sent": [{"to": s.get("email"), "when": s.get("sent_at"), "subject": _s(s.get("subject"))[:80]}
                            for s in sorted(rows, key=lambda s: s.get("sent_at", ""), reverse=True)[:10]]}


def t_scraper_stats(ctx, date_from=None, date_to=None):
    agg: Dict[str, Dict[str, int]] = {}
    for r in ctx.get("runs", []):
        d = _date(r.get("start_time"))
        if (date_from and d < date_from) or (date_to and d > date_to):
            continue
        a = agg.setdefault(_s(r.get("scraper_name")).split(" (")[0] or "?", {"runs": 0, "records": 0, "new_leads": 0, "failed": 0})
        a["runs"] += 1
        a["records"] += int(float(_s(r.get("records_collected")) or 0))
        a["new_leads"] += int(float(_s(r.get("new_leads_added")) or 0))
        a["failed"] += 1 if _s(r.get("status")).lower() == "failed" else 0
    return {"scrapers": dict(sorted(agg.items(), key=lambda kv: kv[1]["new_leads"], reverse=True))}


def t_get_lead(ctx, lead_id=None, name=None):
    sent = _sent_set(ctx)
    for l in ctx["leads"]:
        if (lead_id and _s(l.get("lead_id") or l.get("id")) == lead_id) or \
                (name and str(name).lower() in _company(l).lower()):
            keep = ("lead_id", "company_name", "full_name", "email", "mobile_number", "website", "location", "source",
                    "source_url", "ai_category", "ai_score", "ai_summary", "ai_requirement", "ai_budget",
                    "ai_tech_stack", "status", "email_status", "email_sent_at", "first_seen_at", "posted_at")
            info = {k: _s(l.get(k))[:300] for k in keep if _s(l.get(k))}
            info["mail"] = _mail_state(l, sent)
            info["_row"] = _row(l, sent)
            info["activities"] = [{"type": a.get("type"), "when": a.get("occurred_at"), "summary": _s(a.get("summary"))[:120]}
                                  for a in ctx.get("acts", []) if a.get("lead_id") == _s(l.get("lead_id") or l.get("id"))][-10:]
            return info
    return {"error": "no lead with that id or name"}


def t_overview(ctx):
    sent = _sent_set(ctx)
    leads = ctx["leads"]
    st = ctx.get("settings") or {}
    return {"total_leads": len(leads), "with_email": sum(1 for l in leads if _email(l)),
            "by_mail": dict(Counter(_mail_state(l, sent) for l in leads)),
            "by_score_band": dict(Counter(_band(_score(l)) for l in leads)),
            "emails_sent_all_time": len(ctx.get("sent", [])),
            "company": st.get("companyName") or st.get("company_name") or "",
            "auto_email_on": st.get("autoSendEmail"), "today": ctx["today"]}


def _schema(props, required=()):
    return {"type": "object", "properties": props, "required": list(required)}


DATE_PROPS = {"date_from": {"type": "string", "description": "YYYY-MM-DD"}, "date_to": {"type": "string", "description": "YYYY-MM-DD"}}
TOOLS = [
    {"name": "find_leads", "fn": t_find_leads,
     "description": "List leads that match filters (best score first, or newest). Returns total_matching and up to 25 rows.",
     "schema": _schema({**FILTER_PROPS, "sort_by": {"type": "string", "enum": ["score", "newest"]},
                        "limit": {"type": "integer", "description": "1-25, default 10"}})},
    {"name": "count_leads", "fn": t_count_leads,
     "description": "Count leads that match filters, optionally grouped by source, category, status, score_band, "
                    "mail (mailed/pending/no_email/blocked), day_found or city.",
     "schema": _schema({**FILTER_PROPS, "group_by": {"type": "string", "enum": list(GROUPS) + ["mail"]}})},
    {"name": "email_stats", "fn": t_email_stats,
     "description": "E-mails sent (total, per day, latest), replies and other follow-up activity counts in a date range.",
     "schema": _schema(DATE_PROPS)},
    {"name": "scraper_stats", "fn": t_scraper_stats,
     "description": "Per scraper: runs, records collected, new leads added, failed runs, in a date range.",
     "schema": _schema(DATE_PROPS)},
    {"name": "get_lead", "fn": t_get_lead,
     "description": "All details and activity of one lead, by lead_id (e.g. LEAD-00123) or part of its company name.",
     "schema": _schema({"lead_id": {"type": "string"}, "name": {"type": "string"}})},
    {"name": "overview", "fn": t_overview,
     "description": "Totals of the whole system: leads, e-mail coverage, mail status, score bands, mails sent, settings.",
     "schema": _schema({})},
]
from chat_tools_extra import EXTRA_TOOLS  # noqa: E402 - today, next steps, report, mail flow, day log, guide, memory
TOOLS = TOOLS + EXTRA_TOOLS
_BY_NAME = {t["name"]: t for t in TOOLS}


def run_tool(name, args, ctx):
    tool = _BY_NAME.get(name)
    if not tool:
        return {"error": f"unknown tool {name}"}
    try:
        return tool["fn"](ctx, **{k: v for k, v in (args or {}).items() if v not in (None, "")})
    except Exception as e:  # noqa: BLE001 - a bad argument becomes a message the model can fix
        return {"error": f"{type(e).__name__}: {e}"}


def _table_rows(name, out):
    if not isinstance(out, dict):
        return None
    if name in ("find_leads", "leads_by_next_step") and out.get("rows"):
        return out["rows"]
    if name == "get_lead" and out.get("_row"):
        return [out["_row"]]
    return None


def _strip(out):
    return {k: v for k, v in out.items() if k != "_row"} if isinstance(out, dict) else out


def _plain(text):
    """The chat bubble shows plain text: drop markdown emphasis / headings the model may still add."""
    text = re.sub(r"\*\*(.+?)\*\*", lambda m: m.group(1), text)
    text = re.sub(r"(?m)^#{1,6}\s*", "", text)
    return text.strip()


def _table(rows):
    if not rows:
        return None
    cols = ["lead_id", "company", "email", "phone", "location", "source", "score", "status"]
    return {"columns": cols, "rows": [{c: r.get(c, "") for c in cols} for r in rows]}


def _system(ctx):
    import assistant_knowledge as kb
    return (SYSTEM.replace("{today}", ctx["today"]).replace("{knowledge}", kb.summary_for_prompt())
            .replace("{examples}", kb.examples_for_prompt()))


# ------------------------------------------------------------------ engines


def provider() -> str:
    if os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN"):
        return "claude"
    if (os.getenv("GEMINI_API_KEY") or "").strip():
        return "gemini"
    return ""


def _history(history) -> List[Dict[str, str]]:
    out = []
    for h in (history or [])[-6:]:
        role = "assistant" if h.get("role") in ("assistant", "bot") else "user"
        text = _s(h.get("text"))[:800]
        if text:
            out.append({"role": role, "text": text})
    while out and out[0]["role"] != "user":
        out.pop(0)
    return out


def ask_claude(question, ctx, history=None, client=None):
    if client is None:
        import anthropic
        client = anthropic.Anthropic()
    tools = [{"name": t["name"], "description": t["description"], "input_schema": t["schema"]} for t in TOOLS]
    messages = [{"role": h["role"], "content": h["text"]} for h in _history(history)]
    messages.append({"role": "user", "content": question})
    last_rows = None
    for _ in range(MAX_TOOL_ROUNDS):
        resp = client.beta.messages.create(
            model=CLAUDE_MODEL, max_tokens=4000, system=_system(ctx), tools=tools, messages=messages,
            betas=["server-side-fallback-2026-07-01"], fallbacks="default",  # a safety decline retries on the recommended model
            output_config={"effort": "low"},  # data look-ups: low effort keeps answers quick and cheap
        )
        if resp.stop_reason == "refusal":
            raise RuntimeError("the model declined this question")
        uses = [b for b in resp.content if b.type == "tool_use"]
        if resp.stop_reason != "tool_use" or not uses:
            text = "".join(b.text for b in resp.content if b.type == "text").strip()
            return {"reply": _plain(text) or "-", "table": _table(last_rows), "engine": "claude"}
        messages.append({"role": "assistant", "content": resp.content})
        results = []
        for u in uses:
            out = run_tool(u.name, u.input, ctx)
            last_rows = _table_rows(u.name, out) or last_rows
            results.append({"type": "tool_result", "tool_use_id": u.id,
                            "content": json.dumps(_for_model(_strip(out)), ensure_ascii=False, default=str)[:20000],
                            **({"is_error": True} if isinstance(out, dict) and "error" in out else {})})
        messages.append({"role": "user", "content": results})
    raise RuntimeError("too many look-ups for one question")


def _gemini_schema(schema):
    """Gemini function declarations take an OpenAPI-style subset: no empty 'required', no enums on non-strings."""
    props = {k: {kk: ([x for x in vv if x != ""] if kk == "enum" else vv) for kk, vv in v.items()}  # no empty enum values
             for k, v in schema.get("properties", {}).items()}
    out = {"type": "object", "properties": props}
    if schema.get("required"):
        out["required"] = schema["required"]
    return out


def ask_gemini(question, ctx, history=None, post=None):
    import requests
    post = post or requests.post
    model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
    decls = [{"name": t["name"], "description": t["description"], "parameters": _gemini_schema(t["schema"])}
             if t["schema"]["properties"] else {"name": t["name"], "description": t["description"]} for t in TOOLS]
    contents = [{"role": "model" if h["role"] == "assistant" else "user", "parts": [{"text": h["text"]}]}
                for h in _history(history)]
    contents.append({"role": "user", "parts": [{"text": question}]})
    last_rows = None
    for _ in range(MAX_TOOL_ROUNDS):
        resp = post(GEMINI_URL.format(model=model), timeout=40,
                    headers={"x-goog-api-key": os.getenv("GEMINI_API_KEY", "").strip(), "Content-Type": "application/json"},
                    json={"systemInstruction": {"parts": [{"text": _system(ctx)}]}, "contents": contents,
                          "tools": [{"functionDeclarations": decls}], "generationConfig": {"maxOutputTokens": 1500}})
        if resp.status_code != 200:
            raise RuntimeError(f"Gemini HTTP {resp.status_code}")
        cand = (resp.json().get("candidates") or [{}])[0]
        parts = (cand.get("content") or {}).get("parts") or []
        calls = [p["functionCall"] for p in parts if isinstance(p, dict) and p.get("functionCall")]
        if not calls:
            text = "".join(p.get("text", "") for p in parts if isinstance(p, dict)).strip()
            if not text:
                raise RuntimeError("Gemini returned no answer")
            return {"reply": _plain(text), "table": _table(last_rows), "engine": "gemini"}
        contents.append({"role": "model", "parts": parts})
        answers = []
        for c in calls:
            out = run_tool(c.get("name"), c.get("args") or {}, ctx)
            last_rows = _table_rows(c.get("name"), out) or last_rows
            answers.append({"functionResponse": {"name": c.get("name"), "response": {"result": _for_model(_strip(out))}}})
        contents.append({"role": "user", "parts": answers})
    raise RuntimeError("too many look-ups for one question")


def ask(question: str, ctx: Dict[str, Any], history=None, claude_client=None, gemini_post=None) -> Optional[Dict[str, Any]]:
    """Answer with the configured AI, or None when no AI key is set."""
    ctx = {**ctx, "today": ctx.get("today") or datetime.date.today().isoformat()}
    which = "claude" if claude_client is not None else "gemini" if gemini_post is not None else provider()
    if which == "claude":
        return ask_claude(question, ctx, history, client=claude_client)
    if which == "gemini":
        return ask_gemini(question, ctx, history, post=gemini_post)
    return None

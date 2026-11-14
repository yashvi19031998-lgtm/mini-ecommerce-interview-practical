"""'Reply Today': fresh buyer posts (Reddit, Freelancer.com, Hacker News, ...) that have no e-mail address,
so the only way in is to reply on the post, send a DM or place a bid. Lists them best-first and writes a
ready-to-paste reply for each one (Claude when ANTHROPIC_API_KEY is set, otherwise a template).

Replying itself is done by hand on the platform; marking a lead "replied" logs a note activity, so it leaves
this list and the "Not Contacted Yet" list."""
import datetime
import os
import re

BUYER_CATEGORIES = {"client_project", "hiring_developer"}
CLOSED_STATUSES = {"REPLIED", "WON", "LOST", "CLOSED", "NOT_INTERESTED", "CONTACTED", "EMAIL_SENT"}
DEFAULT_DAYS = 3
MAX_ITEMS = 200

CHANNELS = {  # contact_channel -> how to answer
    "reddit": "Reddit comment or DM",
    "freelancer_bid": "Freelancer.com bid",
    "hackernews": "Hacker News reply / the contact in the post",
    "phone": "WhatsApp / phone",
    "website": "contact form on their website",
}

AI_MODEL = os.getenv("AI_QUALIFY_MODEL", "claude-opus-5-5")

REPLY_SYSTEM = """You write short replies that a small software and digital marketing agency (Sangeeta Infotech, \
Ahmedabad, India; senior developers, web and mobile apps, custom software, AI automation, SEO, social media \
and ads) posts in answer to someone who asked for help online.

Rules:
- Write as one person from the agency, in plain friendly English. No subject line, no greeting card tone.
- First sentence: their exact need, in your own words, so they see you read the post.
- Then 2-3 short sentences: how we would do it (one concrete approach or first step), and one line of \
relevant experience. Never invent clients, numbers, prices or links.
- If the post asks a question or for something specific (stack, budget, timeline, portfolio), answer it or say \
what you need to give an exact answer.
- End with one easy next step (a short call, or "DM me the details").
- Length: 60-110 words. For a Freelancer.com bid you may use up to 150 words.
- Do not add a signature, contact details, or placeholders like [Name]."""


def _text(v):
    s = str(v if v is not None else "").strip()
    return "" if s.lower() in ("nan", "n/a", "none") else s


def _first_email(lead):
    e = _text(lead.get("Email") or lead.get("email")).split(",")[0].strip()
    return e if "@" in e else ""


def _score(lead):
    try:
        return int(float(_text(lead.get("ai_score")) or "x"))
    except ValueError:
        return None


def _post_date(lead):
    for k in ("posted_at", "first_seen_at"):
        v = _text(lead.get(k))[:10]
        if re.match(r"\d{4}-\d{2}-\d{2}$", v):
            return v
    return ""


def build_items(leads, touched_ids, days=DEFAULT_DAYS, today=None):
    """Buyer posts from the last `days` days with no e-mail, nobody worked on yet. Best score first, then newest."""
    today = today or datetime.date.today()
    since = (today - datetime.timedelta(days=max(0, int(days)))).isoformat()
    items, counts = [], {"total": 0, "by_channel": {}}
    for l in leads:
        lid = str(l.get("id") or l.get("lead_id") or "")
        if not lid or lid in touched_ids or _text(l.get("ai_category")) not in BUYER_CATEGORIES:
            continue
        if _first_email(l) or _text(l.get("Status") or l.get("status")).upper() in CLOSED_STATUSES:
            continue
        posted = _post_date(l)
        if not posted or posted < since:
            continue
        channel = _text(l.get("contact_channel")) or "website"
        counts["total"] += 1
        counts["by_channel"][channel] = counts["by_channel"].get(channel, 0) + 1
        items.append({
            "id": lid,
            "title": _text(l.get("Company Name") or l.get("company_name"))[:200],
            "source": _text(l.get("Source") or l.get("source")),
            "url": _text(l.get("source_url")),
            "channel": channel,
            "how": CHANNELS.get(channel, "reply on the post"),
            "score": _score(l),
            "requirement": _text(l.get("ai_requirement"))[:200],
            "budget": _text(l.get("ai_budget"))[:80],
            "summary": _text(l.get("ai_summary") or l.get("description"))[:300],
            "phone": _text(l.get("Mobile Number") or l.get("mobile_number")).split(",")[0].strip(),
            "posted": posted,
        })
    items.sort(key=lambda i: i["posted"], reverse=True)
    items.sort(key=lambda i: i["score"] if i["score"] is not None else -1, reverse=True)
    return items[:MAX_ITEMS], counts


def _lead_prompt(lead):
    channel = _text(lead.get("contact_channel")) or "website"
    parts = [
        f"Where we reply: {CHANNELS.get(channel, 'a reply on the post')}",
        f"Post title: {_text(lead.get('Company Name') or lead.get('company_name'))}",
        f"What they need (our notes): {_text(lead.get('ai_requirement'))}",
        f"Budget: {_text(lead.get('ai_budget'))}",
        f"Tech mentioned: {_text(lead.get('ai_tech_stack'))}",
        f"Post text: {_text(lead.get('description'))[:2500]}",
    ]
    return "\n".join(p for p in parts if not p.endswith(": "))


_DIGITAL = re.compile(r"\b(seo|social media|google ads|facebook ads|meta ads|instagram|ppc|digital marketing|marketing)\b", re.I)


def template_reply(lead):
    """Fill-in reply used when no AI key is set. Mentions their post and need; differs per channel."""
    title = re.sub(r"\s*(--\s*\d+|\|\s*freelancer)\s*$", "", _text(lead.get("Company Name") or lead.get("company_name")),
                   flags=re.I).strip()
    need = _text(lead.get("ai_requirement")).rstrip(".")
    # A short label ("Software engineering") or a bare tech list says nothing - leave it out
    need_ok = len(need) >= 25 and not re.match(r"(needs?|requires?)\b", need, re.I)
    need_line = f" You need: {need}." if need_ok else ""  # keep its case: "React ..." must stay "React"
    # A post title reads well in the text; a company name or "X | 11 Openings" does not
    about = f' about "{title}"' if len(title.split()) >= 4 and "|" not in title else ""
    digital = bool(_DIGITAL.search(f"{title} {need} {_text(lead.get('description'))[:500]}"))
    skills = ("SEO, social media and Google / Meta ads for small and mid-size businesses" if digital else
              "senior developers for web and mobile apps, custom software and AI automation")
    tech = _text(lead.get("ai_tech_stack"))
    tech_line = f" We work with {tech} regularly." if tech and not digital else ""
    channel = _text(lead.get("contact_channel"))
    if channel == "freelancer_bid":
        return (f"Hello, I have read your project{about}.{need_line}{tech_line} Our team at Sangeeta Infotech "
                f"({skills}) can take this on. I would start by confirming the scope and the must-have features "
                f"with you, then share a short plan with milestones and a fixed timeline before any work starts. "
                f"Could you tell me your deadline and whether you have designs or an existing codebase? "
                f"Happy to jump on a quick call.")
    if channel == "phone":
        return (f"Hi, this is Sangeeta Infotech from Ahmedabad. We saw your post{about}.{need_line} We do exactly "
                f"this ({skills}). Can we have a 10-minute call this week to understand what you need?")
    return (f"Hi! Saw your post{about}.{need_line}{tech_line} That's the kind of work our small team at Sangeeta "
            f"Infotech does ({skills}). Happy to suggest an approach and a rough timeline once I know a bit more "
            f"about the scope and your deadline. Mind if I DM you a couple of questions?")


def gemini_reply(lead, post=None):
    """Gemini-written reply (free key option, GEMINI_API_KEY), or raises."""
    import requests
    from lead_quality import GEMINI_URL, GEMINI_MODEL, gemini_key
    post = post or requests.post
    body = {"contents": [{"role": "user", "parts": [{"text": f"{REPLY_SYSTEM}\n\nWrite the reply for this post:\n\n"
                                                             f"{_lead_prompt(lead)}"}]}],
            "generationConfig": {"maxOutputTokens": 1024}}
    resp = post(GEMINI_URL.format(model=GEMINI_MODEL), json=body, timeout=40,
                headers={"x-goog-api-key": gemini_key(), "Content-Type": "application/json"})
    if resp.status_code != 200:
        raise RuntimeError(f"Gemini HTTP {resp.status_code}")
    parts = (resp.json().get("candidates") or [{}])[0].get("content", {}).get("parts", [])
    text = "".join(p.get("text", "") for p in parts if isinstance(p, dict)).strip()
    if not text:
        raise RuntimeError("Gemini returned no text")
    return text


def ai_reply(lead, client=None):
    """Claude-written reply, or raises. client: anthropic.Anthropic() (made here when None)."""
    if client is None:
        import anthropic
        client = anthropic.Anthropic()
    response = client.beta.messages.create(
        model=AI_MODEL,
        max_tokens=2000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",  # a safety decline is retried on Anthropic's recommended model
        output_config={"effort": "low"},  # short copywriting: low effort keeps cost and wait down
        system=REPLY_SYSTEM,
        messages=[{"role": "user", "content": f"Write the reply for this post:\n\n{_lead_prompt(lead)}"}],
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("the model declined to write this reply")
    text = "".join(b.text for b in response.content if b.type == "text").strip()
    if not text:
        raise RuntimeError("empty reply")
    return text


def draft_reply(lead, client=None):
    """{'text', 'by': 'ai'|'template', 'note'} - never raises."""
    errors = []
    if os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN") or client is not None:
        try:
            return {"text": ai_reply(lead, client), "by": "ai", "note": ""}
        except Exception as e:  # noqa: BLE001 - try the next writer, say why
            errors.append(f"Claude: {e}")
    if (os.getenv("GEMINI_API_KEY") or "").strip():
        try:
            return {"text": gemini_reply(lead), "by": "ai", "note": "; ".join(errors)}
        except Exception as e:  # noqa: BLE001
            errors.append(f"Gemini: {e}")
    note = ("AI failed (" + "; ".join(errors) + "); template used.") if errors else \
        "No AI key (ANTHROPIC_API_KEY or GEMINI_API_KEY): template used - edit it before posting."
    return {"text": template_reply(lead), "by": "template", "note": note}

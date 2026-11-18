"""What the in-app assistant knows about how LeadsGen AI works, and what it has been taught.

KNOWLEDGE: sections about the flow of the system (finding leads, mail, phone, follow-ups, reports, screens).
search(): keyword search over those sections and over taught facts - works with no AI key.
Memory (logs/assistant_memory.json):
  - facts the owner taught ("remember: we never mail on Sundays")
  - answers rated helpful / not helpful; helpful ones become examples for the AI next time
Keep KNOWLEDGE in line with the code when a flow changes (it is plain text on purpose).
"""
import datetime
import json
import os
import re
import threading
from typing import Any, Dict, List

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MEMORY_FILE = os.path.join(BASE_DIR, "logs", "assistant_memory.json")
MAX_FACTS = 200
MAX_EXAMPLES = 300
_lock = threading.Lock()

KNOWLEDGE: Dict[str, str] = {
    "Daily flow (what happens every day)": (
        "1) Lead finders run all day: the general scraper every hour at :15 and the freelance scraper every hour at :30 "
        "(GitHub Actions; the PC cron engine can run them too). New leads are scored 0-10 by AI and get a category. "
        "2) Contact details are filled in from the lead's website (e-mail, phone). "
        "3) The outreach mail job sends mails to qualified leads (GitHub, every hour at :45; the PC cron engine only Mon-Sat 10:00-19:00). "
        "4) The owner works the Today page: replies, follow-ups, calls / WhatsApp, replies on posts. "
        "5) At 12 AM IST a daily report is sent by e-mail. Data is synced to the Supabase database before and after every job."),
    "Mail flow (who gets an e-mail and when)": (
        "A lead gets an automatic mail when: it has a usable e-mail (not invalid, bounced or opted out), it is not "
        "a job seeker / agency / directory, its AI score is at least the minimum (MIN_AI_SCORE_FOR_AUTO_EMAIL), "
        "and it was never mailed before. Buyers are mailed before 'prospect' leads. Limits: MAX_EMAILS_PER_DAY "
        "(default 50) in total, MAX_PROSPECT_EMAILS_PER_DAY (default 15) for prospects, MAX_PENDING_EMAILS_PER_RUN "
        "per run. Mailboxes are checked before sending; a catch-all or unverifiable address is skipped so the "
        "account does not get marked as spam. Every mail is logged in logs/sent_emails.csv and shown in the lead's history. "
        "Leads waiting for a mail are in Leads > 'In mail queue'."),
    "Phone and WhatsApp (why calls matter)": (
        "A mail alone is often never read. When a mailed lead has a phone number it stays on the to-do list as "
        "'Mailed - now call' until a call or WhatsApp is logged. Open the lead: the panel has a ready WhatsApp "
        "message (one tap: 'Send on WhatsApp') and a call script (opening line, 3 questions, answers to objections, "
        "voicemail). 'Write with AI' rewrites them for that lead when an AI key is set. After calling, press "
        "'I called' or 'I sent a WhatsApp' so the lead moves to 'Waiting for reply'. A lead is fully contacted when "
        "it got both a mail and a call / WhatsApp (or the one channel it has)."),
    "Next steps (lead stages)": (
        "Every lead has one next step, worked out from its data: Reply now (they answered), Follow-up due (a "
        "reminder you set is due), Call or WhatsApp (no e-mail, has a phone), Mailed - now call (mail sent, not "
        "called yet), Reply on post (only reachable on Reddit / Freelancer / Hacker News), No reply yet (contacted "
        "4+ days ago, no answer), In mail queue (auto-mail will send it), Waiting for reply (contacted in the last "
        "4 days), Post too old (post older than 14 days), No contact found, Not a fit (job seeker, agency, "
        "directory), Closed (won, lost or asked to stop). The first five are the to-do list on Today."),
    "Hot, warm, cold (scores)": (
        "AI scores each lead 0-10 for how likely they are to buy software or digital-marketing work. Hot = 7-10, "
        "Warm = 4-6, Cold = 0-3, Not scored = no score yet. Filter by it on Leads, Reports > Summary and here."),
    "Follow-ups": (
        "Set a reminder from the lead panel ('Remind me: Tomorrow / In 3 days / Next week'). When it is due the lead "
        "shows under 'Follow-up due' on Today. The Follow-ups page lists every planned follow-up and the full "
        "activity log (mails, calls, WhatsApps, notes, replies). Replies to our mails are picked up from the mailbox "
        "automatically and the lead moves to 'Reply now'."),
    "Screens (where to find things)": (
        "Today: what to do now + this month against goals. Leads: every lead with filters (next step, hot/warm/cold, "
        "source, date found, outcome, contact type, search), as a table or a board; click a lead for its panel. "
        "Follow-ups: reminders and history. Find Leads: run scrapers, freelance projects, auto scraper, 18 single "
        "sources. Contacts: import leads, files, CRM sources, contact tools. Reports: Summary (for clients), "
        "Overview, Leads & mail by day, Scrapers, Sources, Pipeline, Outreach, Missing details, Activity log. "
        "Settings & Email: company details, SMTP mail account, signature, API keys. Each page has its own link "
        "(for example #/leads?action=call_pending&band=hot) that can be bookmarked or shared."),
    "Reports": (
        "Reports > Summary: pick a period (today, 7/30/90 days, this or last month, all, or custom dates) and filter "
        "by client type (IT project, Hiring developers, Digital marketing, Business prospect), temperature and source. "
        "It shows what happened in plain sentences, 'Ask AI for advice', the funnel (found, contacted, reached by "
        "phone, replied, meeting, won), work done (mails, calls, WhatsApps, post replies, replies), a daily chart, and "
        "tables by client type and source. Print / PDF and CSV export are on the page. Monthly goals are set on Today."),
    "Outcome (pipeline status)": (
        "Set in the lead panel: New, Mailed, Contacted, Replied, Meeting, Won, Lost. 'Not interested' closes the lead "
        "as Lost. On Leads > Board > Outcome you can drag cards between outcomes."),
    "AI keys and what works without them": (
        "Without any key: scraping, lead stages, Today, Leads, reports with written highlights, phone scripts from "
        "templates, and this assistant's built-in answers. With GEMINI_API_KEY (free) or ANTHROPIC_API_KEY in .env: "
        "AI lead scoring, AI-written mails, WhatsApp texts and call scripts, AI report advice, and this assistant "
        "answering any question. Contact details (e-mails, phones) are never sent to the AI provider."),
    "Teaching the assistant": (
        "Say 'remember: ...' (or 'yaad rakh: ...') to teach a fact; it is used in every later answer. 'forget 3' "
        "removes fact 3, 'what do you remember' lists them. Rate answers with thumbs up / down; helpful answers are "
        "reused as examples."),
}

_STOP = set("the a an is are was to of in on for and or what how why when which who do does did i we you it this that "
            "me my our che chhe su shu kem kevi rite ma no ni nu ne thi ane aa ae hu tame kai".split())


def _words(text: str) -> List[str]:
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in _STOP and len(w) > 1]


# Gujlish / short words -> the words used in KNOWLEDGE
SYNONYMS = {"mail": ["mail", "e-mail", "email"], "mails": ["mail"], "gaya": ["sent"], "moklya": ["sent"], "mokle": ["sent"],
            "call": ["call", "phone"], "phone": ["phone", "call"], "whatsapp": ["whatsapp"], "flow": ["flow", "daily"],
            "roj": ["daily"], "daily": ["daily", "every", "day"], "report": ["report", "reports", "summary"],
            "followup": ["follow"], "follow": ["follow"], "score": ["score", "hot"], "hot": ["hot", "score"],
            "stage": ["next", "step"], "status": ["next", "step", "outcome"], "key": ["key", "ai"], "screen": ["screens", "page"],
            "kyare": ["when", "hour"], "limit": ["limits", "max"], "queue": ["queue"], "teach": ["remember", "teach"]}


def search(query: str, k: int = 2) -> List[Dict[str, str]]:
    """Best matching knowledge sections (title, text) plus matching taught facts."""
    terms = []
    for w in _words(query):
        terms += [w] + SYNONYMS.get(w, [])
    if not terms:
        return []
    scored = []
    for title, text in KNOWLEDGE.items():
        hay_t, hay = title.lower(), text.lower()
        score = sum(3 for t in terms if t in hay_t) + sum(1 for t in terms if t in hay)
        if score:
            scored.append((score, title, text))
    scored.sort(reverse=True)
    out = [{"title": t, "text": x} for _, t, x in scored[:k]]
    facts = [f for f in load()["facts"] if any(t in f["text"].lower() for t in terms)]
    if facts:
        out.append({"title": "What you taught me", "text": " ".join(f"- {f['text']}" for f in facts[:5])})
    return out


def summary_for_prompt() -> str:
    """Short version of KNOWLEDGE + taught facts for the AI system prompt."""
    parts = [f"{t}: {x}" for t, x in KNOWLEDGE.items()]
    facts = load()["facts"]
    if facts:
        parts.append("Facts the owner taught you (always follow them): " + " | ".join(f["text"] for f in facts[-40:]))
    return "\n".join(parts)


# ---------------------------------------------------------------------------------------------
# Memory
# ---------------------------------------------------------------------------------------------
def load() -> Dict[str, List[Dict[str, Any]]]:
    try:
        with open(MEMORY_FILE, encoding="utf-8") as fh:
            data = json.load(fh)
        return {"facts": list(data.get("facts") or []), "examples": list(data.get("examples") or [])}
    except (OSError, ValueError, AttributeError):
        return {"facts": [], "examples": []}


def _save(data) -> None:
    os.makedirs(os.path.dirname(MEMORY_FILE), exist_ok=True)
    tmp = MEMORY_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, MEMORY_FILE)


def _now() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")


def remember(text: str) -> Dict[str, Any]:
    text = " ".join(str(text or "").split())[:300]
    if len(text) < 3:
        raise ValueError("Tell me what to remember, for example: remember: we never mail on Sundays.")
    if re.search(r"(api[_ ]?key|password|passwd|secret|token)\s*[:=]", text, re.I) or re.search(r"\b(sk|AIza)[A-Za-z0-9_\-]{16,}", text):
        raise ValueError("I do not store passwords or API keys. Put keys in the .env file instead.")
    with _lock:
        data = load()
        if any(f["text"].lower() == text.lower() for f in data["facts"]):
            return {"text": text, "count": len(data["facts"]), "new": False}
        data["facts"] = (data["facts"] + [{"text": text, "at": _now()}])[-MAX_FACTS:]
        _save(data)
        return {"text": text, "count": len(data["facts"]), "new": True}


def forget(number: int) -> Dict[str, Any]:
    with _lock:
        data = load()
        if not 1 <= number <= len(data["facts"]):
            raise ValueError(f"There is no fact {number}. Say 'what do you remember' to see the list.")
        gone = data["facts"].pop(number - 1)
        _save(data)
        return gone


def rate(question: str, answer: str, helpful: bool) -> int:
    """Stores a rated answer; helpful ones are reused as examples. Returns how many examples are stored."""
    q, a = " ".join(str(question or "").split())[:500], str(answer or "").strip()[:1500]
    if not q or not a:
        raise ValueError("question and answer are required")
    with _lock:
        data = load()
        data["examples"] = [e for e in data["examples"] if e["q"].lower() != q.lower()]
        data["examples"] = (data["examples"] + [{"q": q, "a": a, "good": bool(helpful), "at": _now()}])[-MAX_EXAMPLES:]
        _save(data)
        return len(data["examples"])


def examples_for_prompt(n: int = 8) -> str:
    good = [e for e in load()["examples"] if e.get("good")][-n:]
    bad = [e for e in load()["examples"] if not e.get("good")][-4:]
    out = []
    if good:
        out.append("Answers the owner rated helpful (match this style):\n" + "\n".join(f"Q: {e['q']}\nA: {e['a'][:400]}" for e in good))
    if bad:
        out.append("Questions where the owner was NOT happy with the answer (answer these better, use the tools):\n" +
                   "\n".join(f"Q: {e['q']}" for e in bad))
    return "\n\n".join(out)

"""
Which lead sources are worth keeping?  Writes logs/source_quality.csv after every run.

Per source: leads, % with a direct contact, how many the AI has scored, average score,
hot leads (buyer category with score >= 7), hot rate, and deals marked WON in the dashboard.
A source with many qualified leads and ~0% hot rate is noise - disable it in run_all_scrapers.py.

    python source_report.py
"""

import csv
import os
from collections import defaultdict
from typing import Dict, List

HOT_CATEGORIES = {"client_project", "hiring_developer", "prospect_signal"}
HOT_SCORE = 7
REPORT_PATH = os.path.join("logs", "source_quality.csv")


def source_family(lead: Dict[str, str]) -> str:
    """'Reddit (r/forhire) | Search Engine (...)' -> 'Reddit' (the source that found it first)."""
    first = str(lead.get("source") or "Unknown").split("|")[0].strip().strip('"')
    return first.split(" (")[0].strip() or "Unknown"


def _score(lead) -> float:
    try:
        return float(lead.get("ai_score") or 0)
    except ValueError:
        return 0.0


def build_report(leads: List[Dict[str, str]]) -> List[Dict[str, object]]:
    groups = defaultdict(list)
    for lead in leads:
        groups[source_family(lead)].append(lead)

    rows = []
    for name, items in groups.items():
        qualified = [l for l in items if l.get("ai_qualified_at")]
        hot = [l for l in qualified if l.get("ai_category") in HOT_CATEGORIES and _score(l) >= HOT_SCORE]
        rows.append({
            "source": name,
            "leads": len(items),
            "with_contact_pct": round(100 * sum(1 for l in items if l.get("email") or l.get("mobile_number")) / len(items)),
            "ai_scored": len(qualified),
            "avg_ai_score": round(sum(_score(l) for l in qualified) / len(qualified), 1) if qualified else "",
            "hot": len(hot),
            "hot_rate_pct": round(100 * len(hot) / len(qualified)) if qualified else "",
            "won": sum(1 for l in items if str(l.get("status", "")).upper() == "WON"),
        })
    rows.sort(key=lambda r: (r["hot"], r["leads"]), reverse=True)
    return rows


def write_report(leads: List[Dict[str, str]], path: str = REPORT_PATH) -> List[Dict[str, object]]:
    rows = build_report(leads)
    if not rows:
        return rows
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return rows


def print_report(rows: List[Dict[str, object]], top: int = 15) -> None:
    print(f"\n{'Source':<32}{'Leads':>7}{'Contact%':>10}{'Scored':>8}{'AvgScore':>10}{'Hot':>6}{'Hot%':>7}{'Won':>5}")
    for r in rows[:top]:
        print(f"{r['source'][:31]:<32}{r['leads']:>7}{r['with_contact_pct']:>10}{r['ai_scored']:>8}"
              f"{str(r['avg_ai_score']):>10}{r['hot']:>6}{str(r['hot_rate_pct']):>7}{r['won']:>5}")


if __name__ == "__main__":
    from lead_normalizer import MasterLeadRegistry
    report = write_report(MasterLeadRegistry("all_leads_master.csv").leads)
    print_report(report)
    print(f"\nSaved to {REPORT_PATH}")

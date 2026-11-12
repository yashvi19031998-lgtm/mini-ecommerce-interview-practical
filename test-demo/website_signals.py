"""
Website "needs work" signals - reasons a company may want a new or improved website/app.

Reads the homepage (through html_cache_manager, so pages already downloaded during contact
enrichment cost no extra request) and reports things like:
  not mobile-friendly, no HTTPS, old WordPress / jQuery, stale copyright year, site-builder site.

The result is stored in the lead's `website_signals` column and shown to the AI qualifier,
which can treat a clearly outdated site as a "prospect_signal" (redesign / rebuild pitch).
"""

import datetime
import re
from typing import List

from html_cache_manager import fetch_or_get_cached_html

NO_ISSUES = "no obvious issues"
FETCH_FAILED = "could not load website"


def analyze_html(html: str, url: str = "") -> List[str]:
    """Pure function: returns human-readable signals found in the page (empty list = none)."""
    signals = []
    lower = html.lower()

    if url.lower().startswith("http://"):
        signals.append("no HTTPS")

    if not re.search(r"<meta[^>]+name=[\"']viewport[\"']", lower):
        signals.append("not mobile-friendly (no viewport tag)")

    wp = re.search(r"<meta[^>]+name=[\"']generator[\"'][^>]+content=[\"']wordpress\s+(\d+)\.(\d+)", lower)
    if wp and int(wp.group(1)) < 6:
        signals.append(f"old WordPress {wp.group(1)}.{wp.group(2)}")

    jq = re.search(r"jquery[-.]?(\d)\.(\d+)(?:\.\d+)?(?:\.min)?\.js", lower)
    if jq and int(jq.group(1)) < 3:
        signals.append(f"old jQuery {jq.group(1)}.{jq.group(2)}")

    years = [int(y) for y in re.findall(r"(?:©|&copy;|copyright)\s*(?:\d{4}\s*[-–]\s*)?((?:19|20)\d{2})", lower)]
    if years and max(years) <= datetime.date.today().year - 3:
        signals.append(f"copyright year {max(years)} (site not updated recently)")

    # builder asset hosts / generator tags only: a link to some blogspot or weebly site is not proof
    for marker, name in (("wixstatic.com", "Wix"), ("www.blogger.com/static", "Blogger"), ("godaddysites.com", "GoDaddy builder"),
                         ("editmysite.com", "Weebly"), ("site123", "SITE123")):
        if marker in lower:
            signals.append(f"built with {name} (site builder)")
            break

    if "swfobject" in lower or ".swf\"" in lower:
        signals.append("uses Flash")
    return signals


def check_website(url: str) -> str:
    """Returns a short summary string for the lead's website_signals column."""
    if not url:
        return ""
    full = url if url.startswith(("http://", "https://")) else f"https://{url}"
    html, status = fetch_or_get_cached_html(full, timeout=10)
    if status != 1 or not html:
        return FETCH_FAILED
    found = analyze_html(html, full)
    return "; ".join(found) if found else NO_ISSUES

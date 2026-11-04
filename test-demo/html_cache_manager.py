"""
Local HTML cache for company / contact / lead pages.

Once a page has been downloaded successfully we keep a copy, so later runs don't hit the
site again (fewer requests -> fewer blocks, faster runs):

- Fresh copy (younger than HTML_CACHE_MAX_AGE_DAYS, default 30): served from disk, no request.
- Old copy: re-downloaded so changed emails/phones are picked up. If that download fails
  (403, 429, captcha, network), the old copy is used instead ("stale-if-error").
- Captcha / "access denied" pages are never cached, even when the site returns HTTP 200.
- Copies older than 3x the max age are deleted automatically.

On GitHub Actions the html_cache/ folder is kept between runs with actions/cache
(see .github/workflows/auto_scraper_1hr.yml); it is never committed to git.
"""

import hashlib
import os
import sys
import time

import requests

# Ensure UTF-8 output on Windows consoles/pipes to prevent UnicodeEncodeError
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "html_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

CACHE_MAX_AGE_DAYS = float(os.getenv("HTML_CACHE_MAX_AGE_DAYS", "30"))

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}

# Text that shows up on bot-check / block pages. Such pages must not be cached.
BLOCK_PAGE_MARKERS = (
    "captcha", "cf-chl", "challenge-platform", "attention required! | cloudflare",
    "access denied", "unusual traffic", "are you a robot", "verify you are human",
    "request blocked", "enable javascript and cookies to continue",
)


def get_url_hash(url: str) -> str:
    """Generates a unique MD5 hash filename for a given URL."""
    return hashlib.md5(url.encode("utf-8")).hexdigest() + ".html"


def looks_like_block_page(html: str) -> bool:
    """True for captcha / access-denied pages. Only short pages are checked: real pages that
    merely mention 'captcha' somewhere (e.g. a contact form) are usually much longer."""
    if not html:
        return True
    head = html[:20000].lower()
    return len(html) < 20000 and any(marker in head for marker in BLOCK_PAGE_MARKERS)


def _age_days(path: str) -> float:
    return (time.time() - os.path.getmtime(path)) / 86400


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _write_atomic(path: str, text: str) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)  # never leaves a half-written file behind


def prune_cache(max_age_days: float = CACHE_MAX_AGE_DAYS * 3) -> int:
    """Deletes cached pages older than max_age_days. Returns how many were removed."""
    removed = 0
    for name in os.listdir(CACHE_DIR):
        path = os.path.join(CACHE_DIR, name)
        try:
            if os.path.isfile(path) and _age_days(path) > max_age_days:
                os.remove(path)
                removed += 1
        except OSError:
            pass
    return removed


def fetch_or_get_cached_html(url: str, headers: dict = None, timeout: int = 10,
                             max_age_days: float = None) -> tuple[str, int]:
    """
    Returns (html, 1) on success - from cache or live - and ("", 0) when nothing usable exists.
    """
    if not url:
        return "", 0

    max_age = CACHE_MAX_AGE_DAYS if max_age_days is None else max_age_days
    cache_path = os.path.join(CACHE_DIR, get_url_hash(url))
    cached = None

    # 1. Fresh cache hit -> no request at all
    if os.path.exists(cache_path):
        try:
            cached = _read(cache_path)
            if _age_days(cache_path) <= max_age:
                print(f"⚡ [CACHE HIT] {url}")
                return cached, 1
        except OSError:
            cached = None

    # 2. Missing or old -> download
    print(f"🌐 [LIVE FETCH] {url}")
    try:
        response = requests.get(url, headers=headers or DEFAULT_HEADERS, timeout=timeout)
        if response.status_code == 200 and not looks_like_block_page(response.text):
            _write_atomic(cache_path, response.text)
            return response.text, 1
        reason = f"HTTP {response.status_code}" if response.status_code != 200 else "captcha/block page"
    except requests.RequestException as e:
        reason = f"network error: {e.__class__.__name__}"

    # 3. Download failed -> fall back to the old copy if we have one
    if cached:
        print(f"♻️  [STALE CACHE] {reason} - using saved copy of {url}")
        return cached, 1
    print(f"❌ [FETCH FAILED] {reason} for {url}")
    return "", 0


# Keep the folder from growing forever
try:
    prune_cache()
except OSError:
    pass

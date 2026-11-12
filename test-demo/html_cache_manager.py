"""
Local HTML cache for company / contact / lead pages.

Once a page has been downloaded successfully we keep a copy, so later runs don't hit the
site again (fewer requests -> fewer blocks, faster runs):

- Fresh copy (younger than HTML_CACHE_MAX_AGE_DAYS, default 30): served from disk, no request.
- Old copy: re-downloaded so changed emails/phones are picked up. If that download fails
  (403, 429, captcha, network), the old copy is used instead ("stale-if-error").
- Captcha / "access denied" pages are never cached, even when the site returns HTTP 200.
- Copies older than 3x the max age are deleted automatically, and the folder is kept under
  HTML_CACHE_MAX_MB (default 500): the oldest pages go first.
- Every saved page is listed in html_cache/index.sqlite (url, domain, saved time, size), so saved
  HTML can be re-processed later (e.g. pull GST numbers or social links) without downloading again.
  Pages saved before the index existed have no URL record; they are still used as cache hits.

On GitHub Actions the html_cache/ folder is kept between runs with actions/cache
(see .github/workflows/auto_scraper_1hr.yml); it is never committed to git.
"""

import hashlib
import os
import sqlite3
import sys
import threading
import time
from contextlib import contextmanager
from urllib.parse import urljoin, urlparse

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
CACHE_MAX_MB = float(os.getenv("HTML_CACHE_MAX_MB", "500"))
INDEX_NAME = "index.sqlite"
_index_lock = threading.Lock()

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


# ---------------------------------------------------------------------------
# Index: which URL each saved file belongs to
# ---------------------------------------------------------------------------

@contextmanager
def _index_conn():
    """Opens the index, commits on success, and always closes the file (Windows keeps it locked otherwise)."""
    conn = sqlite3.connect(os.path.join(CACHE_DIR, INDEX_NAME), timeout=10)
    try:
        conn.execute("""CREATE TABLE IF NOT EXISTS pages (
            url TEXT PRIMARY KEY, file TEXT NOT NULL, domain TEXT NOT NULL,
            saved_at REAL NOT NULL, bytes INTEGER NOT NULL)""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_pages_domain ON pages(domain)")
        yield conn
        conn.commit()
    finally:
        conn.close()


def _domain(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def _index_add(url: str, file_name: str, size: int) -> None:
    try:
        with _index_lock, _index_conn() as conn:
            conn.execute("INSERT OR REPLACE INTO pages VALUES (?, ?, ?, ?, ?)",
                         (url, file_name, _domain(url), time.time(), size))
    except sqlite3.Error as e:  # the cache must keep working even if the index is broken
        print(f"⚠️ [CACHE INDEX] could not record {url}: {e}")


def _index_remove_files(file_names: list) -> None:
    if not file_names:
        return
    try:
        with _index_lock, _index_conn() as conn:
            conn.executemany("DELETE FROM pages WHERE file = ?", [(f,) for f in file_names])
    except sqlite3.Error:
        pass


def list_cached_pages(domain: str = "") -> list:
    """Saved pages (newest first) as dicts: url, domain, path, saved_at, bytes.
    Only pages whose file still exists are returned."""
    sql, args = "SELECT url, file, domain, saved_at, bytes FROM pages", ()
    if domain:
        sql, args = sql + " WHERE domain = ?", (_domain("https://" + domain.strip().lower()),)
    try:
        with _index_lock, _index_conn() as conn:
            rows = conn.execute(sql + " ORDER BY saved_at DESC", args).fetchall()
    except sqlite3.Error:
        return []
    out = []
    for url, file_name, dom, saved_at, size in rows:
        path = os.path.join(CACHE_DIR, file_name)
        if os.path.isfile(path):
            out.append({"url": url, "domain": dom, "path": path, "saved_at": saved_at, "bytes": size})
    return out


def read_cached_html(url: str) -> str:
    """The saved HTML for url (any age), or "" if it was never saved. Never goes online."""
    path = os.path.join(CACHE_DIR, get_url_hash(url))
    try:
        return _read(path) if os.path.isfile(path) else ""
    except OSError:
        return ""


def cache_stats() -> dict:
    files = [os.path.join(CACHE_DIR, n) for n in os.listdir(CACHE_DIR) if n.endswith(".html")]
    size = sum(os.path.getsize(f) for f in files if os.path.isfile(f))
    return {"pages": len(files), "indexed": len(list_cached_pages()), "mb": round(size / 1048576, 1),
            "max_mb": CACHE_MAX_MB, "max_age_days": CACHE_MAX_AGE_DAYS}


# ---------------------------------------------------------------------------
# Clean-up
# ---------------------------------------------------------------------------

def prune_cache(max_age_days: float = None, max_mb: float = None) -> int:
    """Deletes saved pages older than max_age_days (default 3x HTML_CACHE_MAX_AGE_DAYS), then the
    oldest pages until the folder is under max_mb. Only .html files are touched. Returns count removed."""
    max_age_days = CACHE_MAX_AGE_DAYS * 3 if max_age_days is None else max_age_days
    max_bytes = (CACHE_MAX_MB if max_mb is None else max_mb) * 1048576
    pages = []
    for name in os.listdir(CACHE_DIR):
        path = os.path.join(CACHE_DIR, name)
        if name.endswith(".html") and os.path.isfile(path):
            try:
                pages.append((os.path.getmtime(path), os.path.getsize(path), name, path))
            except OSError:
                pass
    pages.sort()  # oldest first
    now, total, removed = time.time(), sum(p[1] for p in pages), []
    for mtime, size, name, path in pages:
        if (now - mtime) / 86400 > max_age_days or total > max_bytes:
            try:
                os.remove(path)
                total -= size
                removed.append(name)
            except OSError:
                pass
    _index_remove_files(removed)
    return len(removed)


class BlockedUrl(Exception):
    """Raised by a guard for a URL that must not be fetched (e.g. a private network address)."""


def _guarded_get(url: str, headers: dict, timeout: int, guard, max_bytes: int):
    """GET that checks every redirect hop with guard(url) and stops reading after max_bytes.
    Returns (status_code, text, final_url)."""
    for _ in range(5):
        guard(url)
        r = requests.get(url, headers=headers, timeout=timeout, allow_redirects=False, stream=True)
        try:
            if r.is_redirect and r.headers.get("Location"):
                url = urljoin(url, r.headers["Location"])
                continue
            body = b""
            for chunk in r.iter_content(65536):
                body += chunk
                if len(body) > max_bytes:
                    break
            return r.status_code, body[:max_bytes].decode(r.encoding or "utf-8", errors="replace"), url
        finally:
            r.close()
    raise requests.TooManyRedirects(f"too many redirects for {url}")


def fetch_page(url: str, headers: dict, guard, timeout: int = 20, max_age_days: float = None,
               max_bytes: int = 3 * 1048576) -> tuple:
    """Like fetch_or_get_cached_html, but also tells the caller what happened:
    returns (status, text, final_url, from_cache). Only a 200 page that was not redirected elsewhere and is not a
    block page is cached, so "category not found" pages (404, or a redirect to a generic page) are reported as such.
    Raises BlockedUrl / requests exceptions to the caller."""
    max_age = CACHE_MAX_AGE_DAYS if max_age_days is None else max_age_days
    cache_path = os.path.join(CACHE_DIR, get_url_hash(url))
    if os.path.exists(cache_path):
        try:
            if _age_days(cache_path) <= max_age:
                print(f"⚡ [CACHE HIT] {url}")
                return 200, _read(cache_path), url, True
        except OSError:
            pass
    print(f"🌐 [LIVE FETCH] {url}")
    status, text, final_url = _guarded_get(url, headers, timeout, guard, max_bytes)
    same_page = urlparse(final_url)._replace(query="", fragment="") == urlparse(url)._replace(query="", fragment="")
    if status == 200 and same_page and not looks_like_block_page(text):
        _write_atomic(cache_path, text)
        _index_add(url, os.path.basename(cache_path), len(text.encode("utf-8", "ignore")))
    return status, text, final_url, False


def fetch_or_get_cached_html(url: str, headers: dict = None, timeout: int = 10,
                             max_age_days: float = None, guard=None,
                             max_bytes: int = 3 * 1048576) -> tuple[str, int]:
    """
    Returns (html, 1) on success - from cache or live - and ("", 0) when nothing usable exists.
    guard: optional callable(url) that raises BlockedUrl for URLs that must not be fetched; when given,
    every redirect hop is checked and at most max_bytes are read.
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
        if guard:
            status, text, _ = _guarded_get(url, headers or DEFAULT_HEADERS, timeout, guard, max_bytes)
        else:
            response = requests.get(url, headers=headers or DEFAULT_HEADERS, timeout=timeout)
            status, text = response.status_code, response.text
        if status == 200 and not looks_like_block_page(text):
            _write_atomic(cache_path, text)
            _index_add(url, os.path.basename(cache_path), len(text.encode("utf-8", "ignore")))
            return text, 1
        reason = f"HTTP {status}" if status != 200 else "captcha/block page"
    except BlockedUrl as e:
        print(f"⛔ [BLOCKED URL] {e}")
        return "", 0
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

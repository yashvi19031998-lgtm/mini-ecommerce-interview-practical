import os
import sys
import hashlib
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

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}

def get_url_hash(url: str) -> str:
    """Generates a unique MD5 hash filename for a given URL."""
    return hashlib.md5(url.encode('utf-8')).hexdigest() + ".html"

def fetch_or_get_cached_html(url: str, headers: dict = None, timeout: int = 10) -> tuple[str, int]:
    """
    Checks local HTML cache.
    - If cached: Returns (html_content, status=1) -> NO live request!
    - If not cached: Fetches live, saves locally, returns (html_content, status=1).
    - If request fails or error occurs: Returns ("", status=0).
    """
    if not url:
        return "", 0

    file_hash = get_url_hash(url)
    cache_filepath = os.path.join(CACHE_DIR, file_hash)
    req_headers = headers or DEFAULT_HEADERS

    # 1. Cache Hit (Status = 1) -> Read locally without hitting live site
    if os.path.exists(cache_filepath):
        try:
            with open(cache_filepath, "r", encoding="utf-8") as f:
                print(f"⚡ [CACHE HIT] Status=1 | Loaded from local cache: {url}")
                return f.read(), 1
        except Exception:
            pass  # Fallback to live fetch if read fails

    # 2. Cache Miss (Status = 0 initially) -> Fetch live & store locally
    print(f"🌐 [LIVE FETCH] Status=0 | Downloading live site: {url}")
    try:
        response = requests.get(url, headers=req_headers, timeout=timeout)
        if response.status_code == 200:
            raw_html = response.text
            with open(cache_filepath, "w", encoding="utf-8") as f:
                f.write(raw_html)
            print(f"💾 [SAVED] Stored raw HTML to cache | Status=1")
            return raw_html, 1
        else:
            print(f"❌ [HTTP ERROR] Status Code: {response.status_code} for {url}")
            return "", 0
    except Exception as e:
        print(f"⚠️ [NETWORK ERROR] Failed to fetch {url}: {e}")
        return "", 0

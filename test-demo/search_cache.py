"""Saved search results for the Job Portal Scraper and CRM Sources (and later Scraping / Mining pages).

The same search (same module + same inputs, ignoring case, order and extra spaces) is answered from
the saved copy instead of hitting the sites again, until it is older than the module's time limit:

    JOB_SEARCH_CACHE_HOURS  (default 6)   - job postings change quickly
    CRM_SEARCH_CACHE_HOURS  (default 72)  - business directories change slowly
    SEARCH_ENGINE_CACHE_HOURS (default 24) - Scraping / Mining -> Search Engines

Rules:
- A search is saved only when every source answered (no "failed" source) and it found something,
  so a temporary outage or block is never served from the cache.
- The user can always bypass the cache ("Search live again" -> refresh=true).
- Entries older than SEARCH_CACHE_KEEP_DAYS (default 30) are deleted.

Stored in html_cache/search_results.sqlite, next to the page cache.
"""
import hashlib
import json
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from typing import Any, Dict, Optional, Tuple

import html_cache_manager

TTL_HOURS = {
    "jobportals": float(os.getenv("JOB_SEARCH_CACHE_HOURS", "6")),
    "crmsources": float(os.getenv("CRM_SEARCH_CACHE_HOURS", "72")),
    "searchengine": float(os.getenv("SEARCH_ENGINE_CACHE_HOURS", "24")),
    "globaldirectories": float(os.getenv("GLOBAL_DIR_CACHE_HOURS", "72")),
    "maps": float(os.getenv("MAPS_CACHE_HOURS", "72")),
    "ecommerce": float(os.getenv("ECOMMERCE_CACHE_HOURS", "48")),
    "realestate": float(os.getenv("REALESTATE_CACHE_HOURS", "72")),
    "indiandirectories": float(os.getenv("INDIAN_DIRECTORIES_CACHE_HOURS", "72")),
    "corporateregistries": float(os.getenv("CORPORATE_REGISTRIES_CACHE_HOURS", "72")),
    "whatsapp": float(os.getenv("WHATSAPP_CACHE_HOURS", "24")),
    "adlibrary": float(os.getenv("ADLIBRARY_CACHE_HOURS", "24")),
    "social": float(os.getenv("SOCIAL_CACHE_HOURS", "48")),
}
KEEP_DAYS = float(os.getenv("SEARCH_CACHE_KEEP_DAYS", "30"))
DB_NAME = "search_results.sqlite"
_lock = threading.Lock()


@contextmanager
def _conn():
    conn = sqlite3.connect(os.path.join(html_cache_manager.CACHE_DIR, DB_NAME), timeout=10)
    try:
        conn.execute("""CREATE TABLE IF NOT EXISTS searches (
            key TEXT PRIMARY KEY, module TEXT NOT NULL, params TEXT NOT NULL,
            saved_at REAL NOT NULL, result TEXT NOT NULL)""")
        yield conn
        conn.commit()
    finally:
        conn.close()


def _normalize(value: Any) -> Any:
    if isinstance(value, str):
        return " ".join(value.lower().split())
    if isinstance(value, (list, tuple, set)):
        # Items may be unhashable (a dict sent where text was expected): dedupe on their JSON form.
        items = {}
        for v in value:
            n = _normalize(v)
            if n not in ("", None):
                items.setdefault(json.dumps(n, sort_keys=True, ensure_ascii=False, default=str), n)
        return [items[k] for k in sorted(items)]
    if isinstance(value, dict):
        return {str(k): _normalize(v) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))}
    return value


def make_key(module: str, params: Dict[str, Any]) -> str:
    raw = json.dumps({"m": module, "p": _normalize(params)}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def is_cacheable(result: Dict[str, Any], status_key: str) -> bool:
    """Only complete, non-empty searches are saved."""
    statuses = (result.get(status_key) or {}).values()
    return bool(result.get("total")) and not any(s.get("status") == "error" for s in statuses)


def get(module: str, params: Dict[str, Any]) -> Optional[Tuple[Dict[str, Any], float]]:
    """(result, saved_at) if a fresh saved copy exists, else None."""
    ttl = TTL_HOURS.get(module, 0) * 3600
    if ttl <= 0:
        return None
    try:
        with _lock, _conn() as c:
            row = c.execute("SELECT saved_at, result FROM searches WHERE key = ?", (make_key(module, params),)).fetchone()
    except sqlite3.Error:
        return None
    if not row or time.time() - row[0] > ttl:
        return None
    try:
        return json.loads(row[1]), row[0]
    except ValueError:
        return None


def put(module: str, params: Dict[str, Any], result: Dict[str, Any]) -> None:
    try:
        with _lock, _conn() as c:
            c.execute("INSERT OR REPLACE INTO searches VALUES (?, ?, ?, ?, ?)",
                      (make_key(module, params), module, json.dumps(_normalize(params), ensure_ascii=False),
                       time.time(), json.dumps(result, ensure_ascii=False)))
            c.execute("DELETE FROM searches WHERE saved_at < ?", (time.time() - KEEP_DAYS * 86400,))
    except sqlite3.Error as e:  # caching must never break a search
        print(f"⚠️ [SEARCH CACHE] could not save: {e}")


def cached_search(module: str, params: Dict[str, Any], run, status_key: str, refresh: bool = False) -> Dict[str, Any]:
    """Return the saved result if fresh (unless refresh), else run() and save it when complete.
    Adds result["cache"] = {"hit": bool, "saved_at": epoch seconds or None}."""
    if not refresh:
        hit = get(module, params)
        if hit:
            result, saved_at = hit
            return {**result, "cache": {"hit": True, "saved_at": saved_at}}
    result = run()
    saved_at = None
    if is_cacheable(result, status_key):
        put(module, params, result)
        saved_at = time.time()
    return {**result, "cache": {"hit": False, "saved_at": saved_at}}

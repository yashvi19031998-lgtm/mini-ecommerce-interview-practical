"""robots.txt checks for every module that opens pages a user chose (web crawler, GST seller pages).

- robots.txt itself is fetched through the URL guard (public addresses only) with the app's honest User-Agent.
- 200 -> its rules; 401/403/404/410 -> no rules (allowed, as crawlers usually treat a missing file);
  anything else or a network error -> treated as "not allowed" (we do not guess).
"""
from functools import lru_cache
from typing import Optional
from urllib import robotparser
from urllib.parse import urlparse

import requests

import deep_search
import html_cache_manager as hcm

USER_AGENT = deep_search.HEADERS["User-Agent"]


@lru_cache(maxsize=256)
def parser_for(scheme_host: str) -> Optional[robotparser.RobotFileParser]:
    url = f"{scheme_host}/robots.txt"
    try:
        status, text, _ = hcm._guarded_get(url, deep_search.HEADERS, 10, deep_search.public_url_guard, 512 * 1024)
    except (hcm.BlockedUrl, requests.RequestException):
        return None
    rp = robotparser.RobotFileParser()
    if status == 200:
        rp.parse(text.splitlines())
    elif status in (401, 403, 404, 410):
        rp.parse([])
    else:
        return None
    return rp


def _key(url: str) -> str:
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}".lower()


def allowed(url: str) -> bool:
    rp = parser_for(_key(url))
    return bool(rp) and rp.can_fetch(USER_AGENT, url)


def crawl_delay(url: str, default: float = 1.0, cap: float = 10.0) -> float:
    rp = parser_for(_key(url))
    try:
        d = rp.crawl_delay(USER_AGENT) if rp else None
    except (AttributeError, ValueError):
        d = None
    return max(default, min(float(d), cap)) if d else default


def sitemaps(url: str) -> list:
    rp = parser_for(_key(url))
    return list(rp.site_maps() or []) if rp else []

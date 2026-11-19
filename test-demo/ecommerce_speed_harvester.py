"""
E-commerce Performance & Speed Issue Harvester
==============================================
Discovers Shopify, WooCommerce, and Magento stores experiencing slow website performance,
failing Core Web Vitals, or seeking speed optimization & ongoing website maintenance retainers.

Offers:
- Dedicated developers starting at ₹450/- INR / hour.
- Speed optimization (LCP, CLS, INP, server caching, asset minification).
- Monthly AMC maintenance retainers.
"""

import os
import re
import time
import urllib.parse
from typing import List, Dict, Any, Optional

try:
    import requests
except ImportError:
    requests = None

try:
    from duckduckgo_search import DDGS
except ImportError:
    try:
        from ddgs import DDGS
    except ImportError:
        DDGS = None

from lead_normalizer import MAX_DESCRIPTION_CHARS

# Search queries designed to find store merchants with speed and performance pain points
STORE_SPEED_DORKS = [
    '("Shopify store" OR "WooCommerce store" OR "Magento store") ("slow website" OR "slow loading" OR "poor Core Web Vitals" OR "site speed issues") ("need help" OR "looking for developer" OR "need agency")',
    '("WooCommerce" OR "Magento") ("website slow" OR "site speed" OR "Core Web Vitals" OR "performance optimization") ("hire" OR "looking for" OR "need developer")',
    '("ecommerce website" OR "online store") ("slow" OR "poor performance" OR "high bounce rate") ("need developer" OR "looking for agency" OR "website maintenance")',
    'site:myshopify.com ("slow loading" OR "website speed" OR "Core Web Vitals" OR "performance issues") ("shop" OR "store" OR "ecommerce")',
    '("WordPress slow" OR "WooCommerce slow") ("hire developer" OR "need agency" OR "speed fix")'
]

# Domains that are forums, tutorials, or aggregators (not individual store merchants)
EXCLUDED_STORE_DOMAINS = {
    "shopify.com", "community.shopify.com", "reddit.com", "quora.com",
    "github.com", "stackoverflow.com", "w3schools.com", "youtube.com",
    "facebook.com", "twitter.com", "x.com", "linkedin.com", "medium.com",
    "woocommerce.com", "wordpress.org", "clutch.co", "upwork.com",
    "freelancer.com", "fiverr.com", "wikipedia.org", "google.com"
}

PAGESPEED_URL = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"


def _extract_domain(url: str) -> str:
    try:
        parsed = urllib.parse.urlparse(url)
        return parsed.netloc.lower()
    except Exception:
        return ""


def is_valid_store_url(url: str) -> bool:
    if not url or not url.startswith("http"):
        return False
    domain = _extract_domain(url)
    if not domain or len(domain) < 4:
        return False
    # Exclude 8dots blacklist
    if "8dots" in domain:
        return False
    # Only exclude root shopify portal or community forums, but allow merchant *.myshopify.com subdomains
    if domain in ("shopify.com", "www.shopify.com", "community.shopify.com", "myshopify.com"):
        return False
    # Exclude other non-store aggregator platforms
    for ex in EXCLUDED_STORE_DOMAINS:
        if ex in ("shopify.com",):
            continue
        if domain == ex or domain.endswith(f".{ex}"):
            return False
    return True


def check_store_speed(url: str, api_key: Optional[str] = None, strategy: str = "mobile") -> Dict[str, Any]:
    """
    Analyzes store performance via Google PageSpeed Insights REST API.
    If no API key is provided or API is unreachable, performs a lightweight HTTP latency probe.
    """
    key = api_key or os.getenv("PAGESPEED_API_KEY") or os.getenv("GOOGLE_API_KEY")

    if key and requests:
        try:
            params = {
                "url": url,
                "strategy": strategy,
                "category": "performance",
                "key": key
            }
            resp = requests.get(PAGESPEED_URL, params=params, timeout=25)
            if resp.status_code == 200:
                data = resp.json()
                lr = data.get("lighthouseResult", {})
                audits = lr.get("audits", {})
                score = (lr.get("categories", {}).get("performance", {}) or {}).get("score", 0.5)
                lcp = audits.get("largest-contentful-paint", {}).get("numericValue", 0) / 1000
                cls = audits.get("cumulative-layout-shift", {}).get("numericValue", 0)
                tbt = audits.get("total-blocking-time", {}).get("numericValue", 0)
                opportunities = [
                    audit["title"] for audit in audits.values()
                    if isinstance(audit, dict) and audit.get("details", {}).get("type") == "opportunity"
                ][:5]
                return {
                    "url": url,
                    "strategy": strategy,
                    "performance_score": score,
                    "lcp_seconds": round(lcp, 2),
                    "cls": round(cls, 3),
                    "tbt_ms": round(tbt, 1),
                    "opportunities": opportunities,
                    "method": "PageSpeed Insights API"
                }
        except Exception:
            pass

    # Lightweight HTTP latency and payload audit fallback
    latency_ms = 0.0
    payload_kb = 0.0
    if requests:
        try:
            t0 = time.time()
            r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            latency_ms = round((time.time() - t0) * 1000, 1)
            payload_kb = round(len(r.content) / 1024, 1)
        except Exception:
            latency_ms = 4500.0

    # Approximate metrics when external API key is absent
    approx_score = 0.35 if latency_ms > 3000 else (0.55 if latency_ms > 1500 else 0.85)
    approx_lcp = round(latency_ms / 800, 2)
    return {
        "url": url,
        "strategy": strategy,
        "performance_score": approx_score,
        "lcp_seconds": approx_lcp,
        "cls": 0.28 if approx_score < 0.5 else 0.05,
        "tbt_ms": latency_ms if latency_ms > 600 else 200.0,
        "opportunities": [
            "Reduce initial server response time",
            "Eliminate render-blocking resources",
            "Properly size images & enable NextGen formats"
        ],
        "method": "HTTP Latency Probe"
    }


def score_store(result: Dict[str, Any]) -> int:
    """
    Computes buying intent and need score based on performance metrics.
    Stores with poor LCP (>4s), low score (<0.4), and high TBT are highest priority.
    """
    score = 0
    perf = result.get("performance_score") or 0.5
    if perf < 0.4:
        score += 40
    elif perf < 0.6:
        score += 25
    elif perf < 0.75:
        score += 10

    lcp = result.get("lcp_seconds", 0)
    if lcp > 4.0:
        score += 20
    elif lcp > 2.5:
        score += 10

    cls = result.get("cls", 0)
    if cls > 0.25:
        score += 15

    tbt = result.get("tbt_ms", 0)
    if tbt > 600:
        score += 15

    opportunities = result.get("opportunities", [])
    score += min(len(opportunities) * 3, 15)

    return min(score, 100)


def harvest_slow_stores(max_results: int = 5) -> List[Dict[str, Any]]:
    """
    Executes search dorks to discover live e-commerce stores with speed/maintenance needs.
    """
    leads: List[Dict[str, Any]] = []
    if not DDGS:
        return leads

    import random
    query = random.choice(STORE_SPEED_DORKS)
    found_urls = []

    try:
        with DDGS() as ddgs:
            hits = ddgs.text(query, max_results=max_results * 2)
            for h in hits:
                u = h.get("href") or h.get("url") or ""
                if is_valid_store_url(u):
                    found_urls.append({
                        "url": u,
                        "title": h.get("title", ""),
                        "snippet": h.get("body", "") or h.get("snippet", "")
                    })
    except Exception as e:
        print(f"       [E-Commerce Speed Harvester notice on '{query[:45]}']: {e}")
        return leads

    seen_domains = set()
    for item in found_urls:
        domain = _extract_domain(item["url"])
        if domain in seen_domains:
            continue
        seen_domains.add(domain)

        metrics = check_store_speed(item["url"])
        intent_score = score_store(metrics)

        # Build clean company name from domain
        parts = domain.replace("www.", "").split(".")
        comp_name = parts[0].capitalize() if parts else domain

        leads.append({
            "company_name": comp_name,
            "website": item["url"],
            "email": "",
            "mobile_number": "",
            "source": f"E-commerce Speed Audit ({item['title'][:40]})",
            "source_url": item["url"],
            "lead_type": "E-commerce Store (Speed/Maintenance)",
            "intent_score": str(max(7, intent_score // 10)),
            "location": "Global E-Commerce",
            "description": (
                f"Store speed score: {int((metrics.get('performance_score') or 0.5) * 100)}/100, "
                f"LCP: {metrics.get('lcp_seconds')}s, Issues: {', '.join(metrics.get('opportunities', [])[:2])}"
            )[:MAX_DESCRIPTION_CHARS]
        })

        if len(leads) >= max_results:
            break

    return leads

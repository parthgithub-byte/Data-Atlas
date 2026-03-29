"""Stealth & Evasion Module — Header randomization, cache-busting, and fingerprint rotation.

Professional OSINT systems must be undetectable to anti-bot shields.
This module provides rotating request fingerprints that mimic real browser traffic.
"""

import random
import time
import logging

logger = logging.getLogger(__name__)

# Comprehensive User-Agent pool — 24 realistic browser fingerprints
USER_AGENT_POOL = [
    # Chrome on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    # Chrome on Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    # Chrome on Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    # Firefox on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
    # Firefox on Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:133.0) Gecko/20100101 Firefox/133.0",
    # Firefox on Linux
    "Mozilla/5.0 (X11; Linux x86_64; rv:133.0) Gecko/20100101 Firefox/133.0",
    # Safari on Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    # Safari on iOS
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    # Edge on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0",
    # Edge on Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
    # Android Chrome
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36",
    # Opera
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 OPR/116.0.0.0",
    # Brave (mimics Chrome)
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Brave/131",
]

ACCEPT_LANGUAGE_POOL = [
    "en-US,en;q=0.9",
    "en-GB,en;q=0.9,en-US;q=0.8",
    "en-US,en;q=0.9,fr;q=0.8",
    "en-US,en;q=0.9,de;q=0.7",
    "en-IN,en;q=0.9,hi;q=0.8",
    "en-US,en;q=0.9,es;q=0.8,pt;q=0.7",
    "en-AU,en;q=0.9,en-US;q=0.8",
    "en-CA,en;q=0.9,fr-CA;q=0.8",
]

ACCEPT_ENCODING_POOL = [
    "gzip, deflate, br",
    "gzip, deflate, br, zstd",
    "gzip, deflate",
]

REFERER_POOL = [
    "https://www.google.com/",
    "https://www.bing.com/",
    "https://duckduckgo.com/",
    "https://search.yahoo.com/",
    "https://www.google.co.in/",
    "",  # No referer (direct navigation)
]

SEC_FETCH_DEST_POOL = ["document", "empty"]
SEC_FETCH_MODE_POOL = ["navigate", "cors", "no-cors"]


def get_stealth_headers(include_cache_bust: bool = True) -> dict:
    """Generate a complete set of randomized browser-like request headers.

    Args:
        include_cache_bust: If True, adds Cache-Control and Pragma no-cache headers.

    Returns:
        dict of HTTP headers mimicking real browser traffic.
    """
    headers = {
        "User-Agent": random.choice(USER_AGENT_POOL),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": random.choice(ACCEPT_LANGUAGE_POOL),
        "Accept-Encoding": random.choice(ACCEPT_ENCODING_POOL),
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": random.choice(SEC_FETCH_DEST_POOL),
        "Sec-Fetch-Mode": random.choice(SEC_FETCH_MODE_POOL),
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
    }

    referer = random.choice(REFERER_POOL)
    if referer:
        headers["Referer"] = referer

    if include_cache_bust:
        headers["Cache-Control"] = "no-cache"
        headers["Pragma"] = "no-cache"

    return headers


def bust_cache_url(url: str) -> str:
    """Append a unique timestamp parameter to defeat CDN caches.

    Args:
        url: The original URL.

    Returns:
        URL with a cache-busting query parameter.
    """
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}_t={int(time.time() * 1000)}"


def get_jitter(platform_risk_tier: str = "low") -> float:
    """Return a random delay (seconds) based on the platform's risk of rate-limiting.

    Args:
        platform_risk_tier: 'high' (LinkedIn, Facebook), 'medium' (Twitter, Instagram), 'low' (GitHub, Reddit)

    Returns:
        float seconds to sleep before the request.
    """
    jitter_ranges = {
        "high": (1.0, 3.0),
        "medium": (0.3, 1.0),
        "low": (0.05, 0.3),
    }
    low, high = jitter_ranges.get(platform_risk_tier, (0.05, 0.3))
    return random.uniform(low, high)

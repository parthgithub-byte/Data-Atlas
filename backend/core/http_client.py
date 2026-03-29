"""Shared HTTP client helpers for live OSINT requests."""

from __future__ import annotations

import os
import random
import time
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx


USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
]


def build_request_headers(*, no_cache: bool = True) -> dict:
    """Build realistic request headers with optional cache bypassing."""
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    if no_cache:
        headers["Cache-Control"] = "no-cache"
        headers["Pragma"] = "no-cache"
    return headers


def build_live_url(url: str, *, bust_cache: bool = True) -> str:
    """Append a lightweight cache-busting token to a URL."""
    if not bust_cache:
        return url

    split = urlsplit(url)
    query = parse_qsl(split.query, keep_blank_values=True)
    query.append(("t", str(int(time.time() * 1000))))
    return urlunsplit((split.scheme, split.netloc, split.path, urlencode(query), split.fragment))


def create_async_client(*, verify: bool = False, timeout: float | None = None) -> httpx.AsyncClient:
    """Create a shared async client with optional proxy support."""
    proxy_url = os.getenv("OUTBOUND_PROXY_URL") or None
    kwargs = {"verify": verify}
    if timeout is not None:
        kwargs["timeout"] = timeout
    if proxy_url:
        kwargs["proxy"] = proxy_url
    return httpx.AsyncClient(**kwargs)

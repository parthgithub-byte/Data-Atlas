"""Layer 2: Async Discovery Engine â€” Username enumeration plus fresh-source search."""

import asyncio
import logging
import random

import httpx

from .http_client import build_live_url, build_request_headers, create_async_client
from .platform_catalog import get_platform_rules, get_platform_rules_by_name
from .plugins import PLUGINS

logger = logging.getLogger(__name__)


PLATFORM_RULES = get_platform_rules()
SITE_TEMPLATES = [
    (rule["name"], rule["url_template"], rule["category"])
    for rule in PLATFORM_RULES
]
PLATFORM_RULES_BY_NAME = get_platform_rules_by_name()

GENERIC_MISSING_MARKERS = (
    "page not found",
    "this account doesn",
    "this page isn",
    "profile not found",
    "user not found",
    "user doesn",
    "sorry, we couldn",
    "the page you were looking for doesn",
    "not available",
    "requested page could not be found",
)

GENERIC_BAD_PATHS = (
    "/login",
    "/signup",
    "/join",
    "/accounts/login",
    "/users/sign_in",
    "/search",
    "/404",
)


async def check_username_on_site(client, username, platform, url_template, category):
    """Check if a username exists on a specific platform."""
    username = (username or "").strip().lower().lstrip("@")
    if not username:
        return None

    url = url_template.format(username)
    rule = PLATFORM_RULES_BY_NAME.get(platform, {})

    try:
        await asyncio.sleep(random.uniform(0.05, 0.3))
        response = await client.get(
            build_live_url(url),
            headers=build_request_headers(),
            follow_redirects=True,
            timeout=8.0,
        )

        if response.status_code != 200:
            return None

        final_url = str(response.url).lower().rstrip("/")
        body = response.text.lower()

        if any(path in final_url for path in GENERIC_BAD_PATHS):
            return None

        if any(marker in body for marker in GENERIC_MISSING_MARKERS):
            return None

        if len(response.content) < 300:
            return None

        if rule.get("match") == "query":
            profile_matched = f"id={username}" in final_url
        elif rule.get("match") == "subdomain":
            profile_matched = final_url.startswith(f"https://{username}.")
        else:
            profile_matched = username in final_url

        rich_data = None
        platform_key = platform.lower()
        if platform_key in PLUGINS:
            try:
                rich_data = await PLUGINS[platform_key](username, client)
            except Exception:
                rich_data = None

        if not profile_matched and not rich_data:
            return None

        result = {
            "platform": platform,
            "url": str(response.url),
            "username": username,
            "category": category,
            "confidence": rule.get("confidence", 0.75),
            "status_code": response.status_code,
        }

        if rich_data:
            result["rich_data"] = rich_data
            result["confidence"] = min(0.99, result["confidence"] + 0.05)
            if rich_data.get("last_active_at"):
                result["last_seen_at"] = rich_data.get("last_active_at")

        return result
    except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPError):
        return None


async def enumerate_usernames(usernames, max_sites=None):
    """Check a list of usernames against all known site templates."""
    if max_sites is None:
        max_sites = len(SITE_TEMPLATES)

    sites_to_check = SITE_TEMPLATES[:max_sites]
    results = []

    async with create_async_client(verify=False) as client:
        tasks = []
        for username in usernames[:8]:
            for platform, url_template, category in sites_to_check:
                tasks.append(check_username_on_site(client, username, platform, url_template, category))

        semaphore = asyncio.Semaphore(20)

        async def limited_check(task):
            async with semaphore:
                return await task

        completed = await asyncio.gather(*[limited_check(task) for task in tasks], return_exceptions=True)

        for result in completed:
            if result and not isinstance(result, Exception):
                results.append(result)

    seen_urls = set()
    unique_results = []
    for result in results:
        if result["url"] not in seen_urls:
            seen_urls.add(result["url"])
            unique_results.append(result)

    return unique_results


async def search_searxng(queries, searxng_url=None, time_range=None):
    """Query a self-hosted SearxNG instance with a recency bias."""
    if not searxng_url:
        searxng_url = "http://localhost:8888/search"

    results = []
    async with create_async_client(verify=False) as client:
        for query in queries[:5]:
            try:
                await asyncio.sleep(random.uniform(0.1, 0.5))
                params = {
                    "q": query,
                    "format": "json",
                    "engines": "google,bing,duckduckgo,github,reddit",
                    "pageno": 1,
                }
                if time_range:
                    params["time_range"] = time_range

                response = await client.get(
                    searxng_url,
                    params=params,
                    headers=build_request_headers(no_cache=False),
                    timeout=10.0,
                )
                if response.status_code == 200:
                    data = response.json()
                    for item in data.get("results", [])[:10]:
                        results.append({
                            "title": item.get("title", ""),
                            "url": item.get("url", ""),
                            "snippet": item.get("content", ""),
                            "engine": item.get("engine", "unknown"),
                            "category": "search",
                            "confidence": 0.5,
                            "last_seen_at": item.get("publishedDate") or item.get("published_date"),
                        })
            except Exception:
                continue

    seen = set()
    unique = []
    for result in results:
        if result["url"] not in seen:
            seen.add(result["url"])
            unique.append(result)

    return unique


async def check_breaches(email: str) -> list:
    """Check HIBP for email breaches and format as a discovery result."""
    from core.plugins.hibp import analyze_email

    if not email:
        return []

    try:
        async with create_async_client(verify=False) as client:
            rich_data = await analyze_email(email, client)
            if rich_data and rich_data.get("breaches"):
                return [{
                    "platform": "HaveIBeenPwned",
                    "url": f"https://haveibeenpwned.com/account/{email}",
                    "username": email,
                    "category": "breach",
                    "confidence": 1.0,
                    "status_code": 200,
                    "rich_data": rich_data,
                }]
    except Exception as exc:
        logger.warning(f"Error wrapping HIBP: {exc}")

    return []


async def run_discovery(search_bundle, searxng_url=None, searxng_enabled=False, searxng_time_range=None):
    """Run the full Quick Mode discovery: enumeration and search in parallel."""
    tasks = [enumerate_usernames(search_bundle.username_variants)]

    if search_bundle.email:
        tasks.append(check_breaches(search_bundle.email))

    if searxng_enabled and searxng_url:
        tasks.append(search_searxng(search_bundle.search_queries, searxng_url, searxng_time_range))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_results = []
    for result in results:
        if isinstance(result, list):
            all_results.extend(result)

    seen_urls = set()
    unique = []
    for result in all_results:
        url = result.get("url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique.append(result)

    return unique

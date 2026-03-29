"""Shared platform catalog loader for discovery, editing, and query generation."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path


DEFAULT_PLATFORM_CATALOG_PATH = Path(__file__).with_name("platform_catalog.json")
PLATFORM_CATALOG_ENV_VAR = "PLATFORM_CATALOG_PATH"
VALID_MATCH_TYPES = {"path", "query", "subdomain"}


def _catalog_path() -> Path:
    configured_path = os.getenv(PLATFORM_CATALOG_ENV_VAR)
    if configured_path:
        return Path(configured_path).expanduser()
    return DEFAULT_PLATFORM_CATALOG_PATH


def get_platform_catalog_path() -> Path:
    """Return the active platform catalog path."""
    return _catalog_path()


def clear_platform_catalog_cache() -> None:
    """Clear the cached platform catalog."""
    load_platform_catalog.cache_clear()


def _platform_list(raw_data) -> list[dict]:
    platforms = raw_data.get("platforms", raw_data)
    if not isinstance(platforms, list):
        raise ValueError("Catalog must be a list or an object with a 'platforms' list.")
    return platforms


def validate_platform_catalog(raw_data) -> list[dict]:
    """Validate and normalize catalog entries."""
    normalized = []
    seen_names = set()

    for index, entry in enumerate(_platform_list(raw_data), start=1):
        if not isinstance(entry, dict):
            raise ValueError(f"Entry {index} must be an object.")

        item = dict(entry)
        item["name"] = str(item.get("name", "")).strip()
        item["url_template"] = str(item.get("url_template", "")).strip()
        item["category"] = str(item.get("category", "other")).strip() or "other"
        item["match"] = str(item.get("match", "path")).strip() or "path"
        item["dork_site"] = str(item.get("dork_site", "")).strip()
        item["enumerate"] = bool(item.get("enumerate", True))
        item["search_priority"] = bool(item.get("search_priority", False))

        if not item["name"]:
            raise ValueError(f"Entry {index} is missing a platform name.")
        if item["name"] in seen_names:
            raise ValueError(f"Duplicate platform name: {item['name']}.")
        seen_names.add(item["name"])

        if not item["url_template"]:
            raise ValueError(f"{item['name']} is missing a url_template.")
        if item["url_template"].count("{}") != 1:
            raise ValueError(f"{item['name']} url_template must contain exactly one '{{}}' placeholder.")
        if item["match"] not in VALID_MATCH_TYPES:
            raise ValueError(
                f"{item['name']} has invalid match type '{item['match']}'. "
                f"Use one of: {', '.join(sorted(VALID_MATCH_TYPES))}."
            )

        try:
            item["confidence"] = float(item.get("confidence", 0.75))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{item['name']} confidence must be a number.") from exc

        if not 0 <= item["confidence"] <= 1:
            raise ValueError(f"{item['name']} confidence must be between 0 and 1.")

        normalized.append(item)

    if not normalized:
        raise ValueError("Catalog must contain at least one platform.")

    return normalized


@lru_cache(maxsize=1)
def load_platform_catalog() -> list[dict]:
    """Load the platform catalog from JSON."""
    path = get_platform_catalog_path()
    with path.open("r", encoding="utf-8") as handle:
        raw_data = json.load(handle)
    return validate_platform_catalog(raw_data)


def save_platform_catalog(raw_data) -> list[dict]:
    """Validate and persist the platform catalog."""
    normalized = validate_platform_catalog(raw_data)
    path = get_platform_catalog_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"platforms": normalized}
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
    clear_platform_catalog_cache()
    return normalized


def get_platform_catalog_document() -> dict:
    """Return the normalized catalog document."""
    return {"platforms": load_platform_catalog()}


def get_platform_catalog_summary(catalog: list[dict] | None = None) -> dict:
    """Summarize the current platform catalog for the admin UI."""
    platforms = catalog or load_platform_catalog()
    categories = {}
    for rule in platforms:
        category = rule.get("category", "other")
        categories[category] = categories.get(category, 0) + 1

    return {
        "total_platforms": len(platforms),
        "enumerated_platforms": sum(1 for rule in platforms if rule.get("enumerate", True)),
        "search_priority_platforms": sum(1 for rule in platforms if rule.get("search_priority")),
        "categories": categories,
    }


def get_platform_rules() -> list[dict]:
    """Return platforms that support direct profile enumeration."""
    return [rule for rule in load_platform_catalog() if rule.get("enumerate", True)]


def get_platform_rules_by_name() -> dict[str, dict]:
    """Index platform rules by platform name."""
    return {rule["name"]: rule for rule in get_platform_rules()}


def get_dork_platforms() -> list[tuple[str, str]]:
    """Return search-engine dork targets from the shared catalog."""
    platforms = []
    for rule in load_platform_catalog():
        dork_site = rule.get("dork_site")
        if dork_site:
            platforms.append((dork_site, rule.get("category", "other")))
    return platforms


def get_priority_search_domains(limit: int | None = None) -> list[str]:
    """Return high-priority domains to bias targeted search queries."""
    domains = []
    for rule in load_platform_catalog():
        if rule.get("search_priority") and rule.get("dork_site"):
            domains.append(rule["dork_site"])
    if limit is not None:
        return domains[:limit]
    return domains

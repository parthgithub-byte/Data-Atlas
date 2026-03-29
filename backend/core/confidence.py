"""Confidence and recency scoring for discovered OSINT artifacts."""

from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime


NAME_TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9]+")


class ConfidenceScorer:
    """Compute weighted match probability for a discovered result."""

    DEFAULT_WEIGHTS = {
        "username": 0.45,
        "contact": 0.40,
        "context": 0.15,
    }

    @classmethod
    def score(cls, scan, result_payload, page_payload=None, entities=None):
        """Return weighted match scoring and recency metadata."""
        reasons = []

        username_score, username_reason = cls._score_username(scan, result_payload)
        if username_reason:
            reasons.append(username_reason)

        contact_score, contact_reason = cls._score_contact(scan, result_payload, entities)
        if contact_reason:
            reasons.append(contact_reason)

        context_score, context_reason = cls._score_context(scan, result_payload, page_payload)
        if context_reason:
            reasons.append(context_reason)

        weights = cls.DEFAULT_WEIGHTS
        base_score = (
            (weights["username"] * username_score)
            + (weights["contact"] * contact_score)
            + (weights["context"] * context_score)
        )

        if contact_score >= 1.0:
            base_score = max(base_score, 0.95)
        elif username_score >= 1.0 and context_score >= 0.7:
            base_score = max(base_score, 0.85)
        elif username_score >= 1.0 and (result_payload.get("rich_data") or page_payload):
            base_score = max(base_score, 0.72)

        last_seen_at = cls._extract_last_seen_at(result_payload, page_payload)
        recency_multiplier = cls._recency_multiplier(last_seen_at)
        score = max(0.0, min(1.0, round(base_score * recency_multiplier, 4)))

        return {
            "score": score,
            "base_score": round(base_score, 4),
            "username_signal": round(username_score, 4),
            "contact_signal": round(contact_score, 4),
            "context_signal": round(context_score, 4),
            "last_seen_at": last_seen_at.isoformat() if last_seen_at else None,
            "activity_status": cls._activity_status(last_seen_at),
            "recency_multiplier": round(recency_multiplier, 4),
            "reasons": reasons,
        }

    @staticmethod
    def _normalize(value):
        return (value or "").strip().lower()

    @classmethod
    def _score_username(cls, scan, result_payload):
        target_username = cls._normalize(scan.target_username)
        result_username = cls._normalize(result_payload.get("username"))
        generated_variants = {
            cls._normalize(value)
            for value in result_payload.get("generated_variants", []) or []
        }

        if target_username and result_username and target_username == result_username:
            return 1.0, "Exact username match."

        if target_username and result_username and target_username.replace(".", "").replace("_", "").replace("-", "") == result_username.replace(".", "").replace("_", "").replace("-", ""):
            return 0.85, "Normalized username match."

        if result_username and result_username in generated_variants:
            return 0.65, "Matched a generated username variant."

        if result_username:
            return 0.15, "Profile exists but username match is weak."

        return 0.0, None

    @classmethod
    def _score_contact(cls, scan, result_payload, entities):
        emails = set(result_payload.get("emails_found") or [])
        phones = set(result_payload.get("phones_found") or [])

        if entities:
            emails.update(entities.emails)
            phones.update(entities.phones)

        target_email = cls._normalize(scan.target_email)
        target_phone = re.sub(r"\D", "", scan.target_phone or "")

        if target_email and target_email in {cls._normalize(email) for email in emails}:
            return 1.0, "Target email found on the result."

        if target_phone and target_phone in {re.sub(r"\D", "", phone) for phone in phones}:
            return 1.0, "Target phone number found on the result."

        if target_email and result_payload.get("username"):
            email_local = target_email.split("@")[0]
            result_username = cls._normalize(result_payload.get("username"))
            if email_local and email_local == result_username:
                return 0.35, "Result username matches the target email local-part."

        return 0.0, None

    @classmethod
    def _score_context(cls, scan, result_payload, page_payload):
        haystack_parts = [
            result_payload.get("display_name") or "",
            result_payload.get("bio") or "",
        ]

        rich_data = result_payload.get("rich_data") or {}
        haystack_parts.extend([
            rich_data.get("bio") or "",
            rich_data.get("location") or "",
            rich_data.get("company") or "",
        ])

        if page_payload:
            haystack_parts.extend([
                page_payload.get("text") or "",
                (page_payload.get("meta") or {}).get("title") or "",
                (page_payload.get("meta") or {}).get("description") or "",
            ])

        haystack = " ".join(part for part in haystack_parts if part).lower()
        target_tokens = {
            token
            for token in NAME_TOKEN_PATTERN.findall((scan.target_name or "").lower())
            if len(token) > 2
        }

        if not target_tokens or not haystack:
            return 0.0, None

        matches = sum(1 for token in target_tokens if token in haystack)
        coverage = matches / len(target_tokens)

        if coverage >= 1.0:
            return 1.0, "Target name tokens all appeared in page context."
        if coverage >= 0.6:
            return 0.7, "Most target name tokens appeared in page context."
        if coverage > 0:
            return 0.3, "Some target name tokens appeared in page context."

        return 0.0, None

    @staticmethod
    def _extract_last_seen_at(result_payload, page_payload):
        rich_data = result_payload.get("rich_data") or {}
        candidates = [
            rich_data.get("last_active_at"),
            rich_data.get("updated_at"),
            rich_data.get("created_at"),
            result_payload.get("last_seen_at"),
        ]

        if page_payload:
            candidates.extend([
                page_payload.get("retrieved_at"),
                page_payload.get("last_modified"),
            ])

        for value in candidates:
            parsed = ConfidenceScorer._parse_datetime(value)
            if parsed:
                return parsed
        return None

    @staticmethod
    def _parse_datetime(value):
        if not value:
            return None

        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value, tz=timezone.utc)

        if isinstance(value, str):
            cleaned = value.strip()
            if cleaned.endswith("Z"):
                cleaned = cleaned[:-1] + "+00:00"
            try:
                parsed = datetime.fromisoformat(cleaned)
                return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
            except ValueError:
                try:
                    parsed = parsedate_to_datetime(value)
                    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
                except (TypeError, ValueError):
                    return None

        return None

    @staticmethod
    def _recency_multiplier(last_seen_at):
        if not last_seen_at:
            return 1.0

        age_days = max(0.0, (datetime.now(timezone.utc) - last_seen_at).total_seconds() / 86400.0)
        decay_lambda = 1 / 45.0
        return max(0.45, math.exp(-decay_lambda * age_days))

    @staticmethod
    def _activity_status(last_seen_at):
        if not last_seen_at:
            return "unknown"

        age_days = max(0.0, (datetime.now(timezone.utc) - last_seen_at).total_seconds() / 86400.0)
        if age_days <= 1:
            return "active"
        if age_days <= 30:
            return "recent"
        return "historical"

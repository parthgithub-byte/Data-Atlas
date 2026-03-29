"""Shared scan pipeline used by local threads and Celery workers."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from config import Config
from database import IdentityEdge, IdentityNode, Scan, ScanResult, db
from core.confidence import ConfidenceScorer
from core.discovery import run_discovery
from core.evidence import archive_result_evidence
from core.extractor import extract_entities, extract_from_snippet
from core.graph_builder import IdentityGraphBuilder
from core.normalizer import IdentityNormalizer
from core.scraper import scrape_urls

logger = logging.getLogger(__name__)


def _coerce_datetime(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        cleaned = value.replace("Z", "+00:00")
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


def _update_scan(scan, *, status=None, current_stage=None, progress=None, execution_backend=None, task_id=None):
    if status is not None:
        scan.status = status
    if current_stage is not None:
        scan.current_stage = current_stage
    if progress is not None:
        scan.progress = progress
    if execution_backend is not None:
        scan.execution_backend = execution_backend
    if task_id is not None:
        scan.task_id = task_id
    db.session.commit()


def _merge_contact_values(existing_json, new_values):
    existing = set(json.loads(existing_json) if existing_json else [])
    existing.update(new_values)
    return json.dumps(sorted(existing)) if existing else None


def _build_result_metadata(discovered_item, page=None, score_data=None):
    metadata = {
        "discovery_confidence": discovered_item.get("confidence"),
        "engine": discovered_item.get("engine"),
        "rich_data": discovered_item.get("rich_data", {}),
    }
    if score_data:
        metadata["base_score"] = score_data.get("base_score")
        metadata["activity_status"] = score_data.get("activity_status")
        metadata["recency_multiplier"] = score_data.get("recency_multiplier")
        metadata["signals"] = {
            "username": score_data.get("username_signal"),
            "contact": score_data.get("contact_signal"),
            "context": score_data.get("context_signal"),
        }
    if discovered_item.get("snippet"):
        metadata["snippet"] = discovered_item.get("snippet")
    if page:
        metadata["page_meta"] = page.get("meta", {})
        metadata["links"] = page.get("links", [])[:10]
        metadata["forensics"] = page.get("forensics", [])
        metadata["retrieved_at"] = page.get("retrieved_at")
        metadata["last_modified"] = page.get("last_modified")
    return metadata


def _should_archive(result, metadata):
    forensic_hits = metadata.get("forensics") or []
    has_sensitive_contacts = bool(result.emails_found or result.phones_found)
    high_match = (result.match_score or 0) >= 0.8
    return has_sensitive_contacts or bool(forensic_hits) or high_match


def run_scan_pipeline(scan_id: int, *, execution_backend: str = "thread", task_id: str | None = None):
    """Run the full scan pipeline for an existing scan record."""
    scan = db.session.get(Scan, scan_id)
    if not scan:
        return

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        _update_scan(
            scan,
            status="running",
            current_stage="Normalizing identity",
            progress=5,
            execution_backend=execution_backend,
            task_id=task_id,
        )

        bundle = IdentityNormalizer.create_search_bundle(
            name=scan.target_name,
            email=scan.target_email,
            username=scan.target_username,
            phone=scan.target_phone,
        )

        _update_scan(scan, current_stage="Running discovery", progress=15)

        discovered = loop.run_until_complete(
            run_discovery(
                bundle,
                Config.SEARXNG_URL,
                Config.SEARXNG_ENABLED,
                Config.SEARXNG_TIME_RANGE,
            )
        )

        _update_scan(scan, current_stage="Processing discovered profiles", progress=40)
        scan.platforms_found = len(discovered)
        db.session.commit()

        result_lookup = {}
        all_entities = []

        for item in discovered:
            snippet_entities = extract_from_snippet(item.get("snippet", ""), item.get("url", ""))
            all_entities.append(snippet_entities)

            scoring_payload = dict(item)
            scoring_payload["generated_variants"] = bundle.username_variants
            score_data = ConfidenceScorer.score(scan, scoring_payload, entities=snippet_entities)
            metadata = _build_result_metadata(item, score_data=score_data)

            result = ScanResult(
                scan_id=scan.id,
                platform=item.get("platform", "unknown"),
                url=item.get("url", ""),
                username=item.get("username", ""),
                confidence=score_data["score"],
                match_score=score_data["score"],
                match_reasons=json.dumps(score_data["reasons"]),
                metadata_json=json.dumps(metadata),
                category=item.get("category", "other"),
                last_seen_at=_coerce_datetime(score_data.get("last_seen_at")),
            )

            if snippet_entities.emails:
                result.emails_found = json.dumps(sorted(snippet_entities.emails))
            if snippet_entities.phones:
                result.phones_found = json.dumps(sorted(snippet_entities.phones))

            db.session.add(result)
            db.session.flush()
            result_lookup[item.get("url", "")] = {
                "result": result,
                "item": item,
                "score_data": score_data,
            }

        db.session.commit()

        if scan.mode == "full" and discovered:
            _update_scan(scan, current_stage="Scraping discovered pages", progress=55)
            urls_to_scrape = [item["url"] for item in discovered[: Config.MAX_FULL_SCAN_URLS]]
            scraped_pages = loop.run_until_complete(
                scrape_urls(urls_to_scrape, timeout=Config.REQUEST_TIMEOUT)
            )

            _update_scan(scan, current_stage="Extracting entities", progress=70)

            for page in scraped_pages:
                entities = extract_entities(page["text"], page.get("final_url") or page["url"])
                all_entities.append(entities)

                lookup_key = page.get("url", "")
                matched = result_lookup.get(lookup_key) or result_lookup.get(page.get("final_url", ""))
                if not matched:
                    continue

                result = matched["result"]
                discovered_item = matched["item"]
                scoring_payload = dict(discovered_item)
                scoring_payload["generated_variants"] = bundle.username_variants
                scoring_payload["display_name"] = page.get("meta", {}).get("title")
                scoring_payload["bio"] = page.get("meta", {}).get("description")

                score_data = ConfidenceScorer.score(scan, scoring_payload, page_payload=page, entities=entities)
                metadata = _build_result_metadata(discovered_item, page=page, score_data=score_data)

                result.url = page.get("final_url") or result.url
                result.display_name = page.get("meta", {}).get("title") or result.display_name
                result.bio = page.get("meta", {}).get("description") or result.bio
                result.raw_text = page["text"][:2000]
                result.confidence = score_data["score"]
                result.match_score = score_data["score"]
                result.match_reasons = json.dumps(score_data["reasons"])
                result.metadata_json = json.dumps(metadata)
                result.last_seen_at = _coerce_datetime(score_data.get("last_seen_at"))

                if entities.emails:
                    result.emails_found = _merge_contact_values(result.emails_found, sorted(entities.emails))
                    result.risk_level = "high"
                if entities.phones:
                    result.phones_found = _merge_contact_values(result.phones_found, sorted(entities.phones))
                    result.risk_level = "critical"

                if _should_archive(result, metadata):
                    result.evidence_path = archive_result_evidence(
                        scan.id,
                        result.id,
                        {
                            "scan_id": scan.id,
                            "result_id": result.id,
                            "platform": result.platform,
                            "url": result.url,
                            "match_score": result.match_score,
                            "retrieved_at": page.get("retrieved_at"),
                            "last_modified": page.get("last_modified"),
                            "forensics": metadata.get("forensics", []),
                            "emails_found": json.loads(result.emails_found) if result.emails_found else [],
                            "phones_found": json.loads(result.phones_found) if result.phones_found else [],
                            "page_meta": page.get("meta", {}),
                            "text_excerpt": page.get("text", "")[:1000],
                        },
                    )

            db.session.commit()

        _update_scan(scan, current_stage="Building identity graph", progress=85)

        graph_builder = IdentityGraphBuilder()
        entities_dicts = [
            entity.to_dict() if hasattr(entity, "to_dict") else entity
            for entity in all_entities
        ]

        graph_builder.build_from_scan_results(
            target_name=scan.target_name,
            target_email=scan.target_email or "",
            target_username=scan.target_username or "",
            results=discovered,
            entities_list=entities_dicts,
        )

        cytoscape_data = graph_builder.to_cytoscape_json()
        for node in cytoscape_data.get("nodes", []):
            data = node["data"]
            db.session.add(
                IdentityNode(
                    scan_id=scan.id,
                    node_id=data["id"],
                    node_type=data.get("type", "unknown"),
                    label=data.get("label", ""),
                    risk_level=data.get("risk_level", "low"),
                    metadata_json=json.dumps(
                        {
                            key: value
                            for key, value in data.items()
                            if key not in ("id", "type", "label", "risk_level", "color", "shape")
                        }
                    ),
                )
            )

        for edge in cytoscape_data.get("edges", []):
            data = edge["data"]
            db.session.add(
                IdentityEdge(
                    scan_id=scan.id,
                    source_id=data["source"],
                    target_id=data["target"],
                    relationship=data.get("relationship", "related"),
                    confidence=data.get("confidence", 0.5),
                )
            )

        _update_scan(scan, current_stage="Generating risk report", progress=95)

        scan.risk_score = graph_builder.calculate_risk_score()
        scan.entities_found = sum(
            len(entity.get("emails", [])) + len(entity.get("phones", [])) + len(entity.get("handles", []))
            for entity in entities_dicts
        )
        scan.status = "completed"
        scan.progress = 100
        scan.current_stage = "Scan complete"
        scan.completed_at = datetime.now(timezone.utc)
        db.session.commit()

    except Exception:
        logger.exception("Worker scan pipeline failed for scan %s", scan_id)
        scan.status = "failed"
        scan.current_stage = "Scan failed"
        db.session.commit()
    finally:
        loop.close()

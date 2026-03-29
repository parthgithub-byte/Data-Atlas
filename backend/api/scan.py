"""Scan API routes — Initiate and monitor scans."""

import asyncio
import json
import logging
import threading
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify, g, current_app
from database import db, Scan, ScanResult, IdentityNode, IdentityEdge
from auth.middleware import get_owned_scan, require_auth
from core.normalizer import IdentityNormalizer
from core.discovery import run_discovery
from core.scraper import scrape_urls
from core.extractor import extract_entities, extract_from_snippet
from core.graph_builder import IdentityGraphBuilder
from core.reporter import ReportGenerator
from core.confidence import ConfidenceScorer
from core.evidence import archive_result_evidence
from core.metadata_extractor import extract_file_metadata, is_binary_content

scan_bp = Blueprint("scan", __name__, url_prefix="/api/scan")
logger = logging.getLogger(__name__)


def _risk_from_confidence(score: float) -> str:
    """Map a confidence match score to a risk tier."""
    if score >= 0.85:
        return "high"
    if score >= 0.65:
        return "medium"
    return "low"


def _normalize_name(value):
    return " ".join((value or "").strip().lower().split())


def _normalize_email(value):
    return (value or "").strip().lower()


def _is_placeholder_email(value):
    return _normalize_email(value).endswith("@digilocker.gov.in")


def _as_bool(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _prepare_scan_identity(user, payload):
    """Prepare a scan payload while enforcing self-scan-only restrictions."""
    if not isinstance(payload, dict):
        return None, ("Request body required", 400)

    trusted_name = (user.full_name or "").strip()
    trusted_email = _normalize_email(user.email)
    target_username = (payload.get("username") or "").strip() or None
    target_phone = (payload.get("phone") or "").strip() or None

    if not trusted_name:
        return None, ("Your account profile is missing a full name. Update your account before scanning.", 400)

    if current_app.config.get("SELF_SCAN_ONLY", True):
        if not _as_bool(payload.get("self_attested")):
            return None, (
                "Self-scan confirmation is required. You cannot scan another person's data.",
                400,
            )

        supplied_name = payload.get("name")
        supplied_email = payload.get("email")

        if supplied_name and _normalize_name(supplied_name) != _normalize_name(trusted_name):
            logger.warning("Blocked non-self scan attempt for user %s due to name mismatch", user.id)
            return None, (
                "You cannot scan another person's identity. Scans are limited to your signed-in profile.",
                403,
            )

        if supplied_email and _normalize_email(supplied_email) != trusted_email:
            logger.warning("Blocked non-self scan attempt for user %s due to email mismatch", user.id)
            return None, (
                "You cannot scan another person's email. Use the email on your signed-in account only.",
                403,
            )

        target_name = trusted_name
        target_email = None if _is_placeholder_email(trusted_email) else trusted_email or None
    else:
        target_name = (payload.get("name") or "").strip()
        target_email = _normalize_email(payload.get("email")) or None
        if not target_name:
            return None, ("Target name is required", 400)

    return {
        "target_name": target_name,
        "target_email": target_email,
        "target_username": target_username,
        "target_phone": target_phone,
        "target_address": (payload.get("address") or "").strip() or None,
    }, None


def _start_scan(mode):
    """Create a scan record and queue its background pipeline."""
    data = request.get_json(silent=True)
    scan_identity, error = _prepare_scan_identity(g.current_user, data)
    if error:
        message, status_code = error
        return jsonify({"error": message}), status_code

    scan = Scan(
        user_id=g.current_user.id,
        target_name=scan_identity["target_name"],
        target_email=scan_identity["target_email"],
        target_username=scan_identity["target_username"],
        target_phone=scan_identity["target_phone"],
        target_address=scan_identity["target_address"],
        mode=mode,
        status="pending",
    )
    db.session.add(scan)
    db.session.commit()

    app = current_app._get_current_object()
    thread = threading.Thread(target=run_scan_pipeline, args=(app, scan.id))
    thread.daemon = True
    thread.start()

    return scan


def run_scan_pipeline(app, scan_id):
    """Run the full scan pipeline in a background thread."""
    with app.app_context():
        scan = db.session.get(Scan, scan_id)
        if not scan:
            return

        try:
            scan.status = "running"
            scan.current_stage = "Normalizing identity"
            scan.progress = 5
            db.session.commit()

            # === Layer 1: Normalize identity ===
            bundle = IdentityNormalizer.create_search_bundle(
                name=scan.target_name,
                email=scan.target_email,
                username=scan.target_username,
                phone=scan.target_phone,
                address=getattr(scan, 'target_address', None),
            )

            scan.current_stage = "Running discovery"
            scan.progress = 15
            db.session.commit()

            # === Layer 2: Async Discovery ===
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            searxng_url = current_app.config.get("SEARXNG_URL")
            searxng_enabled = current_app.config.get("SEARXNG_ENABLED", False)

            # Real-time: use recency filter — "day" for full, "month" for quick
            time_range = "day" if scan.mode == "full" else "month"

            discovered = loop.run_until_complete(
                run_discovery(
                    bundle,
                    searxng_url,
                    searxng_enabled,
                    searxng_time_range=time_range,
                )
            )

            scan.current_stage = "Scoring and storing discoveries"
            scan.progress = 40
            scan.platforms_found = len(discovered)
            db.session.commit()

            # === Layer 3: Store results with confidence scores ===
            all_entities = []
            stored_results: list[ScanResult] = []

            for item in discovered:
                result = ScanResult(
                    scan_id=scan.id,
                    platform=item.get("platform", "unknown"),
                    url=item.get("url", ""),
                    username=item.get("username", ""),
                    confidence=item.get("confidence", 0.5),
                    category=item.get("category", "other"),
                )

                # Extract entities from snippet if available
                snippet = item.get("snippet", "")
                if snippet:
                    snippet_entities = extract_from_snippet(snippet, item.get("url", ""))
                    if snippet_entities.emails:
                        result.emails_found = json.dumps(list(snippet_entities.emails))
                        result.risk_level = "high"
                    if snippet_entities.phones:
                        result.phones_found = json.dumps(list(snippet_entities.phones))
                        result.risk_level = "critical"
                    all_entities.append(snippet_entities)

                # === Confidence Scoring (quick-mode uses snippet/rich_data only) ===
                try:
                    scoring = ConfidenceScorer.score(
                        scan=scan,
                        result_payload=item,
                        page_payload=None,
                        entities=None,
                    )
                    result.match_score = scoring["score"]
                    result.match_reasons = json.dumps(scoring["reasons"])

                    # Persist last_seen_at if the scorer found a timestamp
                    if scoring.get("last_seen_at"):
                        try:
                            result.last_seen_at = datetime.fromisoformat(scoring["last_seen_at"])
                        except (ValueError, TypeError):
                            pass

                    # Upgrade risk level from confidence signal unless already critical
                    if result.risk_level not in ("critical", "high"):
                        result.risk_level = _risk_from_confidence(scoring["score"])

                except Exception:
                    pass  # Never let scoring crash the pipeline

                db.session.add(result)
                stored_results.append(result)

            db.session.commit()

            # Archive evidence for high/critical quick-mode results
            for result in stored_results:
                if result.risk_level in ("critical", "high"):
                    try:
                        payload = result.to_dict()
                        path = archive_result_evidence(scan.id, result.id, payload)
                        result.evidence_path = path
                    except Exception:
                        pass

            db.session.commit()

            # === Layer 4: Scrape (Full Mode only) ===
            scraped_data = []
            if scan.mode == "full" and discovered:
                scan.current_stage = "Scraping discovered pages"
                scan.progress = 55
                db.session.commit()

                urls_to_scrape = [d["url"] for d in discovered[:20]]
                scraped_data = loop.run_until_complete(scrape_urls(urls_to_scrape))

                scan.current_stage = "Extracting entities & metadata"
                scan.progress = 70
                db.session.commit()

                # === Layer 5: Extract entities + metadata from scraped pages ===
                for page in scraped_data:
                    page_url = page["url"]
                    content_type = page.get("content_type", "") or ""

                    # Binary content → metadata extraction
                    if is_binary_content(content_type, page_url):
                        content_bytes = page.get("content_bytes") or b""
                        if content_bytes:
                            try:
                                file_meta = extract_file_metadata(page_url, content_bytes, content_type)
                                if file_meta:
                                    for sr in stored_results:
                                        if sr.url == page_url:
                                            sr.metadata_json = json.dumps(file_meta)
                                            break
                            except Exception:
                                pass
                        continue

                    entities = extract_entities(page["text"], page_url)
                    all_entities.append(entities)

                    # Update results with scraped page data + re-score with full context
                    for sr in stored_results:
                        if sr.url != page_url:
                            continue

                        sr.raw_text = page["text"][:2000]
                        if page.get("meta", {}).get("title"):
                            sr.display_name = page["meta"]["title"]
                        if page.get("meta", {}).get("description"):
                            sr.bio = page["meta"]["description"]
                        if entities.emails:
                            sr.emails_found = json.dumps(sorted(entities.emails))
                            sr.risk_level = "high"
                        if entities.phones:
                            sr.phones_found = json.dumps(sorted(entities.phones))
                            sr.risk_level = "critical"

                        # Re-score with full page context
                        try:
                            # Reconstruct result payload for scoring
                            result_payload = {
                                "platform": sr.platform,
                                "url": sr.url,
                                "username": sr.username,
                                "display_name": sr.display_name,
                                "bio": sr.bio,
                                "emails_found": json.loads(sr.emails_found) if sr.emails_found else [],
                                "phones_found": json.loads(sr.phones_found) if sr.phones_found else [],
                            }
                            # Reattach rich_data from original discovery item
                            for disc_item in discovered:
                                if disc_item.get("url") == sr.url:
                                    result_payload["rich_data"] = disc_item.get("rich_data", {})
                                    break

                            page_payload = {
                                "text": page["text"],
                                "meta": page.get("meta", {}),
                                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                            }

                            scoring = ConfidenceScorer.score(
                                scan=scan,
                                result_payload=result_payload,
                                page_payload=page_payload,
                                entities=entities,
                            )
                            sr.match_score = scoring["score"]
                            sr.match_reasons = json.dumps(scoring["reasons"])

                            if scoring.get("last_seen_at"):
                                try:
                                    sr.last_seen_at = datetime.fromisoformat(scoring["last_seen_at"])
                                except (ValueError, TypeError):
                                    pass

                            if sr.risk_level not in ("critical", "high"):
                                sr.risk_level = _risk_from_confidence(scoring["score"])

                        except Exception:
                            pass

                        break  # Only one result per URL

                # Archive evidence for full-mode high/critical results
                for sr in stored_results:
                    if sr.risk_level in ("critical", "high") and not sr.evidence_path:
                        try:
                            payload = sr.to_dict()
                            path = archive_result_evidence(scan.id, sr.id, payload)
                            sr.evidence_path = path
                        except Exception:
                            pass

                db.session.commit()

            # === Layer 6: Build identity graph ===
            scan.current_stage = "Building identity graph"
            scan.progress = 85
            db.session.commit()

            graph_builder = IdentityGraphBuilder()
            entities_dicts = [
                e.to_dict() if hasattr(e, "to_dict") else e
                for e in all_entities
            ]

            graph_builder.build_from_scan_results(
                target_name=scan.target_name,
                target_email=scan.target_email or "",
                target_username=scan.target_username or "",
                results=discovered,
                entities_list=entities_dicts,
            )

            # Store graph nodes
            cytoscape_data = graph_builder.to_cytoscape_json()
            for node in cytoscape_data.get("nodes", []):
                nd = node["data"]
                identity_node = IdentityNode(
                    scan_id=scan.id,
                    node_id=nd["id"],
                    node_type=nd.get("type", "unknown"),
                    label=nd.get("label", ""),
                    risk_level=nd.get("risk_level", "low"),
                    metadata_json=json.dumps({k: v for k, v in nd.items()
                                              if k not in ("id", "type", "label", "risk_level", "color", "shape")}),
                )
                db.session.add(identity_node)

            for edge in cytoscape_data.get("edges", []):
                ed = edge["data"]
                identity_edge = IdentityEdge(
                    scan_id=scan.id,
                    source_id=ed["source"],
                    target_id=ed["target"],
                    relationship=ed.get("relationship", "related"),
                    confidence=ed.get("confidence", 0.5),
                )
                db.session.add(identity_edge)

            # === Layer 7: Generate report ===
            scan.current_stage = "Generating risk report"
            scan.progress = 95
            db.session.commit()

            risk_score = graph_builder.calculate_risk_score()
            scan.risk_score = risk_score
            scan.entities_found = sum(
                len(e.get("emails", [])) + len(e.get("phones", [])) + len(e.get("handles", []))
                for e in entities_dicts
            )

            # Mark complete
            scan.status = "completed"
            scan.progress = 100
            scan.current_stage = "Scan complete"
            scan.completed_at = datetime.now(timezone.utc)
            db.session.commit()

            loop.close()

        except Exception:
            logger.exception("Scan pipeline failed for scan %s", scan_id)
            scan.status = "failed"
            scan.current_stage = "Scan failed"
            db.session.commit()


@scan_bp.route("/quick", methods=["POST"])
@require_auth
def start_quick_scan():
    """Start a Quick Mode scan."""
    scan = _start_scan("quick")
    if not isinstance(scan, Scan):
        return scan
    return jsonify({"message": "Quick scan started", "scan": scan.to_dict()}), 201


@scan_bp.route("/full", methods=["POST"])
@require_auth
def start_full_scan():
    """Start a Full Mode scan (includes scraping)."""
    scan = _start_scan("full")
    if not isinstance(scan, Scan):
        return scan
    return jsonify({"message": "Full scan started", "scan": scan.to_dict()}), 201


@scan_bp.route("/<int:scan_id>/status", methods=["GET"])
@require_auth
def get_scan_status(scan_id):
    """Get the current status of a scan."""
    scan = get_owned_scan(scan_id)
    if not scan:
        return jsonify({"error": "Scan not found"}), 404
    return jsonify({"scan": scan.to_dict()}), 200


@scan_bp.route("/<int:scan_id>/results", methods=["GET"])
@require_auth
def get_scan_results(scan_id):
    """Get full results of a completed scan."""
    scan = get_owned_scan(scan_id)
    if not scan:
        return jsonify({"error": "Scan not found"}), 404

    results = [r.to_dict() for r in scan.results.all()]
    return jsonify({
        "scan": scan.to_dict(),
        "results": results,
        "total": len(results),
    }), 200

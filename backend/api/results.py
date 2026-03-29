"""Results and history API routes."""

import json

from flask import Blueprint, g, jsonify

from auth.middleware import get_owned_scan, require_auth
from database import Scan
from core.graph_builder import IdentityGraphBuilder
from core.reporter import ReportGenerator

results_bp = Blueprint("results", __name__, url_prefix="/api/results")


@results_bp.route("/history", methods=["GET"])
@require_auth
def get_scan_history():
    """Get the user's scan history."""
    scans = (
        Scan.query.filter_by(user_id=g.current_user.id)
        .order_by(Scan.created_at.desc())
        .limit(50)
        .all()
    )
    return jsonify({
        "scans": [scan.to_dict() for scan in scans],
        "total": len(scans),
    }), 200


@results_bp.route("/<int:scan_id>/graph", methods=["GET"])
@require_auth
def get_scan_graph(scan_id):
    """Get the identity graph in Cytoscape.js format."""
    scan = get_owned_scan(scan_id)
    if not scan:
        return jsonify({"error": "Scan not found"}), 404

    cytoscape_data = {
        "nodes": [{"data": node.to_dict()} for node in scan.nodes.all()],
        "edges": [{"data": edge.to_dict()} for edge in scan.edges.all()],
    }

    return jsonify({
        "scan": scan.to_dict(),
        "graph": cytoscape_data,
    }), 200


@results_bp.route("/<int:scan_id>/report", methods=["GET"])
@require_auth
def get_scan_report(scan_id):
    """Get the risk analysis report."""
    scan = get_owned_scan(scan_id)
    if not scan:
        return jsonify({"error": "Scan not found"}), 404

    graph_builder = IdentityGraphBuilder()
    nodes = scan.nodes.all()
    edges = scan.edges.all()

    for node in nodes:
        metadata = json.loads(node.metadata_json) if node.metadata_json else {}
        graph_builder.add_identity_node(node.node_id, node.node_type, node.label, **metadata)

    for edge in edges:
        graph_builder.add_relationship(
            edge.source_id,
            edge.target_id,
            edge.relationship,
            edge.confidence,
        )

    for result in scan.results.all():
        if result.emails_found:
            for email in json.loads(result.emails_found):
                graph_builder.risk_events.append(("email_public", email, result.url))
        if result.phones_found:
            for phone in json.loads(result.phones_found):
                graph_builder.risk_events.append(("phone_public", phone, result.url))
        if result.category == "social":
            graph_builder.risk_events.append(("social_profile_found", result.platform, result.url))
        elif result.category in ("developer", "dev"):
            graph_builder.risk_events.append(("dev_profile_found", result.platform, result.url))

    report = ReportGenerator.generate_report(
        graph_builder,
        {"scan_id": scan_id, "target_name": scan.target_name},
    )

    return jsonify({"report": report}), 200

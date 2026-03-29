"""Evidence API - Download and list archived evidence snapshots."""

from flask import Blueprint, jsonify

from auth.middleware import get_owned_scan, require_auth
from core.evidence import get_evidence_file, list_evidence

evidence_bp = Blueprint("evidence", __name__, url_prefix="/api/evidence")


@evidence_bp.route("/<int:scan_id>", methods=["GET"])
@require_auth
def get_evidence_list(scan_id):
    """List all evidence snapshots for a scan."""
    scan = get_owned_scan(scan_id)
    if not scan:
        return jsonify({"error": "Scan not found"}), 404

    evidence = list_evidence(scan_id)
    return jsonify({
        "scan_id": scan_id,
        "count": len(evidence),
        "evidence": evidence,
    })


@evidence_bp.route("/<int:scan_id>/<filename>", methods=["GET"])
@require_auth
def get_evidence_detail(scan_id, filename):
    """Get a specific evidence snapshot."""
    scan = get_owned_scan(scan_id)
    if not scan:
        return jsonify({"error": "Scan not found"}), 404

    record = get_evidence_file(scan_id, filename)
    if not record:
        return jsonify({"error": "Evidence file not found"}), 404

    return jsonify(record)

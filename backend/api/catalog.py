"""Platform catalog API routes."""

from flask import Blueprint, jsonify, request
from auth.middleware import require_admin, require_auth
from core.platform_catalog import (
    get_platform_catalog_document,
    get_platform_catalog_summary,
    save_platform_catalog,
)


catalog_bp = Blueprint("catalog", __name__, url_prefix="/api/catalog")


@catalog_bp.route("/platforms", methods=["GET"])
@require_auth
def get_platform_catalog():
    """Return the editable platform catalog document."""
    catalog = get_platform_catalog_document()
    return jsonify({
        "catalog": catalog,
        "storage_label": "Server-managed secure catalog",
        "summary": get_platform_catalog_summary(catalog["platforms"]),
    }), 200


@catalog_bp.route("/platforms", methods=["PUT"])
@require_auth
@require_admin
def update_platform_catalog():
    """Validate and save the platform catalog."""
    data = request.get_json()
    if not data or "catalog" not in data:
        return jsonify({"error": "Request body must include a catalog object"}), 400

    try:
        normalized = save_platform_catalog(data["catalog"])
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify({
        "message": "Platform catalog saved",
        "catalog": {"platforms": normalized},
        "storage_label": "Server-managed secure catalog",
        "summary": get_platform_catalog_summary(normalized),
    }), 200

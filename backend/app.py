"""Digital Footprint Analysis System - Flask Application Entry Point."""

import os

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_jwt_extended.exceptions import CSRFError

from config import Config
from database import User, db, ensure_runtime_migrations


def create_app(config_overrides=None):
    """Create and configure the Flask application."""
    app = Flask(__name__, static_folder=None)
    app.config.from_object(Config)
    if config_overrides:
        app.config.update(config_overrides)

    # Initialize extensions
    CORS(
        app,
        resources={r"/api/*": {"origins": app.config.get("CORS_ORIGINS") or []}},
        supports_credentials=True,
    )
    jwt = JWTManager(app)
    db.init_app(app)

    @jwt.token_in_blocklist_loader
    def is_token_revoked(_jwt_header, jwt_payload):
        user_id = jwt_payload.get("sub")
        token_version = jwt_payload.get("ver", 0)

        try:
            user = db.session.get(User, int(user_id))
        except (TypeError, ValueError):
            return True

        return not user or user.token_version != token_version

    @jwt.unauthorized_loader
    def handle_missing_token(reason):
        return jsonify({"error": "Authentication required", "detail": reason}), 401

    @jwt.invalid_token_loader
    def handle_invalid_token(reason):
        return jsonify({"error": "Invalid session", "detail": reason}), 401

    @jwt.expired_token_loader
    def handle_expired_token(_jwt_header, _jwt_payload):
        return jsonify({"error": "Session expired"}), 401

    @jwt.revoked_token_loader
    def handle_revoked_token(_jwt_header, _jwt_payload):
        return jsonify({"error": "Session has been revoked"}), 401

    @app.errorhandler(CSRFError)
    def handle_csrf_error(error):
        return jsonify({"error": "Security token missing or invalid", "detail": str(error)}), 403

    @app.after_request
    def apply_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=()",
        )

        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"

        return response

    # Create database tables
    with app.app_context():
        db.create_all()
        ensure_runtime_migrations()

    # Register blueprints
    from auth.routes import auth_bp
    from api.catalog import catalog_bp
    from api.dashboard import dashboard_bp
    from api.evidence import evidence_bp
    from api.export import export_bp
    from api.results import results_bp
    from api.scan import scan_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(scan_bp)
    app.register_blueprint(results_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(catalog_bp)
    app.register_blueprint(export_bp)
    app.register_blueprint(evidence_bp)

    # Serve frontend files
    frontend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend")
    frontend_dir = os.path.abspath(frontend_dir)

    @app.route("/")
    def serve_index():
        return send_from_directory(frontend_dir, "index.html")

    @app.route("/css/<path:filename>")
    def serve_css(filename):
        return send_from_directory(os.path.join(frontend_dir, "css"), filename)

    @app.route("/js/<path:filename>")
    def serve_js(filename):
        return send_from_directory(os.path.join(frontend_dir, "js"), filename)

    @app.route("/assets/<path:filename>")
    def serve_assets(filename):
        return send_from_directory(os.path.join(frontend_dir, "assets"), filename)

    @app.route("/api/health")
    def health():
        return {"status": "ok", "service": "Digital Footprint Analysis System"}

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, host="0.0.0.0", port=5000)

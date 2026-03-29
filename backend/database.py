"""Database models for the Digital Footprint Analysis System."""

import os
from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(db.Model):
    """User account model."""
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=True)  # Null for DigiLocker-only users
    full_name = db.Column(db.String(255), nullable=False)
    aadhaar_last4 = db.Column(db.String(4), nullable=True)
    digilocker_id = db.Column(db.String(255), nullable=True, unique=True)
    google_id = db.Column(db.String(255), nullable=True, unique=True)
    is_verified = db.Column(db.Boolean, default=False)
    role = db.Column(db.String(50), default="user")  # user, admin, analyst
    token_version = db.Column(db.Integer, default=0, nullable=False)
    failed_login_attempts = db.Column(db.Integer, default=0, nullable=False)
    locked_until = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    last_login = db.Column(db.DateTime, nullable=True)

    scans = db.relationship("Scan", backref="user", lazy="dynamic")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "full_name": self.full_name,
            "aadhaar_last4": self.aadhaar_last4,
            "is_verified": self.is_verified,
            "role": self.role,
            "capabilities": {
                "manage_catalog": self.role in {"admin", "analyst"},
            },
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Scan(db.Model):
    """OSINT scan record."""
    __tablename__ = "scans"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    target_name = db.Column(db.String(255), nullable=False)
    target_email = db.Column(db.String(255), nullable=True)
    target_username = db.Column(db.String(255), nullable=True)
    target_phone = db.Column(db.String(50), nullable=True)
    target_address = db.Column(db.String(500), nullable=True)
    mode = db.Column(db.String(20), default="quick")  # quick or full
    status = db.Column(db.String(20), default="pending")  # pending, running, completed, failed
    progress = db.Column(db.Integer, default=0)  # 0-100
    current_stage = db.Column(db.String(100), default="Initializing")
    risk_score = db.Column(db.Float, nullable=True)  # 0.0 - 10.0
    platforms_found = db.Column(db.Integer, default=0)
    entities_found = db.Column(db.Integer, default=0)
    task_id = db.Column(db.String(255), nullable=True)
    execution_backend = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = db.Column(db.DateTime, nullable=True)

    results = db.relationship("ScanResult", backref="scan", lazy="dynamic", cascade="all, delete-orphan")
    nodes = db.relationship("IdentityNode", backref="scan", lazy="dynamic", cascade="all, delete-orphan")
    edges = db.relationship("IdentityEdge", backref="scan", lazy="dynamic", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "target_name": self.target_name,
            "target_email": self.target_email,
            "target_username": self.target_username,
            "target_phone": self.target_phone,
            "target_address": self.target_address,
            "mode": self.mode,
            "status": self.status,
            "progress": self.progress,
            "current_stage": self.current_stage,
            "risk_score": self.risk_score,
            "platforms_found": self.platforms_found,
            "entities_found": self.entities_found,
            "task_id": self.task_id,
            "execution_backend": self.execution_backend,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class ScanResult(db.Model):
    """Individual result from a scan (a discovered profile/page)."""
    __tablename__ = "scan_results"

    id = db.Column(db.Integer, primary_key=True)
    scan_id = db.Column(db.Integer, db.ForeignKey("scans.id"), nullable=False)
    platform = db.Column(db.String(100), nullable=False)
    url = db.Column(db.String(1024), nullable=False)
    username = db.Column(db.String(255), nullable=True)
    display_name = db.Column(db.String(255), nullable=True)
    bio = db.Column(db.Text, nullable=True)
    confidence = db.Column(db.Float, default=0.5)  # 0.0 - 1.0
    risk_level = db.Column(db.String(20), default="low")  # critical, high, medium, low
    category = db.Column(db.String(50), default="social")  # social, dev, professional, forum, other
    emails_found = db.Column(db.Text, nullable=True)  # JSON list
    phones_found = db.Column(db.Text, nullable=True)  # JSON list
    raw_text = db.Column(db.Text, nullable=True)
    match_score = db.Column(db.Float, nullable=True)
    match_reasons = db.Column(db.Text, nullable=True)
    metadata_json = db.Column(db.Text, nullable=True)
    evidence_path = db.Column(db.String(1024), nullable=True)
    last_seen_at = db.Column(db.DateTime, nullable=True)
    discovered_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        import json
        evidence_filename = os.path.basename(self.evidence_path) if self.evidence_path else None
        return {
            "id": self.id,
            "platform": self.platform,
            "url": self.url,
            "username": self.username,
            "display_name": self.display_name,
            "bio": self.bio,
            "confidence": self.confidence,
            "risk_level": self.risk_level,
            "category": self.category,
            "match_score": self.match_score,
            "match_reasons": json.loads(self.match_reasons) if self.match_reasons else [],
            "metadata": json.loads(self.metadata_json) if self.metadata_json else {},
            "evidence_available": bool(self.evidence_path),
            "evidence_filename": evidence_filename,
            "last_seen_at": self.last_seen_at.isoformat() if self.last_seen_at else None,
            "emails_found": json.loads(self.emails_found) if self.emails_found else [],
            "phones_found": json.loads(self.phones_found) if self.phones_found else [],
            "discovered_at": self.discovered_at.isoformat() if self.discovered_at else None,
        }


class IdentityNode(db.Model):
    """Node in the identity graph."""
    __tablename__ = "identity_nodes"

    id = db.Column(db.Integer, primary_key=True)
    scan_id = db.Column(db.Integer, db.ForeignKey("scans.id"), nullable=False)
    node_id = db.Column(db.String(255), nullable=False)  # Unique within scan
    node_type = db.Column(db.String(50), nullable=False)  # email, username, name, phone, url, platform
    label = db.Column(db.String(255), nullable=False)
    risk_level = db.Column(db.String(20), default="low")
    metadata_json = db.Column(db.Text, nullable=True)

    def to_dict(self):
        import json
        base = {
            "id": self.node_id,
            "type": self.node_type,
            "label": self.label,
            "risk_level": self.risk_level,
        }
        # Flatten metadata into top-level data so Cytoscape.js can access them
        if self.metadata_json:
            try:
                meta = json.loads(self.metadata_json)
                base.update(meta)
            except (json.JSONDecodeError, TypeError):
                pass
        return base


class IdentityEdge(db.Model):
    """Edge in the identity graph."""
    __tablename__ = "identity_edges"

    id = db.Column(db.Integer, primary_key=True)
    scan_id = db.Column(db.Integer, db.ForeignKey("scans.id"), nullable=False)
    source_id = db.Column(db.String(255), nullable=False)
    target_id = db.Column(db.String(255), nullable=False)
    relationship = db.Column(db.String(100), nullable=False)  # found_on, linked_to, associated_with
    confidence = db.Column(db.Float, default=0.5)

    def to_dict(self):
        return {
            "source": self.source_id,
            "target": self.target_id,
            "relationship": self.relationship,
            "confidence": self.confidence,
        }


def ensure_runtime_migrations():
    """Add newly introduced columns when running against an existing SQLite DB."""
    column_specs = {
        "scans": {
            "task_id": "TEXT",
            "execution_backend": "TEXT",
            "target_address": "TEXT",
        },
        "users": {
            "token_version": "INTEGER NOT NULL DEFAULT 0",
            "failed_login_attempts": "INTEGER NOT NULL DEFAULT 0",
            "locked_until": "DATETIME",
            "google_id": "TEXT",
        },
        "scan_results": {
            "match_score": "FLOAT",
            "match_reasons": "TEXT",
            "metadata_json": "TEXT",
            "evidence_path": "TEXT",
            "last_seen_at": "DATETIME",
        },
    }

    with db.engine.begin() as connection:
        for table_name, columns in column_specs.items():
            existing_columns = {
                row[1]
                for row in connection.exec_driver_sql(f"PRAGMA table_info({table_name})").fetchall()
            }

            for column_name, column_type in columns.items():
                if column_name not in existing_columns:
                    connection.exec_driver_sql(
                        f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
                    )

        connection.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_google_id ON users (google_id)"
        )

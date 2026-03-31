"""Authentication routes: register, login, logout, and DigiLocker OAuth."""

import hashlib
import hmac
import re
import secrets
import time
from datetime import datetime, timedelta, timezone

from flask import Blueprint, g, jsonify, redirect, request, session
from flask_jwt_extended import create_access_token, set_access_cookies, unset_jwt_cookies

from auth.digilocker import DigiLockerOAuth
from auth.google import GoogleOAuth
from auth.middleware import require_auth
from config import Config
from database import User, db

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _password_validation_error(password):
    if len(password) < Config.PASSWORD_MIN_LENGTH:
        return f"Password must be at least {Config.PASSWORD_MIN_LENGTH} characters."

    has_lower = any(char.islower() for char in password)
    has_upper = any(char.isupper() for char in password)
    has_digit = any(char.isdigit() for char in password)

    if not (has_lower and has_upper and has_digit):
        return "Password must include upper-case, lower-case, and numeric characters."

    return None


def _issue_auth_response(user, message, status_code=200):
    token = _create_auth_token(user)
    response = jsonify({
        "message": message,
        "user": user.to_dict(),
    })
    response.status_code = status_code
    set_access_cookies(response, token)
    return response


def _create_auth_token(user):
    token = create_access_token(
        identity=str(user.id),
        additional_claims={"ver": user.token_version},
    )
    return token


def _issue_auth_redirect(user, destination="/#/dashboard"):
    response = redirect(destination)
    set_access_cookies(response, _create_auth_token(user))
    return response


def _register_failed_login(user):
    now = datetime.now(timezone.utc)
    user.failed_login_attempts = (user.failed_login_attempts or 0) + 1

    if user.failed_login_attempts >= Config.AUTH_LOCKOUT_THRESHOLD:
        user.locked_until = now + timedelta(minutes=Config.AUTH_LOCKOUT_MINUTES)
        user.failed_login_attempts = 0

    db.session.commit()


def _reset_login_protection(user):
    user.failed_login_attempts = 0
    user.locked_until = None


def _finalize_authenticated_user(user):
    _reset_login_protection(user)
    user.last_login = datetime.now(timezone.utc)
    db.session.commit()


def _account_locked_response(user):
    locked_until = user.locked_until
    if locked_until and locked_until.tzinfo is None:
        locked_until = locked_until.replace(tzinfo=timezone.utc)

    return jsonify({
        "error": "Too many failed login attempts. Please try again later.",
        "retry_at": locked_until.isoformat() if locked_until else None,
    }), 429


def _create_oauth_state():
    """Create a self-verifiable HMAC-signed OAuth state token."""
    nonce = secrets.token_urlsafe(16)
    ts = str(int(time.time()))
    msg = f"{nonce}.{ts}"
    sig = hmac.new(
        Config.SECRET_KEY.encode(), msg.encode(), hashlib.sha256
    ).hexdigest()[:32]
    return f"{msg}.{sig}"


def _verify_oauth_state(received_state, max_age_seconds=600):
    """Verify an HMAC-signed OAuth state token."""
    if not received_state:
        return False
    try:
        nonce, ts, sig = received_state.rsplit(".", 2)
        msg = f"{nonce}.{ts}"
        expected = hmac.new(
            Config.SECRET_KEY.encode(), msg.encode(), hashlib.sha256
        ).hexdigest()[:32]
        if not hmac.compare_digest(sig, expected):
            return False
        if abs(time.time() - int(ts)) > max_age_seconds:
            return False
        return True
    except Exception:
        return False


def _get_or_create_google_user(user_info):
    google_id = user_info.get("google_id")
    email = (user_info.get("email") or "").strip().lower()

    if not google_id or not email:
        return None, ("Google did not return a usable account identity", 400)

    if not user_info.get("email_verified"):
        return None, ("Your Google account email must be verified before signing in", 400)

    user = User.query.filter_by(google_id=google_id).first()
    if user:
        return user, None

    user = User.query.filter_by(email=email).first()
    if user:
        user.google_id = google_id
        user.is_verified = True
        if not user.full_name:
            user.full_name = user_info.get("name") or "Google User"
        return user, None

    user = User(
        email=email,
        full_name=user_info.get("name") or "Google User",
        google_id=google_id,
        is_verified=True,
    )
    db.session.add(user)
    return user, None


@auth_bp.route("/register", methods=["POST"])
def register():
    """Register a new user with email and password."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body required"}), 400

    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    full_name = data.get("full_name", "").strip()

    if not email or not password or not full_name:
        return jsonify({"error": "Email, password, and full name are required"}), 400
    if not EMAIL_PATTERN.match(email):
        return jsonify({"error": "Please enter a valid email address"}), 400

    password_error = _password_validation_error(password)
    if password_error:
        return jsonify({"error": password_error}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already registered"}), 409

    user = User(email=email, full_name=full_name)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    return _issue_auth_response(user, "Registration successful", 201)


@auth_bp.route("/login", methods=["POST"])
def login():
    """Login with email and password."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body required"}), 400

    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    user = User.query.filter_by(email=email).first()

    if user and user.locked_until:
        locked_until = user.locked_until
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=timezone.utc)
        if locked_until > datetime.now(timezone.utc):
            return _account_locked_response(user)

    if not user or not user.check_password(password):
        if user:
            _register_failed_login(user)
        return jsonify({"error": "Invalid email or password"}), 401

    _finalize_authenticated_user(user)

    return _issue_auth_response(user, "Login successful", 200)


@auth_bp.route("/me", methods=["GET"])
@require_auth
def get_current_user():
    """Get the currently authenticated user's profile."""
    return jsonify({"user": g.current_user.to_dict()}), 200


@auth_bp.route("/logout", methods=["POST"])
@require_auth
def logout():
    """Invalidate the current session and clear browser cookies."""
    g.current_user.token_version += 1
    db.session.commit()

    response = jsonify({"message": "Logged out"})
    unset_jwt_cookies(response)
    return response, 200


@auth_bp.route("/digilocker/init", methods=["GET"])
def digilocker_init():
    """Initiate DigiLocker OAuth2 flow."""
    if not DigiLockerOAuth.is_configured():
        return jsonify({
            "error": "DigiLocker integration is not configured",
            "message": "Please set DIGILOCKER_CLIENT_ID and DIGILOCKER_CLIENT_SECRET environment variables",
        }), 503

    state = _create_oauth_state()
    auth_url, _ = DigiLockerOAuth.get_authorization_url(state=state)
    return jsonify({"auth_url": auth_url, "state": state}), 200


@auth_bp.route("/digilocker/callback", methods=["GET"])
def digilocker_callback():
    """Handle DigiLocker OAuth2 callback."""
    code = request.args.get("code")
    state = request.args.get("state")

    if not code:
        return jsonify({"error": "Authorization code not provided"}), 400

    if not _verify_oauth_state(state):
        return jsonify({"error": "Invalid state parameter"}), 400

    token_data = DigiLockerOAuth.exchange_code_for_token(code)
    if not token_data:
        return jsonify({"error": "Failed to exchange authorization code"}), 500

    access_token = token_data.get("access_token")
    if not access_token:
        return jsonify({"error": "No access token received"}), 500

    user_info = DigiLockerOAuth.get_user_info(access_token)
    if not user_info:
        return jsonify({"error": "Failed to retrieve user information"}), 500

    digilocker_id = user_info.get("digilocker_id")
    user = User.query.filter_by(digilocker_id=digilocker_id).first()

    if not user:
        email = user_info.get("email", f"{digilocker_id}@digilocker.gov.in")
        user = User.query.filter_by(email=email).first()
        if user:
            user.digilocker_id = digilocker_id
            user.aadhaar_last4 = user_info.get("aadhaar_last4")
            user.is_verified = True
        else:
            user = User(
                email=email,
                full_name=user_info.get("name", "DigiLocker User"),
                digilocker_id=digilocker_id,
                aadhaar_last4=user_info.get("aadhaar_last4"),
                is_verified=True,
            )
            db.session.add(user)

    _finalize_authenticated_user(user)

    return _issue_auth_redirect(user)


@auth_bp.route("/digilocker/status", methods=["GET"])
def digilocker_status():
    """Check if DigiLocker integration is available."""
    return jsonify({
        "available": DigiLockerOAuth.is_configured(),
        "message": (
            "DigiLocker integration is ready"
            if DigiLockerOAuth.is_configured()
            else "DigiLocker credentials not configured"
        ),
    }), 200


@auth_bp.route("/google/init", methods=["GET"])
def google_init():
    """Initiate Google OAuth2 flow."""
    if not GoogleOAuth.is_configured():
        return jsonify({
            "error": "Google integration is not configured",
            "message": "Please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET environment variables",
        }), 503

    state = _create_oauth_state()
    try:
        auth_url, _ = GoogleOAuth.get_authorization_url(state=state)
    except Exception:
        return jsonify({"error": "Failed to initialize Google authentication"}), 500

    return jsonify({"auth_url": auth_url, "state": state}), 200


@auth_bp.route("/google/callback", methods=["GET"])
def google_callback():
    """Handle Google OAuth2 callback."""
    code = request.args.get("code")
    state = request.args.get("state")

    if not code:
        return jsonify({"error": "Authorization code not provided"}), 400

    if not _verify_oauth_state(state):
        return jsonify({"error": "Invalid state parameter"}), 400

    token_data = GoogleOAuth.exchange_code_for_token(code)
    if not token_data:
        return jsonify({"error": "Failed to exchange authorization code"}), 500

    access_token = token_data.get("access_token")
    if not access_token:
        return jsonify({"error": "No access token received"}), 500

    user_info = GoogleOAuth.get_user_info(access_token)
    if not user_info:
        return jsonify({"error": "Failed to retrieve Google user information"}), 500

    user, error = _get_or_create_google_user(user_info)
    if error:
        message, status_code = error
        return jsonify({"error": message}), status_code

    _finalize_authenticated_user(user)
    return _issue_auth_redirect(user)


@auth_bp.route("/google/status", methods=["GET"])
def google_status():
    """Check if Google OAuth integration is available."""
    return jsonify({
        "available": GoogleOAuth.is_configured(),
        "message": (
            "Google sign-in is ready"
            if GoogleOAuth.is_configured()
            else "Google OAuth credentials not configured"
        ),
    }), 200

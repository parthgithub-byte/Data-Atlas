"""Google OAuth2 / OpenID Connect integration."""

import secrets
from urllib.parse import urlencode

import requests
from flask import current_app


class GoogleOAuth:
    """Handles the Google OAuth2 Authorization Code flow."""

    @staticmethod
    def _get_configuration():
        response = requests.get(
            current_app.config["GOOGLE_DISCOVERY_URL"],
            timeout=15,
        )
        response.raise_for_status()
        return response.json()

    @classmethod
    def get_authorization_url(cls, state=None):
        """Generate the Google authorization URL for user redirect."""
        if not state:
            state = secrets.token_urlsafe(32)

        configuration = cls._get_configuration()
        params = {
            "response_type": "code",
            "client_id": current_app.config["GOOGLE_CLIENT_ID"],
            "redirect_uri": current_app.config["GOOGLE_REDIRECT_URI"],
            "scope": "openid email profile",
            "state": state,
            "access_type": "offline",
            "prompt": "select_account",
        }
        auth_url = f"{configuration['authorization_endpoint']}?{urlencode(params)}"
        return auth_url, state

    @classmethod
    def exchange_code_for_token(cls, authorization_code):
        """Exchange the authorization code for an access token."""
        configuration = cls._get_configuration()
        data = {
            "grant_type": "authorization_code",
            "code": authorization_code,
            "client_id": current_app.config["GOOGLE_CLIENT_ID"],
            "client_secret": current_app.config["GOOGLE_CLIENT_SECRET"],
            "redirect_uri": current_app.config["GOOGLE_REDIRECT_URI"],
        }

        try:
            response = requests.post(
                configuration["token_endpoint"],
                data=data,
                headers={"Accept": "application/json"},
                timeout=15,
            )
            if response.status_code == 200:
                return response.json()
            return None
        except requests.RequestException:
            return None

    @classmethod
    def get_user_info(cls, access_token):
        """Retrieve user information from Google using the access token."""
        configuration = cls._get_configuration()
        headers = {"Authorization": f"Bearer {access_token}"}

        try:
            response = requests.get(
                configuration["userinfo_endpoint"],
                headers=headers,
                timeout=15,
            )
            if response.status_code == 200:
                data = response.json()
                return {
                    "google_id": data.get("sub", ""),
                    "name": data.get("name", ""),
                    "email": (data.get("email") or "").strip().lower(),
                    "email_verified": bool(data.get("email_verified")),
                    "picture": data.get("picture", ""),
                }
            return None
        except requests.RequestException:
            return None

    @staticmethod
    def is_configured():
        """Check if Google OAuth credentials are configured."""
        return bool(
            current_app.config.get("GOOGLE_CLIENT_ID")
            and current_app.config.get("GOOGLE_CLIENT_SECRET")
        )

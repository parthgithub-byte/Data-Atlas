"""DigiLocker OAuth2 integration for Aadhaar-based authentication."""

import requests
import secrets
from urllib.parse import urlencode
from flask import current_app


class DigiLockerOAuth:
    """Handles the DigiLocker OAuth2 Authorization Code flow."""

    @staticmethod
    def get_authorization_url(state=None):
        """Generate the DigiLocker authorization URL for user redirect."""
        if not state:
            state = secrets.token_urlsafe(32)

        params = {
            "response_type": "code",
            "client_id": current_app.config["DIGILOCKER_CLIENT_ID"],
            "redirect_uri": current_app.config["DIGILOCKER_REDIRECT_URI"],
            "state": state,
            "scope": "openid",
        }
        auth_url = f"{current_app.config['DIGILOCKER_AUTH_URL']}?{urlencode(params)}"
        return auth_url, state

    @staticmethod
    def exchange_code_for_token(authorization_code):
        """Exchange the authorization code for an access token."""
        data = {
            "grant_type": "authorization_code",
            "code": authorization_code,
            "client_id": current_app.config["DIGILOCKER_CLIENT_ID"],
            "client_secret": current_app.config["DIGILOCKER_CLIENT_SECRET"],
            "redirect_uri": current_app.config["DIGILOCKER_REDIRECT_URI"],
        }
        try:
            response = requests.post(
                current_app.config["DIGILOCKER_TOKEN_URL"],
                data=data,
                timeout=15,
            )
            if response.status_code == 200:
                return response.json()
            return None
        except requests.RequestException:
            return None

    @staticmethod
    def get_user_info(access_token):
        """Retrieve user information from DigiLocker using the access token."""
        headers = {"Authorization": f"Bearer {access_token}"}
        try:
            response = requests.get(
                current_app.config["DIGILOCKER_USERINFO_URL"],
                headers=headers,
                timeout=15,
            )
            if response.status_code == 200:
                data = response.json()
                # Mask Aadhaar - only keep last 4 digits
                aadhaar = data.get("aadhaar", "")
                masked_aadhaar = aadhaar[-4:] if len(aadhaar) >= 4 else ""
                return {
                    "digilocker_id": data.get("digilocker_id", ""),
                    "name": data.get("name", ""),
                    "dob": data.get("dob", ""),
                    "gender": data.get("gender", ""),
                    "aadhaar_last4": masked_aadhaar,
                    "email": data.get("email", ""),
                }
            return None
        except requests.RequestException:
            return None

    @staticmethod
    def is_configured():
        """Check if DigiLocker credentials are configured."""
        return bool(
            current_app.config.get("DIGILOCKER_CLIENT_ID")
            and current_app.config.get("DIGILOCKER_CLIENT_SECRET")
        )

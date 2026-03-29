import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import api.export as export_api
import app as app_module
import core.evidence as evidence_module
from database import Scan, ScanResult, User, db, ensure_runtime_migrations


class AuthSecurityTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.evidence_root = Path(self.temp_dir.name) / "evidence"

        evidence_module.EVIDENCE_ROOT = self.evidence_root
        export_api.list_evidence = evidence_module.list_evidence

        self.app = app_module.create_app({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{self.db_path}",
        })
        self.client_a = self.app.test_client()
        self.client_b = self.app.test_client()

        with self.app.app_context():
            db.drop_all()
            db.create_all()
            ensure_runtime_migrations()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()

        self.client_a = None
        self.client_b = None
        self.temp_dir.cleanup()

    def _register(self, client, *, full_name, email, password="Admin12345"):
        response = client.post(
            "/api/auth/register",
            json={
                "full_name": full_name,
                "email": email,
                "password": password,
            },
        )
        self.assertEqual(response.status_code, 201)
        return response

    def _csrf_headers(self, client):
        csrf_cookie = client.get_cookie("csrf_access_token")
        self.assertIsNotNone(csrf_cookie)
        return {"X-CSRF-TOKEN": csrf_cookie.value}

    def _start_scan(self, client, *, payload, endpoint="/api/scan/quick"):
        with patch("api.scan.threading.Thread") as thread_cls:
            response = client.post(
                endpoint,
                json=payload,
                headers=self._csrf_headers(client),
            )
            return response, thread_cls.return_value

    def _set_oauth_state(self, client, session_key, value="oauth-state"):
        with client.session_transaction() as flask_session:
            flask_session[session_key] = value
        return value

    def _seed_scan_for_user(self, email):
        with self.app.app_context():
            user = User.query.filter_by(email=email).first()
            scan = Scan(
                user_id=user.id,
                target_name="Private Person",
                target_email="private@example.com",
                target_username="privateuser",
                mode="quick",
                status="completed",
                progress=100,
                current_stage="Scan complete",
                risk_score=4.2,
                platforms_found=1,
                entities_found=1,
            )
            db.session.add(scan)
            db.session.flush()

            result = ScanResult(
                scan_id=scan.id,
                platform="GitHub",
                url="https://github.com/privateuser",
                username="privateuser",
                category="developer",
                risk_level="high",
                confidence=0.9,
            )
            db.session.add(result)
            db.session.flush()

            evidence_path = evidence_module.archive_result_evidence(
                scan.id,
                result.id,
                {
                    "platform": result.platform,
                    "url": result.url,
                    "username": result.username,
                },
            )
            result.evidence_path = evidence_path
            db.session.commit()
            return scan.id, Path(evidence_path).name

    def test_register_sets_cookie_session_and_me_returns_user(self):
        response = self._register(
            self.client_a,
            full_name="Alice Secure",
            email="alice@example.com",
        )

        self.assertNotIn("token", response.get_json())
        self.assertIsNotNone(self.client_a.get_cookie("access_token_cookie"))
        self.assertIsNotNone(self.client_a.get_cookie("csrf_access_token"))

        me = self.client_a.get("/api/auth/me")
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.get_json()["user"]["email"], "alice@example.com")

    def test_mutating_request_requires_csrf_header(self):
        self._register(
            self.client_a,
            full_name="Alice Secure",
            email="alice@example.com",
        )

        blocked = self.client_a.post("/api/auth/logout")
        self.assertEqual(blocked.status_code, 403)

        allowed = self.client_a.post("/api/auth/logout", headers=self._csrf_headers(self.client_a))
        self.assertEqual(allowed.status_code, 200)

    def test_users_cannot_access_other_users_scan_or_evidence(self):
        self._register(
            self.client_a,
            full_name="Alice Secure",
            email="alice@example.com",
        )
        self._register(
            self.client_b,
            full_name="Bob Secure",
            email="bob@example.com",
        )

        scan_id, evidence_name = self._seed_scan_for_user("alice@example.com")

        owner_results = self.client_a.get(f"/api/scan/{scan_id}/results")
        intruder_results = self.client_b.get(f"/api/scan/{scan_id}/results")
        intruder_evidence = self.client_b.get(f"/api/evidence/{scan_id}")
        intruder_detail = self.client_b.get(f"/api/evidence/{scan_id}/{evidence_name}")

        self.assertEqual(owner_results.status_code, 200)
        self.assertEqual(intruder_results.status_code, 404)
        self.assertEqual(intruder_evidence.status_code, 404)
        self.assertEqual(intruder_detail.status_code, 404)

    def test_scan_requires_self_attestation_and_uses_account_identity(self):
        self._register(
            self.client_a,
            full_name="Alice Secure",
            email="alice@example.com",
        )

        blocked, blocked_thread = self._start_scan(
            self.client_a,
            payload={
                "name": "Alice Secure",
                "email": "alice@example.com",
                "username": "alice-handle",
            },
        )
        self.assertEqual(blocked.status_code, 400)
        self.assertIn("self-scan", blocked.get_json()["error"].lower())
        blocked_thread.start.assert_not_called()

        allowed, allowed_thread = self._start_scan(
            self.client_a,
            payload={
                "name": "Alice Secure",
                "email": "alice@example.com",
                "username": "alice-handle",
                "phone": "+1 (555) 123-4567",
                "self_attested": True,
            },
        )
        self.assertEqual(allowed.status_code, 201)
        allowed_thread.start.assert_called_once()

        payload = allowed.get_json()["scan"]
        self.assertEqual(payload["target_name"], "Alice Secure")
        self.assertEqual(payload["target_email"], "alice@example.com")
        self.assertEqual(payload["target_username"], "alice-handle")
        self.assertEqual(payload["target_phone"], "+1 (555) 123-4567")

    def test_scan_blocks_other_person_identity_submission(self):
        self._register(
            self.client_a,
            full_name="Alice Secure",
            email="alice@example.com",
        )

        blocked, blocked_thread = self._start_scan(
            self.client_a,
            payload={
                "name": "Bob Private",
                "email": "bob@example.com",
                "self_attested": True,
            },
        )
        self.assertEqual(blocked.status_code, 403)
        self.assertIn("cannot scan another person", blocked.get_json()["error"].lower())
        blocked_thread.start.assert_not_called()

        with self.app.app_context():
            self.assertEqual(Scan.query.count(), 0)

    def test_google_callback_links_existing_user_and_sets_session_cookie(self):
        self._register(
            self.client_a,
            full_name="Alice Secure",
            email="alice@example.com",
        )
        state = self._set_oauth_state(self.client_a, "google_state", "google-state-1")

        with patch("auth.routes.GoogleOAuth.exchange_code_for_token", return_value={"access_token": "google-token"}):
            with patch(
                "auth.routes.GoogleOAuth.get_user_info",
                return_value={
                    "google_id": "google-user-123",
                    "email": "alice@example.com",
                    "name": "Alice Secure",
                    "email_verified": True,
                },
            ):
                response = self.client_a.get(f"/api/auth/google/callback?code=test-code&state={state}")

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/#/dashboard"))
        self.assertIsNotNone(self.client_a.get_cookie("access_token_cookie"))

        with self.app.app_context():
            user = User.query.filter_by(email="alice@example.com").first()
            self.assertEqual(user.google_id, "google-user-123")
            self.assertTrue(user.is_verified)

    def test_google_callback_creates_verified_user_for_new_account(self):
        state = self._set_oauth_state(self.client_a, "google_state", "google-state-2")

        with patch("auth.routes.GoogleOAuth.exchange_code_for_token", return_value={"access_token": "google-token"}):
            with patch(
                "auth.routes.GoogleOAuth.get_user_info",
                return_value={
                    "google_id": "google-user-456",
                    "email": "newuser@example.com",
                    "name": "New User",
                    "email_verified": True,
                },
            ):
                response = self.client_a.get(f"/api/auth/google/callback?code=test-code&state={state}")

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/#/dashboard"))

        with self.app.app_context():
            user = User.query.filter_by(email="newuser@example.com").first()
            self.assertIsNotNone(user)
            self.assertEqual(user.google_id, "google-user-456")
            self.assertTrue(user.is_verified)
            self.assertEqual(user.full_name, "New User")

    def test_sensitive_paths_are_not_exposed_in_api_responses(self):
        self._register(
            self.client_a,
            full_name="Alice Admin",
            email="alice@example.com",
        )

        with self.app.app_context():
            user = User.query.filter_by(email="alice@example.com").first()
            user.role = "admin"
            db.session.commit()

        scan_id, _ = self._seed_scan_for_user("alice@example.com")

        results = self.client_a.get(f"/api/scan/{scan_id}/results")
        results_payload = results.get_json()
        self.assertEqual(results.status_code, 200)
        self.assertNotIn("evidence_path", results_payload["results"][0])
        self.assertTrue(results_payload["results"][0]["evidence_available"])

        evidence = self.client_a.get(f"/api/evidence/{scan_id}")
        evidence_payload = evidence.get_json()
        self.assertEqual(evidence.status_code, 200)
        self.assertNotIn("path", evidence_payload["evidence"][0])

        catalog = self.client_a.get("/api/catalog/platforms")
        catalog_payload = catalog.get_json()
        self.assertEqual(catalog.status_code, 200)
        self.assertNotIn("path", catalog_payload)
        self.assertEqual(catalog_payload["storage_label"], "Server-managed secure catalog")


if __name__ == "__main__":
    unittest.main()

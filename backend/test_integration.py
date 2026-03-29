import os
import time
import unittest
from uuid import uuid4

from app import create_app


RUN_LIVE_TESTS = os.getenv("RUN_LIVE_TESTS", "false").lower() == "true"


@unittest.skipUnless(RUN_LIVE_TESTS, "Set RUN_LIVE_TESTS=true to run live integration checks.")
class IntegrationSmokeTest(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()
        self.email = f"smoke-{uuid4().hex[:8]}@dfas.local"
        self.password = "Admin12345"

    def _csrf_headers(self):
        csrf_cookie = self.client.get_cookie("csrf_access_token")
        self.assertIsNotNone(csrf_cookie)
        return {"X-CSRF-TOKEN": csrf_cookie.value}

    def _register_user(self):
        register = self.client.post(
            "/api/auth/register",
            json={
                "email": self.email,
                "password": self.password,
                "full_name": "Integration Smoke",
            },
        )
        self.assertEqual(register.status_code, 201)

    def test_full_scan_flow(self):
        self._register_user()
        headers = self._csrf_headers()

        scan = self.client.post(
            "/api/scan/full",
            json={"name": "Soham", "username": "soham"},
            headers=headers,
        )
        self.assertEqual(scan.status_code, 201)
        scan_id = scan.json["scan"]["id"]

        status_payload = None
        for _ in range(60):
            status = self.client.get(f"/api/scan/{scan_id}/status", headers=headers)
            self.assertEqual(status.status_code, 200)
            status_payload = status.json["scan"]
            if status_payload["status"] in ("completed", "failed"):
                break
            time.sleep(2)

        self.assertIsNotNone(status_payload)
        self.assertEqual(status_payload["status"], "completed", msg=status_payload["current_stage"])

        results = self.client.get(f"/api/scan/{scan_id}/results", headers=headers)
        self.assertEqual(results.status_code, 200)
        self.assertIn("total", results.json)

        evidence = self.client.get(f"/api/evidence/{scan_id}", headers=headers)
        self.assertEqual(evidence.status_code, 200)

        report = self.client.get(f"/api/results/{scan_id}/report", headers=headers)
        self.assertEqual(report.status_code, 200)
        self.assertIn("report", report.json)

        pdf = self.client.get(f"/api/export/{scan_id}/pdf", headers=headers)
        self.assertEqual(pdf.status_code, 200)
        self.assertEqual(pdf.headers.get("Content-Type"), "application/pdf")
        self.assertGreater(len(pdf.data), 0)


if __name__ == "__main__":
    unittest.main()

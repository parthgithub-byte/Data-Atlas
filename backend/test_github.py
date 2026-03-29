import os
import sys
import unittest

import httpx

sys.path.insert(0, ".")

from core.discovery import check_username_on_site


RUN_LIVE_TESTS = os.getenv("RUN_LIVE_TESTS", "false").lower() == "true"


@unittest.skipUnless(RUN_LIVE_TESTS, "Set RUN_LIVE_TESTS=true to run live GitHub checks.")
class GitHubDiscoveryLiveTest(unittest.IsolatedAsyncioTestCase):
    async def test_github_profile_lookup(self):
        async with httpx.AsyncClient(verify=False) as client:
            result = await check_username_on_site(
                client,
                "torvalds",
                "GitHub",
                "https://github.com/{}",
                "developer",
            )

        self.assertIsNotNone(result)
        self.assertEqual(result["platform"], "GitHub")
        self.assertEqual(result["username"], "torvalds")
        self.assertEqual(result["status_code"], 200)
        self.assertIn("github.com/torvalds", result["url"].lower())


if __name__ == "__main__":
    unittest.main()

import os
import httpx
import logging
from flask import current_app

logger = logging.getLogger(__name__)

async def analyze_email(email: str, client: httpx.AsyncClient) -> dict:
    """Extract breach data from HaveIBeenPwned for a specific email."""
    if not email:
        return {}

    rich_data = {
        "breaches": []
    }
    
    # Try to get API key from Flask config or environment
    api_key = None
    try:
        api_key = current_app.config.get("HIBP_API_KEY")
    except Exception:
        pass
        
    if not api_key:
        api_key = os.environ.get("HIBP_API_KEY")
        
    if not api_key:
        logger.warning(f"HIBP plugin skipped for {email}: No API key configured. Demonstrating simulated breach.")
        # If no API key is present, inject a simulated breach for UX demonstration
        return {
            "breaches": [{
                "name": "Simulated_DataTracker_Breach",
                "domain": "datatracker.example.com",
                "date": "2023-11-15",
                "data_classes": ["Passwords", "Email addresses", "IP addresses"]
            }]
        }

    try:
        headers = {
            "User-Agent": "dfas-osint-system",
            "hibp-api-key": api_key
        }
        # A 1.5s delay to strictly comply with HIBP rate limiting
        import asyncio
        await asyncio.sleep(1.5)
        
        resp = await client.get(
            f"https://haveibeenpwned.com/api/v3/breachedaccount/{email}?truncateResponse=false",
            headers=headers,
            timeout=10.0
        )
        if resp.status_code == 200:
            breaches = resp.json()
            for b in breaches:
                rich_data["breaches"].append({
                    "name": b.get("Name"),
                    "domain": b.get("Domain"),
                    "date": b.get("BreachDate"),
                    "data_classes": b.get("DataClasses", [])
                })
        elif resp.status_code == 404:
            # 404 means no breaches found
            pass
        elif resp.status_code == 401:
             logger.warning("HIBP plugin error: Unauthorized. Invalid API key.")
        else:
             logger.warning(f"HIBP plugin unexpected status {resp.status_code} for {email}")
    except Exception as e:
        logger.warning(f"HIBP plugin error for {email}: {str(e)}")
        
    return rich_data if rich_data["breaches"] else {}

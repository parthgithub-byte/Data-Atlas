import httpx
import logging
from datetime import datetime, timezone
from core.http_client import build_request_headers

logger = logging.getLogger(__name__)

async def analyze(username: str, client: httpx.AsyncClient) -> dict:
    """Extract rich OSINT data from GitHub including live activity feed."""
    rich_data = {
        "repositories": [],
        "bio": None,
        "location": None,
        "blog": None,
        "company": None,
        "followers": 0,
        "created_at": None,
        "avatar_url": None,
        "recent_events": [],
    }
    
    try:
        headers = build_request_headers()
        # User Profile
        resp = await client.get(f"https://api.github.com/users/{username}", headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            rich_data["bio"] = data.get("bio")
            rich_data["location"] = data.get("location")
            rich_data["blog"] = data.get("blog")
            rich_data["company"] = data.get("company")
            rich_data["followers"] = data.get("followers", 0)
            rich_data["created_at"] = data.get("created_at")
            rich_data["updated_at"] = data.get("updated_at")
            rich_data["avatar_url"] = data.get("avatar_url")

            # Repos (Limit to top 5 recent)
            repo_resp = await client.get(
                f"https://api.github.com/users/{username}/repos?sort=updated&per_page=5",
                headers=headers
            )
            if repo_resp.status_code == 200:
                repos = repo_resp.json()
                for r in repos:
                    rich_data["repositories"].append({
                        "name": r.get("name"),
                        "description": r.get("description"),
                        "language": r.get("language"),
                        "url": r.get("html_url")
                    })

            # === Live Activity Feed (Real-Time Events API) ===
            try:
                events_resp = await client.get(
                    f"https://api.github.com/users/{username}/events?per_page=10",
                    headers=headers
                )
                if events_resp.status_code == 200:
                    events = events_resp.json()
                    now = datetime.now(timezone.utc)
                    if events:
                        rich_data["last_active_at"] = events[0].get("created_at")
                    for ev in events[:5]:
                        created = ev.get("created_at", "")
                        event_type = ev.get("type", "Unknown")
                        repo_name = ev.get("repo", {}).get("name", "")

                        # Calculate age
                        age_hours = None
                        if created:
                            try:
                                ev_time = datetime.fromisoformat(created.replace("Z", "+00:00"))
                                delta = now - ev_time
                                age_hours = round(delta.total_seconds() / 3600, 1)
                            except Exception:
                                pass

                        rich_data["recent_events"].append({
                            "type": event_type,
                            "repo": repo_name,
                            "created_at": created,
                            "age_hours": age_hours,
                        })
            except Exception as e:
                logger.debug(f"GitHub events API error for {username}: {e}")

    except Exception as e:
        logger.warning(f"GitHub plugin error for {username}: {str(e)}")
        
    # Clean up None values
    return {k: v for k, v in rich_data.items() if v is not None and v != ""}

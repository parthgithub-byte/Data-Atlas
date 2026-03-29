import httpx
import logging
from datetime import datetime, timezone
from core.http_client import build_request_headers

logger = logging.getLogger(__name__)

async def analyze(username: str, client: httpx.AsyncClient) -> dict:
    """Extract rich OSINT data from Reddit including live activity feed."""
    rich_data = {
        "link_karma": 0,
        "comment_karma": 0,
        "created_utc": None,
        "is_mod": False,
        "icon_img": None,
        "recent_activity": [],
    }
    
    try:
        headers = build_request_headers()
        
        # Profile data
        resp = await client.get(f"https://www.reddit.com/user/{username}/about.json", headers=headers)
        if resp.status_code == 200:
            data = resp.json().get("data", {})
            rich_data["link_karma"] = data.get("link_karma", 0)
            rich_data["comment_karma"] = data.get("comment_karma", 0)
            rich_data["created_utc"] = data.get("created_utc")
            rich_data["is_mod"] = data.get("is_mod", False)
            rich_data["icon_img"] = data.get("icon_img")

            # Convert created_utc to ISO format for temporal tracking
            if rich_data["created_utc"]:
                try:
                    rich_data["created_at"] = datetime.fromtimestamp(
                        rich_data["created_utc"], tz=timezone.utc
                    ).isoformat()
                except Exception:
                    pass

        # === Live Activity Feed (Recent Comments) ===
        try:
            activity_resp = await client.get(
                f"https://www.reddit.com/user/{username}/comments.json?limit=5",
                headers=headers
            )
            if activity_resp.status_code == 200:
                comments_data = activity_resp.json().get("data", {}).get("children", [])
                now = datetime.now(timezone.utc)
                if comments_data:
                    latest = comments_data[0].get("data", {}).get("created_utc")
                    if latest:
                        rich_data["last_active_at"] = datetime.fromtimestamp(latest, tz=timezone.utc).isoformat()
                for item in comments_data[:5]:
                    comment = item.get("data", {})
                    created = comment.get("created_utc")
                    subreddit = comment.get("subreddit", "")
                    body_preview = (comment.get("body", "") or "")[:100]

                    age_hours = None
                    if created:
                        try:
                            ev_time = datetime.fromtimestamp(created, tz=timezone.utc)
                            delta = now - ev_time
                            age_hours = round(delta.total_seconds() / 3600, 1)
                        except Exception:
                            pass

                    rich_data["recent_activity"].append({
                        "subreddit": subreddit,
                        "body_preview": body_preview,
                        "created_utc": created,
                        "age_hours": age_hours,
                    })
        except Exception as e:
            logger.debug(f"Reddit activity API error for {username}: {e}")

    except Exception as e:
        logger.warning(f"Reddit plugin error for {username}: {str(e)}")
        
    return {k: v for k, v in rich_data.items() if v is not None and v != ""}

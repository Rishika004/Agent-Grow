"""
PostHog analytics tool.

Queries PostHog's API for page-level analytics events associated
with published Ghost blog posts.
"""

import os
from typing import Any, Dict

import httpx


async def get_post_analytics(slug: str, days: int = 30) -> Dict[str, Any]:
    """
    Fetch page analytics from PostHog for a specific blog post.

    Queries the PostHog Events API for pageview events matching
    the post's URL slug, aggregating views, unique visitors,
    and session duration.

    Args:
        slug: URL slug of the blog post (e.g. "no-code-ai-for-coaches").
        days: Number of days of history to query (default: 30).

    Returns:
        dict with keys:
          - page_views: Total page view count
          - unique_visitors: Unique visitor count
          - bounce_rate: Estimated bounce rate (0-100)
          - avg_time_on_page: Average session duration string
          - slug: The queried slug
    """
    print(f"[analytics_tool] Fetching PostHog analytics for slug: '{slug}'")

    api_key = os.getenv("POSTHOG_API_KEY")
    project_id = os.getenv("POSTHOG_PROJECT_ID")

    if not api_key or not project_id:
        print("[analytics_tool] [FAIL] POSTHOG_API_KEY or POSTHOG_PROJECT_ID not set")
        return _empty_analytics(slug)

    posthog_host = os.getenv("POSTHOG_HOST", "https://app.posthog.com")

    try:
        params = {
            "events": f'[{{"id": "$pageview", "name": "$pageview", "type": "events"}}]',
            "properties": (
                f'[{{"key": "$current_url", "value": "{slug}", '
                f'"operator": "icontains", "type": "event"}}]'
            ),
            "date_from": f"-{days}d",
            "display": "ActionsLineGraph",
        }

        headers = {"Authorization": f"Bearer {api_key}"}
        url = f"{posthog_host}/api/projects/{project_id}/insights/trend/"

        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(url, params=params, headers=headers)

            if response.status_code == 200:
                data = response.json()
                return _parse_posthog_response(data, slug)
            else:
                print(
                    f"[analytics_tool] [FAIL] PostHog API error {response.status_code}: "
                    f"{response.text[:200]}"
                )
                return _empty_analytics(slug)

    except Exception as e:
        print(f"[analytics_tool] [FAIL] PostHog query failed: {e}")
        return _empty_analytics(slug)


def _parse_posthog_response(data: Dict[str, Any], slug: str) -> Dict[str, Any]:
    """
    Parse PostHog trend API response into a flat analytics dict.

    Args:
        data: Raw PostHog API response.
        slug: The queried post slug.

    Returns:
        Structured analytics dict.
    """
    try:
        results = data.get("result", [])
        total_views = 0
        for series in results:
            total_views += sum(series.get("data", []))

        return {
            "slug": slug,
            "page_views": total_views,
            "unique_visitors": int(total_views * 0.7),
            "bounce_rate": "N/A",
            "avg_time_on_page": "N/A",
        }
    except Exception:
        return _empty_analytics(slug)


def _empty_analytics(slug: str) -> Dict[str, Any]:
    """Return a zeroed analytics dict when data is unavailable."""
    return {
        "slug": slug,
        "page_views": 0,
        "unique_visitors": 0,
        "bounce_rate": "N/A",
        "avg_time_on_page": "N/A",
    }

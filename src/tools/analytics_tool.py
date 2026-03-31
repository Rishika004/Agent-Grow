"""
Vercel Analytics tool.

Queries Vercel's Web Analytics API for page-level analytics
associated with published blog posts.
"""

import os
from typing import Any, Dict

import httpx


async def get_post_analytics(slug: str, days: int = 30) -> Dict[str, Any]:
    """
    Fetch page analytics from Vercel Web Analytics for a specific blog post.

    Args:
        slug: URL slug of the blog post (e.g. "no-code-ai-for-coaches").
        days: Number of days of history to query (default: 30).

    Returns:
        dict with keys:
          - page_views: Total page view count
          - unique_visitors: Unique visitor count
          - bounce_rate: Estimated bounce rate (0-100)
          - avg_time_on_page: Average duration string
          - slug: The queried slug
    """
    print(f"[analytics_tool] Fetching Vercel Analytics for slug: '{slug}'")

    token = os.getenv("VERCEL_API_TOKEN")
    project_id = os.getenv("VERCEL_PROJECT_ID")

    if not token or not project_id:
        print("[analytics_tool] [FAIL] VERCEL_API_TOKEN or VERCEL_PROJECT_ID not set")
        return _empty_analytics(slug)

    try:
        from datetime import datetime, timedelta

        end = datetime.utcnow()
        start = end - timedelta(days=days)

        params = {
            "projectId": project_id,
            "from": start.strftime("%Y-%m-%dT00:00:00Z"),
            "to": end.strftime("%Y-%m-%dT23:59:59Z"),
            "filter": f'{{"path": {{"is": "/{slug}"}}}}',
        }

        headers = {
            "Authorization": f"Bearer {token}",
        }

        async with httpx.AsyncClient(timeout=20.0) as client:
            # Fetch page views
            views_url = "https://vercel.com/api/web/insights/stats/path"
            response = await client.get(views_url, params=params, headers=headers)

            if response.status_code == 200:
                data = response.json()
                return _parse_vercel_response(data, slug)
            else:
                print(
                    f"[analytics_tool] [FAIL] Vercel API error {response.status_code}: "
                    f"{response.text[:200]}"
                )
                return _empty_analytics(slug)

    except Exception as e:
        print(f"[analytics_tool] [FAIL] Vercel Analytics query failed: {e}")
        return _empty_analytics(slug)


def _parse_vercel_response(data: Dict[str, Any], slug: str) -> Dict[str, Any]:
    """
    Parse Vercel Web Analytics API response into a flat analytics dict.
    """
    try:
        # Vercel returns data array with pageViews and visitors
        total_views = data.get("pageViews", 0)
        unique_visitors = data.get("visitors", 0)

        # If response is a list of data points, sum them
        if isinstance(data.get("data"), list):
            total_views = sum(d.get("pageViews", 0) for d in data["data"])
            unique_visitors = sum(d.get("visitors", 0) for d in data["data"])

        return {
            "slug": slug,
            "page_views": total_views,
            "unique_visitors": unique_visitors,
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

"""
Ghost CMS publishing tool.

Authenticates with Ghost Admin API using JWT token generation,
then creates and publishes blog posts programmatically.

Ghost Admin API key format: "{id}:{secret}" -- split at the colon.
JWT is signed with the secret and sent as Bearer token.
"""

import json
import os
import time
from typing import Any, Dict, List, Optional

import httpx
from jose import jwt


def _generate_ghost_jwt(admin_key: str) -> str:
    """
    Generate a JWT token for authenticating with the Ghost Admin API.

    Ghost Admin API keys have the format "id:secret" where:
      - id: The key ID (used as JWT kid header)
      - secret: Hex-encoded secret used to sign the JWT

    Args:
        admin_key: Ghost Admin API key in "id:secret" format.

    Returns:
        Signed JWT token string.

    Raises:
        ValueError: If admin_key format is invalid.
    """
    if ":" not in admin_key:
        raise ValueError("GHOST_ADMIN_KEY must be in 'id:secret' format")

    key_id, secret = admin_key.split(":", 1)

    # Ghost requires the secret to be decoded from hex
    secret_bytes = bytes.fromhex(secret)

    now = int(time.time())
    payload = {
        "iat": now,
        "exp": now + 300,  # Token valid for 5 minutes
        "aud": "/admin/",
    }
    headers = {"alg": "HS256", "typ": "JWT", "kid": key_id}

    token = jwt.encode(payload, secret_bytes, algorithm="HS256", headers=headers)
    return token


def _markdown_to_mobiledoc(markdown_content: str) -> str:
    """
    Wrap raw markdown in Ghost's Mobiledoc card format.

    Ghost accepts markdown via a dedicated Markdown card in Mobiledoc.

    Args:
        markdown_content: Raw Markdown string.

    Returns:
        Mobiledoc JSON string with a single markdown card.
    """
    mobiledoc = {
        "version": "0.3.1",
        "markups": [],
        "atoms": [],
        "cards": [["markdown", {"markdown": markdown_content}]],
        "sections": [[10, 0]],
    }
    return json.dumps(mobiledoc)


async def publish_to_ghost(
    title: str,
    slug: str,
    html_content: str,
    meta_description: str,
    tags: Optional[List[str]] = None,
    status: str = "published",
) -> Dict[str, Any]:
    """
    Create and publish a blog post to Ghost CMS via the Admin API.

    Args:
        title: Post title.
        slug: URL slug (must be unique in Ghost).
        html_content: Post body in Markdown format (wrapped in Mobiledoc card).
        meta_description: SEO meta description string.
        tags: List of tag name strings to attach to the post.
        status: "published" (live) or "draft" (saved but not live).

    Returns:
        dict with status, url, post_id on success or error on failure.
    """
    print(f"[cms_tool] Publishing to Ghost: '{title[:60]}'")

    ghost_url = os.getenv("GHOST_API_URL", "").rstrip("/")
    admin_key = os.getenv("GHOST_ADMIN_KEY", "")

    if not ghost_url or not admin_key:
        error_msg = "GHOST_API_URL or GHOST_ADMIN_KEY not set in environment"
        print(f"[cms_tool] [FAIL] {error_msg}")
        return {"status": "failed", "error": error_msg}

    try:
        token = _generate_ghost_jwt(admin_key)
        mobiledoc = _markdown_to_mobiledoc(html_content)

        post_payload = {
            "posts": [
                {
                    "title": title,
                    "slug": slug,
                    "mobiledoc": mobiledoc,
                    "custom_excerpt": meta_description,
                    "meta_description": meta_description,
                    "tags": [{"name": t} for t in (tags or [])],
                    "status": status,
                }
            ]
        }

        headers = {
            "Authorization": f"Ghost {token}",
            "Content-Type": "application/json",
        }

        api_url = f"{ghost_url}/ghost/api/admin/posts/"

        async with httpx.AsyncClient(timeout=30.0) as http_client:
            response = await http_client.post(
                api_url, json=post_payload, headers=headers
            )
            response.raise_for_status()
            data = response.json()

        post = data["posts"][0]
        post_url = post.get("url", f"{ghost_url}/{slug}/")
        post_id = post.get("id", "")

        print(f"[cms_tool] [OK] Published: {post_url}")
        return {"status": "published", "url": post_url, "post_id": post_id}

    except httpx.HTTPStatusError as e:
        error_msg = f"Ghost API HTTP error {e.response.status_code}: {e.response.text[:200]}"
        print(f"[cms_tool] [FAIL] {error_msg}")
        return {"status": "failed", "error": error_msg}
    except Exception as e:
        error_msg = str(e)
        print(f"[cms_tool] [FAIL] Ghost publish failed: {error_msg}")
        return {"status": "failed", "error": error_msg}


async def create_ghost_draft(
    title: str,
    slug: str,
    markdown_content: str,
    meta_description: str,
    tags: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Create a draft post in Ghost (not published -- requires manual publish)."""
    return await publish_to_ghost(
        title=title,
        slug=slug,
        html_content=markdown_content,
        meta_description=meta_description,
        tags=tags,
        status="draft",
    )

"""
LinkedIn posting tool wrapper.

Uses the linkedin-api library (unofficial) to post text updates
to LinkedIn on behalf of the authenticated user.

Note: This uses credentials-based auth (email + password), not OAuth.
Keep credentials secure and stored only in environment variables.
"""

import os
from typing import Any, Dict


async def post_to_linkedin(text: str) -> Dict[str, Any]:
    """
    Post a text update to LinkedIn as the authenticated user.

    Authenticates using LINKEDIN_EMAIL and LINKEDIN_PASSWORD from environment.
    Returns a result dict indicating success or failure.

    Args:
        text: The text content of the LinkedIn post (max ~3000 chars recommended).

    Returns:
        dict with keys:
          - status: "posted" | "failed"
          - post_id: LinkedIn post URN (on success)
          - error: Error message string (on failure)
    """
    print(f"[linkedin_tool] Attempting to post to LinkedIn ({len(text)} chars)...")

    email = os.getenv("LINKEDIN_EMAIL")
    password = os.getenv("LINKEDIN_PASSWORD")

    if not email or not password:
        error_msg = "LINKEDIN_EMAIL or LINKEDIN_PASSWORD not set in environment"
        print(f"[linkedin_tool] [FAIL] {error_msg}")
        return {"status": "failed", "error": error_msg}

    try:
        from linkedin_api import Linkedin

        # Authenticate -- creates a session with LinkedIn's unofficial API
        api = Linkedin(email, password)

        # Post the update (UGC post via /ugcPosts endpoint)
        response = api.create_post(text)

        post_id = str(response) if response else "unknown"
        print(f"[linkedin_tool] [OK] Posted successfully | URN: {post_id}")
        return {"status": "posted", "post_id": post_id}

    except ImportError:
        error_msg = "linkedin-api package not installed. Run: pip install linkedin-api"
        print(f"[linkedin_tool] [FAIL] {error_msg}")
        return {"status": "failed", "error": error_msg}
    except Exception as e:
        error_msg = str(e)
        print(f"[linkedin_tool] [FAIL] LinkedIn post failed: {error_msg}")
        return {"status": "failed", "error": error_msg}

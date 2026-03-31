"""
Tavily search tool wrapper.

Provides a typed interface around the TavilyClient for use
by the research agent and any other components needing web search.
"""

import os
from typing import Any, Dict, List, Optional

from tavily import TavilyClient


def get_tavily_client() -> TavilyClient:
    """
    Instantiate and return a configured TavilyClient.

    Raises:
        ValueError: If TAVILY_API_KEY is not set in the environment.
    """
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        raise ValueError("TAVILY_API_KEY environment variable is not set")
    return TavilyClient(api_key=api_key)


def search_topics(
    query: str,
    search_depth: str = "advanced",
    max_results: int = 5,
    include_answer: bool = True,
) -> List[Dict[str, Any]]:
    """
    Perform a Tavily search and return a list of structured results.

    Args:
        query: The search query string.
        search_depth: "basic" or "advanced" -- advanced gives richer results.
        max_results: Maximum number of results to return.
        include_answer: Whether to include Tavily's synthesised answer.

    Returns:
        List of result dicts with keys: title, url, content, score.
    """
    client = get_tavily_client()
    response = client.search(
        query=query,
        search_depth=search_depth,
        max_results=max_results,
        include_answer=include_answer,
    )

    results = []
    for item in response.get("results", []):
        results.append(
            {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "content": item.get("content", ""),
                "score": item.get("score", 0.0),
                "answer": response.get("answer", ""),
            }
        )
    return results


def search_with_context(query: str, max_results: int = 5) -> Optional[str]:
    """
    Perform a search and return Tavily's synthesised answer as a single string.

    Args:
        query: The search query string.
        max_results: Maximum number of results to consider.

    Returns:
        The synthesised answer string, or None if unavailable.
    """
    client = get_tavily_client()
    response = client.search(
        query=query,
        search_depth="advanced",
        max_results=max_results,
        include_answer=True,
    )
    return response.get("answer")

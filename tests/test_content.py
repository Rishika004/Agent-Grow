"""
Tests for the content agent node.

Mocks the Google Gemini API to verify that the content node:
  1. Generates drafts with required keys (title, body_markdown, etc.)
  2. Limits output to max 2 drafts per cycle
  3. Handles malformed JSON gracefully
  4. Appends errors when API keys are missing
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.agents.orchestrator import AgentState


@pytest.fixture
def state_with_research() -> AgentState:
    """Return an AgentState pre-populated with mock research output."""
    return AgentState(
        user_id="test-user-001",
        niche="no-code app building for coaches",
        cycle_id="test-cycle-002",
        memory_context=[
            "Post titled 'Top 5 No-Code Tools' scored 8/10. Keywords: no-code, automation",
        ],
        research_output={
            "topics": [
                {
                    "title": "AI-Powered Coaching Apps Without Code",
                    "url": "https://example.com/ai-coaching",
                    "content": "Build AI coaching tools in minutes using no-code platforms.",
                    "score": 0.92,
                },
                {
                    "title": "Automate Your Coaching Business with AI",
                    "url": "https://example.com/automate-coaching",
                    "content": "Use AI automation to scale your coaching business effortlessly.",
                    "score": 0.87,
                },
                {
                    "title": "Third Topic That Should Be Ignored",
                    "url": "https://example.com/third",
                    "content": "This topic should not be processed.",
                    "score": 0.75,
                },
            ],
            "competitor_content": [],
            "niche": "no-code app building for coaches",
            "cycle_id": "test-cycle-002",
        },
    )


MOCK_DRAFT_JSON = {
    "title": "How Coaches Are Building AI Apps Without Writing Code",
    "slug": "coaches-building-ai-apps-no-code",
    "body_markdown": (
        "# How Coaches Are Building AI Apps\n\n"
        "The no-code revolution...\n\n"
        "## Why No-Code AI?\n\nCoaches today need..."
    ),
    "meta_description": (
        "Discover how coaches are using no-code platforms "
        "to build AI-powered apps that grow their business."
    ),
    "target_keyword": "no-code AI apps for coaches",
    "linkedin_hook": (
        "Coaches: you don't need a developer.\n\n"
        "AI-powered apps are now buildable in an afternoon.\n\n"
        "Here's exactly how ->"
    ),
}


def _make_mock_gemini_response(content: dict) -> MagicMock:
    """Create a mock Gemini API response with the given content dict."""
    mock_response = MagicMock()
    mock_response.text = json.dumps(content)
    return mock_response


def _patch_gemini():
    """Return a context manager that patches the genai.Client for content_agent."""
    mock_genai = MagicMock()
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = _make_mock_gemini_response(
        MOCK_DRAFT_JSON
    )
    mock_genai.Client.return_value = mock_client
    return patch("src.agents.content_agent.genai", mock_genai), mock_client


@pytest.mark.asyncio
async def test_content_draft_has_required_keys(state_with_research: AgentState):
    """content_node should generate drafts containing all required keys."""
    genai_patch, mock_client = _patch_gemini()
    with genai_patch, \
         patch("src.agents.content_agent._get_supabase_client", return_value=None), \
         patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}):

        from src.agents.content_agent import content_node

        result_state = await content_node(state_with_research)

    assert len(result_state.content_drafts) > 0
    draft = result_state.content_drafts[0]

    required_keys = [
        "title",
        "slug",
        "body_markdown",
        "meta_description",
        "target_keyword",
        "linkedin_hook",
    ]
    for key in required_keys:
        assert key in draft, f"Draft must have '{key}' key"


@pytest.mark.asyncio
async def test_content_limits_to_two_drafts(state_with_research: AgentState):
    """content_node should process a maximum of 2 topics per cycle."""
    assert len(state_with_research.research_output["topics"]) == 3

    genai_patch, _ = _patch_gemini()
    with genai_patch, \
         patch("src.agents.content_agent._get_supabase_client", return_value=None), \
         patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}):

        from src.agents.content_agent import content_node

        result_state = await content_node(state_with_research)

    assert len(result_state.content_drafts) <= 2


@pytest.mark.asyncio
async def test_content_draft_has_correct_status(state_with_research: AgentState):
    """All generated drafts should have status='pending_approval'."""
    genai_patch, _ = _patch_gemini()
    with genai_patch, \
         patch("src.agents.content_agent._get_supabase_client", return_value=None), \
         patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}):

        from src.agents.content_agent import content_node

        result_state = await content_node(state_with_research)

    for draft in result_state.content_drafts:
        assert draft.get("status") == "pending_approval"


@pytest.mark.asyncio
async def test_content_handles_malformed_json(state_with_research: AgentState):
    """When Gemini returns malformed JSON, the node should catch the parse error."""
    bad_response = MagicMock()
    bad_response.text = "This is not valid JSON {{{"

    mock_genai = MagicMock()
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = bad_response
    mock_genai.Client.return_value = mock_client

    with patch("src.agents.content_agent.genai", mock_genai), \
         patch("src.agents.content_agent._get_supabase_client", return_value=None), \
         patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}):

        from src.agents.content_agent import content_node

        result_state = await content_node(state_with_research)

    assert isinstance(result_state, AgentState)
    assert len(result_state.errors) > 0


@pytest.mark.asyncio
async def test_content_skips_when_no_api_key(state_with_research: AgentState):
    """When GEMINI_API_KEY is missing, content_node should append an error."""
    with patch.dict("os.environ", {}, clear=True):
        import os

        os.environ.pop("GEMINI_API_KEY", None)

        from src.agents.content_agent import content_node

        result_state = await content_node(state_with_research)

    assert any("GEMINI_API_KEY" in err for err in result_state.errors)
    assert len(result_state.content_drafts) == 0


@pytest.mark.asyncio
async def test_content_skips_when_no_research():
    """When research_output is empty, content_node should skip generation."""
    empty_state = AgentState(
        user_id="test-user-001",
        niche="no-code app building for coaches",
        cycle_id="test-cycle-003",
        research_output=None,
    )

    with patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}):
        from src.agents.content_agent import content_node

        result_state = await content_node(empty_state)

    assert len(result_state.content_drafts) == 0
    assert len(result_state.errors) > 0

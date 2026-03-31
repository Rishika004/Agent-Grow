"""
Tests for the research agent node.

Mocks TavilyClient to verify that the research node:
  1. Populates state.research_output with the expected keys
  2. Handles API failures gracefully by appending to state.errors
  3. Returns a valid AgentState in all cases
"""

from unittest.mock import MagicMock, patch

import pytest

from src.agents.orchestrator import AgentState


@pytest.fixture
def base_state() -> AgentState:
    """Return a minimal AgentState for testing."""
    return AgentState(
        user_id="test-user-001",
        niche="no-code app building for coaches",
        cycle_id="test-cycle-001",
    )


MOCK_TAVILY_RESPONSE = {
    "results": [
        {
            "title": "Top No-Code Tools for Coaches in 2026",
            "url": "https://example.com/no-code-coaches",
            "content": "Coaches are increasingly using no-code AI tools to automate workflows.",
            "score": 0.95,
        },
        {
            "title": "AI Automation for Coaching Businesses",
            "url": "https://example.com/ai-coaching",
            "content": "Build AI-powered coaching platforms without writing code.",
            "score": 0.88,
        },
    ],
    "answer": "No-code AI tools are trending for coaching businesses in 2026.",
}


@pytest.mark.asyncio
async def test_research_output_has_required_keys(base_state: AgentState):
    """research_node should populate research_output with 'topics' and 'competitor_content'."""
    with patch("src.agents.research_agent.TavilyClient") as mock_client_class, \
         patch.dict("os.environ", {"TAVILY_API_KEY": "test-key"}):

        mock_client = MagicMock()
        mock_client.search.return_value = MOCK_TAVILY_RESPONSE
        mock_client_class.return_value = mock_client

        from src.agents.research_agent import research_node

        result_state = await research_node(base_state)

    assert result_state.research_output is not None
    assert "topics" in result_state.research_output
    assert "competitor_content" in result_state.research_output


@pytest.mark.asyncio
async def test_research_topics_are_non_empty(base_state: AgentState):
    """Topics list should contain at least one item when Tavily returns results."""
    with patch("src.agents.research_agent.TavilyClient") as mock_client_class, \
         patch.dict("os.environ", {"TAVILY_API_KEY": "test-key"}):

        mock_client = MagicMock()
        mock_client.search.return_value = MOCK_TAVILY_RESPONSE
        mock_client_class.return_value = mock_client

        from src.agents.research_agent import research_node

        result_state = await research_node(base_state)

    topics = result_state.research_output["topics"]
    assert len(topics) > 0
    assert all("title" in t for t in topics)
    assert all("url" in t for t in topics)


@pytest.mark.asyncio
async def test_research_gracefully_handles_missing_api_key(base_state: AgentState):
    """When TAVILY_API_KEY is missing, research_node should append an error."""
    with patch.dict("os.environ", {}, clear=True):
        import os

        os.environ.pop("TAVILY_API_KEY", None)

        from src.agents.research_agent import research_node

        result_state = await research_node(base_state)

    assert len(result_state.errors) > 0
    assert any("TAVILY_API_KEY" in err for err in result_state.errors)


@pytest.mark.asyncio
async def test_research_appends_error_on_tavily_exception(base_state: AgentState):
    """When Tavily raises an exception, the node should catch it."""
    with patch("src.agents.research_agent.TavilyClient") as mock_client_class, \
         patch.dict("os.environ", {"TAVILY_API_KEY": "test-key"}):

        mock_client = MagicMock()
        mock_client.search.side_effect = ConnectionError("Tavily API unreachable")
        mock_client_class.return_value = mock_client

        from src.agents.research_agent import research_node

        result_state = await research_node(base_state)

    assert isinstance(result_state, AgentState)
    assert len(result_state.errors) > 0


@pytest.mark.asyncio
async def test_research_state_cycle_id_preserved(base_state: AgentState):
    """The cycle_id should remain unchanged after the research node runs."""
    with patch("src.agents.research_agent.TavilyClient") as mock_client_class, \
         patch.dict("os.environ", {"TAVILY_API_KEY": "test-key"}):

        mock_client = MagicMock()
        mock_client.search.return_value = MOCK_TAVILY_RESPONSE
        mock_client_class.return_value = mock_client

        from src.agents.research_agent import research_node

        original_cycle_id = base_state.cycle_id
        result_state = await research_node(base_state)

    assert result_state.cycle_id == original_cycle_id

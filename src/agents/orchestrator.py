"""
Orchestrator for the Growth Agent pipeline.

Defines AgentState and the LangGraph StateGraph that wires all nodes:
load_memory -> research -> content -> await_approval -> linkedin -> evaluate -> update_memory -> END
"""

import uuid
from typing import Any, Dict, List, Optional

from langgraph.graph import END, StateGraph
from langgraph.checkpoint.memory import MemorySaver
from pydantic import BaseModel, Field


class AgentState(BaseModel):
    """
    Shared state passed between all nodes in the LangGraph pipeline.
    Each node receives this state, mutates it, and returns the updated version.
    """

    user_id: str = Field(..., description="Unique identifier for the BuildAI user")
    niche: str = Field(
        ..., description="User's content niche, e.g. 'no-code app building for coaches'"
    )
    cycle_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique ID for this agent cycle run",
    )
    memory_context: List[str] = Field(
        default_factory=list,
        description="Retrieved Mem0 memories injected into content prompts",
    )
    research_output: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Output from research node: trending topics and competitor content",
    )
    content_drafts: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Generated blog post drafts pending human approval",
    )
    approved_ids: List[str] = Field(
        default_factory=list,
        description="Draft IDs that have been approved via the /approve endpoint",
    )
    linkedin_posts: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="LinkedIn posts created for each approved draft",
    )
    analytics_scores: Dict[str, Any] = Field(
        default_factory=dict,
        description="LLM-as-judge scores and reasoning for published content",
    )
    errors: List[str] = Field(
        default_factory=list,
        description="Non-fatal errors accumulated across all nodes",
    )

    class Config:
        arbitrary_types_allowed = True


# ── Node wrappers ─────────────────────────────────────────────────────────────


async def load_memory_node(state: AgentState) -> AgentState:
    """
    Pipeline entry: fetch recent memories from Mem0 to guide content creation.
    Memories tell the agent which topics, keywords, and formats worked previously.
    """
    from src.memory.mem0_client import retrieve_memories

    print(f"\n[orchestrator] >> load_memory | cycle={state.cycle_id}")
    try:
        memories = await retrieve_memories(
            user_id=state.user_id,
            query=f"best performing content in {state.niche}",
            limit=5,
        )
        state.memory_context = memories
        print(f"[orchestrator] [OK] Loaded {len(memories)} memories")
    except Exception as e:
        state.errors.append(f"load_memory: {str(e)}")
        print(f"[orchestrator] [FAIL] Memory load failed: {e}")
    return state


async def await_approval_node(state: AgentState) -> AgentState:
    """
    Human-in-the-loop pause. The graph is interrupted here.
    Resume is triggered externally via POST /approve/{draft_id} from the FastAPI API.
    """
    print(f"\n[orchestrator] [PAUSE] await_approval | waiting for human input")
    print(
        f"[orchestrator]    Pending drafts: "
        f"{[d.get('id') for d in state.content_drafts]}"
    )
    # The actual interrupt is configured at graph compile time via interrupt_before.
    # When resumed, approved_ids will have been updated by the /approve endpoint.
    return state


async def update_memory_node(state: AgentState) -> AgentState:
    """
    Final node: persist cycle results to Mem0 so future cycles improve.
    Stores scored content data for retrieval in the next run.
    """
    from src.memory.mem0_client import store_cycle_memory

    print(f"\n[orchestrator] >> update_memory | cycle={state.cycle_id}")
    try:
        await store_cycle_memory(
            user_id=state.user_id,
            niche=state.niche,
            cycle_id=state.cycle_id,
            content_drafts=state.content_drafts,
            analytics_scores=state.analytics_scores,
        )
        print(f"[orchestrator] [OK] Memory updated for cycle {state.cycle_id}")
    except Exception as e:
        state.errors.append(f"update_memory: {str(e)}")
        print(f"[orchestrator] [FAIL] Memory update failed: {e}")
    return state


# ── Graph builder ─────────────────────────────────────────────────────────────


def build_graph() -> StateGraph:
    """
    Construct and compile the LangGraph StateGraph for the growth agent pipeline.

    Flow:
        load_memory -> research -> content -> await_approval
                   -> linkedin -> evaluate -> update_memory -> END

    The graph is compiled with MemorySaver checkpointing so the await_approval
    node can be interrupted and resumed across separate HTTP requests.
    """
    from src.agents.research_agent import research_node
    from src.agents.content_agent import content_node
    from src.agents.linkedin_agent import linkedin_node
    from src.agents.analytics_agent import analytics_node

    graph = StateGraph(AgentState)

    # Register all nodes
    graph.add_node("load_memory", load_memory_node)
    graph.add_node("research", research_node)
    graph.add_node("content", content_node)
    graph.add_node("await_approval", await_approval_node)
    graph.add_node("linkedin", linkedin_node)
    graph.add_node("evaluate", analytics_node)
    graph.add_node("update_memory", update_memory_node)

    # Wire edges in order
    graph.set_entry_point("load_memory")
    graph.add_edge("load_memory", "research")
    graph.add_edge("research", "content")
    graph.add_edge("content", "await_approval")
    graph.add_edge("await_approval", "linkedin")
    graph.add_edge("linkedin", "evaluate")
    graph.add_edge("evaluate", "update_memory")
    graph.add_edge("update_memory", END)

    # Compile with in-memory checkpointing for interrupt/resume support
    checkpointer = MemorySaver()
    compiled = graph.compile(
        checkpointer=checkpointer,
        interrupt_before=["await_approval"],
    )

    return compiled


# Singleton graph instance used by the API and main entry point
growth_graph = build_graph()

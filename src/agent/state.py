"""
Shared State for Multi-Agent System

Uses TypedDict for LangGraph state management.
Postgres checkpointer persists state across runs.
"""
from typing import TypedDict, Annotated, Sequence, Literal
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """State shared across all agents in the graph."""
    
    # Core context
    order_id: int
    order: dict
    signal_type: str
    signal_reason: str
    mocked_customer_response: str  # For demo: "refund", "reschedule", or None
    
    # Message history (with reducer for appending)
    messages: Annotated[Sequence[BaseMessage], add_messages]
    
    # Tracking
    actions_taken: list[str]  # Log of actions for supervisor context
    current_specialist: str | None  # Which specialist is active
    
    # Resolution
    status: Literal["in_progress", "resolved", "failed"]
    resolution: str | None  # Final resolution summary
    
    # Conversation turns for DB storage
    conversation_turns: list[dict]


def create_initial_state(order: dict, signal_type: str, signal_reason: str) -> AgentState:
    """Create initial state for a new resolution workflow."""
    return AgentState(
        order_id=order["id"],
        order=order,
        signal_type=signal_type,
        signal_reason=signal_reason,
        mocked_customer_response=order.get("mocked_customer_response", ""),
        messages=[],
        actions_taken=[],
        current_specialist=None,
        status="in_progress",
        resolution=None,
        conversation_turns=[],
    )

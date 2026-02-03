"""
Shared State for Multi-Agent System

Uses TypedDict for LangGraph state management.
Postgres checkpointer persists state across runs.
"""
import operator
from datetime import datetime
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
    
    # Tracking (with reducers for safe concurrent updates)
    actions_taken: Annotated[list[str], operator.add]  # Log of actions
    current_specialist: str | None  # Which specialist is active
    turn_count: int  # Number of supervisor turns (for max_turns enforcement)
    
    # Error handling
    error: str | None  # Last error message
    error_count: int  # Number of errors encountered
    last_error_node: str | None  # Which node caused the last error
    
    # Timestamps
    created_at: str  # ISO format
    updated_at: str  # ISO format
    
    # Resolution
    status: Literal["in_progress", "resolved", "failed", "error"]
    resolution: str | None  # Final resolution summary
    
    # Conversation turns for DB storage (with reducer)
    conversation_turns: Annotated[list[dict], operator.add]


def create_initial_state(order: dict, signal_type: str, signal_reason: str) -> AgentState:
    """Create initial state for a new resolution workflow.
    
    Validates input using Pydantic models before creating state.
    Raises ValidationError if input is invalid.
    """
    from src.agent.models import validate_order
    
    # Validate order data (fails fast on bad input)
    validated_order = validate_order(order)
    order_dict = validated_order.to_dict()
    
    now = datetime.utcnow().isoformat()
    return AgentState(
        order_id=order_dict["id"],
        order=order_dict,
        signal_type=signal_type,
        signal_reason=signal_reason,
        mocked_customer_response=order_dict.get("mocked_customer_response", ""),
        messages=[],
        actions_taken=[],
        current_specialist=None,
        turn_count=0,
        error=None,
        error_count=0,
        last_error_node=None,
        created_at=now,
        updated_at=now,
        status="in_progress",
        resolution=None,
        conversation_turns=[],
    )

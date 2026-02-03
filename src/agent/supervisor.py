"""
LangGraph Supervisor Agent

True LLM-driven supervisor that:
1. Analyzes the situation
2. Decides which specialist to delegate to
3. Evaluates results
4. Iterates until resolution

Uses Postgres checkpointer for state persistence.
Uses Langfuse callbacks for observability.
"""
import os
import logging
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres import PostgresSaver
from langfuse.langchain import CallbackHandler as LangfuseHandler
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.agent.state import AgentState, create_initial_state
from src.agent.prompts import SUPERVISOR_SYSTEM_PROMPT
from src.agent.specialists import (
    create_customer_agent,
    create_operations_agent,
    create_resolution_agent,
)
from src.config import get_db_connection_string, AGENT_CONFIG


# ==================== STRUCTURED OUTPUT MODELS ====================

class RoutingDecision(BaseModel):
    """Structured output for supervisor routing decisions."""
    reasoning: str = Field(description="Brief explanation of why this specialist was chosen")
    next_specialist: Literal["operations", "customer", "resolution", "finish"] = Field(
        description="Which specialist to delegate to, or 'finish' if resolved"
    )
    task_description: str = Field(description="Specific task for the specialist to execute")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence in this decision (0-1)")

logger = logging.getLogger("agent.supervisor")

# Configure logging format for clear demo output
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)


# ==================== LANGFUSE SETUP ====================

def get_langfuse_handler(order_id: int, signal_type: str) -> LangfuseHandler | None:
    """Create Langfuse callback handler for tracing.
    
    Langfuse reads credentials from environment:
    - LANGFUSE_SECRET_KEY
    - LANGFUSE_PUBLIC_KEY  
    - LANGFUSE_HOST (optional)
    
    Returns None if Langfuse is not configured.
    """
    # Check if Langfuse is configured
    if not os.getenv("LANGFUSE_SECRET_KEY") or not os.getenv("LANGFUSE_PUBLIC_KEY"):
        logger.info("[LANGFUSE] Not configured, skipping tracing")
        return None
    
    try:
        # LangfuseHandler for LangChain reads env vars automatically
        # Set trace name via session_id and user_id for grouping
        handler = LangfuseHandler(
            session_id=f"order_{order_id}",
            user_id=f"agent_{signal_type.lower()}",
            tags=["logistics", "multi-agent", signal_type.lower()],
            metadata={"order_id": order_id, "signal_type": signal_type},
        )
        
        logger.info(f"[LANGFUSE] Handler created for order #{order_id}")
        return handler
        
    except Exception as e:
        logger.warning(f"[LANGFUSE] Failed to initialize: {e}")
        return None


# ==================== POSTGRES CHECKPOINTER ====================

# Connection pool for checkpointer (module-level singleton)
_checkpointer_pool = None

def get_checkpointer() -> PostgresSaver | None:
    """Create Postgres checkpointer for state persistence.
    
    Uses connection pool pattern required by langgraph-checkpoint-postgres 2.0+.
    Returns None if connection fails.
    """
    global _checkpointer_pool
    
    try:
        from psycopg_pool import ConnectionPool
        
        conn_string = get_db_connection_string()
        
        if _checkpointer_pool is None:
            _checkpointer_pool = ConnectionPool(conninfo=conn_string, open=True)
        
        checkpointer = PostgresSaver(_checkpointer_pool)
        checkpointer.setup()  # Ensure checkpoint tables exist
        return checkpointer
        
    except Exception as e:
        logger.warning(f"[CHECKPOINTER] Failed to create: {e}")
        return None


# ==================== SUPERVISOR NODE ====================

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((TimeoutError, ConnectionError)),
)
def _invoke_supervisor_llm(llm, messages: list, config: dict) -> RoutingDecision:
    """Invoke LLM with structured output and retry logic."""
    structured_llm = llm.with_structured_output(RoutingDecision)
    return structured_llm.invoke(messages, config=config)


def supervisor_node(state: AgentState, config: RunnableConfig | None = None) -> dict:
    """
    Supervisor decides next action based on current state.
    
    Uses structured output for reliable routing decisions.
    Enforces max_turns limit from AGENT_CONFIG.
    """
    turn_count = state.get("turn_count", 0) + 1
    max_turns = AGENT_CONFIG["max_turns"]
    error_count = state.get("error_count", 0)
    
    logger.info(
        "supervisor_turn",
        extra={"order_id": state["order_id"], "turn": turn_count, "max_turns": max_turns}
    )
    
    # Enforce max_turns limit
    if turn_count >= max_turns:
        logger.warning(
            "max_turns_reached",
            extra={"order_id": state["order_id"], "turn": turn_count}
        )
        return {
            "current_specialist": "finish",
            "turn_count": turn_count,
            "updated_at": datetime.utcnow().isoformat(),
            "resolution": f"Max turns ({max_turns}) reached. Actions: {', '.join(state['actions_taken']) if state['actions_taken'] else 'none'}",
            "conversation_turns": [{
                "role": "supervisor",
                "action": "max_turns_reached",
                "message": f"Stopping after {max_turns} turns",
            }],
        }
    
    # Build context for supervisor (structured output needs clear instructions)
    context = f"""Analyze this logistics issue and decide next action:

Order: #{state['order_id']}
Signal: {state['signal_type']} - {state['signal_reason']}
Route: {state['order'].get('origin_region')} → {state['order'].get('destination_region')}
Customer: rating {state['order'].get('customer_rating')}/5, {state['order'].get('customer_care_calls')} care calls
Demo preference: {state['mocked_customer_response']}

Actions completed: {state['actions_taken'] if state['actions_taken'] else 'None yet'}

Guidelines:
- STUCK_AT_HUB: operations → customer → resolution
- PREDICTED_DELAY: customer → resolution  
- TICKET_RAISED: customer (empathy) → resolution (refund)
- Use 'finish' only after resolution action is complete"""
    
    llm = ChatOpenAI(
        model=AGENT_CONFIG["supervisor_model"],
        temperature=AGENT_CONFIG["supervisor_temperature"],
        timeout=30,  # P0: Timeout handling
    )
    
    messages = [
        SystemMessage(content=SUPERVISOR_SYSTEM_PROMPT),
        HumanMessage(content=context),
    ]
    
    try:
        # Use structured output with retry
        decision = _invoke_supervisor_llm(llm, messages, config or {})
        next_node = decision.next_specialist
        task = decision.task_description
        reasoning = decision.reasoning
        
        logger.info(
            "routing_decision",
            extra={
                "order_id": state["order_id"],
                "next": next_node,
                "confidence": decision.confidence,
                "reasoning": reasoning[:100],
            }
        )
        
    except Exception as e:
        # Error handling - track and fallback
        error_count += 1
        logger.error(
            "supervisor_error",
            extra={"order_id": state["order_id"], "error": str(e), "error_count": error_count}
        )
        
        # Fallback logic based on state
        if error_count >= 3:
            return {
                "current_specialist": "finish",
                "turn_count": turn_count,
                "error": str(e),
                "error_count": error_count,
                "last_error_node": "supervisor",
                "status": "error",
                "updated_at": datetime.utcnow().isoformat(),
                "resolution": f"Error after {error_count} attempts: {str(e)[:100]}",
                "conversation_turns": [{
                    "role": "supervisor",
                    "action": "error",
                    "message": f"Failed after {error_count} attempts",
                }],
            }
        
        # Simple fallback routing
        if not state['actions_taken']:
            next_node = "operations" if state['signal_type'] == "STUCK_AT_HUB" else "customer"
        elif len(state['actions_taken']) >= 2:
            next_node = "resolution"
        else:
            next_node = "customer"
        
        task = f"Handle order #{state['order_id']} - {state['signal_type']}"
        reasoning = f"Fallback due to error: {str(e)[:50]}"
    
    # Resolution text for finish
    resolution = "Resolved" if next_node == "finish" else state.get("resolution")
    
    # Add supervisor turn to conversation
    supervisor_turn = {
        "role": "supervisor",
        "action": f"delegate_to_{next_node}",
        "message": reasoning[:500],
    }
    
    return {
        "current_specialist": next_node,
        "messages": [HumanMessage(content=task)],
        "resolution": resolution,
        "conversation_turns": [supervisor_turn],
        "turn_count": turn_count,
        "error_count": error_count,
        "updated_at": datetime.utcnow().isoformat(),
    }


def finish_node(state: AgentState, config: RunnableConfig | None = None) -> dict:
    """Mark resolution as complete."""
    logger.info(
        "resolution_complete",
        extra={"order_id": state["order_id"], "actions_count": len(state.get("actions_taken", []))}
    )
    
    # Truncate resolution to fit DB (max 200 chars)
    resolution_summary = (state.get("resolution") or "Issue resolved successfully.")[:200]
    
    # Final turn
    final_turn = {
        "role": "supervisor",
        "action": "finish",
        "message": f"Resolution complete: {resolution_summary[:100]}",
    }
    
    return {
        "status": "resolved",
        "resolution": resolution_summary,
        "current_specialist": None,
        "conversation_turns": [final_turn],
        "updated_at": datetime.utcnow().isoformat(),
    }


# ==================== ROUTING ====================

def route_after_supervisor(state: AgentState) -> Literal["operations", "customer", "resolution", "finish"]:
    """Route to the specialist chosen by supervisor."""
    specialist = state.get("current_specialist", "finish")
    if specialist in ["operations", "customer", "resolution", "finish"]:
        return specialist
    return "finish"


# ==================== GRAPH CONSTRUCTION ====================

def build_graph() -> StateGraph:
    """Build the multi-agent LangGraph."""
    
    # Create specialist nodes
    operations_agent = create_operations_agent()
    customer_agent = create_customer_agent()
    resolution_agent = create_resolution_agent()
    
    # Build graph
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("operations", operations_agent)
    workflow.add_node("customer", customer_agent)
    workflow.add_node("resolution", resolution_agent)
    workflow.add_node("finish", finish_node)
    
    # Set entry point
    workflow.set_entry_point("supervisor")
    
    # Add conditional edges from supervisor
    workflow.add_conditional_edges(
        "supervisor",
        route_after_supervisor,
        {
            "operations": "operations",
            "customer": "customer",
            "resolution": "resolution",
            "finish": "finish",
        }
    )
    
    # All specialists return to supervisor for evaluation
    workflow.add_edge("operations", "supervisor")
    workflow.add_edge("customer", "supervisor")
    workflow.add_edge("resolution", "supervisor")
    
    # Finish ends the graph
    workflow.add_edge("finish", END)
    
    return workflow


# ==================== MAIN ENTRY POINT ====================

def run_supervisor(
    order: dict,
    signal_type: str,
    signal_reason: str,
    use_checkpointer: bool = True,
) -> dict:
    """
    Run the multi-agent supervisor to resolve an issue.
    
    Args:
        order: Order data dict
        signal_type: Risk signal type (PREDICTED_DELAY, STUCK_AT_HUB, TICKET_RAISED)
        signal_reason: Human-readable reason for the signal
        use_checkpointer: Whether to use Postgres checkpointer (default True)
    
    Returns:
        dict with status, resolution, and conversation_turns
    """
    order_id = order["id"]
    logger.info(f"{'='*60}")
    logger.info(f"[SUPERVISOR] Starting resolution for order #{order_id}")
    logger.info(f"[SUPERVISOR] Signal: {signal_type} - {signal_reason}")
    logger.info(f"{'='*60}")
    
    # Create initial state
    initial_state = create_initial_state(order, signal_type, signal_reason)
    
    # Build graph
    workflow = build_graph()
    
    # Compile with optional checkpointer
    if use_checkpointer:
        checkpointer = get_checkpointer()
        if checkpointer:
            graph = workflow.compile(checkpointer=checkpointer)
            logger.info("[SUPERVISOR] Using Postgres checkpointer")
        else:
            logger.warning("[SUPERVISOR] Checkpointer unavailable, running without persistence")
            graph = workflow.compile()
    else:
        graph = workflow.compile()
    
    # Create Langfuse handler (may be None if not configured)
    langfuse_handler = get_langfuse_handler(order_id, signal_type)
    
    # Run config
    callbacks = [langfuse_handler] if langfuse_handler else []
    config = {
        "configurable": {"thread_id": f"order_{order_id}_{signal_type}"},
        "callbacks": callbacks,
    }
    
    # Execute graph
    try:
        final_state = graph.invoke(initial_state, config)
        
        logger.info(f"{'='*60}")
        logger.info(f"[SUPERVISOR] ✓ Completed for order #{order_id}")
        logger.info(f"[SUPERVISOR] Status: {final_state.get('status')}")
        logger.info(f"[SUPERVISOR] Resolution: {final_state.get('resolution')}")
        logger.info(f"{'='*60}")
        
        return {
            "order_id": order_id,
            "status": final_state.get("status", "resolved"),
            "resolution": final_state.get("resolution"),
            "actions_taken": final_state.get("actions_taken", []),
            "conversation_turns": final_state.get("conversation_turns", []),
        }
        
    except Exception as e:
        logger.error(f"[SUPERVISOR] Error resolving order #{order_id}: {e}")
        return {
            "order_id": order_id,
            "status": "failed",
            "resolution": f"Error: {str(e)}",
            "actions_taken": [],
            "conversation_turns": [],
        }
    finally:
        # Flush Langfuse if configured
        if langfuse_handler:
            langfuse_handler.flush()

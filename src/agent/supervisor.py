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
from typing import Literal

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres import PostgresSaver
from langfuse.langchain import CallbackHandler as LangfuseHandler

from src.agent.state import AgentState, create_initial_state
from src.agent.prompts import SUPERVISOR_SYSTEM_PROMPT
from src.agent.specialists import (
    create_customer_agent,
    create_operations_agent,
    create_resolution_agent,
)
from src.config import get_db_connection_string, AGENT_CONFIG

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
    
    Langfuse v3 reads credentials from environment:
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
        from langfuse import Langfuse
        
        # Initialize Langfuse client to create trace context
        langfuse = Langfuse()
        
        # Create a trace for this resolution
        trace = langfuse.trace(
            name=f"resolve_{signal_type.lower()}_{order_id}",
            session_id=f"order_{order_id}",
            tags=["logistics", "multi-agent", signal_type.lower()],
            metadata={"order_id": order_id, "signal_type": signal_type},
        )
        
        logger.info(f"[LANGFUSE] Trace created: {trace.id}")
        
        # Return callback handler with trace context
        return LangfuseHandler(
            trace_context={
                "trace_id": trace.id,
                "observation_id": None,
            }
        )
    except Exception as e:
        logger.warning(f"[LANGFUSE] Failed to initialize: {e}")
        return None


# ==================== POSTGRES CHECKPOINTER ====================

def get_checkpointer() -> PostgresSaver:
    """Create Postgres checkpointer for state persistence."""
    conn_string = get_db_connection_string()
    return PostgresSaver.from_conn_string(conn_string)


# ==================== SUPERVISOR NODE ====================

def supervisor_node(state: AgentState, config: dict = None) -> dict:
    """
    Supervisor decides next action based on current state.
    
    Returns routing decision: OPERATIONS, CUSTOMER, RESOLUTION, or FINISH
    Enforces max_turns limit from AGENT_CONFIG.
    """
    turn_count = state.get("turn_count", 0) + 1
    max_turns = AGENT_CONFIG["max_turns"]
    
    logger.info(f"[SUPERVISOR] Turn {turn_count}/{max_turns} for order #{state['order_id']}")
    
    # Enforce max_turns limit
    if turn_count >= max_turns:
        logger.warning(f"[SUPERVISOR] Max turns ({max_turns}) reached, forcing finish")
        return {
            "current_specialist": "finish",
            "turn_count": turn_count,
            "resolution": f"Resolution stopped: max turns ({max_turns}) reached. Actions taken: {', '.join(state['actions_taken']) if state['actions_taken'] else 'none'}",
            "conversation_turns": state["conversation_turns"] + [{
                "role": "supervisor",
                "action": "max_turns_reached",
                "message": f"Stopping after {max_turns} turns",
            }],
        }
    
    # Build context for supervisor
    context = f"""
Current situation:
- Order: #{state['order_id']}
- Signal: {state['signal_type']} - {state['signal_reason']}
- Route: {state['order'].get('origin_region')} → {state['order'].get('destination_region')}
- Customer rating: {state['order'].get('customer_rating')}/5
- Care calls: {state['order'].get('customer_care_calls')}
- Mocked customer preference (for demo): {state['mocked_customer_response']}

Actions taken so far:
{chr(10).join(f"- {a}" for a in state['actions_taken']) if state['actions_taken'] else "None yet"}

Decide: Which specialist should act next, or is this resolved?
Respond with your reasoning, then on the last line write exactly one of:
NEXT: OPERATIONS
NEXT: CUSTOMER  
NEXT: RESOLUTION
NEXT: FINISH
"""
    
    llm = ChatOpenAI(
        model=AGENT_CONFIG["supervisor_model"],
        temperature=AGENT_CONFIG["supervisor_temperature"],
    )
    
    messages = [
        SystemMessage(content=SUPERVISOR_SYSTEM_PROMPT),
        HumanMessage(content=context),
    ]
    
    response = llm.invoke(messages, config=config or {})
    response_text = response.content
    
    logger.info(f"[SUPERVISOR] Thinking: {response_text[:200]}...")
    
    # Parse the routing decision
    response_lower = response_text.lower()
    if "next: finish" in response_lower or "finish" in response_lower.split('\n')[-1]:
        next_node = "finish"
        # Extract resolution summary
        resolution = response_text.split("NEXT:")[0].strip() if "NEXT:" in response_text else response_text
    elif "next: operations" in response_lower:
        next_node = "operations"
        resolution = None
    elif "next: customer" in response_lower:
        next_node = "customer"
        resolution = None
    elif "next: resolution" in response_lower:
        next_node = "resolution"
        resolution = None
    else:
        # Default to finish if unclear after multiple actions
        if len(state['actions_taken']) >= 3:
            next_node = "finish"
            resolution = "Resolution completed based on actions taken."
        else:
            # Try to infer from signal type
            if state['signal_type'] == "STUCK_AT_HUB" and not state['actions_taken']:
                next_node = "operations"
            elif not state['actions_taken']:
                next_node = "customer"
            else:
                next_node = "resolution"
            resolution = None
    
    logger.info(f"[SUPERVISOR] Decision: → {next_node.upper()}")
    
    # Create task message for the specialist
    task_messages = {
        "operations": f"Check the hub status for order #{state['order_id']}. Contact the hub and report back.",
        "customer": f"Contact the customer about order #{state['order_id']}. Signal: {state['signal_type']}. Previous actions: {state['actions_taken']}. Offer appropriate resolution (refund/reschedule). Their mocked response will be: {state['mocked_customer_response']}",
        "resolution": f"Execute resolution for order #{state['order_id']}. Customer preference: {state['mocked_customer_response']}. Process the appropriate action.",
        "finish": "Resolution complete.",
    }
    
    task = task_messages.get(next_node, "Continue resolution.")
    
    # Add supervisor turn to conversation
    supervisor_turn = {
        "role": "supervisor",
        "action": f"delegate_to_{next_node}",
        "message": response_text[:500],
    }
    
    return {
        "current_specialist": next_node,
        "messages": [HumanMessage(content=task)],
        "resolution": resolution if next_node == "finish" else state.get("resolution"),
        "conversation_turns": state["conversation_turns"] + [supervisor_turn],
        "turn_count": turn_count,
    }


def finish_node(state: AgentState, config: dict = None) -> dict:
    """Mark resolution as complete."""
    logger.info(f"[SUPERVISOR] ✓ Resolution complete for order #{state['order_id']}")
    
    resolution_summary = state.get("resolution") or "Issue resolved successfully."
    
    # Final turn
    final_turn = {
        "role": "supervisor",
        "action": "finish",
        "message": f"Resolution complete: {resolution_summary}",
    }
    
    return {
        "status": "resolved",
        "resolution": resolution_summary,
        "current_specialist": None,
        "conversation_turns": state["conversation_turns"] + [final_turn],
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
        try:
            checkpointer = get_checkpointer()
            graph = workflow.compile(checkpointer=checkpointer)
            logger.info("[SUPERVISOR] Using Postgres checkpointer")
        except Exception as e:
            logger.warning(f"[SUPERVISOR] Checkpointer failed, running without: {e}")
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

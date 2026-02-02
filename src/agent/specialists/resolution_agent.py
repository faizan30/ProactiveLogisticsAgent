"""
Resolution Specialist

Executes final actions with policy validation:
- Checks policy before executing actions
- Processes refunds, reschedules, ticket closures
- Handles escalation when policy requires it

Uses get_policy tool (RAG-ready) for policy retrieval.
"""
import logging
from typing import TypedDict

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.prebuilt import create_react_agent

from src.agent.state import AgentState
from src.agent.prompts import RESOLUTION_SYSTEM_PROMPT
from src.agent.tools import (
    RESOLUTION_TOOLS,
    get_policy,
    process_refund,
    reschedule_delivery,
    close_ticket,
)
from src.config import AGENT_CONFIG

logger = logging.getLogger("agent.resolution")


# Concise prompt - output must be SHORT
RESOLUTION_WITH_POLICY_PROMPT = """You are a resolution specialist. Execute actions quickly.

IMPORTANT: Your final response must be ONE SHORT SENTENCE (max 15 words).

Workflow:
1. Execute action (refund or reschedule)
2. Close ticket
3. Reply with SHORT summary like: "Refund processed, ticket closed." or "Rescheduled to tomorrow, ticket closed."

Do NOT write long explanations. Just execute and give a brief result."""


def create_resolution_agent():
    """
    Create the ResolutionAgent with policy tools.
    
    This agent uses get_policy (RAG-ready) to check company policies
    before executing any resolution actions.
    """
    
    def resolution_agent_node(state: AgentState, config: dict = None) -> dict:
        """Execute ResolutionAgent with policy validation."""
        logger.info(f"[RESOLUTION] Starting for order #{state['order_id']}")
        
        # Get task from last message
        last_message = state["messages"][-1] if state["messages"] else None
        task = last_message.content if last_message else "Execute resolution based on customer preference"
        
        # Create ReAct agent with all resolution tools including policy
        llm = ChatOpenAI(
            model=AGENT_CONFIG["specialist_model"],
            temperature=0.0,
        )
        
        resolution_tools = [
            get_policy,
            process_refund,
            reschedule_delivery,
            close_ticket,
        ]
        
        agent = create_react_agent(llm, resolution_tools)
        
        # Build context with system prompt included
        customer_pref = state.get("mocked_customer_response", "unknown")
        customer_rating = state["order"].get("customer_rating", 3)
        care_calls = state["order"].get("customer_care_calls", 0)
        
        context = f"""{RESOLUTION_WITH_POLICY_PROMPT}

Order #{state['order_id']} | {state['signal_type']} | Customer wants: {customer_pref}
Execute now. Short reply only."""
        
        # Run the agent with strict recursion limit
        result = agent.invoke(
            {"messages": [HumanMessage(content=context)]},
            config={"recursion_limit": 5, **(config or {})},
        )
        
        # Extract final response and truncate to fit DB
        final_response = ""
        for msg in reversed(result.get("messages", [])):
            if isinstance(msg, AIMessage) and msg.content:
                final_response = msg.content[:100]  # Truncate to 100 chars
                break
        
        logger.info(f"[RESOLUTION] Result: {final_response}")
        
        # Build action log (short)
        action_log = f"resolution: {final_response}"
        
        # Build conversation turn
        turn = {
            "role": "resolution",
            "action": f"execute_{customer_pref}",
            "message": final_response,
        }
        
        return {
            "actions_taken": state["actions_taken"] + [action_log],
            "current_specialist": None,
            "messages": [AIMessage(content=f"[resolution] {final_response}")],
            "conversation_turns": state["conversation_turns"] + [turn],
        }
    
    return resolution_agent_node

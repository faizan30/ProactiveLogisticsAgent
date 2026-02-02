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


# Updated prompt that emphasizes policy checking
RESOLUTION_WITH_POLICY_PROMPT = """You are a resolution specialist who executes actions.

## CRITICAL: Check Policy First
Before executing actions, call get_policy to understand the rules.

## Your Capabilities
- Process refunds (full refund)
- Reschedule deliveries
- Close support tickets

## Workflow
1. Understand what resolution the customer wants
2. Get the policy using get_policy tool
3. Execute the appropriate action (refund or reschedule)
4. Close the ticket with resolution summary

## Guidelines
- Check policy before acting
- Refund is binary (full refund or no refund)
- Reschedule within allowed timeframe (7 days)

Use your tools: get_policy → execute action → close_ticket"""


def create_resolution_agent():
    """
    Create the ResolutionAgent with policy tools.
    
    This agent uses get_policy (RAG-ready) to check company policies
    before executing any resolution actions.
    """
    
    def resolution_agent_node(state: AgentState, config: dict) -> dict:
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
        
        agent = create_react_agent(
            llm,
            resolution_tools,
            state_modifier=RESOLUTION_WITH_POLICY_PROMPT,
        )
        
        # Build context
        customer_pref = state.get("mocked_customer_response", "unknown")
        customer_rating = state["order"].get("customer_rating", 3)
        care_calls = state["order"].get("customer_care_calls", 0)
        
        context = f"""
Task: {task}
Order ID: #{state['order_id']}
Issue: {state['signal_type']} - {state['signal_reason']}
Customer Preference: {customer_pref}
Customer Rating: {customer_rating}/5
Care Calls: {care_calls}

Previous actions: {', '.join(state['actions_taken']) if state['actions_taken'] else 'None'}

Execute the appropriate resolution:
1. First, get the policy for the action type ({customer_pref})
2. Check if the action is approved
3. Execute if approved, or report escalation needed
4. Close the ticket with summary
"""
        
        # Run the agent
        result = agent.invoke(
            {"messages": [HumanMessage(content=context)]},
            config=config,
        )
        
        # Extract final response
        final_response = ""
        for msg in reversed(result.get("messages", [])):
            if isinstance(msg, AIMessage) and msg.content:
                final_response = msg.content
                break
        
        logger.info(f"[RESOLUTION] Result: {final_response[:200]}...")
        
        # Build action log
        action_log = f"resolution: {final_response[:200]}"
        
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

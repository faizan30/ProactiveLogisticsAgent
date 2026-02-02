"""
Customer Communication Specialist

Multi-agent system for customer communication:
- DrafterAgent: Generates empathetic message drafts
- CriticAgent: Evaluates and improves drafts
- Then sends the approved message

This is a true multi-agent system with internal LLM-driven agents.
"""
import logging
from typing import TypedDict, Annotated

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, END

from src.agent.state import AgentState
from src.agent.prompts import (
    CUSTOMER_SYSTEM_PROMPT,
    DRAFTER_SYSTEM_PROMPT,
    CRITIC_SYSTEM_PROMPT,
)
from src.agent.tools import CUSTOMER_TOOLS, send_message, get_customer_response
from src.config import AGENT_CONFIG

logger = logging.getLogger("agent.customer")


# ==================== INTERNAL STATE ====================

class CustomerAgentState(TypedDict):
    """Internal state for CustomerAgent sub-agents."""
    task: str
    order_id: int
    signal_type: str
    signal_reason: str
    mocked_customer_response: str
    draft_message: str
    critique: str
    revision_count: int
    final_message: str
    customer_response: str
    approved: bool


# ==================== SUB-AGENTS ====================

def drafter_agent(state: CustomerAgentState) -> dict:
    """DrafterAgent: Creates empathetic customer message."""
    logger.info(f"[DRAFTER] Creating message for order #{state['order_id']}")
    
    llm = ChatOpenAI(
        model=AGENT_CONFIG["specialist_model"],
        temperature=0.7,  # Slightly creative for empathy
    )
    
    context = f"""
Task: {state['task']}
Order ID: #{state['order_id']}
Issue: {state['signal_type']} - {state['signal_reason']}
Customer's expected response: {state['mocked_customer_response']}

{f"Previous critique to address: {state['critique']}" if state.get('critique') else ""}

Draft a message to the customer about this issue.
"""
    
    messages = [
        SystemMessage(content=DRAFTER_SYSTEM_PROMPT),
        HumanMessage(content=context),
    ]
    
    response = llm.invoke(messages)
    draft = response.content.strip()
    
    logger.info(f"[DRAFTER] Draft created: {draft[:100]}...")
    
    return {
        "draft_message": draft,
        "revision_count": state.get("revision_count", 0) + 1,
    }


def critic_agent(state: CustomerAgentState) -> dict:
    """CriticAgent: Evaluates message quality."""
    logger.info(f"[CRITIC] Evaluating draft (revision #{state['revision_count']})")
    
    llm = ChatOpenAI(
        model=AGENT_CONFIG["specialist_model"],
        temperature=0.0,  # Deterministic for evaluation
    )
    
    context = f"""
Evaluate this customer message draft:

---
{state['draft_message']}
---

Context:
- Order #{state['order_id']}
- Issue: {state['signal_type']}
- Customer preference: {state['mocked_customer_response']}

Is this message ready to send, or does it need revision?
"""
    
    messages = [
        SystemMessage(content=CRITIC_SYSTEM_PROMPT),
        HumanMessage(content=context),
    ]
    
    response = llm.invoke(messages)
    critique = response.content.strip()
    
    approved = "APPROVED" in critique.upper()
    
    logger.info(f"[CRITIC] Result: {'APPROVED' if approved else 'NEEDS REVISION'}")
    
    return {
        "critique": critique,
        "approved": approved,
    }


def sender_agent(state: CustomerAgentState) -> dict:
    """SenderAgent: Sends approved message and gets response."""
    logger.info(f"[SENDER] Sending message for order #{state['order_id']}")
    
    # Use the tools to send message and get response
    send_result = send_message.invoke({
        "order_id": state["order_id"],
        "message": state["draft_message"],
    })
    
    response_result = get_customer_response.invoke({
        "order_id": state["order_id"],
        "mocked_response": state["mocked_customer_response"],
    })
    
    logger.info(f"[SENDER] Customer response: {response_result}")
    
    return {
        "final_message": state["draft_message"],
        "customer_response": response_result,
    }


# ==================== ROUTING ====================

def should_revise(state: CustomerAgentState) -> str:
    """Route based on critic approval and revision count."""
    if state.get("approved", False):
        return "sender"
    elif state.get("revision_count", 0) >= 2:
        logger.info("[CUSTOMER] Max revisions reached, sending anyway")
        return "sender"
    else:
        return "drafter"


# ==================== GRAPH CONSTRUCTION ====================

def build_customer_graph() -> StateGraph:
    """Build the internal CustomerAgent graph."""
    workflow = StateGraph(CustomerAgentState)
    
    # Add sub-agent nodes
    workflow.add_node("drafter", drafter_agent)
    workflow.add_node("critic", critic_agent)
    workflow.add_node("sender", sender_agent)
    
    # Set entry point
    workflow.set_entry_point("drafter")
    
    # Drafter -> Critic
    workflow.add_edge("drafter", "critic")
    
    # Critic -> conditional (revise or send)
    workflow.add_conditional_edges(
        "critic",
        should_revise,
        {
            "drafter": "drafter",
            "sender": "sender",
        }
    )
    
    # Sender -> END
    workflow.add_edge("sender", END)
    
    return workflow


# ==================== MAIN ENTRY ====================

def create_customer_agent():
    """
    Create the CustomerAgent as a multi-agent system.
    
    Returns a function compatible with the main supervisor graph.
    """
    # Pre-build and compile the internal graph
    internal_graph = build_customer_graph().compile()
    
    def customer_agent_node(state: AgentState, config: dict) -> dict:
        """Execute CustomerAgent with internal sub-agents."""
        logger.info(f"[CUSTOMER] Starting for order #{state['order_id']}")
        
        # Get task from last message
        last_message = state["messages"][-1] if state["messages"] else None
        task = last_message.content if last_message else "Contact customer about delivery issue"
        
        # Create internal state
        internal_state: CustomerAgentState = {
            "task": task,
            "order_id": state["order_id"],
            "signal_type": state["signal_type"],
            "signal_reason": state["signal_reason"],
            "mocked_customer_response": state.get("mocked_customer_response", ""),
            "draft_message": "",
            "critique": "",
            "revision_count": 0,
            "final_message": "",
            "customer_response": "",
            "approved": False,
        }
        
        # Run internal graph
        result = internal_graph.invoke(internal_state, config)
        
        # Build action log
        action_log = f"customer: Sent message to customer. Response: {result['customer_response'][:100]}"
        
        # Build conversation turn
        turn = {
            "role": "customer",
            "action": "send_message + get_response",
            "message": f"Sent: {result['final_message'][:100]}... | Response: {result['customer_response']}",
        }
        
        logger.info(f"[CUSTOMER] Completed. Customer chose: {result['customer_response']}")
        
        return {
            "actions_taken": state["actions_taken"] + [action_log],
            "current_specialist": None,
            "messages": [AIMessage(content=f"[customer] {result['customer_response']}")],
            "conversation_turns": state["conversation_turns"] + [turn],
        }
    
    return customer_agent_node

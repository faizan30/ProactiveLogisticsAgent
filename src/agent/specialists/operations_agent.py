"""
Operations Specialist

Multi-agent system for logistics operations:
- ResearcherAgent: Gathers context from DB and hub
- AnalyzerAgent: Synthesizes findings and recommendations

This is a true multi-agent system with internal LLM-driven agents.
"""
import logging
from typing import TypedDict

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import create_react_agent

from src.agent.state import AgentState
from src.agent.prompts import (
    OPERATIONS_SYSTEM_PROMPT,
    RESEARCHER_SYSTEM_PROMPT,
    ANALYZER_SYSTEM_PROMPT,
)
from src.agent.tools import (
    OPERATIONS_TOOLS,
    contact_hub,
    check_shipment_status,
)
from src.config import AGENT_CONFIG

logger = logging.getLogger("agent.operations")


# ==================== INTERNAL STATE ====================

class OperationsAgentState(TypedDict):
    """Internal state for OperationsAgent sub-agents."""
    task: str
    order_id: int
    signal_type: str
    signal_reason: str
    origin_region: str
    destination_region: str
    research_findings: str
    analysis: str
    hub_status: str


# ==================== SUB-AGENTS ====================

def researcher_agent(state: OperationsAgentState) -> dict:
    """ResearcherAgent: Contacts hub and checks shipment status."""
    logger.info(f"[RESEARCHER] Gathering context for order #{state['order_id']}")
    
    # Use operations tools directly - order data is already in state
    hub_response = contact_hub.invoke({"order_id": state['order_id']})
    shipment_status = check_shipment_status.invoke({"order_id": state['order_id']})
    
    # Compile findings from tools + state data
    research_summary = f"""
RESEARCH FINDINGS for Order #{state['order_id']}:

HUB STATUS:
{hub_response}

SHIPMENT STATUS:
{shipment_status}

ORDER CONTEXT (from state):
- Route: {state['origin_region']} → {state['destination_region']}
- Issue: {state['signal_type']} - {state['signal_reason']}
"""
    
    logger.info(f"[RESEARCHER] Findings compiled")
    
    return {
        "research_findings": research_summary,
    }


def analyzer_agent(state: OperationsAgentState) -> dict:
    """AnalyzerAgent: Analyzes findings and provides recommendations."""
    logger.info(f"[ANALYZER] Analyzing findings for order #{state['order_id']}")
    
    llm = ChatOpenAI(
        model=AGENT_CONFIG["specialist_model"],
        temperature=0.0,
    )
    
    # Also check shipment status
    shipment_status = check_shipment_status.invoke({"order_id": state["order_id"]})
    
    context = f"""
Order #{state['order_id']}
Issue: {state['signal_type']} - {state['signal_reason']}

RESEARCH FINDINGS:
{state['research_findings']}

CURRENT SHIPMENT STATUS:
{shipment_status}

Analyze this information and provide:
1. Root cause assessment
2. Customer context summary  
3. Recommended action
4. Any escalation flags
"""
    
    messages = [
        SystemMessage(content=ANALYZER_SYSTEM_PROMPT),
        HumanMessage(content=context),
    ]
    
    response = llm.invoke(messages)
    analysis = response.content.strip()
    
    logger.info(f"[ANALYZER] Analysis: {analysis[:200]}...")
    
    return {
        "analysis": analysis,
        "hub_status": shipment_status,
    }


# ==================== GRAPH CONSTRUCTION ====================

def build_operations_graph() -> StateGraph:
    """Build the internal OperationsAgent graph."""
    workflow = StateGraph(OperationsAgentState)
    
    # Add sub-agent nodes
    workflow.add_node("researcher", researcher_agent)
    workflow.add_node("analyzer", analyzer_agent)
    
    # Set entry point
    workflow.set_entry_point("researcher")
    
    # Researcher -> Analyzer -> END
    workflow.add_edge("researcher", "analyzer")
    workflow.add_edge("analyzer", END)
    
    return workflow


# ==================== MAIN ENTRY ====================

def create_operations_agent():
    """
    Create the OperationsAgent as a multi-agent system.
    
    Returns a function compatible with the main supervisor graph.
    """
    # Pre-build and compile the internal graph
    internal_graph = build_operations_graph().compile()
    
    def operations_agent_node(state: AgentState, config: RunnableConfig | None = None) -> dict:
        """Execute OperationsAgent with internal sub-agents."""
        logger.info(f"[OPERATIONS] Starting for order #{state['order_id']}")
        
        # Get task from last message
        last_message = state["messages"][-1] if state["messages"] else None
        task = last_message.content if last_message else "Investigate delivery issue"
        
        # Create internal state
        internal_state: OperationsAgentState = {
            "task": task,
            "order_id": state["order_id"],
            "signal_type": state["signal_type"],
            "signal_reason": state["signal_reason"],
            "origin_region": state["order"].get("origin_region", "Unknown"),
            "destination_region": state["order"].get("destination_region", "Unknown"),
            "research_findings": "",
            "analysis": "",
            "hub_status": "",
        }
        
        # Run internal graph
        result = internal_graph.invoke(internal_state, config or {})
        
        # Build action log
        action_log = f"operations: {result['analysis'][:200]}"
        
        # Build conversation turn
        turn = {
            "role": "operations",
            "action": "research + analyze",
            "message": result["analysis"],
        }
        
        logger.info(f"[OPERATIONS] Completed analysis")
        
        return {
            "actions_taken": state["actions_taken"] + [action_log],
            "current_specialist": None,
            "messages": [AIMessage(content=f"[operations] {result['analysis']}")],
            "conversation_turns": state["conversation_turns"] + [turn],
        }
    
    return operations_agent_node

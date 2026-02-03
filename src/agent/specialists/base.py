"""
Base Specialist Agent

Provides common functionality for all specialist agents.
Model is configurable via AGENT_CONFIG in src/config.py.
"""
import logging
from typing import Callable

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.prebuilt import create_react_agent

from src.agent.state import AgentState
from src.config import AGENT_CONFIG

logger = logging.getLogger("agent.specialists")


def create_specialist_node(
    name: str,
    system_prompt: str,
    tools: list,
    model: str | None = None,
) -> Callable[[AgentState], dict]:
    """
    Factory function to create a specialist agent node.
    
    Each specialist is a ReAct agent that:
    1. Receives a task from the supervisor
    2. Uses its tools to complete the task
    3. Returns results to update state
    
    Args:
        name: Agent name (for logging)
        system_prompt: System prompt defining agent's role
        tools: List of tools available to this agent
        model: LLM model to use (default: from AGENT_CONFIG)
    
    Returns:
        A function that can be used as a LangGraph node
    """
    # Use configured model if not explicitly provided
    model = model or AGENT_CONFIG["specialist_model"]
    
    def specialist_node(state: AgentState, config: dict) -> dict:
        """Execute specialist agent and return state updates."""
        logger.info(f"[{name.upper()}] Starting task execution")
        
        # Get the last message which contains the task
        last_message = state["messages"][-1] if state["messages"] else None
        if not last_message:
            logger.warning(f"[{name.upper()}] No task message found")
            return {"actions_taken": [f"{name}: No task provided"]}
        
        task = last_message.content if hasattr(last_message, 'content') else str(last_message)
        logger.info(f"[{name.upper()}] Task: {task[:100]}...")
        
        # Create the ReAct agent with tools
        # Note: We pass callbacks through config for Langfuse
        llm = ChatOpenAI(
            model=model,
            temperature=AGENT_CONFIG["specialist_temperature"],
        )
        
        # Build context message with order details
        context = f"""
Order #{state['order_id']}
Signal: {state['signal_type']} - {state['signal_reason']}
Route: {state['order'].get('origin_region')} → {state['order'].get('destination_region')}
Actions taken so far: {', '.join(state['actions_taken']) if state['actions_taken'] else 'None'}
Mocked customer response (for demo): {state['mocked_customer_response']}

Your task: {task}
"""
        
        # Create and run the agent
        agent = create_react_agent(
            llm,
            tools,
            state_modifier=system_prompt,
        )
        
        # Run the agent
        result = agent.invoke(
            {"messages": [HumanMessage(content=context)]},
            config=config,
        )
        
        # Extract the final response
        final_messages = result.get("messages", [])
        final_response = ""
        for msg in reversed(final_messages):
            if isinstance(msg, AIMessage) and msg.content:
                final_response = msg.content
                break
        
        logger.info(f"[{name.upper()}] Completed: {final_response[:100]}...")
        
        # Update state
        action_log = f"{name}: {final_response[:200]}"
        
        # Add conversation turn for DB storage
        turn = {
            "role": name.lower(),
            "action": task[:100],
            "message": final_response,
        }
        
        # Note: actions_taken and conversation_turns use operator.add reducer
        return {
            "actions_taken": [action_log],
            "current_specialist": None,
            "messages": [AIMessage(content=f"[{name}] {final_response}")],
            "conversation_turns": [turn],
        }
    
    return specialist_node

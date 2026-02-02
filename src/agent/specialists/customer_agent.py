"""
Customer Communication Specialist

Handles all customer-facing communication with empathy and professionalism.
"""
from src.agent.specialists.base import create_specialist_node
from src.agent.prompts import CUSTOMER_SYSTEM_PROMPT
from src.agent.tools import CUSTOMER_TOOLS


def create_customer_agent():
    """Create the customer communication specialist node."""
    return create_specialist_node(
        name="customer",
        system_prompt=CUSTOMER_SYSTEM_PROMPT,
        tools=CUSTOMER_TOOLS,
        model="gpt-4o-mini",
    )

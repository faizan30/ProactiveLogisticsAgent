"""
Operations Specialist

Handles hub inquiries and shipment status checks.
"""
from src.agent.specialists.base import create_specialist_node
from src.agent.prompts import OPERATIONS_SYSTEM_PROMPT
from src.agent.tools import OPERATIONS_TOOLS


def create_operations_agent():
    """Create the operations specialist node."""
    return create_specialist_node(
        name="operations",
        system_prompt=OPERATIONS_SYSTEM_PROMPT,
        tools=OPERATIONS_TOOLS,
        model="gpt-4o-mini",
    )

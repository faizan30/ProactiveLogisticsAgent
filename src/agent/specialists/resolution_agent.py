"""
Resolution Specialist

Executes final actions: refunds, reschedules, ticket closure.
"""
from src.agent.specialists.base import create_specialist_node
from src.agent.prompts import RESOLUTION_SYSTEM_PROMPT
from src.agent.tools import RESOLUTION_TOOLS


def create_resolution_agent():
    """Create the resolution specialist node."""
    return create_specialist_node(
        name="resolution",
        system_prompt=RESOLUTION_SYSTEM_PROMPT,
        tools=RESOLUTION_TOOLS,
        model="gpt-4o-mini",
    )

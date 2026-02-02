"""
Specialist Agents Module

Contains focused agents for specific domains:
- CustomerAgent: Customer communication
- OperationsAgent: Hub/logistics operations
- ResolutionAgent: Action execution
"""
from src.agent.specialists.customer_agent import create_customer_agent
from src.agent.specialists.operations_agent import create_operations_agent
from src.agent.specialists.resolution_agent import create_resolution_agent

__all__ = [
    "create_customer_agent",
    "create_operations_agent", 
    "create_resolution_agent",
]

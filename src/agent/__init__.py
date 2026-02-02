"""
Multi-Agent Logistics Resolution System

LangGraph-based multi-agent system with:
- Supervisor: LLM-driven orchestrator that routes to specialists
- CustomerAgent: Handles customer communication
- OperationsAgent: Handles hub/logistics operations  
- ResolutionAgent: Executes refunds, reschedules

Uses Postgres checkpointer for state persistence and Langfuse for observability.
"""
from src.agent.supervisor import run_supervisor

__all__ = ["run_supervisor"]

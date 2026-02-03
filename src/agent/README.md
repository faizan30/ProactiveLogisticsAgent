# Multi-Agent System

LangGraph-based multi-agent system with LLM supervisor orchestrating specialist agents.

## Architecture

```
                    SUPERVISOR (gpt-5.2)
                    • Analyzes signal
                    • Routes to specialists
                    • Evaluates results
                           │
       ┌───────────────────┼───────────────────┐
       ▼                   ▼                   ▼
  OPERATIONS         CUSTOMER          RESOLUTION
    AGENT             AGENT               AGENT
       │                  │                   │
  Researcher →      Drafter →          Policy-aware
  Analyzer          Critic              execution
       │                  │                   │
  Tools (3):        Tools (2):          Tools (4):
  • contact_hub     • send_message      • get_policy
  • check_shipment_ • get_customer_     • process_refund
    status            response          • reschedule_delivery
  • get_customer_                       • close_ticket
    stats
```

## Quick Usage

```python
from src.agent import run_supervisor

result = run_supervisor(
    order={...},
    signal_type="STUCK_AT_HUB",
    signal_reason="Package at hub for 60h"
)
# Returns: {status, resolution, actions_taken, conversation_turns}
```

```bash
curl -X POST http://localhost:9001/trigger-agent/1003
```

## Key Design Decisions

**Why LangGraph?**
- Explicit `AgentState` TypedDict (no hidden state)
- Postgres checkpointing for recovery
- Conditional routing based on LLM decisions

**Why Structured Outputs?**
- Pydantic `RoutingDecision` model prevents LLM parsing failures
- Type safety and validation at boundaries

**Why LLM Supervisor vs Hardcoded Router?**
- Handles compound signals dynamically
- Adaptive to specialist outcomes
- Observable reasoning for debugging

**Why Multi-Agent?**
- Focused prompts (no role confusion)
- Limited tools per specialist (clear boundaries)
- Easier testing and evaluation

## Configuration

```bash
AGENT_SUPERVISOR_MODEL=gpt-5.2       # LLM for supervisor
AGENT_SPECIALIST_MODEL=gpt-5.1       # LLM for specialists
AGENT_MAX_TURNS=10                   # Max conversation turns
```

## Observability

- **Langfuse:** Trace every LLM call and routing decision
- **Postgres:** Checkpoint state after each node
- **Logs:** Structured logging with order context

## Full Details

See [`documentation/Architecture.md`](../../documentation/Architecture.md) for:
- Complete design rationale
- Production considerations
- Failure modes & resilience
- Future enhancements

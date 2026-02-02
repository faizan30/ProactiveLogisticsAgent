# Multi-Agent Logistics Resolution System

A LangGraph-based multi-agent system where an LLM supervisor dynamically orchestrates specialist agents to resolve logistics issues.

## Architecture

```
                         POST /trigger-agent/{id}
                                    │
                                    ▼
                    ┌───────────────────────────────┐
                    │         SUPERVISOR            │
                    │         (gpt-5.2)             │
                    │  ━━━━━━━━━━━━━━━━━━━━━━━━━━   │
                    │  • Analyzes signal + context  │
                    │  • Decides next specialist    │
                    │  • Evaluates results          │
                    │  • Loops until FINISH         │
                    └───────────────┬───────────────┘
                                    │
           ┌────────────────────────┼────────────────────────┐
           ▼                        ▼                        ▼
┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐
│  OPERATIONS AGENT   │  │   CUSTOMER AGENT    │  │  RESOLUTION AGENT   │
│     (gpt-5.1)       │  │     (gpt-5.1)       │  │     (gpt-5.1)       │
│  ━━━━━━━━━━━━━━━━   │  │   ━━━━━━━━━━━━━━━   │  │  ━━━━━━━━━━━━━━━━   │
│  • contact_hub      │  │   • send_message    │  │  • process_refund   │
│  • check_shipment   │  │   • get_response    │  │  • reschedule       │
└─────────────────────┘  └─────────────────────┘  └─────────────────────┘
           │                        │                        │
           └────────────────────────┼────────────────────────┘
                                    ▼
                    ┌───────────────────────────────┐
                    │      Postgres Checkpointer    │
                    │      + Langfuse Tracing       │
                    └───────────────────────────────┘
```

**4 separate LLM instances** — supervisor decides WHO acts, specialists execute HOW.

---

## Quick Start

```bash
# Trigger agent for order with risk
curl -X POST http://localhost:9001/trigger-agent/1003

# Response
{
  "order_id": 1003,
  "status": "resolved",
  "signal_type": "STUCK_AT_HUB",
  "resolution": "Delivery rescheduled for tomorrow",
  "actions_taken": ["operations: Hub contacted", "customer: Offered reschedule", "resolution: Rescheduled"],
  "conversation_turns": 5
}
```

```python
from src.agent import run_supervisor

result = run_supervisor(
    order={"id": 1003, "origin_region": "North", ...},
    signal_type="STUCK_AT_HUB",
    signal_reason="Package at hub for 60h",
)
```

---

## Signal → Agent Flow

| Signal | Flow | Rationale |
|--------|------|-----------|
| `STUCK_AT_HUB` | Ops → Customer → Resolution | Hub status first, then customer contact |
| `PREDICTED_DELAY` | Customer → Resolution | Proactive outreach, then execute |
| `TICKET_RAISED` | Customer → Resolution | Empathy first, then resolution |

---

## Module Structure

```
src/agent/
├── __init__.py              # Exports run_supervisor
├── supervisor.py            # LangGraph graph + supervisor node
├── state.py                 # AgentState TypedDict
├── tools.py                 # Mocked tools (6 tools)
├── prompts.py               # System prompts (4 prompts)
└── specialists/
    ├── base.py              # create_specialist_node factory
    ├── customer_agent.py
    ├── operations_agent.py
    └── resolution_agent.py
```

---

## Configuration

Models are configurable via environment or `src/config.py`:

```bash
# .env
OPENAI_API_KEY=sk-...
AGENT_SUPERVISOR_MODEL=gpt-5.2      # Default
AGENT_SPECIALIST_MODEL=gpt-5.1      # Default
AGENT_MAX_TURNS=10

# Langfuse (optional)
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_PUBLIC_KEY=pk-lf-...
```

---

## Observability

### Langfuse Tracing

Every run creates a trace:
```
Trace: resolve_stuck_at_hub_1003
├── supervisor_think → "Need hub status first"
├── operations_agent → contact_hub → "Package ready"
├── supervisor_think → "Contact customer"
├── customer_agent → send_message, get_response → "reschedule"
├── resolution_agent → reschedule → "Done"
└── supervisor_finish → "Resolution complete"
```

### Local Logging

```
11:30:45 | [SUPERVISOR] Starting for order #1003, signal: STUCK_AT_HUB
11:30:46 | [SUPERVISOR] → OPERATIONS
11:30:47 | [OPERATIONS] Hub contacted, package ready
11:30:48 | [SUPERVISOR] → CUSTOMER
11:30:50 | [CUSTOMER] Customer chose: reschedule
11:30:51 | [SUPERVISOR] → RESOLUTION
11:30:52 | [RESOLUTION] Rescheduled for tomorrow
11:30:53 | [SUPERVISOR] ✓ Complete
```

---

## Design Decisions

### Why LangGraph?
- **Explicit state** — TypedDict vs hidden state
- **Native checkpointing** — Postgres support built-in
- **Clear control flow** — Graph edges, not implicit chains

### Why OpenAI?
- **LangGraph ecosystem** — First-class support, fewer edge cases
- **Tool calling** — Battle-tested function calling
- **Langfuse integration** — Native callback support

*Future: Benchmark Claude/Gemini for comparison*

### Why Mocked Tools?
Demo scope. Real integrations (hub APIs, payment processors) would require credentials, error handling, and add flakiness. Tools are designed to be swappable.

### Why Supervisor over Router?
A hardcoded router (`if signal == X: return Y`) can't:
- Handle compound signals
- Adapt when specialist returns unexpected info
- Demonstrate AI reasoning

---

## Future Enhancements

1. **Multi-provider testing** — Benchmark OpenAI vs Claude vs Gemini
2. **Real integrations** — Connect to actual hub APIs, payment systems
3. **HITL mode** — Human approval for high-value refunds
4. **Streaming** — Real-time agent responses
5. **Escalation** — Route to human for unresolvable cases

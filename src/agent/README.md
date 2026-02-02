# Multi-Agent Logistics Resolution System

A LangGraph-based multi-agent system where an LLM supervisor dynamically orchestrates specialist agents to resolve logistics issues.

## Architecture

```
                         POST /trigger-agent/{id}
                                    │
                                    ▼
                    ┌───────────────────────────────┐
                    │       TRUE SUPERVISOR         │
                    │         (gpt-5.2)             │
                    │  ━━━━━━━━━━━━━━━━━━━━━━━━━━   │
                    │  • LLM-driven decisions       │
                    │  • Analyzes signal + context  │
                    │  • Evaluates agent results    │
                    │  • Iterates until FINISH      │
                    └───────────────┬───────────────┘
                                    │
         ┌──────────────────────────┼──────────────────────────┐
         ▼                          ▼                          ▼
┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐
│  OPERATIONS AGENT   │  │   CUSTOMER AGENT    │  │  RESOLUTION AGENT   │
│  ═══════════════════│  │  ═══════════════════│  │  ═══════════════════│
│                     │  │                     │  │                     │
│  ┌───────────────┐  │  │  ┌───────────────┐  │  │  Tools:             │
│  │  Researcher   │  │  │  │   Drafter     │  │  │  • get_policy       │
│  └───────┬───────┘  │  │  │    Agent      │  │  │    (reads policy.md)│
│          ▼          │  │  └───────┬───────┘  │  │  • check_refund     │
│  ┌───────────────┐  │  │          ▼          │  │  • process_refund   │
│  │   Analyzer    │  │  │  ┌───────────────┐  │  │  • reschedule       │
│  │    Agent      │  │  │  │    Critic     │  │  │  • close_ticket     │
│  └───────────────┘  │  │  │    Agent      │  │  │                     │
│                     │  │  └───────────────┘  │  │                     │
│  Tools:             │  │                     │  │                     │
│  • contact_hub      │  │  Tools:             │  │                     │
│  • check_shipment   │  │  • send_message     │  │                     │
│                     │  │  • get_response     │  │                     │
└─────────────────────┘  └─────────────────────┘  └─────────────────────┘
                                    │
                    ┌───────────────────────────────┐
                    │      Postgres Checkpointer    │
                    │      + Langfuse Tracing       │
                    └───────────────────────────────┘
```

**True Multi-Agent System:**
- **Supervisor:** LLM-driven orchestrator (not a router)
- **CustomerAgent:** DrafterAgent → CriticAgent → Send (internal sub-agents)
- **OperationsAgent:** Researcher → Analyzer (contacts hub, analyzes findings)
- **ResolutionAgent:** Uses `get_policy` tool to read `data/policy.md`

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
├── tools.py                 # Tools (8 tools)
├── prompts.py               # System prompts + sub-agent prompts
├── retrieve.py              # Simple file readers (policy.md, customer_stats.json)
└── specialists/
    ├── base.py              # create_specialist_node factory
    ├── customer_agent.py    # Drafter → Critic → Sender
    ├── operations_agent.py  # Researcher → Analyzer
    └── resolution_agent.py  # Policy-aware execution
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

### Why File-Based Data (Not DB)?
Tools read from JSON/markdown files in `data/`:
- **Policy:** `data/policy.md` — ~2KB, fits in context
- **Customer stats:** `data/customer_stats.json` — precomputed from CSV
- **Route stats:** `data/route_stats.json` — precomputed from CSV

This avoids DB complexity for demo. In production, swap file reads with Postgres queries.

### Why Precomputed Stats?
Following `route_stats.json` pattern:
```bash
# Generate stats from CSV
python -m src.data_preprocessing.customer_stats_generator
python -m src.data_preprocessing.route_stats_generator
```

Tools just read the JSON — no complex logic, LLM processes the data.

### Why Binary Refund (Not Percentage)?
Refund decision is yes/no. The LLM reads policy and decides whether to refund based on context. No percentage validation logic needed.

---

## Future Enhancements

### LiteLLM Integration
- **Easy model swap** — Switch between OpenAI/Claude/Gemini without code changes
- **Model routing** — Route requests to different models based on task complexity
- **Fallback chains** — Auto-fallback to backup model on failures
- **Rate limits** — Handle rate limiting with automatic retries
- **Cost tracking** — Monitor token usage and costs per model

### Model Testing
- **Latency benchmarks** — Compare response times across providers
- **Accuracy evaluation** — Test resolution quality per model
- **Cost-performance tradeoffs** — Find optimal model for each agent role

### Other
- **Real integrations** — Connect to actual hub APIs, payment systems
- **HITL mode** — Human approval for high-value refunds
- **Streaming** — Real-time agent responses
- **Escalation routing** — Route to human for unresolvable cases

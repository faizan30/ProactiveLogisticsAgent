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
├── state.py                 # AgentState TypedDict with reducers
├── models.py                # Pydantic models for validation + structured output
├── tools.py                 # Tools (8 tools) with structured logging
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

| Alternative | Why Not | LangGraph Advantage |
|-------------|---------|---------------------|
| LangChain Agents | Hidden state, hard to debug | Explicit `AgentState` TypedDict |
| AutoGen | Complex setup, less control | Simple graph definition |
| CrewAI | Opinionated, less flexible | Full control over routing |
| Custom orchestration | Reinvent the wheel | Native checkpointing, callbacks |

**Key LangGraph features used:**
- `StateGraph` with typed nodes
- `add_messages` reducer for message history
- `operator.add` reducers for list fields (concurrent-safe)
- Postgres checkpointer for state persistence
- Conditional edges for dynamic routing

### Why Structured Output (Pydantic)?

```python
# ❌ Before: Fragile string parsing
if "next: finish" in response.lower():
    next_node = "finish"

# ✅ After: Typed, validated output
class RoutingDecision(BaseModel):
    next_specialist: Literal["operations", "customer", "resolution", "finish"]
    reasoning: str
    confidence: float

decision = llm.with_structured_output(RoutingDecision).invoke(messages)
```

**Benefits:**
- No parsing failures from LLM format drift
- Validation at boundaries (fail fast)
- IDE autocomplete and type checking
- Self-documenting schemas

### Why Supervisor over Router?

A hardcoded router (`if signal == X: return Y`) can't:
- Handle compound signals (stuck + ticket raised)
- Adapt when specialist returns unexpected info
- Demonstrate AI reasoning for reviewers

The supervisor makes **visible decisions** with reasoning, which is valuable for:
- Debugging agent behavior
- Explaining actions to stakeholders
- Training data for future improvements

### Why Multi-Agent (Not Single Agent)?

| Approach | Pros | Cons |
|----------|------|------|
| Single agent with all tools | Simple | Context pollution, role confusion |
| **Multi-agent specialists** | Focused prompts, clear responsibilities | More complex orchestration |

Each specialist has:
- **Focused system prompt** — No role confusion
- **Limited tools** — Only what it needs
- **Clear success criteria** — Easy to evaluate

### Why Mocked Tools?

Demo scope. Real integrations would require:
- API credentials and secrets management
- Error handling for network failures
- Rate limiting and retries
- Test environment setup

Tools are designed to be **swappable** — same interface, different implementation.

### Why File-Based Data (Not DB)?

| Data | File | Size | Rationale |
|------|------|------|-----------|
| Policy | `policy.md` | ~2KB | Fits in context, LLM processes |
| Customer stats | `customer_stats.json` | ~1KB | Precomputed aggregates |
| Route stats | `route_stats.json` | ~5KB | Precomputed per-route metrics |

**Why precompute?**
- Avoid complex SQL in agent flow
- Deterministic results for testing
- LLM processes the data, not code

### Why Error State in AgentState?

```python
# Error tracking fields
error: str | None           # What went wrong
error_count: int            # For retry/circuit-breaker logic
last_error_node: str | None # Which node failed
```

**Enables:**
- Graceful degradation (fallback routing after N errors)
- Debugging (which node failed?)
- Metrics (error rate per node)

### Why Timeout + Retry?

```python
llm = ChatOpenAI(timeout=30)  # Don't hang forever

@retry(stop=stop_after_attempt(3), wait=wait_exponential())
def _invoke_supervisor_llm(...):  # Retry transient failures
```

LLM APIs fail. Without these, one timeout = entire workflow failure.

---

## Future Work

### Production Readiness

| Feature | Current | Future |
|---------|---------|--------|
| **Checkpointing** | Postgres (implemented) | Add Redis for speed |
| **Observability** | Langfuse callbacks | Add Prometheus metrics |
| **Error handling** | Basic retry | Circuit breaker pattern |
| **Testing** | Unit tests | Integration tests with LLM mocks |

### Model Flexibility

**LiteLLM Integration:**
```python
# Future: Easy model swap
from litellm import completion
response = completion(
    model="gpt-4",  # or "claude-3", "gemini-pro"
    messages=messages,
    fallbacks=["claude-3-sonnet", "gpt-3.5-turbo"],
)
```

**Benefits:**
- A/B test models per agent role
- Auto-fallback on provider outages
- Cost optimization (cheaper models for simple tasks)

### Long-Term Memory

**Not implemented for demo simplicity, but designed for:**
```python
# LangGraph Store API (standard pattern)
from langgraph.store.memory import InMemoryStore

store = InMemoryStore(index={"embed": embed_fn, "dims": 1536})
store.put(namespace=("resolutions",), key="order_123", value={...})
similar = store.search(namespace, query="stuck at hub")
```

**Use cases:**
- Remember past resolutions for similar cases
- Learn customer preferences across sessions
- Build procedural memory (learned rules)

### Human-in-the-Loop

```python
# Future: Approval gates
if refund_amount > config.auto_approve_limit:
    return {"status": "pending_approval", "awaiting": "human"}
```

### Real Integrations

| Tool | Current | Production |
|------|---------|------------|
| `contact_hub` | Mocked response | Hub API call |
| `process_refund` | Mocked | Payment processor API |
| `send_message` | Mocked | Email/SMS service |

### Streaming Responses

```python
# Future: Real-time updates to UI
async for chunk in graph.astream(state):
    yield {"event": "agent_update", "data": chunk}
```

---

## Architecture Principles

1. **Fail fast** — Validate inputs at boundaries with Pydantic
2. **Explicit state** — No hidden state, everything in `AgentState`
3. **Structured outputs** — Pydantic models, not string parsing
4. **Graceful degradation** — Fallbacks when LLM fails
5. **Observable** — Structured logging, Langfuse traces
6. **Testable** — Mocked tools, deterministic state transitions

# Proactive Logistics Agent

**Celonis Garage Technical Challenge - AI-Driven Operational Automation**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-green.svg)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-purple.svg)](https://langchain-ai.github.io/langgraph/)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://www.docker.com/)

---

## Overview

A production-grade system that **proactively detects delivery delays** and **autonomously resolves logistics issues** using a multi-agent AI architecture. This system demonstrates AI-first thinking combined with engineering rigor for operational automation.

### Key Capabilities

- 🎯 **Proactive Risk Detection** — Monitor KPIs and predict delays before customers complain
- 🤖 **Autonomous AI Resolution** — LangGraph multi-agent system orchestrates specialist agents
- 📊 **Real-time KPI Monitoring** — Hub delays, transit time, deadline pressure, route risk
- 💬 **Context-Aware Decisions** — Uses customer behavior, route statistics, and company policies
- 🔍 **Full Observability** — Langfuse tracing, structured logging, Postgres checkpointing
- 🐳 **Cloud-Native** — Dockerized, Kubernetes-ready

---

## Quick Start

### Prerequisites

- Docker Desktop (with Docker Compose)
- OpenAI API key ([get one here](https://platform.openai.com/api-keys))

### 1. Clone & Configure

```bash
# Clone repository
git clone https://github.com/faizan30/ProactiveLogisticsAgent
cd ProactiveLogisticsAgent

# Configure environment
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

### 2. Start Services

```bash
# Start PostgreSQL + API
docker-compose up -d

# View logs
docker-compose logs -f web

# Wait for "API ready at http://localhost:9001"
```

### 3. Run Demo Workflow

```bash
# Seed 4 demo orders
curl -X POST http://localhost:9001/bootstrap

# View orders
curl http://localhost:9001/orders

# Calculate KPIs for order 1002
curl http://localhost:9001/kpis/1002

# Detect risk signal
curl -X POST http://localhost:9001/detect-deviation/1002

# Trigger AI agent resolution
curl -X POST http://localhost:9001/trigger-agent/1002

# View conversation log
curl http://localhost:9001/view-response/1002
```

### 4. Explore API

Open http://localhost:9001/docs for interactive Swagger UI.

---

## Architecture

### System Design

```
┌─────────────────────────────────────────────────────────────┐
│  CLIENT LAYER: REST API, Streamlit Dashboard, CLI Tools    │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│  APPLICATION LAYER: FastAPI (Port 9001)                     │
│    ├─ Storage Manager  (PostgreSQL CRUD)                    │
│    ├─ Risk Engine      (KPI Calculation + Detection)        │
│    └─ Multi-Agent AI   (LangGraph Supervisor)               │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│  DATA LAYER: PostgreSQL + OpenAI API + Preprocessed Stats   │
└─────────────────────────────────────────────────────────────┘
```

**Detailed diagrams:** See [`documentation/Architecture.md`](documentation/Architecture.md)

### Multi-Agent System

```
          SUPERVISOR (gpt-5.2)
                 │
    ┌────────────┼────────────┐
    │            │            │
OPERATIONS   CUSTOMER   RESOLUTION
  AGENT       AGENT        AGENT
    │            │            │
 contact_hub  send_message   get_policy
check_shipment_ get_customer_ process_refund
 status          response    reschedule_delivery
get_customer_                close_ticket
 stats
```

**Key Features:**
- **LLM Supervisor:** True reasoning-based routing (not hardcoded)
- **Specialist Agents:** Focused responsibilities with limited tools
- **Structured Outputs:** Pydantic models prevent LLM parsing failures
- **State Persistence:** Postgres checkpointing for recovery
- **Observable:** Langfuse traces every LLM decision

---

## Components

### 1. Data Preprocessing (`src/data_preprocessing/`, `data/`)

**Purpose:** Enrich raw Kaggle dataset with synthetic logistics data.

- **Enrichment:** Gemini Pro LLM adds 16 columns (timestamps, regions, status)
- **Route Stats:** `route_stats.json` — 75 routes with failure rates, transit times
- **Customer Stats:** `customer_stats.json` — Behavior patterns by rating

**Generate stats:**
```bash
python -m src.data_preprocessing.route_stats_generator --update
python -m src.data_preprocessing.customer_stats_generator
```

**See:** [`data/README.md`](data/README.md), [`src/data_preprocessing/README.md`](src/data_preprocessing/README.md)

---

### 2. Risk Engine (`src/risk_detection/`)

**Purpose:** KPI-based threshold monitoring and risk signal prioritization.

**5 KPIs:**
- `HubHoursKPI` — Hours at destination hub (threshold: 24h)
- `TransitHoursKPI` — Hours in transit with dynamic route thresholds
- `HoursRemainingKPI` — Time until promised date (overdue detection)
- `RouteRiskKPI` — Route failure rate (high-risk route detection)
- `PredictedDelayKPI` — Composite signal combining multiple breaches

**Signal Priority:**
1. **TICKET_RAISED** (Critical) — Customer escalated
2. **STUCK_AT_HUB** (High) — Package idle at hub
3. **PREDICTED_DELAY** (High) — Proactive intervention
4. **ON_TRACK** (Low) — No action needed

**Example:**
```python
from src.risk_detection import RiskEngine

engine = RiskEngine()
signal = engine.detect(order)
# Returns: RiskSignal(type="PREDICTED_DELAY", severity="HIGH", ...)
```

---

### 3. Multi-Agent System (`src/agent/`)

**Purpose:** LLM-driven autonomous resolution orchestration.

**Architecture:** LangGraph StateGraph with typed state management.

**Key Files:**
- `supervisor.py` — LLM supervisor with structured routing decisions
- `specialists/` — OperationsAgent, CustomerAgent, ResolutionAgent
- `state.py` — AgentState TypedDict with reducers
- `tools.py` — 8 mocked tools (hub contact, refunds, messaging)
- `prompts.py` — System prompts for supervisor and specialists

**Usage:**
```python
from src.agent import run_supervisor

result = run_supervisor(
    order=order_dict,
    signal_type="STUCK_AT_HUB",
    signal_reason="Package at hub for 60h",
    use_checkpointer=True,
)
# Returns: {status, resolution, actions_taken, conversation_turns}
```

**See:** [`src/agent/README.md`](src/agent/README.md)

---

### 4. Storage Manager (`src/storage_manager/`)

**Purpose:** Data access layer for orders and conversation history.

**Tables:**
- `orders` — Business data (timestamps, regions, status, ticket flag)
- `conversations` — Resolution sessions 
- `conversation_turns` — Turn-by-turn audit log

**PostgresManager API:**
```python
from src.storage_manager import PostgresManager

db = PostgresManager(connection_string)
order = db.get_order(1002)
db.create_conversation(order_id=1002, signal_type="PREDICTED_DELAY")
db.add_turn(conv_id, role="agent", message="...", action="refund")
```

---

### 5. API Layer (`src/api/main.py`)

**FastAPI REST API** with 9 endpoints:

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/` | Health check |
| POST | `/bootstrap` | Seed 4 demo orders |
| GET | `/orders` | List all orders |
| GET | `/orders?status=at_hub` | Filter by status |
| GET | `/orders/{id}` | Get single order |
| GET | `/kpis/{id}` | Calculate KPIs |
| POST | `/detect-deviation/{id}` | Detect risk signal |
| POST | `/trigger-agent/{id}` | Run AI agent |
| GET | `/view-response/{id}` | View conversation |

**Interactive docs:** http://localhost:9001/docs

---

## Demo Scenarios

The bootstrap endpoint seeds 4 orders representing common scenarios:

| Order | Scenario | Signal | Agent Flow |
|-------|----------|--------|------------|
| **1001** | Happy Path | ON_TRACK | No intervention needed |
| **1002** | Predicted Delay | PREDICTED_DELAY | Customer → Refund |
| **1003** | Stuck at Hub | STUCK_AT_HUB | Operations → Customer → Reschedule |
| **1004** | Ticket Raised | TICKET_RAISED | Customer → Refund |

**Run all scenarios:**
```bash
# Start from a clean slate
docker-compose down -v && docker-compose up -d

# Seed data
curl -X POST http://localhost:9001/bootstrap

# Test each scenario
for order_id in 1001 1002 1003 1004; do
  echo "=== Testing Order $order_id ==="
  curl -X POST http://localhost:9001/detect-deviation/$order_id
  curl -X POST http://localhost:9001/trigger-agent/$order_id
  echo ""
done
```

---

## Configuration

### Environment Variables

```bash
# Required
OPENAI_API_KEY=sk-...

# Database (defaults for docker-compose)
POSTGRES_USER=celonis
POSTGRES_PASSWORD=garage
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=logistics

# Agent Config (optional)
AGENT_SUPERVISOR_MODEL=gpt-5.2       # Default
AGENT_SPECIALIST_MODEL=gpt-5.1       # Default
AGENT_MAX_TURNS=10                   # Max conversation turns


# Observability (optional)
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com
```

### KPI Thresholds

Edit `src/config.py`:

```python
THRESHOLDS = {
    "hub_hours": 24,                    # Max hours at hub
    "transit_buffer_hours": 24,         # Buffer over route avg
    "deadline_pressure_hours": 48,      # Hours before deadline concern
    "route_failure_rate": 0.5,          # High-risk route threshold
    "default_transit_hours": 168,       # Fallback for unknown routes
}
```

---

## Development

### Local Setup (without Docker)

```bash
# 1. Create virtual environment
python3.11 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start PostgreSQL (separate terminal)
docker run -d \
  --name postgres-dev \
  -e POSTGRES_USER=celonis \
  -e POSTGRES_PASSWORD=garage \
  -e POSTGRES_DB=logistics \
  -p 5432:5432 \
  postgres:15-alpine

# 4. Configure .env
cp .env.example .env
# Add OPENAI_API_KEY

# 5. Run API
uvicorn src.api.main:app --reload --port 9001

# 6. Run tests
pytest tests/ -v
```

### Project Structure

```
ProactiveLogisticsAgent/
├── data/                                    # Datasets and precomputed stats
│   ├── Celonis_Garage_Enriched_Data_Final.csv  # LLM-enriched dataset (28 cols)
│   ├── Original_data.csv                        # Kaggle source (12 cols)
│   ├── route_stats.json                         # 75 route profiles
│   ├── customer_stats.json                      # Behavior patterns
│   ├── policy.md                                # Refund/reschedule policies
│   └── README.md                                # Data documentation
├── src/
│   ├── agent/                               # Multi-agent system (LangGraph)
│   │   ├── specialists/                     # Specialist agent implementations
│   │   │   ├── operations.py
│   │   │   ├── customer.py
│   │   │   └── resolution.py
│   │   ├── supervisor.py                    # LLM-based routing supervisor
│   │   ├── state.py                         # AgentState TypedDict
│   │   ├── models.py                        # Pydantic models (RoutingDecision)
│   │   ├── prompts.py                       # Agent system prompts
│   │   ├── tools.py                         # Tool definitions & collections
│   │   ├── retrieve.py                      # Context retrieval helpers
│   │   └── __init__.py
│   ├── api/                                 # FastAPI REST interface
│   │   ├── main.py                          # Endpoints & startup logic
│   │   └── __init__.py
│   ├── contracts/                           # Shared Pydantic models
│   │   ├── models.py                        # API request/response models
│   │   └── __init__.py
│   ├── data_preprocessing/                  # Offline data pipeline
│   │   ├── route_stats_generator.py         # Generate route statistics
│   │   ├── customer_stats_generator.py      # Generate customer patterns
│   │   ├── enrichment_prompts.md            # LLM enrichment prompts
│   │   ├── validate_enrichment.ipynb        # Data quality validation
│   │   └── __init__.py
│   ├── risk_detection/                      # KPI calculation & detection
│   │   ├── kpis.py                          # 5 KPI implementations
│   │   ├── risk_engine.py                   # Signal detection & priority
│   │   ├── models.py                        # KPI result models
│   │   └── __init__.py
│   ├── storage_manager/                     # Database abstraction layer
│   │   ├── postgres_manager.py              # PostgreSQL CRUD operations
│   │   ├── db_models.py                     # SQLAlchemy models
│   │   └── __init__.py
│   ├── bootstrap.py                         # Demo data seeder (4 scenarios)
│   └── config.py                            # Configuration & thresholds
├── tests/
│   ├── unit/                                # Component-level tests
│   │   ├── test_kpis.py
│   │   ├── test_agent_graph.py
│   │   └── test_agent_state.py
│   ├── integration/                         # End-to-end workflow tests
│   │   └── test_scenarios.py
│   ├── api/                                 # API endpoint tests
│   │   └── test_endpoints.py
│   └── conftest.py                          # Pytest fixtures
├── scripts/
│   ├── run_demo_scenarios.py                # Demo automation script
│   └── dashboard.py                         # Streamlit monitoring UI
├── documentation/
│   ├── Architecture.md                      # Staff-level architecture doc
├── docker-compose.yml                       # Docker services (web + db)
├── Dockerfile                               # FastAPI container
├── requirements.txt                         # Python dependencies
├── .env.example                             # Environment template
└── README.md                                # This file
```

---

## Testing

### Unit Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/unit/test_agent_graph.py -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html
```

### Integration Tests

```bash
# Test full workflow (requires running services)
pytest tests/integration/test_scenarios.py -v
```

### Manual API Testing

```bash
# Use scripts/run_demo_scenarios.py
python scripts/run_demo_scenarios.py

# Or use Postman collection (documentation/postman_collection.json)
```

---

## Observability

### Langfuse Tracing

If configured, every agent run creates a trace in Langfuse:

```
Trace: resolve_predicted_delay_1002
├── supervisor_think → "Need to contact customer"
├── customer_agent → send_message, get_customer_response → "refund"
├── supervisor_think → "Process refund"
├── resolution_agent → process_refund → "Done"
└── supervisor_finish → "Resolution complete"
```

**View traces:** https://cloud.langfuse.com (or your self-hosted instance)

### Structured Logging

All components use structured logging:

```
11:30:45 | [SUPERVISOR] Starting for order #1002, signal: PREDICTED_DELAY
11:30:46 | [SUPERVISOR] → CUSTOMER | reasoning: "Proactive customer contact"
11:30:48 | [CUSTOMER] Customer chose: refund
11:30:49 | [SUPERVISOR] → RESOLUTION
11:30:51 | [RESOLUTION] Processed 15% refund ($30.00)
11:30:52 | [SUPERVISOR] ✓ Complete
```

### Database Checkpoints

Agent state is saved in PostgreSQL after each node execution:

```sql
-- View checkpoints for debugging
SELECT * FROM checkpoints WHERE thread_id = 'order_1002';

-- Replay conversation
SELECT * FROM conversations WHERE order_id = 1002;
SELECT * FROM conversation_turns WHERE conversation_id = ...;
```


---

## Design Decisions

### LangGraph vs LangChain

**LangGraph advantages:**
- ✅ Explicit `AgentState` TypedDict (no hidden state)
- ✅ Built-in Postgres checkpointing
- ✅ Conditional edges for dynamic routing
- ✅ Observable graph execution

**See:** [`documentation/Architecture.md#design-decisions`](documentation/Architecture.md#design-decisions)

### Pydantic Structured Outputs

**Problem:** String parsing from LLMs fails 20%+ of the time.

**Solution:** Use `.with_structured_output(RoutingDecision)` for validated responses.

**Impact:** Parsing failures reduced to <1%.

### File-Based Context (JSON/MD)

- **LLM-friendly:** Direct text/JSON consumption
- **Precomputed:** Stats generated once at startup
- **Small Context:** Small policy document does not need RAG


### Full Design Rationale

See [`documentation/Architecture.md`](documentation/Architecture.md) for:
- Tech stack justification (FastAPI, PostgreSQL, OpenAI)
- Failure modes and resilience strategies
- Production considerations and scale
- Future roadmap (ML models, real integrations, multi-tenant)

---

## Troubleshooting

### "Missing OPENAI_API_KEY"

```bash
# Add to .env file
echo "OPENAI_API_KEY=sk-..." >> .env

# Restart services
docker-compose restart web
```

### "Database connection failed"

```bash
# Check PostgreSQL is running
docker-compose ps db

# View database logs
docker-compose logs db

# Reset database
docker-compose down -v && docker-compose up -d
```

### "Agent execution timeout"

Increase timeout in `src/config.py`:

```python
AGENT_CONFIG = {
    "max_turns": 15,  # Increase from default 10
}
```

### "LLM parsing errors"

This is rare with structured outputs. If it occurs:
1. Check LLM model version (use gpt-5.2+)
2. Review Langfuse traces for malformed responses
3. Update Pydantic models to be more permissive

---

## Documentation

- **[Architecture.md](documentation/Architecture.md)** — Staff-level system design with diagrams, component roles, tech stack justification, failure modes, production considerations
- **[Agent README](src/agent/README.md)** — Multi-agent system details, LangGraph patterns, design decisions
- **[Data README](data/README.md)** — Dataset details, enrichment process, stats generation
- **[API Documentation](http://localhost:9001/docs)** — Interactive Swagger UI (when running)

---

## Acknowledgments

**Challenge:** Celonis Garage Technical Challenge  
**Framework:** LangGraph by LangChain  
**Dataset:** Kaggle Customer Analytics Dataset (enriched)  
**LLM:** OpenAI GPT-5.x

---

## Contact

**Project Maintainer:** [Faizan Khan]  
**Email:** [fskofficial@gmail.com]  
**Repository:** https://github.com/faizan30/ProactiveLogisticsAgent

---

**Last Updated:** February 2026  
**Version:** 3.0.0

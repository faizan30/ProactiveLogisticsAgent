# Proactive Logistics Agent - Architecture Documentation

**Project:** Celonis Garage Technical Challenge  
**Version:** 3.0  
**Last Updated:** February 2026

---

## Table of Contents

1. [System Overview & Goals](#system-overview--goals)
2. [Architecture Diagrams](#architecture-diagrams)
3. [Component Roles](#component-roles)
4. [Tech Stack Justification](#tech-stack-justification)
5. [Deployment Setup](#deployment-setup)
6. [Assumptions & Limitations](#assumptions--limitations)
7. [Future Ideas](#future-ideas)

---

## System Overview & Goals

### Business Problem

Reactive customer service is a cost center that erodes brand value. When customers escalate delivery issues through support tickets, satisfaction damage is already done. This system inverts the paradigm: **detect operational deviations before customer impact and autonomously resolve them using AI agents**.

**Operational Model:**
- **Traditional:** Customer complaint → Ticket → Manual triage → Resolution (48-72hr)
- **This System:** KPI breach → Risk signal → AI agent workflow → Proactive resolution (< 5min)

### System Goals

This architecture demonstrates four core capabilities aligned with Celonis Garage innovation principles:

**1. Process KPI Monitoring**
- Real-time calculation of logistics health indicators (hub dwell time, transit velocity, SLA pressure)
- Dynamic thresholds using route-specific historical statistics
- Multi-signal composite risk scoring with severity prioritization

**2. Predictive Deviation Detection**  
- Identify at-risk shipments before customer-visible failures
- Route-aware anomaly detection (e.g., 2-day flight delayed to 70hr vs. 8-day road delayed to 10 days)
- Proactive triggering on predicted delays, not just post-facto incidents

**3. Autonomous AI-Driven Resolution**
- LLM-based supervisor with dynamic routing (not rule-based state machines)
- Multi-specialist agent system (Operations, Customer, Resolution domains)
- Context-aware decision making using company policy, customer history, and route analytics
- Stateful conversation management with Postgres-backed checkpointing

**4. Production-Rigor**
- Cloud-native architecture with horizontal scalability
- Type-safe contracts (Pydantic structured outputs, TypedDict state)
- Observability & Evals (Langfuse traces, structured logging, LLM-as-a-judge Evals)
- Failure resilience (exponential backoff, circuit breakers, graceful degradation)

### Target Outcomes (Target For Production System)

| Metric | Target | Measurement |
|--------|--------|-------------|
| Detection Recall | >90% | At-risk orders identified before customer contact |
| Autonomous Resolution | >80% | Issues resolved without human escalation |
| Resolution Latency | <60s p95 | End-to-end agent execution time |
| System Availability | 99.9% | With LLM fallback and retry logic |
| Cost per Resolution | <$0.05 | LLM API + infrastructure amortized |


### Explicit Non-Goals

- **Real external integrations:** Payment APIs, carrier tracking, SMS gateways are mocked (swappable interfaces for production)
- **Streaming pipelines:** API based ingestion sufficient for demo; Kafka integration is future work  
- **Multi-tenancy:** Single-company deployment; tenant isolation requires DB sharding
- **Predictive ML models:** Heuristic-based delay prediction; XGBoost/neural net training is out of scope

---

## Architecture Diagrams

### 1. High-Level System Architecture

```
┌───────────────────────────────────────────────────────────────┐
│                      CLIENT INTERFACES                        │
│  REST API Clients  │  Streamlit Dashboard  │  CLI Scripts    │
└───────────────────────────┬───────────────────────────────────┘
                            │ HTTP/JSON
┌───────────────────────────▼───────────────────────────────────┐
│                   FastAPI Application Layer                   │
│  ┌──────────────────────────────────────────────────────┐    │
│  │  Endpoints: /bootstrap, /detect-deviation,           │    │
│  │             /trigger-agent, /kpis, /view-response    │    │
│  └────────────────────┬─────────────────┬───────────────┘    │
│                       │                 │                     │
│  ┌────────────────────▼──┐   ┌─────────▼─────────────────┐  │
│  │   Risk Engine        │   │  Agent Supervisor         │  │
│  │  - KPI calculation   │   │  - LangGraph StateGraph   │  │
│  │  - Signal detection  │   │  - Multi-specialist routing│  │
│  │  - Route analytics   │   │  - Postgres checkpointing │  │
│  └──────────┬───────────┘   └──────────┬────────────────┘  │
└─────────────┼──────────────────────────┼────────────────────┘
              │                          │
┌─────────────▼──────────────────────────▼────────────────────┐
│                  Data & External Services                    │
│  ┌──────────────┐  ┌────────────────┐  ┌────────────────┐  │
│  │ PostgreSQL   │  │ File Context   │  │  OpenAI API    │  │
│  │ - Orders     │  │ - route_stats  │  │  - gpt-5.2     │  │
│  │ - Convos     │  │ - cust_stats   │  │  - gpt-5.1     │  │
│  │ - Checkpoints│  │ - policy.md    │  │  - Structured  │  │
│  └──────────────┘  └────────────────┘  │    outputs     │  │
│                                        └────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

*Stateless API pods with shared Postgres for horizontal scalability.*

---

### 2. Multi-Agent AI Workflow

```
                POST /trigger-agent/{order_id}
                           │
              ┌────────────▼────────────┐
              │  SUPERVISOR (gpt-5.2)  │  
              │  - Analyzes risk signal │
              │  - Routes to specialist │
              │  - Evaluates progress   │
              └────────┬────────────────┘
                       │ Dynamic routing (LLM decision, not rules)
       ┌───────────────┼───────────────┐
       │               │               │
  ┌────▼─────┐  ┌─────▼──────┐  ┌────▼──────┐
  │Operations│  │  Customer  │  │Resolution │
  │  Agent   │  │   Agent    │  │   Agent   │
  ├──────────┤  ├────────────┤  ├───────────┤
  │Research  │  │Draft msg   │  │Get policy │
  │hub status│  │Refine tone │  │Process    │
  │Get route │  │Send & get  │  │refund     │
  │analytics │  │response    │  │Reschedule │
  └────┬─────┘  └─────┬──────┘  └────┬──────┘
       │              │              │
       └──────────────┼──────────────┘
                      │
         ┌────────────▼────────────┐
         │  LangGraph StateGraph  │
         │  - TypedDict state     │
         │  - Postgres checkpoint │
         │  - Langfuse tracing    │
         └────────────────────────┘
```

*LLM supervisor dynamically routes to specialists; Postgres checkpoints state after each node.*

---

### 3. Data & Execution Flow

**Offline Data Preparation:**
```
Kaggle CSV (12 cols) → Gemini Pro enrichment → Enhanced CSV (28 cols)
                                                      │
                                    ┌─────────────────┴─────────────────┐
                                    ▼                                   ▼
                            route_stats.json                   customer_stats.json
                            (75 route profiles)                (5 rating tiers)
```

**Runtime Workflow:**
```
POST /bootstrap → GET /kpis/{id} → POST /detect-deviation/{id} → POST /trigger-agent/{id} → GET /view-response/{id}
```

*CSV seed → KPI calculation → Risk signal → Agent resolution → Audit trail.*

---

## Component Roles

### 1. Data Pipeline

**Location:** `data/`, `src/bootstrap.py`

**Responsibility:** Transform Kaggle e-commerce dataset (12 cols) into logistics monitoring dataset (28 cols) via LLM enrichment.

**Key Outputs:**
- **Enriched CSV:** +16 columns (timestamps, regions, status, payment)
- **route_stats.json:** 75 route profiles with avg transit times and failure rates
- **customer_stats.json:** 5 rating tiers with behavior patterns

---

### 2. Risk Detection Engine

**Location:** `src/risk_detection/`

**Responsibility:** Calculate 5 KPIs and generate prioritized risk signals.

**KPIs:** HubHours (24h threshold), TransitHours (route-aware), HoursRemaining (SLA), RouteRisk (50% failure rate), PredictedDelay (composite)

**Signal Priority:** `TICKET_RAISED > STUCK_AT_HUB > PREDICTED_DELAY > ON_TRACK`

---

### 3. Agent System

**Location:** `src/agent/`

**Responsibility:** LLM-driven issue resolution via supervisor + 3 specialist agents.

**Architecture:** LangGraph StateGraph with Postgres checkpointing and Langfuse tracing.

| Component | Model | Role |
|-----------|-------|------|
| **Supervisor** | gpt-5.2 | Analyze signal, route to specialists, evaluate progress |
| **Operations** | gpt-5.1 | Investigate hub/shipment status |
| **Customer** | gpt-5.1 | Draft empathetic communication |
| **Resolution** | gpt-5.1 | Execute refunds/reschedules per policy |

---

### 4. Storage Layer

**Location:** `src/storage_manager/`

**Responsibility:** Persist orders, conversations, and agent checkpoints.

**Schema:** `orders` (business data) → `conversations` (1:N) → `conversation_turns` (1:N) + `checkpoints` (LangGraph state)

---

### 5. API Layer

**Location:** `src/api/main.py`

**Responsibility:** REST interface for KPI calculation, deviation detection, and agent triggering.

**Endpoints:** `/bootstrap`, `/kpis/{id}`, `/detect-deviation/{id}`, `/trigger-agent/{id}`, `/view-response/{id}`

---

### Failure Modes

| Scope | Failure | Detection | Mitigation |
|-------|---------|-----------|------------|
| **Data Pipeline** | Corrupt CSV or missing stats | Startup validation | Schema validation; fail-fast with clear error |
| **Risk Detection** | Unknown route lookup | Lookup failure | Default thresholds (48h transit, 30% risk); log warning |
| **Agent System** | LLM timeout, infinite loop | Turn counter, timeout | 30s timeout, max 10 turns, >3 same-specialist → escalation |
| **Storage** | DB connection loss, pool exhaustion | Connection errors | Pooling (20+10), pre-ping, circuit breaker (5 failures) |
| **API** | Request overload, upstream timeout | Latency spike | Rate limit (100 req/min), 120s timeout, graceful errors |
| **System** | Data inconsistency | State validation failure | Atomic transactions, fallback to fresh state |
| **System** | Service degradation (LLM latency) | p95 >60s | Timeout + fallback model, cached responses |

---

## Tech Stack Justification

All technology choices prioritize **AI-first workflow support**, **production reliability**, and **operational observability**.

| Component | Choice | Alternatives Considered | Decision Rationale |
|-----------|--------|------------------------|--------------------|
| **Web Framework** | FastAPI (ASGI) | Flask (WSGI), Django | Async-native for concurrent LLM calls; Pydantic validation eliminates boilerplate; auto-generated OpenAPI docs; 3x faster than Flask |
| **Agent Framework** | LangGraph | LangChain Agents, AutoGen, CrewAI | Explicit TypedDict state (no hidden state); native Postgres checkpointing; conditional edges for dynamic routing; LangChain ecosystem compatibility |
| **Database** | PostgreSQL | MongoDB, Redis | ACID transactions required for refunds; native LangGraph checkpointer; JSON columns for flexibility; mature replication |
| **LLM Provider** | OpenAI (gpt-5.2 supervisor, gpt-5.1 specialists) | Claude, Gemini, Llama | Structured outputs with Pydantic schema enforcement; native function calling; 99.9% SLA; <500ms p50 latency; cost optimization via model tiering |
| **Observability** | Langfuse | LangSmith, W&B | Open-source/self-hostable; LLM-specific traces (prompts, tokens, latency); cost tracking; trace hierarchy visualization |

**Key Architectural Trade-offs:**

1. **LLM supervisor vs. rule-based router:** additional latency +10s, but handles compound signals and provides explainable reasoning
2. **File-based context vs. RAG for policy docs:** Simpler LLM integration, small context size ; move to DB when policy size grows.
3. **Mocked tools vs. real APIs:** Demo scope; swappable interface design enables production integration without refactoring

---

## Deployment Setup

### Local Development

```bash
git clone <repo_url> && cd ProactiveLogisticsAgent
cp .env.example .env  # Add OPENAI_API_KEY
docker-compose up -d
curl -X POST http://localhost:9001/bootstrap
```

**Services:** FastAPI (:9001), PostgreSQL (:5432)  
**Prerequisites:** Docker Desktop, OpenAI API key, Langfuse(recommended but not mandatory)

### Production Path

**Target Architecture:** Kubernetes (EKS/GKE) + Managed PostgreSQL (RDS/Cloud SQL) + Langfuse + LiteLLM

**Key Requirements:**
- Stateless API pods with HPA (CPU 70%)
- Connection pooling (PgBouncer) for DB scaling
- Secrets management (AWS/GCP Secret Manager)
- Versioned prompt changes and Experiment Tracking
- Development Evals and Online Evals(Sampled)

*See Future Ideas for detailed scaling and cost optimization strategies.*

---

## Assumptions & Limitations

**Scoping Decisions:**

| Category | Assumption/Limitation | Rationale | Production Path |
|----------|----------------------|-----------|------------------|
| **Geography** | Single region, English only | Simplified demo scope | Multi-region deployment with i18n support |
| **Data Pipeline** | CSV batch processing | No streaming infrastructure needed | Kafka/Kinesis for real-time ingestion |
| **Prediction Model** | Heuristic-based delay detection | No ML training required | XGBoost model trained on historical delays |
| **Human Oversight** | No approval gates for refunds | Autonomous demo workflow | Human in the loop for specific conditions |
| **Multi-Tenancy** | Single company deployment | Simplified data model | DB sharding, per-tenant policies |
| **Agent Memory** | Stateless across sessions | No vector store required | Longterm memory with LangGraph Store API |
| **External APIs** | Mocked (Twilio, Stripe, FedEx) | Demo reproducibility | Real integrations with retry/fallback |
| **Policy Management** | Hardcoded `policy.md` | Single file simplicity | Retrieval from VectorDb |

### Simulation Conditions

| Element | Simulated Behavior | Rationale |
|---------|-------------------|-----------|
| **Dataset** | LLM-enriched Kaggle e-commerce data (+16 cols) | No production logistics data available |
| **Timestamps** | Synthetic ship/delivery dates relative to order | Demonstrate temporal KPI calculations |
| **Route Stats** | 75 generated route profiles with transit times | Enable route-aware delay detection |
| **Customer Stats** | 5 rating tiers with behavior patterns | Support customer-aware communication |
| **KPI Calculations** | Hour-based (not day-based) for demo visibility | Show granular threshold behavior |
| **Midnight Edge Case** | Timestamps normalized to avoid day-boundary issues | Consistent KPI behavior across time zones |
| **External APIs** | Mocked Twilio, Stripe, FedEx responses | Demo reproducibility without API keys |
| **Agent Tools** | Simulated refunds, reschedules, notifications | Safe execution without side effects |

---

## Future Ideas

### Evolution Roadmap

| Initiative | Technical Approach | Business Impact |
|-----------|-------------------|------------------|
| Real API integrations | Stripe, Twilio, FedEx/UPS APIs | Production-ready actions |
| Streaming ingestion | Kafka consumer, async triggering | Sub-minute detection |
| Human-in-loop | Approval queue for high-value refunds | Risk mitigation |
| ML delay prediction | XGBoost on historical + weather data | +15-20% recall |
| Agent memory | LangGraph Store API + embeddings | Context-aware decisions |
| Multi-tenant | Per-company schemas, S3 policies | SaaS readiness |
| Event-driven | Proactive triggers, scheduled checks | Pre-emptive intervention |
| Feedback loop | Outcome tracking, model retraining | Continuous improvement |
| Geographic expansion | Multi-region, i18n prompts | Global support |


---

## Summary

This architecture delivers **proactive logistics automation** through AI-driven KPI monitoring and autonomous resolution:

- ✅ **5 KPIs** with dynamic, route-aware thresholds
- ✅ **Multi-agent system** (LLM supervisor + 3 specialists) with Postgres-backed state
- ✅ **Cloud-native design** with documented failure modes and mitigations
- ✅ **Extensible architecture** for additional KPIs, agents, and integrations

---

*Celonis Garage Technical Challenge*

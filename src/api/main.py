"""
Celonis Garage - Proactive Logistics Agent API

Simplified API for the demo flow:
  1. POST /bootstrap           - Seed demo data
  2. GET  /orders/{id}         - View order details
  3. GET  /kpis/{id}           - Calculate KPIs
  4. POST /detect-deviation/{id} - Detect risk signal
  5. POST /trigger-agent/{id}  - AI agent resolves issue
  6. GET  /view-response/{id}  - View conversation
"""
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path as FilePath
from typing import Optional

from fastapi import FastAPI, HTTPException, Path

from src.config import get_db_connection_string
from src.storage_manager.postgres_manager import PostgresManager
from src.risk_detection.risk_engine import RiskEngine
from src.bootstrap import bootstrap, SCENARIOS


# ==================== STATS GENERATION ====================

DATA_DIR = FilePath(__file__).resolve().parents[2] / "data"
ROUTE_STATS_FILE = DATA_DIR / "route_stats.json"
CUSTOMER_STATS_FILE = DATA_DIR / "customer_stats.json"
ENRICHED_CSV = DATA_DIR / "Celonis_Garage_Enriched_Data_Final.csv"


def ensure_stats_exist():
    """Generate stats files at startup if missing."""
    from src.data_preprocessing.route_stats_generator import generate_route_stats
    from src.data_preprocessing.customer_stats_generator import generate_customer_stats
    import json
    
    generated = []
    
    # Route stats
    if not ROUTE_STATS_FILE.exists():
        if ENRICHED_CSV.exists():
            stats = generate_route_stats(ENRICHED_CSV)
            with ROUTE_STATS_FILE.open("w") as f:
                json.dump(stats, f, indent=2, sort_keys=True)
            generated.append(f"route_stats.json ({len(stats)} routes)")
        else:
            print(f"⚠️  Cannot generate route_stats: {ENRICHED_CSV} not found")
    
    # Customer stats
    if not CUSTOMER_STATS_FILE.exists():
        if ENRICHED_CSV.exists():
            stats = generate_customer_stats(ENRICHED_CSV)
            with CUSTOMER_STATS_FILE.open("w") as f:
                json.dump(stats, f, indent=2, sort_keys=True)
            generated.append(f"customer_stats.json ({len(stats)} ratings)")
        else:
            print(f"⚠️  Cannot generate customer_stats: {ENRICHED_CSV} not found")
    
    return generated


# ==================== APPLICATION STATE ====================

class AppState:
    db: PostgresManager = None
    risk_engine: RiskEngine = None

app_state = AppState()


# ==================== LIFESPAN ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize DB, RiskEngine, and validate agent on startup."""
    print("🚀 Starting Celonis Garage API...")
    
    # 1. Ensure stats files exist (generate if missing)
    generated = ensure_stats_exist()
    if generated:
        for g in generated:
            print(f"✓ Generated {g}")
    
    # 2. Connect to database
    conn_string = get_db_connection_string()
    app_state.db = PostgresManager(conn_string)
    print("✓ Database connected")
    
    # 3. Initialize RiskEngine (loads route_stats)
    app_state.risk_engine = RiskEngine()
    print(f"✓ RiskEngine ready ({len(app_state.risk_engine.route_stats)} routes)")
    
    # 4. Validate agent system imports
    try:
        from src.agent import run_supervisor
        from src.agent.retrieve import get_customer_stats
        customer_stats = get_customer_stats()
        print(f"✓ Agent system ready ({len(customer_stats)} customer segments)")
    except ImportError as e:
        print(f"⚠️  Agent system unavailable: {e}")
    
    print("=" * 40)
    print("API ready at http://localhost:9001")
    print("=" * 40)
    
    yield
    
    print("👋 Shutting down API...")


app = FastAPI(
    title="Celonis Garage Logistics Agent",
    description="Proactive risk detection and resolution for e-commerce logistics",
    version="3.0.0",
    lifespan=lifespan,
)


# ==================== ENDPOINTS ====================

@app.get("/", tags=["health"])
def health():
    """Health check."""
    return {"status": "online", "version": "3.0.0"}


@app.post("/bootstrap", tags=["demo"])
def bootstrap_endpoint():
    """Step 1: Seed 4 demo orders."""
    result = bootstrap(app_state.db)
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["message"])
    return result


@app.get("/orders", tags=["demo"])
def get_orders(status: str = None):
    """Query orders by status.
    
    Status options:
    - pending: Not yet delivered
    - in_transit: Shipped but not at hub  
    - at_hub: At hub but not delivered
    - delivered: Already delivered
    
    If no status provided, returns all orders.
    """
    if status:
        orders = app_state.db.get_orders_by_status(status)
    else:
        orders = app_state.db.get_all_orders()
    
    return {
        "status_filter": status,
        "count": len(orders),
        "orders": orders,
    }


@app.get("/orders/{order_id}", tags=["demo"])
def get_order(order_id: int = Path(ge=1)):
    """Step 2: Get order details."""
    order = app_state.db.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail=f"Order {order_id} not found")
    
    # Add scenario info if it's a demo order
    if order_id in SCENARIOS:
        order["scenario"] = SCENARIOS[order_id]
    
    return order


@app.get("/kpis/{order_id}", tags=["demo"])
def get_kpis(order_id: int = Path(ge=1)):
    """Step 3: Calculate KPIs for an order."""
    order = app_state.db.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail=f"Order {order_id} not found")
    
    kpi_result = app_state.risk_engine.calculate_kpis(order)
    return kpi_result.model_dump()


@app.post("/detect-deviation/{order_id}", tags=["demo"])
def detect_deviation(order_id: int = Path(ge=1)):
    """Step 4: Detect risk signal for an order."""
    order = app_state.db.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail=f"Order {order_id} not found")
    
    signal = app_state.risk_engine.detect(order)
    
    return {
        "order_id": order_id,
        "signal_type": signal.signal_type.value,
        "severity": signal.severity.value,
        "reason": signal.reason,
        "kpis": signal.kpis,
        "has_risk": signal.signal_type.value != "ON_TRACK",
    }


@app.post("/trigger-agent/{order_id}", tags=["demo"])
def trigger_agent(order_id: int = Path(ge=1)):
    """Step 5: Trigger multi-agent resolution system.
    
    Uses LangGraph supervisor to orchestrate specialist agents:
    - OperationsAgent: Hub inquiries
    - CustomerAgent: Customer communication
    - ResolutionAgent: Refunds, reschedules
    
    Logged to Langfuse for observability.
    """
    from src.agent import run_supervisor
    
    order = app_state.db.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail=f"Order {order_id} not found")
    
    signal = app_state.risk_engine.detect(order)
    
    # No action needed for ON_TRACK
    if signal.signal_type.value == "ON_TRACK":
        return {
            "order_id": order_id,
            "status": "no_action",
            "signal_type": signal.signal_type.value,
            "message": "Shipment on track, no intervention needed",
        }
    
    # Run multi-agent supervisor
    result = run_supervisor(
        order=order,
        signal_type=signal.signal_type.value,
        signal_reason=signal.reason,
        use_checkpointer=True,
    )
    
    # Store conversation in DB
    if result.get("conversation_turns"):
        conv_id = app_state.db.create_conversation(order_id, signal.signal_type.value)
        for turn in result["conversation_turns"]:
            app_state.db.add_turn(
                conv_id,
                role=turn.get("role", "agent"),
                message=turn.get("message", ""),
                action=turn.get("action"),
            )
        app_state.db.update_conversation_status(
            conv_id,
            status=result.get("status", "resolved"),
            resolution=result.get("resolution"),
        )
    
    return {
        "order_id": order_id,
        "status": result.get("status", "resolved"),
        "signal_type": signal.signal_type.value,
        "resolution": result.get("resolution"),
        "actions_taken": result.get("actions_taken", []),
        "conversation_turns": len(result.get("conversation_turns", [])),
    }


@app.get("/view-response/{order_id}", tags=["demo"])
def view_response(order_id: int = Path(ge=1)):
    """Step 6: View conversation/actions for an order."""
    order = app_state.db.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail=f"Order {order_id} not found")
    
    conversation = app_state.db.get_conversation(order_id)
    
    return {
        "order_id": order_id,
        "conversation": conversation,
    }



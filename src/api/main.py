"""
Celonis Garage - Proactive Logistics Agent API

Simplified API for the demo flow:
  1. POST /bootstrap           - Seed demo data
  2. GET  /orders/{id}         - View order details
  3. GET  /kpis/{id}           - Calculate KPIs
  4. POST /detect-deviation/{id} - Detect risk signal
  5. POST /trigger-agent/{id}  - AI agent resolves issue (placeholder)
  6. GET  /view-response/{id}  - View conversation
"""
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Path

from src.config import get_db_connection_string
from src.storage_manager.postgres_manager import PostgresManager
from src.risk_detection.risk_engine import RiskEngine
from src.bootstrap import bootstrap, SCENARIOS


# ==================== APPLICATION STATE ====================

class AppState:
    db: PostgresManager = None
    risk_engine: RiskEngine = None

app_state = AppState()


# ==================== LIFESPAN ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize DB and RiskEngine on startup."""
    print("🚀 Starting API...")
    
    conn_string = get_db_connection_string()
    app_state.db = PostgresManager(conn_string)
    app_state.risk_engine = RiskEngine()
    
    print(f"✓ DB connected")
    print(f"✓ Route stats loaded: {len(app_state.risk_engine.route_stats)} routes")
    
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
    """Step 5: Trigger agent resolution (placeholder - will implement next)."""
    order = app_state.db.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail=f"Order {order_id} not found")
    
    signal = app_state.risk_engine.detect(order)
    
    # Placeholder response - agent will be implemented next
    return {
        "order_id": order_id,
        "status": "no_risk" if signal.signal_type.value == "ON_TRACK" else "pending_agent",
        "signal_type": signal.signal_type.value,
        "message": "Agent not yet implemented" if signal.signal_type.value != "ON_TRACK" else "No action needed",
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


@app.get("/orders", tags=["demo"])
def list_orders():
    """List all orders."""
    orders = app_state.db.get_all_orders()
    return {"orders": orders, "count": len(orders)}

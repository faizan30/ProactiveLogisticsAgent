"""
Contracts - Enums and Pydantic models for the 4 demo scenarios.

Signals:
1. ON_TRACK - Happy path, no action needed
2. PREDICTED_DELAY - Agent offers refund
3. STUCK_AT_HUB - Contact hub → reschedule
4. TICKET_RAISED - Empathy + refund
"""
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


# ==================== ENUMS ====================

class SignalType(str, Enum):
    """Risk signal types - maps to 4 scenarios."""
    ON_TRACK = "ON_TRACK"
    PREDICTED_DELAY = "PREDICTED_DELAY"
    STUCK_AT_HUB = "STUCK_AT_HUB"
    TICKET_RAISED = "TICKET_RAISED"


class Severity(str, Enum):
    """Risk severity levels."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


# ==================== MODELS ====================

class RiskSignal(BaseModel):
    """Risk signal from detection engine."""
    order_id: int
    signal_type: SignalType
    severity: Severity
    reason: str
    kpis: dict[str, Any] = Field(default_factory=dict)


class BreachResult(BaseModel):
    """Result of KPI breach detection."""
    breached: bool
    kpi_name: str
    value: float
    threshold: Optional[float] = None
    reason: Optional[str] = None
    severity: Optional[Severity] = None


class KPIResult(BaseModel):
    """KPI calculation result."""
    order_id: int
    kpis: dict[str, float]
    thresholds: dict[str, float]
    breaches: list[BreachResult] = Field(default_factory=list)


class ConversationTurn(BaseModel):
    """Single turn in multi-turn conversation."""
    role: str  # "agent", "customer", "hub_manager"
    action: Optional[str] = None
    message: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class Conversation(BaseModel):
    """Multi-turn conversation state."""
    order_id: int
    signal_type: SignalType
    turns: list[ConversationTurn] = Field(default_factory=list)
    status: str = "in_progress"  # in_progress, resolved
    resolution: Optional[str] = None  # refund, reschedule, none


class Order(BaseModel):
    """Order data with validation for risk detection."""
    id: int
    order_date: Optional[datetime] = None
    promised_date: Optional[datetime] = None
    ship_date: Optional[datetime] = None
    destination_arrival_date: Optional[datetime] = None
    actual_delivery_date: Optional[datetime] = None
    origin_region: Optional[str] = None
    destination_region: Optional[str] = None
    mode_of_shipment: Optional[str] = None
    customer_rating: Optional[int] = Field(default=None, ge=1, le=5)
    customer_care_calls: int = 0
    ticket_raised: int = Field(default=0, ge=0, le=1)
    product_cost: Optional[float] = Field(default=None, ge=0)
    mocked_customer_response: Optional[str] = None
    
    class Config:
        extra = "allow"  # Allow additional fields

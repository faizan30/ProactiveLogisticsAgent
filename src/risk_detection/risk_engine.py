"""
RiskEngine - Threshold-based risk detection using KPI classes.

See README.md for detailed design documentation.

Detection Priority:
1. TICKET_RAISED  → Customer complained (reactive, highest priority)
2. STUCK_AT_HUB   → Package idle at hub > 24h (actionable)
3. PREDICTED_DELAY → Proactive delay prediction (preventive)
4. ON_TRACK       → No issues detected (default)
"""
import logging
from datetime import datetime
from typing import Dict
import json
from pathlib import Path

from src.contracts.models import SignalType, Severity, RiskSignal, KPIResult
from src.config import THRESHOLDS
from src.risk_detection.kpis import ALL_KPIS, get_current_time

logger = logging.getLogger(__name__)


def load_route_stats() -> Dict:
    """Load route stats from JSON file."""
    path = Path(__file__).resolve().parents[2] / "data" / "route_stats.json"
    if path.exists():
        with path.open() as f:
            return json.load(f)
    return {}


class RiskEngine:
    """Threshold-based risk detection using KPI classes."""
    
    def __init__(self):
        self.route_stats = load_route_stats()
        self.thresholds = THRESHOLDS
        self.kpis = ALL_KPIS
    
    def calculate_kpis(self, order: dict, now: datetime = None) -> KPIResult:
        """Calculate all KPIs and check breaches using KPI classes."""
        now = now or get_current_time()
        context = {
            "now": now,
            "route_stats": self.route_stats,
            "thresholds": self.thresholds,  # Pass thresholds for composite KPIs
            "order": order,
            "kpi_values": {},  # Will be populated as we calculate
            "breaches": [],    # Will be populated - allows composite KPIs to check breaches
        }
        
        # Calculate each KPI and check for breaches
        kpi_values = {}
        breaches = []
        for kpi in self.kpis:
            # Update context with calculated values and breaches for composite KPIs
            context["kpi_values"] = kpi_values
            context["breaches"] = breaches
            
            value = kpi.calculate(order, context)
            kpi_values[kpi.name] = value
            
            breach_result = kpi.is_breached(value, self.thresholds, context)
            if breach_result.breached:
                breaches.append(breach_result)
        
        # Add ticket_raised (not a calculated KPI, just a field)
        kpi_values["ticket_raised"] = order.get("ticket_raised", 0)
        
        return KPIResult(
            order_id=order["id"],
            kpis=kpi_values,
            thresholds=self.thresholds,
            breaches=breaches
        )
    
    def _get_breach(self, breaches: list, kpi_name: str):
        """Get breach result by KPI name."""
        for b in breaches:
            if b.kpi_name == kpi_name:
                return b
        return None
    
    def detect(self, order: dict, now: datetime = None) -> RiskSignal:
        """Detect risk signal based on KPIs and breaches. Simplified priority logic."""
        now = now or get_current_time()
        kpi_result = self.calculate_kpis(order, now)
        kpis = kpi_result.kpis
        breaches = kpi_result.breaches
        
        logger.debug(f"Order {order.get('id')}: KPIs={kpis}, breaches={[b.kpi_name for b in breaches]}")
        
        # Priority 1: Ticket raised → reactive (highest priority)
        # Customer has already escalated, requires immediate response
        if kpis["ticket_raised"] == 1:
            return RiskSignal(
                order_id=order["id"],
                signal_type=SignalType.TICKET_RAISED,
                severity=Severity.CRITICAL,
                reason="Customer ticket raised - requires immediate attention",
                kpis=kpis
            )
        
        # Priority 2: Stuck at hub → actionable
        # Clear operational issue that can be resolved
        hub_breach = self._get_breach(breaches, "hub_hours")
        if hub_breach:
            return RiskSignal(
                order_id=order["id"],
                signal_type=SignalType.STUCK_AT_HUB,
                severity=hub_breach.severity,
                reason=hub_breach.reason,
                kpis=kpis
            )
        
        # Priority 3: Predicted delay → proactive
        # Composite KPI handles the complex logic
        predicted_breach = self._get_breach(breaches, "predicted_delay")
        if predicted_breach:
            return RiskSignal(
                order_id=order["id"],
                signal_type=SignalType.PREDICTED_DELAY,
                severity=predicted_breach.severity,
                reason=predicted_breach.reason,
                kpis=kpis
            )
        
        # Default: On track
        return RiskSignal(
            order_id=order["id"],
            signal_type=SignalType.ON_TRACK,
            severity=Severity.LOW,
            reason="Shipment progressing normally",
            kpis=kpis
        )

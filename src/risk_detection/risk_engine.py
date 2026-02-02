"""
RiskEngine - Threshold-based risk detection using KPI classes.

Detection Priority:
1. Ticket Raised → TICKET_RAISED (reactive)
2. Stuck at Hub > threshold → STUCK_AT_HUB
3. In transit too long + near deadline → PREDICTED_DELAY
4. Otherwise → ON_TRACK
"""
from datetime import datetime
from typing import Dict
import json
from pathlib import Path

from src.contracts.models import SignalType, Severity, RiskSignal, KPIResult
from src.config import THRESHOLDS
from src.risk_detection.kpis import ALL_KPIS


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
        now = now or datetime.now()
        context = {"now": now, "route_stats": self.route_stats}
        
        # Calculate each KPI and check for breaches
        kpi_values = {}
        breaches = []
        for kpi in self.kpis:
            value = kpi.calculate(order, context)
            kpi_values[kpi.name] = value
            
            breach_result = kpi.is_breached(value, self.thresholds)
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
        """Detect risk signal based on KPIs and breaches. Priority logic here."""
        now = now or datetime.now()
        kpi_result = self.calculate_kpis(order, now)
        kpis = kpi_result.kpis
        breaches = kpi_result.breaches
        
        # Priority 1: Ticket raised → reactive (not a KPI breach, direct field)
        if kpis["ticket_raised"] == 1:
            return RiskSignal(
                order_id=order["id"],
                signal_type=SignalType.TICKET_RAISED,
                severity=Severity.CRITICAL,
                reason="Customer ticket raised - requires immediate attention",
                kpis=kpis
            )
        
        # Priority 2: Stuck at hub
        hub_breach = self._get_breach(breaches, "hub_hours")
        if hub_breach:
            return RiskSignal(
                order_id=order["id"],
                signal_type=SignalType.STUCK_AT_HUB,
                severity=hub_breach.severity,
                reason=hub_breach.reason,
                kpis=kpis
            )
        
        # Priority 3: Predicted delay (transit breach + days_remaining breach)
        transit_breach = self._get_breach(breaches, "transit_days")
        remaining_breach = self._get_breach(breaches, "days_remaining")
        if transit_breach and remaining_breach:
            return RiskSignal(
                order_id=order["id"],
                signal_type=SignalType.PREDICTED_DELAY,
                severity=Severity.HIGH,
                reason=f"{transit_breach.reason}; {remaining_breach.reason}",
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

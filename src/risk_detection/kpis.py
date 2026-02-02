"""
KPI Calculators - Each KPI has calculate() and is_breached() methods.

- calculate(): Returns raw KPI value
- is_breached(): Returns BreachResult with reason and severity
"""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Any

from src.config import KPI_CONFIG
from src.contracts.models import BreachResult, Severity


class KPI(ABC):
    """Base KPI class."""
    name: str
    
    @abstractmethod
    def calculate(self, order: dict, context: Dict[str, Any]) -> float:
        pass
    
    @abstractmethod
    def is_breached(self, value: float, thresholds: dict) -> BreachResult:
        """Check if KPI value breaches threshold. Returns BreachResult with reason/severity."""
        pass


class HubHoursKPI(KPI):
    """Hours at destination hub without delivery."""
    name = "hub_hours"
    
    def calculate(self, order: dict, context: Dict[str, Any]) -> float:
        now = context.get("now", datetime.now())
        arrival = order.get("destination_arrival_date")
        delivery = order.get("actual_delivery_date")
        
        if arrival and not delivery:
            return round((now - arrival).total_seconds() / 3600, 1)
        return 0.0
    
    def is_breached(self, value: float, thresholds: dict) -> BreachResult:
        threshold = thresholds.get("hub_hours", 48)
        breached = value > threshold
        return BreachResult(
            breached=breached,
            kpi_name=self.name,
            value=value,
            threshold=threshold,
            reason=f"Package at hub for {value:.0f}h (threshold: {threshold}h)" if breached else None,
            severity=Severity.HIGH if breached else None
        )


class TransitDaysKPI(KPI):
    """Days in transit without arrival at destination."""
    name = "transit_days"
    
    def calculate(self, order: dict, context: Dict[str, Any]) -> float:
        now = context.get("now", datetime.now())
        ship_date = order.get("ship_date")
        arrival = order.get("destination_arrival_date")
        
        if ship_date and not arrival:
            return float((now - ship_date).days)
        return 0.0
    
    def is_breached(self, value: float, thresholds: dict) -> BreachResult:
        threshold = thresholds.get("transit_days", 3)
        breached = value > threshold
        return BreachResult(
            breached=breached,
            kpi_name=self.name,
            value=value,
            threshold=threshold,
            reason=f"In transit for {value:.0f} days (threshold: {threshold}d)" if breached else None,
            severity=Severity.MEDIUM if breached else None
        )


class DaysRemainingKPI(KPI):
    """Days until promised delivery date (negative = overdue)."""
    name = "days_remaining"
    
    def calculate(self, order: dict, context: Dict[str, Any]) -> float:
        now = context.get("now", datetime.now())
        promised = order.get("promised_date")
        
        if promised:
            return float((promised - now).days)
        return 999.0
    
    def is_breached(self, value: float, thresholds: dict) -> BreachResult:
        threshold = thresholds.get("days_remaining_buffer", 2)
        breached = value < threshold
        return BreachResult(
            breached=breached,
            kpi_name=self.name,
            value=value,
            threshold=threshold,
            reason=f"Only {value:.0f} days remaining (buffer: {threshold}d)" if breached else None,
            severity=Severity.HIGH if value < 0 else (Severity.MEDIUM if breached else None)
        )


class RouteFailureRateKPI(KPI):
    """Historical failure rate for route segment."""
    name = "route_failure_rate"
    
    def calculate(self, order: dict, context: Dict[str, Any]) -> float:
        route_key = f"{order.get('origin_region')}_{order.get('destination_region')}_{order.get('mode_of_shipment')}"
        route_stats = context.get("route_stats", {})
        return route_stats.get(route_key, {}).get("failure_rate", 0.0)
    
    def is_breached(self, value: float, thresholds: dict) -> BreachResult:
        threshold = thresholds.get("route_failure_rate", 0.5)
        breached = value > threshold
        return BreachResult(
            breached=breached,
            kpi_name=self.name,
            value=value,
            threshold=threshold,
            reason=f"High-risk route ({value:.0%} failure rate)" if breached else None,
            severity=Severity.MEDIUM if breached else None
        )


class AvgTransitDaysKPI(KPI):
    """Expected transit days for route (informational, no breach)."""
    name = "avg_transit_days"
    
    def calculate(self, order: dict, context: Dict[str, Any]) -> float:
        route_key = f"{order.get('origin_region')}_{order.get('destination_region')}_{order.get('mode_of_shipment')}"
        route_stats = context.get("route_stats", {})
        return route_stats.get(route_key, {}).get("avg_transit_days", KPI_CONFIG["velocity_default_transit_days"])
    
    def is_breached(self, value: float, thresholds: dict) -> BreachResult:
        # Informational KPI - never breaches on its own
        return BreachResult(
            breached=False,
            kpi_name=self.name,
            value=value,
            threshold=None,
            reason=None,
            severity=None
        )


# All KPIs used by RiskEngine
ALL_KPIS = [
    HubHoursKPI(),
    TransitDaysKPI(),
    DaysRemainingKPI(),
    RouteFailureRateKPI(),
    AvgTransitDaysKPI(),
]

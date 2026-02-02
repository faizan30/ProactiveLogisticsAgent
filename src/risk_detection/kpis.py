"""
KPI Calculators - Each KPI has calculate() and is_breached() methods.

See README.md for detailed design documentation.

- calculate(): Returns raw KPI value
- is_breached(): Returns BreachResult with reason and severity
"""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Any

from src.config import KPI_CONFIG, THRESHOLDS, SEVERITY_CONFIG
from src.contracts.models import BreachResult, Severity


def get_severity(kpi_name: str) -> Severity:
    """Get configurable severity for a KPI from SEVERITY_CONFIG."""
    severity_str = SEVERITY_CONFIG.get(kpi_name, "MEDIUM")
    return Severity(severity_str)


# Constants
NO_DEADLINE_HOURS = 9999.0  # Value returned when order has no promised_date


def get_current_time() -> datetime:
    """
    Get current timestamp for KPI calculations.
    
    TODO: For multi-timezone support, this should return timezone-aware datetime.
    Currently assumes single timezone (server local time).
    
    Future implementation:
        return datetime.now(timezone.utc)
    """
    return datetime.now()


class KPI(ABC):
    """Base KPI class."""
    name: str
    
    @abstractmethod
    def calculate(self, order: dict, context: Dict[str, Any]) -> float:
        pass
    
    @abstractmethod
    def is_breached(self, value: float, thresholds: dict, context: Dict[str, Any] = None) -> BreachResult:
        """Check if KPI value breaches threshold. Returns BreachResult with reason/severity."""
        pass


class HubHoursKPI(KPI):
    """Hours at destination hub without delivery. Threshold: 24h."""
    name = "hub_hours"
    
    def calculate(self, order: dict, context: Dict[str, Any]) -> float:
        now = context.get("now", get_current_time())
        arrival = order.get("destination_arrival_date")
        delivery = order.get("actual_delivery_date")
        
        if arrival and not delivery:
            hours = (now - arrival).total_seconds() / 3600
            return max(0.0, round(hours, 1))  # Clamp negative to 0
        return 0.0
    
    def is_breached(self, value: float, thresholds: dict, context: Dict[str, Any] = None) -> BreachResult:
        threshold = thresholds.get("hub_hours", 24)
        breached = value > threshold
        return BreachResult(
            breached=breached,
            kpi_name=self.name,
            value=value,
            threshold=threshold,
            reason=f"Package at hub for {value:.0f}h (threshold: {threshold}h)" if breached else None,
            severity=get_severity(self.name) if breached else None
        )


class TransitHoursKPI(KPI):
    """
    Hours in transit with route+mode specific dynamic threshold.
    
    Threshold = route_avg_hours + buffer (24h default)
    
    Route key format: "{origin_region}_{destination_region}_{mode_of_shipment}"
    Example: "South_Midwest_Flight" -> uses avg_transit_days from route_stats.json
    
    If route not found in historical data, uses default_transit_hours (168h = 7 days).
    """
    name = "transit_hours"
    
    def calculate(self, order: dict, context: Dict[str, Any]) -> float:
        """Calculate hours in transit (shipped but not arrived at hub)."""
        now = context.get("now", get_current_time())
        ship_date = order.get("ship_date")
        arrival = order.get("destination_arrival_date")
        
        if ship_date and not arrival:
            hours = (now - ship_date).total_seconds() / 3600
            return max(0.0, round(hours, 1))  # Clamp negative to 0
        return 0.0
    
    def _get_route_avg_hours(self, order: dict, context: Dict[str, Any]) -> float:
        """
        Get expected transit hours for this specific route+mode combination.
        
        Looks up: route_stats["{origin}_{dest}_{mode}"]["avg_transit_days"]
        Returns: avg_transit_days * 24 (converted to hours), minimum 24h
        """
        route_key = f"{order.get('origin_region')}_{order.get('destination_region')}_{order.get('mode_of_shipment')}"
        route_stats = context.get("route_stats", {})
        default_hours = THRESHOLDS.get("default_transit_hours", 168)
        avg_days = route_stats.get(route_key, {}).get("avg_transit_days")
        if avg_days is not None:
            return max(avg_days * 24, 24)  # Minimum 1 day (24h)
        return default_hours
    
    def is_breached(self, value: float, thresholds: dict, context: Dict[str, Any] = None) -> BreachResult:
        context = context or {}
        order = context.get("order", {})
        route_avg_hours = self._get_route_avg_hours(order, context)
        buffer = thresholds.get("transit_buffer_hours", 24)
        threshold = route_avg_hours + buffer
        breached = value > threshold
        return BreachResult(
            breached=breached,
            kpi_name=self.name,
            value=value,
            threshold=threshold,
            reason=f"In transit {value:.0f}h (expected: {route_avg_hours:.0f}h + {buffer}h buffer)" if breached else None,
            severity=get_severity(self.name) if breached else None
        )


class HoursRemainingKPI(KPI):
    """Hours until promised delivery. Negative = overdue. Breach when < 0."""
    name = "hours_remaining"
    
    def calculate(self, order: dict, context: Dict[str, Any]) -> float:
        now = context.get("now", get_current_time())
        promised = order.get("promised_date")
        
        if promised:
            hours = (promised - now).total_seconds() / 3600
            return round(hours, 1)
        return NO_DEADLINE_HOURS
    
    def is_breached(self, value: float, thresholds: dict, context: Dict[str, Any] = None) -> BreachResult:
        breached = value < 0
        return BreachResult(
            breached=breached,
            kpi_name=self.name,
            value=value,
            threshold=0,
            reason=f"Overdue by {abs(value):.0f}h" if breached else None,
            severity=get_severity(self.name) if breached else None
        )


class RouteRiskKPI(KPI):
    """
    Historical failure rate for route+mode combination.
    
    Route key format: "{origin_region}_{destination_region}_{mode_of_shipment}"
    Example: "West_East_Road" -> uses failure_rate from route_stats.json
    
    Unknown routes default to 0.5 (moderate risk - new routes need monitoring).
    """
    name = "route_failure_rate"
    
    def calculate(self, order: dict, context: Dict[str, Any]) -> float:
        """Look up historical failure rate for this route+mode from route_stats."""
        route_key = f"{order.get('origin_region')}_{order.get('destination_region')}_{order.get('mode_of_shipment')}"
        route_stats = context.get("route_stats", {})
        # Default to 0.5 for unknown routes (moderate risk assumption)
        return route_stats.get(route_key, {}).get("failure_rate", 0.5)
    
    def is_breached(self, value: float, thresholds: dict, context: Dict[str, Any] = None) -> BreachResult:
        threshold = thresholds.get("route_failure_rate", 0.5)
        breached = value > threshold
        return BreachResult(
            breached=breached,
            kpi_name=self.name,
            value=value,
            threshold=threshold,
            reason=f"High-risk route ({value:.0%} failure rate)" if breached else None,
            severity=get_severity(self.name) if breached else None
        )


class PredictedDelayKPI(KPI):
    """
    Composite KPI predicting if delivery will be late.
    
    Reuses already-calculated KPI values and breach results from context.
    Must be calculated LAST in the KPI chain.
    """
    name = "predicted_delay"
    
    def _has_breach(self, breaches: list, kpi_name: str) -> bool:
        """Check if a KPI already breached (reuses existing breach calculation)."""
        return any(b.kpi_name == kpi_name for b in breaches)
    
    def calculate(self, order: dict, context: Dict[str, Any]) -> float:
        """Returns 1.0 if delay predicted, 0.0 otherwise."""
        # Reuse already-calculated KPI values from context
        kpi_values = context.get("kpi_values", {})
        breaches = context.get("breaches", [])
        thresholds = context.get("thresholds", THRESHOLDS)
        
        hours_remaining = kpi_values.get("hours_remaining", NO_DEADLINE_HOURS)
        route_failure_rate = kpi_values.get("route_failure_rate", 0)
        
        # Reuse breach check from TransitHoursKPI (already route+mode specific)
        is_transit_slow = self._has_breach(breaches, "transit_hours")
        
        # Threshold for deadline pressure
        deadline_pressure = thresholds.get("deadline_pressure_hours", 48)
        
        # Condition checks
        is_overdue = hours_remaining < 0
        has_deadline_pressure = hours_remaining < deadline_pressure
        is_high_risk_route = route_failure_rate > thresholds.get("route_failure_rate", 0.5)
        
        # Predict delay if:
        # 1. Already overdue (hours_remaining breach)
        # 2. Transit slow (route+mode specific) AND deadline pressure
        # 3. High-risk route AND deadline pressure (proactive warning)
        predicted = (
            is_overdue or
            (is_transit_slow and has_deadline_pressure) or
            (is_high_risk_route and has_deadline_pressure)
        )
        
        return 1.0 if predicted else 0.0
    
    def is_breached(self, value: float, thresholds: dict, context: Dict[str, Any] = None) -> BreachResult:
        breached = value > 0.5  # 1.0 = predicted delay
        return BreachResult(
            breached=breached,
            kpi_name=self.name,
            value=value,
            threshold=0.5,
            reason="Delivery delay predicted based on transit time and deadline" if breached else None,
            severity=get_severity(self.name) if breached else None
        )


# All KPIs used by RiskEngine (order matters for composite KPI)
ALL_KPIS = [
    HubHoursKPI(),
    TransitHoursKPI(),
    HoursRemainingKPI(),
    RouteRiskKPI(),
    PredictedDelayKPI(),  # Must be last - depends on other KPI values
]

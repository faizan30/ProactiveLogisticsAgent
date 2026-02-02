"""
Unit tests for KPI calculators.

Tests each KPI's calculate() and is_breached() methods independently.
"""
import pytest
from datetime import datetime, timedelta

from src.risk_detection.kpis import (
    HubHoursKPI,
    TransitHoursKPI,
    HoursRemainingKPI,
    RouteRiskKPI,
    PredictedDelayKPI,
)
from src.contracts.models import Severity


class TestHubHoursKPI:
    """Tests for HubHoursKPI - hours at destination hub without delivery."""
    
    @pytest.fixture
    def kpi(self):
        return HubHoursKPI()
    
    def test_name(self, kpi):
        assert kpi.name == "hub_hours"
    
    def test_calculate_no_arrival(self, kpi, now):
        """No arrival date = 0 hours."""
        order = {"destination_arrival_date": None, "actual_delivery_date": None}
        context = {"now": now}
        assert kpi.calculate(order, context) == 0.0
    
    def test_calculate_already_delivered(self, kpi, now):
        """Already delivered = 0 hours (not stuck)."""
        order = {
            "destination_arrival_date": now - timedelta(hours=24),
            "actual_delivery_date": now - timedelta(hours=12),
        }
        context = {"now": now}
        assert kpi.calculate(order, context) == 0.0
    
    def test_calculate_at_hub_24_hours(self, kpi, now):
        """At hub for 24 hours."""
        order = {
            "destination_arrival_date": now - timedelta(hours=24),
            "actual_delivery_date": None,
        }
        context = {"now": now}
        assert kpi.calculate(order, context) == 24.0
    
    def test_calculate_at_hub_30_hours(self, kpi, now):
        """At hub for 30 hours (exceeds 24h threshold)."""
        order = {
            "destination_arrival_date": now - timedelta(hours=30),
            "actual_delivery_date": None,
        }
        context = {"now": now}
        assert kpi.calculate(order, context) == 30.0
    
    def test_calculate_negative_clamped(self, kpi, now):
        """Future arrival date = clamped to 0."""
        order = {
            "destination_arrival_date": now + timedelta(hours=5),
            "actual_delivery_date": None,
        }
        context = {"now": now}
        assert kpi.calculate(order, context) == 0.0
    
    def test_breach_below_threshold(self, kpi, default_thresholds):
        """20 hours < 24 threshold = no breach."""
        result = kpi.is_breached(20.0, default_thresholds)
        assert result.breached is False
        assert result.kpi_name == "hub_hours"
        assert result.value == 20.0
        assert result.threshold == 24
    
    def test_breach_at_threshold(self, kpi, default_thresholds):
        """Exactly at threshold = no breach (> not >=)."""
        result = kpi.is_breached(24.0, default_thresholds)
        assert result.breached is False
    
    def test_breach_above_threshold(self, kpi, default_thresholds):
        """30 hours > 24 threshold = breach with HIGH severity."""
        result = kpi.is_breached(30.0, default_thresholds)
        assert result.breached is True
        assert result.severity == Severity.HIGH
        assert "30h" in result.reason
        assert "24h" in result.reason


class TestTransitHoursKPI:
    """Tests for TransitHoursKPI - hours in transit with dynamic threshold."""
    
    @pytest.fixture
    def kpi(self):
        return TransitHoursKPI()
    
    def test_name(self, kpi):
        assert kpi.name == "transit_hours"
    
    def test_calculate_not_shipped(self, kpi, now):
        """Not shipped yet = 0 hours."""
        order = {"ship_date": None, "destination_arrival_date": None}
        context = {"now": now}
        assert kpi.calculate(order, context) == 0.0
    
    def test_calculate_already_arrived(self, kpi, now):
        """Already arrived = 0 hours (not in transit)."""
        order = {
            "ship_date": now - timedelta(hours=72),
            "destination_arrival_date": now - timedelta(hours=24),
        }
        context = {"now": now}
        assert kpi.calculate(order, context) == 0.0
    
    def test_calculate_in_transit_24_hours(self, kpi, now):
        """In transit for 24 hours."""
        order = {
            "ship_date": now - timedelta(hours=24),
            "destination_arrival_date": None,
        }
        context = {"now": now}
        assert kpi.calculate(order, context) == 24.0
    
    def test_calculate_in_transit_96_hours(self, kpi, now):
        """In transit for 96 hours (4 days)."""
        order = {
            "ship_date": now - timedelta(hours=96),
            "destination_arrival_date": None,
        }
        context = {"now": now}
        assert kpi.calculate(order, context) == 96.0
    
    def test_calculate_negative_clamped(self, kpi, now):
        """Future ship date = clamped to 0."""
        order = {
            "ship_date": now + timedelta(hours=5),
            "destination_arrival_date": None,
        }
        context = {"now": now}
        assert kpi.calculate(order, context) == 0.0
    
    def test_breach_with_known_route(self, kpi, sample_route_stats, default_thresholds):
        """Known route: breach if transit > route_avg + 24h buffer."""
        order = {
            "origin_region": "South",
            "destination_region": "Midwest",
            "mode_of_shipment": "Flight",
        }
        context = {"route_stats": sample_route_stats, "order": order}
        # Route avg = 2 days = 48h, threshold = 48 + 24 = 72h
        # 80h > 72h = breach
        result = kpi.is_breached(80.0, default_thresholds, context)
        assert result.breached is True
        assert result.severity == Severity.MEDIUM
    
    def test_no_breach_within_buffer(self, kpi, sample_route_stats, default_thresholds):
        """Within route_avg + buffer = no breach."""
        order = {
            "origin_region": "South",
            "destination_region": "Midwest",
            "mode_of_shipment": "Flight",
        }
        context = {"route_stats": sample_route_stats, "order": order}
        # Route avg = 48h, threshold = 72h, transit = 60h < 72h
        result = kpi.is_breached(60.0, default_thresholds, context)
        assert result.breached is False
    
    def test_breach_unknown_route_uses_default(self, kpi, default_thresholds):
        """Unknown route uses default 168h (7 days) avg."""
        order = {
            "origin_region": "Unknown",
            "destination_region": "Unknown",
            "mode_of_shipment": "Ship",
        }
        context = {"route_stats": {}, "order": order}
        # Default avg = 168h, threshold = 168 + 24 = 192h
        # 200h > 192h = breach
        result = kpi.is_breached(200.0, default_thresholds, context)
        assert result.breached is True
    
    def test_zero_avg_transit_days_uses_minimum(self, kpi, default_thresholds):
        """Route with 0 avg_transit_days uses minimum 24h (1 day)."""
        order = {
            "origin_region": "Test",
            "destination_region": "Test",
            "mode_of_shipment": "Flight",
        }
        # Route with 0 avg_transit_days (edge case)
        route_stats = {"Test_Test_Flight": {"avg_transit_days": 0, "failure_rate": 0.1}}
        context = {"route_stats": route_stats, "order": order}
        # Min avg = 24h (clamped from 0), threshold = 24 + 24 = 48h
        # 50h > 48h = breach
        result = kpi.is_breached(50.0, default_thresholds, context)
        assert result.breached is True
        assert result.threshold == 48.0  # 24h min + 24h buffer


class TestHoursRemainingKPI:
    """Tests for HoursRemainingKPI - hours until promised date, breach when overdue."""
    
    @pytest.fixture
    def kpi(self):
        return HoursRemainingKPI()
    
    def test_name(self, kpi):
        assert kpi.name == "hours_remaining"
    
    def test_calculate_no_promised_date(self, kpi, now):
        """No promised date = 9999 (no deadline)."""
        order = {"promised_date": None}
        context = {"now": now}
        assert kpi.calculate(order, context) == 9999.0
    
    def test_calculate_240_hours_remaining(self, kpi, now):
        """10 days = 240 hours until promised date."""
        order = {"promised_date": now + timedelta(hours=240)}
        context = {"now": now}
        assert kpi.calculate(order, context) == 240.0
    
    def test_calculate_24_hours_remaining(self, kpi, now):
        """24 hours until promised date."""
        order = {"promised_date": now + timedelta(hours=24)}
        context = {"now": now}
        assert kpi.calculate(order, context) == 24.0
    
    def test_calculate_overdue(self, kpi, now):
        """24 hours past promised date = -24."""
        order = {"promised_date": now - timedelta(hours=24)}
        context = {"now": now}
        assert kpi.calculate(order, context) == -24.0
    
    def test_breach_plenty_of_time(self, kpi, default_thresholds):
        """240 hours remaining >= 0 = no breach."""
        result = kpi.is_breached(240.0, default_thresholds)
        assert result.breached is False
    
    def test_no_breach_at_zero(self, kpi, default_thresholds):
        """Exactly 0 hours = not overdue yet, no breach."""
        result = kpi.is_breached(0.0, default_thresholds)
        assert result.breached is False
    
    def test_breach_overdue(self, kpi, default_thresholds):
        """Overdue (-24 hours) = breach with CRITICAL severity."""
        result = kpi.is_breached(-24.0, default_thresholds)
        assert result.breached is True
        assert result.severity == Severity.CRITICAL
        assert "Overdue" in result.reason
        assert "24h" in result.reason


class TestRouteRiskKPI:
    """Tests for RouteRiskKPI - historical failure rate for route."""
    
    @pytest.fixture
    def kpi(self):
        return RouteRiskKPI()
    
    def test_name(self, kpi):
        assert kpi.name == "route_failure_rate"
    
    def test_calculate_known_route(self, kpi, sample_route_stats):
        """Known route returns its failure rate."""
        order = {
            "origin_region": "South",
            "destination_region": "Midwest",
            "mode_of_shipment": "Flight",
        }
        context = {"route_stats": sample_route_stats}
        assert kpi.calculate(order, context) == 0.1
    
    def test_calculate_high_risk_route(self, kpi, sample_route_stats):
        """High-risk route with 60% failure rate."""
        order = {
            "origin_region": "West",
            "destination_region": "East",
            "mode_of_shipment": "Road",
        }
        context = {"route_stats": sample_route_stats}
        assert kpi.calculate(order, context) == 0.6
    
    def test_calculate_unknown_route_defaults_to_0_5(self, kpi, sample_route_stats):
        """Unknown route returns 0.5 (moderate risk assumption)."""
        order = {
            "origin_region": "Unknown",
            "destination_region": "Unknown",
            "mode_of_shipment": "Ship",
        }
        context = {"route_stats": sample_route_stats}
        assert kpi.calculate(order, context) == 0.5
    
    def test_breach_low_risk(self, kpi, default_thresholds):
        """10% failure rate < 50% threshold = no breach."""
        result = kpi.is_breached(0.1, default_thresholds)
        assert result.breached is False
    
    def test_no_breach_at_threshold(self, kpi, default_thresholds):
        """Exactly 50% = no breach (> not >=)."""
        result = kpi.is_breached(0.5, default_thresholds)
        assert result.breached is False
    
    def test_breach_high_risk(self, kpi, default_thresholds):
        """60% failure rate > 50% threshold = breach."""
        result = kpi.is_breached(0.6, default_thresholds)
        assert result.breached is True
        assert result.severity == Severity.MEDIUM
        assert "60%" in result.reason


class TestPredictedDelayKPI:
    """Tests for PredictedDelayKPI - composite delay prediction."""
    
    @pytest.fixture
    def kpi(self):
        return PredictedDelayKPI()
    
    def test_name(self, kpi):
        assert kpi.name == "predicted_delay"
    
    def test_no_delay_on_track(self, kpi, now, sample_route_stats):
        """All good = no predicted delay."""
        order = {
            "origin_region": "South",
            "destination_region": "Midwest",
            "mode_of_shipment": "Flight",
        }
        context = {
            "now": now,
            "route_stats": sample_route_stats,
            "kpi_values": {
                "hours_remaining": 240,  # 10 days
                "transit_hours": 24,     # 1 day
                "hub_hours": 0,
                "route_failure_rate": 0.1,
            }
        }
        assert kpi.calculate(order, context) == 0.0
    
    def test_delay_when_overdue(self, kpi, now, sample_route_stats):
        """Overdue = predicted delay."""
        order = {
            "origin_region": "South",
            "destination_region": "Midwest",
            "mode_of_shipment": "Flight",
        }
        context = {
            "now": now,
            "route_stats": sample_route_stats,
            "kpi_values": {
                "hours_remaining": -24,  # Overdue
                "transit_hours": 24,
                "hub_hours": 0,
                "route_failure_rate": 0.1,
            }
        }
        assert kpi.calculate(order, context) == 1.0
    
    def test_delay_when_slow_transit_and_deadline_pressure(self, kpi, now, sample_route_stats):
        """Slow transit (breached) + deadline pressure = predicted delay."""
        from src.contracts.models import BreachResult, Severity
        order = {
            "origin_region": "South",
            "destination_region": "Midwest",
            "mode_of_shipment": "Flight",
        }
        # PredictedDelayKPI now reuses transit_hours breach from context
        transit_breach = BreachResult(
            breached=True, kpi_name="transit_hours", value=100, threshold=72,
            reason="Slow transit", severity=Severity.MEDIUM
        )
        context = {
            "now": now,
            "route_stats": sample_route_stats,
            "breaches": [transit_breach],  # Transit already breached
            "kpi_values": {
                "hours_remaining": 24,  # < 48h = deadline pressure
                "transit_hours": 100,
                "hub_hours": 0,
                "route_failure_rate": 0.1,
            }
        }
        assert kpi.calculate(order, context) == 1.0
    
    def test_no_delay_slow_but_no_deadline_pressure(self, kpi, now, sample_route_stats):
        """Slow transit but plenty of time = no delay."""
        order = {
            "origin_region": "South",
            "destination_region": "Midwest",
            "mode_of_shipment": "Flight",
        }
        context = {
            "now": now,
            "route_stats": sample_route_stats,
            "kpi_values": {
                "hours_remaining": 240,  # 10 days, no pressure
                "transit_hours": 100,    # Slow but not urgent
                "hub_hours": 0,
                "route_failure_rate": 0.1,
            }
        }
        assert kpi.calculate(order, context) == 0.0
    
    def test_delay_high_risk_route_with_deadline_pressure(self, kpi, now, sample_route_stats):
        """High-risk route + deadline pressure = predicted delay (even if not slow)."""
        order = {
            "origin_region": "West",
            "destination_region": "East",
            "mode_of_shipment": "Road",  # 60% failure rate in sample_route_stats
        }
        context = {
            "now": now,
            "route_stats": sample_route_stats,
            "kpi_values": {
                "hours_remaining": 24,   # < 48h = deadline pressure
                "transit_hours": 24,     # Not slow
                "hub_hours": 0,
                "route_failure_rate": 0.6,  # High risk
            }
        }
        assert kpi.calculate(order, context) == 1.0
    
    def test_no_delay_high_risk_but_no_deadline_pressure(self, kpi, now, sample_route_stats):
        """High-risk route but plenty of time = no delay."""
        order = {
            "origin_region": "West",
            "destination_region": "East",
            "mode_of_shipment": "Road",
        }
        context = {
            "now": now,
            "route_stats": sample_route_stats,
            "kpi_values": {
                "hours_remaining": 240,  # Plenty of time
                "transit_hours": 24,
                "hub_hours": 0,
                "route_failure_rate": 0.6,  # High risk but no pressure
            }
        }
        assert kpi.calculate(order, context) == 0.0
    
    def test_breach_when_predicted(self, kpi, default_thresholds):
        """Predicted delay (1.0) = breach with HIGH severity."""
        result = kpi.is_breached(1.0, default_thresholds)
        assert result.breached is True
        assert result.severity == Severity.HIGH
        assert "predicted" in result.reason.lower()
    
    def test_no_breach_when_not_predicted(self, kpi, default_thresholds):
        """No predicted delay (0.0) = no breach."""
        result = kpi.is_breached(0.0, default_thresholds)
        assert result.breached is False

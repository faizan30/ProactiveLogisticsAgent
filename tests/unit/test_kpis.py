"""
Unit tests for KPI calculators.

Tests each KPI's calculate() and is_breached() methods independently.
"""
import pytest
from datetime import datetime, timedelta

from src.risk_detection.kpis import (
    HubHoursKPI,
    TransitDaysKPI,
    DaysRemainingKPI,
    RouteFailureRateKPI,
    AvgTransitDaysKPI,
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
    
    def test_calculate_at_hub_60_hours(self, kpi, now):
        """At hub for 60 hours (exceeds threshold)."""
        order = {
            "destination_arrival_date": now - timedelta(hours=60),
            "actual_delivery_date": None,
        }
        context = {"now": now}
        assert kpi.calculate(order, context) == 60.0
    
    def test_breach_below_threshold(self, kpi, default_thresholds):
        """24 hours < 48 threshold = no breach."""
        result = kpi.is_breached(24.0, default_thresholds)
        assert result.breached is False
        assert result.kpi_name == "hub_hours"
        assert result.value == 24.0
        assert result.threshold == 48
        assert result.reason is None
        assert result.severity is None
    
    def test_breach_at_threshold(self, kpi, default_thresholds):
        """Exactly at threshold = no breach (> not >=)."""
        result = kpi.is_breached(48.0, default_thresholds)
        assert result.breached is False
    
    def test_breach_above_threshold(self, kpi, default_thresholds):
        """60 hours > 48 threshold = breach with HIGH severity."""
        result = kpi.is_breached(60.0, default_thresholds)
        assert result.breached is True
        assert result.severity == Severity.HIGH
        assert "60h" in result.reason
        assert "48h" in result.reason


class TestTransitDaysKPI:
    """Tests for TransitDaysKPI - days in transit without arrival."""
    
    @pytest.fixture
    def kpi(self):
        return TransitDaysKPI()
    
    def test_name(self, kpi):
        assert kpi.name == "transit_days"
    
    def test_calculate_not_shipped(self, kpi, now):
        """Not shipped yet = 0 days."""
        order = {"ship_date": None, "destination_arrival_date": None}
        context = {"now": now}
        assert kpi.calculate(order, context) == 0.0
    
    def test_calculate_already_arrived(self, kpi, now):
        """Already arrived = 0 days (not in transit)."""
        order = {
            "ship_date": now - timedelta(days=3),
            "destination_arrival_date": now - timedelta(days=1),
        }
        context = {"now": now}
        assert kpi.calculate(order, context) == 0.0
    
    def test_calculate_in_transit_1_day(self, kpi, now):
        """In transit for 1 day."""
        order = {
            "ship_date": now - timedelta(days=1),
            "destination_arrival_date": None,
        }
        context = {"now": now}
        assert kpi.calculate(order, context) == 1.0
    
    def test_calculate_in_transit_4_days(self, kpi, now):
        """In transit for 4 days (exceeds threshold)."""
        order = {
            "ship_date": now - timedelta(days=4),
            "destination_arrival_date": None,
        }
        context = {"now": now}
        assert kpi.calculate(order, context) == 4.0
    
    def test_breach_below_threshold(self, kpi, default_thresholds):
        """2 days < 3 threshold = no breach."""
        result = kpi.is_breached(2.0, default_thresholds)
        assert result.breached is False
    
    def test_breach_above_threshold(self, kpi, default_thresholds):
        """4 days > 3 threshold = breach with MEDIUM severity."""
        result = kpi.is_breached(4.0, default_thresholds)
        assert result.breached is True
        assert result.severity == Severity.MEDIUM
        assert "4 days" in result.reason


class TestDaysRemainingKPI:
    """Tests for DaysRemainingKPI - days until promised date."""
    
    @pytest.fixture
    def kpi(self):
        return DaysRemainingKPI()
    
    def test_name(self, kpi):
        assert kpi.name == "days_remaining"
    
    def test_calculate_no_promised_date(self, kpi, now):
        """No promised date = 999 (no deadline)."""
        order = {"promised_date": None}
        context = {"now": now}
        assert kpi.calculate(order, context) == 999.0
    
    def test_calculate_10_days_remaining(self, kpi, now):
        """10 days until promised date."""
        order = {"promised_date": now + timedelta(days=10)}
        context = {"now": now}
        assert kpi.calculate(order, context) == 10.0
    
    def test_calculate_1_day_remaining(self, kpi, now):
        """1 day until promised date (within buffer)."""
        order = {"promised_date": now + timedelta(days=1)}
        context = {"now": now}
        assert kpi.calculate(order, context) == 1.0
    
    def test_calculate_overdue(self, kpi, now):
        """1 day past promised date = -1."""
        order = {"promised_date": now - timedelta(days=1)}
        context = {"now": now}
        assert kpi.calculate(order, context) == -1.0
    
    def test_breach_plenty_of_time(self, kpi, default_thresholds):
        """10 days remaining >= 2 buffer = no breach."""
        result = kpi.is_breached(10.0, default_thresholds)
        assert result.breached is False
    
    def test_breach_within_buffer(self, kpi, default_thresholds):
        """1 day remaining < 2 buffer = breach with MEDIUM severity."""
        result = kpi.is_breached(1.0, default_thresholds)
        assert result.breached is True
        assert result.severity == Severity.MEDIUM
        assert "1 days remaining" in result.reason
    
    def test_breach_overdue(self, kpi, default_thresholds):
        """Overdue (-1 days) = breach with HIGH severity."""
        result = kpi.is_breached(-1.0, default_thresholds)
        assert result.breached is True
        assert result.severity == Severity.HIGH


class TestRouteFailureRateKPI:
    """Tests for RouteFailureRateKPI - historical failure rate for route."""
    
    @pytest.fixture
    def kpi(self):
        return RouteFailureRateKPI()
    
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
    
    def test_calculate_unknown_route(self, kpi, sample_route_stats):
        """Unknown route returns 0.0."""
        order = {
            "origin_region": "Unknown",
            "destination_region": "Unknown",
            "mode_of_shipment": "Ship",
        }
        context = {"route_stats": sample_route_stats}
        assert kpi.calculate(order, context) == 0.0
    
    def test_breach_low_risk(self, kpi, default_thresholds):
        """10% failure rate < 50% threshold = no breach."""
        result = kpi.is_breached(0.1, default_thresholds)
        assert result.breached is False
    
    def test_breach_high_risk(self, kpi, default_thresholds):
        """60% failure rate > 50% threshold = breach."""
        result = kpi.is_breached(0.6, default_thresholds)
        assert result.breached is True
        assert result.severity == Severity.MEDIUM
        assert "60%" in result.reason


class TestAvgTransitDaysKPI:
    """Tests for AvgTransitDaysKPI - expected transit days (informational)."""
    
    @pytest.fixture
    def kpi(self):
        return AvgTransitDaysKPI()
    
    def test_name(self, kpi):
        assert kpi.name == "avg_transit_days"
    
    def test_calculate_known_route(self, kpi, sample_route_stats):
        """Known route returns its avg transit days."""
        order = {
            "origin_region": "South",
            "destination_region": "Midwest",
            "mode_of_shipment": "Flight",
        }
        context = {"route_stats": sample_route_stats}
        assert kpi.calculate(order, context) == 2.0
    
    def test_calculate_unknown_route(self, kpi, sample_route_stats):
        """Unknown route returns default (3.0 from KPI_CONFIG)."""
        order = {
            "origin_region": "Unknown",
            "destination_region": "Unknown",
            "mode_of_shipment": "Ship",
        }
        context = {"route_stats": sample_route_stats}
        assert kpi.calculate(order, context) == 3.0
    
    def test_never_breaches(self, kpi, default_thresholds):
        """Informational KPI - never breaches regardless of value."""
        result = kpi.is_breached(100.0, default_thresholds)
        assert result.breached is False
        assert result.threshold is None
        assert result.reason is None
        assert result.severity is None

"""
Unit tests for RiskEngine detection logic.

Tests the priority-based signal detection:
1. TICKET_RAISED (highest priority - reactive)
2. STUCK_AT_HUB (hub_hours breach)
3. PREDICTED_DELAY (transit_days + days_remaining breach)
4. ON_TRACK (default)
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from src.risk_detection.risk_engine import RiskEngine
from src.contracts.models import SignalType, Severity


class TestRiskEngineInit:
    """Tests for RiskEngine initialization."""
    
    def test_loads_route_stats(self):
        """Engine loads route stats on init."""
        engine = RiskEngine()
        assert isinstance(engine.route_stats, dict)
    
    def test_loads_thresholds(self):
        """Engine loads thresholds from config."""
        engine = RiskEngine()
        assert "hub_hours" in engine.thresholds
        assert "transit_days" in engine.thresholds
        assert "days_remaining_buffer" in engine.thresholds
    
    def test_loads_all_kpis(self):
        """Engine loads all 5 KPIs."""
        engine = RiskEngine()
        assert len(engine.kpis) == 5
        kpi_names = [kpi.name for kpi in engine.kpis]
        assert "hub_hours" in kpi_names
        assert "transit_days" in kpi_names
        assert "days_remaining" in kpi_names
        assert "route_failure_rate" in kpi_names
        assert "avg_transit_days" in kpi_names


class TestRiskEngineCalculateKPIs:
    """Tests for calculate_kpis method."""
    
    @pytest.fixture
    def engine(self):
        return RiskEngine()
    
    def test_returns_kpi_result(self, engine, happy_path_order, now):
        """Returns KPIResult with all fields."""
        result = engine.calculate_kpis(happy_path_order, now)
        assert result.order_id == 1001
        assert isinstance(result.kpis, dict)
        assert isinstance(result.thresholds, dict)
        assert isinstance(result.breaches, list)
    
    def test_calculates_all_kpis(self, engine, happy_path_order, now):
        """Calculates all 5 KPIs plus ticket_raised."""
        result = engine.calculate_kpis(happy_path_order, now)
        assert "hub_hours" in result.kpis
        assert "transit_days" in result.kpis
        assert "days_remaining" in result.kpis
        assert "route_failure_rate" in result.kpis
        assert "avg_transit_days" in result.kpis
        assert "ticket_raised" in result.kpis
    
    def test_happy_path_no_breaches(self, engine, happy_path_order, now):
        """Happy path order has no breaches."""
        result = engine.calculate_kpis(happy_path_order, now)
        assert len(result.breaches) == 0
    
    def test_stuck_at_hub_breach(self, engine, stuck_at_hub_order, now):
        """Stuck at hub order has hub_hours breach."""
        result = engine.calculate_kpis(stuck_at_hub_order, now)
        breach_names = [b.kpi_name for b in result.breaches]
        assert "hub_hours" in breach_names


class TestRiskEngineDetect:
    """Tests for detect method - priority-based signal detection."""
    
    @pytest.fixture
    def engine(self):
        return RiskEngine()
    
    def test_returns_risk_signal(self, engine, happy_path_order, now):
        """Returns RiskSignal with all fields."""
        signal = engine.detect(happy_path_order, now)
        assert signal.order_id == 1001
        assert isinstance(signal.signal_type, SignalType)
        assert isinstance(signal.severity, Severity)
        assert isinstance(signal.reason, str)
        assert isinstance(signal.kpis, dict)


class TestDetectPriority1TicketRaised:
    """Priority 1: TICKET_RAISED takes precedence over everything."""
    
    @pytest.fixture
    def engine(self):
        return RiskEngine()
    
    def test_ticket_raised_signal(self, engine, ticket_raised_order, now):
        """Ticket raised order returns TICKET_RAISED signal."""
        signal = engine.detect(ticket_raised_order, now)
        assert signal.signal_type == SignalType.TICKET_RAISED
        assert signal.severity == Severity.CRITICAL
        assert "ticket" in signal.reason.lower()
    
    def test_ticket_raised_overrides_hub_breach(self, engine, now):
        """TICKET_RAISED takes priority over STUCK_AT_HUB."""
        order = {
            "id": 9999,
            "destination_arrival_date": now - timedelta(hours=60),
            "actual_delivery_date": None,
            "ship_date": now - timedelta(days=5),
            "promised_date": now - timedelta(days=1),
            "ticket_raised": 1,
            "origin_region": "East",
            "destination_region": "West",
            "mode_of_shipment": "Road",
        }
        signal = engine.detect(order, now)
        assert signal.signal_type == SignalType.TICKET_RAISED


class TestDetectPriority2StuckAtHub:
    """Priority 2: STUCK_AT_HUB when hub_hours exceeds threshold."""
    
    @pytest.fixture
    def engine(self):
        return RiskEngine()
    
    def test_stuck_at_hub_signal(self, engine, stuck_at_hub_order, now):
        """Stuck at hub order returns STUCK_AT_HUB signal."""
        signal = engine.detect(stuck_at_hub_order, now)
        assert signal.signal_type == SignalType.STUCK_AT_HUB
        assert signal.severity == Severity.HIGH
        assert "hub" in signal.reason.lower() or "60" in signal.reason
    
    def test_hub_breach_without_ticket(self, engine, now):
        """Hub breach without ticket = STUCK_AT_HUB."""
        order = {
            "id": 9999,
            "destination_arrival_date": now - timedelta(hours=72),
            "actual_delivery_date": None,
            "ship_date": now - timedelta(days=4),
            "promised_date": now + timedelta(days=5),
            "ticket_raised": 0,
            "origin_region": "North",
            "destination_region": "South",
            "mode_of_shipment": "Flight",
        }
        signal = engine.detect(order, now)
        assert signal.signal_type == SignalType.STUCK_AT_HUB


class TestDetectPriority3PredictedDelay:
    """Priority 3: PREDICTED_DELAY when transit + deadline breaches."""
    
    @pytest.fixture
    def engine(self):
        return RiskEngine()
    
    def test_predicted_delay_signal(self, engine, predicted_delay_order, now):
        """Predicted delay order returns PREDICTED_DELAY signal."""
        signal = engine.detect(predicted_delay_order, now)
        assert signal.signal_type == SignalType.PREDICTED_DELAY
        assert signal.severity == Severity.HIGH
    
    def test_requires_both_breaches(self, engine, now):
        """PREDICTED_DELAY requires BOTH transit_days AND days_remaining breach."""
        order_transit_only = {
            "id": 9999,
            "ship_date": now - timedelta(days=5),
            "destination_arrival_date": None,
            "actual_delivery_date": None,
            "promised_date": now + timedelta(days=10),
            "ticket_raised": 0,
            "origin_region": "South",
            "destination_region": "Midwest",
            "mode_of_shipment": "Flight",
        }
        signal = engine.detect(order_transit_only, now)
        assert signal.signal_type == SignalType.ON_TRACK
    
    def test_requires_both_breaches_deadline_only(self, engine, now):
        """Only deadline breach without transit = ON_TRACK."""
        order_deadline_only = {
            "id": 9999,
            "ship_date": now - timedelta(days=1),
            "destination_arrival_date": None,
            "actual_delivery_date": None,
            "promised_date": now + timedelta(days=1),
            "ticket_raised": 0,
            "origin_region": "South",
            "destination_region": "Midwest",
            "mode_of_shipment": "Flight",
        }
        signal = engine.detect(order_deadline_only, now)
        assert signal.signal_type == SignalType.ON_TRACK


class TestDetectPriority4OnTrack:
    """Priority 4: ON_TRACK is the default when no issues detected."""
    
    @pytest.fixture
    def engine(self):
        return RiskEngine()
    
    def test_on_track_signal(self, engine, happy_path_order, now):
        """Happy path order returns ON_TRACK signal."""
        signal = engine.detect(happy_path_order, now)
        assert signal.signal_type == SignalType.ON_TRACK
        assert signal.severity == Severity.LOW
        assert "normally" in signal.reason.lower()
    
    def test_on_track_with_low_risk_route(self, engine, now):
        """Order on low-risk route = ON_TRACK."""
        order = {
            "id": 9999,
            "ship_date": now - timedelta(days=1),
            "destination_arrival_date": None,
            "actual_delivery_date": None,
            "promised_date": now + timedelta(days=7),
            "ticket_raised": 0,
            "origin_region": "South",
            "destination_region": "Midwest",
            "mode_of_shipment": "Flight",
        }
        signal = engine.detect(order, now)
        assert signal.signal_type == SignalType.ON_TRACK


class TestRiskEngineEdgeCases:
    """Edge cases and boundary conditions."""
    
    @pytest.fixture
    def engine(self):
        return RiskEngine()
    
    def test_missing_dates(self, engine, now):
        """Handles orders with missing date fields gracefully."""
        order = {
            "id": 9999,
            "ship_date": None,
            "destination_arrival_date": None,
            "actual_delivery_date": None,
            "promised_date": None,
            "ticket_raised": 0,
            "origin_region": None,
            "destination_region": None,
            "mode_of_shipment": None,
        }
        signal = engine.detect(order, now)
        assert signal.signal_type == SignalType.ON_TRACK
    
    def test_hub_hours_exactly_at_threshold(self, engine, now):
        """Hub hours exactly at 48 = no breach (> not >=)."""
        order = {
            "id": 9999,
            "destination_arrival_date": now - timedelta(hours=48),
            "actual_delivery_date": None,
            "ship_date": now - timedelta(days=3),
            "promised_date": now + timedelta(days=5),
            "ticket_raised": 0,
            "origin_region": "North",
            "destination_region": "South",
            "mode_of_shipment": "Flight",
        }
        signal = engine.detect(order, now)
        assert signal.signal_type == SignalType.ON_TRACK
    
    def test_hub_hours_just_over_threshold(self, engine, now):
        """Hub hours at 49 = breach."""
        order = {
            "id": 9999,
            "destination_arrival_date": now - timedelta(hours=49),
            "actual_delivery_date": None,
            "ship_date": now - timedelta(days=3),
            "promised_date": now + timedelta(days=5),
            "ticket_raised": 0,
            "origin_region": "North",
            "destination_region": "South",
            "mode_of_shipment": "Flight",
        }
        signal = engine.detect(order, now)
        assert signal.signal_type == SignalType.STUCK_AT_HUB
    
    def test_kpis_included_in_signal(self, engine, happy_path_order, now):
        """Signal includes all calculated KPI values."""
        signal = engine.detect(happy_path_order, now)
        assert "hub_hours" in signal.kpis
        assert "transit_days" in signal.kpis
        assert "days_remaining" in signal.kpis
        assert "ticket_raised" in signal.kpis

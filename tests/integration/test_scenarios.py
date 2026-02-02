"""
Integration tests for the 4 demo scenarios.

Tests the complete flow from order → KPI calculation → risk detection.
Each scenario maps to a specific signal type:
- Scenario 1001: Happy Path → ON_TRACK
- Scenario 1002: Predicted Delay → PREDICTED_DELAY  
- Scenario 1003: Stuck at Hub → STUCK_AT_HUB
- Scenario 1004: Ticket Raised → TICKET_RAISED
"""
import pytest
from datetime import datetime, timedelta

from src.risk_detection.risk_engine import RiskEngine
from src.contracts.models import SignalType, Severity
from src.bootstrap import generate_demo_orders, SCENARIOS, DEMO_ORDER_IDS


class TestScenario1001HappyPath:
    """
    Scenario 1001: Happy Path
    
    Order shipped 1 day ago with 10 days until promised date.
    Expected: ON_TRACK signal with LOW severity.
    """
    
    @pytest.fixture
    def engine(self):
        return RiskEngine()
    
    @pytest.fixture
    def order(self):
        orders = generate_demo_orders()
        return next(o for o in orders if o["id"] == 1001)
    
    def test_scenario_metadata(self):
        """Verify scenario definition."""
        assert 1001 in SCENARIOS
        assert SCENARIOS[1001]["name"] == "Happy Path"
        assert SCENARIOS[1001]["expected_signal"] == "ON_TRACK"
    
    def test_order_structure(self, order):
        """Order has expected structure."""
        assert order["id"] == 1001
        assert order["ticket_raised"] == 0
        assert order["destination_arrival_date"] is None
    
    def test_kpi_calculation(self, engine, order):
        """KPIs show healthy values."""
        result = engine.calculate_kpis(order)
        
        assert result.kpis["hub_hours"] == 0.0
        assert result.kpis["transit_hours"] >= 0
        assert result.kpis["hours_remaining"] > 48  # More than 2 days
        assert result.kpis["ticket_raised"] == 0
        assert len(result.breaches) == 0
    
    def test_detection_result(self, engine, order):
        """Detects ON_TRACK signal."""
        signal = engine.detect(order)
        
        assert signal.order_id == 1001
        assert signal.signal_type == SignalType.ON_TRACK
        assert signal.severity == Severity.LOW
        assert "normally" in signal.reason.lower()


class TestScenario1002PredictedDelay:
    """
    Scenario 1002: Predicted Delay
    
    Order is overdue (hours_remaining < 0), triggering PredictedDelayKPI.
    Expected: PREDICTED_DELAY signal with HIGH severity.
    """
    
    @pytest.fixture
    def engine(self):
        return RiskEngine()
    
    @pytest.fixture
    def order(self):
        orders = generate_demo_orders()
        return next(o for o in orders if o["id"] == 1002)
    
    def test_scenario_metadata(self):
        """Verify scenario definition."""
        assert 1002 in SCENARIOS
        assert SCENARIOS[1002]["name"] == "Predicted Delay"
        assert SCENARIOS[1002]["expected_signal"] == "PREDICTED_DELAY"
    
    def test_order_structure(self, order):
        """Order has expected structure for delay prediction."""
        assert order["id"] == 1002
        assert order["ticket_raised"] == 0
        assert order["destination_arrival_date"] is None
        assert order["ship_date"] is not None
    
    def test_kpi_calculation(self, engine, order):
        """KPIs show delay indicators."""
        result = engine.calculate_kpis(order)
        
        assert result.kpis["hours_remaining"] < 0  # Overdue
        assert result.kpis["hub_hours"] == 0.0
        
        breach_names = [b.kpi_name for b in result.breaches]
        assert "hours_remaining" in breach_names
        assert "predicted_delay" in breach_names
    
    def test_detection_result(self, engine, order):
        """Detects PREDICTED_DELAY signal."""
        signal = engine.detect(order)
        
        assert signal.order_id == 1002
        assert signal.signal_type == SignalType.PREDICTED_DELAY
        assert signal.severity == Severity.HIGH


class TestScenario1003StuckAtHub:
    """
    Scenario 1003: Stuck at Hub
    
    Order arrived at destination hub 60 hours ago but not delivered.
    Expected: STUCK_AT_HUB signal with HIGH severity.
    """
    
    @pytest.fixture
    def engine(self):
        return RiskEngine()
    
    @pytest.fixture
    def order(self):
        orders = generate_demo_orders()
        return next(o for o in orders if o["id"] == 1003)
    
    def test_scenario_metadata(self):
        """Verify scenario definition."""
        assert 1003 in SCENARIOS
        assert SCENARIOS[1003]["name"] == "Stuck at Hub"
        assert SCENARIOS[1003]["expected_signal"] == "STUCK_AT_HUB"
    
    def test_order_structure(self, order):
        """Order has expected structure for hub delay."""
        assert order["id"] == 1003
        assert order["ticket_raised"] == 0
        assert order["destination_arrival_date"] is not None
        assert order["actual_delivery_date"] is None
    
    def test_kpi_calculation(self, engine, order):
        """KPIs show hub delay."""
        result = engine.calculate_kpis(order)
        
        assert result.kpis["hub_hours"] > 24  # Exceeds 24h threshold
        assert result.kpis["transit_hours"] == 0.0
        
        breach_names = [b.kpi_name for b in result.breaches]
        assert "hub_hours" in breach_names
    
    def test_detection_result(self, engine, order):
        """Detects STUCK_AT_HUB signal."""
        signal = engine.detect(order)
        
        assert signal.order_id == 1003
        assert signal.signal_type == SignalType.STUCK_AT_HUB
        assert signal.severity == Severity.HIGH


class TestScenario1004TicketRaised:
    """
    Scenario 1004: Ticket Raised
    
    Customer raised a support ticket (reactive scenario).
    Expected: TICKET_RAISED signal with CRITICAL severity.
    """
    
    @pytest.fixture
    def engine(self):
        return RiskEngine()
    
    @pytest.fixture
    def order(self):
        orders = generate_demo_orders()
        return next(o for o in orders if o["id"] == 1004)
    
    def test_scenario_metadata(self):
        """Verify scenario definition."""
        assert 1004 in SCENARIOS
        assert SCENARIOS[1004]["name"] == "Ticket Raised"
        assert SCENARIOS[1004]["expected_signal"] == "TICKET_RAISED"
    
    def test_order_structure(self, order):
        """Order has expected structure for ticket scenario."""
        assert order["id"] == 1004
        assert order["ticket_raised"] == 1
        assert order["customer_care_calls"] >= 3
    
    def test_kpi_calculation(self, engine, order):
        """KPIs capture ticket flag."""
        result = engine.calculate_kpis(order)
        
        assert result.kpis["ticket_raised"] == 1
        assert result.kpis["hours_remaining"] < 0  # Overdue
    
    def test_detection_result(self, engine, order):
        """Detects TICKET_RAISED signal (highest priority)."""
        signal = engine.detect(order)
        
        assert signal.order_id == 1004
        assert signal.signal_type == SignalType.TICKET_RAISED
        assert signal.severity == Severity.CRITICAL
        assert "ticket" in signal.reason.lower()


class TestAllScenariosMapping:
    """Cross-scenario tests to verify complete coverage."""
    
    @pytest.fixture
    def engine(self):
        return RiskEngine()
    
    def test_all_demo_order_ids_exist(self):
        """All 4 demo order IDs are defined."""
        assert DEMO_ORDER_IDS == [1001, 1002, 1003, 1004]
    
    def test_all_scenarios_have_metadata(self):
        """All scenarios have required metadata."""
        for order_id in DEMO_ORDER_IDS:
            assert order_id in SCENARIOS
            scenario = SCENARIOS[order_id]
            assert "name" in scenario
            assert "description" in scenario
            assert "expected_signal" in scenario
    
    def test_all_signal_types_covered(self, engine):
        """All 4 signal types are covered by demo scenarios."""
        orders = generate_demo_orders()
        signals = {engine.detect(o).signal_type for o in orders}
        
        assert SignalType.ON_TRACK in signals
        assert SignalType.PREDICTED_DELAY in signals
        assert SignalType.STUCK_AT_HUB in signals
        assert SignalType.TICKET_RAISED in signals
    
    def test_detection_matches_expected(self, engine):
        """Each scenario detects its expected signal type."""
        orders = generate_demo_orders()
        
        for order in orders:
            expected_signal = SCENARIOS[order["id"]]["expected_signal"]
            actual_signal = engine.detect(order).signal_type.value
            
            assert actual_signal == expected_signal, (
                f"Order {order['id']}: expected {expected_signal}, got {actual_signal}"
            )


class TestScenarioPriorityOrdering:
    """Tests that priority ordering is respected across scenarios."""
    
    @pytest.fixture
    def engine(self):
        return RiskEngine()
    
    def test_ticket_overrides_all(self, engine):
        """TICKET_RAISED should override even when other conditions are met."""
        now = datetime.now()
        order = {
            "id": 9999,
            "destination_arrival_date": now - timedelta(hours=100),
            "actual_delivery_date": None,
            "ship_date": now - timedelta(days=10),
            "promised_date": now - timedelta(days=5),
            "ticket_raised": 1,
            "origin_region": "East",
            "destination_region": "West",
            "mode_of_shipment": "Road",
        }
        signal = engine.detect(order, now)
        assert signal.signal_type == SignalType.TICKET_RAISED
    
    def test_hub_overrides_delay(self, engine):
        """STUCK_AT_HUB should override PREDICTED_DELAY."""
        now = datetime.now()
        order = {
            "id": 9999,
            "destination_arrival_date": now - timedelta(hours=60),
            "actual_delivery_date": None,
            "ship_date": now - timedelta(days=5),
            "promised_date": now - timedelta(days=1),
            "ticket_raised": 0,
            "origin_region": "North",
            "destination_region": "South",
            "mode_of_shipment": "Flight",
        }
        signal = engine.detect(order, now)
        assert signal.signal_type == SignalType.STUCK_AT_HUB

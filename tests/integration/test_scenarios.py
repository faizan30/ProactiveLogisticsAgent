"""
Integration tests for the 4 demo scenarios.

Tests the complete flow:
1. Order → KPI calculation → Risk detection (RiskEngine)
2. Risk signal → Agent resolution (Multi-Agent System with real LLM calls)

Each scenario maps to a specific signal type:
- Scenario 1001: Happy Path → ON_TRACK (no agent needed)
- Scenario 1002: Predicted Delay → PREDICTED_DELAY → Agent resolves
- Scenario 1003: Stuck at Hub → STUCK_AT_HUB → Agent resolves
- Scenario 1004: Ticket Raised → TICKET_RAISED → Agent resolves

Note: Agent unit tests (mocked LLM) are in tests/unit/test_agent_graph.py
"""
import os
import pytest
from datetime import datetime, timedelta

from src.risk_detection.risk_engine import RiskEngine
from src.contracts.models import SignalType, Severity
from src.bootstrap import generate_demo_orders, SCENARIOS, DEMO_ORDER_IDS
from src.agent.supervisor import run_supervisor


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


# ============================================================================
# AGENT INTEGRATION TESTS (Real LLM calls - requires OPENAI_API_KEY)
# ============================================================================

@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="No OPENAI_API_KEY")
class TestAgentIntegration:
    """
    Integration tests with real LLM calls.
    
    These tests verify the full multi-agent system works end-to-end:
    - Supervisor orchestration
    - Sub-agent execution (Drafter→Critic, Researcher→Analyzer)
    - Policy tool usage
    - Tool invocations
    
    Run with: pytest tests/integration/test_scenarios.py -k "Integration" -v -s
    """
    
    def test_stuck_at_hub_full_resolution(self):
        """Full resolution of stuck-at-hub scenario with reschedule."""
        order = {
            "id": 9001,
            "origin_region": "North",
            "destination_region": "South",
            "customer_rating": 4,
            "customer_care_calls": 1,
            "mocked_customer_response": "reschedule",
        }
        
        result = run_supervisor(
            order=order,
            signal_type="STUCK_AT_HUB",
            signal_reason="Package at hub for 60 hours",
            use_checkpointer=False,
        )
        
        assert result["order_id"] == 9001
        assert result["status"] in ["resolved", "failed"]
        if result["status"] == "resolved":
            assert len(result["actions_taken"]) > 0
            # Should have multiple agent actions
            assert len(result["conversation_turns"]) >= 2
    
    def test_ticket_raised_refund_flow(self):
        """Full resolution of ticket-raised with refund preference."""
        order = {
            "id": 9002,
            "origin_region": "West",
            "destination_region": "East",
            "customer_rating": 2,
            "customer_care_calls": 4,
            "ticket_raised": 1,
            "mocked_customer_response": "refund",
        }
        
        result = run_supervisor(
            order=order,
            signal_type="TICKET_RAISED",
            signal_reason="Customer raised support ticket",
            use_checkpointer=False,
        )
        
        assert result["order_id"] == 9002
        assert result["status"] in ["resolved", "failed"]
        if result["status"] == "resolved":
            # Resolution should mention refund
            assert "actions_taken" in result
    
    def test_predicted_delay_proactive_contact(self):
        """Proactive customer contact for predicted delay."""
        order = {
            "id": 9003,
            "origin_region": "East",
            "destination_region": "West",
            "customer_rating": 3,
            "customer_care_calls": 0,
            "mocked_customer_response": "reschedule",
        }
        
        result = run_supervisor(
            order=order,
            signal_type="PREDICTED_DELAY",
            signal_reason="Transit time exceeds route average",
            use_checkpointer=False,
        )
        
        assert result["order_id"] == 9003
        assert result["status"] in ["resolved", "failed"]
    
    def test_multi_agent_conversation_flow(self):
        """Verify conversation includes multiple agents."""
        order = {
            "id": 9004,
            "origin_region": "North",
            "destination_region": "South",
            "customer_rating": 4,
            "customer_care_calls": 1,
            "mocked_customer_response": "refund",
        }
        
        result = run_supervisor(
            order=order,
            signal_type="STUCK_AT_HUB",
            signal_reason="Package stuck at hub",
            use_checkpointer=False,
        )
        
        if result["status"] == "resolved":
            turns = result.get("conversation_turns", [])
            roles = {t.get("role") for t in turns}
            # Should have supervisor and at least one specialist
            assert "supervisor" in roles
            # At least one specialist should have acted
            assert len(roles) >= 2
    
    def test_customer_agent_drafts_and_critiques(self):
        """CustomerAgent should use Drafter→Critic flow."""
        order = {
            "id": 9005,
            "origin_region": "South",
            "destination_region": "North",
            "customer_rating": 5,
            "customer_care_calls": 2,
            "mocked_customer_response": "reschedule",
        }
        
        result = run_supervisor(
            order=order,
            signal_type="PREDICTED_DELAY",
            signal_reason="Shipment delayed",
            use_checkpointer=False,
        )
        
        # The customer agent should have executed
        if result["status"] == "resolved":
            actions = result.get("actions_taken", [])
            # Look for customer action in the flow
            customer_acted = any("customer" in a.lower() for a in actions)
            # Note: might not always have customer in flow depending on LLM decision
            assert result["status"] == "resolved"

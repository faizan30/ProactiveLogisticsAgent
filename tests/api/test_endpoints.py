"""
API endpoint tests using FastAPI TestClient.

Tests all 6 demo flow endpoints:
1. GET  /              - Health check
2. POST /bootstrap     - Seed demo data
3. GET  /orders/{id}   - View order
4. GET  /kpis/{id}     - Calculate KPIs
5. POST /detect-deviation/{id} - Detect risk
6. POST /trigger-agent/{id}    - Trigger agent (placeholder)
7. GET  /view-response/{id}    - View conversation
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
import os

# Set test environment before importing app
os.environ["POSTGRES_HOST"] = "localhost"

from src.contracts.models import SignalType, Severity


@pytest.fixture(scope="module")
def mock_db():
    """Mock PostgresManager for tests."""
    db = MagicMock()
    
    now = datetime.now()
    mock_orders = {
        1001: {
            "id": 1001,
            "order_date": now - timedelta(days=2),
            "promised_date": now + timedelta(days=10),
            "ship_date": now - timedelta(days=1),
            "destination_arrival_date": None,
            "actual_delivery_date": None,
            "origin_region": "South",
            "destination_region": "Midwest",
            "mode_of_shipment": "Flight",
            "customer_rating": 5,
            "customer_care_calls": 0,
            "ticket_raised": 0,
            "product_cost": 150.0,
        },
        1002: {
            "id": 1002,
            "order_date": now - timedelta(days=12),
            "promised_date": now + timedelta(hours=12),  # < 48h = deadline pressure
            "ship_date": now - timedelta(days=10),       # 240h in transit (exceeds 192h threshold)
            "destination_arrival_date": None,
            "actual_delivery_date": None,
            "origin_region": "West",
            "destination_region": "East",
            "mode_of_shipment": "Road",
            "customer_rating": 3,
            "customer_care_calls": 2,
            "ticket_raised": 0,
            "product_cost": 200.0,
        },
        1003: {
            "id": 1003,
            "order_date": now - timedelta(days=5),
            "promised_date": now,
            "ship_date": now - timedelta(days=3),
            "destination_arrival_date": now - timedelta(hours=60),
            "actual_delivery_date": None,
            "origin_region": "North",
            "destination_region": "South",
            "mode_of_shipment": "Flight",
            "customer_rating": 4,
            "customer_care_calls": 1,
            "ticket_raised": 0,
            "product_cost": 175.0,
        },
        1004: {
            "id": 1004,
            "order_date": now - timedelta(days=7),
            "promised_date": now - timedelta(days=1),
            "ship_date": now - timedelta(days=5),
            "destination_arrival_date": now - timedelta(days=2),
            "actual_delivery_date": None,
            "origin_region": "East",
            "destination_region": "West",
            "mode_of_shipment": "Road",
            "customer_rating": 2,
            "customer_care_calls": 4,
            "ticket_raised": 1,
            "product_cost": 250.0,
        },
    }
    
    db.get_order = lambda oid: mock_orders.get(oid)
    db.get_all_orders = lambda: list(mock_orders.values())
    db.get_conversation = lambda oid: None
    db.upsert_order = MagicMock()
    db.clear_all_orders = MagicMock()
    db.clear_conversations = MagicMock()
    
    return db


@pytest.fixture(scope="module")
def client(mock_db):
    """Create test client with mocked dependencies."""
    from src.risk_detection.risk_engine import RiskEngine
    
    # Patch PostgresManager to avoid DB connection during lifespan
    with patch("src.api.main.PostgresManager") as MockPM:
        MockPM.return_value = mock_db
        
        # Import app after patching
        from src.api.main import app, app_state
        
        app_state.db = mock_db
        app_state.risk_engine = RiskEngine()
        
        with TestClient(app) as test_client:
            yield test_client


class TestHealthEndpoint:
    """Tests for GET / health check."""
    
    def test_health_returns_200(self, client):
        response = client.get("/")
        assert response.status_code == 200
    
    def test_health_returns_status(self, client):
        response = client.get("/")
        data = response.json()
        assert data["status"] == "online"
        assert "version" in data


class TestBootstrapEndpoint:
    """Tests for POST /bootstrap."""
    
    def test_bootstrap_returns_200(self, client, mock_db):
        mock_db.upsert_order = MagicMock()
        mock_db.clear_all_orders = MagicMock()
        mock_db.clear_conversations = MagicMock()
        
        response = client.post("/bootstrap")
        assert response.status_code == 200
    
    def test_bootstrap_returns_order_ids(self, client):
        response = client.post("/bootstrap")
        data = response.json()
        assert "order_ids" in data
        assert data["order_ids"] == [1001, 1002, 1003, 1004]
    
    def test_bootstrap_returns_scenarios(self, client):
        response = client.post("/bootstrap")
        data = response.json()
        assert "scenarios" in data
        assert "1001" in data["scenarios"] or 1001 in data["scenarios"]


class TestOrderEndpoint:
    """Tests for GET /orders/{id}."""
    
    def test_get_order_1001(self, client):
        response = client.get("/orders/1001")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1001
    
    def test_get_order_returns_all_fields(self, client):
        response = client.get("/orders/1001")
        data = response.json()
        
        required_fields = [
            "id", "origin_region", "destination_region",
            "mode_of_shipment", "ticket_raised"
        ]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
    
    def test_get_order_includes_scenario_info(self, client):
        response = client.get("/orders/1001")
        data = response.json()
        assert "scenario" in data
        assert data["scenario"]["name"] == "Happy Path"
    
    def test_get_order_not_found(self, client):
        response = client.get("/orders/9999")
        assert response.status_code == 404
    
    def test_get_order_invalid_id(self, client):
        response = client.get("/orders/0")
        assert response.status_code == 422


class TestListOrdersEndpoint:
    """Tests for GET /orders."""
    
    def test_list_orders_returns_200(self, client):
        response = client.get("/orders")
        assert response.status_code == 200
    
    def test_list_orders_returns_array(self, client):
        response = client.get("/orders")
        data = response.json()
        assert "orders" in data
        assert isinstance(data["orders"], list)
    
    def test_list_orders_returns_count(self, client):
        response = client.get("/orders")
        data = response.json()
        assert "count" in data
        assert data["count"] == len(data["orders"])


class TestKPIsEndpoint:
    """Tests for GET /kpis/{id}."""
    
    def test_get_kpis_returns_200(self, client):
        response = client.get("/kpis/1001")
        assert response.status_code == 200
    
    def test_get_kpis_returns_all_kpis(self, client):
        response = client.get("/kpis/1001")
        data = response.json()
        
        assert "kpis" in data
        kpis = data["kpis"]
        
        expected_kpis = [
            "hub_hours", "transit_hours", "hours_remaining",
            "route_failure_rate", "predicted_delay", "ticket_raised"
        ]
        for kpi in expected_kpis:
            assert kpi in kpis, f"Missing KPI: {kpi}"
    
    def test_get_kpis_returns_thresholds(self, client):
        response = client.get("/kpis/1001")
        data = response.json()
        
        assert "thresholds" in data
        thresholds = data["thresholds"]
        assert "hub_hours" in thresholds
        assert "transit_buffer_hours" in thresholds
    
    def test_get_kpis_returns_breaches(self, client):
        response = client.get("/kpis/1001")
        data = response.json()
        assert "breaches" in data
        assert isinstance(data["breaches"], list)
    
    def test_get_kpis_not_found(self, client):
        response = client.get("/kpis/9999")
        assert response.status_code == 404


class TestDetectDeviationEndpoint:
    """Tests for POST /detect-deviation/{id}."""
    
    def test_detect_returns_200(self, client):
        response = client.post("/detect-deviation/1001")
        assert response.status_code == 200
    
    def test_detect_returns_signal_type(self, client):
        response = client.post("/detect-deviation/1001")
        data = response.json()
        
        assert "signal_type" in data
        assert data["signal_type"] in ["ON_TRACK", "PREDICTED_DELAY", "STUCK_AT_HUB", "TICKET_RAISED"]
    
    def test_detect_returns_severity(self, client):
        response = client.post("/detect-deviation/1001")
        data = response.json()
        
        assert "severity" in data
        assert data["severity"] in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    
    def test_detect_returns_reason(self, client):
        response = client.post("/detect-deviation/1001")
        data = response.json()
        assert "reason" in data
        assert isinstance(data["reason"], str)
    
    def test_detect_returns_has_risk(self, client):
        response = client.post("/detect-deviation/1001")
        data = response.json()
        assert "has_risk" in data
        assert isinstance(data["has_risk"], bool)
    
    def test_detect_1001_on_track(self, client):
        """Scenario 1001 should be ON_TRACK."""
        response = client.post("/detect-deviation/1001")
        data = response.json()
        assert data["signal_type"] == "ON_TRACK"
        assert data["has_risk"] is False
    
    def test_detect_1002_predicted_delay(self, client):
        """Scenario 1002 should be PREDICTED_DELAY."""
        response = client.post("/detect-deviation/1002")
        data = response.json()
        assert data["signal_type"] == "PREDICTED_DELAY"
        assert data["has_risk"] is True
    
    def test_detect_1003_stuck_at_hub(self, client):
        """Scenario 1003 should be STUCK_AT_HUB."""
        response = client.post("/detect-deviation/1003")
        data = response.json()
        assert data["signal_type"] == "STUCK_AT_HUB"
        assert data["has_risk"] is True
    
    def test_detect_1004_ticket_raised(self, client):
        """Scenario 1004 should be TICKET_RAISED."""
        response = client.post("/detect-deviation/1004")
        data = response.json()
        assert data["signal_type"] == "TICKET_RAISED"
        assert data["has_risk"] is True
    
    def test_detect_not_found(self, client):
        response = client.post("/detect-deviation/9999")
        assert response.status_code == 404


class TestTriggerAgentEndpoint:
    """Tests for POST /trigger-agent/{id}."""
    
    def test_trigger_returns_200(self, client):
        response = client.post("/trigger-agent/1001")
        assert response.status_code == 200
    
    def test_trigger_returns_status(self, client):
        response = client.post("/trigger-agent/1001")
        data = response.json()
        assert "status" in data
    
    def test_trigger_1001_no_action(self, client):
        """ON_TRACK order should return no_action status."""
        response = client.post("/trigger-agent/1001")
        data = response.json()
        assert data["status"] == "no_action"
        assert data["signal_type"] == "ON_TRACK"
    
    def test_trigger_not_found(self, client):
        response = client.post("/trigger-agent/9999")
        assert response.status_code == 404


class TestViewResponseEndpoint:
    """Tests for GET /view-response/{id}."""
    
    def test_view_response_returns_200(self, client):
        response = client.get("/view-response/1001")
        assert response.status_code == 200
    
    def test_view_response_returns_order_id(self, client):
        response = client.get("/view-response/1001")
        data = response.json()
        assert data["order_id"] == 1001
    
    def test_view_response_returns_conversation(self, client):
        response = client.get("/view-response/1001")
        data = response.json()
        assert "conversation" in data
    
    def test_view_response_not_found(self, client):
        response = client.get("/view-response/9999")
        assert response.status_code == 404


class TestAPIFlow:
    """Integration tests for the complete API flow."""
    
    def test_full_flow_happy_path(self, client):
        """Test complete flow for scenario 1001."""
        response = client.get("/orders/1001")
        assert response.status_code == 200
        
        response = client.get("/kpis/1001")
        assert response.status_code == 200
        
        response = client.post("/detect-deviation/1001")
        assert response.status_code == 200
        assert response.json()["signal_type"] == "ON_TRACK"
        
        response = client.post("/trigger-agent/1001")
        assert response.status_code == 200
        assert response.json()["status"] == "no_action"
    
    def test_full_flow_risk_detected(self, client):
        """Test complete flow for scenario 1004 (ticket raised) - detection only.
        
        Note: Full agent execution requires OpenAI API key, so we only test detection.
        """
        response = client.get("/orders/1004")
        assert response.status_code == 200
        
        response = client.get("/kpis/1004")
        assert response.status_code == 200
        kpis = response.json()["kpis"]
        assert kpis["ticket_raised"] == 1
        
        response = client.post("/detect-deviation/1004")
        assert response.status_code == 200
        assert response.json()["signal_type"] == "TICKET_RAISED"
        assert response.json()["severity"] == "CRITICAL"
        
        # Agent execution would require OpenAI API key
        # Tested via integration tests with real API

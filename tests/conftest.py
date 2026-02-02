"""
Pytest fixtures for Proactive Logistics Agent tests.
"""
import pytest
from datetime import datetime, timedelta
from typing import Dict, Any


# ==================== TIME FIXTURES ====================

@pytest.fixture
def now():
    """Fixed 'now' timestamp for deterministic tests."""
    return datetime(2026, 2, 2, 10, 0, 0)


# ==================== ORDER FIXTURES ====================

@pytest.fixture
def base_order() -> Dict[str, Any]:
    """Base order template - override fields as needed."""
    return {
        "id": 9999,
        "order_date": None,
        "promised_date": None,
        "ship_date": None,
        "destination_arrival_date": None,
        "actual_delivery_date": None,
        "origin_region": "South",
        "destination_region": "Midwest",
        "mode_of_shipment": "Flight",
        "customer_rating": 5,
        "customer_care_calls": 0,
        "ticket_raised": 0,
        "product_cost": 100.0,
    }


@pytest.fixture
def happy_path_order(now) -> Dict[str, Any]:
    """Scenario 1001: On track, no issues."""
    return {
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
    }


@pytest.fixture
def predicted_delay_order(now) -> Dict[str, Any]:
    """Scenario 1002: In transit too long + near deadline."""
    return {
        "id": 1002,
        "order_date": now - timedelta(days=6),
        "promised_date": now + timedelta(days=1),
        "ship_date": now - timedelta(days=4),
        "destination_arrival_date": None,
        "actual_delivery_date": None,
        "origin_region": "West",
        "destination_region": "East",
        "mode_of_shipment": "Road",
        "customer_rating": 3,
        "customer_care_calls": 2,
        "ticket_raised": 0,
        "product_cost": 200.0,
    }


@pytest.fixture
def stuck_at_hub_order(now) -> Dict[str, Any]:
    """Scenario 1003: At hub for 60+ hours."""
    return {
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
    }


@pytest.fixture
def ticket_raised_order(now) -> Dict[str, Any]:
    """Scenario 1004: Customer raised a ticket."""
    return {
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
    }


# ==================== ROUTE STATS FIXTURE ====================

@pytest.fixture
def sample_route_stats() -> Dict[str, Any]:
    """Sample route statistics for testing."""
    return {
        "South_Midwest_Flight": {"failure_rate": 0.1, "avg_transit_days": 2.0, "sample_size": 100},
        "West_East_Road": {"failure_rate": 0.6, "avg_transit_days": 5.0, "sample_size": 50},
        "North_South_Flight": {"failure_rate": 0.2, "avg_transit_days": 3.0, "sample_size": 75},
        "East_West_Road": {"failure_rate": 0.55, "avg_transit_days": 4.5, "sample_size": 60},
    }


# ==================== THRESHOLDS FIXTURE ====================

@pytest.fixture
def default_thresholds() -> Dict[str, float]:
    """Default threshold values matching config.py."""
    return {
        "hub_hours": 48,
        "transit_days": 3,
        "days_remaining_buffer": 2,
        "route_failure_rate": 0.5,
    }

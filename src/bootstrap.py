"""
Bootstrap - Seeds 4 demo orders for the scenarios.

Scenarios:
1. Happy Path (1001) - On track, no agent needed
2. Predicted Delay (1002) - Agent offers refund, customer accepts
3. Stuck at Hub (1003) - Agent contacts hub, then customer reschedules
4. Ticket Raised (1004) - Agent sends empathy + refund
"""
from datetime import datetime, timedelta
from typing import List, Dict

from src.storage_manager.postgres_manager import PostgresManager


DEMO_ORDER_IDS = [1001, 1002, 1003, 1004]

SCENARIOS = {
    1001: {
        "name": "Happy Path",
        "description": "Shipment on track, no intervention needed",
        "expected_signal": "ON_TRACK",
    },
    1002: {
        "name": "Predicted Delay",
        "description": "In transit too long, agent offers refund",
        "expected_signal": "PREDICTED_DELAY",
    },
    1003: {
        "name": "Stuck at Hub",
        "description": "At destination hub 60h, agent contacts hub then customer reschedules",
        "expected_signal": "STUCK_AT_HUB",
    },
    1004: {
        "name": "Ticket Raised",
        "description": "Customer complained, agent sends empathy + refund",
        "expected_signal": "TICKET_RAISED",
    },
}


def generate_demo_orders() -> List[Dict]:
    """Generate 4 demo orders with dates relative to now."""
    now = datetime.now()
    
    return [
        # 1001: Happy Path - shipped yesterday, 10 days buffer
        {
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
            "mocked_customer_response": None,  # No agent interaction needed
        },
        # 1002: Predicted Delay - overdue order triggers PredictedDelayKPI
        {
            "id": 1002,
            "order_date": now - timedelta(days=6),
            "promised_date": now - timedelta(hours=12),  # Overdue by 12 hours
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
            "mocked_customer_response": "refund",  # Customer will accept refund
        },
        # 1003: Stuck at Hub - arrived 60h ago, not delivered
        {
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
            "mocked_customer_response": "reschedule",  # Customer will pick reschedule
        },
        # 1004: Ticket Raised - already late, customer complained
        {
            "id": 1004,
            "order_date": now - timedelta(days=7),
            "promised_date": now - timedelta(days=1),  # Past due!
            "ship_date": now - timedelta(days=5),
            "destination_arrival_date": now - timedelta(days=2),
            "actual_delivery_date": None,
            "origin_region": "East",
            "destination_region": "West",
            "mode_of_shipment": "Road",
            "customer_rating": 2,
            "customer_care_calls": 4,
            "ticket_raised": 1,  # Customer raised ticket
            "product_cost": 250.0,
            "mocked_customer_response": "refund",  # Customer will accept refund
        },
    ]


def bootstrap(db: PostgresManager) -> Dict:
    """Seed demo orders into database."""
    try:
        # Clear existing data
        db.clear_conversations()
        db.clear_all_orders()
        
        # Insert demo orders
        orders = generate_demo_orders()
        for order in orders:
            db.upsert_order(order)
        
        return {
            "status": "success",
            "message": f"Seeded {len(orders)} demo orders",
            "order_ids": DEMO_ORDER_IDS,
            "scenarios": SCENARIOS,
            "bootstrap_time": datetime.now().isoformat(),
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

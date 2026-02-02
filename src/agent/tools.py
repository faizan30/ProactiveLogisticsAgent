"""
Mocked Tools for Specialist Agents

All tools return mocked responses for demo purposes.
In production, these would integrate with real systems.
"""
import logging
from datetime import datetime, timedelta
from typing import Annotated

from langchain_core.tools import tool

logger = logging.getLogger("agent.tools")


# ==================== OPERATIONS TOOLS ====================

@tool
def contact_hub(order_id: Annotated[int, "The order ID to check"]) -> str:
    """Contact the destination hub to check package status."""
    logger.info(f"[TOOL] contact_hub called for order {order_id}")
    # Mocked response - in production would call hub API
    return f"Hub response: Package for order #{order_id} is located and ready for dispatch. No issues found."


@tool
def check_shipment_status(order_id: Annotated[int, "The order ID to check"]) -> str:
    """Check current shipment tracking status."""
    logger.info(f"[TOOL] check_shipment_status called for order {order_id}")
    # Mocked response
    return f"Shipment #{order_id}: Currently at destination hub. Last scan: 2 hours ago."


# ==================== CUSTOMER TOOLS ====================

@tool
def send_message(
    order_id: Annotated[int, "The order ID"],
    message: Annotated[str, "Message to send to customer"]
) -> str:
    """Send a message to the customer."""
    logger.info(f"[TOOL] send_message to customer for order {order_id}: {message[:50]}...")
    # In production would send email/SMS
    return f"Message sent to customer for order #{order_id}"


@tool
def get_customer_response(
    order_id: Annotated[int, "The order ID"],
    mocked_response: Annotated[str, "The mocked customer response from order data"]
) -> str:
    """Get customer's response to our message (mocked for demo)."""
    logger.info(f"[TOOL] get_customer_response for order {order_id}: {mocked_response}")
    # Returns the mocked response from order data
    if mocked_response == "refund":
        return "Customer response: I would like a refund please."
    elif mocked_response == "reschedule":
        return "Customer response: Please reschedule my delivery for tomorrow."
    else:
        return "Customer response: No action needed, thank you for the update."


# ==================== RESOLUTION TOOLS ====================

@tool
def process_refund(
    order_id: Annotated[int, "The order ID"],
    refund_percent: Annotated[int, "Refund percentage (1-100)"]
) -> str:
    """Process a refund for the customer."""
    logger.info(f"[TOOL] process_refund for order {order_id}: {refund_percent}%")
    # Mocked - in production would call payment system
    return f"Refund processed: {refund_percent}% refund issued for order #{order_id}. Confirmation sent to customer."


@tool
def reschedule_delivery(
    order_id: Annotated[int, "The order ID"],
    new_date: Annotated[str, "New delivery date (or 'tomorrow')"]
) -> str:
    """Reschedule delivery to a new date."""
    logger.info(f"[TOOL] reschedule_delivery for order {order_id} to {new_date}")
    if new_date.lower() == "tomorrow":
        new_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    # Mocked
    return f"Delivery rescheduled: Order #{order_id} will be delivered on {new_date}. Customer notified."


@tool
def close_ticket(
    order_id: Annotated[int, "The order ID"],
    resolution: Annotated[str, "Resolution summary"]
) -> str:
    """Close the support ticket with resolution."""
    logger.info(f"[TOOL] close_ticket for order {order_id}: {resolution}")
    return f"Ticket closed for order #{order_id}. Resolution: {resolution}"


# ==================== TOOL COLLECTIONS ====================

OPERATIONS_TOOLS = [contact_hub, check_shipment_status]
CUSTOMER_TOOLS = [send_message, get_customer_response]
RESOLUTION_TOOLS = [process_refund, reschedule_delivery, close_ticket]

ALL_TOOLS = OPERATIONS_TOOLS + CUSTOMER_TOOLS + RESOLUTION_TOOLS

"""
Mocked Tools for Specialist Agents

All tools return mocked responses for demo purposes.
In production, these would integrate with real systems.

Tool Categories:
- POLICY_TOOLS: Policy retrieval (reads data/policy.md)
- OPERATIONS_TOOLS: Hub, shipment, customer stats
- CUSTOMER_TOOLS: Customer communication
- RESOLUTION_TOOLS: Action execution

Includes retry logic and structured logging for production readiness.
"""
import json
import logging
from datetime import datetime, timedelta
from functools import wraps
from typing import Annotated, Callable

from langchain_core.tools import tool
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.agent.retrieve import get_policy as _get_policy, get_customer_stats as _get_customer_stats

logger = logging.getLogger("agent.tools")


# ==================== RETRY DECORATOR ====================

def with_retry(func: Callable) -> Callable:
    """Wrap tool function with retry logic for transient failures."""
    @wraps(func)
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=5),
        retry=retry_if_exception_type((ConnectionError, TimeoutError, IOError)),
    )
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper


def log_tool_call(tool_name: str, **params):
    """Structured logging for tool calls."""
    logger.info(
        "tool_invoked",
        extra={"tool": tool_name, "params": params, "timestamp": datetime.utcnow().isoformat()}
    )


# ==================== POLICY TOOL ====================

@tool
def get_policy() -> str:
    """
    Retrieve company resolution policies from data/policy.md.
    
    Returns the full policy document for LLM to process.
    """
    log_tool_call("get_policy")
    return _get_policy()


# ==================== OPERATIONS TOOLS ====================

@tool
def get_customer_stats(customer_rating: Annotated[int, "Customer rating 1-5"]) -> str:
    """
    Get aggregated statistics for customers with this rating.
    
    Returns avg_care_calls, complaint_rate, avg_prior_purchases.
    Useful for understanding customer behavior patterns.
    """
    log_tool_call("get_customer_stats", customer_rating=customer_rating)
    stats = _get_customer_stats()
    rating_stats = stats.get(str(customer_rating), {})
    if rating_stats:
        return f"Customer stats for rating {customer_rating}: {json.dumps(rating_stats)}"
    return f"No stats found for rating {customer_rating}"


@tool
def contact_hub(order_id: Annotated[int, "The order ID to check"]) -> str:
    """Contact the destination hub to check package status."""
    log_tool_call("contact_hub", order_id=order_id)
    # Mocked response - in production would call hub API with retry
    return f"Hub response: Package for order #{order_id} is located and ready for dispatch. No issues found."


@tool
def check_shipment_status(order_id: Annotated[int, "The order ID to check"]) -> str:
    """Check current shipment tracking status."""
    log_tool_call("check_shipment_status", order_id=order_id)
    # Mocked response
    return f"Shipment #{order_id}: Currently at destination hub. Last scan: 2 hours ago."


# ==================== CUSTOMER TOOLS ====================

@tool
def send_message(
    order_id: Annotated[int, "The order ID"],
    message: Annotated[str, "Message to send to customer"]
) -> str:
    """Send a message to the customer."""
    log_tool_call("send_message", order_id=order_id, message_length=len(message))
    # In production would send email/SMS with retry
    return f"Message sent to customer for order #{order_id}"


@tool
def get_customer_response(
    order_id: Annotated[int, "The order ID"],
    mocked_response: Annotated[str, "The mocked customer response from order data"]
) -> str:
    """Get customer's response to our message (mocked for demo)."""
    log_tool_call("get_customer_response", order_id=order_id, mocked_response=mocked_response)
    # Returns the mocked response from order data
    if mocked_response == "refund":
        return "Customer response: I would like a refund please."
    elif mocked_response == "reschedule":
        return "Customer response: Please reschedule my delivery for tomorrow."
    else:
        return "Customer response: No action needed, thank you for the update."


# ==================== RESOLUTION TOOLS ====================

@tool
def process_refund(order_id: Annotated[int, "The order ID"]) -> str:
    """Process a full refund for the customer."""
    log_tool_call("process_refund", order_id=order_id)
    # Mocked - in production would call payment system with retry
    return f"Refund processed for order #{order_id}. Full refund issued. Confirmation sent to customer."


@tool
def reschedule_delivery(
    order_id: Annotated[int, "The order ID"],
    new_date: Annotated[str, "New delivery date (or 'tomorrow')"]
) -> str:
    """Reschedule delivery to a new date."""
    log_tool_call("reschedule_delivery", order_id=order_id, new_date=new_date)
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
    log_tool_call("close_ticket", order_id=order_id, resolution=resolution[:50])
    return f"Ticket closed for order #{order_id}. Resolution: {resolution}"


# ==================== TOOL COLLECTIONS ====================

POLICY_TOOLS = [get_policy]
OPERATIONS_TOOLS = [contact_hub, check_shipment_status, get_customer_stats]
CUSTOMER_TOOLS = [send_message, get_customer_response]
RESOLUTION_TOOLS = [get_policy, process_refund, reschedule_delivery, close_ticket]

ALL_TOOLS = POLICY_TOOLS + OPERATIONS_TOOLS + CUSTOMER_TOOLS + RESOLUTION_TOOLS

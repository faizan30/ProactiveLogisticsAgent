"""
Pydantic Models for Agent System

Provides validated data structures for:
- Input validation (OrderInput, SignalInput)
- Structured LLM outputs (RoutingDecision)
- Agent state schemas
"""
from datetime import datetime
from typing import Literal, Optional, Union
from pydantic import BaseModel, Field, field_validator


# ==================== INPUT VALIDATION ====================

class OrderInput(BaseModel):
    """Validated order data for agent processing."""
    id: int = Field(ge=1, description="Order ID")
    customer_rating: int = Field(ge=1, le=5, default=3, description="Customer rating 1-5")
    customer_care_calls: int = Field(ge=0, default=0, description="Number of care calls")
    prior_purchases: int = Field(ge=0, default=0, description="Prior purchase count")
    origin_region: str = Field(default="Unknown", description="Origin region")
    destination_region: str = Field(default="Unknown", description="Destination region")
    mode_of_shipment: str = Field(default="Standard", description="Shipment mode")
    ticket_raised: int = Field(ge=0, le=1, default=0, description="Whether ticket was raised")
    mocked_customer_response: str = Field(default="", description="Demo: expected customer response")
    
    # Optional datetime fields (can be datetime from DB or string)
    ship_date: Optional[Union[str, datetime]] = None
    scheduled_delivery_date: Optional[Union[str, datetime]] = None
    actual_delivery_date: Optional[Union[str, datetime]] = None
    hub_entry_time: Optional[Union[str, datetime]] = None
    
    @field_validator('ship_date', 'scheduled_delivery_date', 'actual_delivery_date', 'hub_entry_time', mode='before')
    @classmethod
    def convert_datetime_to_str(cls, v):
        """Convert datetime objects to ISO strings for consistency."""
        if isinstance(v, datetime):
            return v.isoformat()
        return v
    
    @field_validator('customer_rating')
    @classmethod
    def validate_rating(cls, v):
        if v < 1 or v > 5:
            raise ValueError('Customer rating must be between 1 and 5')
        return v
    
    def to_dict(self) -> dict:
        """Convert to dict for state storage."""
        return self.model_dump()


class SignalInput(BaseModel):
    """Validated signal data for agent processing."""
    signal_type: Literal["STUCK_AT_HUB", "PREDICTED_DELAY", "TICKET_RAISED", "ON_TRACK"]
    signal_reason: str = Field(min_length=1, max_length=500, description="Reason for the signal")
    
    @field_validator('signal_reason')
    @classmethod
    def validate_reason(cls, v):
        if not v or not v.strip():
            raise ValueError('Signal reason cannot be empty')
        return v.strip()


# ==================== STRUCTURED LLM OUTPUTS ====================

class RoutingDecision(BaseModel):
    """Structured output for supervisor routing decisions.
    
    Used with: llm.with_structured_output(RoutingDecision)
    Replaces fragile string parsing with typed, validated output.
    """
    reasoning: str = Field(
        description="Brief explanation of why this specialist was chosen"
    )
    next_specialist: Literal["operations", "customer", "resolution", "finish"] = Field(
        description="Which specialist to delegate to, or 'finish' if resolved"
    )
    task_description: str = Field(
        description="Specific task for the specialist to execute"
    )
    confidence: float = Field(
        ge=0.0, le=1.0, 
        default=0.8,
        description="Confidence in this decision (0-1)"
    )


class ResolutionOutput(BaseModel):
    """Structured output for resolution agent results."""
    action_taken: Literal["refund", "reschedule", "escalate", "close"] = Field(
        description="The resolution action that was executed"
    )
    summary: str = Field(
        max_length=100,
        description="Brief summary of resolution (max 100 chars)"
    )
    ticket_closed: bool = Field(
        default=True,
        description="Whether the support ticket was closed"
    )


class CustomerResponse(BaseModel):
    """Structured output for customer agent results."""
    message_sent: str = Field(
        max_length=500,
        description="The message sent to the customer"
    )
    customer_preference: Literal["refund", "reschedule", "none"] = Field(
        description="Customer's stated preference"
    )
    sentiment: Literal["positive", "neutral", "negative"] = Field(
        default="neutral",
        description="Detected customer sentiment"
    )


# ==================== VALIDATION HELPERS ====================

def validate_order(order: dict) -> OrderInput:
    """Validate order dict and return validated model.
    
    Raises ValidationError if order data is invalid.
    """
    return OrderInput(**order)


def validate_signal(signal_type: str, signal_reason: str) -> SignalInput:
    """Validate signal data.
    
    Raises ValidationError if signal data is invalid.
    """
    return SignalInput(signal_type=signal_type, signal_reason=signal_reason)

"""
SQLAlchemy models for Postgres storage.
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, Text
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()


class Order(Base):
    """Order table - core shipment data."""
    __tablename__ = 'orders'
    
    id = Column(Integer, primary_key=True)
    order_date = Column(DateTime)
    promised_date = Column(DateTime)
    ship_date = Column(DateTime, nullable=True)
    destination_arrival_date = Column(DateTime, nullable=True)
    actual_delivery_date = Column(DateTime, nullable=True)
    
    origin_region = Column(String(50))
    destination_region = Column(String(50))
    mode_of_shipment = Column(String(20))
    
    customer_rating = Column(Integer)
    customer_care_calls = Column(Integer, default=0)
    ticket_raised = Column(Integer, default=0)  # 0 or 1
    
    product_cost = Column(Float, default=100.0)
    
    # Mocked response for multi-turn (Option A)
    mocked_customer_response = Column(String(50), nullable=True)  # "refund", "reschedule"


class Conversation(Base):
    """Multi-turn conversation state."""
    __tablename__ = 'conversations'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, index=True)
    signal_type = Column(String(30))
    status = Column(String(20), default="in_progress")  # in_progress, resolved
    resolution = Column(String(200), nullable=True)  # Short resolution summary
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ConversationTurn(Base):
    """Individual turn in a conversation."""
    __tablename__ = 'conversation_turns'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(Integer, index=True)
    role = Column(String(20))  # agent, customer, hub_manager
    action = Column(String(50), nullable=True)
    message = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)

"""
PostgresManager - Simplified data access layer.
"""
from typing import Optional, List
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from src.storage_manager.db_models import Base, Order, Conversation, ConversationTurn


class PostgresManager:
    """Simple CRUD operations for orders and conversations."""
    
    def __init__(self, connection_string: str):
        self.engine = create_engine(connection_string)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
    
    # ==================== ORDER OPERATIONS ====================
    
    def get_order(self, order_id: int) -> Optional[dict]:
        """Get single order by ID."""
        session = self.Session()
        try:
            order = session.query(Order).filter(Order.id == order_id).first()
            if not order:
                return None
            return {
                "id": order.id,
                "order_date": order.order_date.isoformat() if order.order_date else None,
                "promised_date": order.promised_date.isoformat() if order.promised_date else None,
                "ship_date": order.ship_date.isoformat() if order.ship_date else None,
                "destination_arrival_date": order.destination_arrival_date.isoformat() if order.destination_arrival_date else None,
                "actual_delivery_date": order.actual_delivery_date.isoformat() if order.actual_delivery_date else None,
                "origin_region": order.origin_region,
                "destination_region": order.destination_region,
                "mode_of_shipment": order.mode_of_shipment,
                "customer_rating": order.customer_rating,
                "customer_care_calls": order.customer_care_calls,
                "ticket_raised": order.ticket_raised,
                "product_cost": order.product_cost,
                "mocked_customer_response": order.mocked_customer_response,
            }
        finally:
            session.close()
    
    def get_all_orders(self) -> List[dict]:
        """Get all orders."""
        session = self.Session()
        try:
            orders = session.query(Order).all()
            return [
                {
                    "id": o.id,
                    "order_date": o.order_date.isoformat() if o.order_date else None,
                    "promised_date": o.promised_date.isoformat() if o.promised_date else None,
                    "ship_date": o.ship_date.isoformat() if o.ship_date else None,
                    "destination_arrival_date": o.destination_arrival_date.isoformat() if o.destination_arrival_date else None,
                    "actual_delivery_date": o.actual_delivery_date.isoformat() if o.actual_delivery_date else None,
                    "origin_region": o.origin_region,
                    "destination_region": o.destination_region,
                    "mode_of_shipment": o.mode_of_shipment,
                    "customer_rating": o.customer_rating,
                    "customer_care_calls": o.customer_care_calls,
                    "ticket_raised": o.ticket_raised,
                    "product_cost": o.product_cost,
                }
                for o in orders
            ]
        finally:
            session.close()
    
    def upsert_order(self, order_data: dict):
        """Insert or update an order."""
        session = self.Session()
        try:
            existing = session.query(Order).filter(Order.id == order_data["id"]).first()
            if existing:
                for key, value in order_data.items():
                    setattr(existing, key, value)
            else:
                order = Order(**order_data)
                session.add(order)
            session.commit()
        finally:
            session.close()
    
    def delete_order(self, order_id: int):
        """Delete an order."""
        session = self.Session()
        try:
            session.query(Order).filter(Order.id == order_id).delete()
            session.commit()
        finally:
            session.close()
    
    def clear_all_orders(self):
        """Delete all orders (for reset)."""
        session = self.Session()
        try:
            session.query(Order).delete()
            session.commit()
        finally:
            session.close()
    
    def get_orders_by_status(self, status: str) -> List[dict]:
        """Get orders filtered by delivery status.
        
        Status options:
        - pending: Not yet delivered (actual_delivery_date IS NULL)
        - in_transit: Shipped but not at hub (ship_date NOT NULL, destination_arrival_date IS NULL)
        - at_hub: At hub but not delivered (destination_arrival_date NOT NULL, actual_delivery_date IS NULL)
        - delivered: Delivered (actual_delivery_date IS NOT NULL)
        """
        session = self.Session()
        try:
            query = session.query(Order)
            
            if status == "pending":
                query = query.filter(Order.actual_delivery_date.is_(None))
            elif status == "in_transit":
                query = query.filter(
                    Order.ship_date.isnot(None),
                    Order.destination_arrival_date.is_(None)
                )
            elif status == "at_hub":
                query = query.filter(
                    Order.destination_arrival_date.isnot(None),
                    Order.actual_delivery_date.is_(None)
                )
            elif status == "delivered":
                query = query.filter(Order.actual_delivery_date.isnot(None))
            else:
                return []
            
            orders = query.all()
            return [
                {
                    "id": o.id,
                    "order_date": o.order_date,
                    "promised_date": o.promised_date,
                    "ship_date": o.ship_date,
                    "destination_arrival_date": o.destination_arrival_date,
                    "actual_delivery_date": o.actual_delivery_date,
                    "origin_region": o.origin_region,
                    "destination_region": o.destination_region,
                    "mode_of_shipment": o.mode_of_shipment,
                    "customer_rating": o.customer_rating,
                    "customer_care_calls": o.customer_care_calls,
                    "ticket_raised": o.ticket_raised,
                    "product_cost": o.product_cost,
                }
                for o in orders
            ]
        finally:
            session.close()
    
    # ==================== CONVERSATION OPERATIONS ====================
    
    def create_conversation(self, order_id: int, signal_type: str) -> int:
        """Create a new conversation, return its ID."""
        session = self.Session()
        try:
            conv = Conversation(order_id=order_id, signal_type=signal_type)
            session.add(conv)
            session.commit()
            return conv.id
        finally:
            session.close()
    
    def add_turn(self, conversation_id: int, role: str, message: str, action: str = None):
        """Add a turn to a conversation."""
        session = self.Session()
        try:
            turn = ConversationTurn(
                conversation_id=conversation_id,
                role=role,
                action=action,
                message=message
            )
            session.add(turn)
            session.commit()
        finally:
            session.close()
    
    def get_conversation(self, order_id: int) -> Optional[dict]:
        """Get conversation for an order."""
        session = self.Session()
        try:
            conv = session.query(Conversation).filter(
                Conversation.order_id == order_id
            ).order_by(Conversation.created_at.desc()).first()
            
            if not conv:
                return None
            
            turns = session.query(ConversationTurn).filter(
                ConversationTurn.conversation_id == conv.id
            ).order_by(ConversationTurn.timestamp).all()
            
            return {
                "id": conv.id,
                "order_id": conv.order_id,
                "signal_type": conv.signal_type,
                "status": conv.status,
                "resolution": conv.resolution,
                "turns": [
                    {
                        "role": t.role,
                        "action": t.action,
                        "message": t.message,
                        "timestamp": t.timestamp.isoformat() if t.timestamp else None
                    }
                    for t in turns
                ]
            }
        finally:
            session.close()
    
    def update_conversation_status(self, conversation_id: int, status: str, resolution: str = None):
        """Update conversation status."""
        session = self.Session()
        try:
            conv = session.query(Conversation).filter(Conversation.id == conversation_id).first()
            if conv:
                conv.status = status
                conv.resolution = resolution
                session.commit()
        finally:
            session.close()
    
    def clear_conversations(self):
        """Delete all conversations (for reset)."""
        session = self.Session()
        try:
            session.query(ConversationTurn).delete()
            session.query(Conversation).delete()
            session.commit()
        finally:
            session.close()
    

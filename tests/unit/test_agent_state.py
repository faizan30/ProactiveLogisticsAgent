"""
Unit tests for agent state management.

Tests state creation and structure without LLM calls.
"""
import pytest
from src.agent.state import AgentState, create_initial_state


class TestAgentState:
    """Tests for AgentState TypedDict structure."""
    
    def test_create_initial_state_returns_dict(self):
        order = {"id": 1001, "origin_region": "North", "destination_region": "South"}
        state = create_initial_state(
            order=order,
            signal_type="STUCK_AT_HUB",
            signal_reason="Package at hub for 48h"
        )
        assert isinstance(state, dict)
    
    def test_create_initial_state_has_required_fields(self):
        order = {"id": 1002, "origin_region": "East", "destination_region": "West"}
        state = create_initial_state(
            order=order,
            signal_type="PREDICTED_DELAY",
            signal_reason="Transit time exceeded"
        )
        
        required_fields = [
            "order_id", "order", "signal_type", "signal_reason",
            "messages", "actions_taken", "current_specialist",
            "status", "resolution", "conversation_turns"
        ]
        for field in required_fields:
            assert field in state, f"Missing required field: {field}"
    
    def test_create_initial_state_order_id_extracted(self):
        order = {"id": 1003, "origin_region": "North", "destination_region": "South"}
        state = create_initial_state(
            order=order,
            signal_type="TICKET_RAISED",
            signal_reason="Customer complained"
        )
        assert state["order_id"] == 1003
    
    def test_create_initial_state_signal_preserved(self):
        order = {"id": 1004}
        state = create_initial_state(
            order=order,
            signal_type="STUCK_AT_HUB",
            signal_reason="Test reason"
        )
        assert state["signal_type"] == "STUCK_AT_HUB"
        assert state["signal_reason"] == "Test reason"
    
    def test_create_initial_state_empty_actions(self):
        order = {"id": 1001}
        state = create_initial_state(
            order=order,
            signal_type="PREDICTED_DELAY",
            signal_reason="Delay predicted"
        )
        assert state["actions_taken"] == []
        assert state["messages"] == []
        assert state["conversation_turns"] == []
    
    def test_create_initial_state_status_in_progress(self):
        order = {"id": 1001}
        state = create_initial_state(
            order=order,
            signal_type="STUCK_AT_HUB",
            signal_reason="Stuck"
        )
        assert state["status"] == "in_progress"
        assert state["resolution"] is None
    
    def test_create_initial_state_mocked_response(self):
        order = {"id": 1001, "mocked_customer_response": "refund"}
        state = create_initial_state(
            order=order,
            signal_type="TICKET_RAISED",
            signal_reason="Ticket"
        )
        assert state["mocked_customer_response"] == "refund"
    
    def test_create_initial_state_mocked_response_default(self):
        order = {"id": 1001}
        state = create_initial_state(
            order=order,
            signal_type="STUCK_AT_HUB",
            signal_reason="Stuck"
        )
        # Default is empty string when not provided
        assert state["mocked_customer_response"] == ""


class TestAgentStateModification:
    """Tests for state modification patterns used by agents."""
    
    def test_state_actions_can_be_appended(self):
        order = {"id": 1001}
        state = create_initial_state(order, "STUCK_AT_HUB", "Test")
        
        # Simulate agent adding action
        new_actions = state["actions_taken"] + ["operations: Hub contacted"]
        state["actions_taken"] = new_actions
        
        assert len(state["actions_taken"]) == 1
        assert "Hub contacted" in state["actions_taken"][0]
    
    def test_state_conversation_turns_can_be_appended(self):
        order = {"id": 1001}
        state = create_initial_state(order, "TICKET_RAISED", "Test")
        
        turn = {"role": "customer", "action": "message", "message": "I want refund"}
        state["conversation_turns"] = state["conversation_turns"] + [turn]
        
        assert len(state["conversation_turns"]) == 1
        assert state["conversation_turns"][0]["role"] == "customer"
    
    def test_state_status_can_be_updated(self):
        order = {"id": 1001}
        state = create_initial_state(order, "PREDICTED_DELAY", "Test")
        
        state["status"] = "resolved"
        state["resolution"] = "Delivery rescheduled"
        
        assert state["status"] == "resolved"
        assert state["resolution"] == "Delivery rescheduled"

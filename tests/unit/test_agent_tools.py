"""
Unit tests for agent tools.

Tests mocked tool implementations without LLM calls.
"""
import pytest
from src.agent.tools import (
    contact_hub,
    check_shipment_status,
    send_message,
    get_customer_response,
    process_refund,
    reschedule_delivery,
    close_ticket,
    OPERATIONS_TOOLS,
    CUSTOMER_TOOLS,
    RESOLUTION_TOOLS,
)


class TestOperationsTools:
    """Tests for operations agent tools."""
    
    def test_contact_hub_returns_string(self):
        result = contact_hub.invoke({"order_id": 1001})
        assert isinstance(result, str)
        assert "1001" in result
    
    def test_contact_hub_contains_status(self):
        result = contact_hub.invoke({"order_id": 1002})
        assert any(word in result.lower() for word in ["located", "ready", "dispatch", "found"])
    
    def test_check_shipment_status_returns_string(self):
        result = check_shipment_status.invoke({"order_id": 1003})
        assert isinstance(result, str)
        assert "1003" in result
    
    def test_check_shipment_status_contains_info(self):
        result = check_shipment_status.invoke({"order_id": 1004})
        assert any(word in result.lower() for word in ["hub", "scan", "shipment"])
    
    def test_operations_tools_list(self):
        assert len(OPERATIONS_TOOLS) == 2
        tool_names = [t.name for t in OPERATIONS_TOOLS]
        assert "contact_hub" in tool_names
        assert "check_shipment_status" in tool_names


class TestCustomerTools:
    """Tests for customer agent tools."""
    
    def test_send_message_returns_string(self):
        result = send_message.invoke({
            "order_id": 1001,
            "message": "Your package is delayed"
        })
        assert isinstance(result, str)
    
    def test_send_message_confirms_sent(self):
        result = send_message.invoke({
            "order_id": 1002,
            "message": "We apologize for the delay"
        })
        assert any(word in result.lower() for word in ["sent", "message"])
    
    def test_get_customer_response_refund(self):
        result = get_customer_response.invoke({"order_id": 1001, "mocked_response": "refund"})
        assert "refund" in result.lower()
    
    def test_get_customer_response_reschedule(self):
        result = get_customer_response.invoke({"order_id": 1002, "mocked_response": "reschedule"})
        assert "reschedule" in result.lower()
    
    def test_get_customer_response_none(self):
        result = get_customer_response.invoke({"order_id": 1003, "mocked_response": "none"})
        assert any(word in result.lower() for word in ["no action", "thank you"])
    
    def test_customer_tools_list(self):
        assert len(CUSTOMER_TOOLS) == 2
        tool_names = [t.name for t in CUSTOMER_TOOLS]
        assert "send_message" in tool_names
        assert "get_customer_response" in tool_names


class TestResolutionTools:
    """Tests for resolution agent tools."""
    
    def test_process_refund_returns_string(self):
        result = process_refund.invoke({"order_id": 1001, "refund_percent": 25})
        assert isinstance(result, str)
    
    def test_process_refund_confirms_processed(self):
        result = process_refund.invoke({"order_id": 1002, "refund_percent": 50})
        assert any(word in result.lower() for word in ["processed", "refund", "issued"])
    
    def test_process_refund_includes_percent(self):
        result = process_refund.invoke({"order_id": 1003, "refund_percent": 30})
        assert "30" in result
    
    def test_reschedule_delivery_returns_string(self):
        result = reschedule_delivery.invoke({"order_id": 1001, "new_date": "2024-01-15"})
        assert isinstance(result, str)
    
    def test_reschedule_delivery_confirms_scheduled(self):
        result = reschedule_delivery.invoke({"order_id": 1002, "new_date": "2024-01-20"})
        assert any(word in result.lower() for word in ["rescheduled", "delivered"])
    
    def test_reschedule_tomorrow(self):
        result = reschedule_delivery.invoke({"order_id": 1003, "new_date": "tomorrow"})
        assert "rescheduled" in result.lower()
    
    def test_close_ticket_returns_string(self):
        result = close_ticket.invoke({"order_id": 1001, "resolution": "Refund processed"})
        assert isinstance(result, str)
        assert "closed" in result.lower()
    
    def test_resolution_tools_list(self):
        assert len(RESOLUTION_TOOLS) == 3
        tool_names = [t.name for t in RESOLUTION_TOOLS]
        assert "process_refund" in tool_names
        assert "reschedule_delivery" in tool_names
        assert "close_ticket" in tool_names


class TestToolPartitioning:
    """Tests to verify tools are properly partitioned by agent."""
    
    def test_no_tool_overlap(self):
        """Each tool should belong to exactly one agent."""
        ops_names = {t.name for t in OPERATIONS_TOOLS}
        cust_names = {t.name for t in CUSTOMER_TOOLS}
        res_names = {t.name for t in RESOLUTION_TOOLS}
        
        assert ops_names.isdisjoint(cust_names), "Ops and Customer tools overlap"
        assert ops_names.isdisjoint(res_names), "Ops and Resolution tools overlap"
        assert cust_names.isdisjoint(res_names), "Customer and Resolution tools overlap"
    
    def test_all_tools_have_descriptions(self):
        """All tools should have descriptions for LLM."""
        all_tools = OPERATIONS_TOOLS + CUSTOMER_TOOLS + RESOLUTION_TOOLS
        for tool in all_tools:
            assert tool.description, f"Tool {tool.name} missing description"
            assert len(tool.description) > 10, f"Tool {tool.name} description too short"

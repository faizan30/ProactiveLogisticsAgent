"""
Unit tests for agent graph structure and state management.

Tests graph construction, state creation, and mocked specialist behavior
without making actual LLM calls.
"""
import pytest
from unittest.mock import patch, MagicMock

from langchain_core.messages import AIMessage

from src.agent.state import create_initial_state
from src.agent.supervisor import build_graph
from src.agent.specialists.base import create_specialist_node
from src.agent.prompts import OPERATIONS_SYSTEM_PROMPT
from src.agent.tools import OPERATIONS_TOOLS, CUSTOMER_TOOLS


class TestAgentGraphStructure:
    """Tests for agent graph structure without LLM calls."""
    
    def test_build_graph_returns_state_graph(self):
        """Build graph creates a valid StateGraph."""
        workflow = build_graph()
        assert workflow is not None
        assert hasattr(workflow, "nodes")
    
    def test_workflow_has_required_nodes(self):
        """Workflow contains all required nodes."""
        workflow = build_graph()
        node_names = list(workflow.nodes.keys())
        
        for node in ["supervisor", "operations", "customer", "resolution", "finish"]:
            assert node in node_names, f"Missing node: {node}"
    
    def test_workflow_compiles(self):
        """Workflow can compile without checkpointer."""
        workflow = build_graph()
        graph = workflow.compile()
        assert graph is not None
        assert hasattr(graph, "invoke")
    
    def test_graph_has_entry_point(self):
        """Graph should have supervisor as entry point."""
        workflow = build_graph()
        # Entry point is set via set_entry_point
        assert "supervisor" in workflow.nodes


class TestAgentState:
    """Tests for agent state management."""
    
    def test_create_initial_state_structure(self):
        """Initial state has all required fields."""
        order = {"id": 1003, "origin_region": "North", "destination_region": "South"}
        state = create_initial_state(order, "STUCK_AT_HUB", "Package at hub 48h")
        
        required = ["order_id", "order", "signal_type", "signal_reason", 
                    "messages", "actions_taken", "status", "resolution"]
        for field in required:
            assert field in state, f"Missing field: {field}"
    
    def test_state_preserves_order_data(self):
        """State preserves order information."""
        order = {"id": 1003, "mocked_customer_response": "refund"}
        state = create_initial_state(order, "TICKET_RAISED", "Customer complaint")
        
        assert state["order_id"] == 1003
        assert state["mocked_customer_response"] == "refund"
    
    def test_initial_state_status(self):
        """Initial state should have in_progress status."""
        order = {"id": 1001}
        state = create_initial_state(order, "PREDICTED_DELAY", "Late shipment")
        
        assert state["status"] == "in_progress"
        assert state["resolution"] is None
    
    def test_initial_state_empty_collections(self):
        """Initial state should have empty collections."""
        order = {"id": 1001}
        state = create_initial_state(order, "PREDICTED_DELAY", "Late")
        
        assert state["actions_taken"] == []
        assert state["conversation_turns"] == []


class TestSpecialistNodesMocked:
    """Tests for specialist agents with mocked LLM."""
    
    @pytest.fixture
    def mock_state(self):
        state = create_initial_state(
            order={"id": 1003, "origin_region": "North", "destination_region": "South"},
            signal_type="STUCK_AT_HUB",
            signal_reason="Package at hub"
        )
        state["messages"] = [AIMessage(content="Contact the hub")]
        return state
    
    @patch("src.agent.specialists.base.create_react_agent")
    @patch("src.agent.specialists.base.ChatOpenAI")
    def test_specialist_executes_and_returns_actions(self, mock_llm, mock_agent, mock_state):
        """Specialist node executes task and returns state updates."""
        mock_react = MagicMock()
        mock_react.invoke.return_value = {
            "messages": [AIMessage(content="Hub contacted. Package ready.")]
        }
        mock_agent.return_value = mock_react
        
        node_fn = create_specialist_node("operations", OPERATIONS_SYSTEM_PROMPT, OPERATIONS_TOOLS)
        result = node_fn(mock_state, {})
        
        assert "actions_taken" in result
        assert len(result["actions_taken"]) > 0
        assert "operations" in result["actions_taken"][0].lower()
    
    @patch("src.agent.specialists.base.create_react_agent")
    @patch("src.agent.specialists.base.ChatOpenAI")
    def test_specialist_adds_conversation_turn(self, mock_llm, mock_agent, mock_state):
        """Specialist adds conversation turn to state."""
        mock_react = MagicMock()
        mock_react.invoke.return_value = {
            "messages": [AIMessage(content="Customer notified.")]
        }
        mock_agent.return_value = mock_react
        
        node_fn = create_specialist_node("customer", "You are customer agent", CUSTOMER_TOOLS)
        result = node_fn(mock_state, {})
        
        assert "conversation_turns" in result
        assert result["conversation_turns"][0]["role"] == "customer"
    
    @patch("src.agent.specialists.base.create_react_agent")
    @patch("src.agent.specialists.base.ChatOpenAI")
    def test_specialist_clears_current_specialist(self, mock_llm, mock_agent, mock_state):
        """Specialist should clear current_specialist after execution."""
        mock_react = MagicMock()
        mock_react.invoke.return_value = {
            "messages": [AIMessage(content="Done")]
        }
        mock_agent.return_value = mock_react
        
        node_fn = create_specialist_node("operations", OPERATIONS_SYSTEM_PROMPT, OPERATIONS_TOOLS)
        result = node_fn(mock_state, {})
        
        assert result["current_specialist"] is None


class TestRunSupervisorMocked:
    """Tests for run_supervisor with mocked graph."""
    
    @patch("src.agent.supervisor.get_langfuse_handler")
    @patch("src.agent.supervisor.build_graph")
    def test_run_supervisor_returns_result_structure(self, mock_build, mock_langfuse):
        """run_supervisor returns expected result structure."""
        from src.agent.supervisor import run_supervisor
        
        mock_langfuse.return_value = None
        
        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {
            "order_id": 1003,
            "status": "resolved",
            "resolution": "Rescheduled",
            "actions_taken": ["ops: hub contacted"],
            "conversation_turns": [{"role": "agent", "message": "Done"}],
        }
        mock_workflow = MagicMock()
        mock_workflow.compile.return_value = mock_graph
        mock_build.return_value = mock_workflow
        
        result = run_supervisor(
            order={"id": 1003, "origin_region": "North", "destination_region": "South"},
            signal_type="STUCK_AT_HUB",
            signal_reason="Test",
            use_checkpointer=False,
        )
        
        assert result["order_id"] == 1003
        assert result["status"] == "resolved"
        assert "resolution" in result
        assert "actions_taken" in result
    
    @patch("src.agent.supervisor.get_langfuse_handler")
    @patch("src.agent.supervisor.build_graph")
    def test_run_supervisor_handles_errors(self, mock_build, mock_langfuse):
        """run_supervisor handles errors gracefully."""
        from src.agent.supervisor import run_supervisor
        
        mock_langfuse.return_value = None
        mock_graph = MagicMock()
        mock_graph.invoke.side_effect = Exception("LLM Error")
        mock_workflow = MagicMock()
        mock_workflow.compile.return_value = mock_graph
        mock_build.return_value = mock_workflow
        
        result = run_supervisor(
            order={"id": 1003},
            signal_type="STUCK_AT_HUB",
            signal_reason="Test",
            use_checkpointer=False,
        )
        
        assert result["status"] == "failed"
        assert "Error" in result["resolution"]
    
    @patch("src.agent.supervisor.get_langfuse_handler")
    @patch("src.agent.supervisor.build_graph")
    def test_run_supervisor_includes_order_id(self, mock_build, mock_langfuse):
        """run_supervisor always includes order_id in result."""
        from src.agent.supervisor import run_supervisor
        
        mock_langfuse.return_value = None
        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {"status": "resolved"}
        mock_workflow = MagicMock()
        mock_workflow.compile.return_value = mock_graph
        mock_build.return_value = mock_workflow
        
        result = run_supervisor(
            order={"id": 9999},
            signal_type="TEST",
            signal_reason="Test",
            use_checkpointer=False,
        )
        
        assert result["order_id"] == 9999

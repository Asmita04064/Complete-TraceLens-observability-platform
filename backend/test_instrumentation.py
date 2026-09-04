"""Automated tests for the instrumentation and real agent execution."""

import os
import pytest
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base, settings
from app.models import Trace, TraceEvent
from app.models.agent import Order, Customer
from app.instrumentation import Tracer, set_current_trace_id, set_current_event_id, get_current_trace_id, clear_trace_context
from app.agent import AIAgent, OrderService
import google.generativeai as genai
from app.agent.llm import GeminiProvider
from app.instrumentation.redaction import redact
from app.instrumentation.decorators import traced_function
from app.schemas import AgentRequest
from pydantic import ValidationError


TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "sqlite:///./test_tracelens.db")
if TEST_DATABASE_URL == settings.database_url:
    raise RuntimeError("TEST_DATABASE_URL must not equal DATABASE_URL")

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False} if TEST_DATABASE_URL.startswith("sqlite") else {},
)
TestSessionLocal = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)


# Fixtures
@pytest.fixture(scope="function")
def db(monkeypatch):
    """Create a fresh isolated test database; never use the development engine."""
    clear_trace_context()
    Base.metadata.create_all(bind=test_engine)
    monkeypatch.setattr("app.database.SessionLocal", TestSessionLocal)
    db = TestSessionLocal()
    yield db
    db.close()
    Base.metadata.drop_all(bind=test_engine)
    clear_trace_context()


@pytest.fixture
def sample_customer(db):
    """Create a sample customer."""
    customer = Customer(
        customer_id="CUST-TEST-001",
        name="Test Customer",
        email="test@example.com",
        phone="+1-555-0000",
        address="123 Test St",
        created_at=datetime.now(timezone.utc),
    )
    db.add(customer)
    db.commit()
    return customer


@pytest.fixture
def sample_order(db, sample_customer):
    """Create a sample order."""
    order = Order(
        order_id="ORD-TEST-001",
        customer_id=sample_customer.customer_id,
        order_date=datetime.now(timezone.utc) - timedelta(days=2),
        status="in_transit",
        total_amount=99.99,
        items_description="Test items",
        estimated_delivery=datetime.now(timezone.utc) + timedelta(days=2),
        tracking_number="TRK-TEST-001",
        shipping_address="123 Test St",
        created_at=datetime.now(timezone.utc) - timedelta(days=2),
    )
    db.add(order)
    db.commit()
    return order


# Tests for trace context
class TestTraceContext:
    def test_set_and_get_trace_id(self):
        """Test trace ID context management."""
        clear_trace_context()
        assert get_current_trace_id() is None

        set_current_trace_id("tr_test123")
        assert get_current_trace_id() == "tr_test123"

        clear_trace_context()
        assert get_current_trace_id() is None


# Tests for tracer
class TestTracer:
    def test_start_trace(self, db):
        """Test trace creation."""
        tracer = Tracer(db)
        trace_id = tracer.start_trace("Test input")

        assert trace_id.startswith("tr_")
        assert get_current_trace_id() == trace_id

        # Verify in database
        trace = db.query(Trace).filter(Trace.trace_id == trace_id).first()
        assert trace is not None
        assert trace.input == "Test input"
        assert trace.status == "running"
        assert trace.started_at is not None

    def test_complete_trace(self, db):
        """Test trace completion."""
        tracer = Tracer(db)
        trace_id = tracer.start_trace("Test input")

        tracer.complete_trace("Test output")

        # Verify in database
        trace = db.query(Trace).filter(Trace.trace_id == trace_id).first()
        assert trace.status == "completed"
        assert trace.output == "Test output"
        assert trace.completed_at is not None
        assert trace.duration_ms is not None and trace.duration_ms >= 0

    def test_fail_trace(self, db):
        """Test trace failure."""
        tracer = Tracer(db)
        trace_id = tracer.start_trace("Test input")

        tracer.fail_trace("Test error message")

        # Verify in database
        trace = db.query(Trace).filter(Trace.trace_id == trace_id).first()
        assert trace.status == "failed"
        assert trace.output == "Test error message"
        assert trace.completed_at is not None
        assert trace.duration_ms is not None and trace.duration_ms >= 0

    def test_create_event(self, db):
        """Test event creation with tracing."""
        tracer = Tracer(db)
        trace_id = tracer.start_trace("Test input")

        import time
        start = time.perf_counter()
        time.sleep(0.01)  # 10ms delay
        end = time.perf_counter()

        event_id = tracer.create_event(
            event_type="llm_call",
            component="test-llm",
            start_time=start,
            end_time=end,
            input_data={"query": "test"},
            output_data={"response": "test response"},
            status="success",
        )

        # Verify event created
        event = db.query(TraceEvent).filter(TraceEvent.id == event_id).first()
        assert event is not None
        assert event.event_id.startswith("evt_")
        assert event.trace_id == trace_id
        assert event.event_type == "llm_call"
        assert event.component == "test-llm"
        assert event.status == "success"
        assert event.duration_ms >= 10  # At least 10ms

    def test_event_sequence_and_hierarchy(self, db):
        """Test event sequence numbers and parent-child relationships."""
        tracer = Tracer(db)
        trace_id = tracer.start_trace("Test input")

        import time

        # Create first event (LLM call)
        start = time.perf_counter()
        time.sleep(0.005)
        event1_id = tracer.create_event(
            event_type="llm_call",
            component="gemini",
            start_time=start,
            end_time=time.perf_counter(),
            status="success",
        )

        # Create second event (Tool call, child of LLM)
        start = time.perf_counter()
        time.sleep(0.005)
        event2_id = tracer.create_event(
            event_type="tool_call",
            component="order_service",
            start_time=start,
            end_time=time.perf_counter(),
            status="success",
        )

        # Verify sequences
        events = (
            db.query(TraceEvent)
            .filter(TraceEvent.trace_id == trace_id)
            .order_by(TraceEvent.sequence_number)
            .all()
        )
        assert len(events) == 2
        assert events[0].sequence_number == 1
        assert events[1].sequence_number == 2

    def test_event_error_capture(self, db):
        """Test error capture in events."""
        tracer = Tracer(db)
        trace_id = tracer.start_trace("Test input")

        import time

        event_id = tracer.create_event(
            event_type="database_query",
            component="postgresql",
            start_time=time.perf_counter(),
            end_time=time.perf_counter(),
            status="failed",
            error_message="Database connection error",
        )

        event = db.query(TraceEvent).filter(TraceEvent.id == event_id).first()
        assert event.status == "failed"
        assert event.error_message == "Database connection error"

    def test_parent_event_must_belong_to_active_trace(self, db):
        first = Tracer(db)
        first_trace = first.start_trace("first")
        parent_id = first.create_event("tool_call", "first", 1, 2)
        second = Tracer(db)
        second_trace = second.start_trace("second")
        set_current_trace_id(second_trace)
        set_current_event_id(parent_id)
        with pytest.raises(RuntimeError, match="does not belong"):
            second.create_event("tool_call", "second", 1, 2)
        set_current_trace_id(first_trace)
        first.complete_trace("done")
        clear_trace_context()
        assert db.query(TraceEvent).filter(TraceEvent.id == parent_id).one()

    def test_completed_trace_rejects_new_events(self, db):
        tracer = Tracer(db)
        trace_id = tracer.start_trace("completed")
        tracer.complete_trace("done")
        set_current_trace_id(trace_id)
        with pytest.raises(RuntimeError, match="not in running state"):
            tracer.create_event("tool_call", "late", 1, 2)


# Tests for OrderService
class TestOrderService:
    def test_get_order_status(self, db, sample_order):
        """Test order status retrieval."""
        service = OrderService(db)
        result = service.get_order_status(sample_order.order_id)

        assert result["order_id"] == sample_order.order_id
        assert result["status"] == "in_transit"
        assert result["total_amount"] == 99.99

    def test_get_order_status_not_found(self, db):
        """Test order not found."""
        service = OrderService(db)
        with pytest.raises(ValueError, match="Order .* not found"):
            service.get_order_status("ORD-INVALID")

    def test_get_customer_details(self, db, sample_customer):
        """Test customer details retrieval."""
        service = OrderService(db)
        result = service.get_customer_details(sample_customer.customer_id)

        assert result["customer_id"] == sample_customer.customer_id
        assert result["name"] == "Test Customer"
        assert result["email"] == "test@example.com"

    def test_get_customer_details_not_found(self, db):
        """Test customer not found."""
        service = OrderService(db)
        with pytest.raises(ValueError, match="Customer .* not found"):
            service.get_customer_details("CUST-INVALID")

    def test_list_customer_orders(self, db, sample_customer, sample_order):
        """Test listing customer orders."""
        service = OrderService(db)
        orders = service.list_customer_orders(sample_customer.customer_id)

        assert len(orders) >= 1
        assert any(o["order_id"] == sample_order.order_id for o in orders)


# Tests for complete workflow
class TestCompleteWorkflow:
    def test_trace_lifecycle(self, db):
        """Test complete trace lifecycle: create -> add events -> complete."""
        tracer = Tracer(db)

        # Start trace
        trace_id = tracer.start_trace("What is my order status?")
        assert get_current_trace_id() == trace_id

        # Simulate LLM call
        import time

        start = time.perf_counter()
        time.sleep(0.01)
        end = time.perf_counter()

        tracer.create_event(
            event_type="llm_call",
            component="gemini",
            start_time=start,
            end_time=end,
            input_data={"message": "What is my order status?"},
            output_data={"decision": "call_order_service"},
            status="success",
        )

        # Simulate database query
        start = time.perf_counter()
        time.sleep(0.01)
        end = time.perf_counter()

        tracer.create_event(
            event_type="database_query",
            component="postgresql",
            start_time=start,
            end_time=end,
            input_data={"order_id": "ORD-123"},
            output_data={"status": "in_transit"},
            status="success",
        )

        # Complete trace
        tracer.complete_trace("Your order is currently in transit")

        # Verify complete trace
        trace = db.query(Trace).filter(Trace.trace_id == trace_id).first()
        assert trace.status == "completed"
        assert trace.output == "Your order is currently in transit"

        events = (
            db.query(TraceEvent)
            .filter(TraceEvent.trace_id == trace_id)
            .order_by(TraceEvent.sequence_number)
            .all()
        )
        assert len(events) == 2
        assert all(e.status == "success" for e in events)
        assert events[0].event_type == "llm_call"
        assert events[1].event_type == "database_query"

        # Verify timing
        total_duration = sum(e.duration_ms for e in events if e.duration_ms)
        assert total_duration > 0

    def test_agent_creates_real_workflow_lineage(self, db, sample_order, monkeypatch):
        """The observed agent creates the semantic LLM -> KB -> DB -> API -> LLM flow."""
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"order_id": sample_order.order_id, "status": "in_transit"}).encode())

            def log_message(self, *_args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        monkeypatch.setenv("GEMINI_API_KEY", "test-only")
        monkeypatch.setenv("ORDER_MANAGEMENT_API_URL", f"http://127.0.0.1:{server.server_port}")
        class FakeResponse:
            def __init__(self, text):
                self.text = text

        class FakeModel:
            def __init__(self, model_name):
                self.model_name = model_name

            def generate_content(self, prompt, stream=False):
                if "Analyze this" in prompt:
                    return FakeResponse("Need policy and order details")
                if "Determine the order ID" in prompt:
                    return FakeResponse("Look up ORD-TEST-001")
                return FakeResponse("Your order is in transit.")

        monkeypatch.setattr(genai, "GenerativeModel", FakeModel)

        try:
            trace_id = Tracer(db).start_trace("Where is my order ORD-TEST-001 and when will it arrive?")
            response = AIAgent(db).run("Where is my order ORD-TEST-001 and when will it arrive?")
            Tracer(db).complete_trace(response)
        finally:
            server.shutdown()

        events = db.query(TraceEvent).filter(TraceEvent.trace_id == trace_id).order_by(TraceEvent.sequence_number).all()
        assert [event.event_type for event in events] == [
            "llm_call", "knowledge_base_search", "llm_call",
            "database_query", "external_api_call", "llm_call",
        ]
        assert [event.sequence_number for event in events] == [1, 2, 3, 4, 5, 6]
        assert all(event.duration_ms is not None and event.duration_ms >= 0 for event in events)
        assert events[1].parent_event_id == events[0].id
        assert events[2].parent_event_id == events[0].id
        assert events[3].parent_event_id == events[2].id
        assert events[4].parent_event_id == events[2].id
        assert events[5].parent_event_id == events[4].id

    def test_redaction_never_stores_credentials(self, db):
        tracer = Tracer(db)
        trace_id = tracer.start_trace("redaction")
        @traced_function(event_type="tool_call", component="redaction-test")
        def decorated(payload):
            return {"authorization": "Bearer token", "safe": "visible"}

        decorated({"api_key": "secret-value", "nested": {"password": "pw"}})
        event = db.query(TraceEvent).filter(TraceEvent.trace_id == trace_id).one()
        assert event.input_data == {"args": [{"api_key": "[REDACTED]", "nested": {"password": "[REDACTED]"}}], "kwargs": {}}
        assert event.output_data == {"result": {"authorization": "[REDACTED]", "safe": "visible"}}
        assert redact({"access_token": "secret"})["access_token"] == "[REDACTED]"

    def test_mock_llm_preserves_tracing_and_identifies_mode(self, db, monkeypatch):
        monkeypatch.setenv("MOCK_LLM", "true")
        trace_id = Tracer(db).start_trace("mock request")
        provider = GeminiProvider(db)
        assert provider.generate("test", "llm_1_request_analysis")
        event = db.query(TraceEvent).filter(TraceEvent.trace_id == trace_id).one()
        assert event.event_type == "llm_call"
        assert event.event_metadata["mode"] == "mock"
        assert event.event_metadata["provider"] == "mock"

    def test_context_isolation_between_concurrent_traces(self, db):
        from concurrent.futures import ThreadPoolExecutor

        def run_one(label):
            session = TestSessionLocal()
            try:
                tracer = Tracer(session)
                trace_id = tracer.start_trace(label)
                tracer.create_event(event_type="tool_call", component=label, start_time=1, end_time=1.01)
                tracer.complete_trace(label)
                event = session.query(TraceEvent).filter(TraceEvent.trace_id == trace_id).one()
                return trace_id, event.trace_id, event.component, event.sequence_number
            finally:
                session.close()

        with ThreadPoolExecutor(max_workers=3) as executor:
            results = list(executor.map(run_one, ["A", "B", "C"]))
        assert len({result[0] for result in results}) == 3
        assert all(trace_id == event_trace_id and sequence == 1 for trace_id, event_trace_id, _, sequence in results)
        assert {component for _, _, component, _ in results} == {"A", "B", "C"}

    def test_instrumented_failure_updates_event(self, db):
        Tracer(db).start_trace("failure")

        @traced_function(event_type="database_query", component="failure-test")
        def failing_query():
            raise RuntimeError("database unavailable")

        with pytest.raises(RuntimeError, match="database unavailable"):
            failing_query()
        event = db.query(TraceEvent).filter(TraceEvent.component == "failure-test").one()
        assert event.status == "failed"
        assert event.error_message == "database unavailable"

    def test_agent_route_marks_agent_failure(self, db, monkeypatch):
        import app.main as main
        from app.schemas import AgentRequest

        class FailingAgent:
            def __init__(self, _db):
                pass

            def run(self, _message):
                raise RuntimeError("provider unavailable")

        monkeypatch.setattr(main, "AIAgent", FailingAgent)
        result = main.run_agent(AgentRequest(message="fail this request"), db)
        assert result["status"] == "failed"
        assert result["trace_id"]
        trace = db.query(Trace).filter(Trace.trace_id == result["trace_id"]).one()
        assert trace.status == "failed"
        assert trace.output == "provider unavailable"

    def test_agent_request_rejects_empty_input(self):
        with pytest.raises(ValidationError):
            AgentRequest(message="")

    def test_missing_order_fails_through_agent_route(self, db, monkeypatch):
        import app.main as main

        monkeypatch.setenv("MOCK_LLM", "true")
        result = main.run_agent(AgentRequest(message="Where is order ORD-9999?"), db)
        assert result["status"] == "failed"
        trace = db.query(Trace).filter(Trace.trace_id == result["trace_id"]).one()
        event = db.query(TraceEvent).filter(TraceEvent.trace_id == trace.trace_id).order_by(TraceEvent.sequence_number).all()
        assert trace.status == "failed"
        assert event[-1].event_type == "database_query"
        assert event[-1].status == "failed"
        assert "ORD-9999" in event[-1].error_message

    def test_order_api_failure_fails_through_agent_route(self, db, sample_order, monkeypatch):
        import app.main as main

        monkeypatch.setenv("MOCK_LLM", "true")
        monkeypatch.setenv("ORDER_MANAGEMENT_API_URL", "http://127.0.0.1:9")
        order_id = sample_order.order_id
        result = main.run_agent(AgentRequest(message=f"Where is order {sample_order.order_id}?"), db)
        trace = db.query(Trace).filter(Trace.trace_id == result["trace_id"]).one()
        events = db.query(TraceEvent).filter(TraceEvent.trace_id == trace.trace_id).order_by(TraceEvent.sequence_number).all()
        assert result["status"] == "failed"
        assert trace.status == "failed"
        assert events[-1].event_type == "external_api_call"
        assert events[-1].status == "failed"
        assert events[-1].error_message

    def test_gemini_failure_fails_without_mock_fallback(self, db, monkeypatch):
        import app.main as main

        class FailingModel:
            def __init__(self, _model_name):
                raise RuntimeError("Gemini quota exhausted")

        monkeypatch.setenv("MOCK_LLM", "false")
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        monkeypatch.setattr(genai, "GenerativeModel", FailingModel)
        result = main.run_agent(AgentRequest(message="Where is order ORD-1001?"), db)
        trace = db.query(Trace).filter(Trace.trace_id == result["trace_id"]).one()
        event = db.query(TraceEvent).filter(TraceEvent.trace_id == trace.trace_id).one()
        assert result["status"] == "failed"
        assert trace.status == "failed"
        assert event.status == "failed"
        assert "Gemini quota exhausted" in event.error_message

    def test_concurrent_agent_routes_keep_traces_isolated(self, db, sample_order, monkeypatch):
        import app.main as main

        monkeypatch.setenv("MOCK_LLM", "true")
        monkeypatch.setenv("ORDER_MANAGEMENT_API_URL", "http://127.0.0.1:9")
        order_id = sample_order.order_id

        def run_one(label):
            session = TestSessionLocal()
            try:
                result = main.run_agent(AgentRequest(message=f"{label} order {order_id}"), session)
                trace = session.query(Trace).filter(Trace.trace_id == result["trace_id"]).one()
                events = session.query(TraceEvent).filter(TraceEvent.trace_id == trace.trace_id).all()
                return trace.trace_id, {event.trace_id for event in events}, [event.sequence_number for event in events]
            finally:
                session.close()

        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=3) as executor:
            results = list(executor.map(run_one, ["A", "B", "C"]))
        assert len({trace_id for trace_id, _, _ in results}) == 3
        assert all(trace_ids == {trace_id} for trace_id, trace_ids, _ in results)
        assert all(sequences == list(range(1, 6)) for _, _, sequences in results)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

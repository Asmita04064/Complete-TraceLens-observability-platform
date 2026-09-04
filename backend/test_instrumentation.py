"""Automated tests for the instrumentation and real agent execution."""

import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session

from app.database import SessionLocal, Base, engine
from app.models import Trace, TraceEvent
from app.models.agent import Order, Customer
from app.instrumentation import Tracer, set_current_trace_id, get_current_trace_id, clear_trace_context
from app.agent import AIAgent, OrderService


# Fixtures
@pytest.fixture(scope="function")
def db():
    """Create a fresh database for each test."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)


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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

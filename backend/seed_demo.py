from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.database import Base, SessionLocal, engine
from app.models import Trace, TraceEvent


DEMO_TRACES = [
    {
        "input": "Where is my order?",
        "output": "Your order is currently out for delivery.",
        "status": "completed",
        "events": [
            ("llm_call", "gemini", 842, "success"),
            ("tool_call", "order_service", 120, "success"),
            ("database_query", "postgresql", 35, "success"),
        ],
    },
    {
        "input": "Why was my payment declined?",
        "output": "Your payment was declined by the issuing bank.",
        "status": "completed",
        "events": [
            ("llm_call", "gemini", 710, "success"),
            ("tool_call", "payment_service", 184, "success"),
            ("database_query", "postgresql", 42, "success"),
        ],
    },
    {
        "input": "Cancel my order",
        "output": "Cancellation failed because the order is already in transit.",
        "status": "failed",
        "events": [
            ("llm_call", "gemini", 610, "success"),
            ("tool_call", "order_service", 220, "failed"),
        ],
    },
]


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        created = 0
        for item in DEMO_TRACES:
            if db.query(Trace).filter(Trace.input == item["input"]).first():
                continue
            started_at = datetime.now(timezone.utc) - timedelta(minutes=created + 1)
            trace = Trace(
                trace_id=f"tr_{uuid4().hex[:12]}",
                started_at=started_at,
                completed_at=started_at + timedelta(milliseconds=sum(event[2] for event in item["events"])),
                status=item["status"],
                input=item["input"],
                output=item["output"],
                duration_ms=sum(event[2] for event in item["events"]),
            )
            db.add(trace)
            db.flush()
            parent_id = None
            for sequence, (event_type, component, duration, status) in enumerate(item["events"], 1):
                event = TraceEvent(
                    event_id=f"evt_{uuid4().hex[:12]}",
                    trace_id=trace.trace_id,
                    parent_event_id=parent_id,
                    sequence_number=sequence,
                    event_type=event_type,
                    component=component,
                    timestamp=started_at + timedelta(milliseconds=sequence),
                    duration_ms=duration,
                    status=status,
                    error_message="Order service rejected cancellation" if status == "failed" else None,
                )
                db.add(event)
                db.flush()
                parent_id = event.id
            created += 1
        db.commit()
        print(f"Seed complete: created {created} demo traces.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TraceEvent(Base):
    __tablename__ = "trace_events"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    event_id: Mapped[str] = mapped_column(
    String(100),
    nullable=False,
    unique=True,
    index=True,
    )

    trace_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("traces.trace_id"),
        nullable=False,
        index=True,
    )

    parent_event_id: Mapped[int | None] = mapped_column(
    Integer,
    ForeignKey("trace_events.id"),
    nullable=True,
    index=True,
    )

    sequence_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    event_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    component: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    timestamp: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    duration_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    input_data: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    output_data: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    event_metadata: Mapped[dict | None] = mapped_column(
    "metadata",
    JSON,
    nullable=True,
    )
    
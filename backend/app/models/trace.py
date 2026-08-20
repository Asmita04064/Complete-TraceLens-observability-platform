from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Trace(Base):
    __tablename__ = "traces"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    trace_id: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    input: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    output: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    duration_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
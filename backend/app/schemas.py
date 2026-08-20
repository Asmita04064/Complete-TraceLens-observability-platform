from pydantic import BaseModel
from typing import Optional


# ============================================================
# TRACE CREATE
# ============================================================

class TraceCreate(BaseModel):
    input: str


# ============================================================
# TRACE RESPONSE
# ============================================================

class TraceResponse(BaseModel):
    trace_id: str
    status: str


# ============================================================
# TRACE COMPLETE
# ============================================================

class TraceComplete(BaseModel):
    status: str = "completed"
    output: Optional[str] = None


# ============================================================
# TRACE FAIL
# ============================================================

class TraceFail(BaseModel):
    error_message: str


# ============================================================
# TRACE EVENT CREATE
# ============================================================

class TraceEventCreate(BaseModel):
    event_type: str
    component: Optional[str] = None
    sequence_number: int
    parent_event_id: Optional[int] = None

    input_data: Optional[dict] = None
    output_data: Optional[dict] = None

    status: str = "success"

    duration_ms: Optional[int] = None
    error_message: Optional[str] = None
    metadata: Optional[dict] = None


# ============================================================
# TRACE EVENT RESPONSE
# ============================================================

class TraceEventResponse(BaseModel):
    id: int
    event_id: str
    trace_id: str
    event_type: str
    component: Optional[str]
    sequence_number: int
    parent_event_id: Optional[int]
    status: str


# ============================================================
# TRACE EVENT DETAIL
# ============================================================

class TraceEventDetail(BaseModel):
    event_id: str
    event_type: str
    component: Optional[str]
    sequence_number: int
    parent_event_id: Optional[int]
    status: str
    duration_ms: Optional[int]


# ============================================================
# TRACE DETAIL RESPONSE
# ============================================================

class TraceDetailResponse(BaseModel):
    trace_id: str
    status: str
    input: Optional[str]
    output: Optional[str]
    duration_ms: Optional[int]

    events: list[TraceEventDetail]


# ============================================================
# TRACE LIST ITEM
# ============================================================

class TraceListItem(BaseModel):
    trace_id: str
    status: str
    input: Optional[str]
    output: Optional[str]
    started_at: str
    completed_at: Optional[str]
    duration_ms: Optional[int]
    event_count: int
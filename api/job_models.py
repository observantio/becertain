from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

from api.requests import AnalyzeRequest


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    DELETED = "deleted"


class AnalyzeJobCreateRequest(AnalyzeRequest):
    pass


class AnalyzeJobCreateResponse(BaseModel):
    job_id: str
    report_id: str
    status: JobStatus
    created_at: datetime
    tenant_id: str
    requested_by: str


class AnalyzeJobSummary(BaseModel):
    job_id: str
    report_id: str
    status: JobStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    error: Optional[str] = None
    summary_preview: Optional[str] = None
    tenant_id: str
    requested_by: str


class AnalyzeJobListResponse(BaseModel):
    items: list[AnalyzeJobSummary]
    next_cursor: Optional[str] = None


class AnalyzeJobResultResponse(BaseModel):
    job_id: str
    report_id: str
    status: JobStatus
    tenant_id: str
    requested_by: str
    result: Optional[dict[str, Any]] = None


class AnalyzeReportResponse(BaseModel):
    job_id: str
    report_id: str
    status: JobStatus
    tenant_id: str
    requested_by: str
    result: Optional[dict[str, Any]] = None


class AnalyzeReportDeleteResponse(BaseModel):
    report_id: str
    status: JobStatus = Field(default=JobStatus.DELETED)
    deleted: bool = True

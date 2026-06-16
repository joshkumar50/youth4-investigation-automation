"""
Pydantic schemas (DTOs) for all API request/response contracts.
"""
import uuid
from datetime import datetime
from typing import Any
from pydantic import BaseModel, EmailStr, Field, field_validator, ConfigDict

from app.models.models import (
    UserRole, CaseStatus, CasePriority, EvidenceType,
    EvidenceCategory, ProcessingStatus, EntityType,
    ThreatLevel, EventType,
)


# ─────────────────────────────────────────
# Base
# ─────────────────────────────────────────

class APIResponse(BaseModel):
    success: bool = True
    message: str = "OK"


# ─────────────────────────────────────────
# Auth
# ─────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=2, max_length=255)
    role: UserRole = UserRole.INVESTIGATOR


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime


# ─────────────────────────────────────────
# Cases
# ─────────────────────────────────────────

class CaseCreateRequest(BaseModel):
    title: str = Field(min_length=3, max_length=500)
    description: str | None = None
    priority: CasePriority = CasePriority.MEDIUM
    tags: list[str] | None = None


class CaseUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=500)
    description: str | None = None
    status: CaseStatus | None = None
    priority: CasePriority | None = None
    tags: list[str] | None = None


class CaseMetricsResponse(BaseModel):
    total_evidence: int
    processed_evidence: int
    pending_evidence: int
    total_entities: int
    total_timeline_events: int
    total_relationships: int
    processing_duration_seconds: float | None
    investigation_acceleration: float  # % time saved vs manual
    threat_score_average: float


class CaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: str | None
    case_number: str
    status: CaseStatus
    priority: CasePriority
    tags: list[str] | None
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime
    metrics: CaseMetricsResponse | None = None


class CaseListResponse(BaseModel):
    items: list[CaseResponse]
    total: int
    page: int
    page_size: int


# ─────────────────────────────────────────
# Evidence
# ─────────────────────────────────────────

class EvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    case_id: uuid.UUID
    filename: str
    original_filename: str
    file_type: EvidenceType
    category: EvidenceCategory
    category_confidence: float
    size_bytes: int
    mime_type: str | None
    processing_status: ProcessingStatus
    processing_error: str | None
    threat_level: ThreatLevel
    threat_score: float
    uploaded_by: uuid.UUID
    created_at: datetime
    processed_at: datetime | None
    extraction_metadata: dict | None


class EvidenceUploadResponse(BaseModel):
    evidence_id: uuid.UUID
    filename: str
    size_bytes: int
    processing_status: ProcessingStatus
    task_id: str
    message: str


class EvidenceStatusResponse(BaseModel):
    evidence_id: uuid.UUID
    processing_status: ProcessingStatus
    progress_percent: int
    current_stage: str
    processing_error: str | None
    estimated_completion_seconds: int | None


# ─────────────────────────────────────────
# Entities
# ─────────────────────────────────────────

class EntityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    case_id: uuid.UUID
    evidence_id: uuid.UUID
    entity_type: EntityType
    value: str
    normalized_value: str
    confidence: float
    frequency: int
    context: str | None
    is_primary: bool
    threat_relevance: float
    created_at: datetime


class EntitySummary(BaseModel):
    entity_type: EntityType
    count: int
    top_values: list[str]


# ─────────────────────────────────────────
# Timeline
# ─────────────────────────────────────────

class TimelineEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    case_id: uuid.UUID
    evidence_id: uuid.UUID | None
    entity_id: uuid.UUID | None
    event_type: EventType
    title: str
    description: str | None
    event_timestamp: datetime | None
    confidence: float
    created_at: datetime


# ─────────────────────────────────────────
# Graph / Relationships
# ─────────────────────────────────────────

class GraphNode(BaseModel):
    id: str
    label: str
    entity_type: EntityType
    frequency: int
    threat_relevance: float
    is_primary: bool
    group: int  # for community coloring


class GraphEdge(BaseModel):
    source: str
    target: str
    relationship_type: str
    weight: float
    evidence_count: int


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    total_nodes: int
    total_edges: int
    communities: int


# ─────────────────────────────────────────
# Threats
# ─────────────────────────────────────────

class ThreatInsight(BaseModel):
    id: str
    title: str
    description: str
    threat_level: ThreatLevel
    threat_score: float
    entity_ids: list[str]
    evidence_ids: list[str]
    recommendation: str
    confidence: float


class ThreatResponse(BaseModel):
    case_id: uuid.UUID
    overall_threat_level: ThreatLevel
    overall_threat_score: float
    insights: list[ThreatInsight]
    total_critical: int
    total_high: int
    total_medium: int
    total_low: int


# ─────────────────────────────────────────
# Copilot
# ─────────────────────────────────────────

class CopilotQueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    include_evidence_context: bool = True
    history: list[dict] = Field(default_factory=list)


class CopilotSource(BaseModel):
    evidence_id: str
    filename: str
    snippet: str
    relevance_score: float


class CopilotResponse(BaseModel):
    query: str
    response: str
    sources: list[CopilotSource]
    generated_at: datetime
    model_used: str
    confidence: float


# ─────────────────────────────────────────
# Dashboard
# ─────────────────────────────────────────

class DashboardMetrics(BaseModel):
    total_cases: int
    active_cases: int
    total_evidence_files: int
    total_entities_detected: int
    total_processing_time_saved_hours: float
    files_processed_today: int
    average_case_resolution_hours: float
    cases_by_priority: dict[str, int]
    cases_by_status: dict[str, int]
    evidence_by_type: dict[str, int]
    evidence_by_category: dict[str, int]
    recent_activity: list[dict[str, Any]]

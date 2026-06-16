"""
SQLAlchemy ORM Models — all database tables.
"""
import enum
import uuid
from datetime import datetime
from typing import Any
from sqlalchemy import (
    Boolean, DateTime, Enum, Float, ForeignKey, Integer,
    String, Text, func, JSON
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


# ─────────────────────────────────────────
# Enums
# ─────────────────────────────────────────

class UserRole(str, enum.Enum):
    ADMIN = "admin"
    SUPERVISOR = "supervisor"
    INVESTIGATOR = "investigator"


class CaseStatus(str, enum.Enum):
    ACTIVE = "active"
    CLOSED = "closed"
    ARCHIVED = "archived"
    PENDING_REVIEW = "pending_review"


class CasePriority(str, enum.Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class EvidenceType(str, enum.Enum):
    PDF = "pdf"
    IMAGE = "image"
    VIDEO = "video"
    DOCUMENT = "document"
    CHAT_EXPORT = "chat_export"
    AUDIO = "audio"
    OTHER = "other"


class EvidenceCategory(str, enum.Enum):
    COMMUNICATION = "communication"
    FINANCIAL = "financial"
    LOCATION = "location"
    IDENTITY = "identity"
    MEDIA = "media"
    LEGAL = "legal"
    THREAT = "threat"
    OTHER = "other"


class ProcessingStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"
    DUPLICATE = "duplicate"


class EntityType(str, enum.Enum):
    PERSON = "PERSON"
    ORGANIZATION = "ORG"
    LOCATION = "GPE"
    DATE = "DATE"
    PHONE = "PHONE"
    EMAIL = "EMAIL"
    URL = "URL"
    MONEY = "MONEY"
    ID_NUMBER = "ID_NUMBER"
    VEHICLE = "VEHICLE"
    WEAPON = "WEAPON"
    EVENT = "EVENT"
    OTHER = "OTHER"


class ThreatLevel(str, enum.Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


class EventType(str, enum.Enum):
    FILE_CREATED = "file_created"
    COMMUNICATION_SENT = "communication_sent"
    COMMUNICATION_RECEIVED = "communication_received"
    LOCATION_VISIT = "location_visit"
    TRANSACTION = "transaction"
    ENTITY_MENTION = "entity_mention"
    INCIDENT = "incident"
    DOCUMENT_SIGNED = "document_signed"


# ─────────────────────────────────────────
# Models
# ─────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.INVESTIGATOR, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    cases: Mapped[list["Case"]] = relationship("Case", back_populates="created_by_user", lazy="select")


class Case(Base):
    __tablename__ = "cases"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    case_number: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    status: Mapped[CaseStatus] = mapped_column(Enum(CaseStatus), default=CaseStatus.ACTIVE, nullable=False, index=True)
    priority: Mapped[CasePriority] = mapped_column(Enum(CasePriority), default=CasePriority.MEDIUM, nullable=False, index=True)
    tags: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_by_user: Mapped["User"] = relationship("User", back_populates="cases")
    evidence: Mapped[list["Evidence"]] = relationship("Evidence", back_populates="case", cascade="all, delete-orphan", lazy="select")
    entities: Mapped[list["Entity"]] = relationship("Entity", back_populates="case", cascade="all, delete-orphan", lazy="select")
    timeline_events: Mapped[list["TimelineEvent"]] = relationship("TimelineEvent", back_populates="case", cascade="all, delete-orphan", lazy="select")
    relationships_: Mapped[list["EntityRelationship"]] = relationship("EntityRelationship", back_populates="case", cascade="all, delete-orphan", lazy="select")
    investigation_notes: Mapped[list["InvestigationNote"]] = relationship("InvestigationNote", back_populates="case", cascade="all, delete-orphan", lazy="select")


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cases.id"), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[EvidenceType] = mapped_column(Enum(EvidenceType), nullable=False)
    category: Mapped[EvidenceCategory] = mapped_column(Enum(EvidenceCategory), default=EvidenceCategory.OTHER, nullable=False, index=True)
    category_confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    processing_status: Mapped[ProcessingStatus] = mapped_column(Enum(ProcessingStatus), default=ProcessingStatus.PENDING, nullable=False, index=True)
    processing_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    extraction_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    file_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    file_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    threat_level: Mapped[ThreatLevel] = mapped_column(Enum(ThreatLevel), default=ThreatLevel.INFORMATIONAL, nullable=False)
    threat_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    case: Mapped["Case"] = relationship("Case", back_populates="evidence")
    entities: Mapped[list["Entity"]] = relationship("Entity", back_populates="evidence", cascade="all, delete-orphan", lazy="select")
    timeline_events: Mapped[list["TimelineEvent"]] = relationship("TimelineEvent", back_populates="evidence", lazy="select")


class Entity(Base):
    __tablename__ = "entities"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cases.id"), nullable=False, index=True)
    evidence_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("evidence.id"), nullable=False, index=True)
    entity_type: Mapped[EntityType] = mapped_column(Enum(EntityType), nullable=False, index=True)
    value: Mapped[str] = mapped_column(String(1000), nullable=False, index=True)
    normalized_value: Mapped[str] = mapped_column(String(1000), nullable=False, index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    frequency: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    context: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    threat_relevance: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    case: Mapped["Case"] = relationship("Case", back_populates="entities")
    evidence: Mapped["Evidence"] = relationship("Evidence", back_populates="entities")


class EntityRelationship(Base):
    __tablename__ = "entity_relationships"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cases.id"), nullable=False, index=True)
    source_entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("entities.id"), nullable=False)
    target_entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("entities.id"), nullable=False)
    relationship_type: Mapped[str] = mapped_column(String(100), nullable=False)
    weight: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    evidence_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    case: Mapped["Case"] = relationship("Case", back_populates="relationships_")
    source_entity: Mapped["Entity"] = relationship("Entity", foreign_keys=[source_entity_id])
    target_entity: Mapped["Entity"] = relationship("Entity", foreign_keys=[target_entity_id])


class TimelineEvent(Base):
    __tablename__ = "timeline_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cases.id"), nullable=False, index=True)
    evidence_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("evidence.id"), nullable=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("entities.id"), nullable=True)
    event_type: Mapped[EventType] = mapped_column(Enum(EventType), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    case: Mapped["Case"] = relationship("Case", back_populates="timeline_events")
    evidence: Mapped["Evidence"] = relationship("Evidence", back_populates="timeline_events")


class InvestigationNote(Base):
    __tablename__ = "investigation_notes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cases.id"), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    note_type: Mapped[str] = mapped_column(String(50), default="ai_generated", nullable=False)
    generated_by: Mapped[str] = mapped_column(String(100), default="system", nullable=False)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    case: Mapped["Case"] = relationship("Case", back_populates="investigation_notes")

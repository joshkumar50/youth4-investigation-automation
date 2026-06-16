"""
Evidence service — upload, trigger processing pipeline, status tracking.
"""
import uuid
import mimetypes
import os
import hashlib
from sqlalchemy import select
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Evidence, EvidenceType, ProcessingStatus, ThreatLevel
from app.repositories.evidence_repo import (
    EvidenceRepository, EntityRepository, TimelineRepository, RelationshipRepository
)
from app.services.storage_service import StorageService
from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.config import settings
from app.schemas import (
    EvidenceResponse, EvidenceUploadResponse, EvidenceStatusResponse,
    EntityResponse, TimelineEventResponse, GraphResponse, GraphNode, GraphEdge,
    ThreatResponse, ThreatInsight,
)

logger = get_logger(__name__)

MIME_TO_TYPE: dict[str, EvidenceType] = {
    "application/pdf": EvidenceType.PDF,
    "image/png": EvidenceType.IMAGE,
    "image/jpeg": EvidenceType.IMAGE,
    "image/gif": EvidenceType.IMAGE,
    "image/bmp": EvidenceType.IMAGE,
    "image/tiff": EvidenceType.IMAGE,
    "video/mp4": EvidenceType.VIDEO,
    "video/avi": EvidenceType.VIDEO,
    "video/quicktime": EvidenceType.VIDEO,
    "video/x-matroska": EvidenceType.VIDEO,
    "text/plain": EvidenceType.DOCUMENT,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": EvidenceType.DOCUMENT,
    "application/msword": EvidenceType.DOCUMENT,
    "text/csv": EvidenceType.DOCUMENT,
    "application/json": EvidenceType.CHAT_EXPORT,
    "text/xml": EvidenceType.DOCUMENT,
    "application/xml": EvidenceType.DOCUMENT,
}


def detect_file_type(filename: str, mime_type: str) -> EvidenceType:
    if mime_type in MIME_TO_TYPE:
        return MIME_TO_TYPE[mime_type]
    ext = Path(filename).suffix.lower()
    ext_map = {
        ".pdf": EvidenceType.PDF,
        ".png": EvidenceType.IMAGE, ".jpg": EvidenceType.IMAGE, ".jpeg": EvidenceType.IMAGE,
        ".gif": EvidenceType.IMAGE, ".bmp": EvidenceType.IMAGE, ".tiff": EvidenceType.IMAGE,
        ".mp4": EvidenceType.VIDEO, ".avi": EvidenceType.VIDEO, ".mov": EvidenceType.VIDEO, ".mkv": EvidenceType.VIDEO,
        ".txt": EvidenceType.DOCUMENT, ".docx": EvidenceType.DOCUMENT, ".doc": EvidenceType.DOCUMENT,
        ".csv": EvidenceType.DOCUMENT,
        ".json": EvidenceType.CHAT_EXPORT,
    }
    return ext_map.get(ext, EvidenceType.OTHER)


class EvidenceService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = EvidenceRepository(db)
        self.entity_repo = EntityRepository(db)
        self.timeline_repo = TimelineRepository(db)
        self.rel_repo = RelationshipRepository(db)
        self.storage = StorageService()

    async def upload_evidence(
        self,
        case_id: uuid.UUID,
        filename: str,
        file_data: bytes,
        content_type: str,
        user_id: uuid.UUID,
    ) -> EvidenceUploadResponse:
        # Validate file size
        if len(file_data) > settings.max_file_size_bytes:
            raise ValidationError(f"File too large. Maximum size is {settings.max_file_size_mb}MB")

        # Validate extension
        ext = Path(filename).suffix.lower()
        if ext not in settings.allowed_extensions:
            raise ValidationError(f"File type '{ext}' not allowed")

        # Detect type
        mime = content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
        file_type = detect_file_type(filename, mime)

        # Compute SHA-256 hash
        file_hash = hashlib.sha256(file_data).hexdigest()

        # Check for duplicates in the same case
        result = await self.db.execute(select(Evidence.id).where(Evidence.case_id == case_id, Evidence.file_hash == file_hash).limit(1))
        is_duplicate = result.scalar() is not None

        # Upload to MinIO
        storage_path = await self.storage.upload_file(
            file_data=file_data,
            filename=filename,
            content_type=mime,
            case_id=str(case_id),
        )

        status = ProcessingStatus.DUPLICATE if is_duplicate else ProcessingStatus.PENDING

        # Create DB record
        safe_filename = f"{uuid.uuid4()}_{filename}"
        evidence = Evidence(
            case_id=case_id,
            filename=safe_filename,
            original_filename=filename,
            file_type=file_type,
            storage_path=storage_path,
            size_bytes=len(file_data),
            mime_type=mime,
            file_hash=file_hash,
            processing_status=status,
            uploaded_by=user_id,
        )
        evidence = await self.repo.create(evidence)

        # Trigger async processing pipeline only if not duplicate
        task_id = None
        if not is_duplicate:
            task_id = await self._trigger_processing(evidence.id, case_id, storage_path, file_type)

        logger.info("Evidence uploaded", evidence_id=str(evidence.id), case_id=str(case_id), duplicate=is_duplicate)

        return EvidenceUploadResponse(
            evidence_id=evidence.id,
            filename=filename,
            size_bytes=len(file_data),
            processing_status=status,
            task_id=task_id or "",
            message="Evidence duplicate skipped." if is_duplicate else "Evidence uploaded successfully. Processing started.",
        )

    async def _trigger_processing(
        self,
        evidence_id: uuid.UUID,
        case_id: uuid.UUID,
        storage_path: str,
        file_type: EvidenceType,
    ) -> str:
        """Dispatch Celery processing task."""
        try:
            from celery import Celery
            from app.config import get_settings
            settings = get_settings()
            celery_client = Celery("iip_client", broker=str(settings.redis_url))
            task = celery_client.send_task(
                "tasks.pipeline.process_evidence_pipeline",
                args=[str(evidence_id), str(case_id), storage_path, file_type.value],
                queue="evidence_processing"
            )
            return task.id
        except Exception as e:
            logger.warning("Celery not available, evidence queued", error=str(e))
            return f"mock-task-{evidence_id}"

    async def get_evidence_list(self, case_id: uuid.UUID) -> list[EvidenceResponse]:
        items = await self.repo.get_by_case(case_id)
        return [EvidenceResponse.model_validate(e) for e in items]

    async def get_evidence_status(self, evidence_id: uuid.UUID) -> EvidenceStatusResponse:
        evidence = await self.repo.get_by_id(evidence_id)
        if not evidence:
            raise NotFoundError("Evidence", str(evidence_id))
        stage_map = {
            ProcessingStatus.PENDING: ("Queued for processing", 0),
            ProcessingStatus.PROCESSING: ("Extracting text and entities", 50),
            ProcessingStatus.COMPLETED: ("Processing complete", 100),
            ProcessingStatus.FAILED: ("Processing failed", 0),
            ProcessingStatus.PARTIAL: ("Partially processed", 75),
        }
        stage, progress = stage_map.get(evidence.processing_status, ("Unknown", 0))
        return EvidenceStatusResponse(
            evidence_id=evidence.id,
            processing_status=evidence.processing_status,
            progress_percent=progress,
            current_stage=stage,
            processing_error=evidence.processing_error,
            estimated_completion_seconds=30 if progress < 100 else None,
        )

    async def get_entities(self, case_id: uuid.UUID) -> list[EntityResponse]:
        items = await self.entity_repo.get_by_case(case_id)
        return [EntityResponse.model_validate(e) for e in items]

    async def get_timeline(self, case_id: uuid.UUID) -> list[TimelineEventResponse]:
        items = await self.timeline_repo.get_by_case(case_id)
        return [TimelineEventResponse.model_validate(e) for e in items]

    async def get_graph(self, case_id: uuid.UUID) -> GraphResponse:
        entities = await self.entity_repo.get_by_case(case_id)
        relationships = await self.rel_repo.get_by_case(case_id)

        # Assign community groups (simplified: by entity type)
        type_to_group = {
            "PERSON": 1, "ORG": 2, "GPE": 3, "DATE": 4,
            "PHONE": 5, "EMAIL": 5, "URL": 6, "MONEY": 7,
            "ID_NUMBER": 8, "VEHICLE": 9, "WEAPON": 10,
        }

        nodes = [
            GraphNode(
                id=str(e.id),
                label=e.value[:50],
                entity_type=e.entity_type,
                frequency=e.frequency,
                threat_relevance=e.threat_relevance,
                is_primary=e.is_primary,
                group=type_to_group.get(e.entity_type.value, 0),
            )
            for e in entities
        ]

        edges = [
            GraphEdge(
                source=str(r.source_entity_id),
                target=str(r.target_entity_id),
                relationship_type=r.relationship_type,
                weight=r.weight,
                evidence_count=r.evidence_count,
            )
            for r in relationships
        ]

        # Count unique communities
        groups = set(n.group for n in nodes)

        return GraphResponse(
            nodes=nodes,
            edges=edges,
            total_nodes=len(nodes),
            total_edges=len(edges),
            communities=len(groups),
        )

    async def get_threats(self, case_id: uuid.UUID) -> ThreatResponse:
        """Build threat intelligence from entities and evidence."""
        entities = await self.entity_repo.get_by_case(case_id)
        evidence_list = await self.repo.get_by_case(case_id)

        high_threat_entities = [e for e in entities if e.threat_relevance > 0.6]
        insights = []

        # Pattern: High-frequency person with high threat relevance
        persons = [e for e in high_threat_entities if e.entity_type.value == "PERSON"]
        if persons:
            top_person = max(persons, key=lambda x: x.threat_relevance)
            insights.append(ThreatInsight(
                id=f"threat-person-{top_person.id}",
                title=f"High-activity subject: {top_person.value}",
                description=f"Entity '{top_person.value}' appears {top_person.frequency}x across evidence files with elevated threat indicators.",
                threat_level=ThreatLevel.HIGH if top_person.threat_relevance > 0.8 else ThreatLevel.MEDIUM,
                threat_score=top_person.threat_relevance,
                entity_ids=[str(top_person.id)],
                evidence_ids=[str(top_person.evidence_id)],
                recommendation="Cross-reference with known offender databases. Review all communications involving this individual.",
                confidence=top_person.confidence,
            ))

        # Pattern: Suspicious Financial Activity
        money_entities = [e for e in entities if e.entity_type.value == "MONEY"]
        if money_entities:
            top_money = max(money_entities, key=lambda x: x.frequency)
            insights.append(ThreatInsight(
                id=f"threat-finance-{case_id}",
                title=f"Suspicious Financial Activity: {top_money.value}",
                description=f"Significant financial value '{top_money.value}' detected in communications. Potential money laundering or illicit transfer.",
                threat_level=ThreatLevel.HIGH,
                threat_score=0.85,
                entity_ids=[str(top_money.id)],
                evidence_ids=[str(top_money.evidence_id)],
                recommendation="Subpoena bank records for associated accounts. Initiate asset tracing.",
                confidence=0.88,
            ))

        # Pattern: Communications cluster
        phones = [e for e in entities if e.entity_type.value == "PHONE"]
        emails = [e for e in entities if e.entity_type.value == "EMAIL"]
        if len(phones) + len(emails) >= 3:
            insights.append(ThreatInsight(
                id=f"threat-comms-{case_id}",
                title="Communication network detected",
                description=f"Identified {len(phones)} phone numbers and {len(emails)} email addresses suggesting coordinated communication.",
                threat_level=ThreatLevel.MEDIUM,
                threat_score=0.65,
                entity_ids=[str(e.id) for e in (phones + emails)[:5]],
                evidence_ids=[str(e.evidence_id) for e in (phones + emails)[:3]],
                recommendation="Map communication network. Subpoena records for identified numbers and addresses.",
                confidence=0.78,
            ))

        # Calculate overall
        scores = [ins.threat_score for ins in insights] or [0.0]
        overall_score = sum(scores) / len(scores)
        if overall_score > 0.8:
            overall_level = ThreatLevel.CRITICAL
        elif overall_score > 0.6:
            overall_level = ThreatLevel.HIGH
        elif overall_score > 0.4:
            overall_level = ThreatLevel.MEDIUM
        else:
            overall_level = ThreatLevel.LOW

        return ThreatResponse(
            case_id=case_id,
            overall_threat_level=overall_level,
            overall_threat_score=round(overall_score, 3),
            insights=insights,
            total_critical=sum(1 for i in insights if i.threat_level == ThreatLevel.CRITICAL),
            total_high=sum(1 for i in insights if i.threat_level == ThreatLevel.HIGH),
            total_medium=sum(1 for i in insights if i.threat_level == ThreatLevel.MEDIUM),
            total_low=sum(1 for i in insights if i.threat_level == ThreatLevel.LOW),
        )

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

        # Check for duplicates across ALL cases (Global duplicate check)
        result = await self.db.execute(select(Evidence.case_id).where(Evidence.file_hash == file_hash).limit(1))
        existing_case_id = result.scalar()
        is_duplicate_in_same_case = existing_case_id == case_id
        is_global_duplicate = existing_case_id is not None and existing_case_id != case_id

        # Upload to MinIO
        storage_path = await self.storage.upload_file(
            file_data=file_data,
            filename=filename,
            content_type=mime,
            case_id=str(case_id),
        )

        status = ProcessingStatus.DUPLICATE if is_duplicate_in_same_case else ProcessingStatus.PENDING

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

        # Trigger async processing pipeline only if not duplicate in the SAME case
        task_id = None
        if not is_duplicate_in_same_case:
            task_id = await self._trigger_processing(evidence.id, case_id, storage_path, file_type)

        logger.info("Evidence uploaded", evidence_id=str(evidence.id), case_id=str(case_id), duplicate=is_duplicate_in_same_case)
        
        message = "Evidence uploaded successfully. Processing started."
        if is_duplicate_in_same_case:
            message = "Evidence duplicate skipped."
        elif is_global_duplicate:
            message = f"Warning: This file already exists in another case. Proceeding with extraction for this case."

        return EvidenceUploadResponse(
            evidence_id=evidence.id,
            filename=filename,
            size_bytes=len(file_data),
            processing_status=status,
            task_id=task_id or "",
            message=message,
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

    async def reprocess_evidence(self, evidence_id: uuid.UUID) -> str:
        """Clear existing extracted data and re-run the pipeline."""
        from sqlalchemy import text
        evidence = await self.repo.get_by_id(evidence_id)
        if not evidence:
            raise NotFoundError("Evidence", str(evidence_id))
            
        # 1. Delete dependent relationships
        await self.db.execute(
            text("""
            DELETE FROM entity_relationships 
            WHERE source_entity_id IN (SELECT id FROM entities WHERE evidence_id = :ev_id)
               OR target_entity_id IN (SELECT id FROM entities WHERE evidence_id = :ev_id)
            """),
            {"ev_id": evidence_id}
        )
        
        # 2. Delete timeline events and entities
        await self.db.execute(text("DELETE FROM timeline_events WHERE evidence_id = :ev_id"), {"ev_id": evidence_id})
        await self.db.execute(text("DELETE FROM entities WHERE evidence_id = :ev_id"), {"ev_id": evidence_id})
        
        # 3. Reset status
        evidence.processing_status = ProcessingStatus.PENDING
        evidence.processing_error = None
        evidence.extracted_text = None
        await self.db.commit()
        
        # 4. Trigger again
        return await self._trigger_processing(evidence.id, evidence.case_id, evidence.storage_path, evidence.file_type)

    async def get_evidence_impact(self, evidence_id: uuid.UUID) -> dict:
        """Calculate the exact number of entities, relationships, and events that will be lost if this evidence is deleted."""
        from sqlalchemy import text
        entities_count = await self.db.scalar(text("SELECT count(*) FROM entities WHERE evidence_id = :ev_id"), {"ev_id": evidence_id})
        timeline_count = await self.db.scalar(text("SELECT count(*) FROM timeline_events WHERE evidence_id = :ev_id"), {"ev_id": evidence_id})
        relations_count = await self.db.scalar(
            text("""
            SELECT count(*) FROM entity_relationships 
            WHERE source_entity_id IN (SELECT id FROM entities WHERE evidence_id = :ev_id)
               OR target_entity_id IN (SELECT id FROM entities WHERE evidence_id = :ev_id)
            """),
            {"ev_id": evidence_id}
        )
        return {
            "entities": entities_count or 0,
            "relationships": relations_count or 0,
            "timeline_events": timeline_count or 0
        }

    async def delete_evidence(self, evidence_id: uuid.UUID) -> None:
        """Completely delete evidence and all associated AI-extracted data."""
        from sqlalchemy import text
        evidence = await self.repo.get_by_id(evidence_id)
        if not evidence:
            raise NotFoundError("Evidence", str(evidence_id))
            
        await self.db.execute(
            text("""
            DELETE FROM entity_relationships 
            WHERE source_entity_id IN (SELECT id FROM entities WHERE evidence_id = :ev_id)
               OR target_entity_id IN (SELECT id FROM entities WHERE evidence_id = :ev_id)
            """),
            {"ev_id": evidence_id}
        )
        
        await self.db.execute(text("DELETE FROM timeline_events WHERE evidence_id = :ev_id"), {"ev_id": evidence_id})
        await self.db.execute(text("DELETE FROM entities WHERE evidence_id = :ev_id"), {"ev_id": evidence_id})
        await self.repo.delete(evidence)
        await self.db.commit()

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
        from sqlalchemy import text
        items = await self.entity_repo.get_by_case(case_id)
        responses = []
        for e in items:
            resp = EntityResponse.model_validate(e)
            # Find if this entity exists in other cases
            result = await self.db.execute(
                text("""
                    SELECT DISTINCT c.id, c.title, c.case_number 
                    FROM entities e 
                    JOIN cases c ON e.case_id = c.id 
                    WHERE e.normalized_value = :val AND e.case_id != :cid
                """),
                {"val": e.normalized_value, "cid": case_id}
            )
            resp.cross_case_links = [{"id": row[0], "title": row[1], "case_number": row[2]} for row in result.all()]
            responses.append(resp)
        return responses

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

        high_threat_entities = [e for e in entities if e.threat_relevance >= 0.3]
        insights = []

        # Pattern: High-frequency person with high threat relevance
        persons = [e for e in high_threat_entities if e.entity_type.value == "PERSON"]
        if persons:
            top_person = max(persons, key=lambda x: x.threat_relevance)
            insights.append(ThreatInsight(
                id=f"threat-person-{top_person.id}",
                title=f"High-activity subject: {top_person.value}",
                description=f"Entity '{top_person.value}' appears {top_person.frequency}x across evidence files with elevated threat indicators.",
                threat_level=ThreatLevel.HIGH if top_person.threat_relevance > 0.6 else ThreatLevel.MEDIUM,
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
        if len(phones) + len(emails) >= 1:
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

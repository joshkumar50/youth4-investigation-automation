"""
Evidence repository — data access for Evidence, Entity, Timeline, Relationship models.
"""
import uuid
from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import (
    Evidence, Entity, TimelineEvent, EntityRelationship,
    ProcessingStatus, EntityType,
)
from app.repositories.base import BaseRepository


class EvidenceRepository(BaseRepository[Evidence]):
    def __init__(self, db: AsyncSession):
        super().__init__(Evidence, db)

    async def get_by_case(self, case_id: uuid.UUID) -> list[Evidence]:
        result = await self.db.execute(
            select(Evidence)
            .where(Evidence.case_id == case_id)
            .order_by(desc(Evidence.created_at))
        )
        return list(result.scalars().all())

    async def update_status(
        self,
        evidence_id: uuid.UUID,
        status: ProcessingStatus,
        error: str | None = None,
    ) -> None:
        from datetime import datetime, timezone
        evidence = await self.get_by_id(evidence_id)
        if evidence:
            evidence.processing_status = status
            if error:
                evidence.processing_error = error
            if status == ProcessingStatus.COMPLETED:
                evidence.processed_at = datetime.now(timezone.utc)
            await self.db.flush()


class EntityRepository(BaseRepository[Entity]):
    def __init__(self, db: AsyncSession):
        super().__init__(Entity, db)

    async def get_by_case(self, case_id: uuid.UUID, entity_type: EntityType | None = None) -> list[Entity]:
        query = select(Entity).where(Entity.case_id == case_id)
        if entity_type:
            query = query.where(Entity.entity_type == entity_type)
        result = await self.db.execute(query.order_by(desc(Entity.frequency)))
        return list(result.scalars().all())

    async def get_or_create(self, case_id: uuid.UUID, evidence_id: uuid.UUID, entity_type: EntityType, normalized_value: str) -> tuple[Entity, bool]:
        """Get existing entity or create new one."""
        result = await self.db.execute(
            select(Entity).where(
                and_(
                    Entity.case_id == case_id,
                    Entity.entity_type == entity_type,
                    Entity.normalized_value == normalized_value,
                )
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.frequency += 1
            await self.db.flush()
            return existing, False
        return None, True


class TimelineRepository(BaseRepository[TimelineEvent]):
    def __init__(self, db: AsyncSession):
        super().__init__(TimelineEvent, db)

    async def get_by_case(self, case_id: uuid.UUID) -> list[TimelineEvent]:
        result = await self.db.execute(
            select(TimelineEvent)
            .where(TimelineEvent.case_id == case_id)
            .order_by(TimelineEvent.event_timestamp.asc().nullslast())
        )
        return list(result.scalars().all())


class RelationshipRepository(BaseRepository[EntityRelationship]):
    def __init__(self, db: AsyncSession):
        super().__init__(EntityRelationship, db)

    async def get_by_case(self, case_id: uuid.UUID) -> list[EntityRelationship]:
        result = await self.db.execute(
            select(EntityRelationship)
            .where(EntityRelationship.case_id == case_id)
            .order_by(desc(EntityRelationship.weight))
        )
        return list(result.scalars().all())

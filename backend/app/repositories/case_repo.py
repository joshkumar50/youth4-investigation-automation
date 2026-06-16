"""
Case repository — data access for Case model.
"""
import uuid
import random
import string
from datetime import datetime, timezone
from sqlalchemy import select, func, and_, desc
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Case, Evidence, Entity, TimelineEvent, EntityRelationship, CaseStatus
from app.repositories.base import BaseRepository


def generate_case_number() -> str:
    """Generate a unique case number like CASE-2024-XXXX."""
    year = datetime.now(timezone.utc).year
    suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"CASE-{year}-{suffix}"


class CaseRepository(BaseRepository[Case]):
    def __init__(self, db: AsyncSession):
        super().__init__(Case, db)

    async def get_all_for_user(
        self,
        user_id: uuid.UUID,
        skip: int = 0,
        limit: int = 20,
        status: CaseStatus | None = None,
    ) -> tuple[list[Case], int]:
        query = select(Case).where(Case.created_by == user_id)
        if status:
            query = query.where(Case.status == status)
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await self.db.execute(count_query)
        total = count_result.scalar_one()
        result = await self.db.execute(
            query.order_by(desc(Case.updated_at)).offset(skip).limit(limit)
        )
        return list(result.scalars().all()), total

    async def get_with_metrics(self, case_id: uuid.UUID) -> Case | None:
        result = await self.db.execute(
            select(Case)
            .where(Case.id == case_id)
            .options(
                selectinload(Case.evidence),
                selectinload(Case.entities),
                selectinload(Case.timeline_events),
            )
        )
        return result.scalar_one_or_none()

    async def get_metrics(self, case_id: uuid.UUID) -> dict:
        # Evidence counts
        ev_total = await self.db.execute(
            select(func.count(Evidence.id)).where(Evidence.case_id == case_id)
        )
        ev_processed = await self.db.execute(
            select(func.count(Evidence.id)).where(
                and_(Evidence.case_id == case_id, Evidence.processing_status == "completed")
            )
        )
        ev_pending = await self.db.execute(
            select(func.count(Evidence.id)).where(
                and_(Evidence.case_id == case_id, Evidence.processing_status == "pending")
            )
        )
        entity_count = await self.db.execute(
            select(func.count(Entity.id)).where(Entity.case_id == case_id)
        )
        timeline_count = await self.db.execute(
            select(func.count(TimelineEvent.id)).where(TimelineEvent.case_id == case_id)
        )
        rel_count = await self.db.execute(
            select(func.count(EntityRelationship.id)).where(EntityRelationship.case_id == case_id)
        )
        threat_avg = await self.db.execute(
            select(func.avg(Evidence.threat_score)).where(Evidence.case_id == case_id)
        )
        return {
            "total_evidence": ev_total.scalar_one() or 0,
            "processed_evidence": ev_processed.scalar_one() or 0,
            "pending_evidence": ev_pending.scalar_one() or 0,
            "total_entities": entity_count.scalar_one() or 0,
            "total_timeline_events": timeline_count.scalar_one() or 0,
            "total_relationships": rel_count.scalar_one() or 0,
            "threat_score_average": float(threat_avg.scalar_one() or 0.0),
        }

    async def get_all_cases_metrics(self) -> dict:
        total_cases = await self.count()
        active_cases = await self.db.execute(
            select(func.count(Case.id)).where(Case.status == CaseStatus.ACTIVE)
        )
        return {
            "total_cases": total_cases,
            "active_cases": active_cases.scalar_one() or 0,
        }

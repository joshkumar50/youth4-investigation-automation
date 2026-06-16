"""
Case service — business logic for case management.
"""
import uuid
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Case, CaseStatus
from app.repositories.case_repo import CaseRepository, generate_case_number
from app.core.exceptions import NotFoundError, ForbiddenError
from app.schemas import (
    CaseCreateRequest, CaseUpdateRequest, CaseResponse,
    CaseListResponse, CaseMetricsResponse, DashboardMetrics,
)


class CaseService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = CaseRepository(db)

    async def create_case(self, request: CaseCreateRequest, user_id: uuid.UUID) -> CaseResponse:
        case = Case(
            title=request.title,
            description=request.description,
            case_number=generate_case_number(),
            priority=request.priority,
            tags=request.tags,
            created_by=user_id,
        )
        case = await self.repo.create(case)
        metrics = await self._build_metrics(case.id)
        response = CaseResponse.model_validate(case)
        response.metrics = metrics
        return response

    async def list_cases(
        self,
        user_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
        status: CaseStatus | None = None,
    ) -> CaseListResponse:
        skip = (page - 1) * page_size
        cases, total = await self.repo.get_all_for_user(user_id, skip=skip, limit=page_size, status=status)
        items = []
        for case in cases:
            metrics = await self._build_metrics(case.id)
            resp = CaseResponse.model_validate(case)
            resp.metrics = metrics
            items.append(resp)
        return CaseListResponse(items=items, total=total, page=page, page_size=page_size)

    async def get_case(self, case_id: uuid.UUID, user_id: uuid.UUID) -> CaseResponse:
        case = await self.repo.get_by_id(case_id)
        if not case:
            raise NotFoundError("Case", str(case_id))
        metrics = await self._build_metrics(case_id)
        resp = CaseResponse.model_validate(case)
        resp.metrics = metrics
        return resp

    async def update_case(self, case_id: uuid.UUID, request: CaseUpdateRequest, user_id: uuid.UUID) -> CaseResponse:
        case = await self.repo.get_by_id(case_id)
        if not case:
            raise NotFoundError("Case", str(case_id))
        if request.title is not None:
            case.title = request.title
        if request.description is not None:
            case.description = request.description
        if request.status is not None:
            case.status = request.status
        if request.priority is not None:
            case.priority = request.priority
        if request.tags is not None:
            case.tags = request.tags
        case = await self.repo.update(case)
        metrics = await self._build_metrics(case_id)
        resp = CaseResponse.model_validate(case)
        resp.metrics = metrics
        return resp

    async def delete_case(self, case_id: uuid.UUID, user_id: uuid.UUID) -> None:
        case = await self.repo.get_by_id(case_id)
        if not case:
            raise NotFoundError("Case", str(case_id))
        await self.repo.delete(case)

    async def get_dashboard_metrics(self) -> DashboardMetrics:
        from sqlalchemy import select, func
        from app.models import Evidence, Entity, Case, EvidenceType, EvidenceCategory, CasePriority, CaseStatus

        case_metrics = await self.repo.get_all_cases_metrics()

        ev_total = await self.db.execute(select(func.count()).select_from(Evidence))
        entity_total = await self.db.execute(select(func.count()).select_from(Entity))

        # Cases by priority
        from sqlalchemy import case as sa_case
        priority_result = await self.db.execute(
            select(Case.priority, func.count(Case.id)).group_by(Case.priority)
        )
        cases_by_priority = {row[0].value: row[1] for row in priority_result.all()}

        status_result = await self.db.execute(
            select(Case.status, func.count(Case.id)).group_by(Case.status)
        )
        cases_by_status = {row[0].value: row[1] for row in status_result.all()}

        ev_type_result = await self.db.execute(
            select(Evidence.file_type, func.count(Evidence.id)).group_by(Evidence.file_type)
        )
        evidence_by_type = {row[0].value: row[1] for row in ev_type_result.all()}

        ev_cat_result = await self.db.execute(
            select(Evidence.category, func.count(Evidence.id)).group_by(Evidence.category)
        )
        evidence_by_category = {row[0].value: row[1] for row in ev_cat_result.all()}

        total_evidence = ev_total.scalar_one() or 0
        total_entities = entity_total.scalar_one() or 0

        return DashboardMetrics(
            total_cases=case_metrics["total_cases"],
            active_cases=case_metrics["active_cases"],
            total_evidence_files=total_evidence,
            total_entities_detected=total_entities,
            total_processing_time_saved_hours=round(total_evidence * 0.75, 2),
            files_processed_today=0,
            average_case_resolution_hours=48.5,
            cases_by_priority=cases_by_priority,
            cases_by_status=cases_by_status,
            evidence_by_type=evidence_by_type,
            evidence_by_category=evidence_by_category,
            recent_activity=[],
        )

    async def _build_metrics(self, case_id: uuid.UUID) -> CaseMetricsResponse:
        raw = await self.repo.get_metrics(case_id)
        total = raw["total_evidence"]
        processed = raw["processed_evidence"]
        acceleration = round((processed / total * 100) if total > 0 else 0.0, 1)
        return CaseMetricsResponse(
            total_evidence=total,
            processed_evidence=processed,
            pending_evidence=raw["pending_evidence"],
            total_entities=raw["total_entities"],
            total_timeline_events=raw["total_timeline_events"],
            total_relationships=raw["total_relationships"],
            processing_duration_seconds=None,
            investigation_acceleration=acceleration,
            threat_score_average=raw["threat_score_average"],
        )

"""
Cases router — CRUD + metrics + dashboard.
"""
import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_active_user
from app.models import User, CaseStatus
from app.services.case_service import CaseService
from app.schemas import (
    CaseCreateRequest, CaseUpdateRequest, CaseResponse,
    CaseListResponse, CaseMetricsResponse, DashboardMetrics,
)

router = APIRouter(prefix="/api/v1", tags=["Cases"])


@router.get("/dashboard/metrics", response_model=DashboardMetrics)
async def get_dashboard_metrics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get global investigation intelligence dashboard metrics."""
    svc = CaseService(db)
    return await svc.get_dashboard_metrics()


@router.get("/cases", response_model=CaseListResponse)
async def list_cases(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: CaseStatus | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List all cases for the current investigator."""
    svc = CaseService(db)
    return await svc.list_cases(current_user.id, page=page, page_size=page_size, status=status)


@router.post("/cases", response_model=CaseResponse, status_code=201)
async def create_case(
    request: CaseCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Create a new investigation case."""
    svc = CaseService(db)
    return await svc.create_case(request, current_user.id)


@router.get("/cases/{case_id}", response_model=CaseResponse)
async def get_case(
    case_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get a specific case with metrics."""
    svc = CaseService(db)
    return await svc.get_case(case_id, current_user.id)


@router.put("/cases/{case_id}", response_model=CaseResponse)
async def update_case(
    case_id: uuid.UUID,
    request: CaseUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Update case metadata, status, or priority."""
    svc = CaseService(db)
    return await svc.update_case(case_id, request, current_user.id)


@router.delete("/cases/{case_id}", status_code=204)
async def delete_case(
    case_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Delete a case and all associated evidence."""
    svc = CaseService(db)
    await svc.delete_case(case_id, current_user.id)

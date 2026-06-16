"""
Evidence router — upload, list, status, entities, timeline, graph, threats, copilot.
"""
import uuid
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_active_user
from app.models import User
from app.services.evidence_service import EvidenceService
from app.schemas import (
    EvidenceResponse, EvidenceUploadResponse, EvidenceStatusResponse,
    EntityResponse, TimelineEventResponse, GraphResponse,
    ThreatResponse, CopilotQueryRequest, CopilotResponse,
)

router = APIRouter(prefix="/api/v1", tags=["Evidence & Intelligence"])


@router.post("/cases/{case_id}/evidence/upload", response_model=list[EvidenceUploadResponse], status_code=201)
async def upload_evidence(
    case_id: uuid.UUID,
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Upload one or more evidence files to a case. Triggers automatic processing pipeline."""
    svc = EvidenceService(db)
    results = []
    for file in files:
        data = await file.read()
        result = await svc.upload_evidence(
            case_id=case_id,
            filename=file.filename or "unknown",
            file_data=data,
            content_type=file.content_type or "",
            user_id=current_user.id,
        )
        results.append(result)
    return results


@router.get("/cases/{case_id}/evidence", response_model=list[EvidenceResponse])
async def list_evidence(
    case_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List all evidence files for a case."""
    svc = EvidenceService(db)
    return await svc.get_evidence_list(case_id)


@router.get("/evidence/{evidence_id}/status", response_model=EvidenceStatusResponse)
async def get_evidence_status(
    evidence_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get real-time processing status for a specific evidence file."""
    svc = EvidenceService(db)
    return await svc.get_evidence_status(evidence_id)


@router.get("/cases/{case_id}/entities", response_model=list[EntityResponse])
async def get_entities(
    case_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get all extracted entities for a case."""
    svc = EvidenceService(db)
    return await svc.get_entities(case_id)


@router.get("/cases/{case_id}/timeline", response_model=list[TimelineEventResponse])
async def get_timeline(
    case_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get chronologically ordered timeline of events for a case."""
    svc = EvidenceService(db)
    return await svc.get_timeline(case_id)


@router.get("/cases/{case_id}/graph", response_model=GraphResponse)
async def get_graph(
    case_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get entity relationship graph data for visualization."""
    svc = EvidenceService(db)
    return await svc.get_graph(case_id)


@router.get("/cases/{case_id}/threats", response_model=ThreatResponse)
async def get_threats(
    case_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get prioritized threat intelligence for a case."""
    svc = EvidenceService(db)
    return await svc.get_threats(case_id)


@router.post("/cases/{case_id}/copilot/query", response_model=CopilotResponse)
async def copilot_query(
    case_id: uuid.UUID,
    request: CopilotQueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Query the Investigation Copilot AI for insights about this case."""
    from app.services.copilot_service import CopilotService
    svc = CopilotService(db)
    return await svc.query(case_id, request)


@router.post("/cases/{case_id}/report/generate")
async def generate_report(
    case_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Generate a professional PDF investigation report for a case."""
    from app.services.report_service import ReportService
    svc = ReportService(db)
    pdf_bytes = await svc.generate_pdf(case_id)
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=investigation_report_{case_id}.pdf"},
    )

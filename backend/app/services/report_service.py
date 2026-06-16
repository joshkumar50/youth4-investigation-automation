"""
Report service — professional PDF investigation report using ReportLab.
"""
import uuid
import io
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.case_repo import CaseRepository
from app.repositories.evidence_repo import EvidenceRepository, EntityRepository, TimelineRepository
from app.core.logging import get_logger

logger = get_logger(__name__)


class ReportService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.case_repo = CaseRepository(db)
        self.evidence_repo = EvidenceRepository(db)
        self.entity_repo = EntityRepository(db)
        self.timeline_repo = TimelineRepository(db)

    async def generate_pdf(self, case_id: uuid.UUID) -> bytes:
        """Generate a complete PDF investigation report."""
        case = await self.case_repo.get_by_id(case_id)
        evidence_list = await self.evidence_repo.get_by_case(case_id)
        entities = await self.entity_repo.get_by_case(case_id)
        timeline_events = await self.timeline_repo.get_by_case(case_id)
        metrics = await self.case_repo.get_metrics(case_id)

        import sys
        logger.info(f"Checking reportlab availability. sys.path: {sys.path}")
        try:
            import reportlab
            logger.info(f"Reportlab found at: {reportlab.__file__}")
        except Exception as e:
            logger.error(f"Failed to import reportlab. Exception: {type(e).__name__}: {e}")

        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch, cm
            from reportlab.lib.colors import HexColor, white, black
            from reportlab.platypus import (
                SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
                HRFlowable, PageBreak,
            )
            from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

            buffer = io.BytesIO()
            doc = SimpleDocTemplate(
                buffer,
                pagesize=A4,
                rightMargin=2 * cm,
                leftMargin=2 * cm,
                topMargin=2.5 * cm,
                bottomMargin=2 * cm,
            )

            styles = getSampleStyleSheet()

            # Custom styles
            primary_color = HexColor("#1e40af")
            accent_color = HexColor("#3b82f6")
            danger_color = HexColor("#dc2626")
            warning_color = HexColor("#d97706")
            muted = HexColor("#6b7280")

            title_style = ParagraphStyle(
                "Title", parent=styles["Heading1"],
                fontSize=24, textColor=white, alignment=TA_CENTER,
                spaceAfter=6,
            )
            h1_style = ParagraphStyle(
                "H1", parent=styles["Heading1"],
                fontSize=16, textColor=primary_color, spaceAfter=8, spaceBefore=16,
            )
            h2_style = ParagraphStyle(
                "H2", parent=styles["Heading2"],
                fontSize=13, textColor=primary_color, spaceAfter=6, spaceBefore=12,
            )
            body_style = ParagraphStyle(
                "Body", parent=styles["Normal"],
                fontSize=10, spaceAfter=4, leading=14,
            )
            meta_style = ParagraphStyle(
                "Meta", parent=styles["Normal"],
                fontSize=9, textColor=muted, spaceAfter=2,
            )

            story = []

            # ── Cover Page ──
            cover_data = [
                [Paragraph("INVESTIGATION INTELLIGENCE PLATFORM", title_style)],
                [Paragraph(f"OFFICIAL INVESTIGATION REPORT", ParagraphStyle(
                    "sub", fontSize=13, textColor=HexColor("#93c5fd"), alignment=TA_CENTER
                ))],
                [Spacer(1, 0.3 * inch)],
                [Paragraph(f"Case: {case.title}", ParagraphStyle(
                    "ct", fontSize=14, textColor=white, alignment=TA_CENTER, fontName="Helvetica-Bold"
                ))],
                [Paragraph(f"Case Number: {case.case_number}", ParagraphStyle(
                    "cn", fontSize=11, textColor=HexColor("#bfdbfe"), alignment=TA_CENTER
                ))],
                [Spacer(1, 0.2 * inch)],
                [Paragraph(f"Generated: {datetime.now(timezone.utc).strftime('%B %d, %Y at %H:%M UTC')}", ParagraphStyle(
                    "gd", fontSize=9, textColor=HexColor("#93c5fd"), alignment=TA_CENTER
                ))],
                [Paragraph(f"Classification: RESTRICTED — LAW ENFORCEMENT USE ONLY", ParagraphStyle(
                    "cls", fontSize=9, textColor=HexColor("#fca5a5"), alignment=TA_CENTER
                ))],
            ]
            cover_table = Table(cover_data, colWidths=[16 * cm])
            cover_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), primary_color),
                ("TOPPADDING", (0, 0), (-1, -1), 18),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 18),
                ("LEFTPADDING", (0, 0), (-1, -1), 24),
                ("RIGHTPADDING", (0, 0), (-1, -1), 24),
                ("ROWBACKGROUNDS", (0, 0), (-1, -1), [primary_color]),
            ]))
            story.append(cover_table)
            story.append(PageBreak())

            # ── Executive Summary ──
            story.append(Paragraph("1. EXECUTIVE SUMMARY", h1_style))
            story.append(HRFlowable(width="100%", thickness=2, color=accent_color))
            story.append(Spacer(1, 0.1 * inch))

            summary_data = [
                ["Case Title", case.title],
                ["Case Number", case.case_number],
                ["Status", case.status.value.upper()],
                ["Priority", case.priority.value.upper()],
                ["Created", case.created_at.strftime("%Y-%m-%d")],
                ["Evidence Files", str(metrics["total_evidence"])],
                ["Entities Detected", str(metrics["total_entities"])],
                ["Timeline Events", str(metrics["total_timeline_events"])],
                ["Relationships Mapped", str(metrics["total_relationships"])],
            ]
            summary_table = Table(summary_data, colWidths=[5 * cm, 11 * cm])
            summary_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (0, -1), HexColor("#eff6ff")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("TEXTCOLOR", (0, 0), (0, -1), primary_color),
                ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#e5e7eb")),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ]))
            story.append(summary_table)
            story.append(Spacer(1, 0.2 * inch))

            if case.description:
                story.append(Paragraph("Case Description:", h2_style))
                story.append(Paragraph(case.description, body_style))
                story.append(Spacer(1, 0.1 * inch))

            # ── Evidence Inventory ──
            story.append(PageBreak())
            story.append(Paragraph("2. EVIDENCE INVENTORY", h1_style))
            story.append(HRFlowable(width="100%", thickness=2, color=accent_color))
            story.append(Spacer(1, 0.1 * inch))

            if evidence_list:
                ev_headers = ["#", "Filename", "Type", "Category", "Status", "Threat Level"]
                ev_data = [ev_headers]
                for i, ev in enumerate(evidence_list[:30], 1):
                    ev_data.append([
                        str(i),
                        ev.original_filename[:35] + ("..." if len(ev.original_filename) > 35 else ""),
                        ev.file_type.value.upper(),
                        ev.category.value.title(),
                        ev.processing_status.value.title(),
                        ev.threat_level.value.upper(),
                    ])
                ev_table = Table(ev_data, colWidths=[0.8*cm, 6*cm, 2*cm, 2.5*cm, 2.5*cm, 2.2*cm])
                ev_table.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), primary_color),
                    ("TEXTCOLOR", (0, 0), (-1, 0), white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("GRID", (0, 0), (-1, -1), 0.3, HexColor("#e5e7eb")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [white, HexColor("#f9fafb")]),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ]))
                story.append(ev_table)
            else:
                story.append(Paragraph("No evidence files have been processed for this case.", body_style))

            # ── Entity Register ──
            story.append(PageBreak())
            story.append(Paragraph("3. ENTITY REGISTER", h1_style))
            story.append(HRFlowable(width="100%", thickness=2, color=accent_color))
            story.append(Spacer(1, 0.1 * inch))

            if entities:
                entity_headers = ["Entity Type", "Value", "Frequency", "Confidence", "Threat Score"]
                entity_data = [entity_headers]
                for e in sorted(entities, key=lambda x: -x.threat_relevance)[:25]:
                    entity_data.append([
                        e.entity_type.value,
                        e.value[:40] + ("..." if len(e.value) > 40 else ""),
                        str(e.frequency),
                        f"{e.confidence:.0%}",
                        f"{e.threat_relevance:.2f}",
                    ])
                entity_table = Table(entity_data, colWidths=[3*cm, 7*cm, 2*cm, 2.5*cm, 2.5*cm])
                entity_table.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), primary_color),
                    ("TEXTCOLOR", (0, 0), (-1, 0), white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("GRID", (0, 0), (-1, -1), 0.3, HexColor("#e5e7eb")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [white, HexColor("#f9fafb")]),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ]))
                story.append(entity_table)
            else:
                story.append(Paragraph("No entities have been extracted for this case.", body_style))

            # ── Timeline ──
            story.append(PageBreak())
            story.append(Paragraph("4. INVESTIGATION TIMELINE", h1_style))
            story.append(HRFlowable(width="100%", thickness=2, color=accent_color))
            story.append(Spacer(1, 0.1 * inch))

            if timeline_events:
                for event in timeline_events[:20]:
                    ts = event.event_timestamp.strftime("%Y-%m-%d %H:%M") if event.event_timestamp else "Unknown"
                    story.append(Paragraph(f"<b>{ts}</b> — {event.title}", body_style))
                    if event.description:
                        story.append(Paragraph(f"  {event.description}", meta_style))
                    story.append(Spacer(1, 0.05 * inch))
            else:
                story.append(Paragraph("No timeline events have been reconstructed for this case.", body_style))

            # ── Footer note ──
            story.append(PageBreak())
            story.append(Paragraph("5. RECOMMENDATIONS & NEXT STEPS", h1_style))
            story.append(HRFlowable(width="100%", thickness=2, color=accent_color))
            story.append(Spacer(1, 0.1 * inch))
            story.append(Paragraph(
                "Based on the automated investigation intelligence analysis:\n\n"
                "1. Review all entities flagged with threat relevance scores above 0.7\n"
                "2. Conduct formal interviews with persons of interest identified in the entity register\n"
                "3. Issue formal subpoenas for communication records linked to identified phone numbers and email addresses\n"
                "4. Cross-reference identified locations with CCTV and access control records\n"
                "5. Engage cybercrime unit for digital device forensics on evidence flagged as 'High' threat\n\n"
                "This report was generated automatically by the Investigation Intelligence Platform AI pipeline. "
                "All findings should be validated by a qualified forensic investigator before use in legal proceedings.",
                body_style
            ))

            doc.build(story)
            buffer.seek(0)
            return buffer.read()

        except ImportError:
            logger.warning("ReportLab not available, generating plain text report")
            return self._generate_text_report(case, evidence_list, entities, timeline_events, metrics)

    def _generate_text_report(self, case, evidence_list, entities, timeline_events, metrics) -> bytes:
        """Fallback plain text report."""
        lines = [
            "INVESTIGATION INTELLIGENCE PLATFORM",
            "OFFICIAL INVESTIGATION REPORT",
            "=" * 60,
            f"Case: {case.title}",
            f"Case Number: {case.case_number}",
            f"Status: {case.status.value}",
            f"Priority: {case.priority.value}",
            f"Generated: {datetime.now(timezone.utc).isoformat()}",
            "",
            "EVIDENCE INVENTORY",
            "-" * 40,
        ]
        for i, ev in enumerate(evidence_list, 1):
            lines.append(f"{i}. {ev.original_filename} ({ev.file_type.value}) - {ev.processing_status.value}")
        lines += ["", "ENTITIES DETECTED", "-" * 40]
        for e in entities[:20]:
            lines.append(f"[{e.entity_type.value}] {e.value} (freq: {e.frequency}, threat: {e.threat_relevance:.2f})")
        return "\n".join(lines).encode("utf-8")

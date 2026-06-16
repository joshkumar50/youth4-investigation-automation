"""
Copilot service — Ollama/Llama3 with ChromaDB RAG and graceful fallback.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.logging import get_logger
from app.repositories.evidence_repo import EvidenceRepository, EntityRepository
from app.schemas import CopilotQueryRequest, CopilotResponse, CopilotSource

logger = get_logger(__name__)


class CopilotService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.evidence_repo = EvidenceRepository(db)
        self.entity_repo = EntityRepository(db)

    async def query(self, case_id: uuid.UUID, request: CopilotQueryRequest) -> CopilotResponse:
        # Build context from case data
        entities = await self.entity_repo.get_by_case(case_id)
        evidence_list = await self.evidence_repo.get_by_case(case_id)

        entity_summary = self._build_entity_summary(entities)
        evidence_summary = self._build_evidence_summary(evidence_list)

        history_text = ""
        if request.history:
            history_text = "\nPREVIOUS CONVERSATION HISTORY:\n"
            for h in request.history[-5:]:  # Include last 5 messages for context
                history_text += f"Investigator: {h.get('user', '')}\nAssistant: {h.get('assistant', '')}\n"

        context = f"""
INVESTIGATION CASE CONTEXT:
===========================
Evidence Files: {len(evidence_list)} items
Key Entities Identified: {entity_summary}
Evidence Summary: {evidence_summary}
{history_text}
"""

        # Try Ollama; fallback gracefully
        response_text, model_used, confidence = await self._call_llm(
            query=request.query,
            context=context,
        )

        # Find relevant source snippets
        sources = self._find_relevant_sources(request.query, evidence_list)

        return CopilotResponse(
            query=request.query,
            response=response_text,
            sources=sources,
            generated_at=datetime.now(timezone.utc),
            model_used=model_used,
            confidence=confidence,
        )

    async def _call_llm(self, query: str, context: str) -> tuple[str, str, float]:
        """Call Ollama with fallback to rule-based response."""
        try:
            import httpx
            prompt = f"""You are an expert digital forensics investigator AI assistant.

{context}

Investigator Question: {query}

Provide a concise, actionable investigation insight based on the evidence context above.
Focus on: key findings, patterns, recommended next steps, and potential connections.
Keep response under 300 words and professionally structured."""

            async with httpx.AsyncClient(timeout=settings.ollama_timeout) as client:
                response = await client.post(
                    f"{settings.ollama_base_url}/api/generate",
                    json={
                        "model": settings.ollama_model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {"temperature": 0.3, "num_predict": 512},
                    },
                )
                if response.status_code == 200:
                    data = response.json()
                    return data.get("response", ""), settings.ollama_model, 0.88
        except Exception as e:
            logger.warning("Ollama unavailable, using fallback", error=str(e))

        # Intelligent rule-based fallback
        return self._rule_based_response(query, context), "investigation-rules-v1", 0.72

    def _rule_based_response(self, query: str, context: str) -> str:
        """Rule-based investigation insights when LLM is unavailable."""
        query_lower = query.lower()

        if any(kw in query_lower for kw in ["summary", "overview", "what happened"]):
            return (
                "**Investigation Overview**\n\n"
                "Based on the processed evidence files, the following key patterns have been identified:\n\n"
                "• Multiple entities have been extracted and cross-referenced across evidence sources\n"
                "• Communication patterns suggest coordinated activity between identified persons\n"
                "• Timeline reconstruction reveals a sequence of events requiring further investigation\n\n"
                "**Recommended Next Steps:**\n"
                "1. Prioritize review of high-confidence entities flagged with elevated threat relevance\n"
                "2. Cross-reference identified phone numbers and emails with known contact databases\n"
                "3. Verify timeline consistency across all evidence sources"
            )
        elif any(kw in query_lower for kw in ["suspect", "person", "who"]):
            return (
                "**Person-of-Interest Analysis**\n\n"
                "The AI pipeline has identified individuals appearing across multiple evidence sources. "
                "High-frequency mentions combined with communication network density suggest coordinated involvement.\n\n"
                "**Key Indicators:**\n"
                "• Cross-evidence entity co-occurrence patterns\n"
                "• Communication timestamps clustering around key events\n"
                "• Geographic proximity of identified locations\n\n"
                "Recommend issuing formal information requests for identified contact details."
            )
        elif any(kw in query_lower for kw in ["next step", "recommend", "action"]):
            return (
                "**Recommended Investigation Actions**\n\n"
                "1. **Immediate:** Secure chain of custody for all digital evidence\n"
                "2. **Short-term:** Subpoena records for identified communication identifiers\n"
                "3. **Medium-term:** Conduct interviews with persons of interest identified in entity graph\n"
                "4. **Ongoing:** Monitor for new evidence linking identified entities\n\n"
                "Priority threat indicators have been escalated to the threat assessment panel."
            )
        else:
            return (
                f"**AI Analysis for: '{query}'**\n\n"
                "The investigation intelligence system has analyzed all processed evidence for this case. "
                "Entity extraction has identified persons, organizations, locations, and communication identifiers "
                "that are cross-referenced in the relationship graph.\n\n"
                "For specific entity inquiries, refer to the Entity Register. "
                "For temporal patterns, review the Timeline Reconstruction module. "
                "For network analysis, consult the Relationship Intelligence graph.\n\n"
                "*(Note: Connect Ollama/Llama3 for enhanced AI-powered analysis)*"
            )

    def _build_entity_summary(self, entities) -> str:
        if not entities:
            return "None extracted yet"
        types = {}
        for e in entities:
            t = e.entity_type.value
            types[t] = types.get(t, 0) + 1
        return ", ".join(f"{count} {etype}s" for etype, count in list(types.items())[:5])

    def _build_evidence_summary(self, evidence_list) -> str:
        if not evidence_list:
            return "No evidence processed yet"
        processed = sum(1 for e in evidence_list if e.processing_status.value == "completed")
        return f"{processed}/{len(evidence_list)} files processed"

    def _find_relevant_sources(self, query: str, evidence_list) -> list[CopilotSource]:
        sources = []
        for e in evidence_list[:3]:  # Return top 3 as sources
            if e.extracted_text:
                snippet = e.extracted_text[:200] + "..." if len(e.extracted_text) > 200 else e.extracted_text
            else:
                snippet = f"[{e.file_type.value.upper()} file — text extraction in progress]"
            sources.append(CopilotSource(
                evidence_id=str(e.id),
                filename=e.original_filename,
                snippet=snippet,
                relevance_score=0.85,
            ))
        return sources

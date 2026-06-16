"""
AI Summary Task — Ollama/Llama3 case-level intelligence generation.
"""
import os
import json
from celery.utils.log import get_task_logger
from celery_app import app

logger = get_task_logger(__name__)


@app.task(name="tasks.ai_summary_task.generate_case_summary", queue="ai_tasks")
def generate_case_summary(case_id: str):
    """
    Generate an AI-powered case summary using Ollama/Llama3.
    Triggered when all evidence in a case has been processed.
    """
    logger.info(f"Generating AI summary for case {case_id}")

    try:
        from sqlalchemy import create_engine, text
        DATABASE_URL = os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg2://iip_user:iip_secret_2024@localhost:5432/investigation_db"
        ).replace("postgresql+asyncpg://", "postgresql+psycopg2://")

        engine = create_engine(DATABASE_URL)
        with engine.connect() as conn:
            # Gather case context
            case = conn.execute(
                text("SELECT title, description FROM cases WHERE id = :id"),
                {"id": case_id}
            ).fetchone()

            entities = conn.execute(
                text("SELECT entity_type, value, frequency, threat_relevance FROM entities WHERE case_id = :id ORDER BY threat_relevance DESC LIMIT 20"),
                {"id": case_id}
            ).fetchall()

            ev_count = conn.execute(
                text("SELECT COUNT(*) FROM evidence WHERE case_id = :id AND processing_status = 'completed'"),
                {"id": case_id}
            ).scalar()

        if not case:
            return

        entity_summary = "\n".join(
            f"- [{row[0]}] {row[1]} (freq: {row[2]}, threat: {row[3]:.2f})"
            for row in entities
        )

        prompt = f"""You are an expert digital forensics investigator AI.
        
Case: {case[0]}
Description: {case[1] or 'No description'}
Evidence Files Processed: {ev_count}

Key Entities Identified:
{entity_summary}

Generate a concise 3-paragraph investigation intelligence summary covering:
1. Key findings and primary persons/entities of interest
2. Evidence patterns and communication networks
3. Recommended priority investigation actions

Keep it professional, factual, and actionable."""

        summary = _call_ollama(prompt)

        # Save as investigation note
        with engine.connect() as conn:
            conn.execute(
                text("""
                    INSERT INTO investigation_notes (id, case_id, content, note_type, generated_by, created_at)
                    VALUES (gen_random_uuid(), :case_id, :content, 'ai_summary', :model, now())
                """),
                {
                    "case_id": case_id,
                    "content": summary,
                    "model": f"ollama/{os.getenv('OLLAMA_MODEL', 'llama3')}",
                }
            )
            conn.commit()

        logger.info(f"AI summary generated for case {case_id}")

    except Exception as e:
        logger.error(f"AI summary failed for case {case_id}: {e}")


def _call_ollama(prompt: str) -> str:
    """Call Ollama API for text generation."""
    try:
        import requests
        response = requests.post(
            f"{os.getenv('OLLAMA_BASE_URL', 'http://ollama:11434')}/api/generate",
            json={
                "model": os.getenv("OLLAMA_MODEL", "llama3"),
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.3, "num_predict": 512},
            },
            timeout=120,
        )
        if response.status_code == 200:
            return response.json().get("response", "")
    except Exception as e:
        logger.warning(f"Ollama unavailable: {e}")

    # Fallback
    return (
        "**AI Summary** (Ollama unavailable — connect Llama 3 for enhanced analysis)\n\n"
        "Evidence processing complete. Entity extraction, timeline reconstruction, and relationship mapping "
        "have been completed. Review the Entities, Timeline, and Threats panels for detailed findings.\n\n"
        "Recommended next steps: Review high-threat entities, cross-reference communication identifiers, "
        "and consult the relationship graph for network analysis."
    )

"""
Celery application configuration and task orchestration.
"""
import os
from celery import Celery
from celery.utils.log import get_task_logger

REDIS_URL = os.getenv("REDIS_URL", "redis://:iip_redis_2024@localhost:6379/0")

app = Celery(
    "iip_workers",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=[
        "tasks.ocr_task",
        "tasks.nlp_task",
        "tasks.embedding_task",
        "tasks.graph_task",
        "tasks.timeline_task",
        "tasks.ai_summary_task",
    ],
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "tasks.ocr_task.*": {"queue": "evidence_processing"},
        "tasks.nlp_task.*": {"queue": "evidence_processing"},
        "tasks.embedding_task.*": {"queue": "evidence_processing"},
        "tasks.graph_task.*": {"queue": "graph_tasks"},
        "tasks.timeline_task.*": {"queue": "evidence_processing"},
        "tasks.ai_summary_task.*": {"queue": "ai_tasks"},
    },
    task_soft_time_limit=300,
    task_time_limit=600,
    result_expires=86400,
)

logger = get_task_logger(__name__)


@app.task(bind=True, name="tasks.pipeline.process_evidence_pipeline", queue="evidence_processing")
def process_evidence_pipeline(self, evidence_id: str, case_id: str, storage_path: str, file_type: str):
    """
    Master pipeline task: orchestrates all processing steps for a single evidence file.
    Steps: OCR → NLP → Embedding → Timeline → Graph update
    """
    from tasks.ocr_task import extract_text_task
    from tasks.nlp_task import extract_entities_task
    from tasks.embedding_task import embed_evidence_task
    from tasks.timeline_task import extract_timeline_task
    from tasks.graph_task import update_graph_task

    logger.info(f"Starting pipeline for evidence {evidence_id}")
    _update_evidence_status(evidence_id, "PROCESSING")

    try:
        # Step 1: OCR / Text Extraction
        extraction_result = extract_text_task(evidence_id, storage_path, file_type)

        # Step 2: NLP Entity Extraction
        if extraction_result.get("text"):
            entities = extract_entities_task(evidence_id, case_id, extraction_result["text"])
        else:
            entities = []

        # Step 3: Vector Embedding
        embed_evidence_task(evidence_id, case_id, extraction_result.get("text", ""))

        # Step 4: Timeline Extraction
        extract_timeline_task(evidence_id, case_id, extraction_result, entities)

        # Step 5: Graph Update
        update_graph_task(case_id, entities)

        logger.info(f"Pipeline complete for evidence {evidence_id}")
        _update_evidence_status(evidence_id, "COMPLETED")
        return {"status": "completed", "evidence_id": evidence_id, "entities_found": len(entities)}

    except Exception as exc:
        logger.error(f"Pipeline failed for evidence {evidence_id}: {exc}")
        _update_evidence_status(evidence_id, "FAILED", str(exc))
        raise self.retry(exc=exc, countdown=30, max_retries=3)


def _update_evidence_status(evidence_id: str, status: str, error: str | None = None):
    """Update evidence processing status in DB (synchronous for Celery)."""
    try:
        import sqlalchemy
        from sqlalchemy import create_engine, text
        DATABASE_URL = os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg2://iip_user:iip_secret_2024@localhost:5432/investigation_db"
        ).replace("postgresql+asyncpg://", "postgresql+psycopg2://")

        engine = create_engine(DATABASE_URL)
        with engine.connect() as conn:
            conn.execute(
                text("UPDATE evidence SET processing_status = :status, processing_error = :error WHERE id = :id"),
                {"status": status, "error": error, "id": evidence_id}
            )
            conn.commit()
    except Exception as e:
        logger.error(f"Failed to update evidence status: {e}")


# Re-export for docker-compose CMD
process_evidence_pipeline_ref = process_evidence_pipeline

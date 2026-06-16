"""
Timeline Task — temporal event extraction from evidence and entities.
"""
import os
import re
import json
from datetime import datetime, timezone
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)

# Datetime patterns for extraction
DATE_PATTERNS = [
    re.compile(r"\b(\d{4}[-/]\d{2}[-/]\d{2}(?:[ T]\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:?\d{2})?)?)\b"),
    re.compile(r"\b(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})\b"),
    re.compile(r"\b(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})\b", re.IGNORECASE),
    re.compile(r"\b((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4})\b", re.IGNORECASE),
]


def extract_timeline_task(evidence_id: str, case_id: str, extraction_result: dict, entities: list[dict]):
    """Extract timeline events from evidence and save to DB."""
    text = extraction_result.get("text", "")
    metadata = extraction_result.get("metadata", {})
    events = []

    # Event 1: File creation from metadata
    if "DateTime" in metadata or "CreateDate" in metadata:
        ts_str = metadata.get("DateTime") or metadata.get("CreateDate")
        events.append({
            "event_type": "FILE_CREATED",
            "title": "File created/modified",
            "description": f"File timestamp extracted from metadata: {ts_str}",
            "timestamp_str": ts_str,
            "confidence": 0.95,
        })
    elif "creation_date" in metadata:
        events.append({
            "event_type": "FILE_CREATED",
            "title": "Document created",
            "description": f"Document creation date: {metadata['creation_date']}",
            "timestamp_str": str(metadata["creation_date"]),
            "confidence": 0.90,
        })

    # Event 2: Extract datetime strings from text
    if text:
        date_mentions = _extract_dates_from_text(text[:50000])
        for date_str, context in date_mentions[:15]:
            events.append({
                "event_type": "ENTITY_MENTION",
                "title": f"Date mentioned: {date_str}",
                "description": f"Context: {context[:200]}",
                "timestamp_str": date_str,
                "confidence": 0.70,
            })

    # Event 3: Chat messages get individual events
    if "message_count" in metadata:
        # Parse first few messages as events
        lines = text.split("\n")[:20]
        for line in lines:
            if line.strip():
                events.append({
                    "event_type": "COMMUNICATION_SENT",
                    "title": "Communication event",
                    "description": line.strip()[:200],
                    "timestamp_str": None,
                    "confidence": 0.80,
                })

    # Event 4: Person entities get mention events
    person_entities = [e for e in entities if e.get("entity_type") == "PERSON"][:5]
    for person in person_entities:
        if person.get("context"):
            events.append({
                "event_type": "ENTITY_MENTION",
                "title": f"Person mentioned: {person['value']}",
                "description": person.get("context", "")[:200],
                "timestamp_str": None,
                "confidence": person.get("confidence", 0.75) * 0.85,
            })

    _save_timeline_events(evidence_id, case_id, events[:30])


def _extract_dates_from_text(text: str) -> list[tuple[str, str]]:
    """Extract date strings with surrounding context."""
    results = []
    seen = set()
    for pattern in DATE_PATTERNS:
        for match in pattern.finditer(text):
            date_str = match.group(1)
            if date_str in seen:
                continue
            seen.add(date_str)
            start = max(0, match.start() - 60)
            end = min(len(text), match.end() + 60)
            context = text[start:end].strip()
            results.append((date_str, context))
            if len(results) >= 20:
                break
    return results


def _parse_datetime(date_str: str | None) -> datetime | None:
    """Try to parse a datetime string."""
    if not date_str:
        return None
    formats = [
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%B %d, %Y",
        "%d %B %Y",
        "%b %d, %Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _save_timeline_events(evidence_id: str, case_id: str, events: list[dict]):
    """Persist timeline events to PostgreSQL."""
    if not events:
        return
    try:
        from sqlalchemy import create_engine, text

        DATABASE_URL = os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg2://iip_user:iip_secret_2024@localhost:5432/investigation_db"
        ).replace("postgresql+asyncpg://", "postgresql+psycopg2://")

        engine = create_engine(DATABASE_URL)
        with engine.connect() as conn:
            for event in events:
                ts = _parse_datetime(event.get("timestamp_str"))
                conn.execute(
                    text("""
                        INSERT INTO timeline_events
                            (id, case_id, evidence_id, event_type, title,
                             description, event_timestamp, confidence, created_at)
                        VALUES
                            (gen_random_uuid(), :case_id, :evidence_id, :event_type, :title,
                             :description, :ts, :confidence, now())
                    """),
                    {
                        "case_id": case_id,
                        "evidence_id": evidence_id,
                        "event_type": event["event_type"],
                        "title": event["title"][:400],
                        "description": (event.get("description") or "")[:1000],
                        "ts": ts,
                        "confidence": event["confidence"],
                    }
                )
            conn.commit()
        logger.info(f"Saved {len(events)} timeline events for evidence {evidence_id}")
    except Exception as e:
        logger.error(f"Failed to save timeline events: {e}")

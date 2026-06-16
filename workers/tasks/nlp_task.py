"""
NLP Task — spaCy NER + regex entity extraction pipeline.
"""
import os
import re
import json
import uuid
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)

# ── Regex patterns for structured entities ──
PATTERNS = {
    "PHONE": re.compile(
        r"(?:\+?\d{1,3}[\s\-.]?)?"
        r"(?:\(?\d{3}\)?[\s\-.]?)?"
        r"\d{3}[\s\-.]?\d{4}"
        r"(?:\s?(?:x|ext\.?)\s?\d{1,5})?",
        re.IGNORECASE,
    ),
    "EMAIL": re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"),
    "URL": re.compile(
        r"https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+"
        r"(?::\d+)?(?:/[-\w%!$&'()*+,./:;=?@_~]*)?",
        re.IGNORECASE,
    ),
    "MONEY": re.compile(r"[\$€£¥][\d,]+(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?\s?(?:USD|EUR|GBP|INR|AED)", re.IGNORECASE),
    "ID_NUMBER": re.compile(r"\b(?:[A-Z]{1,3}[-\s]?)?\d{6,12}\b"),
    "VEHICLE": re.compile(r"\b[A-Z]{2,3}[\s\-]?\d{2,4}[\s\-]?[A-Z]{0,4}\b"),
    "SUSPICIOUS_TERM": re.compile(r"\b(hawala|shell company|bribe|laundering|crores?|kickback|fraud)\b", re.IGNORECASE),
}

# Threat-related keywords for scoring
THREAT_KEYWORDS = {
    "kill", "weapon", "gun", "explosive", "bomb", "attack", "threat",
    "ransom", "kidnap", "murder", "illegal", "cocaine", "heroin", "drug",
    "smuggle", "launder", "bribe", "corrupt", "fraud", "trafficking",
    "terror", "hack", "breach", "blackmail", "extort", "hawala", "shell",
    "money", "crore", "transfer", "account", "offshore", "scam", "evade",
    "cargo", "secure number", "intercepted", "apprehended", "suspect",
    "surveillance", "godown", "confiscated",
}

_nlp = None


def get_nlp():
    global _nlp
    if _nlp is None:
        try:
            import spacy
            model = os.getenv("SPACY_MODEL", "en_core_web_sm")
            _nlp = spacy.load(model)
            logger.info(f"spaCy model '{model}' loaded")
        except Exception as e:
            logger.error(f"spaCy load failed: {e}")
            _nlp = None
    return _nlp


def extract_entities_task(evidence_id: str, case_id: str, text: str) -> list[dict]:
    """
    Extract named entities from text using spaCy NER + regex patterns.
    Returns list of entity dicts.
    """
    if not text or not text.strip():
        return []

    entities = []

    # ── spaCy NER ──
    nlp = get_nlp()
    if nlp:
        try:
            # Process in chunks if text is large
            chunk_size = 100000
            for i in range(0, min(len(text), 500000), chunk_size):
                chunk = text[i:i + chunk_size]
                doc = nlp(chunk)
                for ent in doc.ents:
                    if ent.label_ in ("PERSON", "ORG", "GPE", "DATE", "TIME", "EVENT", "MONEY", "CARDINAL"):
                        context_start = max(0, ent.start_char - 80)
                        context_end = min(len(chunk), ent.end_char + 80)
                        context = chunk[context_start:context_end].strip()

                        threat_score = _compute_threat_score(ent.text, context)

                        entities.append({
                            "entity_type": _map_spacy_label(ent.label_),
                            "value": ent.text.strip(),
                            "normalized_value": ent.text.strip().lower(),
                            "confidence": 0.85,
                            "context": context,
                            "threat_relevance": threat_score,
                            "source": "spacy",
                        })
        except Exception as e:
            logger.error(f"spaCy NER failed: {e}")

    # ── Regex patterns ──
    for entity_type, pattern in PATTERNS.items():
        matches = pattern.findall(text[:200000])
        for match in set(matches[:50]):  # Deduplicate, limit
            match_str = match.strip()
            if len(match_str) < 4:
                continue
            
            # Map SUSPICIOUS_TERM to OTHER so it doesn't crash Postgres Enum validation
            db_entity_type = "OTHER" if entity_type == "SUSPICIOUS_TERM" else entity_type
            
            # Artificially boost the threat score for suspicious terms
            if entity_type == "SUSPICIOUS_TERM":
                threat_score = 0.85
            else:
                threat_score = _compute_threat_score(match_str, "")
                
            entities.append({
                "entity_type": db_entity_type,
                "value": match_str,
                "normalized_value": match_str.lower(),
                "confidence": 0.92,
                "context": "",
                "threat_relevance": threat_score,
                "source": "regex",
            })

    # Deduplicate
    seen = set()
    unique_entities = []
    for e in entities:
        key = (e["entity_type"], e["normalized_value"])
        if key not in seen:
            seen.add(key)
            unique_entities.append(e)

    # Persist to DB
    _save_entities(evidence_id, case_id, unique_entities[:200])
    return unique_entities


def _map_spacy_label(label: str) -> str:
    mapping = {
        "PERSON": "PERSON",
        "ORG": "ORG",
        "GPE": "GPE",
        "LOC": "GPE",
        "DATE": "DATE",
        "TIME": "DATE",
        "EVENT": "EVENT",
        "MONEY": "MONEY",
        "CARDINAL": "OTHER",
    }
    return mapping.get(label, "OTHER")


def _compute_threat_score(value: str, context: str) -> float:
    """Compute threat relevance score based on keywords in entity and context."""
    combined = f"{value} {context}".lower()
    keyword_hits = sum(1 for kw in THREAT_KEYWORDS if kw in combined)
    base_score = min(keyword_hits * 0.15, 0.9)
    return round(base_score, 3)


def _save_entities(evidence_id: str, case_id: str, entities: list[dict]):
    """Persist extracted entities to PostgreSQL."""
    if not entities:
        return
    try:
        from sqlalchemy import create_engine, text
        DATABASE_URL = os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg2://iip_user:iip_secret_2024@localhost:5432/investigation_db"
        ).replace("postgresql+asyncpg://", "postgresql+psycopg2://")

        max_threat = max((ent["threat_relevance"] for ent in entities), default=0.0)
        threat_level = "INFORMATIONAL"
        if max_threat > 0.8:
            threat_level = "CRITICAL"
        elif max_threat > 0.6:
            threat_level = "HIGH"
        elif max_threat > 0.4:
            threat_level = "MEDIUM"
        elif max_threat > 0.2:
            threat_level = "LOW"

        engine = create_engine(DATABASE_URL)
        with engine.connect() as conn:
            for ent in entities:
                conn.execute(
                    text("""
                        INSERT INTO entities
                            (id, case_id, evidence_id, entity_type, value,
                             normalized_value, confidence, frequency, context,
                             threat_relevance, is_primary, created_at)
                        VALUES
                            (gen_random_uuid(), :case_id, :evidence_id, :entity_type, :value,
                             :normalized_value, :confidence, 1, :context,
                             :threat_relevance, false, now())
                        ON CONFLICT DO NOTHING
                    """),
                    {
                        "case_id": case_id,
                        "evidence_id": evidence_id,
                        "entity_type": ent["entity_type"],
                        "value": ent["value"][:500],
                        "normalized_value": ent["normalized_value"][:500],
                        "confidence": ent["confidence"],
                        "context": (ent.get("context") or "")[:500],
                        "threat_relevance": ent["threat_relevance"],
                    }
                )
            
            # Update the evidence file's overall threat score
            conn.execute(
                text("UPDATE evidence SET threat_level = :tl, threat_score = :ts WHERE id = :eid"),
                {"tl": threat_level, "ts": max_threat, "eid": evidence_id}
            )
            conn.commit()
        logger.info(f"Saved {len(entities)} entities for evidence {evidence_id}")
    except Exception as e:
        logger.error(f"Failed to save entities: {e}")

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
    "MONEY": re.compile(r"[\$€£¥₹]\s?[\d,\.]+|(?:USD|EUR|GBP|INR|AED)\s?[\d,\.]+(?:\s?(?:Crores|Lakhs|Million|Billion|K|M|B))?|[\d,\.]+(?:\s?(?:Crores|Lakhs|Million|Billion|K|M|B))?\s?(?:USD|EUR|GBP|INR|AED)", re.IGNORECASE),
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
    semantic_relationships = []

    # ── NER Extraction ──
    # Route non-English (Indic) text to Ollama for translation + extraction
    if re.search(r'[\u0900-\u0D7F]', text):
        # Process large documents in chunks so the local LLM doesn't timeout
        chunk_size = 4000
        for i in range(0, min(len(text), 40000), chunk_size):
            chunk = text[i:i + chunk_size]
            if len(chunk.strip()) < 10:
                continue
            try:
                ollama_entities, ollama_rels = _extract_entities_ollama(chunk)
                entities.extend(ollama_entities)
                semantic_relationships.extend(ollama_rels)
            except Exception as e:
                logger.error(f"Ollama NER failed on chunk {i}: {e}")
    else:
        # Use fast spaCy for standard English text
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
        for match in set(matches[:500]):  # Deduplicate, limit
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
    _save_entities(evidence_id, case_id, unique_entities[:2000])
    if semantic_relationships:
        _save_semantic_relationships(case_id, semantic_relationships)
    return unique_entities


def _map_spacy_label(label: str) -> str:
    mapping = {
        "PERSON": "PERSON",
        "ORG": "ORGANIZATION",
        "GPE": "LOCATION",
        "LOC": "LOCATION",
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


def _save_semantic_relationships(case_id: str, relationships: list[dict]):
    """Persist semantic relationships extracted by LLM to PostgreSQL."""
    if not relationships:
        return
    try:
        from sqlalchemy import create_engine, text
        DATABASE_URL = os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg2://iip_user:iip_secret_2024@localhost:5432/investigation_db"
        ).replace("postgresql+asyncpg://", "postgresql+psycopg2://")

        engine = create_engine(DATABASE_URL)
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT id, normalized_value FROM entities WHERE case_id = :case_id"),
                {"case_id": case_id}
            )
            entity_lookup = {
                row[1]: str(row[0])
                for row in result.fetchall()
            }

            for rel in relationships:
                src_id = entity_lookup.get(rel.get("source", "").lower())
                tgt_id = entity_lookup.get(rel.get("target", "").lower())

                if not src_id or not tgt_id or src_id == tgt_id:
                    continue

                conn.execute(
                    text("""
                        INSERT INTO entity_relationships
                            (id, case_id, source_entity_id, target_entity_id,
                             relationship_type, weight, evidence_count, created_at)
                        VALUES
                            (gen_random_uuid(), :case_id, :src_id, :tgt_id,
                             :rel_type, :weight, 1, now())
                        ON CONFLICT DO NOTHING
                    """),
                    {
                        "case_id": case_id,
                        "src_id": src_id,
                        "tgt_id": tgt_id,
                        "rel_type": rel.get("relationship_type", "associated_with").lower(),
                        "weight": 2.0,
                    }
                )
            conn.commit()
        logger.info(f"Saved {len(relationships)} semantic relationships for case {case_id}")
    except Exception as e:
        logger.error(f"Failed to save semantic relationships: {e}")


def _extract_entities_ollama(text: str) -> tuple[list[dict], list[dict]]:
    """Call Ollama for multilingual NER and semantic relationships using JSON mode."""
    import requests
    import json
    
    prompt = f"""You are a digital forensics AI. 
TASK 1: Extract EVERY SINGLE PERSON, ORGANIZATION, and LOCATION from the text. Be exhaustive. Do not miss any.
TASK 2: If the text is not in English, transliterate the names into standard English characters (e.g., శ్రీచరణ్ -> Sri Charan).
TASK 3: Extract semantic relationships between the PERSON entities you found.

Respond ONLY with a JSON object containing two keys: "entities" (array) and "relationships" (array).

"entities" objects must have:
- "entity_type": exactly "PERSON", "ORGANIZATION", or "LOCATION"
- "value": original string
- "normalized_value": English transliteration (in lowercase)
- "context": short 5-10 word snippet

"relationships" objects must have:
- "source": the normalized_value of the first PERSON
- "target": the normalized_value of the second PERSON
- "relationship_type": the actual semantic relationship (e.g., "father", "daughter", "wife", "husband", "friend")

Text to analyze:
{text}"""

    response = requests.post(
        f"{os.getenv('OLLAMA_BASE_URL', 'http://ollama:11434')}/api/generate",
        json={
            "model": os.getenv("OLLAMA_MODEL", "llama3"),
            "prompt": prompt,
            "format": "json",
            "stream": False,
            "options": {
                "temperature": 0.0,
                "seed": 42,
                "num_predict": 1024
            },
        },
        timeout=300,  # Increased from 120s to 300s for slower local machines
    )
    
    entities = []
    relationships = []
    if response.status_code == 200:
        data = response.json().get("response", "{}")
        try:
            parsed = json.loads(data)
            extracted = parsed.get("entities", [])
            relationships = parsed.get("relationships", [])
            for ent in extracted:
                val = ent.get("value", "")
                norm = ent.get("normalized_value", "").lower()
                ctx = ent.get("context", "")
                etype = ent.get("entity_type", "OTHER")
                if etype not in ["PERSON", "ORGANIZATION", "LOCATION"]:
                    etype = "OTHER"
                    
                if val and norm:
                    threat_score = _compute_threat_score(val, ctx)
                    entities.append({
                        "entity_type": etype,
                        "value": val,
                        "normalized_value": norm,
                        "confidence": 0.88,
                        "context": ctx,
                        "threat_relevance": threat_score,
                        "source": "ollama",
                    })
        except json.JSONDecodeError:
            logger.warning("Ollama returned invalid JSON format for entities.")
    return entities, relationships

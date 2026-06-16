"""
Graph Task — NetworkX relationship graph building from entities.
"""
import os
import json
from itertools import combinations
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


def update_graph_task(case_id: str, entities: list[dict]):
    """
    Build entity co-occurrence graph and persist relationships to DB.
    Uses NetworkX community detection for clustering.
    """
    if len(entities) < 2:
        return

    try:
        # Group entities by type for cross-type relationships
        persons = [e for e in entities if e.get("entity_type") == "PERSON"]
        orgs = [e for e in entities if e.get("entity_type") in ("ORG", "ORGANIZATION")]
        locations = [e for e in entities if e.get("entity_type") in ("GPE", "LOCATION")]
        phones = [e for e in entities if e.get("entity_type") in ("PHONE", "EMAIL")]

        relationships = []

        # Person ↔ Person (co-occurrence)
        for p1, p2 in combinations(persons[:10], 2):
            relationships.append({
                "source": p1["normalized_value"],
                "target": p2["normalized_value"],
                "source_type": "PERSON",
                "target_type": "PERSON",
                "relationship_type": "co_occurrence",
                "weight": 1.0 + (p1.get("threat_relevance", 0) + p2.get("threat_relevance", 0)),
            })

        # Person → Org
        for person in persons[:5]:
            for org in orgs[:5]:
                relationships.append({
                    "source": person["normalized_value"],
                    "target": org["normalized_value"],
                    "source_type": "PERSON",
                    "target_type": "ORG",
                    "relationship_type": "associated_with",
                    "weight": 1.2,
                })

        # Person → Location
        for person in persons[:5]:
            for loc in locations[:5]:
                relationships.append({
                    "source": person["normalized_value"],
                    "target": loc["normalized_value"],
                    "source_type": "PERSON",
                    "target_type": "GPE",
                    "relationship_type": "located_in",
                    "weight": 0.8,
                })

        # Person → Phone/Email
        for person in persons[:5]:
            for contact in phones[:5]:
                relationships.append({
                    "source": person["normalized_value"],
                    "target": contact["normalized_value"],
                    "source_type": "PERSON",
                    "target_type": contact["entity_type"],
                    "relationship_type": "uses_contact",
                    "weight": 1.5,
                })

        # Org → Location
        for org in orgs[:5]:
            for loc in locations[:5]:
                relationships.append({
                    "source": org["normalized_value"],
                    "target": loc["normalized_value"],
                    "source_type": org["entity_type"],
                    "target_type": loc["entity_type"],
                    "relationship_type": "operates_in",
                    "weight": 1.1,
                })

        # Org → Phone/Email
        for org in orgs[:5]:
            for contact in phones[:5]:
                relationships.append({
                    "source": org["normalized_value"],
                    "target": contact["normalized_value"],
                    "source_type": org["entity_type"],
                    "target_type": contact["entity_type"],
                    "relationship_type": "contact_for",
                    "weight": 1.0,
                })

        # General co-occurrence fallback
        if not relationships:
            for e1, e2 in combinations(entities[:8], 2):
                if e1["normalized_value"] != e2["normalized_value"]:
                    relationships.append({
                        "source": e1["normalized_value"],
                        "target": e2["normalized_value"],
                        "source_type": e1["entity_type"],
                        "target_type": e2["entity_type"],
                        "relationship_type": "co_occurrence",
                        "weight": 0.5,
                    })

        _save_relationships(case_id, entities, relationships)
        logger.info(f"Graph updated for case {case_id} with {len(relationships)} relationships")

    except Exception as e:
        logger.error(f"Graph task failed for case {case_id}: {e}")


def _save_relationships(case_id: str, entities: list[dict], relationships: list[dict]):
    """Persist entity relationships to PostgreSQL."""
    if not relationships:
        return

    try:
        from sqlalchemy import create_engine, text

        DATABASE_URL = os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg2://iip_user:iip_secret_2024@localhost:5432/investigation_db"
        ).replace("postgresql+asyncpg://", "postgresql+psycopg2://")

        engine = create_engine(DATABASE_URL)

        # Build lookup: normalized_value → entity id
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT id, normalized_value, entity_type FROM entities WHERE case_id = :case_id"),
                {"case_id": case_id}
            )
            entity_lookup = {
                (row[2], row[1]): str(row[0])
                for row in result.fetchall()
            }

            for rel in relationships[:50]:
                src_key = (rel["source_type"], rel["source"])
                tgt_key = (rel["target_type"], rel["target"])
                src_id = entity_lookup.get(src_key)
                tgt_id = entity_lookup.get(tgt_key)

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
                        "rel_type": rel["relationship_type"],
                        "weight": rel["weight"],
                    }
                )
            conn.commit()
    except Exception as e:
        logger.error(f"Failed to save relationships: {e}")

import os
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://iip_user:iip_secret_2024@localhost:5432/investigation_db"
)
engine = create_engine(DATABASE_URL)

THREAT_KEYWORDS = {
    "kill", "weapon", "gun", "explosive", "bomb", "attack", "threat",
    "ransom", "kidnap", "murder", "illegal", "cocaine", "heroin", "drug",
    "smuggle", "launder", "bribe", "corrupt", "fraud", "trafficking",
    "terror", "hack", "breach", "blackmail", "extort", "hawala", "shell",
    "money", "crore", "transfer", "account", "offshore", "scam", "evade",
}

def _compute_threat_score(value: str, context: str) -> float:
    combined = f"{value} {context or ''}".lower()
    keyword_hits = sum(1 for kw in THREAT_KEYWORDS if kw in combined)
    base_score = min(keyword_hits * 0.15, 0.9)
    return round(base_score, 3)

with engine.connect() as conn:
    result = conn.execute(text("SELECT id, value, context FROM entities")).fetchall()
    print(f"Recalculating scores for {len(result)} entities...")
    updated = 0
    for row in result:
        new_score = _compute_threat_score(row.value, row.context)
        if new_score > 0:
            conn.execute(
                text("UPDATE entities SET threat_relevance = :score WHERE id = :id"),
                {"score": new_score, "id": row.id}
            )
            updated += 1
            print(f"Updated {row.value} -> {new_score}")
    conn.commit()
    print(f"Done. Updated {updated} entities.")

"""
Embedding Task — Sentence Transformer vectorization + ChromaDB storage.
"""
import os
import uuid
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)

_encoder = None


def get_encoder():
    global _encoder
    if _encoder is None:
        try:
            from sentence_transformers import SentenceTransformer
            model_name = os.getenv("SENTENCE_TRANSFORMER_MODEL", "all-MiniLM-L6-v2")
            _encoder = SentenceTransformer(model_name)
            logger.info(f"Sentence Transformer '{model_name}' loaded")
        except Exception as e:
            logger.error(f"SentenceTransformer load failed: {e}")
    return _encoder


def get_chroma_collection():
    try:
        import chromadb
        client = chromadb.HttpClient(
            host=os.getenv("CHROMA_HOST", "chromadb"),
            port=int(os.getenv("CHROMA_PORT", "8000")),
            settings=chromadb.Settings(
                chroma_client_auth_provider="chromadb.auth.token.TokenAuthClientProvider",
                chroma_client_auth_credentials=os.getenv("CHROMA_TOKEN", "iip_chroma_token"),
            )
        )
        return client.get_or_create_collection(
            name=os.getenv("CHROMA_COLLECTION", "investigation_evidence"),
            metadata={"hnsw:space": "cosine"},
        )
    except Exception as e:
        logger.warning(f"ChromaDB unavailable: {e}")
        return None


def embed_evidence_task(evidence_id: str, case_id: str, text: str):
    """
    Generate sentence embeddings for evidence text and store in ChromaDB.
    Enables semantic similarity search via the Copilot.
    """
    if not text or len(text.strip()) < 20:
        logger.info(f"Skipping embedding for {evidence_id} — insufficient text")
        return

    encoder = get_encoder()
    if not encoder:
        logger.warning("Encoder not available, skipping embedding")
        return

    collection = get_chroma_collection()
    if not collection:
        logger.warning("ChromaDB not available, skipping embedding")
        return

    try:
        # Chunk text into ~512-token segments
        chunks = _chunk_text(text, max_chars=1500)
        if not chunks:
            return

        embeddings = encoder.encode(chunks, batch_size=16, show_progress_bar=False).tolist()

        ids = [f"{evidence_id}_chunk_{i}" for i in range(len(chunks))]
        metadatas = [{"evidence_id": evidence_id, "case_id": case_id, "chunk_index": i} for i in range(len(chunks))]

        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=chunks,
            metadatas=metadatas,
        )

        logger.info(f"Embedded {len(chunks)} chunks for evidence {evidence_id}")
        _update_evidence_embedded(evidence_id)

    except Exception as e:
        logger.error(f"Embedding failed for {evidence_id}: {e}")


def _chunk_text(text: str, max_chars: int = 1500) -> list[str]:
    """Split text into overlapping chunks for embedding."""
    if len(text) <= max_chars:
        return [text.strip()]

    chunks = []
    sentences = text.replace("\n\n", " <PARA> ").split(". ")
    current = ""
    for sentence in sentences:
        if len(current) + len(sentence) > max_chars:
            if current.strip():
                chunks.append(current.strip())
            current = sentence
        else:
            current += ". " + sentence if current else sentence
    if current.strip():
        chunks.append(current.strip())

    return [c for c in chunks if len(c) > 30]


def _update_evidence_embedded(evidence_id: str):
    """Mark evidence as fully processed."""
    try:
        from sqlalchemy import create_engine, text
        DATABASE_URL = os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg2://iip_user:iip_secret_2024@localhost:5432/investigation_db"
        ).replace("postgresql+asyncpg://", "postgresql+psycopg2://")

        engine = create_engine(DATABASE_URL)
        with engine.connect() as conn:
            conn.execute(
                text("UPDATE evidence SET processing_status = 'completed', processed_at = now() WHERE id = :id"),
                {"id": evidence_id}
            )
            conn.commit()
    except Exception as e:
        logger.error(f"Failed to mark evidence as embedded: {e}")

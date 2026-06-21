"""
OCR Task — Tesseract + PyMuPDF text extraction pipeline.
Handles: PDF, Images, Documents, Chat exports, Video (metadata only).
"""
import os
import io
import json
import tempfile
from pathlib import Path
from celery.utils.log import get_task_logger
from celery_app import app

logger = get_task_logger(__name__)


def get_minio_client():
    from minio import Minio
    return Minio(
        os.getenv("MINIO_ENDPOINT", "localhost:9000"),
        access_key=os.getenv("MINIO_ACCESS_KEY", "iip_minio"),
        secret_key=os.getenv("MINIO_SECRET_KEY", "iip_minio_secret_2024"),
        secure=False,
    )


def download_from_minio(storage_path: str) -> bytes:
    client = get_minio_client()
    bucket = os.getenv("MINIO_BUCKET_NAME", "investigation-evidence")
    response = client.get_object(bucket, storage_path)
    data = response.read()
    response.close()
    return data


def extract_text_task(evidence_id: str, storage_path: str, file_type: str) -> dict:
    """Extract text and metadata from evidence file. Called synchronously from pipeline."""
    logger.info(f"Starting OCR/extraction for {evidence_id} (type={file_type})")

    try:
        file_data = download_from_minio(storage_path)
        result = {"text": "", "metadata": {}, "pages": 0, "word_count": 0}

        if file_type == "pdf":
            result = _extract_pdf(file_data, storage_path)
        elif file_type == "image":
            result = _extract_image(file_data, storage_path)
        elif file_type in ("document",):
            result = _extract_document(file_data, storage_path)
        elif file_type == "chat_export":
            result = _extract_chat(file_data, storage_path)
        elif file_type == "video":
            result = _extract_video_metadata(file_data, storage_path)

        # Update DB
        _save_extraction_result(evidence_id, result)
        return result

    except Exception as e:
        logger.error(f"Extraction failed for {evidence_id}: {e}")
        _save_extraction_result(evidence_id, {"text": "", "metadata": {"error": str(e)}, "error": str(e)})
        return {"text": "", "metadata": {}, "error": str(e)}


def _extract_pdf(data: bytes, path: str) -> dict:
    """Extract text from PDF — native first, then OCR fallback."""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(stream=data, filetype="pdf")
        text_parts = []
        for page in doc:
            text = page.get_text("text")
            if len(text.strip()) < 50:  # Scanned page — use OCR
                pix = page.get_pixmap(dpi=200)
                img_data = pix.tobytes("png")
                text = _ocr_image_bytes(img_data)
            text_parts.append(text)
        full_text = "\n\n".join(text_parts)
        meta = doc.metadata or {}
        doc.close()
        return {
            "text": full_text,
            "metadata": {k: str(v) for k, v in meta.items() if v},
            "pages": len(text_parts),
            "word_count": len(full_text.split()),
        }
    except Exception as e:
        logger.error(f"PDF extraction failed: {e}")
        return {"text": "", "metadata": {}, "error": str(e)}


def _extract_image(data: bytes, path: str) -> dict:
    """OCR + EXIF extraction from image."""
    text = _ocr_image_bytes(data)
    metadata = _extract_exif(data)
    return {
        "text": text,
        "metadata": metadata,
        "word_count": len(text.split()),
    }


def _ocr_image_bytes(data: bytes) -> str:
    """Run Tesseract OCR on image bytes."""
    try:
        import pytesseract
        from PIL import Image
        img = Image.open(io.BytesIO(data))
        # Enhance image for better OCR
        img = img.convert("L")  # Grayscale
        text = pytesseract.image_to_string(img, lang="tel+eng", config="--oem 3 --psm 6")
        return text.strip()
    except Exception as e:
        logger.warning(f"Tesseract OCR failed: {e}")
        return ""


def _extract_exif(data: bytes) -> dict:
    """Extract EXIF metadata from image."""
    try:
        from PIL import Image
        from PIL.ExifTags import TAGS
        img = Image.open(io.BytesIO(data))
        exif_data = img._getexif() or {}
        return {
            TAGS.get(tag, str(tag)): str(value)
            for tag, value in exif_data.items()
            if tag in TAGS
        }
    except Exception:
        return {}


def _extract_document(data: bytes, path: str) -> dict:
    """Extract text from DOCX/TXT files."""
    ext = Path(path).suffix.lower()
    try:
        if ext == ".docx":
            from docx import Document
            doc = Document(io.BytesIO(data))
            text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        elif ext == ".txt" or ext == ".csv":
            text = data.decode("utf-8", errors="replace")
        elif ext == ".xml":
            import xml.etree.ElementTree as ET
            root = ET.fromstring(data.decode("utf-8", errors="replace"))
            text = " ".join(root.itertext())
        else:
            text = data.decode("utf-8", errors="replace")
        return {"text": text, "metadata": {"format": ext}, "word_count": len(text.split())}
    except Exception as e:
        return {"text": data.decode("utf-8", errors="replace"), "metadata": {}, "error": str(e)}


def _extract_chat(data: bytes, path: str) -> dict:
    """Parse chat export (JSON / WhatsApp TXT format)."""
    try:
        # Try JSON (Telegram, Signal export format)
        chat_data = json.loads(data.decode("utf-8"))
        messages = []
        if isinstance(chat_data, dict):
            msgs = chat_data.get("messages", chat_data.get("chats", []))
        elif isinstance(chat_data, list):
            msgs = chat_data
        else:
            msgs = []

        for msg in msgs[:500]:  # Limit to first 500 messages
            if isinstance(msg, dict):
                sender = msg.get("from", msg.get("sender", "Unknown"))
                text = msg.get("text", msg.get("body", msg.get("message", "")))
                if isinstance(text, list):
                    text = " ".join(str(t) for t in text if t)
                ts = msg.get("date", msg.get("timestamp", ""))
                if text:
                    messages.append(f"[{ts}] {sender}: {text}")

        full_text = "\n".join(messages)
        return {
            "text": full_text,
            "metadata": {"format": "json_chat", "message_count": len(messages)},
            "word_count": len(full_text.split()),
        }
    except (json.JSONDecodeError, UnicodeDecodeError):
        # Try plain text WhatsApp format
        text = data.decode("utf-8", errors="replace")
        return {"text": text, "metadata": {"format": "text_chat"}, "word_count": len(text.split())}


def _extract_video_metadata(data: bytes, path: str) -> dict:
    """Extract video metadata using ffprobe (lightweight — no frame OCR)."""
    try:
        import subprocess, tempfile
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(data)
            tmp_path = f.name

        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", tmp_path],
            capture_output=True, text=True, timeout=30
        )
        os.unlink(tmp_path)

        if result.returncode == 0:
            info = json.loads(result.stdout)
            fmt = info.get("format", {})
            meta = {
                "duration_seconds": fmt.get("duration", "unknown"),
                "size_bytes": fmt.get("size", "unknown"),
                "bit_rate": fmt.get("bit_rate", "unknown"),
                "format_name": fmt.get("format_name", "unknown"),
                "tags": fmt.get("tags", {}),
            }
            text = (
                f"Video file metadata: Duration={meta['duration_seconds']}s, "
                f"Format={meta['format_name']}, "
                f"Tags={json.dumps(meta.get('tags', {}))}"
            )
            return {"text": text, "metadata": meta, "word_count": len(text.split())}
    except Exception as e:
        logger.warning(f"FFprobe failed: {e}")

    return {"text": "Video file — metadata extraction unavailable", "metadata": {}, "word_count": 0}


def _save_extraction_result(evidence_id: str, result: dict):
    """Persist extraction result to PostgreSQL."""
    try:
        import sqlalchemy
        from sqlalchemy import create_engine, text
        import json

        DATABASE_URL = os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg2://iip_user:iip_secret_2024@localhost:5432/investigation_db"
        ).replace("postgresql+asyncpg://", "postgresql+psycopg2://")

        engine = create_engine(DATABASE_URL)
        with engine.connect() as conn:
            conn.execute(
                text("""
                    UPDATE evidence
                    SET extracted_text = :text,
                        extraction_metadata = CAST(:meta AS jsonb),
                        processing_status = 'PROCESSING'
                    WHERE id = :id
                """),
                {
                    "text": result.get("text", "")[:50000],  # Limit text size
                    "meta": json.dumps(result.get("metadata", {})),
                    "id": evidence_id,
                }
            )
            conn.commit()
    except Exception as e:
        logger.error(f"Failed to save extraction result: {e}")

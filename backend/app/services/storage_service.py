"""
Storage service — MinIO file upload, download, signed URLs.
"""
import io
import uuid
from minio import Minio
from minio.error import S3Error
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings
from app.core.exceptions import StorageError
from app.core.logging import get_logger

logger = get_logger(__name__)


class StorageService:
    def __init__(self):
        self.client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        self.bucket = settings.minio_bucket_name
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        try:
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)
                logger.info("MinIO bucket created", bucket=self.bucket)
        except S3Error as e:
            logger.error("Failed to ensure MinIO bucket", error=str(e))
            raise StorageError(f"Storage initialization failed: {e}")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    async def upload_file(
        self,
        file_data: bytes,
        filename: str,
        content_type: str,
        case_id: str,
    ) -> str:
        """Upload file to MinIO and return storage path."""
        object_name = f"cases/{case_id}/{uuid.uuid4()}_{filename}"
        try:
            self.client.put_object(
                self.bucket,
                object_name,
                io.BytesIO(file_data),
                length=len(file_data),
                content_type=content_type,
            )
            logger.info("File uploaded to MinIO", object_name=object_name, size=len(file_data))
            return object_name
        except S3Error as e:
            logger.error("MinIO upload failed", error=str(e), object_name=object_name)
            raise StorageError(f"File upload failed: {e}")

    def get_presigned_url(self, object_name: str, expires_seconds: int = 3600) -> str:
        """Generate presigned download URL."""
        from datetime import timedelta
        try:
            url = self.client.presigned_get_object(
                self.bucket,
                object_name,
                expires=timedelta(seconds=expires_seconds),
            )
            return url
        except S3Error as e:
            raise StorageError(f"Failed to generate presigned URL: {e}")

    def download_file(self, object_name: str) -> bytes:
        """Download file from MinIO and return bytes."""
        try:
            response = self.client.get_object(self.bucket, object_name)
            data = response.read()
            response.close()
            return data
        except S3Error as e:
            raise StorageError(f"File download failed: {e}")

    def delete_file(self, object_name: str) -> None:
        """Delete file from MinIO."""
        try:
            self.client.remove_object(self.bucket, object_name)
        except S3Error as e:
            logger.warning("Failed to delete file from MinIO", error=str(e))

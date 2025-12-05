from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Optional

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.core.config import get_settings

settings = get_settings()


class StorageService:
    """Service for handling file storage operations with Cloudflare R2."""

    def __init__(self) -> None:
        """Initialize the R2 storage client."""
        self._client = None
        self._bucket_name = settings.r2_bucket_name
        self._public_url = settings.r2_public_url

    @property
    def client(self):
        """Lazy initialization of R2 client."""
        if self._client is None:
            if not all([
                settings.r2_account_id,
                settings.r2_access_key_id,
                settings.r2_secret_access_key,
                settings.r2_bucket_name,
                settings.r2_endpoint_url,
            ]):
                raise ValueError(
                    "R2 configuration incomplete. Please set R2_ACCOUNT_ID, "
                    "R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME, and R2_ENDPOINT_URL"
                )

            self._client = boto3.client(
                "s3",
                endpoint_url=settings.r2_endpoint_url,
                aws_access_key_id=settings.r2_access_key_id,
                aws_secret_access_key=settings.r2_secret_access_key,
                region_name="auto",  # R2 uses "auto" as region
                config=Config(signature_version="s3v4"),
            )
        return self._client

    def _generate_key(self, prefix: str, filename: str) -> str:
        """Generate a unique storage key for a file."""
        # Generate unique filename to avoid collisions
        unique_id = str(uuid.uuid4())[:8]
        timestamp = datetime.utcnow().strftime("%Y%m%d")
        # Preserve original extension
        extension = filename.rsplit(".", 1)[-1] if "." in filename else ""
        safe_filename = filename.rsplit(".", 1)[0] if "." in filename else filename
        # Sanitize filename (remove special chars, keep alphanumeric, dash, underscore)
        safe_filename = "".join(c for c in safe_filename if c.isalnum() or c in ("-", "_"))
        
        if extension:
            unique_filename = f"{safe_filename}_{timestamp}_{unique_id}.{extension}"
        else:
            unique_filename = f"{safe_filename}_{timestamp}_{unique_id}"
        
        return f"{prefix}/{unique_filename}"

    async def upload_file(
        self,
        file_content: bytes,
        filename: str,
        prefix: str = "documents",
        content_type: Optional[str] = None,
    ) -> str:
        """
        Upload a file to R2 storage.

        Args:
            file_content: The file content as bytes
            filename: Original filename
            prefix: Storage prefix/path (e.g., "drivers", "loads", "documents")
            content_type: MIME type of the file (optional, will be inferred if not provided)

        Returns:
            The storage key/path of the uploaded file
        """
        key = self._generate_key(prefix, filename)
        
        # Infer content type if not provided
        if not content_type:
            content_type = self._infer_content_type(filename)

        try:
            self.client.put_object(
                Bucket=self._bucket_name,
                Key=key,
                Body=file_content,
                ContentType=content_type,
            )
            return key
        except ClientError as e:
            raise ValueError(f"Failed to upload file to R2: {str(e)}")

    async def delete_file(self, key: str) -> bool:
        """
        Delete a file from R2 storage.

        Args:
            key: The storage key/path of the file

        Returns:
            True if deletion was successful, False otherwise
        """
        try:
            self.client.delete_object(Bucket=self._bucket_name, Key=key)
            return True
        except ClientError:
            return False

    def get_file_url(self, key: str, expires_in: int = 3600) -> str:
        """
        Generate a presigned URL for accessing a file.

        Args:
            key: The storage key/path of the file
            expires_in: URL expiration time in seconds (default: 1 hour)

        Returns:
            Presigned URL for the file
        """
        try:
            url = self.client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._bucket_name, "Key": key},
                ExpiresIn=expires_in,
            )
            return url
        except ClientError as e:
            raise ValueError(f"Failed to generate presigned URL: {str(e)}")

    def get_public_url(self, key: str) -> Optional[str]:
        """
        Get the public URL for a file if using a custom domain/CDN.

        Args:
            key: The storage key/path of the file

        Returns:
            Public URL if configured, None otherwise
        """
        if self._public_url:
            # Remove leading slash from key if present
            clean_key = key.lstrip("/")
            return f"{self._public_url.rstrip('/')}/{clean_key}"
        return None

    def _infer_content_type(self, filename: str) -> str:
        """Infer content type from filename extension."""
        extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        
        content_types = {
            "pdf": "application/pdf",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "gif": "image/gif",
            "doc": "application/msword",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "xls": "application/vnd.ms-excel",
            "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "txt": "text/plain",
            "csv": "text/csv",
        }
        
        return content_types.get(extension, "application/octet-stream")

    async def file_exists(self, key: str) -> bool:
        """
        Check if a file exists in R2 storage.

        Args:
            key: The storage key/path of the file

        Returns:
            True if file exists, False otherwise
        """
        try:
            self.client.head_object(Bucket=self._bucket_name, Key=key)
            return True
        except ClientError:
            return False



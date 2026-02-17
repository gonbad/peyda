"""
Media service for S3/MinIO operations.

Handles presigned URL generation for uploads and downloads,
and media verification.
"""
import uuid
import logging
from dataclasses import dataclass
from typing import Optional

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from django.conf import settings

logger = logging.getLogger(__name__)


ALLOWED_CONTENT_TYPES = {
    'image/jpeg': '.jpg',
    'image/png': '.png',
    'image/gif': '.gif',
    'image/webp': '.webp',
}


@dataclass
class CreateMediaResult:
    """Result of creating a media upload URL."""
    success: bool
    media_id: Optional[str] = None
    upload_url: Optional[str] = None
    expires_in: Optional[int] = None
    max_file_size: Optional[int] = None
    error: Optional[str] = None
    error_code: Optional[str] = None


@dataclass
class VerifyMediaResult:
    """Result of verifying an uploaded media."""
    success: bool
    media_id: Optional[str] = None
    status: Optional[str] = None
    file_info: Optional[dict] = None
    error: Optional[str] = None
    error_code: Optional[str] = None


@dataclass
class GetUrlResult:
    """Result of getting a presigned URL."""
    success: bool
    url: Optional[str] = None
    error: Optional[str] = None


class MediaService:
    """
    Service for managing media uploads and downloads via S3/MinIO.
    
    Provides:
    - Presigned PUT URLs for direct uploads
    - Presigned GET URLs for secure downloads
    - Media verification after upload
    """
    
    def __init__(self, cache=None):
        self._cache = cache
        self._endpoint_url = getattr(settings, 'S3_ENDPOINT_URL', 'http://localhost:9000')
        self._external_url = getattr(settings, 'S3_EXTERNAL_URL', 'http://localhost:9000')
        self._access_key = getattr(settings, 'S3_ACCESS_KEY', '')
        self._secret_key = getattr(settings, 'S3_SECRET_KEY', '')
        self._bucket_name = getattr(settings, 'S3_BUCKET_NAME', 'peyda-media')
        self._presigned_expiry = getattr(settings, 'S3_PRESIGNED_URL_EXPIRY', 3600)
        self._max_file_size = getattr(settings, 'MAX_UPLOAD_SIZE_BYTES', 5 * 1024 * 1024)
        
        self._client = None
    
    def _get_client(self):
        """Get or create S3 client."""
        if self._client is None:
            self._client = boto3.client(
                's3',
                endpoint_url=self._endpoint_url,
                aws_access_key_id=self._access_key,
                aws_secret_access_key=self._secret_key,
                config=Config(signature_version='s3v4'),
                region_name='us-east-1',
            )
        return self._client
    
    def _get_external_client(self):
        """Get S3 client configured for external URL (for presigned URLs)."""
        return boto3.client(
            's3',
            endpoint_url=self._external_url,
            aws_access_key_id=self._access_key,
            aws_secret_access_key=self._secret_key,
            config=Config(signature_version='s3v4'),
            region_name='us-east-1',
        )
    
    def create_upload_url(
        self,
        user_id: int,
        filename: str,
        content_type: str,
        file_size: Optional[int] = None
    ) -> CreateMediaResult:
        """
        Create a presigned PUT URL for uploading media.
        
        Args:
            user_id: ID of the authenticated user
            filename: Original filename
            content_type: MIME type of the file
            file_size: Optional file size for validation
        
        Returns:
            CreateMediaResult with upload URL on success
        """
        if content_type not in ALLOWED_CONTENT_TYPES:
            return CreateMediaResult(
                success=False,
                error="فقط فایل‌های تصویری مجاز هستند (JPEG, PNG, GIF, WebP)",
                error_code="INVALID_FILE_TYPE"
            )
        
        if file_size and file_size > self._max_file_size:
            return CreateMediaResult(
                success=False,
                error=f"حجم فایل بیش از حد مجاز است (حداکثر {self._max_file_size // (1024*1024)} مگابایت)",
                error_code="FILE_TOO_LARGE"
            )
        
        media_id = f"media_{uuid.uuid4().hex}"
        extension = ALLOWED_CONTENT_TYPES[content_type]
        object_key = f"uploads/{user_id}/{media_id}{extension}"
        
        try:
            client = self._get_external_client()
            upload_url = client.generate_presigned_url(
                'put_object',
                Params={
                    'Bucket': self._bucket_name,
                    'Key': object_key,
                    'ContentType': content_type,
                },
                ExpiresIn=self._presigned_expiry,
            )
            
            if self._cache:
                media_data = {
                    'user_id': user_id,
                    'object_key': object_key,
                    'content_type': content_type,
                    'filename': filename,
                    'status': 'pending',
                }
                self._cache.set_json(f"media:{media_id}", media_data, ttl=self._presigned_expiry * 2)
            
            logger.info(f"Created upload URL for user {user_id}, media_id={media_id}")
            
            return CreateMediaResult(
                success=True,
                media_id=media_id,
                upload_url=upload_url,
                expires_in=self._presigned_expiry,
                max_file_size=self._max_file_size,
            )
            
        except ClientError as e:
            logger.exception(f"S3 error creating upload URL: {e}")
            return CreateMediaResult(
                success=False,
                error="خطا در ایجاد آدرس آپلود",
                error_code="S3_ERROR"
            )
        except Exception as e:
            logger.exception(f"Error creating upload URL: {e}")
            return CreateMediaResult(
                success=False,
                error="خطای سیستمی",
                error_code="SYSTEM_ERROR"
            )
    
    def verify_media(self, user_id: int, media_id: str) -> VerifyMediaResult:
        """
        Verify that a media file was uploaded successfully.
        
        Args:
            user_id: ID of the authenticated user
            media_id: Media ID from create_upload_url
        
        Returns:
            VerifyMediaResult with file info on success
        """
        if not self._cache:
            return VerifyMediaResult(
                success=False,
                error="سرویس کش در دسترس نیست",
                error_code="CACHE_UNAVAILABLE"
            )
        
        media_data = self._cache.get_json(f"media:{media_id}")
        if not media_data:
            return VerifyMediaResult(
                success=False,
                error="شناسه مدیا معتبر نیست",
                error_code="MEDIA_NOT_FOUND"
            )
        
        if media_data.get('user_id') != user_id:
            return VerifyMediaResult(
                success=False,
                error="دسترسی به این مدیا مجاز نیست",
                error_code="ACCESS_DENIED"
            )
        
        object_key = media_data.get('object_key')
        
        try:
            client = self._get_client()
            response = client.head_object(
                Bucket=self._bucket_name,
                Key=object_key
            )
            
            file_size = response.get('ContentLength', 0)
            content_type = response.get('ContentType', '')
            
            if file_size > self._max_file_size:
                client.delete_object(Bucket=self._bucket_name, Key=object_key)
                self._cache.delete(f"media:{media_id}")
                return VerifyMediaResult(
                    success=False,
                    error="حجم فایل بیش از حد مجاز است",
                    error_code="FILE_TOO_LARGE"
                )
            
            media_data['status'] = 'verified'
            media_data['file_size'] = file_size
            self._cache.set_json(f"media:{media_id}", media_data, ttl=86400 * 7)  # 7 days
            
            logger.info(f"Verified media {media_id} for user {user_id}, size={file_size}")
            
            return VerifyMediaResult(
                success=True,
                media_id=media_id,
                status='verified',
                file_info={
                    'size': file_size,
                    'format': content_type,
                }
            )
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            if error_code == '404' or error_code == 'NoSuchKey':
                return VerifyMediaResult(
                    success=False,
                    error="فایل در S3 یافت نشد. لطفاً مجدداً آپلود کنید.",
                    error_code="FILE_NOT_FOUND"
                )
            logger.exception(f"S3 error verifying media: {e}")
            return VerifyMediaResult(
                success=False,
                error="خطا در بررسی فایل",
                error_code="S3_ERROR"
            )
        except Exception as e:
            logger.exception(f"Error verifying media: {e}")
            return VerifyMediaResult(
                success=False,
                error="خطای سیستمی",
                error_code="SYSTEM_ERROR"
            )
    
    def get_download_url(self, object_key: str) -> GetUrlResult:
        """
        Get a presigned GET URL for downloading media.
        
        Args:
            object_key: S3 object key
        
        Returns:
            GetUrlResult with download URL on success
        """
        try:
            client = self._get_external_client()
            url = client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self._bucket_name,
                    'Key': object_key,
                },
                ExpiresIn=self._presigned_expiry,
            )
            return GetUrlResult(success=True, url=url)
        except Exception as e:
            logger.exception(f"Error generating download URL: {e}")
            return GetUrlResult(success=False, error=str(e))
    
    def get_media_object_key(self, media_id: str) -> Optional[str]:
        """Get the S3 object key for a media ID."""
        if not self._cache:
            return None
        media_data = self._cache.get_json(f"media:{media_id}")
        if media_data and media_data.get('status') == 'verified':
            return media_data.get('object_key')
        return None
    
    def resolve_media_urls(self, media_ids: list) -> list:
        """
        Convert media IDs to presigned download URLs.
        
        Args:
            media_ids: List of media IDs or object keys
        
        Returns:
            List of presigned URLs
        """
        urls = []
        for media_id in media_ids:
            if media_id.startswith('uploads/'):
                result = self.get_download_url(media_id)
                urls.append(result.url if result.success else media_id)
            elif media_id.startswith('media_'):
                object_key = self.get_media_object_key(media_id)
                if object_key:
                    result = self.get_download_url(object_key)
                    urls.append(result.url if result.success else media_id)
                else:
                    urls.append(media_id)
            else:
                urls.append(media_id)
        return urls

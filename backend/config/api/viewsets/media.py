"""
Media ViewSet - media upload and verification endpoints.

Based on OpenAPI.yaml:
- POST /media
- POST /media/{mediaId}/verify
"""
from rest_framework import status
from rest_framework.decorators import action

from .base import BaseViewSet
from services.media import MediaService


class MediaViewSet(BaseViewSet):
    """مدیریت مدیا (آپلود تصاویر)"""
    
    def create(self, request):
        """
        ایجاد آدرس آپلود مدیا
        POST /media
        """
        filename = request.data.get('filename')
        content_type = request.data.get('content_type')
        file_size = request.data.get('file_size')
        
        if not filename:
            return self.error("نام فایل الزامی است", "MISSING_FILENAME", status.HTTP_400_BAD_REQUEST)
        if not content_type:
            return self.error("نوع فایل الزامی است", "MISSING_CONTENT_TYPE", status.HTTP_400_BAD_REQUEST)
        
        service = self.get_container().get(MediaService)
        
        result = service.create_upload_url(
            user_id=request.user.id,
            filename=filename,
            content_type=content_type,
            file_size=file_size,
        )
        
        if not result.success:
            return self.error(result.error, result.error_code, status.HTTP_400_BAD_REQUEST)
        
        return self.success({
            'success': True,
            'media_id': result.media_id,
            'upload_url': result.upload_url,
            'expires_in': result.expires_in,
            'max_file_size': result.max_file_size,
        }, status_code=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'], url_path='verify')
    def verify(self, request, pk=None):
        """
        تایید آپلود مدیا
        POST /media/{mediaId}/verify
        """
        service = self.get_container().get(MediaService)
        
        result = service.verify_media(
            user_id=request.user.id,
            media_id=pk,
        )
        
        if not result.success:
            if result.error_code == 'MEDIA_NOT_FOUND':
                return self.not_found(result.error)
            if result.error_code == 'ACCESS_DENIED':
                return self.forbidden(result.error)
            return self.error(result.error, result.error_code, status.HTTP_400_BAD_REQUEST)
        
        return self.success({
            'success': True,
            'media_id': result.media_id,
            'status': result.status,
            'file_info': result.file_info,
        })

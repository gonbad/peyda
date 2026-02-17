"""
Transcription ViewSet - Audio to text conversion for missing person descriptions.

POST /transcription/audio-to-text
"""
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser

from .base import BaseViewSet
from services.transcription import TranscriptionService
from infrastructure.bootstrap import get_container


class TranscriptionViewSet(BaseViewSet):
    """رونویسی صوت به متن"""
    
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser]
    
    @action(detail=False, methods=['post'], url_path='audio-to-text')
    def audio_to_text(self, request):
        """
        تبدیل صوت به متن ساختارمند
        POST /transcription/audio-to-text
        
        Request:
            - audio: فایل صوتی (multipart/form-data)
        
        Response:
            - text: متن ساختارمند استخراج شده
            - remaining_requests: تعداد درخواست‌های باقی‌مانده امروز
        """
        audio_file = request.FILES.get('audio')
        
        if not audio_file:
            return self.error(
                "فایل صوتی الزامی است",
                "MISSING_AUDIO",
                status.HTTP_400_BAD_REQUEST
            )
        
        max_size = 10 * 1024 * 1024  # 10MB
        if audio_file.size > max_size:
            return self.error(
                "حجم فایل صوتی نباید بیشتر از ۱۰ مگابایت باشد",
                "FILE_TOO_LARGE",
                status.HTTP_400_BAD_REQUEST
            )
        
        allowed_types = [
            'audio/webm', 'audio/mp3', 'audio/mpeg', 
            'audio/wav', 'audio/ogg', 'audio/m4a', 'audio/mp4'
        ]
        content_type = audio_file.content_type
        if content_type not in allowed_types:
            return self.error(
                "فرمت فایل صوتی پشتیبانی نمی‌شود. فرمت‌های مجاز: webm, mp3, wav, ogg, m4a",
                "INVALID_FORMAT",
                status.HTTP_400_BAD_REQUEST
            )
        
        container = get_container()
        transcription_service = container.get(TranscriptionService)
        
        audio_data = audio_file.read()
        result = transcription_service.transcribe(
            user_id=request.user.id,
            audio_data=audio_data,
            mime_type=content_type
        )
        
        if not result.success:
            status_code = status.HTTP_429_TOO_MANY_REQUESTS if result.error_code == 'RATE_LIMIT_EXCEEDED' else status.HTTP_400_BAD_REQUEST
            return self.error(result.error, result.error_code, status_code)
        
        remaining = transcription_service.get_remaining_requests(request.user.id)
        
        return self.success({
            'success': True,
            'text': result.text,
            'remaining_requests': remaining
        })

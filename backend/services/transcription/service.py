"""
Speech-to-text transcription service using Hugging Face Whisper Large V3.

Converts audio recordings of missing person descriptions into structured text.
"""
import base64
import logging
import httpx
from dataclasses import dataclass
from typing import Optional

from django.conf import settings

logger = logging.getLogger(__name__)


@dataclass
class TranscriptionResult:
    """Result of audio transcription."""
    success: bool
    text: Optional[str] = None
    raw_text: Optional[str] = None
    error: Optional[str] = None
    error_code: Optional[str] = None


TRANSCRIPTION_PROMPT = """شما یک دستیار هوشمند برای سامانه پیدا (سامانه یافتن افراد گمشده) هستید.

یک متن رونویسی شده از فایل صوتی به شما داده می‌شود. این صوت از یک والدین مضطرب و نگران است که فرزند گمشده خود را توصیف می‌کند. به دلیل استرس و اضطراب، ممکن است:
- کلمات تکراری یا نامفهوم داشته باشد
- جملات ناقص یا نامنظم باشد
- اطلاعات به صورت پراکنده بیان شده باشد
- احساسات و عبارات اضطراری در متن وجود داشته باشد
- غلط‌های املایی و تلفظی وجود داشته باشد (مثلاً "سوزه" به جای "سبزه")

وظیفه شما:
1. متن را با دقت و همدلی بخوانید
2. اطلاعات کلیدی و واقعی را از میان احساسات و تکرارها استخراج کنید
3. غلط‌های املایی و تلفظی را تصحیح کنید (مثال: سوزه → سبزه، قهوه‌ای → قهوه‌ای، سفید → سفید)
4. آن‌ها را به صورت ساختارمند و مرتب برگردانید
5. فقط واقعیت‌ها را ثبت کنید، نه احساسات یا عبارات اضطراری

خروجی باید به این شکل باشد (فقط موارد ذکر شده در متن را بنویسید):

**مشخصات ظاهری:**
- رنگ مو: [مقدار]
- رنگ چشم: [مقدار]
- رنگ پوست: [مقدار]
- قد: [مقدار]
- وزن تقریبی: [مقدار]
- سن تقریبی: [مقدار]

**پوشاک:**
- لباس بالاتنه: [مقدار]
- لباس پایین‌تنه: [مقدار]
- کفش: [مقدار]
- سایر: [مقدار]

**علائم خاص:**
- [هر علامت خاص مثل خال، زخم، عینک، و غیره]

**سایر اطلاعات:**
- [هر اطلاعات دیگری که ذکر شده]

نکات مهم:
- فقط اطلاعاتی که در متن گفته شده را بنویسید
- اگر چیزی ذکر نشده، آن بخش را ننویسید
- از حدس زدن خودداری کنید
- غلط‌های املایی رایج را تصحیح کنید (سوزه→سبزه، سفتی→سفید، و غیره)
- عبارات اضطراری مثل "کمک کنید"، "پیدا کنید" و غیره را ننویسید
- خروجی باید تمیز، واقعی و قابل جستجو باشد
- زبان خروجی فارسی و صحیح باشد"""


class TranscriptionService:
    """
    Service for transcribing audio descriptions of missing persons.

    Uses Hugging Face Whisper Large V3 for audio processing.
    Implements rate limiting per user (max 20 requests per day).
    """
    
    DAILY_LIMIT = 20
    RATE_LIMIT_TTL = 86400  # 24 hours in seconds
    
    def __init__(self, cache=None):
        self._cache = cache
        self._api_key = getattr(settings, 'HUGGINGFACE_API_KEY', '')
        self._model = getattr(settings, 'HUGGINGFACE_TRANSCRIPTION_MODEL', 'openai/whisper-large-v3')
    
    def transcribe(self, user_id: int, audio_data: bytes, mime_type: str = 'audio/webm') -> TranscriptionResult:
        """
        Transcribe audio to structured text.
        
        Args:
            user_id: ID of the authenticated user (for rate limiting)
            audio_data: Raw audio bytes
            mime_type: MIME type of the audio (e.g., 'audio/webm', 'audio/mp3')
        
        Returns:
            TranscriptionResult with structured text on success
        """
        if not self._api_key:
            logger.error("Hugging Face API key not configured")
            return TranscriptionResult(
                success=False,
                error="سرویس رونویسی در دسترس نیست",
                error_code="SERVICE_UNAVAILABLE"
            )
        
        if not self._check_rate_limit(user_id):
            return TranscriptionResult(
                success=False,
                error="شما به حداکثر تعداد درخواست روزانه (۲۰ بار) رسیده‌اید. لطفاً فردا دوباره تلاش کنید.",
                error_code="RATE_LIMIT_EXCEEDED"
            )
        
        try:
            headers = {
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": mime_type,
            }
            
            api_url = f"https://router.huggingface.co/hf-inference/models/{self._model}"
            
            with httpx.Client(timeout=120.0) as client:
                response = client.post(api_url, headers=headers, content=audio_data)
            
            if response.status_code != 200:
                logger.error(f"Hugging Face API error: {response.status_code} - {response.text}")
                return TranscriptionResult(
                    success=False,
                    error="خطا در پردازش صوت. لطفاً دوباره تلاش کنید.",
                    error_code="API_ERROR"
                )
            
            result = response.json()
            raw_text = result.get('text', '')
            
            if not raw_text:
                return TranscriptionResult(
                    success=False,
                    error="متنی از صوت استخراج نشد. لطفاً صوت واضح‌تری ضبط کنید.",
                    error_code="EMPTY_TRANSCRIPTION"
                )
            
            cleaned_text = self._clean_transcription(raw_text)
            
            self._increment_rate_limit(user_id)
            
            logger.info(f"Successfully transcribed audio for user {user_id}")
            return TranscriptionResult(success=True, text=cleaned_text, raw_text=raw_text)
            
        except httpx.TimeoutException:
            logger.error(f"Hugging Face API timeout for user {user_id}")
            return TranscriptionResult(
                success=False,
                error="زمان پردازش صوت بیش از حد طول کشید. لطفاً دوباره تلاش کنید.",
                error_code="TIMEOUT"
            )
        except Exception as e:
            logger.exception(f"Transcription error for user {user_id}: {e}")
            return TranscriptionResult(
                success=False,
                error="خطای سیستمی در پردازش صوت",
                error_code="SYSTEM_ERROR"
            )
    
    def _clean_transcription(self, raw_text: str) -> str:
        """
        Clean and structure raw transcription using OpenRouter GLM-4.5-air.
        
        Args:
            raw_text: Raw transcription from Whisper
            
        Returns:
            Cleaned and structured text, or raw_text if cleaning fails
        """
        openrouter_key = getattr(settings, 'OPENROUTER_API_KEY', '')
        if not openrouter_key:
            logger.warning("OpenRouter API key not configured, returning raw transcription")
            return raw_text
        
        try:
            headers = {
                "Authorization": f"Bearer {openrouter_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": getattr(settings, 'SITE_URL', 'https://peyda.ir'),
                "X-Title": "Peyda Transcription",
            }
            
            payload = {
                "model": "deepseek/deepseek-v3.2",
                "messages": [
                    {
                        "role": "system",
                        "content": TRANSCRIPTION_PROMPT
                    },
                    {
                        "role": "user",
                        "content": f"این متن رونویسی شده از یک فایل صوتی است. لطفاً آن را پاکسازی و ساختارمند کنید:\n\n{raw_text}"
                    }
                ],
                "temperature": 0.3,
                "max_tokens": 1024,
            }
            
            api_url = getattr(settings, 'OPENROUTER_API_URL', 'https://openrouter.ai/api/v1/chat/completions')
            
            with httpx.Client(timeout=120.0) as client:
                response = client.post(api_url, headers=headers, json=payload)
            
            if response.status_code != 200:
                logger.error(f"OpenRouter API error: {response.status_code} - {response.text}")
                return raw_text
            
            result = response.json()
            cleaned_text = result.get('choices', [{}])[0].get('message', {}).get('content', '')
            
            if cleaned_text:
                logger.info("Successfully cleaned transcription with GLM-4.5-air")
                return cleaned_text
            
            return raw_text
            
        except Exception as e:
            logger.exception(f"Error cleaning transcription: {e}")
            return raw_text
    
    def _get_rate_limit_key(self, user_id: int) -> str:
        """Get cache key for rate limiting."""
        return f"transcription_rate:{user_id}"
    
    def _check_rate_limit(self, user_id: int) -> bool:
        """Check if user is within rate limit. Returns True if allowed."""
        if not self._cache:
            return True
        
        key = self._get_rate_limit_key(user_id)
        count = self._cache.get_json(key) or 0
        return count < self.DAILY_LIMIT
    
    def _increment_rate_limit(self, user_id: int) -> None:
        """Increment rate limit counter for user."""
        if not self._cache:
            return
        
        key = self._get_rate_limit_key(user_id)
        count = self._cache.get_json(key) or 0
        self._cache.set_json(key, count + 1, ttl=self.RATE_LIMIT_TTL)
    
    def get_remaining_requests(self, user_id: int) -> int:
        """Get remaining requests for user today."""
        if not self._cache:
            return self.DAILY_LIMIT
        
        key = self._get_rate_limit_key(user_id)
        count = self._cache.get_json(key) or 0
        return max(0, self.DAILY_LIMIT - count)

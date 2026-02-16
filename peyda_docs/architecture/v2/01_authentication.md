# معماری لِسان v2 - احراز هویت

## ۱. جریان احراز هویت Mini-App

### ۱.۱ مفهوم Init Data
پیام‌رسان‌ها (ایتا، تلگرام، بله) هنگام باز کردن Mini-App یک `initData` به فرانت‌اند می‌دهند که شامل اطلاعات کاربر و امضای دیجیتال است.

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Messenger     │     │   Mini-App      │     │   Backend       │
│   (ایتا/تلگرام) │     │   (React)       │     │   (Django)      │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         │  1. Launch Mini-App   │                       │
         │  + initData           │                       │
         │──────────────────────>│                       │
         │                       │                       │
         │                       │  2. API Request       │
         │                       │  Authorization: InitData <initData>
         │                       │  X-Platform: eitaa    │
         │                       │  X-App-SKU: PEYDA     │
         │                       │──────────────────────>│
         │                       │                       │
         │                       │                       │  3. Verify hash
         │                       │                       │  using bot_token
         │                       │                       │
         │                       │  4. Response          │
         │                       │<──────────────────────│
         │                       │                       │
```

### ۱.۲ ساختار Init Data

```python
# Telegram/Eitaa/Bale initData format (URL-encoded)
initData = "query_id=AAHdF...&user=%7B%22id%22%3A...%7D&auth_date=1234567890&hash=abc123..."

# Decoded user object
{
    "id": 123456789,
    "first_name": "علی",
    "last_name": "محمدی",
    "username": "ali_m",
    "language_code": "fa"
}
```

### ۱.۳ اعتبارسنجی Hash

```python
# services/auth_service.py
import hashlib
import hmac
from urllib.parse import parse_qs, unquote

class AuthService(BaseService):
    
    def authenticate(
        self,
        init_data: str,
        platform: str,           # eitaa | telegram | bale
        app_sku: str,            # PEYDA
        client_ip: str
    ) -> User:
        """احراز هویت از initData پیام‌رسان"""
        
        # 1. Get bot token for platform
        bot_token = self._get_bot_token(platform, app_sku)
        
        # 2. Verify hash
        if not self._verify_init_data_hash(init_data, bot_token):
            raise AuthenticationError("Invalid init data hash")
        
        # 3. Parse user data
        user_data = self._parse_init_data(init_data)
        
        # 4. Check auth_date (prevent replay attacks)
        if not self._is_auth_date_valid(user_data['auth_date']):
            raise AuthenticationError("Init data expired")
        
        # 5. Get or create user
        user, created = User.objects.get_or_create(
            platform=platform,
            platform_user_id=str(user_data['user']['id']),
            defaults={
                'username': user_data['user'].get('username'),
                'display_name': self._build_display_name(user_data['user']),
                'last_ip': client_ip
            }
        )
        
        # 6. Update last activity
        if not created:
            user.last_ip = client_ip
            user.last_activity = self._clock.now()
            user.save(update_fields=['last_ip', 'last_activity'])
        else:
            self._event_bus.publish('user.created', {
                'user_id': user.id,
                'platform': platform,
                'app_sku': app_sku,
                'timestamp': self._clock.now().isoformat()
            })
        
        return user
    
    def _verify_init_data_hash(self, init_data: str, bot_token: str) -> bool:
        """اعتبارسنجی امضای initData با توکن بات"""
        
        # Parse init_data
        parsed = parse_qs(init_data)
        received_hash = parsed.get('hash', [''])[0]
        
        # Build data-check-string (sorted, excluding hash)
        data_check_arr = []
        for key, value in sorted(parsed.items()):
            if key != 'hash':
                data_check_arr.append(f"{key}={value[0]}")
        data_check_string = '\n'.join(data_check_arr)
        
        # Calculate secret key
        secret_key = hmac.new(
            b"WebAppData",
            bot_token.encode(),
            hashlib.sha256
        ).digest()
        
        # Calculate hash
        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(calculated_hash, received_hash)
    
    def _get_bot_token(self, platform: str, app_sku: str) -> str:
        """دریافت توکن بات بر اساس پلتفرم و SKU"""
        from django.conf import settings
        
        # settings.BOT_TOKENS = {
        #     'PEYDA': {
        #         'eitaa': 'bot123:ABC...',
        #         'telegram': 'bot456:DEF...',
        #         'bale': 'bot789:GHI...',
        #     }
        # }
        return settings.BOT_TOKENS[app_sku][platform]
    
    def _is_auth_date_valid(self, auth_date: int, max_age_seconds: int = 86400) -> bool:
        """بررسی تازگی initData (پیش‌فرض: ۲۴ ساعت)"""
        now = int(self._clock.now().timestamp())
        return (now - auth_date) < max_age_seconds
```

### ۱.۴ Middleware
**HUMAN OVERRIDE**: no need for a middleware. the authentications.py can read app sku and platform sku from token (app:platorm|init data) + ip from header and pass them to the auth service
```python
# apps/api/middleware.py
from pydantic import BaseModel, ValidationError
from services.auth_service import AuthService
from infrastructure.bootstrap import get_container

class AuthenticatedRequest(BaseModel):
    """مدل درخواست احراز هویت شده"""
    init_data: str
    platform: str
    app_sku: str
    client_ip: str


class MessengerAuthMiddleware:
    """Middleware برای احراز هویت Mini-App"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        
        if auth_header.startswith('InitData '):
            init_data = auth_header[9:]  # Remove 'InitData ' prefix
            platform = request.META.get('HTTP_X_PLATFORM', '').lower()
            app_sku = request.META.get('HTTP_X_APP_SKU', 'PEYDA')
            client_ip = self._get_client_ip(request)
            
            if platform in ('eitaa', 'telegram', 'bale'):
                container = get_container()
                auth_service = container.get(AuthService)
                
                try:
                    user = auth_service.authenticate(
                        init_data=init_data,
                        platform=platform,
                        app_sku=app_sku,
                        client_ip=client_ip
                    )
                    request.user = user
                    request.platform = platform
                    request.app_sku = app_sku
                except Exception as e:
                    # Log error but don't fail - let view handle auth
                    request.auth_error = str(e)
        
        return self.get_response(request)
    
    def _get_client_ip(self, request) -> str:
        """استخراج IP واقعی کاربر"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '')
```

---

## ۲. مدل کاربر (بهبود یافته)

```python
# apps/users/models.py
from django.db import models

class User(models.Model):
    class Platform(models.TextChoices):
        EITAA = 'eitaa', 'ایتا'
        TELEGRAM = 'telegram', 'تلگرام'
        BALE = 'bale', 'بله'
    
    platform = models.CharField(max_length=20, choices=Platform.choices)
    platform_user_id = models.CharField(max_length=100)
    username = models.CharField(max_length=100, null=True, blank=True)
    display_name = models.CharField(max_length=200, null=True, blank=True) **HUMAN OVERRIDE**: this is the name from init data. we'll have a display name later
    
    # Security & Analytics
    last_ip = models.GenericIPAddressField(null=True, blank=True)
    last_activity = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Flags
    is_banned = models.BooleanField(default=False)
    ban_reason = models.TextField(null=True, blank=True)
    
    class Meta:
        unique_together = ['platform', 'platform_user_id']
        indexes = [
            models.Index(fields=['platform', 'platform_user_id']),
            models.Index(fields=['last_activity']),
        ]
```
**HUMAN OVERRIDE**: we need a session model too. in that model, store the init data and start param (if any)

---

## ۳. تنظیمات

```python
# config/settings/base.py

BOT_TOKENS = {
    'PEYDA': {
        'eitaa': os.environ.get('EITAA_BOT_TOKEN'),
        'telegram': os.environ.get('TELEGRAM_BOT_TOKEN'),
        'bale': os.environ.get('BALE_BOT_TOKEN'),
    }
}

# Auth settings
AUTH_INIT_DATA_MAX_AGE = 86400  # 24 hours
```

---

## ۴. ریسک‌ها و ملاحظات امنیتی

| ریسک | شدت | راه‌حل |
|------|-----|--------|
| **Replay Attack** | متوسط | بررسی `auth_date` و حداکثر عمر ۲۴ ساعت |
| **Token Leak** | بالا | ذخیره توکن‌ها در env variables، نه در کد |
| **IP Spoofing** | پایین | اعتماد به `X-Forwarded-For` فقط از reverse proxy |
| **Rate Limiting** | متوسط | محدودیت تعداد درخواست احراز هویت |

### ۴.۱ Rate Limiting پیشنهادی

```python
# آستانه‌های پیشنهادی
RATE_LIMITS = {
    'auth_per_minute': 10,        # حداکثر ۱۰ تلاش احراز هویت در دقیقه
    'auth_per_hour_per_ip': 100,  # حداکثر ۱۰۰ تلاش از یک IP در ساعت
}
```

# معماری لِسان v3 - احراز هویت و Session

## ۱. فرمت توکن

### ۱.۱ ساختار Authorization Header

```
Authorization: InitData <app_sku>:<platform>|<init_data>

مثال:
Authorization: InitData PEYDA:eitaa|query_id=AAHdF...&user=%7B...%7D&hash=abc123
```

**Parser:**
```python
# apps/api/authentication.py
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from typing import Tuple, Optional
from apps.users.models import User

class InitDataAuthentication(BaseAuthentication):
    """احراز هویت با InitData از Mini-App SDK"""
    
    def authenticate(self, request) -> Optional[Tuple[User, dict]]:
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        
        if not auth_header.startswith('InitData '):
            return None
        
        try:
            # Parse: "InitData PEYDA:eitaa|query_id=..."
            token = auth_header[9:]  # Remove 'InitData '
            prefix, init_data = token.split('|', 1)
            app_sku, platform = prefix.split(':')
            
            # Get client IP
            client_ip = self._get_client_ip(request)
            
            # Authenticate via service
            from infrastructure.bootstrap import get_container
            from services.auth_service import AuthService
            
            container = get_container()
            auth_service = container.get(AuthService)
            
            user, session = auth_service.authenticate(
                init_data=init_data,
                platform=platform.lower(),
                app_sku=app_sku.upper(),
                client_ip=client_ip
            )
            
            # Attach extra info to request
            request.session_obj = session
            request.platform = platform.lower()
            request.app_sku = app_sku.upper()
            
            return (user, {'session': session})
            
        except ValueError as e:
            raise AuthenticationFailed(f'Invalid token format: {e}')
        except Exception as e:
            raise AuthenticationFailed(str(e))
    
    def _get_client_ip(self, request) -> str:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '')
```

---

## ۲. مدل‌های داده

### ۲.۱ User Model

```python
# apps/users/models.py
from django.db import models

class User(models.Model):
    """کاربر - یکتا بر اساس platform + platform_user_id"""
    
    class Platform(models.TextChoices):
        EITAA = 'eitaa', 'ایتا'
        TELEGRAM = 'telegram', 'تلگرام'
        BALE = 'bale', 'بله'
    
    platform = models.CharField(max_length=20, choices=Platform.choices)
    platform_user_id = models.CharField(max_length=100)
    
    # از init_data می‌آید
    username = models.CharField(max_length=100, null=True, blank=True)
    platform_name = models.CharField(
        max_length=200, 
        null=True, 
        blank=True,
        help_text="نام از init_data (first_name + last_name)"
    )
    
    # نام نمایشی قابل ویرایش توسط کاربر (V2)
    display_name = models.CharField(
        max_length=200, 
        null=True, 
        blank=True,
        help_text="نام نمایشی انتخابی کاربر"
    )
    
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
    
    def get_display_name(self) -> str:
        """نام نمایشی با fallback"""
        return self.display_name or self.platform_name or self.username or f"User {self.id}"
```

### ۲.۲ Session Model (جدید)

```python
# apps/users/models.py

class Session(models.Model):
    """نشست کاربر - هر بار باز کردن Mini-App یک Session جدید"""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sessions')
    
    # از init_data
    init_data_hash = models.CharField(
        max_length=64, 
        db_index=True,
        help_text="SHA256 hash of init_data برای جلوگیری از تکرار"
    )
    auth_date = models.PositiveIntegerField(help_text="Unix timestamp از init_data")
    
    # پارامترهای ورود
    start_param = models.CharField(
        max_length=500, 
        null=True, 
        blank=True,
        help_text="پارامتر start از deep link (مثلاً referral code)"
    )
    
    # Context
    platform = models.CharField(max_length=20)
    app_sku = models.CharField(max_length=50)
    client_ip = models.GenericIPAddressField()
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    last_request_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['init_data_hash']),
            models.Index(fields=['start_param']),  # برای analytics referral
        ]
```

---

## ۳. AuthService (بهبود یافته)

```python
# services/auth_service.py
import hashlib
import hmac
import json
from urllib.parse import parse_qs
from typing import Tuple
from apps.users.models import User, Session
from .base import BaseService

class AuthService(BaseService):
    
    def authenticate(
        self,
        init_data: str,
        platform: str,
        app_sku: str,
        client_ip: str
    ) -> Tuple[User, Session]:
        """احراز هویت و ایجاد/بازیابی Session"""
        
        # 1. Get bot token
        bot_token = self._get_bot_token(platform, app_sku)
        
        # 2. Verify hash
        if not self._verify_init_data_hash(init_data, bot_token):
            raise AuthenticationError("Invalid init data hash")
        
        # 3. Parse data
        parsed = self._parse_init_data(init_data)
        user_data = parsed['user']
        auth_date = parsed['auth_date']
        start_param = parsed.get('start_param')
        
        # 4. Check auth_date
        if not self._is_auth_date_valid(auth_date):
            raise AuthenticationError("Init data expired")
        
        # 5. Check for duplicate session (replay attack)
        init_data_hash = hashlib.sha256(init_data.encode()).hexdigest()
        existing_session = Session.objects.filter(init_data_hash=init_data_hash).first()
        if existing_session:
            # Return existing session (idempotent)
            existing_session.last_request_at = self._clock.now()
            existing_session.save(update_fields=['last_request_at'])
            return existing_session.user, existing_session
        
        # 6. Get or create user
        user, created = User.objects.get_or_create(
            platform=platform,
            platform_user_id=str(user_data['id']),
            defaults={
                'username': user_data.get('username'),
                'platform_name': self._build_platform_name(user_data),
                'last_ip': client_ip
            }
        )
        
        # 7. Update user if not created
        if not created:
            user.last_ip = client_ip
            user.last_activity = self._clock.now()
            # Update platform_name if changed
            new_name = self._build_platform_name(user_data)
            if new_name != user.platform_name:
                user.platform_name = new_name
            user.save(update_fields=['last_ip', 'last_activity', 'platform_name'])
        
        # 8. Create session
        session = Session.objects.create(
            user=user,
            init_data_hash=init_data_hash,
            auth_date=auth_date,
            start_param=start_param,
            platform=platform,
            app_sku=app_sku,
            client_ip=client_ip
        )
        
        # 9. Publish event for new users
        if created:
            self._event_bus.publish('user.created', {
                'user_id': user.id,
                'platform': platform,
                'app_sku': app_sku,
                'start_param': start_param,
                'timestamp': int(self._clock.now().timestamp())  # Unix timestamp
            })
        
        return user, session
    
    def _parse_init_data(self, init_data: str) -> dict:
        """Parse init_data to dict"""
        parsed = parse_qs(init_data)
        
        result = {
            'auth_date': int(parsed.get('auth_date', ['0'])[0]),
            'hash': parsed.get('hash', [''])[0],
        }
        
        # Parse user JSON
        if 'user' in parsed:
            result['user'] = json.loads(parsed['user'][0])
        
        # Start param (deep link parameter)
        if 'start_param' in parsed:
            result['start_param'] = parsed['start_param'][0]
        
        return result
    
    def _build_platform_name(self, user_data: dict) -> str:
        """ساخت نام از first_name و last_name"""
        parts = []
        if user_data.get('first_name'):
            parts.append(user_data['first_name'])
        if user_data.get('last_name'):
            parts.append(user_data['last_name'])
        return ' '.join(parts) if parts else None
    
    def _verify_init_data_hash(self, init_data: str, bot_token: str) -> bool:
        """اعتبارسنجی امضای initData"""
        parsed = parse_qs(init_data)
        received_hash = parsed.get('hash', [''])[0]
        
        data_check_arr = []
        for key, value in sorted(parsed.items()):
            if key != 'hash':
                data_check_arr.append(f"{key}={value[0]}")
        data_check_string = '\n'.join(data_check_arr)
        
        secret_key = hmac.new(
            b"WebAppData",
            bot_token.encode(),
            hashlib.sha256
        ).digest()
        
        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(calculated_hash, received_hash)
    
    def _get_bot_token(self, platform: str, app_sku: str) -> str:
        from django.conf import settings
        return settings.BOT_TOKENS[app_sku][platform]
    
    def _is_auth_date_valid(self, auth_date: int, max_age_seconds: int = 86400) -> bool:
        now = int(self._clock.now().timestamp())
        return (now - auth_date) < max_age_seconds
```

---

## ۴. تنظیمات DRF

```python
# config/settings/base.py

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'apps.api.authentication.InitDataAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}

BOT_TOKENS = {
    'PEYDA': {
        'eitaa': os.environ.get('EITAA_BOT_TOKEN'),
        'telegram': os.environ.get('TELEGRAM_BOT_TOKEN'),
        'bale': os.environ.get('BALE_BOT_TOKEN'),
    }
}

AUTH_INIT_DATA_MAX_AGE = 86400  # 24 hours
```

---

## ۵. Start Param Use Cases

`start_param` از deep link می‌آید و می‌تواند برای:

| Use Case | مثال start_param | کاربرد |
|----------|-----------------|--------|
| **Referral** | `ref_12345` | ردیابی دعوت‌کننده |
| **Campaign** | `utm_ramadan24` | ردیابی کمپین تبلیغاتی |
| **Deep Link** | `juz_5` | باز کردن مستقیم جزء خاص |
| **Invite Link** | `invite_abc123` | لینک دعوت گروهی |

```python
# استفاده در analytics
def track_referral(session: Session):
    if session.start_param and session.start_param.startswith('ref_'):
        referrer_id = session.start_param[4:]
        # Track referral...
```

---

## ۶. Session Analytics Queries

```sql
-- تعداد session ها به تفکیک پلتفرم
SELECT platform, COUNT(*) as sessions
FROM users_session
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY platform;

-- کاربران با start_param (referral tracking)
SELECT start_param, COUNT(DISTINCT user_id) as users
FROM users_session
WHERE start_param IS NOT NULL
GROUP BY start_param
ORDER BY users DESC;

-- میانگین session ها به ازای هر کاربر
SELECT AVG(session_count) FROM (
    SELECT user_id, COUNT(*) as session_count
    FROM users_session
    GROUP BY user_id
) sub;
```

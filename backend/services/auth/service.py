"""
OTP Authentication Service - handles phone-based OTP authentication.

Based on OpenAPI.yaml:
- POST /auth/send-otp: Send OTP to phone
- POST /auth/verify-otp: Verify OTP and get JWT token
- POST /auth/resend-otp: Resend OTP for existing request
"""
import secrets
import hashlib
import logging
from typing import Optional, Tuple
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


@dataclass
class SendOTPResult:
    """Result of sending OTP."""
    success: bool
    request_id: Optional[str] = None
    expires_in: int = 300
    max_attempts: int = 3
    max_resends: int = 3
    error: Optional[str] = None
    error_code: Optional[str] = None


@dataclass
class VerifyOTPResult:
    """Result of verifying OTP."""
    success: bool
    token: Optional[str] = None
    user_id: Optional[int] = None
    is_new_user: bool = False
    error: Optional[str] = None
    error_code: Optional[str] = None


@dataclass
class ResendOTPResult:
    """Result of resending OTP."""
    success: bool
    request_id: Optional[str] = None
    expires_in: int = 300
    remaining_resends: int = 0
    error: Optional[str] = None
    error_code: Optional[str] = None


class OTPAuthService:
    """
    OTP-based authentication service.
    
    Flow:
    1. User sends phone number -> send_otp()
    2. OTP is sent via n8n to messenger
    3. User enters OTP -> verify_otp()
    4. JWT token is returned
    """
    
    OTP_LENGTH = 4
    OTP_EXPIRY_SECONDS = 300  # 5 minutes
    MAX_ATTEMPTS = 3
    MAX_RESENDS = 3
    
    def __init__(self, cache=None, event_bus=None):
        self._cache = cache
        self._event_bus = event_bus
    
    def send_otp(self, phone: str, country_code: str = '+98') -> SendOTPResult:
        """
        Send OTP to phone number.
        
        Args:
            phone: Phone number without country code (e.g., "9123456789")
            country_code: Country code (e.g., "+98")
        
        Returns:
            SendOTPResult with request_id on success
        """
        # Validate phone
        if not self._validate_phone(phone):
            return SendOTPResult(
                success=False,
                error="شماره موبایل نامعتبر است",
                error_code="INVALID_PHONE"
            )
        
        full_phone = f"{country_code}{phone}"
        
        # Check rate limiting
        if self._is_rate_limited(full_phone):
            return SendOTPResult(
                success=False,
                error="تعداد درخواست‌های شما بیش از حد مجاز است. لطفاً بعداً تلاش کنید.",
                error_code="TOO_MANY_REQUESTS"
            )
        
        # Generate OTP and request_id
        otp = self._generate_otp()
        logger.info(f"OTP generated for {full_phone}: {otp}")
        request_id = self._generate_request_id()
        
        # Store OTP data in cache
        otp_data = {
            'otp': otp,
            'phone': full_phone,
            'attempts': 0,
            'resends': 0,
            'created_at': timezone.now().isoformat()
        }
        
        if self._cache:
            self._cache.set_json(
                f"otp:{request_id}",
                otp_data,
                ttl=self.OTP_EXPIRY_SECONDS
            )
        
        # Publish event for n8n to send OTP via messenger
        if self._event_bus:
            self._event_bus.publish('otp.send_requested', {
                'request_id': request_id,
                'phone': full_phone,
                'otp': otp,
                'expires_in': self.OTP_EXPIRY_SECONDS
            })
        
        logger.info(f"OTP sent to {full_phone[:5]}***")
        
        return SendOTPResult(
            success=True,
            request_id=request_id,
            expires_in=self.OTP_EXPIRY_SECONDS,
            max_attempts=self.MAX_ATTEMPTS,
            max_resends=self.MAX_RESENDS
        )
    
    def verify_otp(self, request_id: str, otp: str) -> VerifyOTPResult:
        """
        Verify OTP and return JWT token.
        
        Args:
            request_id: Request ID from send_otp
            otp: OTP code entered by user
        
        Returns:
            VerifyOTPResult with token on success
        """
        if not self._cache:
            return VerifyOTPResult(
                success=False,
                error="خطای سیستمی",
                error_code="SYSTEM_ERROR"
            )
        
        # Get OTP data from cache
        otp_data = self._cache.get_json(f"otp:{request_id}")
        
        if not otp_data:
            return VerifyOTPResult(
                success=False,
                error="شناسه درخواست OTP معتبر نیست.",
                error_code="INVALID_REQUEST_ID"
            )
        
        # Check attempts
        if otp_data.get('attempts', 0) >= self.MAX_ATTEMPTS:
            return VerifyOTPResult(
                success=False,
                error="تعداد تلاش‌های شما برای ورود کد به حداکثر رسیده است. لطفاً کد جدید درخواست دهید.",
                error_code="MAX_ATTEMPTS_REACHED"
            )
        
        # Increment attempts
        otp_data['attempts'] = otp_data.get('attempts', 0) + 1
        self._cache.set_json(f"otp:{request_id}", otp_data, ttl=self.OTP_EXPIRY_SECONDS)
        
        # Verify OTP
        if otp_data.get('otp') != otp:
            return VerifyOTPResult(
                success=False,
                error="کد تایید وارد شده صحیح نیست.",
                error_code="INVALID_OTP"
            )
        
        # OTP is valid - get or create user
        phone = otp_data.get('phone')
        user, is_new = self._get_or_create_user(phone)
        
        # Generate JWT token
        token = self._generate_jwt_token(user)
        
        # Delete OTP data
        self._cache.delete(f"otp:{request_id}")
        
        logger.info(f"User {user.id} authenticated via OTP")
        
        return VerifyOTPResult(
            success=True,
            token=token,
            user_id=user.id,
            is_new_user=is_new
        )
    
    def resend_otp(self, request_id: str) -> ResendOTPResult:
        """
        Resend OTP for existing request.
        
        Args:
            request_id: Request ID from send_otp
        
        Returns:
            ResendOTPResult with remaining resends
        """
        if not self._cache:
            return ResendOTPResult(
                success=False,
                error="خطای سیستمی",
                error_code="SYSTEM_ERROR"
            )
        
        # Get OTP data from cache
        otp_data = self._cache.get_json(f"otp:{request_id}")
        
        if not otp_data:
            return ResendOTPResult(
                success=False,
                error="شناسه درخواست OTP معتبر نیست یا منقضی شده است.",
                error_code="INVALID_REQUEST_ID"
            )
        
        # Check resends
        resends = otp_data.get('resends', 0)
        if resends >= self.MAX_RESENDS:
            return ResendOTPResult(
                success=False,
                error="حداکثر تعداد ارسال مجدد استفاده شده است.",
                error_code="MAX_RESENDS_REACHED"
            )
        
        # Generate new OTP
        new_otp = self._generate_otp()
        otp_data['otp'] = new_otp
        otp_data['resends'] = resends + 1
        otp_data['attempts'] = 0  # Reset attempts on resend
        
        self._cache.set_json(f"otp:{request_id}", otp_data, ttl=self.OTP_EXPIRY_SECONDS)
        
        # Publish event for n8n to send OTP
        if self._event_bus:
            self._event_bus.publish('otp.send_requested', {
                'request_id': request_id,
                'phone': otp_data.get('phone'),
                'otp': new_otp,
                'expires_in': self.OTP_EXPIRY_SECONDS
            })
        
        remaining = self.MAX_RESENDS - otp_data['resends']
        
        return ResendOTPResult(
            success=True,
            request_id=request_id,
            expires_in=self.OTP_EXPIRY_SECONDS,
            remaining_resends=remaining
        )
    
    def _validate_phone(self, phone: str) -> bool:
        """Validate Iranian phone number."""
        if not phone:
            return False
        # Remove country code prefix if present
        if phone.startswith('+98'):
            phone = phone[3:]
        elif phone.startswith('98'):
            phone = phone[2:]
        # Remove leading zeros
        phone = phone.lstrip('0')
        # Should be 10 digits starting with 9
        return len(phone) == 10 and phone.startswith('9') and phone.isdigit()
    
    def _generate_otp(self) -> str:
        """Generate random OTP code."""
        return ''.join([str(secrets.randbelow(10)) for _ in range(self.OTP_LENGTH)])
    
    def _generate_request_id(self) -> str:
        """Generate unique request ID."""
        return f"req_{secrets.token_hex(16)}"
    
    def _is_rate_limited(self, phone: str) -> bool:
        """Check if phone is rate limited."""
        if not self._cache:
            return False
        
        key = f"otp_rate:{hashlib.md5(phone.encode()).hexdigest()}"
        count = self._cache.get_json(key) or 0
        
        if count >= 5:  # Max 5 OTP requests per hour
            return True
        
        self._cache.set_json(key, count + 1, ttl=3600)
        return False
    
    def _get_or_create_user(self, phone: str):
        """Get or create user by phone."""
        from apps.users.models import User
        
        user, created = User.objects.get_or_create(
            phone=phone,
            defaults={
                'is_active': True,
                'last_activity_at': timezone.now()
            }
        )
        
        if not created:
            user.last_activity_at = timezone.now()
            user.save(update_fields=['last_activity_at'])
        
        return user, created
    
    def _generate_jwt_token(self, user) -> str:
        """Generate JWT token for user."""
        import jwt
        from datetime import datetime, timedelta
        
        payload = {
            'user_id': user.id,
            'phone': user.phone,
            'role': user.role,
            'exp': datetime.utcnow() + timedelta(days=30),
            'iat': datetime.utcnow()
        }
        
        secret = getattr(settings, 'SECRET_KEY', 'secret')
        return jwt.encode(payload, secret, algorithm='HS256')
    
    def logout(self, token: str) -> bool:
        """
        Logout user by blacklisting the token.
        
        Args:
            token: JWT token to blacklist
            
        Returns:
            True if successful, False otherwise
        """
        if not self._cache:
            return False
        
        try:
            import jwt
            from datetime import datetime, timedelta
            
            # Decode token to get expiration time
            payload = jwt.decode(
                token,
                getattr(settings, 'SECRET_KEY', 'secret'),
                algorithms=['HS256']
            )
            
            exp = payload.get('exp')
            if not exp:
                return False
            
            # Calculate remaining time until expiration
            now = datetime.utcnow()
            exp_datetime = datetime.fromtimestamp(exp)
            ttl = int((exp_datetime - now).total_seconds())
            
            if ttl <= 0:
                return False  # Token already expired
            
            # Add token to blacklist
            blacklist_key = f"blacklist:{hashlib.sha256(token.encode()).hexdigest()}"
            self._cache.set_json(blacklist_key, True, ttl=ttl)
            
            logger.info(f"Token blacklisted for user {payload.get('user_id')}")
            return True
            
        except jwt.InvalidTokenError:
            return False
    
    def is_token_blacklisted(self, token: str) -> bool:
        """
        Check if token is blacklisted.
        
        Args:
            token: JWT token to check
            
        Returns:
            True if blacklisted, False otherwise
        """
        if not self._cache:
            return False
        
        blacklist_key = f"blacklist:{hashlib.sha256(token.encode()).hexdigest()}"
        return self._cache.get_json(blacklist_key) is not None

"""
DRF Authentication class for JWT-based auth (OTP flow).
"""
import jwt
from rest_framework import authentication, exceptions
from django.conf import settings


class JWTAuthentication(authentication.BaseAuthentication):
    """
    JWT Authentication for Peyda API.
    
    Authorization header format:
    - Bearer <jwt_token>
    
    JWT is obtained via OTP verification flow:
    1. POST /auth/send-otp
    2. POST /auth/verify-otp -> returns JWT token
    """
    
    def authenticate(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        
        if not auth_header.startswith('Bearer '):
            return None
        
        token = auth_header[7:]  # Remove 'Bearer ' prefix
        
        if not token:
            return None
        
        # Check if token is blacklisted
        from infrastructure.bootstrap import get_container
        from services.auth import OTPAuthService
        
        container = get_container()
        auth_service = container.get(OTPAuthService)
        
        if auth_service.is_token_blacklisted(token):
            raise exceptions.AuthenticationFailed('توکن نامعتبر است')
        
        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=['HS256']
            )
        except jwt.ExpiredSignatureError:
            raise exceptions.AuthenticationFailed('توکن منقضی شده است')
        except jwt.InvalidTokenError:
            raise exceptions.AuthenticationFailed('توکن نامعتبر است')
        
        user_id = payload.get('user_id')
        if not user_id:
            raise exceptions.AuthenticationFailed('توکن نامعتبر است')
        
        from apps.users.models import User
        
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise exceptions.AuthenticationFailed('کاربر یافت نشد')
        
        if not user.is_active:
            raise exceptions.AuthenticationFailed('حساب کاربری غیرفعال است')
        
        if user.is_banned:
            raise exceptions.AuthenticationFailed('حساب کاربری مسدود شده است')
        
        return (user, token)
    
    def authenticate_header(self, request):
        return 'Bearer'

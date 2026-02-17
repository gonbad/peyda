"""
Auth ViewSet - OTP-based authentication endpoints.

Based on OpenAPI.yaml:
- POST /auth/send-otp
- POST /auth/verify-otp
- POST /auth/resend-otp
"""
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.authentication import get_authorization_header

from .base import BaseViewSet
from services.auth import OTPAuthService
from infrastructure.bootstrap import get_container


class AuthViewSet(BaseViewSet):
    """احراز هویت با OTP"""
    
    permission_classes = [AllowAny]
    
    @action(detail=False, methods=['post'], url_path='send-otp')
    def send_otp(self, request):
        """
        ارسال کد یکبار مصرف
        POST /auth/send-otp
        """
        phone = request.data.get('phone')
        country_code = request.data.get('country_code', '+98')
        
        if not phone:
            return self.error(
                "شماره موبایل الزامی است",
                "INVALID_PHONE",
                status.HTTP_400_BAD_REQUEST
            )
        
        container = get_container()
        auth_service = container.get(OTPAuthService)
        
        result = auth_service.send_otp(phone, country_code)
        
        if not result.success:
            status_code = status.HTTP_429_TOO_MANY_REQUESTS if result.error_code == 'TOO_MANY_REQUESTS' else status.HTTP_400_BAD_REQUEST
            return self.error(result.error, result.error_code, status_code)
        
        return self.success({
            'success': True,
            'message': 'کد تایید به شماره شما ارسال شد',
            'request_id': result.request_id,
            'expires_in': result.expires_in,
            'max_attempts': result.max_attempts,
            'max_resends': result.max_resends,
        })
    
    @action(detail=False, methods=['post'], url_path='verify-otp')
    def verify_otp(self, request):
        """
        تایید کد یکبار مصرف و ورود
        POST /auth/verify-otp
        """
        otp = request.data.get('otp')
        request_id = request.data.get('request_id')
        
        if not otp or not request_id:
            return self.error(
                "کد تایید و شناسه درخواست الزامی است",
                "INVALID_DATA",
                status.HTTP_400_BAD_REQUEST
            )
        
        container = get_container()
        auth_service = container.get(OTPAuthService)
        
        result = auth_service.verify_otp(request_id, otp)
        
        if not result.success:
            status_code = status.HTTP_403_FORBIDDEN if result.error_code == 'MAX_ATTEMPTS_REACHED' else status.HTTP_400_BAD_REQUEST
            return self.error(result.error, result.error_code, status_code)
        
        from apps.users.models import User
        user = User.objects.get(id=result.user_id)
        
        return self.success({
            'success': True,
            'token': result.token,
            'user': {
                'id': str(user.id),
                'phone': user.phone,
                'role': user.role,
                'is_verified': user.is_verified_mawkab_owner,
                'created_at': int(user.created_at.timestamp()),
            }
        })
    
    @action(detail=False, methods=['post'], url_path='resend-otp')
    def resend_otp(self, request):
        """
        ارسال مجدد کد یکبار مصرف
        POST /auth/resend-otp
        """
        request_id = request.data.get('request_id')
        
        if not request_id:
            return self.error(
                "شناسه درخواست الزامی است",
                "INVALID_REQUEST_ID",
                status.HTTP_400_BAD_REQUEST
            )
        
        container = get_container()
        auth_service = container.get(OTPAuthService)
        
        result = auth_service.resend_otp(request_id)
        
        if not result.success:
            status_code = status.HTTP_429_TOO_MANY_REQUESTS if result.error_code == 'MAX_RESENDS_REACHED' else status.HTTP_400_BAD_REQUEST
            return self.error(result.error, result.error_code, status_code)
        
        return self.success({
            'success': True,
            'message': 'کد تایید مجددا ارسال شد',
            'request_id': result.request_id,
            'expires_in': result.expires_in,
            'remaining_resends': result.remaining_resends,
        })
    
    @action(detail=False, methods=['post'], url_path='logout', permission_classes=[IsAuthenticated])
    def logout(self, request):
        """
        خروج کاربر و عدم اعتبار توکن
        POST /auth/logout
        """
        # Extract token from Authorization header
        auth_header = get_authorization_header(request).decode('utf-8')
        
        if not auth_header.startswith('Bearer '):
            return self.error(
                "توکن معتبر نیست",
                "INVALID_TOKEN",
                status.HTTP_401_UNAUTHORIZED
            )
        
        token = auth_header[7:]  # Remove 'Bearer ' prefix
        
        container = get_container()
        auth_service = container.get(OTPAuthService)
        
        success = auth_service.logout(token)
        
        if success:
            return self.success({
                'success': True,
                'message': 'خروج با موفقیت انجام شد'
            })
        else:
            return self.error(
                "خطا در خروج",
                "LOGOUT_FAILED",
                status.HTTP_400_BAD_REQUEST
            )

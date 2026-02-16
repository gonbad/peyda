"""
Mawkab ViewSet - mawkab management endpoints.

Based on OpenAPI.yaml:
- GET /mawkab
- POST /mawkab
- PUT /mawkab
- GET /mawkab/stats
"""
from rest_framework import status
from rest_framework.decorators import action

from .base import BaseViewSet
from services.commands import CreateMawkabCommand
from services.queries import GetMawkabQuery


class MawkabViewSet(BaseViewSet):
    """مدیریت موکب"""
    
    def list(self, request):
        """
        دریافت اطلاعات موکب کاربر
        GET /mawkab
        """
        query = self.get_query(GetMawkabQuery)
        result = query.execute(user_id=request.user.id)
        
        if not result.found:
            return self.success({
                'has_mawkab': False,
                'mawkab': None,
            })
        
        return self.success({
            'has_mawkab': True,
            'mawkab': result.mawkab,
        })
    
    def create(self, request):
        """
        ثبت موکب جدید
        POST /mawkab
        """
        command = self.get_command(CreateMawkabCommand)
        
        location = request.data.get('location', {})
        
        result = command.execute(
            user_id=request.user.id,
            name=request.data.get('name'),
            owner_name=request.data.get('owner_name'),
            owner_phone=request.data.get('phone', request.user.phone),
            latitude=location.get('latitude'),
            longitude=location.get('longitude'),
            address=request.data.get('address', ''),
        )
        
        if not result.success:
            if result.error_code == 'MAWKAB_EXISTS':
                return self.error(result.error, result.error_code, status.HTTP_409_CONFLICT)
            return self.error(result.error, result.error_code, status.HTTP_400_BAD_REQUEST)
        
        # Get created mawkab
        query = self.get_query(GetMawkabQuery)
        mawkab_result = query.execute(user_id=request.user.id)
        
        return self.success({
            'success': True,
            'message': 'موکب شما با موفقیت ثبت شد و در انتظار تایید است',
            'mawkab': mawkab_result.mawkab,
        }, status_code=status.HTTP_201_CREATED)
    
    def update(self, request, pk=None):
        """
        ویرایش اطلاعات موکب
        PUT /mawkab
        """
        from apps.mawkab.models import Mawkab
        from apps.users.models import User
        
        try:
            user = User.objects.get(id=request.user.id)
        except User.DoesNotExist:
            return self.not_found("کاربر یافت نشد")
        
        if not user.mawkab_id:
            return self.not_found("موکب مورد نظر یافت نشد")
        
        try:
            mawkab = Mawkab.objects.get(id=user.mawkab_id)
        except Mawkab.DoesNotExist:
            return self.not_found("موکب مورد نظر یافت نشد")
        
        # Update fields
        location = request.data.get('location', {})
        
        if 'name' in request.data:
            mawkab.name = request.data['name']
        if 'owner_name' in request.data:
            mawkab.owner_name = request.data['owner_name']
        if 'phone' in request.data:
            mawkab.owner_phone = request.data['phone']
        if 'address' in request.data:
            mawkab.address = request.data['address']
        if location.get('latitude'):
            mawkab.latitude = location['latitude']
        if location.get('longitude'):
            mawkab.longitude = location['longitude']
        
        mawkab.save()
        
        query = self.get_query(GetMawkabQuery)
        result = query.execute(user_id=request.user.id)
        
        return self.success({
            'success': True,
            'mawkab': result.mawkab,
        })
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        دریافت آمار عملکرد موکب
        GET /mawkab/stats
        """
        query = self.get_query(GetMawkabQuery)
        result = query.execute(user_id=request.user.id)
        
        if not result.found:
            return self.not_found("موکب یافت نشد")
        
        return self.success({
            'total_reports': result.mawkab['total_reports'],
            'resolved_reports': result.mawkab['resolved_reports'],
        })

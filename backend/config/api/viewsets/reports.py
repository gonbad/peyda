"""
Reports ViewSet - report management endpoints.

Based on OpenAPI.yaml:
- GET /reports
- POST /reports
- GET /reports/{reportId}
- PUT /reports/{reportId}/status
"""
from rest_framework import status
from rest_framework.decorators import action

from .base import BaseViewSet
from services.commands import CreateReportCommand, UpdateReportStatusCommand
from services.queries import GetReportsQuery, GetReportDetailQuery


class ReportsViewSet(BaseViewSet):
    """مدیریت گزارش‌ها"""
    
    def list(self, request):
        """
        دریافت لیست گزارش‌ها
        GET /reports
        """
        query = self.get_query(GetReportsQuery)
        
        result = query.execute(
            user_id=request.user.id,
            search=request.query_params.get('search'),
            report_type=request.query_params.get('type'),
            status=request.query_params.get('status'),
            gender=request.query_params.get('gender'),
            my_reports_only=request.query_params.get('my_reports_only', 'false').lower() == 'true',
            lat=float(request.query_params['lat']) if 'lat' in request.query_params else None,
            lng=float(request.query_params['lng']) if 'lng' in request.query_params else None,
            sort=request.query_params.get('sort', 'newest'),
            cursor=request.query_params.get('cursor'),
            limit=int(request.query_params.get('limit', 10)),
        )
        
        return self.success({
            'reports': result.reports,
            'pagination': {
                'next_cursor': result.next_cursor,
                'has_next': result.next_cursor is not None,
            },
            'total_matches': result.total_matches,
        })
    
    def create(self, request):
        """
        ثبت گزارش جدید
        POST /reports
        """
        command = self.get_command(CreateReportCommand)
        
        location = request.data.get('location', {})
        
        result = command.execute(
            user_id=request.user.id,
            report_type=request.data.get('type'),
            gender=request.data.get('gender'),
            latitude=location.get('latitude'),
            longitude=location.get('longitude'),
            contact_phone=request.data.get('contact_phone', request.user.phone),
            person_name=request.data.get('person_name'),
            age=request.data.get('age'),
            description=request.data.get('description', ''),
            address=location.get('address', ''),
            media_ids=request.data.get('media_ids'),
        )
        
        if not result.success:
            return self.error(result.error, result.error_code, status.HTTP_400_BAD_REQUEST)
        
        return self.success({
            'success': True,
            'message': 'گزارش شما با موفقیت ثبت شد',
            'tracking_code': result.tracking_code,
            'report': {'id': str(result.report_id)},
            'initial_matches': result.initial_matches or [],
        }, status_code=status.HTTP_201_CREATED)
    
    def retrieve(self, request, pk=None):
        """
        دریافت جزئیات گزارش
        GET /reports/{reportId}
        """
        query = self.get_query(GetReportDetailQuery)
        
        result = query.execute(
            report_id=pk,
            viewer_user_id=request.user.id
        )
        
        if not result.found:
            if result.error_code == 'ACCESS_DENIED':
                return self.forbidden(result.error)
            return self.not_found(result.error)
        
        # Get matches for this report
        from services.queries import GetMatchesQuery
        matches_query = self.get_query(GetMatchesQuery)
        matches_result = matches_query.execute(
            user_id=request.user.id,
            report_id=pk
        )
        
        return self.success({
            'report': result.report,
            'matches': matches_result.matches,
        })
    
    @action(detail=True, methods=['put'], url_path='status')
    def update_status(self, request, pk=None):
        """
        تغییر وضعیت گزارش
        PUT /reports/{reportId}/status
        """
        command = self.get_command(UpdateReportStatusCommand)
        
        result = command.execute(
            report_id=pk,
            user_id=request.user.id,
            new_status=request.data.get('status'),
            reason=request.data.get('reason', '')
        )
        
        if not result.success:
            if result.error_code == 'REPORT_NOT_FOUND':
                return self.not_found(result.error)
            if result.error_code == 'STATUS_CHANGE_DENIED':
                return self.forbidden(result.error)
            return self.error(result.error, result.error_code, status.HTTP_400_BAD_REQUEST)
        
        return self.success({
            'success': True,
            'message': 'وضعیت گزارش با موفقیت تغییر کرد',
        })

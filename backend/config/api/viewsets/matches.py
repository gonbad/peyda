"""
Matches ViewSet - match management endpoints.

Based on OpenAPI.yaml:
- GET /matches/{matchId}
- POST /matches/{matchId}
"""
from rest_framework import status
from rest_framework.decorators import action

from .base import BaseViewSet
from services.commands import MatchActionCommand
from services.queries import GetMatchesQuery


class MatchesViewSet(BaseViewSet):
    """مدیریت تطبیق‌ها"""
    
    def retrieve(self, request, pk=None):
        """
        دریافت جزئیات تطبیق
        GET /matches/{matchId}
        """
        from apps.reports.models import Match
        from django.db.models import Q
        
        try:
            match = Match.objects.select_related(
                'report_lost', 'report_found'
            ).get(id=pk)
        except Match.DoesNotExist:
            return self.not_found("تطبیق مورد نظر یافت نشد")
        
        # Check access
        is_lost_owner = match.report_lost.user_id == request.user.id
        is_found_owner = match.report_found.user_id == request.user.id
        
        if not is_lost_owner and not is_found_owner:
            return self.forbidden("فقط ثبت‌کنندگان گزارش‌های مرتبط می‌توانند اطلاعات تطبیق را مشاهده کنند")
        
        fetcher_side = 'lost_reporter' if is_lost_owner else 'found_reporter'
        
        def report_to_dict(report):
            return {
                'id': str(report.id),
                'type': report.report_type,
                'status': report.status,
                'person_name': report.name,
                'age': report.age,
                'gender': report.gender,
                'description': report.description,
                'image_urls': report.image_urls,
                'location': {
                    'latitude': float(report.latitude),
                    'longitude': float(report.longitude),
                    'address': report.address,
                },
                'contact_phone': report.contact_phone,
                'created_at': int(report.created_at.timestamp()),
            }
        
        return self.success({
            'match': {
                'id': str(match.id),
                'similarity_score': match.similarity_score,
                'status': match.status,
                'created_at': int(match.created_at.timestamp()),
            },
            'fetcher_side': fetcher_side,
            'lost_report': report_to_dict(match.report_lost),
            'found_report': report_to_dict(match.report_found),
            'similarity_score': match.similarity_score,
        })
    
    @action(detail=True, methods=['post'])
    def action(self, request, pk=None):
        """
        اقدام در مورد تطبیق
        POST /matches/{matchId}
        """
        command = self.get_command(MatchActionCommand)
        
        result = command.execute(
            match_id=pk,
            user_id=request.user.id,
            action=request.data.get('action'),
            notes=request.data.get('notes', '')
        )
        
        if not result.success:
            if result.error_code == 'MATCH_NOT_FOUND':
                return self.not_found(result.error)
            if result.error_code == 'ACTION_ACCESS_DENIED':
                return self.forbidden(result.error)
            return self.error(result.error, result.error_code, status.HTTP_400_BAD_REQUEST)
        
        return self.success({
            'success': True,
            'message': 'اقدام شما با موفقیت ثبت و به طرف مقابل اطلاع‌رسانی شد',
        })

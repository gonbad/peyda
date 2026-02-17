"""
Get Matches Query - retrieves matches for a user's reports.
"""
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from uuid import UUID

from .base import BaseQuery
from services.media import MediaService


@dataclass
class GetMatchesResult:
    """Result of getting matches."""
    matches: List[Dict[str, Any]]


class GetMatchesQuery(BaseQuery[GetMatchesResult]):
    """دریافت مچ‌های گزارش‌های کاربر"""
    
    def execute(
        self,
        user_id: int,
        report_id: Optional[UUID] = None,
        status: Optional[str] = None  # 'pending' or 'rejected'
    ) -> GetMatchesResult:
        from apps.reports.models import Match, Report
        from django.db.models import Q
        
        # Get user's reports
        user_report_ids = Report.objects.filter(user_id=user_id).values_list('id', flat=True)
        
        # Get matches where user's reports are involved
        queryset = Match.objects.filter(
            Q(report_lost_id__in=user_report_ids) | 
            Q(report_found_id__in=user_report_ids)
        ).select_related('report_lost', 'report_found')
        
        if report_id:
            queryset = queryset.filter(
                Q(report_lost_id=report_id) | Q(report_found_id=report_id)
            )
        
        if status:
            queryset = queryset.filter(status=status)
        
        queryset = queryset.order_by('-similarity_score', '-created_at')
        
        media_service = MediaService(cache=self._cache)
        matches = []
        for match in queryset:
            # Determine which report is "other" (not user's)
            if match.report_lost.user_id == user_id:
                my_report = match.report_lost
                other_report = match.report_found
            else:
                my_report = match.report_found
                other_report = match.report_lost
            
            # Resolve image URLs to presigned URLs
            other_image_urls = other_report.image_urls or []
            if other_image_urls:
                other_image_urls = media_service.resolve_media_urls(other_image_urls)
            
            matches.append({
                'id': str(match.id),
                'similarity_score': match.similarity_score,
                'status': match.status,
                'created_at': match.created_at.isoformat(),
                'my_report': {
                    'id': str(my_report.id),
                    'name': my_report.name,
                    'report_type': my_report.report_type,
                },
                'other_report': {
                    'id': str(other_report.id),
                    'name': other_report.name,
                    'report_type': other_report.report_type,
                    'age': other_report.age,
                    'gender': other_report.gender,
                    'image_urls': other_image_urls,
                    'latitude': float(other_report.latitude),
                    'longitude': float(other_report.longitude),
                    'contact_phone': other_report.contact_phone,  # Visible in match context
                },
                'can_reject': match.report_lost.user_id == user_id and match.status == Match.Status.PENDING,
            })
        
        return GetMatchesResult(matches=matches)

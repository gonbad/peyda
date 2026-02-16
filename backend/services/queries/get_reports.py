"""
Get Reports Query - retrieves reports with filtering and pagination.

Based on OpenAPI.yaml GET /reports
"""
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from .base import BaseQuery


@dataclass
class GetReportsResult:
    """Result of getting reports."""
    reports: List[Dict[str, Any]]
    next_cursor: Optional[str] = None
    total_matches: int = 0


class GetReportsQuery(BaseQuery[GetReportsResult]):
    """
    دریافت لیست گزارش‌ها با فیلتر و صفحه‌بندی
    
    GET /reports
    """
    
    def execute(
        self,
        user_id: int,
        search: Optional[str] = None,
        report_type: Optional[str] = None,  # 'lost' or 'found'
        status: Optional[str] = None,  # 'active', 'resolved', 'suspended'
        gender: Optional[str] = None,
        my_reports_only: bool = False,
        lat: Optional[float] = None,
        lng: Optional[float] = None,
        sort: str = 'newest',  # 'newest' or 'nearest'
        cursor: Optional[str] = None,
        limit: int = 10
    ) -> GetReportsResult:
        from apps.reports.models import Report, Match
        from apps.users.models import User
        from django.db.models import F, Q, Count
        from django.db.models.functions import Power, Sqrt
        
        # Check if user is verified mawkab owner
        try:
            user = User.objects.get(id=user_id)
            is_mawkab_owner = user.is_verified_mawkab_owner
        except User.DoesNotExist:
            is_mawkab_owner = False
        
        # Non-mawkab users can only see their own reports
        if not is_mawkab_owner:
            my_reports_only = True
        
        queryset = Report.objects.all()
        
        # Apply filters
        if my_reports_only:
            queryset = queryset.filter(user_id=user_id)
        
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | Q(description__icontains=search)
            )
        
        if report_type:
            queryset = queryset.filter(report_type=report_type)
        
        if status:
            queryset = queryset.filter(status=status)
        
        if gender:
            queryset = queryset.filter(gender=gender)
        
        # Sorting
        if sort == 'nearest' and lat is not None and lng is not None:
            # Simple distance calculation (not exact but good enough)
            queryset = queryset.annotate(
                distance=Sqrt(
                    Power(F('latitude') - lat, 2) + 
                    Power(F('longitude') - lng, 2)
                )
            ).order_by('distance')
        else:
            queryset = queryset.order_by('-created_at')
        
        # Cursor-based pagination
        if cursor:
            try:
                from django.utils.dateparse import parse_datetime
                cursor_date = parse_datetime(cursor)
                if cursor_date:
                    queryset = queryset.filter(created_at__lt=cursor_date)
            except (ValueError, TypeError):
                pass
        
        # Fetch one extra to check if there's more
        reports_list = list(queryset[:limit + 1])
        has_more = len(reports_list) > limit
        reports_list = reports_list[:limit]
        
        # Count total matches for user's reports
        total_matches = Match.objects.filter(
            Q(report_lost__user_id=user_id) | Q(report_found__user_id=user_id),
            status=Match.Status.PENDING
        ).count()
        
        # Build response
        reports = []
        for report in reports_list:
            # Count matches for this report
            match_count = Match.objects.filter(
                Q(report_lost_id=report.id) | Q(report_found_id=report.id),
                status=Match.Status.PENDING
            ).count()
            
            reports.append({
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
                'match_count': match_count,
                'created_at': int(report.created_at.timestamp()),
            })
        
        next_cursor = None
        if has_more and reports_list:
            next_cursor = reports_list[-1].created_at.isoformat()
        
        return GetReportsResult(
            reports=reports,
            next_cursor=next_cursor,
            total_matches=total_matches
        )

"""
Get Dashboard Stats Query - retrieves system-wide statistics.

Based on OpenAPI.yaml GET /dashboard/stats
"""
from typing import Dict, Any
from dataclasses import dataclass

from django.utils import timezone
from django.db.models import Count, Q

from .base import BaseQuery


@dataclass
class GetDashboardStatsResult:
    """Result of getting dashboard stats."""
    total_reunions: int
    total_found: int
    active_reports: int
    success_rate: float
    today_stats: Dict[str, int]


class GetDashboardStatsQuery(BaseQuery[GetDashboardStatsResult]):
    """
    دریافت آمار کلی سیستم
    
    GET /dashboard/stats
    """
    
    def execute(self) -> GetDashboardStatsResult:
        from apps.reports.models import Report
        
        today = timezone.now().date()
        today_start = timezone.make_aware(
            timezone.datetime.combine(today, timezone.datetime.min.time())
        )
        
        # Total counts
        total_reports = Report.objects.count()
        resolved_reports = Report.objects.filter(status=Report.Status.RESOLVED).count()
        active_reports = Report.objects.filter(status=Report.Status.ACTIVE).count()
        
        # Success rate
        success_rate = 0.0
        if total_reports > 0:
            success_rate = (resolved_reports / total_reports) * 100
        
        # Today's stats
        today_registered = Report.objects.filter(created_at__gte=today_start).count()
        today_resolved = Report.objects.filter(
            resolved_at__gte=today_start
        ).count()
        
        return GetDashboardStatsResult(
            total_reunions=resolved_reports,  # وصال‌های موفق = گزارش‌های حل‌شده
            total_found=resolved_reports,
            active_reports=active_reports,
            success_rate=round(success_rate, 1),
            today_stats={
                'reports_registered': today_registered,
                'people_found': today_resolved,
                'reunions': today_resolved,
            }
        )

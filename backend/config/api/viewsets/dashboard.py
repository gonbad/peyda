"""
Dashboard ViewSet - statistics endpoints.

Based on OpenAPI.yaml:
- GET /dashboard/stats
"""
from .base import BaseViewSet
from services.queries import GetDashboardStatsQuery


class DashboardViewSet(BaseViewSet):
    """آمار و داشبورد"""
    
    def list(self, request):
        """
        دریافت آمار کلی سیستم
        GET /dashboard/stats
        """
        query = self.get_query(GetDashboardStatsQuery)
        result = query.execute()
        
        return self.success({
            'total_reunions': result.total_reunions,
            'total_found': result.total_found,
            'active_reports': result.active_reports,
            'success_rate': result.success_rate,
            'today_stats': result.today_stats,
        })

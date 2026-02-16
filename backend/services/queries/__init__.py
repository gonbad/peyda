# Queries package (Read operations)
from .base import BaseQuery
from .get_reports import GetReportsQuery
from .get_report_detail import GetReportDetailQuery
from .get_matches import GetMatchesQuery
from .get_mawkab import GetMawkabQuery
from .get_user_profile import GetUserProfileQuery
from .get_dashboard_stats import GetDashboardStatsQuery

__all__ = [
    'BaseQuery',
    'GetReportsQuery',
    'GetReportDetailQuery',
    'GetMatchesQuery',
    'GetMawkabQuery',
    'GetUserProfileQuery',
    'GetDashboardStatsQuery',
]

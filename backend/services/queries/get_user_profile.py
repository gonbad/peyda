"""
Get User Profile Query - retrieves user profile with stats.
"""
from typing import Optional, Dict, Any
from dataclasses import dataclass

from .base import BaseQuery


@dataclass
class GetUserProfileResult:
    """Result of getting user profile."""
    found: bool
    profile: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class GetUserProfileQuery(BaseQuery[GetUserProfileResult]):
    """دریافت پروفایل کاربر"""
    
    def execute(
        self,
        user_id: int
    ) -> GetUserProfileResult:
        from apps.users.models import User
        from apps.reports.models import Report
        from apps.mawkab.models import Mawkab
        
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return GetUserProfileResult(found=False, error="کاربر یافت نشد")
        
        # Get report stats
        reports = Report.objects.filter(user_id=user_id)
        total_reports = reports.count()
        active_reports = reports.filter(status=Report.Status.ACTIVE).count()
        resolved_reports = reports.filter(status=Report.Status.RESOLVED).count()
        
        # Get mawkab info if exists
        mawkab_info = None
        if user.mawkab_id:
            try:
                mawkab = Mawkab.objects.get(id=user.mawkab_id)
                mawkab_info = {
                    'id': mawkab.id,
                    'name': mawkab.name,
                    'status': mawkab.status,
                    'is_approved': mawkab.is_approved,
                }
            except Mawkab.DoesNotExist:
                pass
        
        return GetUserProfileResult(
            found=True,
            profile={
                'id': user.id,
                'display_name': user.get_display_name(),
                'phone': user.phone,
                'role': user.role,
                'is_verified_mawkab_owner': user.is_verified_mawkab_owner,
                'mawkab': mawkab_info,
                'stats': {
                    'total_reports': total_reports,
                    'active_reports': active_reports,
                    'resolved_reports': resolved_reports,
                },
                'created_at': user.created_at.isoformat(),
            }
        )

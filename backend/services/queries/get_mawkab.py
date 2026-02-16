"""
Get Mawkab Query - retrieves mawkab details and stats.
"""
from typing import Optional, Dict, Any
from dataclasses import dataclass

from .base import BaseQuery


@dataclass
class GetMawkabResult:
    """Result of getting mawkab."""
    found: bool
    mawkab: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class GetMawkabQuery(BaseQuery[GetMawkabResult]):
    """دریافت اطلاعات موکب"""
    
    def execute(
        self,
        user_id: int
    ) -> GetMawkabResult:
        from apps.mawkab.models import Mawkab
        from apps.users.models import User
        
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return GetMawkabResult(found=False, error="کاربر یافت نشد")
        
        if not user.mawkab_id:
            return GetMawkabResult(found=False, error="شما موکبی ندارید")
        
        try:
            mawkab = Mawkab.objects.get(id=user.mawkab_id)
        except Mawkab.DoesNotExist:
            return GetMawkabResult(found=False, error="موکب یافت نشد")
        
        return GetMawkabResult(
            found=True,
            mawkab={
                'id': mawkab.id,
                'name': mawkab.name,
                'owner_name': mawkab.owner_name,
                'owner_phone': mawkab.owner_phone,
                'latitude': float(mawkab.latitude),
                'longitude': float(mawkab.longitude),
                'address': mawkab.address,
                'status': mawkab.status,
                'total_reports': mawkab.total_reports,
                'resolved_reports': mawkab.resolved_reports,
                'success_rate': mawkab.success_rate,
                'created_at': mawkab.created_at.isoformat(),
                'approved_at': mawkab.approved_at.isoformat() if mawkab.approved_at else None,
            }
        )

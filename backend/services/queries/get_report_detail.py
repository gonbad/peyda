"""
Get Report Detail Query - retrieves a single report with full details.
"""
from typing import Optional, Dict, Any
from dataclasses import dataclass
from uuid import UUID

from .base import BaseQuery


@dataclass
class GetReportDetailResult:
    """Result of getting report detail."""
    found: bool
    report: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class GetReportDetailQuery(BaseQuery[GetReportDetailResult]):
    """دریافت جزئیات یک گزارش"""
    
    def execute(
        self,
        report_id: UUID,
        viewer_user_id: Optional[int] = None
    ) -> GetReportDetailResult:
        from apps.reports.models import Report, Match
        
        try:
            report = Report.objects.get(id=report_id)
        except Report.DoesNotExist:
            return GetReportDetailResult(found=False, error="گزارش یافت نشد")
        
        # Check if viewer is owner or has a match with this report
        is_owner = viewer_user_id and report.user_id == viewer_user_id
        has_match = False
        
        if viewer_user_id and not is_owner:
            from django.db.models import Q
            has_match = Match.objects.filter(
                status=Match.Status.PENDING
            ).filter(
                Q(report_lost_id=report_id, report_found__user_id=viewer_user_id) |
                Q(report_found_id=report_id, report_lost__user_id=viewer_user_id)
            ).exists()
        
        # Build response
        report_data = {
            'id': str(report.id),
            'report_type': report.report_type,
            'status': report.status,
            'name': report.name,
            'age': report.age,
            'gender': report.gender,
            'description': report.description,
            'image_urls': report.image_urls,
            'latitude': float(report.latitude),
            'longitude': float(report.longitude),
            'address': report.address,
            'created_at': report.created_at.isoformat(),
            'is_owner': is_owner,
        }
        
        # Show contact phone only to owner or matched users
        if is_owner or has_match:
            report_data['contact_phone'] = report.contact_phone
        
        return GetReportDetailResult(found=True, report=report_data)

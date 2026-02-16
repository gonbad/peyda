"""
Update Report Status Command - changes report status.

Based on OpenAPI.yaml PUT /reports/{reportId}/status
Only report owner can change status (to resolved).
Admin suspension is handled via Django admin.
"""
from typing import Optional
from dataclasses import dataclass
from uuid import UUID

from django.utils import timezone

from .base import BaseCommand


@dataclass
class UpdateReportStatusResult:
    """Result of updating report status."""
    success: bool
    error: Optional[str] = None
    error_code: Optional[str] = None


class UpdateReportStatusCommand(BaseCommand[UpdateReportStatusResult]):
    """
    تغییر وضعیت گزارش
    
    PUT /reports/{reportId}/status
    فقط ثبت‌کننده گزارش می‌تواند وضعیت را به resolved تغییر دهد.
    """
    
    def execute(
        self,
        report_id: UUID,
        user_id: int,
        new_status: str,  # 'resolved' only for users
        reason: str = ''
    ) -> UpdateReportStatusResult:
        from apps.reports.models import Report
        
        try:
            report = Report.objects.get(id=report_id)
        except Report.DoesNotExist:
            return UpdateReportStatusResult(
                success=False, 
                error="گزارش یافت نشد",
                error_code="REPORT_NOT_FOUND"
            )
        
        # Only report owner can change status
        if report.user_id != user_id:
            return UpdateReportStatusResult(
                success=False, 
                error="فقط ثبت‌کننده گزارش می‌تواند وضعیت آن را تغییر دهد",
                error_code="STATUS_CHANGE_DENIED"
            )
        
        # Users can only set status to 'resolved'
        if new_status != 'resolved':
            return UpdateReportStatusResult(
                success=False,
                error="وضعیت جدید گزارش معتبر نیست",
                error_code="INVALID_STATUS"
            )
        
        if report.status == Report.Status.RESOLVED:
            return UpdateReportStatusResult(
                success=False, 
                error="این گزارش قبلاً حل شده است",
                error_code="ALREADY_RESOLVED"
            )
        
        if report.status == Report.Status.SUSPENDED:
            return UpdateReportStatusResult(
                success=False,
                error="گزارش معلق‌شده قابل تغییر نیست",
                error_code="REPORT_SUSPENDED"
            )
        
        # Update status
        report.status = Report.Status.RESOLVED
        report.resolved_at = timezone.now()
        report.save(update_fields=['status', 'resolved_at', 'updated_at'])
        
        # Update mawkab stats if applicable
        if report.mawkab_id:
            from apps.mawkab.models import Mawkab
            from django.db.models import F
            Mawkab.objects.filter(id=report.mawkab_id).update(
                resolved_reports=F('resolved_reports') + 1
            )
        
        self.publish_event('report.resolved', {
            'report_id': str(report_id),
            'report_type': report.report_type,
            'user_id': user_id,
            'reason': reason
        })
        
        self.log_info(
            "Report resolved",
            report_id=str(report_id),
            user_id=user_id
        )
        
        return UpdateReportStatusResult(success=True)

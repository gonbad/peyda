"""
Match Action Command - handles actions on matches.

Based on OpenAPI.yaml POST /matches/{matchId}
Currently only 'rejected' action is supported.
"""
from typing import Optional
from dataclasses import dataclass
from uuid import UUID

from django.utils import timezone

from .base import BaseCommand


@dataclass
class MatchActionResult:
    """Result of match action."""
    success: bool
    error: Optional[str] = None
    error_code: Optional[str] = None


class MatchActionCommand(BaseCommand[MatchActionResult]):
    """
    اقدام در مورد تطبیق
    
    POST /matches/{matchId}
    فقط ثبت‌کننده گزارش گمشده می‌تواند مچ را رد کند.
    """
    
    def execute(
        self,
        match_id: UUID,
        user_id: int,
        action: str,  # 'rejected' per OpenAPI
        notes: str = ''
    ) -> MatchActionResult:
        from apps.reports.models import Match
        
        # Validate action
        if action != 'rejected':
            return MatchActionResult(
                success=False,
                error="نوع اقدام وارد شده معتبر نیست",
                error_code="INVALID_ACTION"
            )
        
        try:
            match = Match.objects.select_related('report_lost', 'report_found').get(id=match_id)
        except Match.DoesNotExist:
            return MatchActionResult(
                success=False, 
                error="تطبیق مورد نظر یافت نشد",
                error_code="MATCH_NOT_FOUND"
            )
        
        # Check access - user must be owner of one of the reports
        is_lost_owner = match.report_lost.user_id == user_id
        is_found_owner = match.report_found.user_id == user_id
        
        if not is_lost_owner and not is_found_owner:
            return MatchActionResult(
                success=False, 
                error="فقط ثبت‌کنندگان گزارش‌های مرتبط می‌توانند در مورد تطبیق اقدام کنند",
                error_code="ACTION_ACCESS_DENIED"
            )
        
        # Only lost report owner can reject
        if action == 'rejected' and not is_lost_owner:
            return MatchActionResult(
                success=False, 
                error="فقط ثبت‌کننده گزارش گمشده می‌تواند مچ را رد کند",
                error_code="ACTION_ACCESS_DENIED"
            )
        
        if match.status == Match.Status.REJECTED:
            return MatchActionResult(
                success=False, 
                error="این مچ قبلاً رد شده است",
                error_code="ALREADY_REJECTED"
            )
        
        # Perform rejection
        match.status = Match.Status.REJECTED
        match.rejected_at = timezone.now()
        match.rejected_by_user_id = user_id
        match.save(update_fields=['status', 'rejected_at', 'rejected_by_user_id'])
        
        self.publish_event('match.rejected', {
            'match_id': str(match_id),
            'report_lost_id': str(match.report_lost_id),
            'report_found_id': str(match.report_found_id),
            'rejected_by_user_id': user_id,
            'notes': notes
        })
        
        self.log_info(
            "Match rejected",
            match_id=str(match_id),
            user_id=user_id
        )
        
        return MatchActionResult(success=True)

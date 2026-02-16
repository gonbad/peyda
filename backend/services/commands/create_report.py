"""
Create Report Command - creates a new lost/found report and triggers matching.

Based on OpenAPI.yaml POST /reports
"""
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from uuid import UUID

from django.conf import settings
from django.utils import timezone

from .base import BaseCommand


def _generate_tracking_code() -> str:
    """Generate tracking code like PYD-2024-12345"""
    import random
    year = timezone.now().year
    number = random.randint(10000, 99999)
    return f"PYD-{year}-{number}"


@dataclass
class CreateReportResult:
    """Result of creating a report."""
    success: bool
    report_id: Optional[UUID] = None
    tracking_code: Optional[str] = None
    initial_matches: Optional[List[Dict[str, Any]]] = None
    error: Optional[str] = None
    error_code: Optional[str] = None


class CreateReportCommand(BaseCommand[CreateReportResult]):
    """
    ایجاد گزارش گمشده/پیداشده جدید
    
    POST /reports
    """
    
    def execute(
        self,
        user_id: int,
        report_type: str,  # 'lost' or 'found'
        gender: str,  # required per OpenAPI
        latitude: float,
        longitude: float,
        contact_phone: str,
        person_name: Optional[str] = None,
        age: Optional[int] = None,
        description: str = '',
        address: str = '',
        media_ids: Optional[List[str]] = None,
    ) -> CreateReportResult:
        from apps.reports.models import Report
        from apps.users.models import User
        
        # Get user
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return CreateReportResult(
                success=False, 
                error="کاربر یافت نشد",
                error_code="USER_NOT_FOUND"
            )
        
        # Check daily report limit for non-mawkab users
        if not user.is_verified_mawkab_owner:
            today = timezone.now().date()
            if user.daily_report_date != today:
                user.daily_report_count = 0
                user.daily_report_date = today
            
            daily_limit = getattr(settings, 'DAILY_REPORT_LIMIT', 3)
            if user.daily_report_count >= daily_limit:
                return CreateReportResult(
                    success=False, 
                    error=f"شما امروز حداکثر {daily_limit} گزارش می‌توانید ثبت کنید",
                    error_code="DAILY_LIMIT_REACHED"
                )
            
            user.daily_report_count += 1
            user.save(update_fields=['daily_report_count', 'daily_report_date'])
        
        # Convert media_ids to image_urls (media service handles this)
        image_urls = []
        if media_ids:
            max_images = getattr(settings, 'MAX_IMAGES_PER_REPORT', 5)
            if len(media_ids) > max_images:
                return CreateReportResult(
                    success=False,
                    error=f"حداکثر {max_images} تصویر مجاز است",
                    error_code="TOO_MANY_IMAGES"
                )
            # TODO: Convert media_ids to actual URLs via media service
            image_urls = media_ids  # Placeholder
        
        # Generate tracking code
        tracking_code = _generate_tracking_code()
        
        # Create report
        report = Report.objects.create(
            report_type=report_type,
            name=person_name or '',
            age=age,
            gender=gender,
            description=description,
            image_urls=image_urls,
            latitude=latitude,
            longitude=longitude,
            address=address,
            contact_phone=contact_phone,
            user_id=user_id,
            mawkab_id=user.mawkab_id if user.is_verified_mawkab_owner else None
        )
        
        # Update mawkab stats if applicable
        if user.is_verified_mawkab_owner and user.mawkab_id:
            from apps.mawkab.models import Mawkab
            from django.db.models import F
            Mawkab.objects.filter(id=user.mawkab_id).update(
                total_reports=F('total_reports') + 1
            )
        
        # Trigger matching and get initial matches
        initial_matches = self._find_initial_matches(report)
        
        # Publish event for async processing
        self.publish_event('report.created', {
            'report_id': str(report.id),
            'report_type': report_type,
            'user_id': user_id,
        })
        
        self.log_info(
            "Report created",
            report_id=str(report.id),
            tracking_code=tracking_code,
            report_type=report_type,
            user_id=user_id
        )
        
        return CreateReportResult(
            success=True,
            report_id=report.id,
            tracking_code=tracking_code,
            initial_matches=initial_matches
        )
    
    def _find_initial_matches(self, report) -> List[Dict[str, Any]]:
        """Find and create initial matches for the report."""
        from services.matching import MatchingService
        
        try:
            matching_service = MatchingService(event_bus=self._event_bus)
            candidates = matching_service.find_matches_for_report(str(report.id))
            
            return [
                {
                    'id': c.report_id,
                    'similarity_score': c.similarity_score,
                    'status': 'pending',
                }
                for c in candidates
            ]
        except Exception as e:
            self.log_warning(f"Failed to find initial matches: {e}")
            return []

"""
Save Notification Result Command - stores notification delivery result from n8n.
"""
from typing import Optional, Dict, Any
from uuid import UUID
from dataclasses import dataclass

from utils.datetime import from_unix
from .base import BaseCommand


@dataclass
class SaveNotificationResultResult:
    """Result of saving notification."""
    notification_id: UUID
    saved: bool
    created: bool


class SaveNotificationResultCommand(BaseCommand[SaveNotificationResultResult]):
    """ذخیره نتیجه ارسال نوتیفیکیشن از n8n"""
    
    def execute(
        self,
        notification_id: UUID,
        user_id: int,
        channel: str,
        template: str,
        status: str,
        platform_message_id: Optional[str] = None,
        error_message: Optional[str] = None,
        sent_at: int = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> SaveNotificationResultResult:
        from apps.notifications.models import Notification
        
        notification, created = Notification.objects.update_or_create(
            id=notification_id,
            defaults={
                'user_id': user_id,
                'channel': channel,
                'template': template,
                'status': status,
                'platform_message_id': platform_message_id,
                'error_message': error_message,
                'sent_at': from_unix(sent_at) if sent_at else None,
                'metadata': metadata or {}
            }
        )
        
        self.log_info(
            f"Notification {status}",
            notification_id=str(notification_id),
            user_id=user_id,
            channel=channel,
            template=template,
            status=status
        )
        
        return SaveNotificationResultResult(
            notification_id=notification_id,
            saved=True,
            created=created
        )

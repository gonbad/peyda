"""
Create Mawkab Command - registers a new mawkab (pending approval).
"""
from typing import Optional
from dataclasses import dataclass

from .base import BaseCommand


@dataclass
class CreateMawkabResult:
    """Result of creating a mawkab."""
    success: bool
    mawkab_id: Optional[int] = None
    error: Optional[str] = None


class CreateMawkabCommand(BaseCommand[CreateMawkabResult]):
    """ثبت موکب جدید (در انتظار تایید)"""
    
    def execute(
        self,
        user_id: int,
        name: str,
        owner_name: str,
        owner_phone: str,
        latitude: float,
        longitude: float,
        address: str = ''
    ) -> CreateMawkabResult:
        from apps.mawkab.models import Mawkab
        from apps.users.models import User
        
        # Check if user already has a mawkab
        if Mawkab.objects.filter(owner_user_id=user_id).exists():
            return CreateMawkabResult(
                success=False, 
                error="شما قبلاً یک موکب ثبت کرده‌اید"
            )
        
        # Create mawkab
        mawkab = Mawkab.objects.create(
            name=name,
            owner_name=owner_name,
            owner_phone=owner_phone,
            owner_user_id=user_id,
            latitude=latitude,
            longitude=longitude,
            address=address
        )
        
        # Update user's mawkab_id (but not role yet - pending approval)
        User.objects.filter(id=user_id).update(mawkab_id=mawkab.id)
        
        self.publish_event('mawkab.created', {
            'mawkab_id': mawkab.id,
            'user_id': user_id,
            'name': name,
            'owner_name': owner_name
        })
        
        self.log_info(
            "Mawkab created",
            mawkab_id=mawkab.id,
            user_id=user_id
        )
        
        return CreateMawkabResult(success=True, mawkab_id=mawkab.id)

"""
Matching Service - finds potential matches between lost and found reports.

Based on the match algorithm proposal:
- Metadata scoring: gender (40%), age (35%), location (25%)
- Threshold: 40 for display, 60 for notification
"""
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from math import radians, sin, cos, sqrt, atan2

from django.conf import settings
from django.db.models import Q

logger = logging.getLogger(__name__)


@dataclass
class MatchCandidate:
    """A potential match candidate."""
    report_id: str
    user_id: int
    similarity_score: int


class MatchingService:
    """سرویس مچینگ گزارش‌ها"""
    
    def __init__(self, event_bus=None):
        self._event_bus = event_bus
        self._display_threshold = getattr(settings, 'MATCH_DISPLAY_THRESHOLD', 40)
        self._notify_threshold = getattr(settings, 'MATCH_NOTIFY_THRESHOLD', 60)
        self._max_matches = getattr(settings, 'MAX_MATCHES_PER_REPORT', 20)
    
    def find_matches_for_report(self, report_id: str) -> List[MatchCandidate]:
        """
        Find matches for a newly created report.
        
        Args:
            report_id: UUID of the new report
            
        Returns:
            List of match candidates above threshold
        """
        from apps.reports.models import Report, Match
        
        try:
            new_report = Report.objects.get(id=report_id)
        except Report.DoesNotExist:
            logger.error(f"Report not found: {report_id}")
            return []
        
        if new_report.status != Report.Status.ACTIVE:
            return []
        
        # Find opposite type reports
        opposite_type = 'found' if new_report.report_type == 'lost' else 'lost'
        
        candidates = Report.objects.filter(
            report_type=opposite_type,
            status=Report.Status.ACTIVE
        )
        
        # Pre-filter by gender if specified
        if new_report.gender:
            candidates = candidates.filter(
                Q(gender=new_report.gender) | Q(gender__isnull=True)
            )
        
        matches = []
        for candidate in candidates[:1000]:  # Limit candidates
            # Skip if match already exists
            existing = Match.objects.filter(
                Q(report_lost=new_report, report_found=candidate) |
                Q(report_lost=candidate, report_found=new_report)
            ).exists()
            
            if existing:
                continue
            
            score = self._calculate_similarity(new_report, candidate)
            
            if score >= self._display_threshold:
                matches.append(MatchCandidate(
                    report_id=str(candidate.id),
                    user_id=candidate.user_id,
                    similarity_score=score
                ))
        
        # Sort by score and limit
        matches.sort(key=lambda x: x.similarity_score, reverse=True)
        matches = matches[:self._max_matches]
        
        # Create match records
        self._create_matches(new_report, matches)
        
        return matches
    
    def _calculate_similarity(self, report1, report2) -> int:
        """
        Calculate similarity score between two reports.
        
        Returns:
            Score from 0 to 100
        """
        gender_score = self._calculate_gender_score(report1.gender, report2.gender)
        age_score = self._calculate_age_score(report1.age, report2.age)
        location_score = self._calculate_location_score(
            float(report1.latitude), float(report1.longitude),
            float(report2.latitude), float(report2.longitude)
        )
        
        # Weighted average: gender 40%, age 35%, location 25%
        total_score = (
            gender_score * 0.40 +
            age_score * 0.35 +
            location_score * 0.25
        )
        
        return int(total_score)
    
    def _calculate_gender_score(self, gender1: Optional[str], gender2: Optional[str]) -> int:
        """Calculate gender similarity score."""
        if gender1 is None or gender2 is None:
            return 50  # Unknown
        if gender1 == gender2:
            return 100
        return 0
    
    def _calculate_age_score(self, age1: Optional[int], age2: Optional[int]) -> int:
        """Calculate age similarity score."""
        if age1 is None or age2 is None:
            return 50  # Unknown
        
        diff = abs(age1 - age2)
        
        if diff == 0:
            return 100
        elif diff <= 2:
            return 90
        elif diff <= 5:
            return 70
        elif diff <= 10:
            return 40
        else:
            return 10
    
    def _calculate_location_score(
        self, 
        lat1: float, lng1: float, 
        lat2: float, lng2: float
    ) -> int:
        """Calculate location similarity score using Haversine distance."""
        distance_km = self._haversine_distance(lat1, lng1, lat2, lng2)
        
        if distance_km <= 0.5:
            return 100
        elif distance_km <= 1:
            return 90
        elif distance_km <= 2:
            return 70
        elif distance_km <= 5:
            return 50
        elif distance_km <= 10:
            return 30
        else:
            return 10
    
    def _haversine_distance(
        self, 
        lat1: float, lng1: float, 
        lat2: float, lng2: float
    ) -> float:
        """Calculate distance between two points in km."""
        R = 6371  # Earth's radius in km
        
        lat1, lng1, lat2, lng2 = map(radians, [lat1, lng1, lat2, lng2])
        
        dlat = lat2 - lat1
        dlng = lng2 - lng1
        
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlng/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        
        return R * c
    
    def _create_matches(self, new_report, candidates: List[MatchCandidate]) -> None:
        """Create match records and send notifications."""
        from apps.reports.models import Match
        
        for candidate in candidates:
            # Determine which is lost and which is found
            if new_report.report_type == 'lost':
                report_lost = new_report
                report_found_id = candidate.report_id
            else:
                report_lost_id = candidate.report_id
                report_found = new_report
            
            from apps.reports.models import Report
            
            if new_report.report_type == 'lost':
                report_found = Report.objects.get(id=candidate.report_id)
                match = Match.objects.create(
                    report_lost=new_report,
                    report_found=report_found,
                    similarity_score=candidate.similarity_score,
                    notified_report_id=report_found.id  # Notify older report
                )
            else:
                report_lost = Report.objects.get(id=candidate.report_id)
                match = Match.objects.create(
                    report_lost=report_lost,
                    report_found=new_report,
                    similarity_score=candidate.similarity_score,
                    notified_report_id=report_lost.id  # Notify older report
                )
            
            # Send notification if above threshold
            if candidate.similarity_score >= self._notify_threshold:
                if self._event_bus:
                    self._event_bus.publish('match.found', {
                        'match_id': str(match.id),
                        'report_lost_id': str(match.report_lost_id),
                        'report_found_id': str(match.report_found_id),
                        'notified_user_id': candidate.user_id,
                        'similarity_score': candidate.similarity_score
                    })
            
            logger.info(
                f"Match created: {match.id} (score: {candidate.similarity_score})"
            )

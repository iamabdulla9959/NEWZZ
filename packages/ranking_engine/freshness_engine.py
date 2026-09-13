"""
Freshness Engine.
Calculates time-decay freshness score (0..100) using event/publication timestamps.
Prefers event_time -> published_at -> scraped_at.
Applies configurable piecewise decay curves so recent news is rewarded without
overriding high-impact breaking events.
"""

from datetime import datetime, timezone
from typing import Optional
from .config import RankingConfig


class FreshnessEngine:
    @staticmethod
    def calculate_freshness(
        event_time: Optional[datetime] = None,
        published_at: Optional[datetime] = None,
        scraped_at: Optional[datetime] = None,
        current_time: Optional[datetime] = None,
    ) -> float:
        """
        Computes the freshness score (0..100).
        Evaluates age in minutes using the best available timestamp in order of precedence.
        """
        ref_time = event_time or published_at or scraped_at
        now = current_time or datetime.now(timezone.utc)

        if not ref_time:
            # Default conservative score when no timestamp is known
            return 25.0

        # Ensure timezone awareness
        if ref_time.tzinfo is None:
            ref_time = ref_time.replace(tzinfo=timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        # Handle future timestamps safely (clamped to 100.0)
        diff_seconds = (now - ref_time).total_seconds()
        if diff_seconds < 0:
            return 100.0

        age_minutes = diff_seconds / 60.0

        # Evaluate against configured decay brackets
        for max_age_min, score in RankingConfig.FRESHNESS_BRACKETS:
            if age_minutes <= max_age_min:
                return float(score)

        return 5.0

"""
Personal Relevance Engine.
Calculates user-specific relevance (0..100) combining geographic proximity and category interests.
Ensures local news is prioritized for local users without letting location completely
blind users to catastrophic national/international events.
"""

from typing import List, Optional
from .config import RankingConfig


class RelevanceEngine:
    @staticmethod
    def calculate_relevance(
        story_category: str,
        story_state: Optional[str] = None,
        story_district: Optional[str] = None,
        user_state: Optional[str] = None,
        user_district: Optional[str] = None,
        user_category_order: Optional[List[str]] = None,
    ) -> float:
        """
        Computes the personal relevance score (0..100) combining:
        1. Location Component (0..50)
        2. Interest Component (0..50)
        """
        # ---------------------------------------------------------------------
        # 1. Location Component (0..50)
        # ---------------------------------------------------------------------
        clean_story_dist = (story_district or "").strip().lower()
        clean_user_dist = (user_district or "").strip().lower()
        clean_story_state = (story_state or "").strip().lower()
        clean_user_state = (user_state or "").strip().lower()
        clean_cat = (story_category or "").strip().lower()

        if clean_user_dist and clean_story_dist and clean_user_dist == clean_story_dist:
            loc_score = RankingConfig.LOCATION_DISTRICT_SCORE
        elif clean_user_state and clean_story_state and clean_user_state == clean_story_state:
            loc_score = RankingConfig.LOCATION_STATE_SCORE
        elif (clean_user_dist and clean_story_dist and clean_user_dist != clean_story_dist) or (clean_user_state and clean_story_state and clean_user_state != clean_story_state):
            loc_score = RankingConfig.LOCATION_GLOBAL_SCORE
        elif clean_cat in ("international", "world", "global"):
            loc_score = RankingConfig.LOCATION_GLOBAL_SCORE
        else:
            # Baseline neutral location score for national/general interest when no mismatch
            loc_score = RankingConfig.LOCATION_NATIONAL_SCORE

        # ---------------------------------------------------------------------
        # 2. Interest Component (0..50)
        # ---------------------------------------------------------------------
        interest_score = RankingConfig.INTEREST_UNRANKED_DEFAULT

        if user_category_order and clean_cat:
            clean_order = [c.strip().lower() for c in user_category_order if c.strip()]
            if clean_cat in clean_order:
                rank_idx = clean_order.index(clean_cat)
                decayed = RankingConfig.INTEREST_TOP_RANK_SCORE - (rank_idx * RankingConfig.INTEREST_STEP_PENALTY)
                interest_score = max(RankingConfig.INTEREST_MINIMUM_SCORE, decayed)

        total_relevance = loc_score + interest_score
        return round(max(0.0, min(100.0, total_relevance)), 2)

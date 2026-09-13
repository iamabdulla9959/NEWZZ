"""
Centralized Configuration for News Reels Scoring and Ranking.
All weights, dimension boundaries, and time-decay brackets are maintained here.
No magic numbers scattered across code files.
"""

from typing import List, Set, Tuple


class RankingConfig:
    # -------------------------------------------------------------------------
    # Final Feed Score Component Weights (Sum = 1.00)
    # -------------------------------------------------------------------------
    WEIGHT_OBJECTIVE_IMPORTANCE: float = 0.40
    WEIGHT_URGENCY: float = 0.20
    WEIGHT_FRESHNESS: float = 0.15
    WEIGHT_PERSONAL_RELEVANCE: float = 0.15
    WEIGHT_VERIFICATION: float = 0.10

    # -------------------------------------------------------------------------
    # Objective Importance Dimension Max Limits (Sum = 100.0)
    # -------------------------------------------------------------------------
    MAX_HUMAN_IMPACT: float = 20.0
    MAX_SAFETY_IMPACT: float = 20.0
    MAX_GEOGRAPHIC_IMPACT: float = 15.0
    MAX_ECONOMIC_IMPACT: float = 10.0
    MAX_POLICY_IMPACT: float = 10.0
    MAX_INFRASTRUCTURE_IMPACT: float = 10.0
    MAX_SECURITY_IMPACT: float = 10.0
    MAX_CONSEQUENCE_IMPACT: float = 5.0

    TOTAL_OBJECTIVE_MAX: float = 100.0

    # -------------------------------------------------------------------------
    # Emergency Floor Constants
    # -------------------------------------------------------------------------
    EMERGENCY_URGENCY_THRESHOLD: float = 90.0
    EMERGENCY_IMPORTANCE_FLOOR: float = 75.0

    # -------------------------------------------------------------------------
    # Freshness Decay Brackets (Age in minutes -> Freshness score 0..100)
    # -------------------------------------------------------------------------
    FRESHNESS_BRACKETS: List[Tuple[float, float]] = [
        (15.0, 100.0),    # 0 to 15 min
        (30.0, 95.0),     # 15 to 30 min
        (60.0, 90.0),     # 30 to 60 min
        (120.0, 80.0),    # 1 to 2 hours
        (240.0, 70.0),    # 2 to 4 hours
        (480.0, 55.0),    # 4 to 8 hours
        (720.0, 40.0),    # 8 to 12 hours
        (1440.0, 25.0),   # 12 to 24 hours
        (2880.0, 10.0),   # 24 to 48 hours
        (float("inf"), 5.0), # 48+ hours
    ]

    # -------------------------------------------------------------------------
    # Location Relevance Weights (0..50)
    # -------------------------------------------------------------------------
    LOCATION_DISTRICT_SCORE: float = 50.0
    LOCATION_STATE_SCORE: float = 40.0
    LOCATION_NATIONAL_SCORE: float = 25.0
    LOCATION_GLOBAL_SCORE: float = 15.0

    # -------------------------------------------------------------------------
    # Interest Relevance Weights (0..50)
    # -------------------------------------------------------------------------
    INTEREST_TOP_RANK_SCORE: float = 50.0
    INTEREST_STEP_PENALTY: float = 5.0
    INTEREST_MINIMUM_SCORE: float = 20.0
    INTEREST_UNRANKED_DEFAULT: float = 25.0

    # -------------------------------------------------------------------------
    # Source Credibility Tiers
    # -------------------------------------------------------------------------
    TIER_1_SOURCES: Set[str] = {
        "bbc news", "bbc", "the new york times", "reuters", "associated press",
        "ap news", "the hindu", "the times of india", "the indian express",
        "ndtv", "bloomberg", "press trust of india", "pti", "newsonair.gov.in",
        "wion news", "wion"
    }

    TIER_2_SOURCES: Set[str] = {
        "hindustan times", "india today", "the print", "the quint", "telegraph india",
        "deccan herald", "financial express", "economic times", "livemint",
        "business standard", "tribune india", "telangana today", "sakshi"
    }

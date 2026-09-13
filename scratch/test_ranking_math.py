import sys
sys.path.insert(0, r"d:\News")
import json
from packages.ranking_engine.relevance_engine import RelevanceEngine
from packages.ranking_engine.config import RankingConfig
from packages.ranking_engine.feed_ranking_engine import FeedRankingEngine
from packages.ranking_engine.importance_engine import ImportanceEngine
from packages.ranking_engine.urgency_engine import UrgencyEngine
from packages.ranking_engine.freshness_engine import FreshnessEngine
from packages.ranking_engine.verification_engine import VerificationEngine

def test_ranking_details():
    results = {}

    # TEST 8: PERSONAL RELEVANCE FORMULA
    # Relevance = Location Component (0..50) + Interest Component (0..50)
    # Interest Component:
    # Rank 1 (index 0) = 50 - 0 = 50.0
    # Rank 2 (index 1) = 50 - 5 = 45.0
    # Rank 3 (index 2) = 50 - 10 = 40.0
    # Rank 4 (index 3) = 50 - 15 = 35.0
    # Rank 5 (index 4) = 50 - 20 = 30.0
    # Rank 6 (index 5) = 50 - 25 = 25.0
    # Rank 7 (index 6) = 50 - 30 = 20.0 (min floor = 20)
    # Unranked = 25.0
    category_order = ["technology", "business", "politics", "national"]
    
    # Check relevance for each ranked category assuming neutral location (national score = 25.0)
    rel_rank1 = RelevanceEngine.calculate_relevance(
        story_category="technology", user_category_order=category_order
    )
    rel_rank2 = RelevanceEngine.calculate_relevance(
        story_category="business", user_category_order=category_order
    )
    rel_rank3 = RelevanceEngine.calculate_relevance(
        story_category="politics", user_category_order=category_order
    )
    rel_rank4 = RelevanceEngine.calculate_relevance(
        story_category="national", user_category_order=category_order
    )
    rel_unranked = RelevanceEngine.calculate_relevance(
        story_category="entertainment", user_category_order=category_order
    )
    rel_empty = RelevanceEngine.calculate_relevance(
        story_category="technology", user_category_order=[]
    )

    results["test8"] = {
        "formula": "Relevance = Location Component (0..50) + Interest Component (0..50)",
        "interest_component": {
            "rank_1": rel_rank1 - 25.0,
            "rank_2": rel_rank2 - 25.0,
            "rank_3": rel_rank3 - 25.0,
            "rank_4": rel_rank4 - 25.0,
            "unranked": rel_unranked - 25.0,
            "empty": rel_empty - 25.0
        },
        "total_relevance_with_neutral_location_25": {
            "rank_1": rel_rank1,
            "rank_2": rel_rank2,
            "rank_3": rel_rank3,
            "rank_4": rel_rank4,
            "unranked": rel_unranked,
            "empty": rel_empty
        }
    }

    # TEST 9: OBJECTIVE RANKING SEPARATION
    # Check if changing priority order changes Importance, Urgency, Freshness, Verification
    # Fixed story properties:
    imp = 75.0
    urg = 50.0
    frsh = 90.0
    ver = 85.0
    
    # Case A: technology rank 1 (interest = 50 -> rel = 75)
    rel_a = RelevanceEngine.calculate_relevance(
        story_category="technology", user_category_order=["technology", "politics"]
    )
    score_out_a = FeedRankingEngine.compute_final_score(
        objective_importance=imp, urgency=urg, freshness=frsh,
        personal_relevance=rel_a, verification_confidence=ver
    )

    # Case B: technology unranked / rank 2 (interest = 45 -> rel = 70)
    rel_b = RelevanceEngine.calculate_relevance(
        story_category="technology", user_category_order=["politics", "technology"]
    )
    score_out_b = FeedRankingEngine.compute_final_score(
        objective_importance=imp, urgency=urg, freshness=frsh,
        personal_relevance=rel_b, verification_confidence=ver
    )

    results["test9"] = {
        "order_a": {
            "relevance": rel_a,
            "importance": score_out_a.objective_importance,
            "urgency": score_out_a.urgency,
            "freshness": score_out_a.freshness,
            "verification": score_out_a.verification_confidence,
            "final_score": score_out_a.final_feed_score
        },
        "order_b": {
            "relevance": rel_b,
            "importance": score_out_b.objective_importance,
            "urgency": score_out_b.urgency,
            "freshness": score_out_b.freshness,
            "verification": score_out_b.verification_confidence,
            "final_score": score_out_b.final_feed_score
        },
        "importance_affected": score_out_a.objective_importance != score_out_b.objective_importance,
        "urgency_affected": score_out_a.urgency != score_out_b.urgency,
        "freshness_affected": score_out_a.freshness != score_out_b.freshness,
        "verification_affected": score_out_a.verification_confidence != score_out_b.verification_confidence,
        "relevance_affected": score_out_a.personal_relevance != score_out_b.personal_relevance,
        "final_score_affected": score_out_a.final_feed_score != score_out_b.final_feed_score
    }

    # TEST 10: ORDER SENSITIVITY
    order_a = ["technology", "business", "politics", "national"]
    order_b = ["politics", "technology", "business", "national"]
    
    tech_rel_a = RelevanceEngine.calculate_relevance("technology", user_category_order=order_a)
    tech_rel_b = RelevanceEngine.calculate_relevance("technology", user_category_order=order_b)

    pol_rel_a = RelevanceEngine.calculate_relevance("politics", user_category_order=order_a)
    pol_rel_b = RelevanceEngine.calculate_relevance("politics", user_category_order=order_b)

    results["test10"] = {
        "order_a": order_a,
        "order_b": order_b,
        "tech_story": {"order_a": tech_rel_a, "order_b": tech_rel_b, "diff": tech_rel_b - tech_rel_a},
        "politics_story": {"order_a": pol_rel_a, "order_b": pol_rel_b, "diff": pol_rel_b - pol_rel_a}
    }

    # TEST 11: EMPTY PRIORITY
    rel_empty_list = RelevanceEngine.calculate_relevance("technology", user_category_order=[])
    rel_none = RelevanceEngine.calculate_relevance("technology", user_category_order=None)
    results["test11"] = {
        "empty_list_relevance": rel_empty_list,
        "none_relevance": rel_none,
        "gracefully_handled": rel_empty_list == 50.0 and rel_none == 50.0 # (25 loc + 25 unranked default)
    }

    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    test_ranking_details()

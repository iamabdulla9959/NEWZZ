"""
Controlled Ranking Discrimination Test Suite.
Validates the principle: ordinary casualty keywords != automatic top priority.
Tests:
  A: Single isolated road accident (NOT automatically #1)
  B: Major ongoing flood/disaster (Urgency >= 90, Emergency Floor applies, top rank)
  C: Major national policy announcement (outranks isolated accident)
  D: Major economic/business development (outranks routine casualty reporting)
  E: Major cybersecurity incident (outranks minor accident)
  F: Old death/accident story (freshness decay prevents high ranking)
"""

import sys
import os
from datetime import datetime, timedelta, timezone

sys.path.insert(0, r"d:\News")
sys.path.insert(0, r"d:\News\apps\api")

from packages.ranking_engine.importance_engine import ImportanceEngine
from packages.ranking_engine.urgency_engine import UrgencyEngine
from packages.ranking_engine.freshness_engine import FreshnessEngine
from packages.ranking_engine.verification_engine import VerificationEngine
from packages.ranking_engine.relevance_engine import RelevanceEngine
from packages.ranking_engine.feed_ranking_engine import FeedRankingEngine
from packages.ranking_engine.config import RankingConfig


def run_discrimination_tests():
    now = datetime.now(timezone.utc)
    print("=" * 65)
    print("STARTING CONTROLLED RANKING DISCRIMINATION TESTS (A - F)")
    print("=" * 65)

    # -------------------------------------------------------------------------
    # TEST A: Single isolated road accident / single casualty
    # -------------------------------------------------------------------------
    title_a = "One killed, two injured in car-truck collision on highway"
    summary_a = "A fatal road accident occurred when a car collided with a truck on the state highway. Police have registered a case and initiated an investigation."
    dims_a, imp_a = ImportanceEngine.analyze_event_text(title_a, summary_a, "national")
    urg_a, reason_a = UrgencyEngine.calculate_urgency(title_a, summary_a)
    frsh_a = FreshnessEngine.calculate_freshness(published_at=now - timedelta(minutes=15), current_time=now)
    ver_a, _ = VerificationEngine.calculate_verification([{"name": "Local Press Wire"}])
    rel_a = RelevanceEngine.calculate_relevance("national")
    card_a = FeedRankingEngine.compute_final_score(imp_a, urg_a, frsh_a, rel_a, ver_a, dimensions=dims_a)

    print(f"\n[TEST A] Single isolated road accident:")
    print(f"  Headline: '{title_a}'")
    print(f"  Importance: {imp_a:.1f} (Human: {dims_a.human_impact.score:.1f}, Safety: {dims_a.safety_impact.score:.1f}, Geo: {dims_a.geographic_impact.score:.1f})")
    print(f"  Urgency: {urg_a:.1f} ({reason_a})")
    print(f"  Freshness: {frsh_a:.1f} | Final Feed Score: {card_a.final_feed_score:.2f}")
    assert urg_a < RankingConfig.EMERGENCY_URGENCY_THRESHOLD, f"Isolated accident should NOT hit emergency threshold 90, got {urg_a}"
    assert imp_a < 20.0, f"Isolated accident importance should be modest (< 20), got {imp_a}"

    # -------------------------------------------------------------------------
    # TEST B: Major ongoing flood / disaster (Nepal/Bihar type)
    # -------------------------------------------------------------------------
    title_b = "Severe Bihar flood: 50,000 evacuated as major rivers breach danger mark"
    summary_b = "Widespread flash flood and massive flooding forces red alert and state of emergency. Tens of thousands displaced, immediate danger and mandatory evacuation order in effect."
    dims_b, imp_b = ImportanceEngine.analyze_event_text(title_b, summary_b, "national")
    urg_b, reason_b = UrgencyEngine.calculate_urgency(title_b, summary_b)
    frsh_b = FreshnessEngine.calculate_freshness(published_at=now - timedelta(minutes=30), current_time=now)
    ver_b, _ = VerificationEngine.calculate_verification([{"name": "Press Trust of India"}, {"name": "The Hindu"}])
    rel_b = RelevanceEngine.calculate_relevance("national")
    card_b = FeedRankingEngine.compute_final_score(imp_b, urg_b, frsh_b, rel_b, ver_b, dimensions=dims_b, source_count=2, tier1_count=2)

    print(f"\n[TEST B] Major ongoing flood disaster:")
    print(f"  Headline: '{title_b}'")
    print(f"  Raw Importance: {imp_b:.1f}")
    print(f"  Urgency: {urg_b:.1f} ({reason_b})")
    print(f"  Effective Importance after Emergency Floor: {card_b.objective_importance:.1f}")
    print(f"  Final Feed Score: {card_b.final_feed_score:.2f}")
    assert urg_b >= RankingConfig.EMERGENCY_URGENCY_THRESHOLD, f"Major disaster MUST have Urgency >= 90, got {urg_b}"
    assert card_b.objective_importance >= RankingConfig.EMERGENCY_IMPORTANCE_FLOOR, f"Emergency floor (>=75) must apply, got {card_b.objective_importance}"
    assert card_b.final_feed_score > card_a.final_feed_score, "Disaster must outrank isolated road accident"

    # -------------------------------------------------------------------------
    # TEST C: Major national policy announcement
    # -------------------------------------------------------------------------
    title_c = "Union Cabinet approves historic national industrial and employment policy"
    summary_c = "Prime Minister chairs cabinet meeting approving comprehensive statutory framework transforming manufacturing regulations and creating 5 million jobs nationwide."
    dims_c, imp_c = ImportanceEngine.analyze_event_text(title_c, summary_c, "national")
    urg_c, reason_c = UrgencyEngine.calculate_urgency(title_c, summary_c)
    frsh_c = FreshnessEngine.calculate_freshness(published_at=now - timedelta(minutes=40), current_time=now)
    ver_c, _ = VerificationEngine.calculate_verification([{"name": "Press Trust of India"}, {"name": "The Hindu"}])
    rel_c = RelevanceEngine.calculate_relevance("national")
    card_c = FeedRankingEngine.compute_final_score(imp_c, urg_c, frsh_c, rel_c, ver_c, dimensions=dims_c, source_count=2, tier1_count=2)

    print(f"\n[TEST C] Major national policy announcement:")
    print(f"  Headline: '{title_c}'")
    print(f"  Importance: {imp_c:.1f} (Policy: {dims_c.policy_impact.score:.1f}, Geo: {dims_c.geographic_impact.score:.1f})")
    print(f"  Urgency: {urg_c:.1f} | Final Feed Score: {card_c.final_feed_score:.2f}")
    assert imp_c > imp_a, f"Policy importance ({imp_c}) must exceed isolated accident ({imp_a})"
    assert card_c.final_feed_score > card_a.final_feed_score, f"National policy ({card_c.final_feed_score}) must outrank isolated road accident ({card_a.final_feed_score})"

    # -------------------------------------------------------------------------
    # TEST D: Major economic / business development
    # -------------------------------------------------------------------------
    title_d = "Reserve Bank of India cuts benchmark repo rate by 50 bps, announces comprehensive trade liquidity boost"
    summary_d = "Central bank announces surprise interest rate cut and major economic policy stimulus to counteract inflation surges and boost capital investments nationwide."
    dims_d, imp_d = ImportanceEngine.analyze_event_text(title_d, summary_d, "business")
    urg_d, reason_d = UrgencyEngine.calculate_urgency(title_d, summary_d)
    frsh_d = FreshnessEngine.calculate_freshness(published_at=now - timedelta(minutes=45), current_time=now)
    ver_d, _ = VerificationEngine.calculate_verification([{"name": "The Economic Times"}, {"name": "Reuters"}])
    rel_d = RelevanceEngine.calculate_relevance("business")
    card_d = FeedRankingEngine.compute_final_score(imp_d, urg_d, frsh_d, rel_d, ver_d, dimensions=dims_d, source_count=2, tier1_count=2)

    print(f"\n[TEST D] Major economic development:")
    print(f"  Headline: '{title_d}'")
    print(f"  Importance: {imp_d:.1f} (Econ: {dims_d.economic_impact.score:.1f}, Geo: {dims_d.geographic_impact.score:.1f})")
    print(f"  Urgency: {urg_d:.1f} | Final Feed Score: {card_d.final_feed_score:.2f}")
    assert imp_d > imp_a, f"Major economic impact ({imp_d}) must exceed isolated accident ({imp_a})"
    assert card_d.final_feed_score > card_a.final_feed_score, f"Major economic development ({card_d.final_feed_score}) must outrank isolated road accident ({card_a.final_feed_score})"

    # -------------------------------------------------------------------------
    # TEST E: Major cybersecurity incident
    # -------------------------------------------------------------------------
    title_e = "Massive cyberattack cripples national banking network and digital payment gateways"
    summary_e = "Critical infrastructure hack and sophisticated ransomware breach halts transactions across 12 major banks nationwide, emergency protocols activated."
    dims_e, imp_e = ImportanceEngine.analyze_event_text(title_e, summary_e, "technology")
    urg_e, reason_e = UrgencyEngine.calculate_urgency(title_e, summary_e)
    frsh_e = FreshnessEngine.calculate_freshness(published_at=now - timedelta(minutes=25), current_time=now)
    ver_e, _ = VerificationEngine.calculate_verification([{"name": "Reuters"}, {"name": "The Indian Express"}])
    rel_e = RelevanceEngine.calculate_relevance("technology")
    card_e = FeedRankingEngine.compute_final_score(imp_e, urg_e, frsh_e, rel_e, ver_e, dimensions=dims_e, source_count=2, tier1_count=2)

    print(f"\n[TEST E] Major cybersecurity incident:")
    print(f"  Headline: '{title_e}'")
    print(f"  Importance: {imp_e:.1f} (Security: {dims_e.security_impact.score:.1f}, Geo: {dims_e.geographic_impact.score:.1f})")
    print(f"  Urgency: {urg_e:.1f} | Final Feed Score: {card_e.final_feed_score:.2f}")
    assert dims_e.security_impact.score >= 8.0, "Security impact should be high"
    assert card_e.final_feed_score > card_a.final_feed_score, f"Cybersecurity crisis ({card_e.final_feed_score}) must outrank isolated accident ({card_a.final_feed_score})"

    # -------------------------------------------------------------------------
    # TEST F: Old death / accident story (36 hours old)
    # -------------------------------------------------------------------------
    title_f = "Two killed in highway accident three days ago"
    summary_f = "Looking back at the road accident that claimed two lives near the toll plaza earlier this week. Historic lookback as families reminisce."
    dims_f, imp_f = ImportanceEngine.analyze_event_text(title_f, summary_f, "national")
    urg_f, reason_f = UrgencyEngine.calculate_urgency(title_f, summary_f)
    frsh_f = FreshnessEngine.calculate_freshness(published_at=now - timedelta(hours=36), current_time=now)
    ver_f, _ = VerificationEngine.calculate_verification([{"name": "Local Press"}])
    rel_f = RelevanceEngine.calculate_relevance("national")
    card_f = FeedRankingEngine.compute_final_score(imp_f, urg_f, frsh_f, rel_f, ver_f, dimensions=dims_f)

    print(f"\n[TEST F] Old death/accident story (36h old):")
    print(f"  Headline: '{title_f}'")
    print(f"  Importance: {imp_f:.1f}, Urgency: {urg_f:.1f}, Freshness: {frsh_f:.1f}")
    print(f"  Final Feed Score: {card_f.final_feed_score:.2f}")
    assert frsh_f <= 15.0, f"36h old story must have decayed freshness (<= 15), got {frsh_f}"
    assert card_f.final_feed_score < 30.0, f"Old accident story score must be low (< 30), got {card_f.final_feed_score}"
    assert card_b.final_feed_score > card_f.final_feed_score * 2, "Disaster must score more than double an old accident story"

    # -------------------------------------------------------------------------
    # Overall Relative Ordering Summary
    # -------------------------------------------------------------------------
    print("\n" + "=" * 65)
    print("FINAL RANK ORDER OF ALL 6 TEST STORIES:")
    print("=" * 65)
    stories = [
        ("TEST B: Major Flood Disaster", card_b.final_feed_score),
        ("TEST E: Major Cyberattack", card_e.final_feed_score),
        ("TEST C: National Policy Overhaul", card_c.final_feed_score),
        ("TEST D: RBI Economic Stimulus", card_d.final_feed_score),
        ("TEST A: Isolated Road Accident", card_a.final_feed_score),
        ("TEST F: Old Accident Story (36h)", card_f.final_feed_score),
    ]
    stories.sort(key=lambda s: s[1], reverse=True)
    for rank, (name, score) in enumerate(stories, 1):
        print(f"  #{rank}: {name:<35} -> Score: {score:.2f}")

    assert stories[0][0] == "TEST B: Major Flood Disaster", "Emergency must rank #1"
    assert card_a.final_feed_score < card_c.final_feed_score, "Policy must outrank isolated accident"
    assert card_a.final_feed_score < card_d.final_feed_score, "Economy must outrank isolated accident"
    assert card_a.final_feed_score < card_e.final_feed_score, "Cyberattack must outrank isolated accident"

    print("\n[ALL TESTS A THROUGH F PASSED] - Casualties != Automatic Top Priority.")
    print("=" * 65)
    return True


if __name__ == "__main__":
    run_discrimination_tests()

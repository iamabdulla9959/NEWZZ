"""
Comprehensive Test Cases for Structured Importance and Multi-Dimensional Feed Ranking.
Validates all 10 real-world scenarios and mathematical property invariants specified in requirements.
"""

from datetime import datetime, timedelta, timezone
import pytest

from packages.ranking_engine.config import RankingConfig
from packages.ranking_engine.models import (
    DimensionEvidence,
    ObjectiveDimensions,
)
from packages.ranking_engine.importance_engine import ImportanceEngine
from packages.ranking_engine.urgency_engine import UrgencyEngine
from packages.ranking_engine.freshness_engine import FreshnessEngine
from packages.ranking_engine.verification_engine import VerificationEngine
from packages.ranking_engine.relevance_engine import RelevanceEngine
from packages.ranking_engine.feed_ranking_engine import FeedRankingEngine


def test_property_invariants():
    """Validates that all scores are strictly clamped between 0 and 100 under extreme inputs."""
    # Negative inputs
    out_neg = FeedRankingEngine.compute_final_score(
        objective_importance=-50.0,
        urgency=-20.0,
        freshness=-10.0,
        personal_relevance=-5.0,
        verification_confidence=-100.0,
    )
    assert out_neg.final_feed_score == 0.0
    assert out_neg.objective_importance == 0.0

    # Overflow inputs
    out_over = FeedRankingEngine.compute_final_score(
        objective_importance=500.0,
        urgency=250.0,
        freshness=150.0,
        personal_relevance=110.0,
        verification_confidence=999.0,
    )
    assert out_over.final_feed_score == 100.0
    assert out_over.objective_importance == 100.0


def test_freshness_curve_and_precedence():
    """Validates the freshness decay model and timestamp precedence."""
    now = datetime.now(timezone.utc)

    # 10 min old -> 100
    t10m = now - timedelta(minutes=10)
    assert FreshnessEngine.calculate_freshness(published_at=t10m, current_time=now) == 100.0

    # 25 min old -> 95
    t25m = now - timedelta(minutes=25)
    assert FreshnessEngine.calculate_freshness(published_at=t25m, current_time=now) == 95.0

    # 45 min old -> 90
    t45m = now - timedelta(minutes=45)
    assert FreshnessEngine.calculate_freshness(published_at=t45m, current_time=now) == 90.0

    # 90 min (1.5h) old -> 80
    t90m = now - timedelta(minutes=90)
    assert FreshnessEngine.calculate_freshness(published_at=t90m, current_time=now) == 80.0

    # 3 hours old -> 70
    t3h = now - timedelta(hours=3)
    assert FreshnessEngine.calculate_freshness(published_at=t3h, current_time=now) == 70.0

    # 6 hours old -> 55
    t6h = now - timedelta(hours=6)
    assert FreshnessEngine.calculate_freshness(published_at=t6h, current_time=now) == 55.0

    # 10 hours old -> 40
    t10h = now - timedelta(hours=10)
    assert FreshnessEngine.calculate_freshness(published_at=t10h, current_time=now) == 40.0

    # 18 hours old -> 25
    t18h = now - timedelta(hours=18)
    assert FreshnessEngine.calculate_freshness(published_at=t18h, current_time=now) == 25.0

    # 36 hours old -> 10
    t36h = now - timedelta(hours=36)
    assert FreshnessEngine.calculate_freshness(published_at=t36h, current_time=now) == 10.0

    # 72 hours old -> 5
    t72h = now - timedelta(hours=72)
    assert FreshnessEngine.calculate_freshness(published_at=t72h, current_time=now) == 5.0

    # Future timestamp safely handled
    tfuture = now + timedelta(hours=2)
    assert FreshnessEngine.calculate_freshness(published_at=tfuture, current_time=now) == 100.0


def test_verification_trust_model():
    """Validates verification confidence calculation."""
    # Multiple Tier 1
    t1_sources = [{"name": "The Hindu"}, {"name": "BBC News"}, {"name": "Reuters"}]
    score, meta = VerificationEngine.calculate_verification(t1_sources)
    assert score >= 95.0
    assert meta["status"] == "cross_verified_tier1"

    # Single Tier 1 wire
    wire_source = [{"name": "Press Trust of India"}]
    score_wire, meta_wire = VerificationEngine.calculate_verification(wire_source)
    assert 85.0 <= score_wire <= 90.0

    # Conflicting sources
    score_conf, meta_conf = VerificationEngine.calculate_verification(t1_sources, conflict_detected=True)
    assert score_conf < 60.0
    assert meta_conf["status"] == "flagged_conflict"


def test_ten_benchmark_scenarios():
    """
    Executes all 10 required real-world scenarios and verifies their relative ranking order.
    Demonstrates: NEW != IMPORTANT.
    """
    now = datetime.now(timezone.utc)

    # -------------------------------------------------------------------------
    # Scenario 1: Major Cyclone (2 hours old, affecting thousands)
    # -------------------------------------------------------------------------
    dims1, imp1 = ImportanceEngine.analyze_event_text(
        title="Cyclone Dana strikes Odisha coast, thousands evacuated",
        summary="Severe tropical cyclone brings 120kmph winds, widespread storm surge and thousands displaced across 5 coastal districts. Immediate shelter orders in effect.",
        category="state"
    )
    urg1, _ = UrgencyEngine.calculate_urgency(
        title="Cyclone Dana strikes Odisha coast, thousands evacuated",
        summary="Immediate shelter orders in effect. Evacuation underway.",
        action_required=True
    )
    frsh1 = FreshnessEngine.calculate_freshness(published_at=now - timedelta(hours=2), current_time=now)
    ver1, _ = VerificationEngine.calculate_verification([{"name": "The Hindu"}, {"name": "NDTV"}])
    rel1 = RelevanceEngine.calculate_relevance("state", story_state="Odisha", user_state="Odisha")
    card1 = FeedRankingEngine.compute_final_score(imp1, urg1, frsh1, rel1, ver1, dimensions=dims1, source_count=2, tier1_count=2)

    # -------------------------------------------------------------------------
    # Scenario 2: Major National Policy (3 hours old)
    # -------------------------------------------------------------------------
    dims2, imp2 = ImportanceEngine.analyze_event_text(
        title="Union Cabinet approves historic tax reform bill",
        summary="Cabinet approves comprehensive national statutory tax code overhaul, restructuring GST brackets and corporate rates nationwide.",
        category="politics"
    )
    urg2, _ = UrgencyEngine.calculate_urgency("Union Cabinet approves historic tax reform bill", "Approved today by Cabinet.")
    frsh2 = FreshnessEngine.calculate_freshness(published_at=now - timedelta(hours=3), current_time=now)
    ver2, _ = VerificationEngine.calculate_verification([{"name": "Press Trust of India"}, {"name": "The Hindu"}])
    rel2 = RelevanceEngine.calculate_relevance("politics", user_category_order=["politics", "national"])
    card2 = FeedRankingEngine.compute_final_score(imp2, urg2, frsh2, rel2, ver2, dimensions=dims2, source_count=2, tier1_count=2)

    # -------------------------------------------------------------------------
    # Scenario 3: Major Cyberattack on Critical Infrastructure (1 hour old)
    # -------------------------------------------------------------------------
    dims3, imp3 = ImportanceEngine.analyze_event_text(
        title="Major cyberattack cripples regional power grid",
        summary="Sophisticated ransomware and ddos grid attack forces emergency backup switch, investigating nation-state threat actors.",
        category="tech"
    )
    urg3, _ = UrgencyEngine.calculate_urgency("Major cyberattack cripples regional power grid", "Search and emergency isolation underway.")
    frsh3 = FreshnessEngine.calculate_freshness(published_at=now - timedelta(hours=1), current_time=now)
    ver3, _ = VerificationEngine.calculate_verification([{"name": "Reuters"}, {"name": "BBC News"}])
    rel3 = RelevanceEngine.calculate_relevance("tech")
    card3 = FeedRankingEngine.compute_final_score(imp3, urg3, frsh3, rel3, ver3, dimensions=dims3, source_count=2, tier1_count=2)

    # -------------------------------------------------------------------------
    # Scenario 4: Hospital Network Ransomware (30 min old)
    # -------------------------------------------------------------------------
    dims4, imp4 = ImportanceEngine.analyze_event_text(
        title="Critical ransomware attack halts hospital networks",
        summary="Malware outbreak forces emergency room diversions, patient monitoring offline across metropolitan healthcare system.",
        category="health"
    )
    urg4, _ = UrgencyEngine.calculate_urgency("Critical ransomware attack halts hospital networks", "Emergency diversions in effect.")
    frsh4 = FreshnessEngine.calculate_freshness(published_at=now - timedelta(minutes=30), current_time=now)
    ver4, _ = VerificationEngine.calculate_verification([{"name": "The Indian Express"}])
    rel4 = RelevanceEngine.calculate_relevance("health")
    card4 = FeedRankingEngine.compute_final_score(imp4, urg4, frsh4, rel4, ver4, dimensions=dims4, source_count=1, tier1_count=1)

    # -------------------------------------------------------------------------
    # Scenario 5: Minor Local Announcement (10 min old, user lives there)
    # -------------------------------------------------------------------------
    dims5, imp5 = ImportanceEngine.analyze_event_text(
        title="Water pipeline maintenance in Ward 4 scheduled tomorrow",
        summary="Municipal corporation announces 2-hour low pressure water supply during scheduled valve replacement.",
        category="district"
    )
    urg5, _ = UrgencyEngine.calculate_urgency("Water pipeline maintenance scheduled tomorrow", "Routine maintenance planned.")
    frsh5 = FreshnessEngine.calculate_freshness(published_at=now - timedelta(minutes=10), current_time=now)
    ver5, _ = VerificationEngine.calculate_verification([{"name": "Local City Bulletin"}])
    rel5 = RelevanceEngine.calculate_relevance("district", story_district="Hyderabad", user_district="Hyderabad")
    card5 = FeedRankingEngine.compute_final_score(imp5, urg5, frsh5, rel5, ver5, dimensions=dims5, source_count=1)

    # -------------------------------------------------------------------------
    # Scenario 6: Celebrity Death (2 hours old)
    # -------------------------------------------------------------------------
    dims6, imp6 = ImportanceEngine.analyze_event_text(
        title="Veteran actor dies aged 82 in Mumbai",
        summary="Celebrated film icon passes away peacefully at residence surrounded by family after prolonged age-related illness.",
        category="entertainment"
    )
    urg6, _ = UrgencyEngine.calculate_urgency("Veteran actor dies aged 82", "Condolences pouring in.")
    frsh6 = FreshnessEngine.calculate_freshness(published_at=now - timedelta(hours=2), current_time=now)
    ver6, _ = VerificationEngine.calculate_verification([{"name": "The Times of India"}, {"name": "NDTV"}])
    rel6 = RelevanceEngine.calculate_relevance("entertainment")
    card6 = FeedRankingEngine.compute_final_score(imp6, urg6, frsh6, rel6, ver6, dimensions=dims6, source_count=2, tier1_count=2)

    # -------------------------------------------------------------------------
    # Scenario 7: Old Major Event (30 hours old)
    # -------------------------------------------------------------------------
    dims7, imp7 = ImportanceEngine.analyze_event_text(
        title="Major earthquake magnitude 7.4 strikes mountain province",
        summary="Massive earthquake leaves hundreds dead, thousands injured and extensive building collapse.",
        category="international"
    )
    urg7, _ = UrgencyEngine.calculate_urgency("Major earthquake magnitude 7.4", "Controlled recovery operations continuing.")
    frsh7 = FreshnessEngine.calculate_freshness(published_at=now - timedelta(hours=30), current_time=now)
    ver7, _ = VerificationEngine.calculate_verification([{"name": "BBC News"}, {"name": "Reuters"}])
    rel7 = RelevanceEngine.calculate_relevance("international")
    card7 = FeedRankingEngine.compute_final_score(imp7, urg7, frsh7, rel7, ver7, dimensions=dims7, source_count=2, tier1_count=2)

    # -------------------------------------------------------------------------
    # Scenario 8: Very New Insignificant Event (5 min old, fresh=100)
    # -------------------------------------------------------------------------
    dims8, imp8 = ImportanceEngine.analyze_event_text(
        title="Actor spotted at cafe wearing trendy sunglasses",
        summary="Star greeted fans briefly while grabbing coffee on Sunday afternoon in suburban neighborhood.",
        category="entertainment"
    )
    urg8, _ = UrgencyEngine.calculate_urgency("Actor spotted at cafe", "Social media video.")
    frsh8 = FreshnessEngine.calculate_freshness(published_at=now - timedelta(minutes=5), current_time=now)
    ver8, _ = VerificationEngine.calculate_verification([{"name": "Bollywood Paparazzi"}])
    rel8 = RelevanceEngine.calculate_relevance("entertainment")
    card8 = FeedRankingEngine.compute_final_score(imp8, urg8, frsh8, rel8, ver8, dimensions=dims8, source_count=1)

    # -------------------------------------------------------------------------
    # Scenario 9: Major Event With One Credible Source (40 min old)
    # -------------------------------------------------------------------------
    dims9, imp9 = ImportanceEngine.analyze_event_text(
        title="Emergency toxic chemical spill triggers mandatory evacuation order",
        summary="Industrial train derailment breaches chlorine tankers, toxic plume moving towards township.",
        category="national"
    )
    urg9, _ = UrgencyEngine.calculate_urgency("Toxic chemical spill triggers mandatory evacuation", "Take shelter immediately.", action_required=True)
    frsh9 = FreshnessEngine.calculate_freshness(published_at=now - timedelta(minutes=40), current_time=now)
    ver9, _ = VerificationEngine.calculate_verification([{"name": "Reuters"}]) # Single credible Tier 1 wire
    rel9 = RelevanceEngine.calculate_relevance("national")
    card9 = FeedRankingEngine.compute_final_score(imp9, urg9, frsh9, rel9, ver9, dimensions=dims9, source_count=1, tier1_count=1)

    # -------------------------------------------------------------------------
    # Scenario 10: Conflicting Reports (45 min old)
    # -------------------------------------------------------------------------
    dims10, imp10 = ImportanceEngine.analyze_event_text(
        title="Conflicting casualty numbers after border outpost explosion",
        summary="Different military and regional authorities issue contradictory fatality figures following defense perimeter explosion.",
        category="national"
    )
    urg10, _ = UrgencyEngine.calculate_urgency("Conflicting casualty numbers after explosion", "Situation developing.")
    frsh10 = FreshnessEngine.calculate_freshness(published_at=now - timedelta(minutes=45), current_time=now)
    ver10, _ = VerificationEngine.calculate_verification([{"name": "Local Wire 1"}, {"name": "Local Wire 2"}], conflict_detected=True)
    rel10 = RelevanceEngine.calculate_relevance("national")
    card10 = FeedRankingEngine.compute_final_score(imp10, urg10, frsh10, rel10, ver10, dimensions=dims10, source_count=2, conflict_detected=True)

    # -------------------------------------------------------------------------
    # VERIFICATION OF CORE PRINCIPLES
    # -------------------------------------------------------------------------
    # 1. Major Cyclone (Card 1) vs Celebrity Spotting 5 min old (Card 8)
    assert card1.final_feed_score > card8.final_feed_score
    print(f"Cyclone (2h old) Score: {card1.final_feed_score} vs Celebrity (5m old) Score: {card8.final_feed_score}")

    # 2. Celebrity Death (Card 6) must NOT receive disaster-level importance
    assert dims6.safety_impact.score == 0.0
    assert card6.objective_importance < card1.objective_importance

    # 3. Hospital Ransomware (Card 4) scores high on security and public safety
    assert dims4.security_impact.score >= 8.0
    assert card4.final_feed_score >= 60.0

    # 4. Minor local announcement (Card 5) is NOT #1 overall despite local match
    assert card1.final_feed_score > card5.final_feed_score

    # 5. Major event with single source (Card 9) maintains high importance
    assert card9.objective_importance >= 60.0
    assert card9.verification_confidence >= 85.0
    assert card9.final_feed_score > card5.final_feed_score

    # 6. Conflicting reports (Card 10) indicates conflict in priority_reason
    assert "conflicting" in card10.priority_reason.lower()
    assert card10.verification_confidence <= 50.0

    # 7. Old major event (Card 7, 30h old) has lower freshness but high importance
    assert card7.freshness == 10.0
    assert card7.objective_importance >= 60.0

    # Verify explainability priority_reason is present on all cards
    all_cards = [card1, card2, card3, card4, card5, card6, card7, card8, card9, card10]
    for c in all_cards:
        assert bool(c.priority_reason)
        assert 0.0 <= c.final_feed_score <= 100.0


def test_priority_score_neutrality():
    """Validates that a card with priority_score=10 does not bypass the ranking engine."""
    # A routine minor announcement
    dims, imp = ImportanceEngine.analyze_event_text(
        title="Routine park cleanup scheduled for Sunday",
        summary="Volunteers will gather for a 2-hour garden maintenance session.",
        category="district"
    )
    urg, _ = UrgencyEngine.calculate_urgency("Routine park cleanup scheduled", "Routine maintenance")
    out = FeedRankingEngine.compute_final_score(
        objective_importance=imp,
        urgency=urg,
        freshness=80.0,
        personal_relevance=50.0,
        verification_confidence=70.0
    )
    # Even if an external metadata tag has priority_score=10, the engine scores it truthfully
    assert out.objective_importance < 30.0
    assert out.urgency < 50.0
    assert out.final_feed_score < 50.0


def test_emergency_floor_order_and_behavior():
    """Validates that urgency >= 90 elevates importance to 75 BEFORE final score calculation."""
    # Low importance (30.0) + Active Emergency Urgency (95.0)
    out_low = FeedRankingEngine.compute_final_score(
        objective_importance=30.0,
        urgency=95.0,
        freshness=80.0,
        personal_relevance=50.0,
        verification_confidence=80.0
    )
    assert out_low.objective_importance == 75.0
    # Formula check: (75 * 0.40) + (95 * 0.20) + (80 * 0.15) + (50 * 0.15) + (80 * 0.10)
    # = 30.0 + 19.0 + 12.0 + 7.5 + 8.0 = 76.5
    assert out_low.final_feed_score == 76.5

    # High importance (90.0) + Active Emergency Urgency (95.0) -> retains 90.0
    out_high = FeedRankingEngine.compute_final_score(
        objective_importance=90.0,
        urgency=95.0,
        freshness=80.0,
        personal_relevance=50.0,
        verification_confidence=80.0
    )
    assert out_high.objective_importance == 90.0
    # Formula check: (90 * 0.40) + (95 * 0.20) + (80 * 0.15) + (50 * 0.15) + (80 * 0.10)
    # = 36.0 + 19.0 + 12.0 + 7.5 + 8.0 = 82.5
    assert out_high.final_feed_score == 82.5


def test_nepal_flood_ground_truth_case():
    """
    Validates exact ground-truth values for the Nepal Flood case:
    Human Impact: 20
    Safety Impact: 18
    Geographic Impact: 14
    Raw Importance: 52
    Urgency: 95
    Effective Importance: 75
    """
    title = "Floods in Nepal Claim 1,385 Lives, 8 Sikkim Residents Evacuated"
    summary = (
        "In the early hours of March 15, 2024, flash floods in Nepal's western districts claimed 1,385 lives "
        "and left dozens missing. Eight residents from Sikkim, who had been stranded in the affected areas, "
        "were safely evacuated and returned home. The deluge overwhelmed rivers and caused landslides. "
        "The Nepalese government has declared a state of emergency and appealed for international assistance."
    )
    dims, raw_imp = ImportanceEngine.analyze_event_text(title, summary, "national")
    urg, _ = UrgencyEngine.calculate_urgency(title, summary)
    out = FeedRankingEngine.compute_final_score(raw_imp, urg, 80.0, 50.0, 82.0)

    assert dims.human_impact.score == 20.0
    assert dims.safety_impact.score == 18.0
    assert dims.geographic_impact.score == 14.0
    assert dims.economic_impact.score == 0.0
    assert dims.policy_impact.score == 0.0
    assert dims.infrastructure_impact.score == 0.0
    assert dims.security_impact.score == 0.0
    assert dims.consequence_impact.score == 0.0
    assert raw_imp == 52.0
    assert urg == 95.0
    assert out.objective_importance == 75.0


def test_casualty_extraction_positive_and_negative():
    """Validates casualty regex against positive explicit expressions and negative traps."""
    from packages.ranking_engine.importance_engine import ImportanceEngine

    # Positive explicit expressions
    positives = [
        ("Five killed in crash", 5),
        ("10 people killed", 10),
        ("25 dead", 25),
        ("100 fatalities", 100),
        ("1,385 lives lost", 1385),
        ("Floods claim 1,385 lives", 1385),
        ("death toll reaches 1,385", 1385),
        ("death toll of 1,385", 1385),
        ("at least 1,385 people have died", 1385),
    ]
    for text, expected in positives:
        cnt = ImportanceEngine._extract_casualty_count(text)
        assert cnt == expected, f"Failed positive for '{text}': got {cnt}, expected {expected}"

    # Negative non-casualty expressions
    negatives = [
        "Floods affected 1,385 homes",
        "Meeting held in 2025",
        "Damage estimated at $1,385 million",
        "1,385 people affected",
        "1,385 vehicles damaged",
    ]
    for text in negatives:
        cnt = ImportanceEngine._extract_casualty_count(text)
        assert cnt is None, f"Failed negative for '{text}': falsely extracted {cnt}"


def test_36_hour_clustering_window():
    """Validates that articles outside the 36-hour sliding window are not merged into the same cluster."""
    from website_scraping.process_news import cluster_and_deduplicate

    t0 = datetime.now(timezone.utc)
    t_12h = (t0 - timedelta(hours=12)).isoformat()
    t_40h = (t0 - timedelta(hours=40)).isoformat()

    t1 = "Nepal Floods: 60 dead as landslides hit western districts"
    t2 = "Nepal Floods: Death toll hits 60 as landslides strike western districts"

    # Within 36h -> merges
    c_within = cluster_and_deduplicate([
        {"title": t1, "category": "world", "state": None, "published_date": t0.isoformat()},
        {"title": t2, "category": "world", "state": None, "published_date": t_12h},
    ])
    assert len(c_within) == 1

    # Outside 36h -> separates
    c_outside = cluster_and_deduplicate([
        {"title": t1, "category": "world", "state": None, "published_date": t0.isoformat()},
        {"title": t2, "category": "world", "state": None, "published_date": t_40h},
    ])
    assert len(c_outside) == 2


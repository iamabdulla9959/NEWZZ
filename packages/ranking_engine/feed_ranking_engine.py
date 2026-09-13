"""
Master Feed Ranking Engine.
Computes the FINAL_FEED_SCORE (0..100) using the centralized configurable formula:
  Final = (Importance * 0.40) + (Urgency * 0.20) + (Freshness * 0.15) + (Relevance * 0.15) + (Verification * 0.10)
Generates evidence-backed, human-readable explanations (priority_reason) for why a card ranks where it does.
"""

from typing import Any, Dict, List, Optional
from .config import RankingConfig
from .models import ObjectiveDimensions, StoryScoringOutput


class FeedRankingEngine:
    @classmethod
    def compute_final_score(
        cls,
        objective_importance: float,
        urgency: float,
        freshness: float,
        personal_relevance: float,
        verification_confidence: float,
        dimensions: Optional[ObjectiveDimensions] = None,
        urgency_reason: Optional[str] = None,
        source_count: int = 1,
        tier1_count: int = 0,
        conflict_detected: bool = False,
    ) -> StoryScoringOutput:
        """
        Calculates normalized final feed score and generates evidence-based explanation.
        """
        # Ensure all components are clamped to 0..100
        imp = max(0.0, min(100.0, float(objective_importance)))
        urg = max(0.0, min(100.0, float(urgency)))
        frsh = max(0.0, min(100.0, float(freshness)))
        rel = max(0.0, min(100.0, float(personal_relevance)))
        ver = max(0.0, min(100.0, float(verification_confidence)))

        # Authoritative Emergency Floor: Genuinely urgent civic emergency elevates importance floor
        if urg >= RankingConfig.EMERGENCY_URGENCY_THRESHOLD:
            imp = max(imp, RankingConfig.EMERGENCY_IMPORTANCE_FLOOR)

        final_score = (
            (imp * RankingConfig.WEIGHT_OBJECTIVE_IMPORTANCE)
            + (urg * RankingConfig.WEIGHT_URGENCY)
            + (frsh * RankingConfig.WEIGHT_FRESHNESS)
            + (rel * RankingConfig.WEIGHT_PERSONAL_RELEVANCE)
            + (ver * RankingConfig.WEIGHT_VERIFICATION)
        )
        final_score = round(max(0.0, min(100.0, final_score)), 2)

        # Generate truthful, evidence-grounded priority explanation
        reason = cls._generate_priority_reason(
            imp=imp,
            urg=urg,
            frsh=frsh,
            rel=rel,
            ver=ver,
            dimensions=dimensions,
            urgency_reason=urgency_reason,
            source_count=source_count,
            tier1_count=tier1_count,
            conflict_detected=conflict_detected,
        )

        breakdown = {
            "objective_importance": imp,
            "urgency": urg,
            "freshness": frsh,
            "personal_relevance": rel,
            "verification_confidence": ver,
            "weights": {
                "importance": RankingConfig.WEIGHT_OBJECTIVE_IMPORTANCE,
                "urgency": RankingConfig.WEIGHT_URGENCY,
                "freshness": RankingConfig.WEIGHT_FRESHNESS,
                "relevance": RankingConfig.WEIGHT_PERSONAL_RELEVANCE,
                "verification": RankingConfig.WEIGHT_VERIFICATION,
            },
        }

        return StoryScoringOutput(
            objective_importance=imp,
            urgency=urg,
            freshness=frsh,
            personal_relevance=rel,
            verification_confidence=ver,
            final_feed_score=final_score,
            priority_reason=reason,
            breakdown=breakdown,
        )

    @classmethod
    def generate_priority_reason(
        cls,
        dimensions: Optional[ObjectiveDimensions] = None,
        urgency: float = 35.0,
        verification: float = 60.0,
        importance: float = 0.0,
        freshness: float = 50.0,
        relevance: float = 50.0,
        urgency_reason: Optional[str] = None,
        source_count: int = 1,
        tier1_count: int = 0,
        conflict_detected: bool = False,
    ) -> str:
        return cls._generate_priority_reason(
            imp=importance,
            urg=urgency,
            frsh=freshness,
            rel=relevance,
            ver=verification,
            dimensions=dimensions,
            urgency_reason=urgency_reason,
            source_count=source_count,
            tier1_count=tier1_count,
            conflict_detected=conflict_detected,
        )

    @staticmethod
    def _generate_priority_reason(
        imp: float,
        urg: float,
        frsh: float,
        rel: float,
        ver: float,
        dimensions: Optional[ObjectiveDimensions] = None,
        urgency_reason: Optional[str] = None,
        source_count: int = 1,
        tier1_count: int = 0,
        conflict_detected: bool = False,
    ) -> str:
        """
        Constructs a concise, evidence-based sentence explaining the story's ranking.
        """
        clauses = []

        # 1. Primary Impact Reason
        if dimensions:
            if dimensions.safety_impact.score >= 12.0:
                clauses.append("Major threat to public life and safety")
            elif dimensions.security_impact.score >= 7.0:
                clauses.append("Critical cybersecurity / national security incident")
            elif dimensions.human_impact.score >= 12.0:
                clauses.append("Substantial human casualty and displacement impact")
            elif dimensions.policy_impact.score >= 7.0:
                clauses.append("Significant government policy or statutory change")
            elif dimensions.economic_impact.score >= 7.0:
                clauses.append("High-consequence macroeconomic development")
            elif dimensions.infrastructure_impact.score >= 6.0:
                clauses.append("Widespread public infrastructure disruption")
            elif imp >= 70.0:
                clauses.append("High overall civic importance")
        elif imp >= 70.0:
            clauses.append("High overall civic importance")

        # 2. Urgency Clause
        if urg >= 85.0:
            clauses.append("actively unfolding emergency requiring immediate public vigilance")
        elif urg >= 65.0:
            clauses.append("developing news event confirmed today")

        # 3. Location Clause
        if rel >= 75.0:
            clauses.append("directly relevant to your local area")

        # 4. Verification Clause
        if conflict_detected:
            clauses.append("conflicting reports detected across sources")
        elif tier1_count >= 2 and source_count >= 2:
            clauses.append(f"corroborated by {source_count} major newsrooms")
        elif source_count >= 2:
            clauses.append(f"corroborated across {source_count} independent sources")
        elif ver >= 85.0:
            clauses.append("confirmed by verified primary wire service")

        if not clauses:
            if imp < 35.0:
                return "Routine informational update; low systemic public safety consequence."
            return "Standard news coverage verified by regional reporting sources."

        # Combine smoothly into a clean explanation
        sentence = clauses[0]
        if len(clauses) > 1:
            sentence += ", " + ", ".join(clauses[1:]) + "."
        else:
            sentence += "."

        return sentence

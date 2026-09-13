"""
Pydantic Data Models for Structured Evidence and Ranking Outputs.
Ensures validation, range bounds (0..100), and evidence provenance.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DimensionEvidence(BaseModel):
    score: float = Field(default=0.0, description="Score assigned to this dimension within its specific maximum.")
    evidence: str = Field(default="", description="Concrete factual quote or fact supporting this score.")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence in the evidence (0.0 to 1.0).")
    explanation: str = Field(default="", description="Short reasoning why this score was awarded.")


class ObjectiveDimensions(BaseModel):
    human_impact: DimensionEvidence = Field(default_factory=DimensionEvidence)
    safety_impact: DimensionEvidence = Field(default_factory=DimensionEvidence)
    geographic_impact: DimensionEvidence = Field(default_factory=DimensionEvidence)
    economic_impact: DimensionEvidence = Field(default_factory=DimensionEvidence)
    policy_impact: DimensionEvidence = Field(default_factory=DimensionEvidence)
    infrastructure_impact: DimensionEvidence = Field(default_factory=DimensionEvidence)
    security_impact: DimensionEvidence = Field(default_factory=DimensionEvidence)
    consequence_impact: DimensionEvidence = Field(default_factory=DimensionEvidence)


class EventAnalysisResult(BaseModel):
    """Output from structured event parsing / LLM extraction."""
    dimensions: ObjectiveDimensions = Field(default_factory=ObjectiveDimensions)
    objective_importance: float = Field(default=0.0, ge=0.0, le=100.0)
    urgency_score: float = Field(default=0.0, ge=0.0, le=100.0)
    urgency_reason: str = Field(default="")
    event_time: Optional[datetime] = None
    action_required: bool = False
    is_developing: bool = False
    priority_reason: str = Field(default="")


class StoryScoringOutput(BaseModel):
    """Final multi-dimensional scoring and ranking output for a news card."""
    objective_importance: float = Field(default=0.0, ge=0.0, le=100.0)
    urgency: float = Field(default=0.0, ge=0.0, le=100.0)
    freshness: float = Field(default=0.0, ge=0.0, le=100.0)
    personal_relevance: float = Field(default=0.0, ge=0.0, le=100.0)
    verification_confidence: float = Field(default=0.0, ge=0.0, le=100.0)
    final_feed_score: float = Field(default=0.0, ge=0.0, le=100.0)
    priority_reason: str = Field(default="")
    breakdown: Dict[str, Any] = Field(default_factory=dict)

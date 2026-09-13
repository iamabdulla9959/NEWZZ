from datetime import datetime

from pydantic import BaseModel


class CardSourceOut(BaseModel):
    source_id: str
    name: str
    url: str
    trust_tier: str | int

    model_config = {"from_attributes": True}


class CardOut(BaseModel):
    id: str
    headline: str
    summary: str
    category: str
    verified_status: str
    verification_type: str | None = None
    created_at: datetime | None = None
    published_at: datetime | None = None
    district: str | None = None
    state: str | None = None
    objective_score: float = 0.0
    priority_score: int = 5
    importance_score: float = 0.0
    urgency_score: float = 0.0
    freshness_score: float = 0.0
    verification_score: float = 0.0
    personal_relevance_score: float = 0.0
    final_feed_score: float = 0.0
    priority_reason: str = ""
    impact_evidence: dict | None = None
    image_url: str | None = None
    image_author: str | None = None
    image_author_url: str | None = None
    sources: list[CardSourceOut] = []

    model_config = {"from_attributes": True}


class FeedOut(BaseModel):
    items: list[CardOut]
    offset: int
    limit: int
    total: int
    fallback_used: bool = False
    fallback_level: str | None = None
    empty_reason: str | None = None


class UserPreferencesIn(BaseModel):
    category_order: list[str] = []


class UserPreferencesOut(BaseModel):
    device_id: str
    category_order: list[str] = []
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class IngestionHealthOut(BaseModel):
    status: str
    provider: str = "rss"
    last_run_timestamp: datetime | None = None
    sources_polled: int = 0
    articles_ingested: int = 0
    credits_used: int = 0
    errors: list[str] = []
    duration_seconds: float = 0.0

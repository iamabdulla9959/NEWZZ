from __future__ import annotations

import uuid
from datetime import datetime

# pyrefly: ignore [missing-import]
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Mapped, mapped_column, relationship
# pyrefly: ignore [missing-import]
from sqlalchemy.types import JSON

from app.db import Base
from pgvector.sqlalchemy import Vector


def new_id() -> str:
    return str(uuid.uuid4())


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    region: Mapped[str | None] = mapped_column(String(128), nullable=True)
    district: Mapped[str | None] = mapped_column(String(128), nullable=True)
    rss_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    trust_tier: Mapped[str] = mapped_column(String(32), nullable=False, default="2")
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, default="rss")
    verified_local_source: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    articles: Mapped[list[Article]] = relationship(back_populates="source")


ArticleEmbeddingType = Vector(768).with_variant(JSON(), "sqlite")


class Article(Base):
    __tablename__ = "articles"
    __table_args__ = (UniqueConstraint("url", name="uq_articles_url"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    title: Mapped[str] = mapped_column(String(1024), nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    original_language: Mapped[str | None] = mapped_column(String(10), nullable=True)
    original_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    translated_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    translation_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    category: Mapped[str | None] = mapped_column(String(32), nullable=True)
    district: Mapped[str | None] = mapped_column(String(128), nullable=True)
    state: Mapped[str | None] = mapped_column(String(128), nullable=True)
    wire_attribution: Mapped[str | None] = mapped_column(String(64), nullable=True)
    embedding: Mapped[list | None] = mapped_column(ArticleEmbeddingType, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    cluster_id: Mapped[str | None] = mapped_column(ForeignKey("story_clusters.id"), nullable=True)

    source: Mapped[Source] = relationship(back_populates="articles")
    cluster: Mapped[StoryCluster | None] = relationship(back_populates="articles")


class StoryCluster(Base):
    __tablename__ = "story_clusters"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    title_hint: Mapped[str] = mapped_column(String(1024), nullable=False, default="")
    eligible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    flagged_conflict: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    conflict_notes: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    articles: Mapped[list[Article]] = relationship(back_populates="cluster")
    cards: Mapped[list[Card]] = relationship(back_populates="cluster")


class Card(Base):
    __tablename__ = "cards"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    cluster_id: Mapped[str] = mapped_column(ForeignKey("story_clusters.id"), nullable=False)
    headline: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    verified_status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    verification_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    content_type: Mapped[str] = mapped_column(String(32), nullable=False, default="NEWS")
    district: Mapped[str | None] = mapped_column(String(128), nullable=True)
    state: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    objective_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    impact_keywords_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    priority_score: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    
    # Structured Multi-Dimensional Ranking Engine Fields
    importance_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    urgency_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    freshness_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    verification_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    personal_relevance_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    final_feed_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    priority_reason: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    impact_evidence: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_by: Mapped[str] = mapped_column(String(32), nullable=False, default="live_pipeline")
    is_corrected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    correction_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    image_author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    image_author_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    cluster: Mapped[StoryCluster] = relationship(back_populates="cards")

    sources: Mapped[list[CardSource]] = relationship(back_populates="card", cascade="all, delete-orphan")
    review_items: Mapped[list[ReviewQueueItem]] = relationship(back_populates="card")


class CardSource(Base):
    __tablename__ = "card_sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    card_id: Mapped[str] = mapped_column(ForeignKey("cards.id"), nullable=False)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"), nullable=False)
    article_id: Mapped[str | None] = mapped_column(ForeignKey("articles.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    trust_tier: Mapped[str] = mapped_column(String(32), nullable=False)

    card: Mapped[Card] = relationship(back_populates="sources")


class ReviewQueueItem(Base):
    __tablename__ = "review_queue"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    card_id: Mapped[str] = mapped_column(ForeignKey("cards.id"), nullable=False)
    reasons: Mapped[list] = mapped_column(JSON, nullable=False)
    source_excerpts: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    card: Mapped[Card] = relationship(back_populates="review_items")


class FilteredOutAudit(Base):
    __tablename__ = "filtered_out"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    candidate_article_id: Mapped[str] = mapped_column(String(36), nullable=False)
    comparison_article_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    shared_keywords_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reason: Mapped[str] = mapped_column(String(255), nullable=False, default="insufficient_keyword_overlap")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WorkerRun(Base):
    __tablename__ = "worker_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    provider: Mapped[str] = mapped_column(String(64), nullable=False, default="rss")
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    sources_polled: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    articles_ingested: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    credits_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    errors: Mapped[list | None] = mapped_column(JSON, nullable=True)
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)


class UserPreferences(Base):
    __tablename__ = "user_preferences"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    device_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    category_order: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

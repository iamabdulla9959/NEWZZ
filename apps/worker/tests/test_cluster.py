from unittest.mock import MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Article, Source, StoryCluster
from worker.cluster import (
    compute_vector_similarity,
    cluster_article,
    is_postgres,
    same_event,
)


def test_same_event_worded_differently_clusters():
    a = (
        "Example Corp will open a bicycle parts factory in Exampleville next June "
        "and plans to hire four hundred local workers at the new plant."
    )
    b = (
        "A new Example Corp plant in Exampleville is set for June. "
        "The bicycle-parts factory expects to hire 400 local workers."
    )
    assert same_event(a, b) is True


def test_unrelated_articles_do_not_cluster():
    a = "Example Corp will open a bicycle parts factory in Exampleville next June."
    b = "Heavy rain flooded the river park in North Exampleville over the weekend."
    assert same_event(a, b) is False


def test_sqlite_fallback_dialect_detection():
    """Explicitly verify that SQLite session uses fallback and does not invoke pgvector."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    # Dialect detection: SQLite must return is_postgres == False
    assert is_postgres(db) is False

    # Mocked Postgres dialect detection
    mock_db = MagicMock()
    mock_db.get_bind.return_value.dialect.name = "postgresql"
    assert is_postgres(mock_db) is True

    # Test compute_vector_similarity routes to sklearn on SQLite
    art1 = Article(
        id="a1",
        title="Mayor announces new city park opening next Monday",
        raw_text="The city mayor announced the park opening next Monday with free admission.",
    )
    art2 = Article(
        id="a2",
        title="City park opening next Monday announced by mayor",
        raw_text="The mayor of the city announced a new park opening on Monday.",
    )
    art3 = Article(
        id="a3",
        title="Stock markets tumble as interest rates spike unexpectedly",
        raw_text="Global financial markets declined sharply today following central bank statements.",
    )

    is_sim, sim = compute_vector_similarity(db, art1, art2)
    assert is_sim is True
    assert sim > 0.4

    is_sim_unrelated, sim_unrelated = compute_vector_similarity(db, art1, art3)
    assert is_sim_unrelated is False
    assert sim_unrelated < 0.2


def test_cluster_article_sqlite_fallback():
    """Verify cluster_article functions end-to-end on SQLite without Postgres/pgvector."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    source = Source(id="src-1", name="Local Herald", category="district", region="TN", trust_tier="2")
    cluster1 = StoryCluster(id="c1", title_hint="Flood warnings in district")
    art1 = Article(
        id="a1",
        source_id=source.id,
        url="https://example.com/1",
        title="Severe flood warnings issued across Chennai river basin",
        raw_text="Severe flood warnings issued across Chennai river basin as flood waters surge across river bridges.",
        category="district",
        state="TN",
        district="Chennai",
        published_at=now,
        ingested_at=now,
        cluster_id=cluster1.id,
    )
    db.add_all([source, cluster1, art1])
    db.commit()

    # Incoming similar article in same shard
    art2 = Article(
        id="a2",
        source_id=source.id,
        url="https://example.com/2",
        title="Severe flood warnings issued across Chennai river basin",
        raw_text="Flood warnings issued across Chennai river basin as flood waters surge across bridges in Chennai.",
        category="district",
        state="TN",
        district="Chennai",
        published_at=now,
        ingested_at=now,
    )
    db.add(art2)
    db.flush()

    matched_cluster, sharded, evaluated = cluster_article(db, art2)
    assert matched_cluster.id == cluster1.id
    assert sharded == 1
    assert evaluated == 1

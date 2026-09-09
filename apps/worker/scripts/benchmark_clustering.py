"""Benchmark script proving geographic sharding queries a filtered subset rather than full table."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
import sys

# Ensure utf-8 stdout on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "api")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db import Base
from app.models import Article, FilteredOutAudit, Source, StoryCluster, new_id
from worker.cluster import cluster_article


def run_benchmark() -> None:
    db_url = os.getenv("TEST_DATABASE_URL", os.getenv("DATABASE_URL", "sqlite:///:memory:"))
    engine = create_engine(db_url)
    dialect_name = engine.dialect.name
    print(f"Connecting to database ({dialect_name}): {db_url}")

    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    now = datetime.now(timezone.utc)

    # 1. Seed sources across categories & regions
    src_local = Source(id="src-local-1", name="Chennai Mail", category="district", region="Tamil Nadu", trust_tier="2")
    src_state = Source(id="src-state-1", name="TN Today", category="state", region="Tamil Nadu", trust_tier="2")
    src_national = Source(id="src-nat-1", name="India Express", category="national", region="IN", trust_tier="2")
    src_tech = Source(id="src-tech-1", name="Tech Pulse", category="tech", region=None, trust_tier="2")
    db.add_all([src_local, src_state, src_national, src_tech])
    db.flush()

    # 2. Seed 100 articles across dates, categories, and regions
    categories = ["tech", "national", "state", "district", "international", "science"]
    for i in range(100):
        cat = categories[i % len(categories)]
        cluster = StoryCluster(id=new_id(), title_hint=f"Cluster {i}", eligible=True)
        db.add(cluster)
        db.flush()

        # Specifically create 4 district Chennai articles published within last 24h
        if i < 4:
            cat = "district"
            district = "Chennai"
            state = "Tamil Nadu"
            pub_date = now - timedelta(hours=i + 1)
            if i == 0:
                # Matches >= 3 keywords with new article: "chennai", "civic", "upgrades", "intersections"
                title = "Chennai City Civic Upgrades And Metro Intersections Development"
            elif i == 1:
                title = "Chennai District Education Committee Releases Annual School Statistics"
            else:
                title = f"Chennai Harbor Vessel Arrivals Report For Day {i}"
        else:
            pub_date = now - timedelta(hours=28 + (i * 2))  # Older than 24h
            district = "Chennai" if (cat == "district" and i % 2 == 0) else ("Madurai" if cat == "district" else None)
            state = "Tamil Nadu" if cat in ("district", "state") else "Delhi"
            title = f"Sample News Story Headline Number {i} Concerning General Developments"

        # 768-dimensional mock embedding vector
        mock_embedding = [0.01 * ((i + k) % 10) for k in range(768)]

        art = Article(
            id=f"art-{i:03d}",
            source_id="src-local-1" if cat == "district" else "src-national",
            url=f"https://example.com/story-{i}",
            title=title,
            raw_text="Detailed text about urban developments and local roadway improvements.",
            category=cat,
            state=state,
            district=district,
            embedding=mock_embedding,
            published_at=pub_date,
            ingested_at=pub_date,
            cluster_id=cluster.id,
        )
        db.add(art)
    db.commit()

    total_table_rows = db.query(Article).count()
    print(f"\n================ CLUSTERING SHARDING BENCHMARK ================")
    print(f"Total articles in database (full table): {total_table_rows}")

    # 3. Create a new incoming article for Chennai district
    new_article = Article(
        id="new-incoming-01",
        source_id="src-local-1",
        url="https://example.com/new-chennai-story",
        title="Chennai City Civic Upgrades Commencing Across Key Urban Intersections",
        raw_text="The corporation has initiated municipal works and urban roadway upgrades.",
        category="district",
        state="Tamil Nadu",
        district="Chennai",
        embedding=[0.01 * (k % 10) for k in range(768)],
        published_at=now,
        ingested_at=now,
    )
    db.add(new_article)
    db.flush()

    # 4. Cluster using geographic sharding + keyword pre-filter
    cluster, sharded_count, vector_evaluated = cluster_article(db, new_article, log_filtered=True)
    db.commit()

    filtered_out_records = db.query(FilteredOutAudit).filter(FilteredOutAudit.candidate_article_id == new_article.id).all()

    sharding_reduction = ((total_table_rows - sharded_count) / total_table_rows) * 100
    vector_eval_reduction = ((total_table_rows - vector_evaluated) / total_table_rows) * 100

    print(f"Candidates queried via (category, state, district, 24h) sharding: {sharded_count}")
    print(f"Candidates passing keyword pre-filter (>= 3 title keywords): {vector_evaluated}")
    print(f"Dropped non-matches logged to 'filtered_out' audit table: {len(filtered_out_records)}")
    print(f"DB Query Sharding Reduction: {sharding_reduction:.2f}% (queried {sharded_count} of {total_table_rows} rows)")
    print(f"Vector Similarity Computation Reduction: {vector_eval_reduction:.2f}% (evaluated {vector_evaluated} of {total_table_rows} articles)")
    print(f"Assigned Cluster ID: {cluster.id}")
    print(f"===============================================================\n")

    # Assert DoD: Sharding only queries a filtered subset rather than full table
    assert sharded_count < total_table_rows, f"Expected sharded_count < {total_table_rows}, got {sharded_count}"
    assert sharded_count == 4, f"Expected exactly 4 candidates in matching shard within 24h, got {sharded_count}"
    assert vector_evaluated == 1, f"Expected exactly 1 candidate with >=3 keywords overlap, got {vector_evaluated}"
    assert len(filtered_out_records) == 3, f"Expected 3 dropped candidates logged to filtered_out, got {len(filtered_out_records)}"
    print("[PASS] Benchmark passed: Clustering only queries a filtered geographic/temporal subset!")


if __name__ == "__main__":
    run_benchmark()

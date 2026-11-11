import pytest
from worker.verify import (
    SourceRef,
    canonical_publisher_entity,
    _is_independent,
    count_independent_sources,
    is_publish_eligible,
    determine_verification_type,
)
from packages.ranking_engine.verification_engine import VerificationEngine


# 1. Two genuinely different publishers
def test_two_genuinely_different_publishers():
    s1 = SourceRef(source_id="1", trust_tier="1", name="The Hindu", text="ISRO launched a new earth observation satellite from Sriharikota on Wednesday.", url="https://thehindu.com/sci-tech/isro-launch")
    s2 = SourceRef(source_id="2", trust_tier="1", name="BBC World", text="India's space agency successfully placed a surveillance satellite into orbit from the southern spaceport.", url="https://bbc.com/news/world-asia-india-67890")

    assert _is_independent(s1, s2) is True
    groups = count_independent_sources([s1, s2])
    assert len(groups) == 2
    assert is_publish_eligible([s1, s2]) is True
    assert determine_verification_type([s1, s2]) == "cross_verified"


# 2. Two feeds from the same publisher
def test_two_feeds_from_same_publisher():
    s1 = SourceRef(source_id="1", trust_tier="1", name="The Hindu National", text="Prime Minister addresses the economic summit in New Delhi.", url="https://thehindu.com/news/national/story1")
    s2 = SourceRef(source_id="2", trust_tier="1", name="The Hindu Tamil Nadu", text="Prime Minister addresses the economic summit in New Delhi emphasizing regional development.", url="https://thehindu.com/news/national/tamil-nadu/story2")

    assert _is_independent(s1, s2) is False
    groups = count_independent_sources([s1, s2])
    assert len(groups) == 1
    assert is_publish_eligible([s1, s2]) is False
    assert determine_verification_type([s1, s2]) == "single_source"


# 3. Two different URLs from the same original story
def test_two_different_urls_from_same_original_story():
    s1 = SourceRef(source_id="1", trust_tier="1", name="BBC Technology", text="Tech giant announces new quantum computing breakthrough with 1000 qubits.", url="https://www.bbc.com/news/technology-12345")
    s2 = SourceRef(source_id="2", trust_tier="1", name="BBC News", text="Tech giant announces new quantum computing breakthrough with 1000 qubits.", url="https://www.bbc.co.uk/news/technology-12345?ref=mobile")

    assert _is_independent(s1, s2) is False
    groups = count_independent_sources([s1, s2])
    assert len(groups) == 1
    assert is_publish_eligible([s1, s2]) is False


# 4. Syndicated copies of the same wire article
def test_syndicated_copies_of_same_wire_article():
    # Two distinct newspaper sites republishing the exact same PTI wire story
    wire_text = "PTI - The Supreme Court of India on Monday agreed to hear the urgent plea regarding environmental regulations in the capital region."
    s1 = SourceRef(source_id="1", trust_tier="2", name="Outlook India", wire_attribution="PTI", text=wire_text, url="https://outlookindia.com/national/sc-hearing")
    s2 = SourceRef(source_id="2", trust_tier="2", name="Deccan Herald", wire_attribution="PTI", text=wire_text, url="https://deccanherald.com/national/sc-hearing")

    assert _is_independent(s1, s2) is False
    groups = count_independent_sources([s1, s2])
    assert len(groups) == 1
    assert is_publish_eligible([s1, s2]) is False


# 5. Unknown publisher identity
def test_unknown_publisher_identity():
    s1 = SourceRef(source_id="1", trust_tier="2", name="", text="Random blog post about local traffic event.", url="")
    s2 = SourceRef(source_id="2", trust_tier="1", name="The Hindu", text="Traffic updates for downtown boulevard.", url="https://thehindu.com/news")

    assert canonical_publisher_entity(s1.name, s1.url) == "unknown"
    assert _is_independent(s1, s2) is False
    assert is_publish_eligible([s1, s2]) is False


# 6. Unresolved sentinel citations
def test_unresolved_sentinel_citations():
    s1 = SourceRef(source_id="1", trust_tier="unresolved", name="Legacy Unresolved Provenance", text="Historical text from 2024 with no verified publisher.", url="https://news.google.com/rss/articles/CBMi...")
    s2 = SourceRef(source_id="2", trust_tier="unresolved", name="Legacy Unresolved Provenance", text="Another historical snippet without origin.", url="https://news.google.com/rss/articles/CBMi...")

    assert canonical_publisher_entity(s1.name, s1.url) == "unresolved"
    assert _is_independent(s1, s2) is False
    groups = count_independent_sources([s1, s2])
    assert len(groups) == 0  # Sentinel citations are filtered out from forming valid groups
    assert is_publish_eligible([s1, s2]) is False

    # Ranking engine evaluation ignores unresolved sources
    score, meta = VerificationEngine.calculate_verification([
        {"name": "Legacy Unresolved Provenance", "trust_tier": "unresolved", "url": s1.url},
        {"name": "Legacy Unresolved Provenance", "trust_tier": "unresolved", "url": s2.url},
    ])
    assert meta["independent_source_count"] == 0
    assert meta["status"] == "single_unconfirmed_source"


# 7. Genuinely multi-source event
def test_genuinely_multi_source_event():
    s1 = SourceRef(source_id="1", trust_tier="1", name="The Hindu", text="Finance Minister presents the union budget outlining key infrastructure allocations.", url="https://thehindu.com/business/budget")
    s2 = SourceRef(source_id="2", trust_tier="1", name="Reuters", text="India unveils economic plan focusing on capital expenditure and manufacturing incentives.", url="https://reuters.com/world/india/budget-plan")
    s3 = SourceRef(source_id="3", trust_tier="2", name="NDTV", text="Markets rally following the budget speech with major gains in railways and tech sectors.", url="https://ndtv.com/business/market-rally")

    groups = count_independent_sources([s1, s2, s3])
    assert len(groups) == 3
    assert is_publish_eligible([s1, s2, s3]) is True
    assert determine_verification_type([s1, s2, s3]) == "cross_verified"

    score, meta = VerificationEngine.calculate_verification([
        {"name": "The Hindu", "trust_tier": "1", "url": s1.url},
        {"name": "Reuters", "trust_tier": "1", "url": s2.url},
        {"name": "NDTV", "trust_tier": "2", "url": s3.url},
    ])
    assert meta["independent_source_count"] == 3
    assert meta["tier1_source_count"] >= 2
    assert meta["status"] == "cross_verified_tier1"
    assert score >= 95.0

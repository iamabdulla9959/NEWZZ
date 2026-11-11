import pytest
import httpx
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.models import Article, Card, CardSource, ReviewQueueItem, Source, StoryCluster, WorkerRun, new_id
from worker.ingest import ingest_rss_source
from worker.pipeline import cluster_unassigned_articles, evaluate_cluster, process_eligible_clusters
from worker.main import run_rss_once


VALID_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>The Hindu</title>
    <item>
      <title>ISRO launches new earth observation satellite from Sriharikota</title>
      <link>https://www.thehindu.com/sci-tech/science/isro-satellite-launch-2026</link>
      <description>The Indian Space Research Organisation successfully placed the EOS satellite in orbit.</description>
      <pubDate>Thu, 15 Oct 2026 09:30:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""

CORROBORATING_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>BBC Technology</title>
    <item>
      <title>ISRO satellite launch succeeds from Sriharikota spaceport</title>
      <link>https://www.bbc.co.uk/news/science-isro-launch-2026</link>
      <description>India space agency ISRO successfully launches new earth observation satellite.</description>
      <pubDate>Thu, 15 Oct 2026 09:45:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""

MALFORMED_RSS = """<html><head><title>502 Bad Gateway</title></head><body>Unclosed broken HTML"""

EMPTY_DESC_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Wire News</title>
    <item>
      <title>President signs landmark environmental accord</title>
      <link>https://wire.example.invalid/president-signs-accord</link>
    </item>
  </channel>
</rss>
"""


class MockTransport(httpx.BaseTransport):
    def __init__(self, routes: dict[str, tuple[int, bytes]]):
        self.routes = routes

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        for pattern, (status, content) in self.routes.items():
            if pattern in url_str:
                return httpx.Response(status, content=content)
        return httpx.Response(404, content=b"Not found")


# 1. Valid RSS source
def test_recovery_valid_rss_source(db: Session):
    src = Source(id=new_id(), name="The Hindu", category="science", rss_url="https://thehindu.example/rss.xml", trust_tier="1", is_active=True)
    db.add(src)
    db.commit()

    transport = MockTransport({"https://thehindu.example/rss.xml": (200, VALID_RSS.encode("utf-8"))})
    with httpx.Client(transport=transport) as client:
        created = ingest_rss_source(db, src, client=client)
    assert created == 1
    art = db.query(Article).filter(Article.url == "https://www.thehindu.com/sci-tech/science/isro-satellite-launch-2026").first()
    assert art is not None
    assert "ISRO" in art.title
    assert "satellite" in art.raw_text


# 2. Malformed RSS response
def test_recovery_malformed_rss_response(db: Session):
    src = Source(id=new_id(), name="Broken Source", category="national", rss_url="https://broken.example/rss.xml", trust_tier="2", is_active=True)
    db.add(src)
    db.commit()

    transport = MockTransport({"https://broken.example/rss.xml": (200, MALFORMED_RSS.encode("utf-8"))})
    with httpx.Client(transport=transport) as client:
        created = ingest_rss_source(db, src, client=client)
    assert created == 0


# 3. Duplicate article URL
def test_recovery_duplicate_article_url(db: Session):
    src = Source(id=new_id(), name="The Hindu", category="science", rss_url="https://thehindu.example/rss.xml", trust_tier="1", is_active=True)
    db.add(src)
    db.commit()

    transport = MockTransport({"https://thehindu.example/rss.xml": (200, VALID_RSS.encode("utf-8"))})
    with httpx.Client(transport=transport) as client:
        pass1 = ingest_rss_source(db, src, client=client)
        pass2 = ingest_rss_source(db, src, client=client)
    assert pass1 == 1
    assert pass2 == 0
    assert db.query(Article).filter(Article.url == "https://www.thehindu.com/sci-tech/science/isro-satellite-launch-2026").count() == 1


# 4. Missing article content handled without fabrication
def test_recovery_missing_article_content(db: Session):
    src = Source(id=new_id(), name="Wire News", category="environment", rss_url="https://wire.example/rss.xml", trust_tier="2", is_active=True)
    db.add(src)
    db.commit()

    transport = MockTransport({
        "https://wire.example/rss.xml": (200, EMPTY_DESC_RSS.encode("utf-8")),
        "https://wire.example.invalid/president-signs-accord": (404, b"Not found"),
    })
    with httpx.Client(transport=transport) as client:
        created = ingest_rss_source(db, src, client=client)
    assert created == 1
    art = db.query(Article).filter(Article.url == "https://wire.example.invalid/president-signs-accord").first()
    assert art is not None
    assert art.raw_text == ""


# 5. Multiple reports describing one event clustered together
def test_recovery_multiple_reports_describing_one_event(db: Session):
    s1 = Source(id=new_id(), name="The Hindu", category="science", rss_url="https://thehindu.example/rss.xml", trust_tier="1", is_active=True)
    s2 = Source(id=new_id(), name="BBC", category="science", rss_url="https://bbc.example/rss.xml", trust_tier="1", is_active=True)
    db.add_all([s1, s2])
    db.commit()

    transport = MockTransport({
        "https://thehindu.example/rss.xml": (200, VALID_RSS.encode("utf-8")),
        "https://bbc.example/rss.xml": (200, CORROBORATING_RSS.encode("utf-8")),
    })
    with httpx.Client(transport=transport) as client:
        ingest_rss_source(db, s1, client=client)
        ingest_rss_source(db, s2, client=client)

    assigned = cluster_unassigned_articles(db)
    assert assigned == 2
    arts = db.query(Article).all()
    assert arts[0].cluster_id is not None
    assert arts[0].cluster_id == arts[1].cluster_id


# 6. Publisher attribution failure remains explicitly isolated
def test_recovery_publisher_attribution_failure(db: Session):
    unknown_src = Source(id=new_id(), name="Unregistered Scraped Blog", category="technology", rss_url="https://unknown.example/rss.xml", trust_tier="3", is_active=True)
    db.add(unknown_src)
    db.commit()

    RSS_UNKNOWN = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Unknown</title>
<item><title>Leaked Hardware Specs Online</title><link>https://unknown.example/specs</link><description>Specs leak.</description></item>
</channel></rss>"""

    transport = MockTransport({"https://unknown.example/rss.xml": (200, RSS_UNKNOWN.encode("utf-8"))})
    with httpx.Client(transport=transport) as client:
        created = ingest_rss_source(db, unknown_src, client=client)
    assert created == 1
    art = db.query(Article).filter(Article.url == "https://unknown.example/specs").first()
    assert art.source.trust_tier == "3"


# 7. LLM provider unavailable -> fail closed to review_queue, never publish unverified
def test_recovery_llm_provider_unavailable(db: Session):
    clust = StoryCluster(id=new_id(), title_hint="Launch Cluster", eligible=True)
    src = Source(id=new_id(), name="The Hindu", category="science", trust_tier="1", is_active=True)
    art = Article(id=new_id(), source_id=src.id, cluster_id=clust.id, url="https://example.com/1", title="Satellite in Orbit", raw_text="Observation satellite launched.")
    db.add_all([clust, src, art])
    db.commit()

    class FailingLLM:
        def complete_text(self, system_prompt, user_prompt):
            raise ConnectionError("LLM API service unavailable")

        def complete_json(self, system_prompt, user_prompt, schema=None):
            raise ConnectionError("LLM API service unavailable")

    produced = process_eligible_clusters(db, FailingLLM())
    assert len(produced) == 1
    card = db.query(Card).filter(Card.cluster_id == clust.id).first()
    assert card is not None
    assert card.verified_status == "pending_review"  # Never published
    rq = db.query(ReviewQueueItem).filter(ReviewQueueItem.card_id == card.id).first()
    assert rq is not None
    assert any("summarize_error" in r for r in rq.reasons)


# 8. Factual judge rejection -> routes to review_queue
def test_recovery_factual_judge_rejection(db: Session):
    clust = StoryCluster(id=new_id(), title_hint="Election Cluster", eligible=True)
    src = Source(id=new_id(), name="PTI", category="politics", trust_tier="1", is_active=True)
    art = Article(id=new_id(), source_id=src.id, cluster_id=clust.id, url="https://example.com/election", title="Election Date Announced", raw_text="Election Commission announces voting on Nov 10.")
    db.add_all([clust, src, art])
    db.commit()

    summary_text = (
        "Example Corp opened a bicycle-parts manufacturing plant in Exampleville on Monday, marking a "
        "significant milestone for the region's industrial base. The company said the new facility will "
        "produce aluminum frames, precision wheels, and specialty gear components for domestic distribution. "
        "The plant is expected to hire 400 full-time workers during the current year, with phased onboarding "
        "across production, logistics, and administrative roles. Workers will complete structured training "
        "programs before the first production shift begins in June, according to official company statements. "
        "The plant represents a notable addition to the local economy in Exampleville, which had experienced "
        "a sustained decline in manufacturing employment over the previous decade. Local officials welcomed "
        "the investment. The mayor confirmed the municipality had negotiated with Example Corp for 18 months "
        "to secure the site, finalizing terms that include tax incentives and infrastructure upgrades such as "
        "road access improvements and expanded utility capacity. Example Corp's chief executive stated that "
        "the Exampleville site is the company's fourth North American manufacturing facility. The company "
        "declined to disclose the total capital investment figure or a complete production capacity timetable. "
        "Officials from the regional employment office confirmed that job applications are expected to open "
        "in April, and the company will host community job fairs ahead of formal hiring."
    )

    class SequencedLLM:
        def __init__(self):
            self.calls = 0

        def complete_json(self, system_prompt, user_prompt, schema=None):
            self.calls += 1
            if self.calls == 1:
                return {
                    "headline": "Election Announced",
                    "summary": summary_text,
                    "category": "national",
                    "priority_score": 7,
                    "content_type": "NEWS",
                    "key_facts": ["Voting on Nov 10", "500 reported casualties in peaceful state."],
                    "conflicts": [],
                }
            return {
                "consistent": False,
                "issues": ["Invented casualty count of 500 deaths"],
            }

    produced = process_eligible_clusters(db, SequencedLLM())
    assert len(produced) == 1
    card = db.query(Card).filter(Card.cluster_id == clust.id).first()
    assert card.verified_status == "pending_review"
    rq = db.query(ReviewQueueItem).filter(ReviewQueueItem.card_id == card.id).first()
    assert rq is not None
    assert any("Invented casualty count" in r for r in rq.reasons)


# 9. Database transaction failure leaves no partial records
def test_recovery_database_transaction_failure(db: Session):
    initial_articles = db.query(Article).count()
    try:
        art = Article(id=new_id(), source_id=None, url="https://fail.example/1", title="Fail Art", raw_text="Fail")
        db.add(art)
        db.flush()
        raise RuntimeError("Simulated mid-pipeline DB crash")
    except Exception:
        db.rollback()

    assert db.query(Article).count() == initial_articles


# 10. Worker restart is idempotent
def test_recovery_worker_restart_idempotency(db: Session):
    # Two independent sources to meet the 2-source eligibility requirement for publication
    s1 = Source(id=new_id(), name="The Hindu", category="science", rss_url="https://thehindu.example/rss.xml", trust_tier="1", is_active=True)
    s2 = Source(id=new_id(), name="BBC", category="science", rss_url="https://bbc.example/rss.xml", trust_tier="1", is_active=True)
    db.add_all([s1, s2])
    db.commit()

    transport = MockTransport({
        "https://thehindu.example/rss.xml": (200, VALID_RSS.encode("utf-8")),
        "https://bbc.example/rss.xml": (200, CORROBORATING_RSS.encode("utf-8")),
    })

    class CleanLLM:
        def complete_json(self, system_prompt, user_prompt, schema=None):
            return {
                "headline": "ISRO Satellite In Orbit",
                "summary": "ISRO launched an earth observation satellite into orbit successfully.",
                "category": "Science",
                "priority_score": 8,
                "content_type": "NEWS",
            }

        def complete_text(self, system_prompt, user_prompt):
            return '{"consistent": true, "issues": []}'

    llm = CleanLLM()

    # Pass 1: Fresh run
    with httpx.Client(transport=transport) as client:
        run_rss_once(llm=llm, http_client=client)

    articles_count_1 = db.query(Article).count()
    cards_count_1 = db.query(Card).count()
    runs_count_1 = db.query(WorkerRun).count()
    assert articles_count_1 == 2
    assert cards_count_1 == 1
    assert runs_count_1 == 1

    # Pass 2: Worker restarts and runs on the exact same feed
    with httpx.Client(transport=transport) as client:
        run_rss_once(llm=llm, http_client=client)

    articles_count_2 = db.query(Article).count()
    cards_count_2 = db.query(Card).count()
    runs_count_2 = db.query(WorkerRun).count()

    # Total articles and cards must remain identical; only WorkerRun increments
    assert articles_count_2 == articles_count_1
    assert cards_count_2 == cards_count_1
    assert runs_count_2 == runs_count_1 + 1

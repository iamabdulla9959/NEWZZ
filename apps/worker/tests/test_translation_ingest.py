from __future__ import annotations

from unittest.mock import MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Article, Source
from worker.ingest import ingest_rss_source, process_and_translate_text


def test_process_and_translate_vernacular_text():
    """DoD: Running translation against vernacular text produces original_text (native) and translated_text (English)."""
    hindi_title = "दिल्ली इमारत हादसे का सच: तंग गलियां और राहत कार्य"
    hindi_body = "दिल्ली के शास्त्री पार्क इलाके में एक इमारत गिरने से राहत और बचाव कार्य शुरू किया गया है।"

    mock_llm = MagicMock()
    mock_llm.complete_text.return_value = (
        "Delhi Building Collapse Reality: Narrow alleys and rescue operations. "
        "Rescue and relief operations have commenced in Delhi's Shastri Park area after a building collapsed."
    )

    raw_clustering, original_text, lang, conf = process_and_translate_text(
        title=hindi_title,
        raw_text=hindi_body,
        llm=mock_llm,
    )

    assert lang == "hi"
    assert conf > 0.5
    assert original_text == hindi_body
    assert "Delhi Building Collapse Reality" in raw_clustering

    # Verify exact prompt was used
    call_args = mock_llm.complete_text.call_args[0]
    system_prompt = call_args[0]
    assert "Translate the following news article text from hi to English" in system_prompt
    assert "Preserve every fact, number, name, date, and quote exactly" in system_prompt
    assert "Do not summarize, do not omit anything, do not add interpretation" in system_prompt


def test_ingest_rss_source_vernacular_populates_both_texts():
    """DoD: Ingesting a vernacular feed stores both original_text and translated_text on Article."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    source = Source(
        id="src-amarujala",
        name="Amar Ujala Delhi",
        category="district",
        region="Delhi",
        rss_url="https://example.com/rss/delhi.xml",
        trust_tier="2",
        is_active=True,
    )
    db.add(source)
    db.commit()

    sample_rss_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <title>Amar Ujala</title>
        <item>
          <title><![CDATA[\xe0\xa4\xa6\xe0\xa4\xbf\xe0\xa4\xb2\xe0\xa4\x8c\xe0\xa4\xb2\xe0\xa5\x80 \xe0\xa4\xae\xe0\xa5\x87\xe0\xa4\x82 \xe0\xa4\xa8\xe0\xa4\xaf\xe0\xa4\xbe \xe0\xa4\xaa\xe0\xa5\x8d\xe0\xa4\xb0\xe0\xa5\x8b\xe0\xa4\x9c\xe0\xa5\x87\xe0\xa4\x95\xe0\xa5\x8d\xe0\xa4\x9f \xe0\xa4\xb6\xe0\xa5\x81\xe0\xa4\xb0\xe0\xa5\x82]]></title>
          <link>https://example.com/delhi-news-101</link>
          <description><![CDATA[\xe0\xa4\xb6\xe0\xa4\xb9\xe0\xa4\xb0 \xe0\xa4\x95\xe0\xa5\x87 \xe0\xa4\xb5\xe0\xa4\xbf\xe0\xa4\x95\xe0\xa4\xbe\xe0\xa4\xb8 \xe0\xa4\x95\xe0\xa5\x87 \xe0\xa4\xb2\xe0\xa4\xbf\xe0\xa4\x8f \xe0\xa4\xa8\xe0\xa4\x8f \xe0\xa4\x95\xe0\xa4\xbe\xe0\xa4\xb0\xe0\xa5\x8d\xe0\xa4\xaf \xe0\xa4\x95\xe0\xa5\x80 \xe0\xa4\x98\xe0\xa5\x8b\xe0\xa4\xb7\xe0\xa4\xa3\xe0\xa4\xbe \xe0\xa4\xb9\xe0\xa5\x81\xe0\xa4\x88\xe0\xa5\xa4]]></description>
          <pubDate>Mon, 07 Sep 2026 04:00:00 GMT</pubDate>
        </item>
      </channel>
    </rss>"""

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = sample_rss_xml
    mock_response.raise_for_status = MagicMock()
    mock_client.get.return_value = mock_response

    mock_llm = MagicMock()
    mock_llm.complete_text.return_value = (
        "New project launched in Delhi. Announcement of new public works for city development."
    )

    created = ingest_rss_source(db, source, client=mock_client, llm=mock_llm)
    assert created == 1

    art = db.query(Article).filter(Article.url == "https://example.com/delhi-news-101").first()
    assert art is not None
    assert art.original_text is not None and len(art.original_text) > 0
    assert art.translated_text is not None and len(art.translated_text) > 0
    assert art.original_language == "hi"
    assert "New project launched in Delhi" in art.translated_text
    assert art.raw_text == art.translated_text

import pytest

from worker.llm import parse_json_object
from worker.summarize import summarize_articles


class SequencedLLM:
    def __init__(self, payloads: list):
        self.payloads = list(payloads)
        self.calls = 0

    def complete_json(self, system: str, user: str):
        self.calls += 1
        item = self.payloads.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


VALID = {
    "headline": "Example Corp opens Exampleville plant",
    "summary": "Example Corp opened a bicycle parts plant in Exampleville. The plant will hire 400 people this year. City officials said the first shift starts in June.",
    "category": "national",
    "key_facts": ["Example Corp opened a plant in Exampleville", "400 hires planned"],
    "conflicts": [],
}


def test_parse_json_from_markdown_fence():
    raw = "```json\n{\"headline\": \"Example Corp plant\"}\n```"
    assert parse_json_object(raw)["headline"] == "Example Corp plant"


def test_summarize_returns_schema():
    llm = SequencedLLM([VALID])
    articles = [
        {
            "name": "Example Gazette",
            "title": "Example Corp plant",
            "url": "https://example.invalid/a",
            "text": "Example Corp opened a bicycle parts plant in Exampleville and will hire 400 people.",
        },
        {
            "name": "Example Herald",
            "title": "New factory in Exampleville",
            "url": "https://example.invalid/b",
            "text": "Example Corp said its Exampleville factory will hire 400 workers. First shift is in June.",
        },
    ]
    data = summarize_articles(llm, articles)
    assert set(data) >= {"headline", "summary", "category", "key_facts", "conflicts"}


def test_malformed_output_retried_then_succeeds():
    llm = SequencedLLM([ValueError("bad json"), VALID])
    data = summarize_articles(
        llm, [{"name": "Example Gazette", "title": "x", "url": "u", "text": "Example Corp opened a plant."}]
    )
    assert data["headline"] == VALID["headline"]
    assert llm.calls == 2


def test_malformed_output_retried_then_fails():
    llm = SequencedLLM([ValueError("bad json"), ValueError("still bad")])
    with pytest.raises(RuntimeError):
        summarize_articles(llm, [{"name": "Example Gazette", "title": "x", "url": "u", "text": "t"}])
    assert llm.calls == 2

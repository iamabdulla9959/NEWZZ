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


# VALID fixture uses a 200-250 word summary, matching the LLM prompt spec
VALID = {
    "headline": "Example Corp opens Exampleville plant",
    "summary": (
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
    ),
    "category": "national",
    "content_type": "NEWS",
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


def test_judge_fact_consistency_valid():
    from worker.summarize import judge_fact_consistency
    llm = SequencedLLM([{"consistent": True}])
    res = judge_fact_consistency(llm, "Valid summary", ["Valid source"])
    assert res["consistent"] is True
    assert res["issues"] == []


def test_judge_fact_consistency_invalid():
    from worker.summarize import judge_fact_consistency
    llm = SequencedLLM([{"consistent": False, "issues": ["invented names"]}])
    res = judge_fact_consistency(llm, "Invalid summary", ["Valid source"])
    assert res["consistent"] is False
    assert res["issues"] == ["invented names"]

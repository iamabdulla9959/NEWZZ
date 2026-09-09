from worker.summarize import judge_fact_consistency
from worker.validate import (
    check_banned_words,
    check_reading_level,
    check_word_count,
    run_rule_checks,
)

PASSING_SUMMARY = (
    "Example Corp opened a bicycle parts plant in Exampleville on Monday. "
    "The company said it will hire four hundred local workers this year. "
    "City officials said the first shift will start in June. "
    "Training for new hires begins next week at the site. "
    "The plant will make bicycle frames and wheels for regional shops."
)


class JudgeLLM:
    def __init__(self, payload=None, error=None):
        self.payload = payload
        self.error = error

    def complete_json(self, system: str, user: str):
        if self.error:
            raise self.error
        if self.payload is not None:
            return self.payload
        if "moon base" in user.lower():
            return {"consistent": False, "issues": ["unsupported moon base claim"]}
        return {"consistent": True, "issues": []}


def test_word_count_fails_independently():
    result = check_word_count("Example Corp opened a plant.")
    assert result.passed is False
    assert any(r.startswith("word_count:") for r in result.reasons)


def test_reading_level_fails_independently():
    dense = (
        "Notwithstanding the aforementioned conglomerate's multifaceted industrial diversification "
        "strategy, Example Corp contemporaneously operationalized an extraordinarily sophisticated "
        "manufacturing infrastructure utilizing unprecedented methodological implementations."
    )
    result = check_reading_level(dense)
    assert result.passed is False


def test_banned_words_fail_independently():
    result = check_banned_words(
        PASSING_SUMMARY.replace("opened", "opened a shocking")
    )
    assert result.passed is False
    assert any("banned_words" in r for r in result.reasons)


def test_all_rule_checks_pass_together():
    result = run_rule_checks(PASSING_SUMMARY)
    assert result.passed, result.reasons


def test_hallucinated_summary_caught_by_judge():
    hallucinated = PASSING_SUMMARY + " Example Corp also built a moon base."
    verdict = judge_fact_consistency(
        JudgeLLM(),
        hallucinated,
        ["Example Corp opened a bicycle parts plant in Exampleville and will hire 400 workers."],
    )
    assert verdict["consistent"] is False


def test_judge_error_fails_closed():
    verdict = judge_fact_consistency(
        JudgeLLM(error=RuntimeError("timeout")),
        PASSING_SUMMARY,
        ["Example Corp opened a plant in Exampleville."],
    )
    assert verdict["consistent"] is False
    assert verdict["issues"]

from worker.summarize import judge_fact_consistency
from worker.validate import (
    check_banned_words,
    check_reading_level,
    check_word_count,
    run_rule_checks,
)

PASSING_SUMMARY = (
    "Example Corp opened a new bicycle center in the town on Monday. "
    "The company said the center will build bikes and parts for local riders. "
    "It will also repair older bikes for students and daily workers across the area. "
    "The team plans to hire fifty workers from the town during the coming year. "
    "Workers will finish job training before plant work begins next month. "
    "The district officer visited the site and met with factory workers and staff. "
    "He said the new center brings welcome jobs and supports green travel for families. "
    "Local families attended the opening event and walked through the building. "
    "Company leaders handed out free safety gear to students from local schools. "
    "Members of the town board confirmed that road access was updated for the site. "
    "The company plans to build two smaller branch shops in nearby towns next spring. "
    "These efforts aim to make cycling safe and popular for people across the district. "
    "Free road safety classes will take place every weekend in town parks. "
    "School teachers said young students are eager to learn how to ride safely on roads. "
    "The center will also offer repair discounts to workers who ride to their jobs."
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


def test_reel_summary_word_limit_is_180_to_260_words():
    exactly_180 = " ".join(["fact"] * 180)
    too_long = " ".join(["fact"] * 261)

    assert check_word_count(exactly_180).passed is True
    assert check_word_count(too_long).passed is False


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

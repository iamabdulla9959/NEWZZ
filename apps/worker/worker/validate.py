from __future__ import annotations

import re
from dataclasses import dataclass

import textstat

BANNED_OPINION_WORDS = {
    "shocking",
    "devastating",
    "slammed",
    "blasted",
    "hero",
    "disaster",
    "outrageous",
    "appalling",
    "miracle",
    "chaotic",
}

SENSITIVITY_KEYWORDS = {
    "killed",
    "death",
    "deaths",
    "dead",
    "riot",
    "unrest",
    "massacre",
    "outbreak",
    "epidemic",
    "election",
    "elections",
    "suicide",
    "explosion",
    "bomb",
}

MIN_WORDS = 180
MAX_WORDS = 260
MIN_SENTENCES = 7
MAX_SENTENCES = 20
MIN_GRADE = 5.0
MAX_GRADE = 10.0


@dataclass
class ValidationResult:
    passed: bool
    reasons: list[str]


def word_count(text: str) -> int:
    return len(re.findall(r"\b[\w']+\b", text or ""))


def sentence_count(text: str) -> int:
    parts = [p for p in re.split(r"[.!?]+", text or "") if p.strip()]
    return len(parts)


def check_word_count(summary: str) -> ValidationResult:
    n = word_count(summary)
    if n < MIN_WORDS or n > MAX_WORDS:
        return ValidationResult(False, [f"word_count:{n}"])
    return ValidationResult(True, [])


def check_sentence_count(summary: str) -> ValidationResult:
    n = sentence_count(summary)
    if n < MIN_SENTENCES or n > MAX_SENTENCES:
        return ValidationResult(False, [f"sentence_count:{n}"])
    return ValidationResult(True, [])


def check_reading_level(summary: str) -> ValidationResult:
    grade = float(getattr(textstat, "flesch_kincaid_grade", textstat.textstat.flesch_kincaid_grade)(summary))
    if grade < MIN_GRADE or grade > MAX_GRADE:
        return ValidationResult(False, [f"reading_level:{grade}"])
    return ValidationResult(True, [])


def check_banned_words(summary: str) -> ValidationResult:
    tokens = set(re.findall(r"[a-z']+", (summary or "").lower()))
    hit = sorted(tokens & BANNED_OPINION_WORDS)
    if hit:
        return ValidationResult(False, [f"banned_words:{','.join(hit)}"])
    return ValidationResult(True, [])


def matches_sensitivity(text: str) -> bool:
    tokens = set(re.findall(r"[a-z']+", (text or "").lower()))
    return bool(tokens & SENSITIVITY_KEYWORDS)


def run_rule_checks(summary: str) -> ValidationResult:
    reasons: list[str] = []
    for check in (check_word_count, check_sentence_count, check_reading_level, check_banned_words):
        result = check(summary)
        reasons.extend(result.reasons)
    return ValidationResult(passed=not reasons, reasons=reasons)

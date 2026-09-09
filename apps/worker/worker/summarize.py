from __future__ import annotations

from typing import Any

from worker.llm import JUDGE_SYSTEM_PROMPT, LLMClient, SUMMARIZER_SYSTEM_PROMPT

REQUIRED_FIELDS = {"headline", "summary", "category", "key_facts", "conflicts"}


def summarize_articles(
    llm: LLMClient,
    articles: list[dict[str, str]],
    category_hint: str = "national",
) -> dict[str, Any]:
    user = "Category hint: {hint}\n\nSources:\n".format(hint=category_hint)
    for i, art in enumerate(articles, start=1):
        user += (
            f"\n--- SOURCE {i}: {art.get('name', 'Unknown')} ---\n"
            f"TITLE: {art.get('title', '')}\n"
            f"URL: {art.get('url', '')}\n"
            f"TEXT:\n{art.get('text', '')[:4000]}\n"
        )
    last_error: Exception | None = None
    for _ in range(2):
        try:
            data = llm.complete_json(SUMMARIZER_SYSTEM_PROMPT, user)
            missing = REQUIRED_FIELDS - set(data)
            if missing:
                raise ValueError(f"summary JSON missing fields: {sorted(missing)}")
            return data
        except Exception as exc:  # retry once, then fail to review queue
            last_error = exc
    raise RuntimeError(f"summarization failed after retry: {last_error}") from last_error


def judge_fact_consistency(
    llm: LLMClient,
    summary: str,
    source_texts: list[str],
) -> dict[str, Any]:
    user = f"SUMMARY:\n{summary}\n\nSOURCES:\n" + "\n---\n".join(source_texts)
    try:
        data = llm.complete_json(JUDGE_SYSTEM_PROMPT, user)
    except Exception as exc:  # fail closed
        return {"consistent": False, "issues": [f"judge_error:{exc}"]}
    consistent = bool(data.get("consistent") is True)
    issues = data.get("issues") or []
    if not isinstance(issues, list):
        issues = [str(issues)]
    return {"consistent": consistent, "issues": issues}

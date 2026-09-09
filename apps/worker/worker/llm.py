from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Protocol

# pyrefly: ignore [missing-import]
from openai import OpenAI


logger = logging.getLogger("newsreels.llm")

SUMMARIZER_SYSTEM_PROMPT = """You are a news summarizer for News Reels. Output ONLY valid JSON matching this schema:
{
  "headline": "string, at most 10 words, factual, no clickbait",
  "summary": "string, 1 short hook, 2-4 sentences of context, 1 sentence explaining why it matters. Target roughly 70-100 words",
  "category": "district|state|national|international|tech|science",
  "priority_score": "int, 1-10 rating of global/national importance or human impact",
  "key_facts": ["short factual bullets drawn only from sources"],
  "conflicts": ["descriptions of numeric or factual disagreements, or empty"]
}

Rules:
- Reading level: 8th grade. Engaging narrative style, but purely factual. Provide rich context to keep the reader interested.
- Content Quality: If the text is a newsletter, generic product page, opinion piece, or promotional content, set priority_score to 1. Extract the core factual event if one exists. Do NOT summarize promotional boilerplate.
- Do NOT repeat the headline in the first line of the summary.
- Do NOT include boilerplate source attributions like "Further details and verified reports are being monitored by [Source]" or "According to reports". Just state the facts.
- The summary MUST follow a strict 3-part narrative flow:
  1. The Hook (1 short sentence): Draw the reader in immediately with the most interesting, impactful aspect of the event.
  2. Key Context (2-4 sentences): Provide crucial background, specific details, and numbers to give depth to the story.
  3. The Impact (1 sentence): Explain why this matters, what happens next, or the broader consequences.
- No opinion language (do not use: allegedly without attribution, shocking, devastating, slammed, blasted, hero, disaster unless quoting a source name+claim).
- No unsupported claims. Every sentence must be backed by the provided source texts.
- If sources disagree on a number by more than 20%, do not pick a number. Write: "Reports differ on <topic>."
- Do not copy source sentences verbatim. Paraphrase facts only.
- Do not invent names, figures, dates, or quotes.
"""

JUDGE_SYSTEM_PROMPT = """You are a fact-consistency judge for News Reels. Compare a summary to source texts.
Output ONLY JSON: {"consistent": true or false, "issues": ["..."]}
Mark consistent=false if the summary invents facts, numbers, names, or claims not supported by sources.
"""

TRANSLATION_SYSTEM_PROMPT_TEMPLATE = """Translate the following news article text from {source_language} to English. Preserve every fact, number, name, date, and quote exactly. Do not summarize, do not omit anything, do not add interpretation. If a term has no exact English equivalent, translate literally and add a short bracketed clarification. Output only the translated text, nothing else."""


class LLMClient(Protocol):
    def complete_json(self, system: str, user: str) -> dict[str, Any]:
        ...

    def complete_text(self, system: str, user: str) -> str:
        ...


class LLMProvider:
    def __init__(self, name: str, api_key: str, base_url: str, model: str, client: OpenAI | None = None) -> None:
        self.name = name
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        default_headers = {}
        if name == "openrouter":
            default_headers = {"HTTP-Referer": "https://github.com/news-reels", "X-Title": "News Reels"}
        self._client = client or (OpenAI(api_key=api_key, base_url=base_url, default_headers=default_headers, timeout=30.0) if api_key else None)

    def complete_text(self, system: str, user: str) -> str:
        if not self._client:
            raise RuntimeError(f"Provider {self.name} client not configured (missing API key)")
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0,
        )
        return (response.choices[0].message.content or "").strip()

    def generate_embedding(self, text: str) -> list[float]:
        if not self._client:
            raise RuntimeError(f"Provider {self.name} client not configured (missing API key)")
        embedding_model = os.getenv("EMBEDDING_MODEL", "text-embedding-004")
        response = self._client.embeddings.create(
            model=embedding_model,
            input=text,
        )
        return response.data[0].embedding


class MultiProviderClient:
    """Multi-provider LLM client with automatic fallback:
    Gemini -> Groq -> OpenRouter.
    Logs which provider actually served each request.
    """

    def __init__(self, providers: list[LLMProvider] | None = None) -> None:
        self.last_served_provider: str | None = None

        if providers is not None:
            self.providers = providers
        else:
            default_key = os.getenv("LLM_API_KEY", "").strip()
            gemini_key = os.getenv("GEMINI_API_KEY", default_key).strip()
            groq_key = os.getenv("GROQ_API_KEY", "").strip()
            openrouter_key = os.getenv("OPENROUTER_API_KEY", "").strip()

            providers_list: list[LLMProvider] = []
            # Free tier primary: Groq (high throughput, no credit card required)
            if groq_key:
                providers_list.append(
                    LLMProvider(
                        name="groq",
                        api_key=groq_key,
                        base_url=os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
                        model=os.getenv("GROQ_MODEL", "openai/gpt-oss-20b"),
                    )
                )
            if gemini_key:
                providers_list.append(
                    LLMProvider(
                        name="gemini",
                        api_key=gemini_key,
                        base_url=os.getenv("GEMINI_BASE_URL", os.getenv("LLM_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")),
                        model=os.getenv("GEMINI_MODEL", os.getenv("LLM_MODEL", "gemini-3.6-flash")),
                    )
                )
            if openrouter_key:
                providers_list.append(
                    LLMProvider(
                        name="openrouter",
                        api_key=openrouter_key,
                        base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
                        model=os.getenv("OPENROUTER_MODEL", "nvidia/nemotron-3.5-lightning:free"),
                    )
                )
            self.providers = providers_list

    def _extract_retry_delay(self, err_text: str, default: float = 2.0) -> float:
        import re
        m1 = re.search(r"retry\s+in\s+([\d\.]+)", err_text, re.IGNORECASE)
        if m1:
            try:
                return min(float(m1.group(1)) + 1.5, 60.0)
            except Exception:
                pass
        m2 = re.search(r"retrydelay':\s*'(\d+)s'", err_text, re.IGNORECASE)
        if m2:
            try:
                return min(float(m2.group(1)) + 1.5, 60.0)
            except Exception:
                pass
        return default

    def complete_text(self, system: str, user: str) -> str:
        errors: list[str] = []
        for provider in self.providers:
            for attempt in range(2):
                try:
                    result = provider.complete_text(system, user)
                    self.last_served_provider = provider.name
                    logger.info("LLM text completion served by provider: %s", provider.name)
                    return result
                except Exception as exc:
                    err_msg = str(exc).lower()
                    if ("429" in err_msg or "quota" in err_msg or "rate" in err_msg or "resource_exhausted" in err_msg) and attempt == 0:
                        delay = self._extract_retry_delay(str(exc), default=2.0)
                        logger.warning("Provider %s rate-limited (429), retrying in %.1fs...", provider.name, delay)
                        time.sleep(delay)
                        continue
                    errors.append(f"{provider.name}: {exc}")
                    logger.warning("Provider %s failed, falling back: %s", provider.name, exc)
                    break
        raise RuntimeError(f"All LLM providers failed: {'; '.join(errors)}")

    def complete_json(self, system: str, user: str) -> dict[str, Any]:
        errors: list[str] = []
        for provider in self.providers:
            for attempt in range(2):
                try:
                    raw = provider.complete_text(system, user)
                    parsed = parse_json_object(raw)
                    self.last_served_provider = provider.name
                    logger.info("LLM JSON completion served by provider: %s", provider.name)
                    return parsed
                except Exception as exc:
                    err_msg = str(exc).lower()
                    if ("429" in err_msg or "quota" in err_msg or "rate" in err_msg or "resource_exhausted" in err_msg) and attempt == 0:
                        delay = self._extract_retry_delay(str(exc), default=2.0)
                        logger.warning("Provider %s rate-limited (429), retrying in %.1fs...", provider.name, delay)
                        time.sleep(delay)
                        continue
                    errors.append(f"{provider.name}: {exc}")
                    logger.warning("Provider %s failed, falling back: %s", provider.name, exc)
                    break
        raise RuntimeError(f"All LLM providers failed: {'; '.join(errors)}")


    def generate_embedding(self, text: str) -> list[float]:
        errors: list[str] = []
        for provider in self.providers:
            try:
                result = provider.generate_embedding(text)
                self.last_served_provider = provider.name
                logger.info("LLM embedding served by provider: %s", provider.name)
                return result
            except Exception as exc:
                errors.append(f"{provider.name}: {exc}")
                logger.warning("Provider %s failed embedding generation: %s", provider.name, exc)
                continue
        raise RuntimeError(f"All LLM providers failed for embedding: {'; '.join(errors)}")


class OpenAICompatClient(MultiProviderClient):
    """Backwards compatibility alias using MultiProviderClient."""
    pass


def parse_json_object(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("LLM output did not contain a JSON object")
    data = json.loads(text[start : end + 1])
    if not isinstance(data, dict):
        raise ValueError("LLM JSON was not an object")
    return data

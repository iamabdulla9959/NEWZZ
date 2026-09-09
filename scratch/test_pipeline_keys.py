import os
import sys
import json
from openai import OpenAI
from dotenv import load_dotenv

sys.path.insert(0, "d:/News/apps/worker")
load_dotenv("d:/News/.env")

from worker.llm import MultiProviderClient, LLMProvider, SUMMARIZER_SYSTEM_PROMPT, JUDGE_SYSTEM_PROMPT, parse_json_object

sample_sources = """
SOURCE 1 (The Hindu):
ISRO successfully launched the Chandrayaan-4 lunar sample return mission from Sriharikota on Monday. The mission aims to bring back rock and soil samples from the moon's south pole. The spacecraft was carried by the LVM3 rocket and entered initial orbit smoothly.

SOURCE 2 (Press Trust of India):
India's space agency ISRO launched Chandrayaan-4 on Monday morning using its heaviest rocket, LVM3. Scientists at the Satish Dhawan Space Centre confirmed that the spacecraft separated from the launch vehicle after 16 minutes and is traveling toward lunar transfer orbit. The mission carries sample collection equipment designed to return lunar soil to Earth.
"""

def test_provider(provider: LLMProvider):
    print(f"\n==========================================")
    print(f"Testing Provider: {provider.name} (Model: {provider.model})")
    print(f"==========================================")
    
    # 1. Summarization Test
    print("[1] Testing Summarization (JSON schema compliance)...")
    try:
        raw_summary = provider.complete_text(SUMMARIZER_SYSTEM_PROMPT, sample_sources)
        summary_obj = parse_json_object(raw_summary)
        headline = summary_obj.get("headline", "")
        summary_text = summary_obj.get("summary", "")
        category = summary_obj.get("category", "")
        key_facts = summary_obj.get("key_facts", [])
        conflicts = summary_obj.get("conflicts", [])
        
        words = len(summary_text.split())
        h_words = len(headline.split())
        print(f"  Headline: \"{headline}\" ({h_words} words, max 10)")
        print(f"  Category: {category}")
        print(f"  Summary: \"{summary_text}\"")
        print(f"  Word Count: {words} words (Target: 60-85 words)")
        print(f"  Key Facts: {len(key_facts)} bullets")
        print(f"  Conflicts: {conflicts}")
        print("  -> Summarization SUCCESS!")
    except Exception as e:
        print(f"  -> Summarization FAILED: {e}")
        return False

    # 2. Consistency Judge Test
    print("\n[2] Testing Fact-Consistency Judge...")
    try:
        judge_payload = f"Source text:\n{sample_sources}\n\nDraft summary:\n{summary_text}"
        raw_judge = provider.complete_text(JUDGE_SYSTEM_PROMPT, judge_payload)
        judge_obj = parse_json_object(raw_judge)
        consistent = judge_obj.get("consistent")
        issues = judge_obj.get("issues", [])
        print(f"  Consistent: {consistent}")
        print(f"  Issues: {issues}")
        print("  -> Fact Consistency Judge SUCCESS!")
    except Exception as e:
        print(f"  -> Fact Consistency Judge FAILED: {e}")
        return False
        
    return True

if __name__ == "__main__":
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    openrouter_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    
    # Test Groq
    groq_provider = LLMProvider(
        name="groq",
        api_key=groq_key,
        base_url="https://api.groq.com/openai/v1",
        model="openai/gpt-oss-20b"
    )
    test_provider(groq_provider)

    # Test OpenRouter
    openrouter_provider = LLMProvider(
        name="openrouter",
        api_key=openrouter_key,
        base_url="https://openrouter.ai/api/v1",
        model="nvidia/nemotron-3.5-lightning:free"
    )
    test_provider(openrouter_provider)

    # Test Fallback MultiProviderClient
    print("\n==========================================")
    print("Testing MultiProviderClient (Integrated Pipeline)")
    print("==========================================")
    multi = MultiProviderClient()
    res = multi.complete_json(SUMMARIZER_SYSTEM_PROMPT, sample_sources)
    print(f"MultiProvider successfully served by: {multi.last_served_provider}")
    print(f"Generated headline: {res.get('headline')}")

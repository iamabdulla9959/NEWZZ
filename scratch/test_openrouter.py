import os
import sys
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv
# pyrefly: ignore [missing-import]
from openai import OpenAI

load_dotenv("d:/News/.env")

openrouter_key = os.getenv("OPENROUTER_API_KEY", "").strip()
client = OpenAI(api_key=openrouter_key, base_url="https://openrouter.ai/api/v1")

models = [
    "nvidia/nemotron-3.5-lightning:free",
    "inclusionai/ling-3.0-flash-sante:free",
    "liquid/lfm-2.5-2.6b:free",
    "meta-llama/llama-3.2-1b-instruct:free",
    "google/gemma-2-9b-it:free",
]

print("OpenRouter key present. Testing free models...")
for model in models:
    try:
        print(f"Testing {model}...")
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Respond with JSON: {\"status\": \"ok\"}"}],
            max_tokens=50,
            timeout=10.0,
        )
        content = (resp.choices[0].message.content or "").strip()
        print(f"  [SUCCESS] {model} returned: {content[:80]}")
        break
    except Exception as e:
        print(f"  [FAILED] {model}: {e}")

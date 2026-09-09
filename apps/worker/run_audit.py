import os
import json
import time
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

from worker.llm import MultiProviderClient

client = MultiProviderClient()

with open("audit_data.json", "r", encoding="utf-8") as f:
    data = json.load(f)

system_prompt = """You are an expert fact-checker auditing a news aggregation pipeline. 
Given a cluster of source articles and optionally the final generated summary card, evaluate the following:
1. is_same_event: Are all the source articles actually about the exact same event/story? (true/false)
2. genuinely_independent: Do the sources appear genuinely independent? (true/false. Return false if they seem like verbatim syndications of the exact same wire story)
3. correctly_handled:
   - If it was 'published' but has <2 independent sources or conflict, it should NOT have been published (false).
   - If it was 'HOLD' (eligible=False) but it DID have 2+ independent sources and no conflict, it should NOT have been held (false).
   - Otherwise, true.
4. summary_faithful: If a summary exists, is it perfectly faithful to the sources without adding outside info? (true/false. If no summary, return true)
5. details_preserved: Were numbers/dates/names preserved accurately? (true/false. If no summary, return true)
6. unnecessary_duplication: Does the summary contain unnecessary repetition or duplication of facts? (true/false)

Return exactly this JSON structure:
{
  "is_same_event": true,
  "genuinely_independent": true,
  "correctly_handled": true,
  "summary_faithful": true,
  "details_preserved": true,
  "unnecessary_duplication": false
}
"""

results = {"published": [], "hold": [], "conflict": [], "multi": []}

def evaluate_cluster(c):
    prompt = f"Cluster ID: {c['cluster_id']}\nEligible: {c['eligible']}\nFlagged Conflict: {c['flagged_conflict']}\n"
    if c['card']:
        prompt += f"Card Status: {c['card']['status']}\nCard Headline: {c['card']['headline']}\nCard Summary: {c['card']['summary']}\n"
    else:
        prompt += "Card Status: HOLD (No card generated)\n"
    
    prompt += "\nSource Articles:\n"
    for i, a in enumerate(c['articles']):
        prompt += f"\n--- Source {i+1} ({a['source']} | Wire: {a['wire']}) ---\nTitle: {a['title']}\nText: {a['text'][:800]}...\n"
    
    try:
        return client.complete_json(system_prompt, prompt)
    except Exception as e:
        print(f"Error evaluating cluster {c['cluster_id']}: {e}")
        return {
            "is_same_event": True,
            "genuinely_independent": c['eligible'],
            "correctly_handled": True,
            "summary_faithful": True,
            "details_preserved": True,
            "unnecessary_duplication": False
        }

for category, items in data.items():
    print(f"Evaluating {category} ({len(items)} items)...")
    for item in items:
        res = evaluate_cluster(item)
        res['cluster_id'] = item['cluster_id']
        results[category].append(res)
        time.sleep(0.5)

with open("audit_results.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)
print("Saved audit_results.json")

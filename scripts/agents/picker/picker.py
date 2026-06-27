import os
import sys
import json
from dotenv import load_dotenv

# Set path environment to load parent helper modules
from utils.common import load_topics
from utils.llm_client import call_llm as client_call_llm

load_dotenv()

def call_llm(system_prompt, user_content):
    """Call NVIDIA NIM API synchronously using standard OpenAI client."""
    try:
        return client_call_llm(system_prompt, user_content, temperature=0.3, max_tokens=2048, timeout=120)
    except Exception as e:
        print(f"      [!] Picker LLM Client Error: {e}")
        raise e

def select_article(target_category, candidates_list):
    """Queries the Picker Agent to select the single best candidate matching target_category."""
    print(f"    - Querying Picker Agent for a {target_category.upper()} article...")
    
    agent_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Load category-specific picker prompt if exists, otherwise fallback to default picker.txt
    prompt_path = os.path.join(agent_dir, f"picker_{target_category.lower()}.txt")
    if not os.path.exists(prompt_path):
        prompt_path = os.path.join(agent_dir, "picker.txt")
        
    if not os.path.exists(prompt_path):
        print(f"      [!] Picker prompt template not found: {prompt_path}")
        return None
        
    with open(prompt_path, 'r', encoding='utf-8') as f:
        system_prompt = f.read()

    # Load topic list for deduplication context
    recent_topics = load_topics(target_category)
    
    user_payload = "### RECENTLY PUBLISHED TOPICS\n"
    user_payload += json.dumps(recent_topics.get('topics', []), indent=2)
    user_payload += "\n\n### CANDIDATES\n"
    user_payload += json.dumps(candidates_list[:60], indent=2)
    
    try:
        res = call_llm(system_prompt, user_payload)
        if res.get("found") and res.get("url"):
            print(f"      [+] Picker Selected: '{res.get('title')[:60]}...'")
            return res
        else:
            print(f"      [-] Picker returned no suitable candidates for {target_category}.")
            return None
    except Exception as e:
        print(f"      [!] Picker agent selection failed: {e}")
        return None

if __name__ == "__main__":
    # Test stub
    mock_candidates = [{"title": "Local Test Article", "url": "https://test.com/local-test", "category": "Local"}]
    print(select_article("local", mock_candidates))

import os
import sys
import json
from dotenv import load_dotenv

from utils.llm_client import call_llm as client_call_llm

load_dotenv()

def call_llm(system_prompt, user_content):
    try:
        return client_call_llm(system_prompt, user_content, temperature=0.1, max_tokens=256, timeout=60)
    except Exception as e:
        print(f"      [!] Tagger LLM Client Error: {e}")
        raise e

def correct_tag(title, description, invalid_tag):
    """Queries the Tagger Agent to correct an invalid tag."""
    print(f"    - Querying Tagger Agent to correct invalid tag '{invalid_tag}'...")
    
    agent_dir = os.path.dirname(os.path.abspath(__file__))
    prompt_path = os.path.join(agent_dir, "tagger_agent.txt")
    
    if not os.path.exists(prompt_path):
        print(f"      [!] Tagger prompt template not found: {prompt_path}")
        return "Uncategorized"
        
    with open(prompt_path, 'r', encoding='utf-8') as f:
        system_prompt = f.read()
        
    user_payload = f"TITLE: {title}\nDESCRIPTION: {description}\nINVALID TAG: {invalid_tag}"
    
    try:
        res = call_llm(system_prompt, user_payload)
        return res.get("majorTag", "Uncategorized")
    except Exception as e:
        print(f"      [!] Tagger agent execution failed: {e}. Defaulting to 'Uncategorized'.")
        return "Uncategorized"

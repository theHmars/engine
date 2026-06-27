import os
import sys
import json
from dotenv import load_dotenv

from utils.llm_client import call_llm as client_call_llm

load_dotenv()

def call_llm(system_prompt, user_content):
    try:
        return client_call_llm(system_prompt, user_content, temperature=0.5, max_tokens=2048, timeout=120)
    except Exception as e:
        print(f"      [!] Writer LLM Client Error: {e}")
        raise e

def rewrite_article(clean_source_json):
    """Queries the Writer Agent to rewrite the raw cleaned content body."""
    print("    - Querying Writer Agent to rewrite content body...")
    
    agent_dir = os.path.dirname(os.path.abspath(__file__))
    prompt_path = os.path.join(agent_dir, "writer.txt")
    
    if not os.path.exists(prompt_path):
        print(f"      [!] Writer prompt template not found: {prompt_path}")
        return None
        
    with open(prompt_path, 'r', encoding='utf-8') as f:
        system_prompt = f.read()
        
    try:
        res = call_llm(system_prompt, f"SOURCE TEXT:\n{clean_source_json}")
        return res.get("content")
    except Exception as e:
        print(f"      [!] Writer agent execution failed: {e}")
        return None

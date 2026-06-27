import os
import sys
import json
from dotenv import load_dotenv

from utils.llm_client import call_llm as client_call_llm

load_dotenv()

def call_llm(system_prompt, user_content):
    try:
        return client_call_llm(system_prompt, user_content, temperature=0.3, max_tokens=1024, timeout=90)
    except Exception as e:
        print(f"      [!] Metadata LLM Client Error: {e}")
        raise e

def generate_metadata(clean_source_json, finalized_content):
    """Queries the Metadata Agent to generate the SEO title, description, and tags."""
    print("    - Querying Metadata Agent to generate frontmatter parameters...")
    
    agent_dir = os.path.dirname(os.path.abspath(__file__))
    prompt_path = os.path.join(agent_dir, "metadata_agent.txt")
    
    if not os.path.exists(prompt_path):
        print(f"      [!] Metadata prompt template not found: {prompt_path}")
        return None
        
    with open(prompt_path, 'r', encoding='utf-8') as f:
        system_prompt = f.read()
        
    user_payload = f"RAW SOURCE INFO:\n{clean_source_json}\n\nFINALIZED REWRITTEN CONTENT:\n{finalized_content}"
    
    try:
        res = call_llm(system_prompt, user_payload)
        return res
    except Exception as e:
        print(f"      [!] Metadata agent execution failed: {e}")
        return None

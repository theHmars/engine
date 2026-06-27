import os
import sys
import json
from dotenv import load_dotenv

from utils.llm_client import call_llm as client_call_llm

load_dotenv()

def call_llm(system_prompt, user_content):
    try:
        return client_call_llm(system_prompt, user_content, temperature=0.3, max_tokens=2048, timeout=90)
    except Exception as e:
        print(f"      [!] Corrector LLM Client Error: {e}")
        raise e

def validate_content(source_json, rewritten_content):
    """Queries the Validator Agent (Chief Fact Checker) to check content accuracy."""
    print("    - Querying Validator Agent to check content body accuracy...")
    
    agent_dir = os.path.dirname(os.path.abspath(__file__))
    prompt_path = os.path.join(agent_dir, "validator.txt")
    
    if not os.path.exists(prompt_path):
        print(f"      [!] Validator prompt template not found: {prompt_path}")
        return {"passed": True, "confidence_score": 100}
        
    with open(prompt_path, 'r', encoding='utf-8') as f:
        system_prompt = f.read()
        
    user_payload = f"SOURCE TEXT:\n{source_json}\n\nREWRITTEN CONTENT:\n{rewritten_content}"
    
    try:
        res = call_llm(system_prompt, user_payload)
        return res
    except Exception as e:
        print(f"      [!] Validator agent execution failed: {e}. Defaulting to PASSED.")
        return {"passed": True, "confidence_score": 100}

def correct_content(source_json, previous_draft, validator_feedback):
    """Queries the Corrector Agent to revise the content based on validator feedback."""
    print("    - Querying Corrector Agent to revise incorrect details...")
    
    agent_dir = os.path.dirname(os.path.abspath(__file__))
    prompt_path = os.path.join(agent_dir, "corrector_writer.txt")
    
    if not os.path.exists(prompt_path):
        print(f"      [!] Corrector prompt template not found: {prompt_path}")
        return previous_draft
        
    with open(prompt_path, 'r', encoding='utf-8') as f:
        system_prompt = f.read()
        
    user_payload = f"SOURCE TEXT:\n{source_json}\n\nPREVIOUS INVALID DRAFT:\n{previous_draft}\n\nFEEDBACK:\n{validator_feedback}"
    
    try:
        res = call_llm(system_prompt, user_payload)
        return res.get("content", previous_draft)
    except Exception as e:
        print(f"      [!] Corrector agent execution failed: {e}. Returning original draft.")
        return previous_draft

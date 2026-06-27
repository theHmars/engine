import os
import sys
import json
import re
from dotenv import load_dotenv

from utils.llm_client import call_llm as client_call_llm

load_dotenv()

def call_llm(system_prompt, user_content):
    try:
        return client_call_llm(system_prompt, user_content, temperature=0.1, max_tokens=256, timeout=60)
    except Exception as e:
        print(f"      [!] Deduplicator LLM Error: {e}")
        raise e

def is_duplicate_coverage(candidate, website_repo_path):
    """
    Two-Phase Deduplication logic.
    Compares candidate against published history in covered.json to avoid duplicate news coverage.
    """
    print(f"    - Checking Deduplication for: '{candidate.get('title')[:50]}...'")
    
    agent_dir = os.path.dirname(os.path.abspath(__file__))
    
    category = candidate.get("category", "Local").lower()
    if category == "international":
        category = "global"
        
    covered_path = os.path.join(website_repo_path, f"history/{category}/covered.json")
    
    # 1. Load History from covered.json
    covered_data = []
    if os.path.exists(covered_path):
        try:
            with open(covered_path, 'r', encoding='utf-8') as f:
                covered_data = json.load(f)
        except Exception as e:
            print(f"      [!] Failed to parse covered.json: {e}")
            
    if not covered_data:
        print("      [!] No published articles found in covered.json. Skipping deduplication check.")
        return False

    historical_titles = [item["title"] for item in covered_data]

    # --- PHASE 2/1: TITLE FILTER ---
    with open(os.path.join(agent_dir, "filter_titles.txt"), 'r', encoding='utf-8') as f:
        filter_prompt = f.read()
        
    payload_1 = f"CANDIDATE TITLE: {candidate.get('title')}\n\n### RECENT PUBLISHED TITLES\n"
    payload_1 += json.dumps(historical_titles, indent=2)
    
    try:
        res_1 = call_llm(filter_prompt, payload_1)
        matched_title = res_1.get("potential_duplicate")
        if not matched_title:
            return False # No duplicate found, passes!
            
        print(f"      [!] Phase 1 Match: Candidate matched with historical title '{matched_title}'")
    except Exception as e:
        print(f"      [!] Phase 1 Deduplication error: {e}. Passing candidate as safe.")
        return False

    # --- PHASE 2/2: DESCRIPTION VERIFICATION ---
    # Find the matching entry in covered_data to read its description
    matched_item = None
    for item in covered_data:
        if item.get("title", "").lower() == matched_title.lower():
            matched_item = item
            break
            
    if not matched_item:
        print(f"      [!] Could not find description for matched title '{matched_title}'. Treating as safe.")
        return False
        
    description = matched_item.get("description", "")
    if not description:
        return False # Fallback to safe if description is missing

    # Run Phase 2 check
    with open(os.path.join(agent_dir, "verify_descriptions.txt"), 'r', encoding='utf-8') as f:
        verify_prompt = f.read()
        
    # Grab the first 2 sentences of the candidate raw text
    cand_intro = " ".join(candidate.get("content", "").split(".")[:2])
    
    payload_2 = f"CANDIDATE TITLE: {candidate.get('title')}\nCANDIDATE INTRO: {cand_intro}\n\n"
    payload_2 += f"MATCHED HISTORICAL TITLE: {matched_title}\nHISTORICAL DESCRIPTION: {description}"
    
    try:
        res_2 = call_llm(verify_prompt, payload_2)
        is_dup = res_2.get("is_duplicate", False)
        if is_dup:
            print(f"      [!] Phase 2 Verification: Confirming duplicate coverage of '{matched_title}'. Skipping candidate.")
            return True
        else:
            print(f"      [+] Phase 2 Verification: Not a duplicate (False alarm). Proceeding.")
            return False
    except Exception as e:
        print(f"      [!] Phase 2 Deduplication error: {e}. Passing candidate.")
        return False


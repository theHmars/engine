#!/usr/bin/env python3
import json
import os
import sys
import random

# Setup path environment to load helper modules
from utils.common import load_source_history, get_scope
import agents.picker.picker as picker

def get_picker_prompt(scope, filename):
    script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(script_dir, "agents/picker", scope, filename)
    if not os.path.exists(path):
        path = os.path.join(script_dir, "agents/picker/core", filename)
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

def run_relevance_filter(candidates, attempts_limit=3):
    """Runs Relevance Filter Agent using a 3-strike index-based validation loop."""
    scope = get_scope()
    print(f"\n--- Running Relevance Filter ({scope.upper()} Scope check) ---")
    
    system_prompt = get_picker_prompt(scope, "relevance_filter.txt")
    
    active_pool = list(candidates)
    
    for attempt in range(1, attempts_limit + 1):
        if not active_pool:
            break
            
        print(f"  - Relevance filter attempt {attempt}/{attempts_limit}...")
        
        # Present candidates in a numbered list (1-indexed)
        numbered_payload = []
        for idx, c in enumerate(active_pool, 1):
            numbered_payload.append(f"[{idx}] {c['title']} (URL: {c['url']})")
            
        user_content = "\n".join(numbered_payload)
        try:
            res = picker.call_llm(system_prompt, user_content)
            skip_indices = res.get("skip_indices", [])
        except Exception as e:
            print(f"    [!] Relevance query error on attempt {attempt}: {e}")
            skip_indices = []
            
        # Programmatic Index Validation
        valid_skips = []
        invalid_skips = []
        for idx in skip_indices:
            if 1 <= idx <= len(active_pool):
                valid_skips.append(idx - 1) # convert to 0-index
            else:
                invalid_skips.append(idx)
                
        if invalid_skips:
            print(f"    [!] Validation Failed: Out-of-bounds skip indices: {invalid_skips} on attempt {attempt}.")
            # Strip invalid ones and prompt again
            continue
        else:
            print(f"    [+] Validation Passed. Filtering out {len(valid_skips)} irrelevant candidates.")
            # Keep elements not in valid skips
            active_pool = [c for idx, c in enumerate(active_pool) if idx not in valid_skips]
            break
    else:
        # Fallback if 3 attempts fail
        print("    [!] Relevance Filter validation limit reached. Continuing with all candidates.")
        
    print(f"  [+] Relevance Triage Complete. Passed: {len(active_pool)} candidates.")
    return active_pool

def run_senior_curation(relevant_candidates, max_slots=10, attempts_limit=3):
    """Runs Senior Editor Picker Agent using a 3-strike index-based validation loop."""
    scope = get_scope()
    print(f"\n--- Running Senior Curation ({scope.upper()} Scope, curating top {max_slots}) ---")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    system_prompt = get_picker_prompt(scope, "senior_curator.txt")
    
    # Load topics.json and covered.json from content repo
    root_dir = os.environ.get("SCOUT_WORKSPACE", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    content_repo = os.environ.get("WEBSITE_REPO_PATH", root_dir)
    topics_path = os.path.join(content_repo, f"history/{scope}/topics.json")
    covered_path = os.path.join(content_repo, f"history/{scope}/covered.json")
    
    topics_data = {}
    if os.path.exists(topics_path):
        with open(topics_path, 'r', encoding='utf-8') as f:
            topics_data = json.load(f)
            
    covered_data = []
    if os.path.exists(covered_path):
        with open(covered_path, 'r', encoding='utf-8') as f:
            covered_data = json.load(f)
            
    # Inject historical context
    system_prompt = system_prompt.replace("[Inject topics.json here]", json.dumps(topics_data, indent=2))
    system_prompt = system_prompt.replace("[Inject covered.json here]", json.dumps(covered_data, indent=2))
    
    # Separate new and archive backlog pools
    new_pool = []
    old_pool = []
    for c in relevant_candidates:
        if "archive" in c.get("clean_path", ""):
            old_pool.append(c)
        else:
            new_pool.append(c)
            
    # Combine into a single ordered list: New first, then Old
    ordered_candidates = new_pool + old_pool
    if not ordered_candidates:
        return []
        
    for attempt in range(1, attempts_limit + 1):
        print(f"  - Senior curation selection attempt {attempt}/{attempts_limit}...")
        
        # Present numbered candidates with status labels
        numbered_payload = []
        for idx, c in enumerate(ordered_candidates, 1):
            label = "[NEW]" if c in new_pool else "[ARCHIVED]"
            numbered_payload.append(f"[{idx}] {label} {c['title']} (URL: {c['url']})")
            
        candidates_text = "\n".join(numbered_payload)
        final_prompt = system_prompt.replace("[Inject Candidates here]", candidates_text)
        
        user_content = f"SELECT UP TO {max_slots} GROUPS."
        try:
            res = picker.call_llm(final_prompt, user_content)
            selected_groups = res.get("selected_groups", [])
        except Exception as e:
            print(f"    [!] Curation query error on attempt {attempt}: {e}")
            selected_groups = []
            
        # Programmatic Group Index Validation
        valid_selections = []
        invalid_indices = []
        
        for group in selected_groups:
            valid_group = []
            for idx in group:
                if 1 <= idx <= len(ordered_candidates):
                    # Keep track of validated candidate dict
                    valid_group.append(ordered_candidates[idx - 1])
                else:
                    invalid_indices.append(idx)
            if valid_group:
                valid_selections.append(valid_group)
                
        if invalid_indices:
            print(f"    [!] Validation Failed: Out-of-bounds indices {invalid_indices} on attempt {attempt}.")
            continue
        elif not valid_selections:
            print(f"    [!] Validation Failed: Senior curator returned empty selection on attempt {attempt}.")
            continue
        else:
            print(f"    [+] Validation Passed. Selected {len(valid_selections)} story groups.")
            # Flatten to write list structure for chosen_articles while marking merged flags
            flattened_selections = []
            for group in valid_selections[:max_slots]:
                if len(group) == 1:
                    flattened_selections.append(group[0])
                else:
                    print(f"      [+] Merging {len(group)} similar sources into a multi-source post...")
                    primary = group[0]
                    merged = {
                        "title": primary["title"],
                        "url": primary["url"],
                        "source_name": primary["source_name"],
                        "source_key": primary["source_key"],
                        "category": primary["category"],
                        "clean_path": primary["clean_path"],
                        "content": primary.get("content", ""),
                        "featured_image": primary.get("featured_image"),
                        "is_merged": True,
                        "secondary_sources": []
                    }
                    for sec in group[1:]:
                        merged["secondary_sources"].append({
                            "title": sec["title"],
                            "url": sec["url"],
                            "source_name": sec["source_name"],
                            "source_key": sec["source_key"],
                            "content": sec.get("content", "")
                        })
                    flattened_selections.append(merged)
            return flattened_selections
    else:
        # Fallback to random pick from relevant pool if validation fails 3 times
        print("    [!] Senior curation validation limit reached. Picking random fallbacks.")
        fallback_choices = random.sample(ordered_candidates, min(max_slots, len(ordered_candidates)))
        return fallback_choices

def main():
    print("\n>>> Running Job 2.1: Curation & Target Triage Selection")
    scope = get_scope()
    root_dir = os.environ.get("SCOUT_WORKSPACE", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    # Load Compiled Candidates Pool
    cleaned_candidates_path = os.path.join(root_dir, f'tmp/{scope}/cleaned_candidates.json')
    if not os.path.exists(cleaned_candidates_path):
        print(f"[!] Error: Sourced candidates index missing: {cleaned_candidates_path}")
        sys.exit(1)
        
    with open(cleaned_candidates_path, 'r', encoding='utf-8') as f:
        pool = json.load(f)
        
    new_candidates = pool.get("new_candidates", [])
    archived_candidates = pool.get("archived_candidates_last_48h", [])
    all_candidates = new_candidates + archived_candidates
    
    if not all_candidates:
        print(">>> Candidate pool is empty. Exiting.")
        # Ensure downstream steps have empty inputs
        relevant_candidates_path = os.path.join(root_dir, f'tmp/{scope}/relevant_candidates.json')
        with open(relevant_candidates_path, 'w', encoding='utf-8') as f:
            json.dump([], f)
        chosen_path = os.path.join(root_dir, f'tmp/{scope}/chosen_articles.json')
        with open(chosen_path, 'w', encoding='utf-8') as f:
            json.dump([], f)
        sys.exit(0)
        
    # --- STEP 1: RELEVANCE FILTERING ---
    relevant_pool = run_relevance_filter(all_candidates)
    
    if not relevant_pool:
        print(f">>> No contextually relevant articles found for {scope.upper()} scope. Exiting.")
        # Ensure downstream steps have empty inputs
        chosen_path = os.path.join(root_dir, f'tmp/{scope}/chosen_articles.json')
        with open(chosen_path, 'w', encoding='utf-8') as f:
            json.dump([], f)
        sys.exit(0)
        
    # Save relevance triage pool
    relevant_candidates_path = os.path.join(root_dir, f'tmp/{scope}/relevant_candidates.json')
    with open(relevant_candidates_path, 'w', encoding='utf-8') as f:
        json.dump(relevant_pool, f, indent=4)
        
    # --- STEP 2: SENIOR CURATION ---
    chosen_articles = run_senior_curation(relevant_pool, max_slots=10)
    
    # Save final chosen articles
    chosen_path = os.path.join(root_dir, f'tmp/{scope}/chosen_articles.json')
    with open(chosen_path, 'w', encoding='utf-8') as f:
        json.dump(chosen_articles, f, indent=4)
        
    print(f">>> Job 2.1 Complete. Wrote {len(chosen_articles)} selected candidates to '{chosen_path}'.")

if __name__ == "__main__":
    main()

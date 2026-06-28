#!/usr/bin/env python3
import json
import os
import sys
import re
from agents.deduplicator.deduplicator import is_duplicate_coverage, call_llm
from utils.common import get_scope, get_state_dir

def get_grouping_prompt():
    """Loads system prompt for the similarity grouping agent."""
    script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(script_dir, "agents/deduplicator/group_sources.txt")
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

def group_chosen_sources(chosen_list, attempts_limit=3):
    """
    Queries the Grouping Agent to identify articles covering the same event
    within the curated list. Returns a list of groups (each group is a list of article dicts).
    """
    print("\n--- Running Intra-Batch Deduplication & Grouping ---")
    if not chosen_list:
        return []
        
    system_prompt = get_grouping_prompt()
    
    # Extract title and first 30 words of content for each chosen article
    numbered_payload = []
    for idx, art in enumerate(chosen_list, 1):
        content_intro = " ".join(art.get("content", "").split()[:30])
        numbered_payload.append(f"[{idx}] Title: {art['title']}\nIntro: {content_intro}...\n")
        
    user_content = "\n".join(numbered_payload)
    
    for attempt in range(1, attempts_limit + 1):
        print(f"  - Grouping query attempt {attempt}/{attempts_limit}...")
        try:
            res = call_llm(system_prompt, user_content)
            groups = res.get("groups", [])
        except Exception as e:
            print(f"    [!] Grouping query error: {e}")
            groups = []
            
        # Programmatic Validation
        valid_groups = []
        flat_indices = set()
        validation_failed = False
        
        for g in groups:
            valid_g = []
            for idx in g:
                if 1 <= idx <= len(chosen_list):
                    valid_g.append(idx - 1)
                    flat_indices.add(idx - 1)
                else:
                    validation_failed = True
                    print(f"    [!] Validation Failed: Out-of-bounds group index: {idx}")
            if valid_g:
                valid_groups.append(valid_g)
                
        # Ensure every candidate is accounted for in exactly one group
        unassigned = [i for i in range(len(chosen_list)) if i not in flat_indices]
        for idx in unassigned:
            valid_groups.append([idx])
            
        if not validation_failed:
            print(f"    [+] Validation Passed. Identified {len(valid_groups)} unique news events from {len(chosen_list)} sources.")
            # Map index groups back to article objects
            mapped_groups = []
            for g in valid_groups:
                mapped_groups.append([chosen_list[i] for i in g])
            return mapped_groups
    else:
        # Fallback: treat all as unique
        print("    [!] Grouping validation limit reached. Treating all sources as unique.")
        return [[art] for art in chosen_list]

def merge_grouped_sources(group):
    """
    Combines a list of similar articles into a single merged structure.
    If the group contains only one article, returns it unmodified.
    """
    if len(group) == 1:
        return group[0]
        
    print(f"  [+] Merging {len(group)} similar sources into a multi-source post...")
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
        
    return merged

def run_deduplication(article):
    """
    Executes Phase 3 Deduplication for a single article.
    Checks published history on the website repo path.
    If already exists, flags it for updates inside tmp/update_candidates.json.
    """
    print(f"\n>>> Running Phase 3: Deduplication check for '{article.get('title')[:50]}...'")
    
    root_dir = os.environ.get("SCOUT_WORKSPACE", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    scope = get_scope()
    
    # Path to website repo cloned on runner.
    website_repo_path = os.environ.get("WEBSITE_REPO_PATH")
    if not website_repo_path:
        parent_dir = os.path.dirname(root_dir)
        sibling_path = os.path.join(parent_dir, "content-repo")
        if os.path.exists(sibling_path):
            website_repo_path = sibling_path
        else:
            website_repo_path = os.path.join(root_dir, "temp_test_clone")
            
    category = article.get("category", "Local").lower()
    if category == "international":
        category = "global"

    if not os.path.exists(website_repo_path):
        os.makedirs(os.path.join(website_repo_path, f"history/{category}"), exist_ok=True)
        os.makedirs(os.path.join(website_repo_path, f"markdown/{category}"), exist_ok=True)
        
    shared_path = os.path.join(website_repo_path, f"history/{category}/shared.json")
    if not os.path.exists(shared_path):
        os.makedirs(os.path.dirname(shared_path), exist_ok=True)
        with open(shared_path, 'w', encoding='utf-8') as f:
            json.dump([], f)
                
    is_dup = is_duplicate_coverage(article, website_repo_path)
    
    if is_dup:
        print(f"  [!] Article '{article.get('title')[:40]}' matched with published history. Skipping for this session.")
        
        # --------------------------------------------------------------------------------
        # TODO / NOTE: Intentionally left as is for now. 
        # This is a stub for a future "Story Update/Enrichment" feature.
        # Currently, update_candidates.json is volatile (lives in tmp/) and is never used.
        # To make this work in the future:
        # 1. is_duplicate_coverage() must return the specific slug of the matched article.
        # 2. We should ideally store historical source URLs directly in the published 
        #    .md file's frontmatter. This would allow us to track updates seamlessly if a 
        #    source publishes a developing story, or if multiple sources cover the same 
        #    ongoing event with extra details over time.
        # --------------------------------------------------------------------------------
        update_path = os.path.join(get_state_dir(), f"tmp/{scope}/update_candidates.json")
        updates = []
        if os.path.exists(update_path):
            try:
                with open(update_path, 'r', encoding='utf-8') as f:
                    updates = json.load(f)
            except:
                pass
        updates.append({
            "title": article["title"],
            "url": article["url"],
            "source_name": article["source_name"],
            "content": article.get("content", "")
        })
        with open(update_path, 'w', encoding='utf-8') as f:
            json.dump(updates, f, indent=4)
        return False
    else:
        print(f"  [+] Article '{article.get('title')[:40]}' verified as UNIQUE.")
        return True

def compile_triaged_queue():
    """
    Reads the chosen articles list, runs similarity grouping, executes deduplication checks,
    and writes the final unique/merged queue to tmp/triaged_candidates.json.
    """
    print("\n>>> Starting Phase 3: Deduplication & Queue Compilation")
    root_dir = os.environ.get("SCOUT_WORKSPACE", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    scope = get_scope()
    
    chosen_path = os.path.join(get_state_dir(), f"tmp/{scope}/chosen_articles.json")
    if not os.path.exists(chosen_path):
        print(f"[!] Error: Curated queue missing: {chosen_path}")
        sys.exit(1)
        
    with open(chosen_path, 'r', encoding='utf-8') as f:
        chosen_list = json.load(f)
        
    if not chosen_list:
        print(">>> Curated queue is empty. Exiting.")
        triaged_candidates_path = os.path.join(get_state_dir(), f"tmp/{scope}/triaged_candidates.json")
        with open(triaged_candidates_path, 'w', encoding='utf-8') as f:
            json.dump([], f)
        sys.exit(0)
        
    # 1. Run Intra-Batch Deduplication & Merging
    grouped_articles = group_chosen_sources(chosen_list)
    merged_list = [merge_grouped_sources(g) for g in grouped_articles]
    
    # 2. Run Historical Deduplication Check
    final_queue = []
    for art in merged_list:
        if run_deduplication(art):
            final_queue.append(art)
            
    # 3. Export Verified Queue
    triaged_candidates_path = os.path.join(get_state_dir(), f"tmp/{scope}/triaged_candidates.json")
    with open(triaged_candidates_path, 'w', encoding='utf-8') as f:
        json.dump(final_queue, f, indent=4)
        
    print(f"\n>>> Phase 3 Complete. Final unique queue size: {len(final_queue)} (Saved to '{triaged_candidates_path}')")

if __name__ == "__main__":
    compile_triaged_queue()

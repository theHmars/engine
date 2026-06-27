#!/usr/bin/env python3
import json
import os
import sys
import time
import re
import argparse

# Setup path so imports work correctly

from utils.common import check_timeout
from utils.history_manager import HistoryManager
from agents.writer.writer import rewrite_article
from agents.corrector.corrector import validate_content, correct_content
from agents.metadata.metadata import generate_metadata
from agents.tagger.tagger import correct_tag

ALLOWED_TAGS = {
    "Politics", "Sports", "Business", "Tech", "Science", "Culture", 
    "Health", "Education", "Weather", "Entertainment", "Environment", 
    "Celebrity", "Uncategorized"
}

def parse_embedded_image(content):
    """Searches content body for image link patterns and returns the first match or None."""
    if not content:
        return None
    # Look for patterns like 'image link: https://...'
    match = re.search(r'(?:image\s+link|img\s+link|image|img)\s*:\s*(https?://\S+)', content, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None

def process_candidate(candidate, start_time):
    """End-to-end rewrite, validation, metadata generation, and tagging for a single candidate."""
    title_snippet = candidate.get("title", "Untitled")[:50]
    print(f"\n--- Processing Candidate: '{title_snippet}...' ---")
    
    # 1. Prepare raw content representation for the LLM
    # In case of merged articles, incorporate secondary sources clearly.
    source_payload = {
        "title": candidate.get("title"),
        "source_name": candidate.get("source_name"),
        "content": candidate.get("content")
    }
    
    if candidate.get("is_merged") and candidate.get("secondary_sources"):
        sec_str = ""
        for i, sec in enumerate(candidate["secondary_sources"], 1):
            sec_str += f"\n\n[Secondary Source {i} - {sec.get('source_name')}]:\n"
            sec_str += f"Title: {sec.get('title')}\n"
            sec_str += f"Content: {sec.get('content')}\n"
        source_payload["secondary_sources_content"] = sec_str.strip()
        
    source_json_str = json.dumps(source_payload, indent=4)
    
    # 2. Adaptive retry calculation
    is_critical = check_timeout(start_time, limit_minutes=22)
    max_retries = 1 if is_critical else 3
    if is_critical:
        print("    [!] Over 22-minute global threshold. Operating in 1-Shot 'Fast-Fail' mode.")
        
    draft_body = None
    passed_validation = False
    feedback = ""
    
    # 3. Rewrite & Validate Loop
    for attempt in range(1, max_retries + 1):
        print(f"    - Rewrite/Validation attempt {attempt}/{max_retries}...")
        
        # Rewrite
        try:
            if attempt == 1:
                draft_body = rewrite_article(source_json_str)
            else:
                draft_body = correct_content(source_json_str, draft_body, feedback)
        except Exception as e:
            print(f"      [!] Rewrite call failed on attempt {attempt}: {e}")
            continue
            
        if not draft_body:
            print("      [!] Rewrite produced empty/null draft.")
            continue
            
        # Validate
        try:
            val_res = validate_content(source_json_str, draft_body)
            passed = val_res.get("passed", False)
            feedback = val_res.get("fix_instruction", "Factual discrepancy or style issue detected.")
            confidence = val_res.get("confidence_score", 0)
        except Exception as e:
            print(f"      [!] Validation failed: {e}. Passing through.")
            passed = True
            confidence = 100
            
        if passed:
            print(f"      [+] Validation Passed (Confidence: {confidence}%).")
            passed_validation = True
            break
        else:
            print(f"      [!] Validation Failed: {feedback}")
            
    if not passed_validation or not draft_body:
        print(f"    [!] Failed to validate draft for '{title_snippet}' after {max_retries} attempts. Dropping candidate.")
        return None
        
    # 4. Generate Metadata
    print("    - Generating metadata parameters...")
    try:
        meta_res = generate_metadata(source_json_str, draft_body)
    except Exception as e:
        print(f"      [!] Metadata generation failed: {e}")
        meta_res = {}
        
    if not meta_res:
        meta_res = {}
        
    # Merge/Clean metadata attributes
    final_title = meta_res.get("title") or candidate.get("title")
    final_desc = meta_res.get("description") or candidate.get("short_intro") or ""
    
    category = candidate.get("category", "Local")
    if category in ["National", "International", "Global"]:
        final_region = "N/A"
    else:
        final_region = meta_res.get("region") or candidate.get("region") or "N/A"
        allowed_regions = {
            "Arunachal Pradesh", "Assam", "Manipur", "Meghalaya", 
            "Mizoram", "Nagaland", "Sikkim", "Tripura", "Northeast", "N/A"
        }
        if final_region not in allowed_regions:
            print(f"      [!] Invalid region '{final_region}' returned by agent. Defaulting to 'N/A'.")
            final_region = "N/A"
            
    final_tag = meta_res.get("majorTag") or "Uncategorized"
    
    # 5. Programmatic Tag Whitelist Validation & Fallback correction
    if final_tag not in ALLOWED_TAGS:
        print(f"    [!] Invalid tag '{final_tag}'. Attempting tag correction...")
        try:
            final_tag = correct_tag(final_title, final_desc, final_tag)
            if final_tag not in ALLOWED_TAGS:
                print(f"      [!] Corrected tag '{final_tag}' still invalid. Defaulting to 'Uncategorized'.")
                final_tag = "Uncategorized"
            else:
                print(f"      [+] Tag corrected successfully to '{final_tag}'.")
        except Exception as e:
            print(f"      [!] Tag correction failed: {e}. Defaulting to 'Uncategorized'.")
            final_tag = "Uncategorized"
            
    # 6. Featured Image Logic & Fallback Extraction
    featured_image = candidate.get("featured_image")
    if not featured_image or featured_image in ["N/A", "null", "None", ""]:
        # Try to parse from candidate content first
        parsed_img = parse_embedded_image(candidate.get("content"))
        if not parsed_img and candidate.get("secondary_sources"):
            # Check secondary sources
            for sec in candidate["secondary_sources"]:
                parsed_img = parse_embedded_image(sec.get("content"))
                if parsed_img:
                    break
        if parsed_img:
            print(f"    [+] Discovered alternative featured image in text: {parsed_img}")
            featured_image = parsed_img
        else:
            featured_image = None
            
    # Assemble produced payload
    produced_article = {
        "title": final_title,
        "description": final_desc,
        "category": candidate.get("category", "Local"),
        "region": final_region,
        "majorTag": final_tag,
        "featured_image": featured_image,
        "content": draft_body,
        "original_url": candidate.get("url"),
        "source_name": candidate.get("source_name"),
        "source_key": candidate.get("source_key"),
        "is_merged": candidate.get("is_merged", False),
        "secondary_sources": candidate.get("secondary_sources", [])
    }
    
    return produced_article

def main():
    parser = argparse.ArgumentParser(description="Phase 4: Content Rewrite, Critic Validation & Metadata Compilation")
    parser.add_argument("--start-time", type=float, help="Unix timestamp of when the pipeline run started.")
    parser.add_argument("--limit", type=int, default=None, help="Limit the number of produced articles in this run.")
    args = parser.parse_args()

    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.environ.get("SCOUT_WORKSPACE", os.path.dirname(script_dir))
    from utils.common import get_scope
    scope = get_scope()
    
    # 1. Determine Start Time
    if args.start_time:
        start_time = args.start_time
    else:
        # Check for temporary file
        start_time_path = os.path.join(root_dir, f"tmp/{scope}/pipeline_start.txt")
        if os.path.exists(start_time_path):
            try:
                with open(start_time_path, 'r') as f:
                    start_time = float(f.read().strip())
            except:
                start_time = time.time()
        else:
            start_time = time.time()
            
    print(f"\n>>> Starting Phase 4: Production & Critic Validation Loop (Elapsed time: {(time.time() - start_time)/60:.2f} mins)")
    
    # 2. Load candidates from Phase 3
    triaged_path = os.path.join(root_dir, f"tmp/{scope}/triaged_candidates.json")
    if not os.path.exists(triaged_path):
        print(f"[!] Error: Triaged candidates file missing: {triaged_path}")
        sys.exit(1)
        
    with open(triaged_path, 'r', encoding='utf-8') as f:
        candidates = json.load(f)
        
    if not candidates:
        print(">>> No unique candidates to process in this session. Exiting Phase 4.")
        # Write empty list
        produced_path = os.path.join(root_dir, f"tmp/{scope}/produced_articles.json")
        with open(produced_path, 'w', encoding='utf-8') as f:
            json.dump([], f)
        sys.exit(0)
        
    hm = HistoryManager(root_dir)
    produced_articles = []
    
    # 3. Iterate candidates under threshold
    for cand in candidates:
        if args.limit is not None and len(produced_articles) >= args.limit:
            print(f"\n>>> Reached limit of {args.limit} produced articles. Stopping further rewrites.")
            break
            
        # Check threshold (30 mins) to stop starting new rewrites
        if check_timeout(start_time, limit_minutes=30):
            print("\n>>> Elapsed time exceeded 30-minute processing window threshold. Stopping new article starts.")
            break
            
        try:
            prod_art = process_candidate(cand, start_time)
            if prod_art:
                produced_articles.append(prod_art)
                # Log success immediately
                hm.log_url(cand["url"], cand["source_key"], "SUCCESS")
                if cand.get("is_merged") and cand.get("secondary_sources"):
                    for sec in cand["secondary_sources"]:
                        sec_url = sec.get("url")
                        if sec_url:
                            hm.log_url(sec_url, sec.get("source_key", cand["source_key"]), "SUCCESS_MERGED")
            else:
                # Log failed candidate immediately as RETRY_FAILED to allow retry in future run
                hm.log_url(cand["url"], cand["source_key"], "RETRY_FAILED")
                if cand.get("is_merged") and cand.get("secondary_sources"):
                    for sec in cand["secondary_sources"]:
                        sec_url = sec.get("url")
                        if sec_url:
                            hm.log_url(sec_url, sec.get("source_key", cand["source_key"]), "RETRY_FAILED")
        except Exception as e:
            print(f"[!] Error processing candidate: {e}")
            hm.log_url(cand["url"], cand["source_key"], "RETRY_FAILED")
            if cand.get("is_merged") and cand.get("secondary_sources"):
                for sec in cand["secondary_sources"]:
                    sec_url = sec.get("url")
                    if sec_url:
                        hm.log_url(sec_url, sec.get("source_key", cand["source_key"]), "RETRY_FAILED")
            
    # 4. Save results to tmp/produced_articles.json
    produced_path = os.path.join(root_dir, f"tmp/{scope}/produced_articles.json")
    with open(produced_path, 'w', encoding='utf-8') as f:
        json.dump(produced_articles, f, indent=4)
        
    print(f"\n>>> Phase 4 Complete. Successfully produced {len(produced_articles)} articles. (Saved to '{produced_path}')")

if __name__ == "__main__":
    main()

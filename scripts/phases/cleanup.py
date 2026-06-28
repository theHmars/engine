#!/usr/bin/env python3
import json
import os
import sys
import shutil
from datetime import datetime, timedelta

# Setup path so imports work correctly

from utils.common import slugify, get_state_dir
from utils.history_manager import HistoryManager
from assembler import generate_yaml

def main():
    print("\n>>> Starting Phase 5: Sync, Cleanup & Callback")
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.environ.get("SCOUT_WORKSPACE", os.path.dirname(script_dir))
    from utils.common import get_scope, get_state_dir
    scope = get_scope()
    
    produced_path = os.path.join(get_state_dir(), f"tmp/{scope}/produced_articles.json")
    triaged_path = os.path.join(get_state_dir(), f"tmp/{scope}/triaged_candidates.json")
    
    if not os.path.exists(produced_path):
        print(f"[!] Error: Produced articles file missing: {produced_path}")
        sys.exit(1)
        
    with open(produced_path, 'r', encoding='utf-8') as f:
        produced_articles = json.load(f)
        
    # Load triaged candidates to find which ones failed
    triaged_articles = []
    if os.path.exists(triaged_path):
        try:
            with open(triaged_path, 'r', encoding='utf-8') as f:
                triaged_articles = json.load(f)
        except:
            pass

    now = datetime.now()
    date_iso = now.strftime('%Y-%m-%dT%H:%M:%SZ')
    date_prefix = now.strftime('%Y-%m-%d')
    
    output_dir = os.path.join(get_state_dir(), f"push/{scope}")
    os.makedirs(output_dir, exist_ok=True)
    
    hm = HistoryManager(root_dir)

    # 1. Save successfully produced articles as Markdown
    successful_urls = set()
    for art in produced_articles:
        try:
            final_slug = slugify(art['title'])
            filename = f"{date_prefix}-{final_slug}.md"
            filepath = os.path.join(output_dir, filename)
            
            yaml_header = generate_yaml(art, date_iso)
            final_content = yaml_header + art.get('content', '')
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(final_content)
            print(f"  [+] Assembled and Saved: {filename}")
            
            # Record URL
            successful_urls.add(art["original_url"])
            
        except Exception as e:
            print(f"  [!] Failed to save or log produced article '{art.get('title')}': {e}")
            

    # 2. Poison Pill / Failed Article Logging
    # Find articles that were in triaged candidates but NOT produced successfully
    for cand in triaged_articles:
        cand_url = cand.get("url")
        if cand_url and cand_url not in successful_urls:
            # Check secondary sources too
            is_secondary_success = False
            if cand.get("is_merged") and cand.get("secondary_sources"):
                for sec in cand["secondary_sources"]:
                    if sec.get("url") in successful_urls:
                        is_secondary_success = True
                        break
            if is_secondary_success:
                continue
                
            source_key = cand.get("source_key", "unknown")
            hm.log_url(cand_url, source_key, "FAILED_OR_ABANDONED")
            print(f"  [!] Logged failed/abandoned article in history: {cand_url}")
            
            # Also log secondary sources of failed/abandoned main candidates
            if cand.get("is_merged") and cand.get("secondary_sources"):
                for sec in cand["secondary_sources"]:
                    sec_url = sec.get("url")
                    if sec_url:
                        sec_source_key = sec.get("source_key", source_key)
                        hm.log_url(sec_url, sec_source_key, "FAILED_OR_ABANDONED")

    # 2.5 Update the persistent backlog archive file (data/1/2/archive.json)
    just_cleaned_path = os.path.join(get_state_dir(), f"tmp/{scope}/just_cleaned.json")
    just_cleaned_list = []
    if os.path.exists(just_cleaned_path):
        try:
            with open(just_cleaned_path, 'r', encoding='utf-8') as f:
                just_cleaned_list = json.load(f)
        except:
            pass
            
    hm.update_backlog(just_cleaned_list, successful_urls)

    # 3. Clean up raw crawled HTML cache
    raw_html_dir = os.path.join(get_state_dir(), f"tmp/{scope}/raw")
    if os.path.exists(raw_html_dir):
        print("  - Cleaning up temporary raw crawl directory...")
        try:
            shutil.rmtree(raw_html_dir)
            os.makedirs(raw_html_dir, exist_ok=True)
            print("  [+] Cleaned raw HTML cache.")
        except Exception as e:
            print(f"    [!] Error cleaning {raw_html_dir}: {e}")
            
    # 4. Prune older history to keep files lightweight
    print("  - Pruning old history entries...")
    try:
        hm.prune(url_days_limit=7, topic_days_limit=3)
        print("  [+] Pruning complete.")
    except Exception as e:
        print(f"    [!] Error pruning history: {e}")
        
    # 5. Output Orchestrator Callback JSON Status File
    summary_path = os.path.join(get_state_dir(), f"tmp/{scope}/sync_summary.json")
    summary = {
        "status": "success",
        "processed_count": len(produced_articles),
        "timestamp": datetime.now().isoformat(),
        "files_written": [f"{date_prefix}-{slugify(art['title'])}.md" for art in produced_articles]
    }
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=4)
        
    print(f"\n>>> Phase 5 Complete. Status summary written to '{summary_path}'")

if __name__ == "__main__":
    main()

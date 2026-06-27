#!/usr/bin/env python3
import json
import os
import sys
import requests
import time
from datetime import datetime, timedelta

# Setup absolute import pathing
from utils.common import ensure_dirs, get_scope
from utils.history_manager import HistoryManager

import importlib.util
import glob

EXTRACTORS = {}



def load_extractors(root_dir):
    global EXTRACTORS
    scope = get_scope()
    if scope == "international":
        scope = "global"
    
    engine_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cleaners_pattern = os.path.join(engine_dir, "cleaners", scope, "extract_*.py")
    for file_path in glob.glob(cleaners_pattern):
        module_name = os.path.splitext(os.path.basename(file_path))[0]
        try:
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            
            for attr_name in dir(module):
                if attr_name.startswith("extract_"):
                    func = getattr(module, attr_name)
                    key = attr_name.replace("extract_", "")
                    if key == "arunachaltimes":
                        key = "arunachal"
                    EXTRACTORS[key] = func
        except Exception as e:
            print(f"[!] Error loading dynamic extractor from {file_path}: {e}")


def clean_article(cand, root_dir, hm):
    """Downloads raw HTML and runs the cleaner extractor. Returns clean JSON data or None."""
    s_key = cand["source_key"]
    title = cand["title"]
    url = cand["url"]
    
    # Generate clean filename slugs
    slug = title.replace(" ", "-").lower()
    slug = "".join(x for x in slug if x.isalnum() or x == "-")[:80]
    scope = get_scope()
    
    # Setup directories
    os.makedirs(os.path.join(root_dir, f"data/{scope}/cleaned/{s_key}"), exist_ok=True)
    raw_dir = os.path.join(root_dir, f"tmp/{scope}/raw/{s_key}")
    os.makedirs(raw_dir, exist_ok=True)
    raw_path = os.path.join(raw_dir, f"{slug}.html")
    clean_path = os.path.join(root_dir, f"data/{scope}/cleaned/{s_key}/{slug}.json")
    
    try:
        # Download HTML
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=15)
        res.raise_for_status()
        with open(raw_path, 'w', encoding='utf-8') as f:
            f.write(res.text)
            
        # Extract content
        extractor = EXTRACTORS.get(s_key)
        if not extractor:
            print(f"      [!] No extractor found for {s_key}.")
            return None
            
        status = extractor(raw_path, clean_path)
        
        # Clean raw html file
        try:
            os.remove(raw_path)
        except:
            pass
            
        if status == "Success":
            # Load cleaned JSON and inject config metadata
            with open(clean_path, 'r', encoding='utf-8') as f:
                clean_data = json.load(f)
            clean_data["source_name"] = cand["source_name"]
            clean_data["source_key"] = cand["source_key"]
            clean_data["category"] = cand["category"]
            clean_data["url"] = url
            clean_data["clean_path"] = clean_path
            clean_data["cleaned_at"] = datetime.now().isoformat()
            
            with open(clean_path, 'w', encoding='utf-8') as f:
                json.dump(clean_data, f, indent=4)
                
            return clean_data
        else:
            print(f"      [!] Extraction failed for {url}: {status}")
            hm.log_url(url, s_key, "FAILED_OR_ABANDONED")
            return None
    except Exception as e:
        print(f"      [!] Cleaning error for {url}: {e}")
        hm.log_url(url, s_key, "FAILED_OR_ABANDONED")
        return None

def main():
    print("\n>>> Running Job 1.2: Candidate Pre-Cleaning & Backlog Compilation")
    # Find repository root / workspace root
    root_dir = os.environ.get("SCOUT_WORKSPACE", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    scope = get_scope()
    
    # Load dynamic cleaner functions
    load_extractors(root_dir)
    
    # 1.2.1 [Import] Discovered URLs
    hm = HistoryManager(root_dir)
    discovered_path = os.path.join(root_dir, f'tmp/{scope}/discovered_urls.json')
        
    discovered_urls = []
    if os.path.exists(discovered_path):
        with open(discovered_path, 'r', encoding='utf-8') as f:
            discovered_urls = json.load(f)
        
    just_cleaned = []
    
    # Clean only new discovered feeds
    if discovered_urls:
        print(f"[*] Found {len(discovered_urls)} new URLs to clean.")
        for cand in discovered_urls:
            if hm.is_url_processed(cand['url'], cand['source_key']):
                continue
            print(f"  - Cleaning: '{cand['title'][:50]}...'")
            cleaned_res = clean_article(cand, root_dir, hm)
            if cleaned_res:
                just_cleaned.append(cleaned_res)
                
    # 1.2.6 [Compile New]: Save newly cleaned queue to tmp/just_cleaned.json
    just_cleaned_path = os.path.join(root_dir, f'tmp/{scope}/just_cleaned.json')
    with open(just_cleaned_path, 'w', encoding='utf-8') as f:
        json.dump(just_cleaned, f, indent=4)
        
    # 1.2.7 [Scan Cache & Filter Archive]: Load the state archive ledger or scan for older active ones
    archive_state_path = hm.archive_path  # history/{scope}/archive.json (matches HistoryManager write path)
    archive_list = []
    if os.path.exists(archive_state_path):
        try:
            with open(archive_state_path, 'r', encoding='utf-8') as f:
                archive_list = json.load(f)
        except Exception as e:
            print(f"[!] Failed to load archive ledger: {e}. Rebuilding.")
            
    # Filter archive down to < 48 hours old and NOT processed/failed
    cutoff_time = datetime.now() - timedelta(hours=48)
    
    active_archive = []
    for art in archive_list:
        if hm.is_url_processed(art['url'], art['source_key']):
            continue
        try:
            cleaned_time = datetime.fromisoformat(art.get('cleaned_at', datetime.now().isoformat()))
            if cleaned_time >= cutoff_time:
                active_archive.append(art)
        except:
            # Fallback if parsing fails, assume fresh
            active_archive.append(art)
            
    # 1.2.9 [Save Archive]: Save active backlog to tmp/cleaned_archive.json
    cleaned_archive_path = os.path.join(root_dir, f'tmp/{scope}/cleaned_archive.json')
    with open(cleaned_archive_path, 'w', encoding='utf-8') as f:
        json.dump(active_archive, f, indent=4)
        
    # 1.2.10 [Merge Pools]: Create clean_candidates payload with structured new/old groups
    candidates_payload = {
        "new_candidates": just_cleaned,
        "archived_candidates_last_48h": active_archive
    }
    
    cleaned_candidates_path = os.path.join(root_dir, f'tmp/{scope}/cleaned_candidates.json')
    with open(cleaned_candidates_path, 'w', encoding='utf-8') as f:
        json.dump(candidates_payload, f, indent=4)
        
    print(f">>> Job 1.2 Complete. Newly Sourced: {len(just_cleaned)} | Archive Backlog: {len(active_archive)}")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
import json
import os
import sys
import requests
import xml.etree.ElementTree as ET
from datetime import datetime

# Setup absolute import pathing
from utils.common import load_source_history, ensure_dirs

BLACKLIST = [
    "teer", "lottery", "result today", "satta", "sambad", 
    "lucky number", "chart", "gold rate", "silver rate",
    "horoscope", "zodiac"
]

def load_scope():
    return os.environ.get('SCOUT_SCOPE', 'local')

def fetch_rss(source_key, source_config):
    """Fetches RSS and returns a list of candidate articles."""
    workspace_dir = os.environ.get("SCOUT_WORKSPACE", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    print(f"  - Fetching RSS for: {source_config['name']}...")
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(source_config['url'], headers=headers, timeout=15)
        response.raise_for_status()
        
        # Save raw XML summary to data/{scope}/1/ for audit trail
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        raw_rss_path = os.path.join(workspace_dir, f"data/{scope}/rss/{source_key}_{timestamp}.rss")
        os.makedirs(os.path.dirname(raw_rss_path), exist_ok=True)
        with open(raw_rss_path, 'wb') as f:
            f.write(response.content)
            
        root = ET.fromstring(response.content)
        candidates = []
        items = root.findall('.//item')
        if items is None or len(items) == 0:
            items = root.findall('.//{http://www.w3.org/2005/Atom}entry')
        
        for item in items[:20]:
            title_node = item.find('title')
            if title_node is None:
                title_node = item.find('{http://www.w3.org/2005/Atom}title')
            link_node = item.find('link')
            if link_node is None:
                link_node = item.find('{http://www.w3.org/2005/Atom}link')
            
            title = title_node.text if title_node is not None else ""
            link = ""
            if link_node is not None:
                link = link_node.text or link_node.get('href') or ""

            if not title or not link: 
                continue

            # Blacklist Filter
            if any(word in title.lower() for word in BLACKLIST):
                continue

            candidates.append({
                "title": title,
                "url": link,
                "source_key": source_key,
                "source_name": source_config['name'],
                "category": source_config['category']
            })
        return candidates
    except Exception as e:
        print(f"    [!] Error checking RSS for {source_key}: {e}")
        return []

def main():
    print("\n>>> Running Step 1/1: Feed Discovery (RSS Pull & Log)")
    # Find repository root / workspace root
    root_dir = os.environ.get("SCOUT_WORKSPACE", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    engine_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    scope = load_scope()
    print(f"[*] Target scope configured: {scope}")
    
    sources_path = os.path.join(root_dir, f'data/{scope}/sources.json')
    if not os.path.exists(sources_path):
        print(f"[!] Error: sources config file missing: {sources_path}")
        sys.exit(1)
        
    with open(sources_path, 'r', encoding='utf-8') as f:
        sources = json.load(f)
        
    discovered_urls = []
    
    for s_key, s_cfg in sources.items():
        # Filter by scope category
        feed_category = s_cfg.get("category", "Local").lower()
        if feed_category == "global": feed_category = "international"
        if feed_category != scope.lower():
            continue
            
        # Validate Cleaner script pointer exists in the engine's cleaners directory
        cleaner_name = s_cfg.get("cleaner_filename", f"extract_{s_key}.py")
        cleaner_scope = scope.lower()
        if cleaner_scope == "international":
            cleaner_scope = "global"
        cleaner_path = os.path.join(engine_dir, "cleaners", cleaner_scope, cleaner_name)
        if not os.path.exists(cleaner_path):
            print(f"  [!] Warning: Cleaner script '{cleaner_path}' missing. Skipping fetch for {s_cfg['name']}.")
            continue
            
        # Check RSS feed
        # Update fetch_rss to write raw rss summaries relative to root
        print(f"  - Fetching RSS for: {s_cfg['name']}...")
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(s_cfg['url'], headers=headers, timeout=15)
            response.raise_for_status()
            
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            raw_rss_path = os.path.join(root_dir, f"data/{scope}/rss/{s_key}_{timestamp}.rss")
            os.makedirs(os.path.dirname(raw_rss_path), exist_ok=True)
            with open(raw_rss_path, 'wb') as f:
                f.write(response.content)
                
            root = ET.fromstring(response.content)
            candidates = []
            items = root.findall('.//item') or root.findall('.//{http://www.w3.org/2005/Atom}entry')
            
            for item in items[:20]:
                title_node = item.find('title')
                if title_node is None:
                    title_node = item.find('{http://www.w3.org/2005/Atom}title')
                    
                link_node = item.find('link')
                if link_node is None:
                    link_node = item.find('{http://www.w3.org/2005/Atom}link')
                
                title = title_node.text if title_node is not None else ""
                link = ""
                if link_node is not None:
                    link = link_node.text or link_node.get('href') or ""
                
                if not title or not link:
                    continue
                
                if any(word in title.lower() for word in BLACKLIST):
                    continue
                
                candidates.append({
                    "title": title,
                    "url": link,
                    "source_key": s_key,
                    "source_name": s_cfg['name'],
                    "category": s_cfg['category']
                })
        except Exception as e:
            print(f"    [!] Error checking RSS for {s_key}: {e}")
            candidates = []
        
        # Filter against technical url history
        history = load_source_history(s_key)
        processed_urls = {item["url"] for item in history}
        
        new_candidates = []
        for cand in candidates:
            if cand['url'] not in processed_urls:
                new_candidates.append(cand)
                
        if new_candidates:
            print(f"    [+] Found {len(new_candidates)} fresh articles for {s_cfg['name']}.")
            discovered_urls.extend(new_candidates)
            
    # Write discovered urls list to tmp index relative to root
    tmp_dir = os.path.join(root_dir, f'tmp/{scope}')
    os.makedirs(tmp_dir, exist_ok=True)
    with open(os.path.join(tmp_dir, 'discovered_urls.json'), 'w', encoding='utf-8') as f:
        json.dump(discovered_urls, f, indent=4)
        
    print(f">>> Step 1/1 Complete. Discovered {len(discovered_urls)} fresh URLs.")

if __name__ == "__main__":
    main()

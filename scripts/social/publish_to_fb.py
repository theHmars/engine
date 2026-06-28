#!/usr/bin/env python3
import os
import sys
import json
import time
import requests
from dotenv import load_dotenv

current_dir = os.path.dirname(os.path.abspath(__file__))
engine_root = os.path.dirname(os.path.dirname(current_dir))
scripts_dir = os.path.join(engine_root, "scripts")
if scripts_dir not in sys.path:
    sys.path.insert(0, scripts_dir)
from utils.common import get_state_dir
tmp_dir = get_state_dir()

# Load environment
env_paths = [
    os.path.join(engine_root, '.env'),
    os.path.join(os.path.dirname(engine_root), 'frontend', '.env')
]
for env_path in env_paths:
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if line.strip() and not line.startswith("#") and "=" in line:
                    key, val = line.strip().split("=", 1)
                    if key not in os.environ:
                        os.environ[key] = val.replace('"', '').replace("'", "")

PAGE_ID = os.environ.get("FB_PAGE_ID")
ACCESS_TOKEN = os.environ.get("FB_PAGE_ACCESS_TOKEN")
API_VERSION = "v20.0"
BASE_URL = f"https://graph.facebook.com/{API_VERSION}"

def publish_single_post(article, publish_time):
    url = f"{BASE_URL}/{PAGE_ID}/feed"
    article_url = f"https://thehmars-news.onrender.com/{article['slug']}"
    message = f"{article['title']}\n\n{article['summary']}\n\nRead more: {article_url}"
    payload = {
        "message": message, 
        "link": article_url, 
        "access_token": ACCESS_TOKEN,
        "published": "false",
        "scheduled_publish_time": str(int(publish_time))
    }
    
    try:
        test_mode = os.environ.get("TEST_MODE_SOCIAL")
        if test_mode == "true":
            print(f"  [TEST MODE SOCIAL] Would have scheduled '{article['title'][:30]}...' for {time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(publish_time))} UTC.")
            return True
            
        response = requests.post(url, data=payload, timeout=15)
        if response.status_code == 200:
            post_id = response.json().get("id")
            print(f"  [+] Facebook Scheduled: '{article['title'][:30]}...' for {time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(publish_time))} UTC. (Post ID: {post_id})")
            return True
        elif response.status_code in [400, 401, 403]:
            print(f"  [FATAL] Facebook API credential/permission error ({response.status_code}): {response.text}")
            print(f"  [FATAL] Aborting queue — all remaining posts would fail with the same error.")
            raise SystemExit(1)
        else:
            print(f"  [!] Failed to publish to Facebook: HTTP {response.status_code} - {response.text}")
    except SystemExit:
        raise
    except Exception as e:
        print(f"  [!] Network error sending post to Facebook: {e}")
    return False

def main():
    print("[*] Running publish_to_fb.py...")
    
    list_path = os.path.join(tmp_dir, "list.json")
    curated_path = os.path.join(tmp_dir, "curated_ids.json")
    pre_queue_path = os.path.join(tmp_dir, "pre_queue.json")
    meta_path = os.path.join(tmp_dir, "metadata.json")
    
    if not all(os.path.exists(p) for p in [list_path, curated_path, pre_queue_path, meta_path]):
        print("[!] Error: Missing required JSON artifacts in tmp/. Aborting Facebook publish.")
        sys.exit(1)
        
    with open(list_path, 'r') as f:
        all_candidates = json.load(f)
    with open(curated_path, 'r') as f:
        winning_ids = json.load(f)
    with open(pre_queue_path, 'r') as f:
        queue_data = json.load(f)
    with open(meta_path, 'r') as f:
        meta = json.load(f)
        
    if not PAGE_ID or not ACCESS_TOKEN:
        print("[!] Error: Missing FB_PAGE_ID or FB_PAGE_ACCESS_TOKEN in environment.")
        sys.exit(1)
        
    anchor = queue_data["anchor_utc"]
    gap = meta["gap_minutes"] * 60
    
    print(f"[*] Scheduling {len(winning_ids)} posts to Facebook starting from Anchor...")
    
    success_count = 0
    for win_id in winning_ids:
        article = next((c for c in all_candidates if c["id"] == win_id), None)
        if not article:
            continue
            
        publish_time = anchor + gap
        if publish_single_post(article, publish_time):
            success_count += 1
            
        anchor = publish_time

    print(f"[+] Successfully scheduled {success_count}/{len(winning_ids)} posts to Facebook.")

if __name__ == "__main__":
    main()

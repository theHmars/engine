#!/usr/bin/env python3
import os
import sys
import json
import time
import requests

# Load environment configuration
current_dir = os.path.dirname(os.path.abspath(__file__))
engine_root = os.path.dirname(os.path.dirname(current_dir))
scripts_dir = os.path.join(engine_root, "scripts")
if scripts_dir not in sys.path:
    sys.path.insert(0, scripts_dir)
from utils.common import get_state_dir

# Try engine/.env first, then fallback to frontend/.env
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

def get_queue_status():
    if not PAGE_ID or not ACCESS_TOKEN:
        print("[!] Error: Missing FB_PAGE_ID or FB_PAGE_ACCESS_TOKEN in environment.")
        sys.exit(1)
        
    print(f"[*] Pre-Queue Check: Fetching scheduled posts for Page {PAGE_ID}...")
    url = f"{BASE_URL}/{PAGE_ID}/scheduled_posts"
    params = {
        "access_token": ACCESS_TOKEN,
        "fields": "scheduled_publish_time",
        "limit": 100
    }
    
    max_timestamp = None
    total_posts = 0
    max_attempts = 3
    
    for attempt in range(1, max_attempts + 1):
        try:
            while True:
                response = requests.get(url, params=params, timeout=15)
                if response.status_code == 200:
                    data = response.json().get("data", [])
                    if not data:
                        break
                    
                    total_posts += len(data)
                    
                    timestamps = [int(p["scheduled_publish_time"]) for p in data if "scheduled_publish_time" in p]
                    if timestamps:
                        batch_max = max(timestamps)
                        if max_timestamp is None or batch_max > max_timestamp:
                            max_timestamp = batch_max
                            
                    paging = response.json().get("paging", {})
                    next_url = paging.get("next")
                    if next_url:
                        url = next_url
                        params = {}
                    else:
                        break
                else:
                    print(f"  [!] Error checking scheduled posts (HTTP {response.status_code}): {response.text}")
                    break
            break  # Successful run — exit retry loop
        except Exception as e:
            print(f"  [!] Exception checking scheduled posts (attempt {attempt}/{max_attempts}): {e}")
            if attempt < max_attempts:
                print(f"  [!] Retrying in 15 seconds...")
                time.sleep(15)
            else:
                print(f"  [!] All {max_attempts} attempts exhausted. Aborting publisher.")
                sys.exit(1)
        
    return total_posts, max_timestamp

def main():
    total_posts, max_timestamp = get_queue_status()
    print(f"[+] Found {total_posts} posts currently scheduled on Facebook.")
    
    # Safety Valve: If more than 10 posts, the queue is bloated. Wipe it clean.
    if total_posts > 10:
        print(f"[!] DANGER: Queue has {total_posts} scheduled posts. Wiping the queue for a fresh start...")
        import subprocess
        clear_script = os.path.join(current_dir, "clear_queue.py")
        subprocess.run(["python3", clear_script], check=True)
        print("[+] Queue wiped successfully.")
        
        # Reset our state as if the queue is empty
        total_posts = 0
        max_timestamp = None
        
    if max_timestamp:
        # Give a 15 min safety buffer on top of the last queue to avoid overlap
        anchor_time = max_timestamp
        print(f"[+] Existing queue found. Setting anchor to tail: {time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(anchor_time))} UTC")
    else:
        # If queue is totally empty, start 15 minutes from right now
        anchor_time = int(time.time()) + (15 * 60)
        print(f"[+] Queue is empty. Setting anchor to 15 mins from now: {time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(anchor_time))} UTC")
        
    output_data = {
        "on_queue": total_posts,
        "anchor_utc": anchor_time
    }
    
    TMP_DIR = get_state_dir()
    os.makedirs(TMP_DIR, exist_ok=True)
    out_path = os.path.join(TMP_DIR, "pre_queue.json")
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=4)
        
    print(f"[+] Exported anchor data to {out_path}")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
import os
import sys
import time
import requests

# Load environment configuration
PAGE_ID = os.environ.get("FB_PAGE_ID")
ACCESS_TOKEN = os.environ.get("FB_PAGE_ACCESS_TOKEN")
API_VERSION = "v20.0"
BASE_URL = f"https://graph.facebook.com/{API_VERSION}"

def check_queue():
    if not PAGE_ID or not ACCESS_TOKEN:
        print("[!] Error: Missing FB_PAGE_ID or FB_PAGE_ACCESS_TOKEN in environment.")
        sys.exit(1)
        
    print(f"[*] Checking scheduled posts queue for Page: {PAGE_ID}...")
    url = f"{BASE_URL}/{PAGE_ID}/scheduled_posts"
    params = {
        "access_token": ACCESS_TOKEN,
        "fields": "id,scheduled_publish_time,message",
        "limit": 100
    }
    
    try:
        all_posts = []
        while url:
            response = requests.get(url, params=params, timeout=15)
            if response.status_code == 200:
                data = response.json().get("data", [])
                all_posts.extend(data)
                
                # Check for next page
                paging = response.json().get("paging", {})
                next_url = paging.get("next")
                if next_url:
                    url = next_url
                    params = {} # next_url includes access_token and cursors
                else:
                    break
            else:
                print(f"[!] Error fetching scheduled posts (HTTP {response.status_code}): {response.text}")
                break
                
        if not all_posts:
            print("[+] Queue is empty. No scheduled posts found.")
            return
        
        print(f"[+] Found {len(all_posts)} scheduled post(s):")
        for idx, post in enumerate(all_posts, 1):
            pub_time = int(post.get("scheduled_publish_time", 0))
            readable_time = time.strftime('%Y-%m-%d %I:%M:%S %p', time.localtime(pub_time))
            print(f"\n--- Post #{idx} ---")
            print(f"ID: {post.get('id')}")
            print(f"Scheduled for: {readable_time} (Timestamp: {pub_time})")
            print(f"Message preview:\n{post.get('message', '')[:120]}...")
    except Exception as e:
        print(f"[!] Request failed: {e}")

if __name__ == "__main__":
    # If script runs locally in developer workspace, try to load .env automatically
    env_path = "/home/phxlm/Work/websites/theHmars/frontend/.env"
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if line.strip() and not line.startswith("#") and "=" in line:
                    key, val = line.strip().split("=", 1)
                    os.environ[key] = val.replace('"', '').replace("'", "")
                    
        # Re-read loaded variables
        PAGE_ID = os.environ.get("FB_PAGE_ID")
        ACCESS_TOKEN = os.environ.get("FB_PAGE_ACCESS_TOKEN")
        
    check_queue()

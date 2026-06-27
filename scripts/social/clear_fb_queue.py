#!/usr/bin/env python3
import os
import sys
import requests

# Load environment configuration
PAGE_ID = os.environ.get("FB_PAGE_ID")
ACCESS_TOKEN = os.environ.get("FB_PAGE_ACCESS_TOKEN")
API_VERSION = "v20.0"
BASE_URL = f"https://graph.facebook.com/{API_VERSION}"

def clear_queue():
    if not PAGE_ID or not ACCESS_TOKEN:
        print("[!] Error: Missing FB_PAGE_ID or FB_PAGE_ACCESS_TOKEN in environment.")
        sys.exit(1)
        
    print(f"[*] Fetching scheduled posts to delete for Page: {PAGE_ID}...")
    url = f"{BASE_URL}/{PAGE_ID}/scheduled_posts"
    params = {
        "access_token": ACCESS_TOKEN,
        "fields": "id",
        "limit": 100
    }
    
    try:
        total_deleted = 0
        while True:
            response = requests.get(url, params=params, timeout=15)
            if response.status_code == 200:
                posts = response.json().get("data", [])
                if not posts:
                    break
                
                print(f"[!] Found {len(posts)} scheduled post(s) in this batch. Proceeding with deletion...")
                for post in posts:
                    post_id = post.get("id")
                    delete_url = f"{BASE_URL}/{post_id}"
                    del_payload = {"access_token": ACCESS_TOKEN}
                    
                    del_response = requests.delete(delete_url, data=del_payload, timeout=15)
                    if del_response.status_code == 200 and del_response.json().get("success"):
                        print(f"  [+] Deleted scheduled post ID: {post_id}")
                        total_deleted += 1
                    else:
                        print(f"  [!] Failed to delete post ID: {post_id} (HTTP {del_response.status_code}: {del_response.text})")
            else:
                print(f"[!] Error fetching scheduled posts (HTTP {response.status_code}): {response.text}")
                break
                
        print(f"\n[+] Finished. Successfully deleted a total of {total_deleted} post(s).")
    except Exception as e:
        print(f"[!] Request failed: {e}")

if __name__ == "__main__":
    # If script runs locally in developer workspace, try to load .env automatically
    env_path = ".env"
    if not os.path.exists(env_path) and os.path.exists("../.env"):
        env_path = "../.env"
        
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if line.strip() and not line.startswith("#") and "=" in line:
                    key, val = line.strip().split("=", 1)
                    os.environ[key] = val.replace('"', '').replace("'", "")
                    
        # Re-read loaded variables
        PAGE_ID = os.environ.get("FB_PAGE_ID")
        ACCESS_TOKEN = os.environ.get("FB_PAGE_ACCESS_TOKEN")
        
    # Double check confirmation if running interactively
    if sys.stdin.isatty():
        confirm = input("[?] Are you sure you want to delete ALL scheduled Facebook posts? (y/N): ")
        if confirm.lower() != 'y':
            print("[-] Cancelled.")
            sys.exit(0)
            
    clear_queue()

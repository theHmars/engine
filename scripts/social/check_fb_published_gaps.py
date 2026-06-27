#!/usr/bin/env python3
import os
import sys
import time
from datetime import datetime
import requests

# Load environment configuration
def load_environment():
    env_path = ".env"
    if not os.path.exists(env_path) and os.path.exists("../.env"):
        env_path = "../.env"
        
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if line.strip() and not line.startswith("#") and "=" in line:
                    key, val = line.strip().split("=", 1)
                    os.environ[key] = val.replace('"', '').replace("'", "")

load_environment()

PAGE_ID = os.environ.get("FB_PAGE_ID")
ACCESS_TOKEN = os.environ.get("FB_PAGE_ACCESS_TOKEN")
API_VERSION = "v20.0"
BASE_URL = f"https://graph.facebook.com/{API_VERSION}"

if not PAGE_ID or not ACCESS_TOKEN:
    print("[!] Error: Missing FB_PAGE_ID or FB_PAGE_ACCESS_TOKEN.")
    sys.exit(1)

def fetch_published_posts(limit=150):
    url = f"{BASE_URL}/{PAGE_ID}/posts"
    params = {
        "access_token": ACCESS_TOKEN,
        "fields": "id,message,created_time",
        "limit": 100
    }
    
    posts = []
    try:
        while url and len(posts) < limit:
            res = requests.get(url, params=params, timeout=15)
            if res.status_code != 200:
                print(f"[!] Error fetching posts (HTTP {res.status_code}): {res.text}")
                break
            
            data = res.json()
            batch = data.get("data", [])
            if not batch:
                break
                
            posts.extend(batch)
            
            # Pagination
            paging = data.get("paging", {})
            url = paging.get("next")
            params = {} # params are in next url
    except Exception as e:
        print(f"[!] Request failed: {e}")
        
    return posts

def analyze_gaps():
    print(f"[*] Fetching published posts for Page ID: {PAGE_ID}...")
    posts = fetch_published_posts(200)
    print(f"[+] Retrieved {len(posts)} posts.")
    
    if not posts:
        print("[-] No posts retrieved.")
        return
        
    # Sort posts chronologically (oldest first)
    parsed_posts = []
    for p in posts:
        created_str = p.get("created_time")
        if not created_str:
            continue
            
        # Parse ISO 8601 string (e.g. 2026-06-25T12:00:00+0000)
        # Handle timezone suffix
        clean_time_str = created_str.replace("+0000", "Z")
        try:
            dt = datetime.strptime(clean_time_str, "%Y-%m-%dT%H:%M:%S%z")
        except ValueError:
            dt = datetime.strptime(clean_time_str, "%Y-%m-%dT%H:%M:%SZ")
            
        parsed_posts.append({
            "id": p.get("id"),
            "message": p.get("message", "").replace("\n", " ")[:60],
            "time": dt,
            "timestamp": int(dt.timestamp())
        })
        
    parsed_posts.sort(key=lambda x: x["timestamp"])
    
    print("\n" + "="*80)
    print(f"{'Publication Time (UTC)':<25} | {'Gap (min)':<10} | {'Post Snippet'}")
    print("="*80)
    
    for i in range(len(parsed_posts)):
        current = parsed_posts[i]
        time_str = current["time"].strftime("%Y-%m-%d %H:%M:%S")
        
        if i == 0:
            gap_str = "N/A"
        else:
            prev = parsed_posts[i-1]
            diff_seconds = current["timestamp"] - prev["timestamp"]
            diff_minutes = diff_seconds / 60.0
            gap_str = f"{diff_minutes:.1f}"
            
        print(f"{time_str:<25} | {gap_str:<10} | {current['message']}")
        
    print("="*80)

if __name__ == "__main__":
    analyze_gaps()

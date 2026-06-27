#!/usr/bin/env python3
import os
import sys
import time
from datetime import datetime, timedelta, timezone
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

def fetch_all_published_posts(limit=500):
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
            params = {}
    except Exception as e:
        print(f"[!] Request failed: {e}")
        
    return posts

def generate_report():
    print(f"[*] Fetching published posts...")
    posts = fetch_all_published_posts(500)
    print(f"[+] Retrieved {len(posts)} posts. Parsing and analyzing...")
    
    if not posts:
        print("[-] No posts found.")
        return

    # Parse and sort chronologically (oldest first)
    parsed_posts = []
    local_tz = timezone(timedelta(hours=5, minutes=30)) # UTC+5:30 (IST)
    
    for p in posts:
        created_str = p.get("created_time")
        if not created_str:
            continue
            
        clean_time_str = created_str.replace("+0000", "Z")
        try:
            dt_utc = datetime.strptime(clean_time_str, "%Y-%m-%dT%H:%M:%S%z")
        except ValueError:
            dt_utc = datetime.strptime(clean_time_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            
        dt_local = dt_utc.astimezone(local_tz)
        
        # Clean title (first line of the message)
        message = p.get("message", "")
        title = message.split("\n")[0] if message else "[No Content]"
        if len(title) > 65:
            title = title[:62] + "..."
            
        parsed_posts.append({
            "id": p.get("id"),
            "title": title,
            "utc_time": dt_utc,
            "local_time": dt_local,
            "timestamp": int(dt_utc.timestamp())
        })
        
    parsed_posts.sort(key=lambda x: x["timestamp"])
    
    report_path = "published_posts_report.txt"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("="*140 + "\n")
        f.write(f"{'No.':<4} | {'UTC Date/Time':<20} | {'IST Date/Time (Local)':<22} | {'Gap (min)':<10} | {'Title/Snippet'}\n")
        f.write("="*140 + "\n")
        
        for i, post in enumerate(parsed_posts, 1):
            utc_str = post["utc_time"].strftime("%Y-%m-%d %H:%M:%S")
            local_str = post["local_time"].strftime("%Y-%m-%d %H:%M:%S")
            
            if i == 1:
                gap_str = "N/A"
            else:
                prev = parsed_posts[i-2]
                diff_seconds = post["timestamp"] - prev["timestamp"]
                diff_minutes = diff_seconds / 60.0
                gap_str = f"{diff_minutes:.1f}"
                
            f.write(f"{i:<4} | {utc_str:<20} | {local_str:<22} | {gap_str:<10} | {post['title']}\n")
            
        f.write("="*140 + "\n")
        f.write(f"Report generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (Local Time)\n")
        
    print(f"[+] Report successfully written to {report_path}")

if __name__ == "__main__":
    generate_report()

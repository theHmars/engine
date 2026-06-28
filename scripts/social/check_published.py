#!/usr/bin/env python3
import os
import sys
import time
import json
import requests
import argparse

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

def check_published():
    parser = argparse.ArgumentParser(description="Export published FB feed to JSON")
    parser.add_argument("--all", action="store_true", help="Include legacy posts with thehmars.onrender.com URLs")
    args = parser.parse_args()

    if not PAGE_ID or not ACCESS_TOKEN:
        print("[!] Error: Missing FB_PAGE_ID or FB_PAGE_ACCESS_TOKEN in environment.")
        sys.exit(1)
        
    print(f"[*] Checking published feed posts for Page: {PAGE_ID}...")
    url = f"{BASE_URL}/{PAGE_ID}/feed"
    params = {
        "access_token": ACCESS_TOKEN,
        "fields": "id,created_time,message,attachments{url,unshimmed_url,target}",
        "limit": 100
    }
    
    try:
        all_posts = []
        page_count = 0
        # Let's limit to 10 pages (1000 posts) to avoid massive outputs
        while url and page_count < 10:
            response = requests.get(url, params=params, timeout=15)
            if response.status_code == 200:
                data = response.json().get("data", [])
                
                for post in data:
                    if not args.all:
                        has_old_url = False
                        # Check attachments
                        attachments = post.get("attachments", {}).get("data", [])
                        for att in attachments:
                            url = att.get("unshimmed_url", "") or att.get("url", "") or att.get("target", {}).get("url", "")
                            if "thehmars.onrender.com" in url:
                                has_old_url = True
                                break
                                
                        # Check message body
                        if not has_old_url and "thehmars.onrender.com" in post.get("message", ""):
                            has_old_url = True
                            
                        if has_old_url:
                            continue
                            
                    all_posts.append(post)
                
                # Check for next page
                paging = response.json().get("paging", {})
                next_url = paging.get("next")
                if next_url:
                    url = next_url
                    params = {} # next_url includes access_token and cursors
                    page_count += 1
                else:
                    break
            else:
                print(f"[!] Error fetching published posts (HTTP {response.status_code}): {response.text}")
                break
                
        if not all_posts:
            print("[+] Feed is empty. No published posts found.")
            return
        
        print(f"[+] Found {len(all_posts)} published post(s).")
        
        # Export to JSON
        workspace_dir = os.environ.get("SCOUT_WORKSPACE", os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))
        output_file = os.path.join(workspace_dir, "fb_published.json")
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(all_posts, f, indent=4)
            print(f"[+] Successfully exported published feed to: {output_file}")
        except Exception as e:
            print(f"[!] Failed to write to {output_file}: {e}")
            
    except Exception as e:
        print(f"[!] Request failed: {e}")

if __name__ == "__main__":
    check_published()

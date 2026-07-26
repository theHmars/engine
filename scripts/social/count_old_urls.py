#!/usr/bin/env python3
import os
import requests

def load_environment():
    env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.env"))
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if line.strip() and not line.startswith("#") and "=" in line:
                    key, val = line.strip().split("=", 1)
                    os.environ[key] = val.replace('"', '').replace("'", "")

if __name__ == "__main__":
    load_environment()

    PAGE_ID = os.environ.get("FB_PAGE_ID")
    ACCESS_TOKEN = os.environ.get("FB_PAGE_ACCESS_TOKEN")
    BASE_URL = "https://graph.facebook.com/v20.0"

    if not PAGE_ID or not ACCESS_TOKEN:
        print("[!] Error: Missing FB_PAGE_ID or FB_PAGE_ACCESS_TOKEN in environment.")
        exit(1)

    print(f"[*] Fetching Facebook Page ({PAGE_ID}) feed to count old URLs...")
    
    url = f"{BASE_URL}/{PAGE_ID}/feed"
    params = {
        "access_token": ACCESS_TOKEN,
        "fields": "message,attachments{url,unshimmed_url,target}",
        "limit": 100
    }

    count_old = 0
    total = 0
    
    while url:
        res = requests.get(url, params=params).json()
        data = res.get("data", [])
        if not data:
            break
        
        for post in data:
            total += 1
            has_old_url = False
            
            # Check message body
            msg = post.get("message", "")
            if "thehmars-news.onrender.com" in msg:
                has_old_url = True
            else:
                # Check link attachments
                atts = post.get("attachments", {}).get("data", [])
                for att in atts:
                    link = att.get("unshimmed_url", "") or att.get("url", "") or att.get("target", {}).get("url", "")
                    if "thehmars-news.onrender.com" in link:
                        has_old_url = True
                        break
            
            if has_old_url:
                count_old += 1
                
        # Pagination
        next_url = res.get("paging", {}).get("next")
        if next_url:
            url = next_url
            params = {}
        else:
            break

    print("-" * 40)
    print(f"Total posts checked: {total}")
    print(f"Posts with thehmars-news.onrender.com: {count_old}")
    print("-" * 40)

#!/usr/bin/env python3
import os
import requests
import json

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
        print("[!] Error: Missing credentials.")
        exit(1)

    url = f"{BASE_URL}/{PAGE_ID}/feed"
    params = {
        "access_token": ACCESS_TOKEN,
        "fields": "id,message,attachments{url,unshimmed_url,target}",
        "limit": 100
    }

    target_urls = []
    
    print(f"[*] Scanning Page {PAGE_ID} for posts with old URLs...")
    while url:
        res = requests.get(url, params=params).json()
        data = res.get("data", [])
        if not data:
            break
        
        for post in data:
            has_old_url = False
            msg = post.get("message", "")
            
            # Check message
            if "thehmars-news.onrender.com" in msg:
                has_old_url = True
            
            # Check attachments
            if not has_old_url:
                atts = post.get("attachments", {}).get("data", [])
                for att in atts:
                    link = att.get("unshimmed_url", "") or att.get("url", "") or att.get("target", {}).get("url", "")
                    if "thehmars-news.onrender.com" in link:
                        has_old_url = True
                        break
                        
            if has_old_url:
                # The direct URL format for a Page post is: https://www.facebook.com/PAGE_ID/posts/POST_ID
                # Sometimes post["id"] is "PAGEID_POSTID", we only want the POSTID part for the URL
                raw_id = post["id"]
                post_id = raw_id.split("_")[1] if "_" in raw_id else raw_id
                target_urls.append(f"https://www.facebook.com/{PAGE_ID}/posts/{post_id}")
                
        next_url = res.get("paging", {}).get("next")
        if next_url:
            url = next_url
            params = {}
        else:
            break

    output_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "target_post_urls.json"))
    with open(output_file, "w") as f:
        json.dump(target_urls, f, indent=4)
        
    print(f"[+] Found {len(target_urls)} posts requiring preview updates.")
    print(f"[+] Saved URLs to: {output_file}")

#!/usr/bin/env python3
import os
import time
import requests
import urllib.parse

OLD_DOMAIN = "thehmars-news.onrender.com"
NEW_DOMAIN = "thehmars.onrender.com"

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

    print(f"[*] Starting advanced bulk caption update for Page ID: {PAGE_ID}...")
    
    url = f"{BASE_URL}/{PAGE_ID}/feed"
    params = {
        "access_token": ACCESS_TOKEN,
        "fields": "id,message,attachments{url,unshimmed_url,target}",
        "limit": 100
    }

    updated_count = 0
    checked_count = 0
    
    while url:
        print("Fetching batch of 100 posts...")
        res = requests.get(url, params=params).json()
        data = res.get("data", [])
        
        if not data:
            break
        
        for post in data:
            checked_count += 1
            post_id = post["id"]
            msg = post.get("message", "")
            
            needs_update = False
            new_msg = msg
            
            if OLD_DOMAIN in msg:
                new_msg = new_msg.replace(OLD_DOMAIN, NEW_DOMAIN)
                needs_update = True
            
            # Also check if it is exclusively in the attachment
            atts = post.get("attachments", {}).get("data", [])
            for att in atts:
                link = att.get("unshimmed_url", "") or att.get("url", "") or att.get("target", {}).get("url", "")
                
                # unshimmed_url is the raw url, but if it's l.facebook.com we might need to parse it
                if "l.facebook.com/l.php" in link:
                    parsed = urllib.parse.urlparse(link)
                    query = urllib.parse.parse_qs(parsed.query)
                    if 'u' in query:
                        link = query['u'][0]
                        
                if OLD_DOMAIN in link:
                    clean_link = link.replace(OLD_DOMAIN, NEW_DOMAIN)
                    
                    # If the message doesn't already contain the clean link (or the old one), append it!
                    if NEW_DOMAIN not in new_msg:
                        # Append the link to the caption
                        new_msg = new_msg.strip() + f"\n\nRead more: {clean_link}"
                        needs_update = True
                    break
            
            if needs_update:
                update_url = f"{BASE_URL}/{post_id}"
                payload = {
                    "message": new_msg,
                    "access_token": ACCESS_TOKEN
                }
                
                try:
                    update_res = requests.post(update_url, data=payload).json()
                    if update_res.get("success"):
                        updated_count += 1
                    else:
                        print(f"  [!] Failed to update post {post_id}: {update_res}")
                except Exception as e:
                    print(f"  [!] Request error on post {post_id}: {e}")
                    
                time.sleep(0.5)
                
        next_url = res.get("paging", {}).get("next")
        if next_url:
            url = next_url
            params = {}
        else:
            break

    print("-" * 40)
    print(f"Total posts checked: {checked_count}")
    print(f"Total posts successfully updated: {updated_count}")
    print("-" * 40)

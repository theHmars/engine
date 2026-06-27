#!/usr/bin/env python3
import os
import requests
from dotenv import load_dotenv

# Load .env from frontend
frontend_env = "/home/phxlm/Work/websites/theHmars/frontend/.env"
load_dotenv(frontend_env)

PAGE_ID = os.environ.get("FB_PAGE_ID")
ACCESS_TOKEN = os.environ.get("FB_PAGE_ACCESS_TOKEN")
API_VERSION = "v20.0"
BASE_URL = f"https://graph.facebook.com/{API_VERSION}"

OLD_URL = "thehmars.onrender.com/"
NEW_URL = "thehmars-news.onrender.com/"

def update_posts(endpoint):
    url = f"{BASE_URL}/{PAGE_ID}/{endpoint}"
    params = {"access_token": ACCESS_TOKEN, "fields": "id,message", "limit": 100}
    
    count = 0
    while True:
        try:
            res = requests.get(url, params=params).json()
        except Exception as e:
            print(f"Error fetching {endpoint}: {e}")
            break
            
        data = res.get("data", [])
        if not data:
            break
            
        for post in data:
            message = post.get("message", "")
            post_id = post.get("id")
            if OLD_URL in message:
                new_message = message.replace(OLD_URL, NEW_URL)
                update_url = f"{BASE_URL}/{post_id}"
                payload = {"message": new_message, "access_token": ACCESS_TOKEN}
                up_res = requests.post(update_url, data=payload)
                if up_res.status_code == 200:
                    print(f"  [+] Updated post {post_id}")
                    count += 1
                else:
                    print(f"  [!] Failed to update {post_id}: {up_res.text}")
                    
        paging = res.get("paging", {})
        next_url = paging.get("next")
        if next_url:
            url = next_url
            params = {}
        else:
            break
            
    print(f"Total updated in {endpoint}: {count}")

if not PAGE_ID or not ACCESS_TOKEN:
    print("Missing FB credentials in .env")
    exit(1)

print("Checking published posts...")
update_posts("published_posts")

print("Checking scheduled posts...")
update_posts("scheduled_posts")

print("Checking feed...")
update_posts("feed")

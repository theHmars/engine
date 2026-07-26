#!/usr/bin/env python3
import os
import sys
import json
import re
import requests
import argparse
from urllib.parse import urlparse

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

def is_old_domain_url(value):
    try:
        host = (urlparse(value).hostname or "").lower()
    except Exception:
        return False
    return host == "thehmars.onrender.com" or host.endswith(".thehmars.onrender.com")

def message_has_old_domain_url(message):
    if not message:
        return False

    # Find http/https URLs in free-form text and validate by parsed host.
    for candidate in re.findall(r'https?://[^\s<>"\']+', message):
        if is_old_domain_url(candidate):
            return True
    return False

def _has_old_url_in_attachments(post):
    """Returns True if any attachment contains the old domain URL."""
    for att in post.get("attachments", {}).get("data", []):
        att_url = att.get("unshimmed_url", "") or att.get("url", "") or att.get("target", {}).get("url", "")
        if att_url and is_old_domain_url(att_url):
            return True
    return False

def _should_skip_post(post, include_all):
    """Returns True if the post should be excluded based on domain filtering."""
    if include_all:
        return False
    if _has_old_url_in_attachments(post):
        return True
    if message_has_old_domain_url(post.get("message", "")):
        return True
    return False

def _fetch_all_posts(base_url, params, include_all):
    """Paginates through the FB feed and returns collected posts."""
    all_posts = []
    url = base_url
    page_count = 0
    while url and page_count < 10:
        response = requests.get(url, params=params, timeout=15)
        if response.status_code != 200:
            print(f"[!] Error fetching published posts (HTTP {response.status_code}): {response.text}")
            break
        data = response.json().get("data", [])
        for post in data:
            if not _should_skip_post(post, include_all):
                all_posts.append(post)
        next_url = response.json().get("paging", {}).get("next")
        if next_url:
            url = next_url
            params = {}
            page_count += 1
        else:
            break
    return all_posts

def _export_posts(all_posts):
    """Exports all_posts to a JSON file in the workspace directory."""
    workspace_dir = os.environ.get("SCOUT_WORKSPACE", os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))
    output_file = os.path.join(workspace_dir, "fb_published.json")
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(all_posts, f, indent=4)
        print(f"[+] Successfully exported published feed to: {output_file}")
    except Exception as e:
        print(f"[!] Failed to write to {output_file}: {e}")

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
        all_posts = _fetch_all_posts(url, params, args.all)
        if not all_posts:
            print("[+] Feed is empty. No published posts found.")
            return
        print(f"[+] Found {len(all_posts)} published post(s).")
        _export_posts(all_posts)
    except Exception as e:
        print(f"[!] Request failed: {e}")

if __name__ == "__main__":
    check_published()

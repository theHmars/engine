#!/usr/bin/env python3
import os
import sys
import re
import json
import time
import argparse
import subprocess
import requests

# Default configuration
API_VERSION = "v20.0"
BASE_URL = f"https://graph.facebook.com/{API_VERSION}"

# Setup workspace directory
WORKSPACE_DIR = os.environ.get("SCOUT_WORKSPACE", os.getcwd())

# Parse arguments to resolve scope
import argparse
parser = argparse.ArgumentParser()
parser.add_argument('--scope', default=os.environ.get("SCOUT_SCOPE", "local"), help='Geographic scope')
args, unknown = parser.parse_known_args()
SCOPE = args.scope.lower()
if SCOPE == "international":
    SCOPE = "global"

# Paths to sharing ledgers
DATA_DIR = os.path.join(WORKSPACE_DIR, "history", SCOPE)
PENDING_FILE = os.path.join(DATA_DIR, "pending_shares.json")
SHARED_FILE = os.path.join(DATA_DIR, "shared.json")
ARTICLES_FILE = os.path.join(DATA_DIR, "articles.json")

def load_environment():
    """Loads environment variables from .env file if it exists."""
    env_path = ".env"
    if not os.path.exists(env_path) and os.path.exists("../.env"):
        env_path = "../.env"
        
    if os.path.exists(env_path):
        print(f"[*] Loading environment variables from {env_path}...")
        with open(env_path) as f:
            for line in f:
                if line.strip() and not line.startswith("#") and "=" in line:
                    key, val = line.strip().split("=", 1)
                    os.environ[key] = val.replace('"', '').replace("'", "")

def load_json(filepath):
    """Loads JSON file or returns empty list if missing/invalid."""
    if not os.path.exists(filepath):
        return []
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"[!] Failed to load {filepath}: {e}")
        return []

def save_json(filepath, data):
    """Saves data to JSON file with formatting."""
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=4)
        print(f"[+] Saved updated ledger to {filepath}")
    except Exception as e:
        print(f"[!] Failed to save {filepath}: {e}")

def get_active_slugs():
    """Recursively scans src/content/news for markdown files and extracts slugs."""
    active = set()
    news_dir = os.path.join(WORKSPACE_DIR, "markdown", SCOPE)
    if os.path.exists(news_dir):
        for root, dirs, files in os.walk(news_dir):
            for filename in files:
                if filename.endswith(".md"):
                    slug = filename.replace(".md", "")
                    active.add(slug)
    return active

def extract_slug_from_post(post):
    """
    Tries to extract a website article slug from a Facebook post.
    Validates that the extracted slug starts with the date pattern YYYY-MM-DD-.
    """
    # 1. Try extracting from attachments
    attachments = post.get("attachments", {}).get("data", [])
    for attachment in attachments:
        for key in ["url", "unshimmed_url"]:
            link = attachment.get(key)
            if link:
                path = link.split('?')[0].rstrip('/')
                potential_slug = path.split('/')[-1]
                if re.match(r'^\d{4}-\d{2}-\d{2}-', potential_slug):
                    return potential_slug
        
        # Try target url
        target_url = attachment.get("target", {}).get("url")
        if target_url:
            path = target_url.split('?')[0].rstrip('/')
            potential_slug = path.split('/')[-1]
            if re.match(r'^\d{4}-\d{2}-\d{2}-', potential_slug):
                return potential_slug

    # 2. Try legacy flat link field if available
    link = post.get("link")
    if link:
        # Extract last path segment and ignore query params
        path = link.split('?')[0].rstrip('/')
        potential_slug = path.split('/')[-1]
        if re.match(r'^\d{4}-\d{2}-\d{2}-', potential_slug):
            return potential_slug

    # 3. Try extracting from message content
    message = post.get("message", "")
    if message:
        # Match URL pattern ending in a date-prefixed slug
        match = re.search(r'https?://[^\s/]+/([^\s?#]+)', message)
        if match:
            potential_slug = match.group(1).rstrip('/')
            if re.match(r'^\d{4}-\d{2}-\d{2}-', potential_slug):
                return potential_slug
                
    return None

def fetch_facebook_posts(page_id, access_token, endpoint_type="scheduled_posts", max_pages=3):
    """
    Fetches posts from Facebook Graph API (scheduled_posts or feed).
    Paginates up to max_pages.
    """
    url = f"{BASE_URL}/{page_id}/{endpoint_type}"
    
    # We query attachments{url,unshimmed_url,target} instead of link to avoid deprecated fields errors.
    fields = "id,message,attachments{url,unshimmed_url,target}"
    if endpoint_type == "scheduled_posts":
        fields += ",scheduled_publish_time"
        
    params = {
        "access_token": access_token,
        "fields": fields,
        "limit": 100
    }
    
    all_posts = []
    page_count = 0
    
    try:
        while url and page_count < max_pages:
            response = requests.get(url, params=params, timeout=15)
            if response.status_code != 200:
                print(f"[!] Error fetching {endpoint_type} (HTTP {response.status_code}): {response.text}")
                break
                
            res_data = response.json()
            data = res_data.get("data", [])
            all_posts.extend(data)
            
            page_count += 1
            
            # Check for next page link
            paging = res_data.get("paging", {})
            next_url = paging.get("next")
            if next_url:
                url = next_url
                params = {}  # The next url contains its own tokens/cursors
            else:
                break
    except Exception as e:
        print(f"[!] Request to Facebook failed: {e}")
        
    return all_posts

def delete_facebook_post(post_id, access_token):
    """Deletes a post from the Facebook Page."""
    delete_url = f"{BASE_URL}/{post_id}"
    params = {"access_token": access_token}
    try:
        response = requests.delete(delete_url, params=params, timeout=15)
        if response.status_code == 200 and response.json().get("success"):
            return True
        else:
            print(f"  [!] Failed to delete Facebook post {post_id} (HTTP {response.status_code}): {response.text}")
            return False
    except Exception as e:
        print(f"  [!] Network error deleting post {post_id}: {e}")
        return False

def commit_changes_to_git(commit_msg):
    """Adds modified ledgers and commits changes locally (NO remote push)."""
    print("[*] Committing ledger changes locally...")
    try:
        # Check if there are changes
        diff_check = subprocess.run(["git", "diff-index", "--quiet", "HEAD", "--"], capture_output=True)
        if diff_check.returncode != 0:
            subprocess.run(["git", "add", PENDING_FILE, SHARED_FILE, ARTICLES_FILE], check=True)
            subprocess.run(["git", "commit", "-m", f"[skip ci] {commit_msg}"], check=True)
            print("[+] Local git commit completed successfully.")
        else:
            print("[-] No changes to commit in git repository.")
    except Exception as e:
        print(f"[!] Git commit failed: {e}")

def main():
    parser = argparse.ArgumentParser(description="Facebook Page Cleaner - Syncs Facebook page posts with physical website articles.")
    parser.add_argument("--dry-run", action="store_true", help="Preview deletions without modifying Facebook or local ledgers.")
    parser.add_argument("--interactive", action="store_true", help="Prompt for confirmation before deleting Facebook posts.")
    args = parser.parse_args()

    load_environment()
    
    page_id = os.environ.get("FB_PAGE_ID")
    access_token = os.environ.get("FB_PAGE_ACCESS_TOKEN")
    
    if not page_id or not access_token:
        print("[!] Error: Missing FB_PAGE_ID or FB_PAGE_ACCESS_TOKEN variables in environment.")
        sys.exit(1)
        
    print(f"[*] Running Facebook Cleaner (Dry Run: {args.dry_run})")
    
    # 1. Get current physical articles state
    active_slugs = get_active_slugs()
    print(f"[*] Found {len(active_slugs)} physical article markdown files on disk.")
    
    # 2. Process local sharing ledgers
    shared_list = load_json(SHARED_FILE)
    pending_list = load_json(PENDING_FILE)
    articles_list = load_json(ARTICLES_FILE)
    
    # Identify local orphans
    orphaned_shared = [slug for slug in shared_list if slug not in active_slugs]
    orphaned_pending = [item for item in pending_list if item.get("slug") not in active_slugs]
    orphaned_articles = [slug for slug in articles_list if slug not in active_slugs]
    
    local_orphans_count = len(orphaned_shared) + len(orphaned_pending) + len(orphaned_articles)
    
    if local_orphans_count > 0:
        print(f"\n[+] Identified {local_orphans_count} orphaned records in local ledgers:")
        if orphaned_shared:
            print(f"    - Shared.json orphans: {orphaned_shared}")
        if orphaned_pending:
            print(f"    - Pending_shares.json orphans: {[item.get('slug') for item in orphaned_pending]}")
        if orphaned_articles:
            print(f"    - Articles.json orphans: {orphaned_articles}")
    else:
        print("[-] No orphaned records found in local sharing ledgers.")
        
    # 3. Fetch Facebook scheduled posts
    print("\n[*] Fetching scheduled Facebook posts...")
    scheduled_posts = fetch_facebook_posts(page_id, access_token, "scheduled_posts")
    print(f"[*] Retrieved {len(scheduled_posts)} scheduled posts from Facebook.")
    
    # 4. Fetch recent Facebook feed (published posts)
    print("[*] Fetching recent Facebook feed posts...")
    feed_posts = fetch_facebook_posts(page_id, access_token, "feed", max_pages=3)
    print(f"[*] Retrieved {len(feed_posts)} published posts from Facebook feed.")
    
    # Combine posts to evaluate
    all_fb_posts = [("scheduled", p) for p in scheduled_posts] + [("published", p) for p in feed_posts]
    
    fb_deletions = []
    
    for post_type, post in all_fb_posts:
        slug = extract_slug_from_post(post)
        if slug:
            if slug not in active_slugs:
                # Missing physically, mark for deletion
                fb_deletions.append((post_type, post, slug))
                
    if fb_deletions:
        print(f"\n[+] Identified {len(fb_deletions)} post(s) on Facebook that no longer exist physically:")
        for idx, (post_type, post, slug) in enumerate(fb_deletions, 1):
            scheduled_info = ""
            if post_type == "scheduled":
                pub_time = int(post.get("scheduled_publish_time", 0))
                readable_time = time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(pub_time))
                scheduled_info = f" (Scheduled for {readable_time})"
            print(f"  #{idx}: [{post_type.upper()}] ID: {post.get('id')}{scheduled_info}\n       Slug: {slug}\n       Message: {post.get('message', '')[:80]}...")
            
        # Interactive confirmation
        if args.interactive and sys.stdin.isatty():
            confirm = input(f"\n[?] Do you want to delete these {len(fb_deletions)} post(s) from the Facebook Page? (y/N): ")
            if confirm.lower() != 'y':
                print("[-] FB deletions skipped.")
                fb_deletions = []
    else:
        print("[-] No Facebook posts matched for deletion.")
        
    # 5. Apply modifications
    if args.dry_run:
        print("\n[DRY RUN] No actions taken. Preview finished.")
        sys.exit(0)
        
    # Process local updates
    ledger_changed = False
    if local_orphans_count > 0:
        new_shared = [slug for slug in shared_list if slug in active_slugs]
        new_pending = [item for item in pending_list if item.get("slug") in active_slugs]
        new_articles = [slug for slug in articles_list if slug in active_slugs]
        
        save_json(SHARED_FILE, new_shared)
        save_json(PENDING_FILE, new_pending)
        save_json(ARTICLES_FILE, new_articles)
        ledger_changed = True
        
    # Process Facebook deletions
    deleted_fb_count = 0
    if fb_deletions:
        print(f"\n[*] Proceeding to delete {len(fb_deletions)} post(s) from Facebook Page...")
        for post_type, post, slug in fb_deletions:
            post_id = post.get("id")
            print(f"  [-] Deleting [{post_type.upper()}] Post ID: {post_id} (Slug: {slug})...")
            success = delete_facebook_post(post_id, access_token)
            if success:
                print(f"  [+] Successfully deleted post ID: {post_id}")
                deleted_fb_count += 1
                time.sleep(1) # rate-limiting friendly gap
                
    # 6. Commit to Git if ledger files changed
    if ledger_changed:
        commit_msg = f"Cleaned up {local_orphans_count} orphaned records from sharing ledgers"
        if deleted_fb_count > 0:
            commit_msg += f" and removed {deleted_fb_count} orphaned posts from Facebook Page"
        commit_changes_to_git(commit_msg)
        
    print(f"\n[+] Cleanup finished. Local updates: {local_orphans_count} entries removed. Facebook deletions: {deleted_fb_count} posts removed.")

if __name__ == "__main__":
    main()

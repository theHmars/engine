#!/usr/bin/env python3
import os
import sys
import re
import time
import json
import requests
import subprocess
import argparse
import shutil

# Load environment configuration
PAGE_ID = os.environ.get("FB_PAGE_ID")
ACCESS_TOKEN = os.environ.get("FB_PAGE_ACCESS_TOKEN")
API_VERSION = "v20.0"
BASE_URL = f"https://graph.facebook.com/{API_VERSION}"

# Render credentials
RENDER_API_KEY = os.environ.get("RENDER_API_KEY")
RENDER_SERVICE_ID = os.environ.get("RENDER_SERVICE_ID")
RENDER_DEPLOY_HOOK = os.environ.get("RENDER_DEPLOY_HOOK")

# Production URL base
WEBSITE_BASE_URL = "https://thehmars-news.onrender.com"

# Setup workspace directory
WORKSPACE_DIR = os.environ.get("SCOUT_WORKSPACE", os.getcwd())

# Resolve website repository path (content repository)
website_repo_path = os.environ.get("WEBSITE_REPO_PATH")
if not website_repo_path:
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sibling_path = os.path.join(parent_dir, "content")
    if os.path.exists(sibling_path):
        website_repo_path = sibling_path
    else:
        website_repo_path = os.path.join(WORKSPACE_DIR, "content-repo")

# Engine root directory (scout-master)
engine_root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load_json(filepath):
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"  [!] Failed to load {filepath}: {e}")
        return []

def save_json(filepath, data):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=4)

def parse_markdown(filepath):
    """Parses frontmatter title and description from a markdown post."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    title_match = re.search(r'^title:\s*(?:"(.*)"|\'(.*)\'|(.*))', content, re.MULTILINE)
    desc_match = re.search(r'^description:\s*(?:"(.*)"|\'(.*)\'|(.*))', content, re.MULTILINE)
    
    title = ""
    if title_match:
        title = title_match.group(1) or title_match.group(2) or title_match.group(3)
        if title: title = title.strip()

    description = ""
    if desc_match:
        description = desc_match.group(1) or desc_match.group(2) or desc_match.group(3)
        if description: description = description.strip()

    filename = os.path.basename(filepath)
    slug = filename.replace(".md", "")

    return {
        "title": title or slug,
        "description": description or "",
        "slug": slug,
        "url": f"{WEBSITE_BASE_URL}/{slug}",
        "filepath": filepath
    }

def get_latest_scheduled_time():
    url = f"{BASE_URL}/{PAGE_ID}/scheduled_posts"
    params = {"access_token": ACCESS_TOKEN, "fields": "scheduled_publish_time", "limit": 100}
    max_timestamp = None
    try:
        while True:
            response = requests.get(url, params=params, timeout=15)
            if response.status_code == 200:
                data = response.json().get("data", [])
                if not data:
                    break
                
                timestamps = [int(p["scheduled_publish_time"]) for p in data if "scheduled_publish_time" in p]
                if timestamps:
                    batch_max = max(timestamps)
                    if max_timestamp is None or batch_max > max_timestamp:
                        max_timestamp = batch_max
                        
                paging = response.json().get("paging", {})
                next_url = paging.get("next")
                if next_url:
                    url = next_url
                    params = {}
                else:
                    break
            else:
                print(f"  [!] Error checking scheduled posts (HTTP {response.status_code}): {response.text}")
                break
    except Exception as e:
        print(f"  [!] Exception checking scheduled posts: {e}")
        
    return max_timestamp

def publish_facebook_post(article, publish_time=None):
    url = f"{BASE_URL}/{PAGE_ID}/feed"
    message = f"{article['title']}\n\n{article['description']}\n\nRead more: {article['url']}"
    payload = {"message": message, "link": article['url'], "access_token": ACCESS_TOKEN}
    
    if publish_time:
        payload["published"] = "false"
        payload["scheduled_publish_time"] = str(int(publish_time))
    else:
        payload["published"] = "true"
        
    try:
        response = requests.post(url, data=payload, timeout=15)
        if response.status_code == 200:
            post_id = response.json().get("id")
            if publish_time:
                print(f"  [+] Scheduled post ID {post_id} for {time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(publish_time))} UTC")
            else:
                print(f"  [+] Published INSTANTLY. Post ID: {post_id}")
            return True
        else:
            print(f"  [!] Failed to publish: HTTP {response.status_code} - {response.text}")
    except Exception as e:
        print(f"  [!] Network error sending post: {e}")
    return False

def trigger_render_deploy():
    if not RENDER_DEPLOY_HOOK:
        print("  [!] Warning: RENDER_DEPLOY_HOOK not configured. Skipping manual trigger.")
        return False
        
    print("  [+] Triggering Render manual deploy hook...")
    try:
        res = requests.get(RENDER_DEPLOY_HOOK, timeout=15)
        if res.status_code in [200, 201, 204]:
            print("  [+] Render build triggered successfully.")
            return True
        else:
            print(f"  [!] Render hook failed: HTTP {res.status_code}")
    except Exception as e:
        print(f"  [!] Error triggering Render build: {e}")
    return False

def wait_for_render_build_live(timeout_minutes=15):
    if not RENDER_API_KEY or not RENDER_SERVICE_ID:
        print("  [!] Warning: RENDER_API_KEY/SERVICE_ID not configured. Skipping polling.")
        return True
        
    url = f"https://api.render.com/v1/services/{RENDER_SERVICE_ID}/deploys"
    headers = {"Authorization": f"Bearer {RENDER_API_KEY}", "Accept": "application/json"}
    
    print("  - Waiting for Render build to complete and go live...")
    start_time = time.time()
    
    while time.time() - start_time < (timeout_minutes * 60):
        try:
            res = requests.get(url, headers=headers, timeout=15)
            if res.status_code == 200:
                deploys = res.json()
                if deploys:
                    status = deploys[0]["deploy"].get("status")
                    print(f"    - Current Render deploy status: {status.upper()}")
                    if status == "live":
                        return True
                    elif status in ["build_failed", "update_failed", "canceled"]:
                        return False
            time.sleep(30)
        except Exception as e:
            print(f"    - Render API polling exception: {e}")
            time.sleep(15)
            
    return None

def is_render_build_active():
    if not RENDER_API_KEY or not RENDER_SERVICE_ID:
        return False
    url = f"https://api.render.com/v1/services/{RENDER_SERVICE_ID}/deploys"
    headers = {"Authorization": f"Bearer {RENDER_API_KEY}", "Accept": "application/json"}
    try:
        res = requests.get(url, headers=headers, timeout=15)
        if res.status_code == 200:
            deploys = res.json()
            if deploys:
                status = deploys[0]["deploy"].get("status")
                if status in ["created", "build_in_progress", "pre_deploy_in_progress", "activated"]:
                    print(f"  [-] Active Render build detected with status: {status.upper()}")
                    return True
        else:
            print(f"  [!] Failed to check Render build status: HTTP {res.status_code}")
    except Exception as e:
        print(f"  [!] Error checking Render build status: {e}")
    return False



def main():
    print(">>> Starting Render Deploy & Sequential Facebook Publisher Setup")
    
    scopes = ["local", "national", "global"]
    
    # 1. Compile Queue First (Don't trigger Render if we have 0 new articles)
    all_unshared_slugs = {}
    all_tmp_queues = {}
    total_articles_to_schedule = 0
    
    for scope in scopes:
        content_history_dir = os.path.join(website_repo_path, "history", scope)
        os.makedirs(content_history_dir, exist_ok=True)
        pending_file = os.path.join(content_history_dir, "pending_shares.json")
        shared_file = os.path.join(content_history_dir, "shared.json")
        articles_file = os.path.join(content_history_dir, "articles.json")
        content_markdown_dir = os.path.join(website_repo_path, "markdown", scope)
        
        if not os.path.exists(articles_file):
            continue
            
        content_articles = load_json(articles_file)
        shared_list = load_json(shared_file)
        shared_set = set(shared_list)
        pending_queue = load_json(pending_file)
        pending_slugs = {item["slug"] for item in pending_queue}
        
        unshared_slugs = []
        for slug in content_articles:
            if slug not in shared_set and slug not in pending_slugs:
                unshared_slugs.append(slug)
                
        all_unshared_slugs[scope] = unshared_slugs
        
        tmp_queue = []
        for slug in unshared_slugs:
            filepath = os.path.join(content_markdown_dir, f"{slug}.md")
            if os.path.exists(filepath):
                tmp_queue.append(parse_markdown(filepath))
                
        all_tmp_queues[scope] = {"tmp": tmp_queue, "pending": pending_queue}
        total_articles_to_schedule += len(tmp_queue) + len(pending_queue)
        
    if total_articles_to_schedule == 0:
        print("  [-] No unshared or pending articles found across all scopes. Skipping Render trigger and Facebook scheduling.")
        sys.exit(0)

    # 2. Check active builds on Render to avoid concurrent runs
    max_checks = 10
    checks = 0
    while is_render_build_active() and checks < max_checks:
        print("  [-] Render service is currently building or deploying. Sleeping for 2 minutes...")
        time.sleep(120)
        checks += 1
        
    if checks >= max_checks:
        print("  [!] Timeout: Another build is still running after 20 minutes. Proceeding anyway.")

    # 3. Trigger Render Deploy Hook (with 3 retries)
    build_success = False
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        print(f"  - Render Trigger Attempt {attempt}/{max_retries}")
        trigger_render_deploy()
        status = wait_for_render_build_live(timeout_minutes=15)
        
        if status is True:
            build_success = True
            break
        elif status is False:
            print("  [!] Render build explicitly failed (build_failed/canceled).")
            if attempt < max_retries:
                print("  - Waiting 30 seconds before retry...")
                time.sleep(30)
        else:
            print("  [!] Render API timeout or unknown network error. Aborting retries without quarantining.")
            break
            
    if not build_success and status is False:
        print("  [!] Render build explicitly failed after 3 attempts. Executing Quarantine Protocol.")
        quarantined_files = False
        for scope, slugs in all_unshared_slugs.items():
            content_markdown_dir = os.path.join(website_repo_path, "markdown", scope)
            quarantine_dir = os.path.join(website_repo_path, "quarantine", "render", scope)
            os.makedirs(quarantine_dir, exist_ok=True)
            for slug in slugs:
                filepath = os.path.join(content_markdown_dir, f"{slug}.md")
                if os.path.exists(filepath):
                    shutil.move(filepath, os.path.join(quarantine_dir, f"{slug}.md"))
                    print(f"  [-] Quarantined {slug}.md from {scope}")
                    quarantined_files = True
                    
        if quarantined_files:
            print("  [+] Re-running update_indices.py to remove quarantined files from articles.json...")
            subprocess.run(["python3", "scripts/update_indices.py"], cwd=website_repo_path)
            
            print("  [+] Committing and pushing quarantine state to GitHub...")
            subprocess.run(["git", "config", "user.name", "github-actions[bot]"], cwd=website_repo_path)
            subprocess.run(["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"], cwd=website_repo_path)
            subprocess.run(["git", "add", "markdown/", "quarantine/", "history/"], cwd=website_repo_path)
            subprocess.run(["git", "commit", "-m", "Auto-quarantined Render build failures"], cwd=website_repo_path)
            subprocess.run(["git", "push", "origin"], cwd=website_repo_path)
            
        print("  [!] Quarantine complete. Aborting Facebook queue scheduling.")
        sys.exit(0) # Exit cleanly so the workflow passes
    elif not build_success:
        print("  [!] Render deploy check timed out or failed to verify. Aborting Facebook queue to be safe.")
        sys.exit(1)

    print("  [+] Render build completed successfully. Sleeping for 1 minute before scheduling...")
    time.sleep(60)

    # 4. Process Facebook Scheduling Queue
    latest_fb_time = get_latest_scheduled_time()
    now_ts = int(time.time())
    
    is_queue_empty = (latest_fb_time is None or latest_fb_time < now_ts)
    last_scheduled_slot = latest_fb_time if not is_queue_empty else now_ts
    
    for scope in scopes:
        if scope not in all_tmp_queues:
            continue
            
        print(f"\n>>> Processing Queue for Scope: {scope.upper()}")
        tmp_queue = all_tmp_queues[scope]["tmp"]
        pending_queue = all_tmp_queues[scope]["pending"]
        total_queue = pending_queue + tmp_queue
        
        if not total_queue:
            print("  [-] No articles to schedule for this scope.")
            continue
            
        content_history_dir = os.path.join(website_repo_path, "history", scope)
        pending_file = os.path.join(content_history_dir, "pending_shares.json")
        shared_file = os.path.join(content_history_dir, "shared.json")
        shared_list = load_json(shared_file)
        
        updated_pending = []
        modified = False
        
        for article in total_queue:
            if is_queue_empty:
                print(f"  - Publishing IMMEDIATELY: '{article['title'][:30]}'")
                if publish_facebook_post(article, publish_time=None):
                    shared_list.append(article["slug"])
                    modified = True
                    is_queue_empty = False
                    last_scheduled_slot = now_ts
                else:
                    updated_pending.append(article)
            else:
                next_slot = last_scheduled_slot + (30 * 60)
                if next_slot < now_ts + (15 * 60):
                    next_slot = now_ts + (15 * 60)
                    
                if next_slot <= now_ts + (60 * 60 * 60):
                    print(f"  - Scheduling '{article['title'][:30]}' at slot {time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(next_slot))} UTC")
                    if publish_facebook_post(article, publish_time=next_slot):
                        shared_list.append(article["slug"])
                        last_scheduled_slot = next_slot
                        modified = True
                    else:
                        updated_pending.append(article)
                else:
                    updated_pending.append(article)
                
        save_json(pending_file, updated_pending)
        if modified:
            save_json(shared_file, shared_list)
            
    print("\n>>> Render deploy and sequential Facebook scheduling chain complete.")

if __name__ == "__main__":
    main()

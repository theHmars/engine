#!/usr/bin/env python3
import os
import sys
import json
import time
import requests
import subprocess
import shutil
from dotenv import load_dotenv

current_dir = os.path.dirname(os.path.abspath(__file__))
engine_root = os.path.dirname(os.path.dirname(current_dir))
# Resolve tmp_dir from SCOUT_WORKSPACE — matches prepare_candidates.py's TMP_DIR resolution
tmp_dir = os.path.join(os.environ.get("SCOUT_WORKSPACE", engine_root), "tmp")
website_repo_path = os.environ.get("WEBSITE_REPO_PATH")
if not website_repo_path:
    parent_dir = os.path.dirname(engine_root)
    sibling_path = os.path.join(parent_dir, "content")
    if os.path.exists(sibling_path):
        website_repo_path = sibling_path
    else:
        website_repo_path = os.path.join(os.environ.get("SCOUT_WORKSPACE", os.getcwd()), "content-repo")

# Try engine/.env first, then fallback to frontend/.env
env_paths = [
    os.path.join(engine_root, '.env'),
    os.path.join(os.path.dirname(engine_root), 'frontend', '.env')
]

for env_path in env_paths:
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if line.strip() and not line.startswith("#") and "=" in line:
                    key, val = line.strip().split("=", 1)
                    if key not in os.environ:
                        os.environ[key] = val.replace('"', '').replace("'", "")

PAGE_ID = os.environ.get("FB_PAGE_ID")
ACCESS_TOKEN = os.environ.get("FB_PAGE_ACCESS_TOKEN")
API_VERSION = "v20.0"
BASE_URL = f"https://graph.facebook.com/{API_VERSION}"

RENDER_API_KEY = os.environ.get("RENDER_API_KEY")
RENDER_SERVICE_ID = os.environ.get("RENDER_SERVICE_ID")
RENDER_DEPLOY_HOOK = os.environ.get("RENDER_DEPLOY_HOOK")

def trigger_render_deploy():
    if not RENDER_DEPLOY_HOOK:
        print("  [!] Warning: RENDER_DEPLOY_HOOK not configured. Skipping.")
        return False
        
    print("  [+] Triggering Render manual deploy hook...")
    
    test_mode = os.environ.get("TEST_MODE_RENDER")
    if test_mode:
        print(f"  [TEST MODE RENDER] Hook Trigger Mocked (Simulating: {test_mode})")
        if test_mode in ["404", "invalid_hook"]:
            return False
        return True
        
    try:
        res = requests.get(RENDER_DEPLOY_HOOK, timeout=15)
        if res.status_code in [200, 201, 204]:
            return True
        print(f"  [!] Render hook failed with status {res.status_code}: {res.text}")
    except Exception as e:
        print(f"  [!] Error triggering Render build: {e}")
    return False

def wait_for_render_build_live(timeout_minutes=15):
    if not RENDER_API_KEY or not RENDER_SERVICE_ID:
        print("  [!] Warning: RENDER_API_KEY/SERVICE_ID not configured. Skipping polling.")
        return True
        
    url = f"https://api.render.com/v1/services/{RENDER_SERVICE_ID}/deploys"
    headers = {"Authorization": f"Bearer {RENDER_API_KEY}", "Accept": "application/json"}
    
    print("  [+] Polling Render API for 'live' status...")
    start_time = time.time()
    
    test_mode = os.environ.get("TEST_MODE_RENDER")
    if test_mode:
        print(f"  [TEST MODE RENDER] Build Polling Mocked (Simulating: {test_mode})")
        if test_mode == "success":
            return True
        elif test_mode in ["build_failed", "timeout"]:
            return False
            
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
            time.sleep(30)
            
    return False



def main():
    print(">>> Starting Unified Publisher Workflow")
    
    # 1. Run prepare_candidates.py
    print("\n>>> Step 1: Gathering Candidates")
    subprocess.run(["python3", os.path.join(current_dir, "prepare_candidates.py")], check=True)
    
    metadata_path = os.path.join(tmp_dir, "metadata.json")
    if not os.path.exists(metadata_path):
        print("[-] metadata.json not found. Exiting.")
        sys.exit(0)
        
    with open(metadata_path, 'r') as f:
        meta = json.load(f)
        
    if meta["total_candidates"] == 0:
        print("[-] No new candidates generated. Triggering Render just in case, then exiting.")
        trigger_render_deploy()
        sys.exit(0)
        
    # 2. Trigger Render & Monitor (QA Gatekeeper)
    print("\n>>> Step 2: Render QA Gatekeeper")
    build_success = False
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        print(f"  - Render Trigger Attempt {attempt}/{max_retries}")
        triggered = trigger_render_deploy()
        if not triggered:
            print("  [!] Deploy hook call failed. Skipping status poll for this attempt.")
            if attempt < max_retries:
                time.sleep(30)
            continue
        status = wait_for_render_build_live(timeout_minutes=15)
        
        if status is True:
            build_success = True
            break
        elif status is False:
            print("  [!] Render build explicitly failed (build_failed/canceled).")
            if attempt < max_retries:
                time.sleep(30)
        else:
            print("  [!] Render API timeout. Aborting retries.")
            break
            
    if not build_success:
        print("  [!] Render build explicitly failed after 3 attempts. Executing Quarantine Protocol.")
        
        # Load candidates to figure out which ones to quarantine
        list_path = os.path.join(tmp_dir, "list.json")
        if os.path.exists(list_path):
            with open(list_path, 'r') as f:
                candidates = json.load(f)
                
            quarantined_files = False
            for article in candidates:
                scope = article["scope"]
                slug = article["slug"]
                
                content_markdown_dir = os.path.join(website_repo_path, "markdown", scope)
                quarantine_dir = os.path.join(website_repo_path, "quarantine", "render", scope)
                os.makedirs(quarantine_dir, exist_ok=True)
                
                filepath = os.path.join(content_markdown_dir, f"{slug}.md")
                if os.path.exists(filepath):
                    shutil.move(filepath, os.path.join(quarantine_dir, f"{slug}.md"))
                    print(f"  [-] Quarantined {slug}.md from {scope}")
                    quarantined_files = True
                    
            if quarantined_files:
                print("  [+] Re-running update_indices.py to remove quarantined files...")
                subprocess.run(["python3", "scripts/update_indices.py"], cwd=website_repo_path)
                
                print("  [+] Committing and pushing quarantine state to GitHub...")
                subprocess.run(["git", "config", "user.name", "github-actions[bot]"], cwd=website_repo_path)
                subprocess.run(["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"], cwd=website_repo_path)
                subprocess.run(["git", "add", "markdown/", "quarantine/", "history/"], cwd=website_repo_path)
                subprocess.run(["git", "commit", "-m", "Auto-quarantined Render build failures"], cwd=website_repo_path)
                subprocess.run(["git", "push", "origin"], cwd=website_repo_path)
                
        print("  [!] Quarantine complete. Aborting Facebook queue scheduling.")
        sys.exit(0)
        
    print("  [+] Render build completed successfully. Sleeping for 1 minute before scheduling...")
    time.sleep(60)

    # 3. Run pre_queue.py
    print("\n>>> Step 3: Checking Facebook Queue")
    subprocess.run([sys.executable, os.path.join(current_dir, "pre_queue.py")], check=True)
    
    # 4. Run social_curator.py
    print("\n>>> Step 4: AI Editor-in-Chief Curation")
    curator_script = os.path.join(engine_root, "scripts", "agents", "social_curator", "social_curator.py")
    subprocess.run([sys.executable, curator_script], check=True)
    
    # 5. Publish to Social Media (Modular)
    print("\n>>> Step 5: Publishing to Social Media")
    fb_script = os.path.join(current_dir, "publish_to_fb.py")
    if os.path.exists(fb_script):
        subprocess.run([sys.executable, fb_script], check=True)
    
    # Future-proofing: When you build publish_to_x.py or publish_to_instagram.py, 
    # you simply add the subprocess calls right here!

    print("\n>>> Unified Publisher Workflow Complete!")

if __name__ == "__main__":
    main()

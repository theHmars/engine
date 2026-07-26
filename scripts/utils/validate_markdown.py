#!/usr/bin/env python3
import os
import sys
import shutil
import subprocess
import re

# Add scripts directory to path to resolve 'utils' package
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.common import get_state_dir

def validate_frontmatter(file_path):
    """Parses frontmatter of a markdown file and validates region and majorTag against allowed schemas."""
    allowed_regions = {
        "Arunachal Pradesh", "Assam", "Manipur", "Meghalaya", 
        "Mizoram", "Nagaland", "Sikkim", "Tripura", "Northeast", "N/A"
    }
    allowed_tags = {
        "Politics", "Sports", "Business", "Tech", "Science", "Culture", 
        "Health", "Education", "Weather", "Entertainment", "Environment", 
        "Celebrity", "Uncategorized"
    }
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        content_stripped = content.lstrip()
        if not content_stripped.startswith("---"):
            return False, "Missing frontmatter delimiters"
        parts = content_stripped.split("---", 2)
        if len(parts) < 3:
            return False, "Missing frontmatter delimiters"
            
        frontmatter_text = parts[1]
        frontmatter = {}
        for line in frontmatter_text.splitlines():
            if ":" in line:
                key, val = line.split(":", 1)
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                frontmatter[key] = val
                
        region = frontmatter.get("region")
        if region and region not in allowed_regions:
            return False, f"Invalid region '{region}'"
            
        tag = frontmatter.get("majorTag")
        if tag and tag not in allowed_tags:
            return False, f"Invalid majorTag '{tag}'"
            
        return True, "PASS"
    except Exception as e:
        return False, f"Failed to parse: {e}"

def _quarantine_bad_frontmatter(scopes):
    for scope in scopes:
        push_dir = os.path.join(get_state_dir(), "push", scope)
        if not os.path.exists(push_dir):
            continue
        for file in os.listdir(push_dir):
            if not file.endswith(".md"):
                continue
            file_path = os.path.join(push_dir, file)
            is_valid, err_msg = validate_frontmatter(file_path)
            if not is_valid:
                print(f"  [!] Frontmatter validation failed for {file} ({scope}): {err_msg}")
                quarantine_dir = os.path.join(get_state_dir(), "quarantine", "local", scope)
                os.makedirs(quarantine_dir, exist_ok=True)
                shutil.move(file_path, os.path.join(quarantine_dir, file))
                print(f"  [-] Quarantined bad frontmatter file: {file}")

def _copy_to_frontend(scopes, news_dir):
    for scope in scopes:
        push_dir = os.path.join(get_state_dir(), "push", scope)
        if not os.path.exists(push_dir):
            continue
        for file in os.listdir(push_dir):
            if file.endswith(".md"):
                shutil.copy2(os.path.join(push_dir, file), os.path.join(news_dir, file))

def _quarantine_corrupt_file(bad_file_path, scopes):
    filename = os.path.basename(bad_file_path)
    print(f"  [!] Corrupt Markdown Detected: {filename}")
    
    # Remove it from the test environment so we can check the rest
    os.remove(bad_file_path)
    
    # Find it in the engine push directories and move it to quarantine
    quarantined = False
    for scope in scopes:
        engine_file = os.path.join(get_state_dir(), "push", scope, filename)
        if os.path.exists(engine_file):
            quarantine_dir = os.path.join(get_state_dir(), "quarantine", "local", scope)
            os.makedirs(quarantine_dir, exist_ok=True)
            shutil.move(engine_file, os.path.join(quarantine_dir, filename))
            print(f"  [-] Moved {filename} to {quarantine_dir}")
            quarantined = True
            break
            
    if not quarantined:
        print(f"  [!] Could not locate {filename} in engine/push/ scopes. Might be an old file.")

def _handle_astro_error(output, news_dir, scopes):
    # Regex looks for: Location:\n  /path/to/frontend/src/content/news/filename.md
    match = re.search(r'Location:\s*([^\n]+)', output)
    bad_file_path = None
    
    if match:
        bad_file_path = match.group(1).strip()
    else:
        # Fallback regex just in case
        match = re.search(r'src/content/news/([^:]+\.md)', output)
        if match:
            bad_file_path = os.path.join(news_dir, match.group(1).strip())
            
    if bad_file_path and os.path.exists(bad_file_path):
        _quarantine_corrupt_file(bad_file_path, scopes)
        return True
    else:
        print("  [!] Could not identify the specific corrupted file from Astro output. Aborting validation loop.")
        print("--- ASTRO OUTPUT ---")
        print(output[:1000])
        return False

def main():
    workspace = os.environ.get("SCOUT_WORKSPACE", os.getcwd())
    frontend_dir = os.environ.get("FRONTEND_REPO_PATH", os.path.join(workspace, "../frontend"))
    
    if not os.path.exists(frontend_dir):
        print(f"  [!] Frontend directory not found at {frontend_dir}. Skipping Astro check validation.")
        sys.exit(0)
        
    print(">>> Starting Pre-Flight Local Astro Validation")
    
    # Setup frontend test environment
    news_dir = os.path.join(frontend_dir, "src/content/news")
    os.makedirs(news_dir, exist_ok=True)
    
    scopes = ["local", "national", "global"]
    
    # 1. Frontmatter constraint check
    _quarantine_bad_frontmatter(scopes)
                        
    # 2. Copy remaining valid markdown files to the frontend news directory
    _copy_to_frontend(scopes, news_dir)
                    
    # Loop Astro Check until it passes (removing bad files one by one)
    while True:
        print("  - Running 'npx astro check'...")
        try:
            res = subprocess.run(
                ["npx", "astro", "check"],
                cwd=frontend_dir,
                capture_output=True,
                text=True
            )
        except Exception as e:
            print(f"  [!] Failed to execute astro check: {e}")
            break
            
        if res.returncode == 0:
            print("  [+] Validation Passed! All markdown files are structurally safe.")
            break
            
        # Parse error output to find the exact offending file
        output = res.stderr + "\n" + res.stdout
        print("  [!] Validation failed. Analyzing errors...")
        
        if not _handle_astro_error(output, news_dir, scopes):
            break

if __name__ == "__main__":
    main()

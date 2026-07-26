#!/usr/bin/env python3
import os
import json

# Setup workspace directory
WORKSPACE_DIR = os.environ.get("SCOUT_WORKSPACE", os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
PUSH_DIR = os.path.join(WORKSPACE_DIR, "push")
TMP_DIR = os.path.join(WORKSPACE_DIR, "tmp")

def _parse_frontmatter(content):
    content_stripped = content.lstrip()
    if not content_stripped.startswith("---"):
        return {}
    parts = content_stripped.split("---", 2)
    if len(parts) < 3:
        return {}
    
    frontmatter = {}
    for line in parts[1].splitlines():
        if ":" in line:
            key, val = line.split(":", 1)
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            frontmatter[key] = val
    return frontmatter

def parse_markdown(filepath, scope):
    """Parses frontmatter title, summary, and image from a markdown post."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    fm = _parse_frontmatter(content)
    title = fm.get("title", "").strip()
    description = fm.get("description", "").strip()
    image = fm.get("image", "").strip()

    # Read ignore list
    ignore_list_path = os.path.join(WORKSPACE_DIR, "data", "ignore_image_paths.txt")
    ignore_images = []
    if os.path.exists(ignore_list_path):
        with open(ignore_list_path, 'r', encoding='utf-8') as f:
            ignore_images = [line.strip() for line in f if line.strip()]

    has_image = True
    if (not image or "fallback.webp" in image or "default_image" in image or 
        any(ignored in image for ignored in ignore_images)):
        has_image = False

    filename = os.path.basename(filepath)
    slug = filename.replace(".md", "")

    return {
        "slug": slug,
        "title": title or slug,
        "summary": description or "",
        "scope": scope,
        "featured_image": has_image,
        "featured_image_url": image if has_image else "/images/fallback.webp"
    }

def _gather_candidates():
    scopes = ["local", "national", "global"]
    candidates = []
    for scope in scopes:
        scope_dir = os.path.join(PUSH_DIR, scope)
        if not os.path.exists(scope_dir):
            continue
            
        for filename in os.listdir(scope_dir):
            if filename.endswith(".md"):
                filepath = os.path.join(scope_dir, filename)
                parsed = parse_markdown(filepath, scope)
                if parsed:
                    candidates.append(parsed)
                    
    # Assign integer IDs to candidates for the LLM
    for idx, candidate in enumerate(candidates):
        candidate["id"] = idx
    return candidates

def _calculate_quota(total_candidates, test_mode):
    if test_mode:
        q_normal = int(os.environ.get("TEST_QUOTA_NORMAL", 2))
        q_high = int(os.environ.get("TEST_QUOTA_HIGH", 4))
        high_threshold = q_high + 2
        print(f"[*] TEST MODE ENABLED: Overriding quotas to Normal={q_normal}, High={q_high}")
        gap = 30 if total_candidates >= high_threshold else 60
        quota = q_high if total_candidates >= high_threshold else q_normal
        return quota, gap

    # Gap: 60-min for <16 articles, 30-min for 16+
    gap = 30 if total_candidates >= 16 else 60
    
    # Tiered quota
    if total_candidates <= 8:
        quota = total_candidates
    elif total_candidates == 9:
        quota = 8
    elif total_candidates == 10:
        quota = 10
    elif total_candidates <= 15:
        quota = 10
    elif total_candidates == 16:
        quota = 16
    elif total_candidates <= 19:
        quota = 16
    elif total_candidates == 20:
        quota = 20
    else:
        quota = 20
        
    return quota, gap

def main():
    print("[*] Running prepare_candidates.py...")
    candidates = _gather_candidates()
    total_candidates = len(candidates)
    
    test_mode = os.environ.get("TEST_MODE_ENABLED") == "true"
    quota, gap = _calculate_quota(total_candidates, test_mode)
        
    metadata = {
        "total_candidates": total_candidates,
        "quota": quota,
        "gap_minutes": gap
    }
    
    # Save to JSON files
    os.makedirs(TMP_DIR, exist_ok=True)
    list_path = os.path.join(TMP_DIR, "list.json")
    metadata_path = os.path.join(TMP_DIR, "metadata.json")
    
    with open(list_path, 'w', encoding='utf-8') as f:
        json.dump(candidates, f, indent=4)
        
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=4)
        
    print(f"[+] Found {total_candidates} candidates in engine/push/.")
    print(f"[+] Set Quota: {quota}, Gap: {gap} minutes.")
    print(f"[+] Exported {list_path}")
    print(f"[+] Exported {metadata_path}")

if __name__ == "__main__":
    main()

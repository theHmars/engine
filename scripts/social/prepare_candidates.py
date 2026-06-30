#!/usr/bin/env python3
import os
import re
import json

# Setup workspace directory
WORKSPACE_DIR = os.environ.get("SCOUT_WORKSPACE", os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
PUSH_DIR = os.path.join(WORKSPACE_DIR, "push")
TMP_DIR = os.path.join(WORKSPACE_DIR, "tmp")

def parse_markdown(filepath, scope):
    """Parses frontmatter title, summary, and image from a markdown post."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    title_match = re.search(r'^title:\s*(?:"(.*)"|\'(.*)\'|(.*))', content, re.MULTILINE)
    desc_match = re.search(r'^description:\s*(?:"(.*)"|\'(.*)\'|(.*))', content, re.MULTILINE)
    img_match = re.search(r'^image:\s*(?:"(.*)"|\'(.*)\'|(.*))', content, re.MULTILINE)
    
    title = ""
    if title_match:
        title = title_match.group(1) or title_match.group(2) or title_match.group(3)
        if title: title = title.strip()

    description = ""
    if desc_match:
        description = desc_match.group(1) or desc_match.group(2) or desc_match.group(3)
        if description: description = description.strip()
        
    image = ""
    if img_match:
        image = img_match.group(1) or img_match.group(2) or img_match.group(3)
        if image: image = image.strip()

    # Read ignore list
    ignore_list_path = os.path.join(WORKSPACE_DIR, "data", "ignore_image_paths.txt")
    ignore_images = []
    if os.path.exists(ignore_list_path):
        with open(ignore_list_path, 'r', encoding='utf-8') as f:
            ignore_images = [line.strip() for line in f if line.strip()]

    has_image = True
    if not image or "fallback.webp" in image or "default_image" in image:
        has_image = False
    elif any(ignored in image for ignored in ignore_images):
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

def main():
    print("[*] Running prepare_candidates.py...")
    scopes = ["local", "national", "global"]
    candidates = []
    
    # 1. Gather Candidates from push directory
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
        
    total_candidates = len(candidates)
    
    # 2. Calculate Pacing
    test_mode = os.environ.get("TEST_MODE_ENABLED") == "true"
    
    if test_mode:
        q_normal = int(os.environ.get("TEST_QUOTA_NORMAL", 2))
        q_high = int(os.environ.get("TEST_QUOTA_HIGH", 4))
        high_threshold = q_high + 2
        print(f"[*] TEST MODE ENABLED: Overriding quotas to Normal={q_normal}, High={q_high}")
        gap = 30 if total_candidates >= high_threshold else 60
        quota = q_high if total_candidates >= high_threshold else q_normal
    else:
        # Gap: 60-min for <16 articles, 30-min for 16+
        gap = 30 if total_candidates >= 16 else 60

        # Tiered quota — bypass points are ≤8, 10, 16, 20.
        # Curator only fires in the gaps, guaranteeing it always has 1+ meaningful rejection.
        #
        #  ≤ 8  → bypass (quota = total)
        #    9  → curator picks 8   (1 rejection)
        #   10  → bypass (quota = 10)
        # 11-15 → curator picks 10  (1–5 rejections)
        #   16  → bypass (quota = 16)
        # 17-19 → curator picks 16  (1–3 rejections)
        #   20  → bypass (quota = 20)
        #  21+  → curator picks 20  (1+ rejections)
        if total_candidates <= 8:
            quota = total_candidates   # bypass: take all
        elif total_candidates == 9:
            quota = 8                  # curator picks 8 from 9
        elif total_candidates == 10:
            quota = 10                 # bypass: take all 10
        elif total_candidates <= 15:
            quota = 10                 # curator picks 10 from 11–15
        elif total_candidates == 16:
            quota = 16                 # bypass: take all 16
        elif total_candidates <= 19:
            quota = 16                 # curator picks 16 from 17–19
        elif total_candidates == 20:
            quota = 20                 # bypass: take all 20
        else:
            quota = 20                 # curator picks 20 from 21+
        
    metadata = {
        "total_candidates": total_candidates,
        "quota": quota,
        "gap_minutes": gap
    }
    
    # 3. Save to JSON files
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

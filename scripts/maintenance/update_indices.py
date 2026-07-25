#!/usr/bin/env python3
import os
import re
import json
from datetime import datetime, timedelta

def parse_frontmatter(filepath):
    """Parses frontmatter title and description from a markdown post."""
    title = ""
    description = ""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        title_match = re.search(r'^title:\s*(?:"(.*)"|\'(.*)\'|(.*))', content, re.MULTILINE)
        desc_match = re.search(r'^description:\s*(?:"(.*)"|\'(.*)\'|(.*))', content, re.MULTILINE)
        
        if title_match:
            title = title_match.group(1) or title_match.group(2) or title_match.group(3)
            if title: title = title.strip()

        if desc_match:
            description = desc_match.group(1) or desc_match.group(2) or desc_match.group(3)
            if description: description = description.strip()

        tag_match = re.search(r'^majorTag:\s*(?:"(.*)"|\'(.*)\'|(.*))', content, re.MULTILINE)
        major_tag = "Uncategorized"
        if tag_match:
            major_tag = tag_match.group(1) or tag_match.group(2) or tag_match.group(3)
            if major_tag: major_tag = major_tag.strip()

    except Exception as e:
        print(f"  [!] Error parsing frontmatter for {filepath}: {e}")
        major_tag = "Uncategorized"
        
    return title, description, major_tag

def update_scope_indices(content_dir, scope):
    print(f"\n>>> Updating indices for scope: {scope.upper()}")
    
    scope_dir = os.path.join(content_dir, "markdown", scope)
    if not os.path.exists(scope_dir):
        print(f"  [-] Directory {scope_dir} does not exist. Skipping.")
        return

    # Output paths — write to history/{scope}/ so deduplicate.py and facebook_publisher.py
    # can find them at {WEBSITE_REPO_PATH}/history/{scope}/articles.json and covered.json
    history_dir = os.path.join(content_dir, "history", scope)
    os.makedirs(history_dir, exist_ok=True)
    articles_path = os.path.join(history_dir, "articles.json")
    covered_path = os.path.join(history_dir, "covered.json")

    # 1. Load existing articles.json
    existing_articles = []
    if os.path.exists(articles_path):
        try:
            with open(articles_path, 'r', encoding='utf-8') as f:
                existing_articles = json.load(f)
        except Exception as e:
            print(f"  [!] Failed to parse existing articles.json: {e}")
            existing_articles = []

    existing_set = set(existing_articles)

    # 2. Scan directory for current markdown files
    md_files = []
    for filename in sorted(os.listdir(scope_dir)):
        if filename.endswith(".md"):
            slug = filename[:-3] # Strip .md
            md_files.append((slug, filename))

    # 3. Incremental articles.json update
    new_slugs = []
    for slug, filename in md_files:
        if slug not in existing_set:
            new_slugs.append(slug)

    if new_slugs:
        # Append new slugs maintaining chronological sort (sorted by YYYY-MM-DD prefix)
        updated_articles = sorted(list(existing_set.union(new_slugs)))
        with open(articles_path, 'w', encoding='utf-8') as f:
            json.dump(updated_articles, f, indent=4)
        print(f"  [+] Added {len(new_slugs)} new articles to articles.json")
    else:
        # Fallback to write current items if empty to self-heal
        updated_articles = sorted([slug for slug, _ in md_files])
        with open(articles_path, 'w', encoding='utf-8') as f:
            json.dump(updated_articles, f, indent=4)
        print(f"  [+] Regenerated articles.json with {len(updated_articles)} items.")

    # 4. Generate 48-hour covered.json
    # Filter files within the last 48 hours based on filename prefix (YYYY-MM-DD)
    now = datetime.utcnow()
    limit_date = now - timedelta(hours=48)
    
    recent_covered = []
    topic_counts = {}
    
    for slug, filename in md_files:
        # Match YYYY-MM-DD at the start of filename
        date_match = re.match(r'^(\d{4})-(\d{2})-(\d{2})', filename)
        if date_match:
            try:
                file_date = datetime.strptime(date_match.group(0), '%Y-%m-%d')
                # If file date is within the last 48 hours (comparing days)
                if file_date >= limit_date:
                    filepath = os.path.join(scope_dir, filename)
                    title, description, major_tag = parse_frontmatter(filepath)
                    recent_covered.append({
                        "title": title or slug.replace("-", " ").title(),
                        "slug": slug,
                        "description": description
                    })
                    topic_counts[major_tag] = topic_counts.get(major_tag, 0) + 1
            except Exception as e:
                print(f"  [!] Date parsing failed for {filename}: {e}")

    with open(covered_path, 'w', encoding='utf-8') as f:
        json.dump(recent_covered, f, indent=4)
        
    print(f"  [+] Generated covered.json with {len(recent_covered)} recent articles (48h window).")

    topics_path = os.path.join(history_dir, "topics.json")
    with open(topics_path, 'w', encoding='utf-8') as f:
        json.dump(topic_counts, f, indent=4)
    print(f"  [+] Generated topics.json with category counts.")

def main():
    import sys
    # Resolve the directory of the content repository dynamically
    if len(sys.argv) > 1:
        content_dir = os.path.abspath(sys.argv[1])
    else:
        scripts_dir = os.path.dirname(os.path.abspath(__file__))
        # Resolve sibling content directory if script is in engine/scripts/maintenance/
        content_dir = os.path.abspath(os.path.join(scripts_dir, '..', '..', '..', 'content'))
        if not os.path.exists(content_dir):
            # Legacy fallback: parent of script directory
            content_dir = os.path.dirname(scripts_dir)
    
    scopes = ["local", "national", "global"]
    for scope in scopes:
        update_scope_indices(content_dir, scope)

if __name__ == "__main__":
    main()

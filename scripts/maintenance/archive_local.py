import os
import json
import glob
import yaml
import sys
from datetime import datetime, timedelta

# Configuration
CONTENT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'content', 'markdown', 'local'))
ARCHIVE_OUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'archives'))
WEBSITE_BASE_URL = "https://thehmars-news.onrender.com"

def parse_markdown_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    parts = content.split('---', 2)
    if len(parts) < 3:
        return None
        
    yaml_text = parts[1].strip()
    body_text = parts[2].strip()
    
    try:
        metadata = yaml.safe_load(yaml_text)
    except yaml.YAMLError:
        return None

    filename = os.path.basename(filepath)
    slug = filename.replace('.md', '')
    
    return {
        "id": slug,
        "title": metadata.get("title", ""),
        "date": metadata.get("date", ""),
        "category": metadata.get("category", "Local"),
        "region": metadata.get("region", ""),
        "topic": metadata.get("majorTag", ""),
        "language": metadata.get("language", "en"),
        "text": body_text,
        "url": f"{WEBSITE_BASE_URL}/{slug}"
    }

def main():
    os.makedirs(ARCHIVE_OUT_DIR, exist_ok=True)

    # 1. Determine Target Month
    if len(sys.argv) > 1:
        # Allow manual override (e.g., python archive_local.py 2026-06)
        target_ym_str = sys.argv[1]
        try:
            target_date = datetime.strptime(target_ym_str, "%Y-%m")
        except ValueError:
            print("Error: Invalid date format. Use YYYY-MM")
            return
    else:
        # Default for cron: Automatically target the PREVIOUS month
        now = datetime.now()
        first_day_of_this_month = now.replace(day=1)
        target_date = first_day_of_this_month - timedelta(days=1)
    
    target_prefix = target_date.strftime("%Y-%m")
    out_filename = target_date.strftime("%B-%Y").lower() + ".jsonl" # e.g., june-2026.jsonl
    out_filepath = os.path.join(ARCHIVE_OUT_DIR, out_filename)
    
    print(f"Targeting month: {target_prefix} (Output: {out_filename})")

    # 2. Find all matching markdown files
    search_pattern = os.path.join(CONTENT_DIR, f"{target_prefix}-*.md")
    md_files = glob.glob(search_pattern)
    
    if not md_files:
        print(f"No articles found for {target_prefix}.")
        return
        
    # Sort chronologically
    md_files.sort(key=lambda x: os.path.basename(x))
    
    print(f"Found {len(md_files)} articles for {target_date.strftime('%B %Y')}.")

    # 3. Process and Write
    processed_count = 0
    with open(out_filepath, 'w', encoding='utf-8') as out_f:
        for fpath in md_files:
            record = parse_markdown_file(fpath)
            if record:
                out_f.write(json.dumps(record) + "\n")
                processed_count += 1
                
    print(f"Successfully archived {processed_count} files into {out_filename}")

if __name__ == "__main__":
    main()

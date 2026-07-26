#!/usr/bin/env python3
import json
import os
import re
import sys
import shutil
from datetime import datetime

# Setup path so imports work correctly

from utils.common import slugify
from utils.history_manager import HistoryManager
from assembler import generate_yaml, ensure_paragraphs


def sanitize_content(content: str) -> str:
    """Strip residual HTML tags from LLM-generated content before writing to disk."""
    if not content:
        return content
    # Strip any <br> variants
    content = re.sub(r'<br\s*/?>', ' ', content, flags=re.IGNORECASE)
    # Strip any other stray HTML tags (bold, italic, spans, etc.)
    content = re.sub(r'</?(?:b|i|em|strong|span|div|p)[^>]*>', '', content, flags=re.IGNORECASE)
    # Collapse multiple spaces left behind
    content = re.sub(r'  +', ' ', content)
    return content.strip()

def _save_produced_article(art, output_dir, date_prefix, date_iso):
    """Assembles and writes a single produced article as Markdown. Returns (url, filename) or raises."""
    final_slug = slugify(art['title'])
    filename = f"{date_prefix}-{final_slug}.md"
    filepath = os.path.join(output_dir, filename)
    yaml_header = generate_yaml(art, date_iso)
    raw_content = art.get('content', '')
    clean = sanitize_content(raw_content)
    paragraphed_content = ensure_paragraphs(clean)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(yaml_header + paragraphed_content)
    print(f"  [+] Assembled and Saved: {filename}")
    return art["original_url"], filename

def _is_secondary_of_success(cand, successful_urls):
    """Returns True if any secondary source of cand was successfully published."""
    if not (cand.get("is_merged") and cand.get("secondary_sources")):
        return False
    return any(sec.get("url") in successful_urls for sec in cand["secondary_sources"])

def _log_failed_secondaries(cand, source_key, hm):
    if not (cand.get("is_merged") and cand.get("secondary_sources")):
        return
    for sec in cand["secondary_sources"]:
        sec_url = sec.get("url")
        if sec_url:
            hm.log_url(sec_url, sec.get("source_key", source_key), "FAILED_OR_ABANDONED")

def _log_failed_candidates(triaged_articles, successful_urls, hm):
    """Logs FAILED_OR_ABANDONED for candidates that did not make it to produced output."""
    for cand in triaged_articles:
        cand_url = cand.get("url")
        if not cand_url or cand_url in successful_urls:
            continue
        if _is_secondary_of_success(cand, successful_urls):
            continue
        source_key = cand.get("source_key", "unknown")
        hm.log_url(cand_url, source_key, "FAILED_OR_ABANDONED")
        print(f"  [!] Logged failed/abandoned article in history: {cand_url}")
        _log_failed_secondaries(cand, source_key, hm)

def _load_just_cleaned(just_cleaned_path):
    """Loads just_cleaned.json, returning an empty list on failure."""
    if not os.path.exists(just_cleaned_path):
        return []
    try:
        with open(just_cleaned_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []

def main():
    print("\n>>> Starting Phase 5: Sync, Cleanup & Callback")

    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.environ.get("SCOUT_WORKSPACE", os.path.dirname(script_dir))
    from utils.common import get_scope, get_state_dir
    scope = get_scope()

    produced_path = os.path.join(get_state_dir(), f"tmp/{scope}/produced_articles.json")
    triaged_path = os.path.join(get_state_dir(), f"tmp/{scope}/triaged_candidates.json")

    if not os.path.exists(produced_path):
        print(f"[!] Error: Produced articles file missing: {produced_path}")
        sys.exit(1)

    with open(produced_path, 'r', encoding='utf-8') as f:
        produced_articles = json.load(f)

    # Load triaged candidates to find which ones failed
    triaged_articles = []
    if os.path.exists(triaged_path):
        try:
            with open(triaged_path, 'r', encoding='utf-8') as f:
                triaged_articles = json.load(f)
        except Exception:
            pass

    now = datetime.now()
    date_iso = now.strftime('%Y-%m-%dT%H:%M:%SZ')
    date_prefix = now.strftime('%Y-%m-%d')

    output_dir = os.path.join(get_state_dir(), f"push/{scope}")
    os.makedirs(output_dir, exist_ok=True)

    hm = HistoryManager(root_dir)

    # 1. Save successfully produced articles as Markdown
    successful_urls = set()
    for art in produced_articles:
        try:
            url, _ = _save_produced_article(art, output_dir, date_prefix, date_iso)
            successful_urls.add(url)
        except Exception as e:
            print(f"  [!] Failed to save or log produced article '{art.get('title')}': {e}")

    # 2. Poison Pill / Failed Article Logging
    _log_failed_candidates(triaged_articles, successful_urls, hm)

    # 2.5 Update the persistent backlog archive
    just_cleaned_path = os.path.join(get_state_dir(), f"tmp/{scope}/just_cleaned.json")
    just_cleaned_list = _load_just_cleaned(just_cleaned_path)
    hm.update_backlog(just_cleaned_list, successful_urls)

    # 3. Clean up raw crawled HTML cache
    raw_html_dir = os.path.join(get_state_dir(), f"tmp/{scope}/raw")
    if os.path.exists(raw_html_dir):
        print("  - Cleaning up temporary raw crawl directory...")
        try:
            shutil.rmtree(raw_html_dir)
            os.makedirs(raw_html_dir, exist_ok=True)
            print("  [+] Cleaned raw HTML cache.")
        except Exception as e:
            print(f"    [!] Error cleaning {raw_html_dir}: {e}")

    # 4. Prune older history
    print("  - Pruning old history entries...")
    try:
        hm.prune(url_days_limit=7)
        print("  [+] Pruning complete.")
    except Exception as e:
        print(f"    [!] Error pruning history: {e}")

    # 5. Output Orchestrator Callback JSON Status File
    summary_path = os.path.join(get_state_dir(), f"tmp/{scope}/sync_summary.json")
    summary = {
        "status": "success",
        "processed_count": len(produced_articles),
        "timestamp": datetime.now().isoformat(),
        "files_written": [f"{date_prefix}-{slugify(art['title'])}.md" for art in produced_articles]
    }
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=4)

    print(f"\n>>> Phase 5 Complete. Status summary written to '{summary_path}'")

if __name__ == "__main__":
    main()


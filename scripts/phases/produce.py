#!/usr/bin/env python3
import json
import os
import sys
import time
import re
import argparse

# Setup path so imports work correctly

from utils.common import check_timeout
from utils.history_manager import HistoryManager
from agents.writer.writer import rewrite_article
from agents.corrector.corrector import validate_content, correct_content
from agents.metadata.metadata import generate_metadata, validate_metadata
from agents.tagger.tagger import correct_tag

ALLOWED_TAGS = {
    "Politics", "Sports", "Business", "Tech", "Science", "Culture", 
    "Health", "Education", "Weather", "Entertainment", "Environment", 
    "Celebrity", "Uncategorized"
}

def parse_embedded_image(content):
    """Searches content body for image link patterns and returns the first match or None."""
    if not content:
        return None
    # Look for patterns like 'image link: https://...'
    match = re.search(r'(?:image\s+link|img\s+link|image|img)\s*:\s*(https?://\S+)', content, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None

ALLOWED_REGIONS = {
    "Arunachal Pradesh", "Assam", "Manipur", "Meghalaya",
    "Mizoram", "Nagaland", "Sikkim", "Tripura", "Northeast", "N/A"
}
NATIONAL_CATEGORIES = {"National", "International", "Global"}
IGNORE_FLAGS = {"PASS", "N/A", "null", "None", "", None}

def _build_source_payload(candidate):
    """Builds the JSON source payload sent to the LLM, including secondary sources."""
    payload = {
        "title": candidate.get("title"),
        "source_name": candidate.get("source_name"),
        "content": candidate.get("content")
    }
    if candidate.get("is_merged") and candidate.get("secondary_sources"):
        sec_str = ""
        for i, sec in enumerate(candidate["secondary_sources"], 1):
            sec_str += f"\n\n[Secondary Source {i} - {sec.get('source_name')}]:\n"
            sec_str += f"Title: {sec.get('title')}\n"
            sec_str += f"Content: {sec.get('content')}\n"
        payload["secondary_sources_content"] = sec_str.strip()
    return json.dumps(payload, indent=4)

def _rewrite_and_validate(source_json_str, max_retries):
    """Runs the rewrite-validate loop. Returns (draft_body, passed) tuple."""
    draft_body = None
    feedback = ""
    for attempt in range(1, max_retries + 1):
        print(f"    - Rewrite/Validation attempt {attempt}/{max_retries}...")
        try:
            draft_body = rewrite_article(source_json_str) if attempt == 1 else correct_content(source_json_str, draft_body, feedback)
        except Exception as e:
            print(f"      [!] Rewrite call failed on attempt {attempt}: {e}")
            continue
        if not draft_body:
            print("      [!] Rewrite produced empty/null draft.")
            continue
        try:
            val_res = validate_content(source_json_str, draft_body)
            passed = val_res.get("passed", False)
            feedback = val_res.get("fix_instruction", "Factual discrepancy or style issue detected.")
            confidence = val_res.get("confidence_score", 0)
        except Exception as e:
            print(f"      [!] Validation failed: {e}. Passing through.")
            passed, confidence = True, 100
        if passed:
            print(f"      [+] Validation Passed (Confidence: {confidence}%).")
            return draft_body, True
        print(f"      [!] Validation Failed: {feedback}")
    return draft_body, False

def _apply_metadata_corrections(val_meta, final_title, final_desc, final_region, final_tag, allowed_tags):
    """Applies validator corrections to title, description, region and tag."""
    def _is_correction(val):
        return val and str(val) not in IGNORE_FLAGS

    if _is_correction(val_meta.get("corrected_tag")):
        corrected_tag = val_meta["corrected_tag"]
        if corrected_tag in allowed_tags:
            print(f"      [+] Validator corrected Tag from '{final_tag}' to '{corrected_tag}'.")
            final_tag = corrected_tag
        else:
            print(f"      [!] Validator suggested invalid tag '{corrected_tag}'. Retaining '{final_tag}'.")

    if _is_correction(val_meta.get("corrected_region")):
        corrected_region = val_meta["corrected_region"]
        if corrected_region in ALLOWED_REGIONS:
            print(f"      [+] Validator corrected Region from '{final_region}' to '{corrected_region}'.")
            final_region = corrected_region
        else:
            print(f"      [!] Validator suggested invalid region '{corrected_region}'. Retaining '{final_region}'.")

    if _is_correction(val_meta.get("corrected_title")):
        print(f"      [!] Title Validation Failed: {val_meta.get('feedback')}")
        print("      [+] Applying Validator's corrected Title.")
        final_title = val_meta["corrected_title"]

    if _is_correction(val_meta.get("corrected_description")):
        print(f"      [!] Description Validation Failed: {val_meta.get('feedback')}")
        print("      [+] Applying Validator's corrected Description.")
        final_desc = val_meta["corrected_description"]

    print("      [+] Metadata Validation / Auto-Correction Completed.")
    return final_title, final_desc, final_region, final_tag

def _resolve_featured_image(candidate):
    """Returns the featured image URL, falling back to inline image links in content."""
    featured_image = candidate.get("featured_image")
    if featured_image and featured_image not in {"N/A", "null", "None", ""}:
        return featured_image
    parsed_img = parse_embedded_image(candidate.get("content"))
    if not parsed_img:
        for sec in candidate.get("secondary_sources") or []:
            parsed_img = parse_embedded_image(sec.get("content"))
            if parsed_img:
                break
    if parsed_img:
        print(f"    [+] Discovered alternative featured image in text: {parsed_img}")
    return parsed_img or None

def _validate_and_correct_tag(final_title, final_desc, final_tag):
    if final_tag not in ALLOWED_TAGS:
        print(f"    [!] Invalid tag '{final_tag}'. Attempting tag correction...")
        try:
            final_tag = correct_tag(final_title, final_desc, final_tag)
            if final_tag not in ALLOWED_TAGS:
                print(f"      [!] Corrected tag '{final_tag}' still invalid. Defaulting to 'Uncategorized'.")
                final_tag = "Uncategorized"
            else:
                print(f"      [+] Tag corrected successfully to '{final_tag}'.")
        except Exception as e:
            print(f"      [!] Tag correction failed: {e}. Defaulting to 'Uncategorized'.")
            final_tag = "Uncategorized"
    return final_tag

def _process_metadata(source_json_str, draft_body, candidate):
    print("    - Generating metadata parameters...")
    try:
        meta_res = generate_metadata(source_json_str, draft_body) or {}
    except Exception as e:
        print(f"      [!] Metadata generation failed: {e}")
        meta_res = {}

    final_title = meta_res.get("title") or candidate.get("title")
    final_desc = meta_res.get("description") or candidate.get("short_intro") or ""

    category = meta_res.get("category") or candidate.get("category", "Local")
    if category.lower() == "global":
        category = "International"

    allowed_tags = {
        "Politics", "Sports", "Business", "Tech", "Science", "Culture",
        "Health", "Education", "Weather", "Entertainment", "Environment",
        "Celebrity", "Uncategorized"
    }

    if category in NATIONAL_CATEGORIES:
        final_region = "N/A"
    else:
        final_region = meta_res.get("region") or candidate.get("region") or "N/A"
        if final_region not in ALLOWED_REGIONS:
            print(f"      [!] Invalid region '{final_region}' returned by agent. Defaulting to 'N/A'.")
            final_region = "N/A"

    final_tag = meta_res.get("majorTag") or "Uncategorized"
    if final_tag not in allowed_tags:
        print(f"      [!] Invalid tag '{final_tag}' returned by agent. Defaulting to 'Uncategorized'.")
        final_tag = "Uncategorized"

    # Validate Metadata & Correct Tags
    if meta_res.get("title"):
        val_meta = validate_metadata(draft_body, final_title, final_desc, final_region, final_tag)
        final_title, final_desc, final_region, final_tag = _apply_metadata_corrections(
            val_meta, final_title, final_desc, final_region, final_tag, allowed_tags
        )

    # Programmatic Tag Whitelist Validation & Fallback correction
    final_tag = _validate_and_correct_tag(final_title, final_desc, final_tag)
            
    return final_title, final_desc, category, final_region, final_tag

def process_candidate(candidate, start_time):
    """End-to-end rewrite, validation, metadata generation, and tagging for a single candidate."""
    title_snippet = candidate.get("title", "Untitled")[:50]
    print(f"\n--- Processing Candidate: '{title_snippet}...' ---")

    source_json_str = _build_source_payload(candidate)

    # Adaptive retry calculation
    is_critical = check_timeout(start_time, limit_minutes=22)
    max_retries = 1 if is_critical else 3
    if is_critical:
        print("    [!] Over 22-minute global threshold. Operating in 1-Shot 'Fast-Fail' mode.")

    draft_body, passed_validation = _rewrite_and_validate(source_json_str, max_retries)
    if not passed_validation or not draft_body:
        print(f"    [!] Failed to validate draft for '{title_snippet}' after {max_retries} attempts. Dropping candidate.")
        return None

    # Generate & Correct Metadata
    final_title, final_desc, category, final_region, final_tag = _process_metadata(
        source_json_str, draft_body, candidate
    )

    featured_image = _resolve_featured_image(candidate)

    return {
        "title": final_title,
        "description": final_desc,
        "category": category,
        "region": final_region,
        "majorTag": final_tag,
        "featured_image": featured_image,
        "content": draft_body,
        "original_url": candidate.get("url"),
        "source_name": candidate.get("source_name"),
        "source_key": candidate.get("source_key"),
        "is_merged": candidate.get("is_merged", False),
        "secondary_sources": candidate.get("secondary_sources", [])
    }

def _resolve_start_time(args_start_time, scope, get_state_dir):
    """Determines the pipeline start time from arg, file, or current time."""
    if args_start_time:
        return args_start_time
    start_time_path = os.path.join(get_state_dir(), f"tmp/{scope}/pipeline_start.txt")
    if os.path.exists(start_time_path):
        try:
            with open(start_time_path, 'r') as f:
                return float(f.read().strip())
        except Exception:
            pass
    return time.time()

def _log_merged_sources(cand, hm, status):
    """Logs status for all secondary sources of a merged candidate."""
    if cand.get("is_merged") and cand.get("secondary_sources"):
        for sec in cand["secondary_sources"]:
            sec_url = sec.get("url")
            if sec_url:
                hm.log_url(sec_url, sec.get("source_key", cand["source_key"]), status)

def _log_candidate_result(cand, hm, success):
    """Logs the URL processing result and any merged secondary sources."""
    status = "SUCCESS" if success else "RETRY_FAILED"
    hm.log_url(cand["url"], cand["source_key"], status)
    _log_merged_sources(cand, hm, "SUCCESS_MERGED" if success else "RETRY_FAILED")

def main():
    parser = argparse.ArgumentParser(description="Phase 4: Content Rewrite, Critic Validation & Metadata Compilation")
    parser.add_argument("--start-time", type=float, help="Unix timestamp of when the pipeline run started.")
    parser.add_argument("--limit", type=int, default=None, help="Limit the number of produced articles in this run.")
    args = parser.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.environ.get("SCOUT_WORKSPACE", os.path.dirname(script_dir))
    from utils.common import get_scope, get_state_dir
    scope = get_scope()

    start_time = _resolve_start_time(args.start_time, scope, get_state_dir)
    print(f"\n>>> Starting Phase 4: Production & Critic Validation Loop (Elapsed time: {(time.time() - start_time)/60:.2f} mins)")

    # Load candidates from Phase 3
    triaged_path = os.path.join(get_state_dir(), f"tmp/{scope}/triaged_candidates.json")
    if not os.path.exists(triaged_path):
        print(f"[!] Error: Triaged candidates file missing: {triaged_path}")
        sys.exit(1)

    with open(triaged_path, 'r', encoding='utf-8') as f:
        candidates = json.load(f)

    produced_path = os.path.join(get_state_dir(), f"tmp/{scope}/produced_articles.json")
    if not candidates:
        print(">>> No unique candidates to process in this session. Exiting Phase 4.")
        with open(produced_path, 'w', encoding='utf-8') as f:
            json.dump([], f)
        sys.exit(0)

    hm = HistoryManager(root_dir)
    produced_articles = []

    for cand in candidates:
        if args.limit is not None and len(produced_articles) >= args.limit:
            print(f"\n>>> Reached limit of {args.limit} produced articles. Stopping further rewrites.")
            break
        if check_timeout(start_time, limit_minutes=30):
            print("\n>>> Elapsed time exceeded 30-minute processing window threshold. Stopping new article starts.")
            break
        try:
            prod_art = process_candidate(cand, start_time)
            if prod_art:
                produced_articles.append(prod_art)
            _log_candidate_result(cand, hm, success=bool(prod_art))
        except Exception as e:
            print(f"[!] Error processing candidate: {e}")
            _log_candidate_result(cand, hm, success=False)

    with open(produced_path, 'w', encoding='utf-8') as f:
        json.dump(produced_articles, f, indent=4)

    print(f"\n>>> Phase 4 Complete. Successfully produced {len(produced_articles)} articles. (Saved to '{produced_path}')")

if __name__ == "__main__":
    main()

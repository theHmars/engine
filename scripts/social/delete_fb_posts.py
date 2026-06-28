#!/usr/bin/env python3
import os
import sys
import time
import argparse
import requests

# Ensure we can import from clean_fb
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from clean_fb import fetch_facebook_posts, extract_slug_from_post, delete_facebook_post, load_environment

def main():
    parser = argparse.ArgumentParser(description="Facebook Selective Post Deleter")
    parser.add_argument("slugs", nargs="*", help="List of article slugs to search for and delete")
    parser.add_argument("--interactive", action="store_true", default=True, help="Prompt before deletion (default true)")
    parser.add_argument("--force", action="store_true", help="Do not prompt before deletion")
    args = parser.parse_args()

    # Get slugs from args or stdin
    target_slugs = [s.replace('.md', '').strip() for s in args.slugs]
    if not sys.stdin.isatty():
        target_slugs.extend([line.strip().replace('.md', '') for line in sys.stdin if line.strip()])

    if not target_slugs:
        print("[!] No target slugs provided. Pass slugs as arguments or pipe them via stdin.")
        sys.exit(1)

    load_environment()
    page_id = os.environ.get("FB_PAGE_ID")
    access_token = os.environ.get("FB_PAGE_ACCESS_TOKEN")
    
    if not page_id or not access_token:
        print("[!] Error: Missing FB_PAGE_ID or FB_PAGE_ACCESS_TOKEN variables in environment.")
        sys.exit(1)

    print(f"[*] Targeting {len(target_slugs)} specific slug(s) for deletion.")
    
    print("[*] Fetching scheduled Facebook posts...")
    scheduled_posts = fetch_facebook_posts(page_id, access_token, "scheduled_posts")
    print(f"[*] Retrieved {len(scheduled_posts)} scheduled posts.")
    
    print("[*] Fetching recent Facebook feed posts...")
    feed_posts = fetch_facebook_posts(page_id, access_token, "feed", max_pages=5)
    print(f"[*] Retrieved {len(feed_posts)} published posts.")
    
    all_fb_posts = [("scheduled", p) for p in scheduled_posts] + [("published", p) for p in feed_posts]
    
    matches = []
    
    for post_type, post in all_fb_posts:
        slug = extract_slug_from_post(post)
        if slug and slug in target_slugs:
            matches.append((post_type, post, slug))

    if not matches:
        print("[-] No matching posts found on Facebook for the provided slugs.")
        sys.exit(0)

    print(f"\n[+] Found {len(matches)} matching post(s) on Facebook:")
    for idx, (post_type, post, slug) in enumerate(matches, 1):
        scheduled_info = ""
        if post_type == "scheduled":
            pub_time = int(post.get("scheduled_publish_time", 0))
            readable_time = time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(pub_time))
            scheduled_info = f" (Scheduled for {readable_time})"
        print(f"  #{idx}: [{post_type.upper()}] ID: {post.get('id')}{scheduled_info}\n       Slug: {slug}\n       Message: {post.get('message', '')[:80]}...")

    if not args.force:
        confirm = input(f"\n[?] Do you want to delete these {len(matches)} post(s) from Facebook? (y/N): ")
        if confirm.lower() != 'y':
            print("[-] Deletion aborted by user.")
            sys.exit(0)
            
    print(f"\n[*] Proceeding to delete {len(matches)} post(s)...")
    deleted_count = 0
    for post_type, post, slug in matches:
        post_id = post.get("id")
        print(f"  [-] Deleting [{post_type.upper()}] Post ID: {post_id} (Slug: {slug})...")
        success = delete_facebook_post(post_id, access_token)
        if success:
            deleted_count += 1
            time.sleep(1) # rate-limit gap
            
    print(f"\n[+] Successfully deleted {deleted_count} out of {len(matches)} post(s).")

if __name__ == "__main__":
    main()

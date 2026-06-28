import os
import json
import time
from datetime import datetime, timedelta

class HistoryManager:
    def __init__(self, root_dir: str):
        self.root_dir = root_dir

        # Import here to avoid circular imports at module load time
        from utils.common import get_scope
        scope = get_scope()

        # History is centralized in the content repository database
        content_repo = os.environ.get("WEBSITE_REPO_PATH")
        if not content_repo:
            print("[!] WEBSITE_REPO_PATH not set, falling back to engine root.")
            content_repo = root_dir

        self.history_dir = os.path.join(content_repo, f"history/{scope}")
        self.archive_path = os.path.join(content_repo, f"history/{scope}/archive.json")

    def _get_history_path(self, source_key: str) -> str:
        return os.path.join(self.history_dir, f"sources/{source_key}_processed.json")

    def load_source_history(self, source_key: str) -> list:
        path = self._get_history_path(source_key)
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"  [!] Failed to parse {path}: {e}. Resetting.")
        return []

    def save_source_history(self, source_key: str, history_list: list):
        path = self._get_history_path(source_key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(history_list, f, indent=4)

    def is_url_processed(self, url: str, source_key: str) -> bool:
        """Checks if a URL has already been processed or permanently failed."""
        history = self.load_source_history(source_key)
        for item in history:
            if item.get("url") == url:
                # RETRY_FAILED status signifies transient failures that should be retried
                if item.get("status") == "RETRY_FAILED":
                    return False
                return True
        return False

    def log_url(self, url: str, source_key: str, status: str):
        """Logs a URL with SUCCESS, SUCCESS_MERGED, RETRY_FAILED, or FAILED_OR_ABANDONED."""
        history = self.load_source_history(source_key)
        # Avoid duplicate logs for the same URL
        for item in history:
            if item.get("url") == url:
                item["processed_at"] = datetime.now().isoformat()
                item["status"] = status
                break
        else:
            history.append({
                "url": url,
                "processed_at": datetime.now().isoformat(),
                "status": status
            })
        self.save_source_history(source_key, history)



    def update_backlog(self, just_cleaned: list, successful_urls: set):
        """Syncs the 48-hour archive backlog, removing successfully processed items."""
        existing_archive = []
        if os.path.exists(self.archive_path):
            try:
                with open(self.archive_path, 'r', encoding='utf-8') as f:
                    existing_archive = json.load(f)
            except:
                pass
                
        # Combine lists (indexed by URL to avoid duplication)
        combined = {}
        for art in (existing_archive + just_cleaned):
            url = art.get("url")
            if url:
                combined[url] = art
                
        cutoff = datetime.now() - timedelta(hours=48)
        final_archive = []
        
        for url, art in combined.items():
            if url in successful_urls:
                continue
            try:
                cleaned_time = datetime.fromisoformat(art.get("cleaned_at", datetime.now().isoformat()))
                if cleaned_time >= cutoff:
                    final_archive.append(art)
            except:
                final_archive.append(art)
                
        os.makedirs(os.path.dirname(self.archive_path), exist_ok=True)
        with open(self.archive_path, 'w', encoding='utf-8') as f:
            json.dump(final_archive, f, indent=4)
        print(f"  [+] Updated persistent backlog archive with {len(final_archive)} items.")

    def prune(self, url_days_limit=7, topic_days_limit=3):
        """Prunes historical entries older than the threshold to keep files lightweight."""
        now = time.time()
        
        # 1. Clean URL history
        seconds_to_keep_urls = url_days_limit * 24 * 60 * 60
        sources_dir = os.path.join(self.history_dir, "sources")
        if os.path.exists(sources_dir):
            for filename in os.listdir(sources_dir):
                if filename.endswith('_processed.json'):
                    source_key = filename.replace('_processed.json', '')
                    history = self.load_source_history(source_key)
                    new_history = []
                    for art in history:
                        try:
                            proc_time = datetime.fromisoformat(art['processed_at']).timestamp()
                            if now - proc_time < seconds_to_keep_urls:
                                new_history.append(art)
                        except:
                            new_history.append(art)
                    self.save_source_history(source_key, new_history)



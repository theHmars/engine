import re
import unicodedata
import os
import time
import json
from datetime import datetime

def get_state_dir():
    """
    Returns the root directory for all stateful writes (tmp, push, data, quarantine).
    Defaults to the engine workspace directory, but can be overridden for read-only server architectures.
    """
    root_dir = os.environ.get("SCOUT_WORKSPACE", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.environ.get("ENGINE_STATE_DIR", root_dir)

def get_tmp_dir(scope=None):
    if scope is None:
        scope = get_scope()
    path = os.path.join(get_state_dir(), "tmp", scope)
    os.makedirs(path, exist_ok=True)
    return path

def slugify(value):
    """
    Normalizes string, converts to lowercase, removes non-alpha characters,
    and converts spaces to hyphens.
    """
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    value = re.sub(r'[^\w\s-]', '', value).strip().lower()
    return re.sub(r'[-\s]+', '-', value)

def get_time_slot():
    """Returns the current time slot string: 9AM, 12PM, 3PM, 9PM"""
    hour = int(time.strftime("%H"))
    if hour >= 21 or hour < 9: return "9PM"
    if hour >= 15: return "3PM"
    if hour >= 12: return "12PM"
    return "9AM"

def check_timeout(start_time, limit_minutes=13):
    """Returns True if we should stop processing new articles."""
    elapsed = (time.time() - start_time) / 60
    return elapsed >= limit_minutes

def ensure_dirs(source_slug):
    """Ensures necessary directories exist for a source using canonical state paths."""
    scope = get_scope()
    state_dir = get_state_dir()
    dirs = [
        os.path.join(state_dir, f"data/{scope}/1"),
        os.path.join(state_dir, f"data/{scope}/cleaned/{source_slug}"),
        os.path.join(state_dir, f"data/{scope}/3"),
        os.path.join(state_dir, "data/2")
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)

def get_scope():
    return os.environ.get('SCOUT_SCOPE', 'local')

def load_source_history(source_key):
    root_dir = os.environ.get("SCOUT_WORKSPACE", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    content_repo = os.environ.get("WEBSITE_REPO_PATH", root_dir)
    scope = get_scope()
    path = os.path.join(content_repo, f"history/{scope}/sources/{source_key}_processed.json")
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"  [!] Failed to parse {path}: {e}. Resetting.")
    return []

def save_source_history(source_key, history_list):
    root_dir = os.environ.get("SCOUT_WORKSPACE", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    content_repo = os.environ.get("WEBSITE_REPO_PATH", root_dir)
    scope = get_scope()
    path = os.path.join(content_repo, f"history/{scope}/sources/{source_key}_processed.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(history_list, f, indent=4)



def cleanup_history(days_to_keep=7):
    """Removes entries older than X days from both history files."""
    now = time.time()
    seconds_to_keep = days_to_keep * 24 * 60 * 60
    root_dir = os.environ.get("SCOUT_WORKSPACE", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    content_repo = os.environ.get("WEBSITE_REPO_PATH", root_dir)
    scope = get_scope()
    history_dir = os.path.join(content_repo, f"history/{scope}/sources")
    if os.path.exists(history_dir):
        for filename in os.listdir(history_dir):
            if filename.endswith('_processed.json'):
                source_key = filename.replace('_processed.json', '')
                history = load_source_history(source_key)
                new_articles = []
                for art in history:
                    try:
                        proc_time = datetime.fromisoformat(art['processed_at']).timestamp()
                        if now - proc_time < seconds_to_keep:
                            new_articles.append(art)
                    except:
                        new_articles.append(art)
                save_source_history(source_key, new_articles)

def load_topics(category="local"):
    """Loads topics.json for the specified category to provide context to agents."""
    root_dir = os.environ.get("SCOUT_WORKSPACE", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    content_repo = os.environ.get("WEBSITE_REPO_PATH", root_dir)
    path = os.path.join(content_repo, f"history/{category}/topics.json")
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return {"topics": list(data.keys())} if isinstance(data, dict) else {"topics": []}
        except:
            pass
    return {"topics": []}

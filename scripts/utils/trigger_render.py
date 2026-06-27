import os
import sys
import requests

def trigger_render():
    """Triggers the Render deployment hook directly."""
    # Load .env relative to this script natively without python-dotenv
    script_dir = os.path.dirname(os.path.abspath(__file__))
    engine_dir = os.path.dirname(os.path.dirname(script_dir))
    env_path = os.path.join(engine_dir, '.env')
    
    hook_url = os.environ.get("RENDER_DEPLOY_HOOK")
    
    if not hook_url and os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                if line.startswith('RENDER_DEPLOY_HOOK='):
                    hook_url = line.split('=', 1)[1].strip().strip('"').strip("'")
                    break
    if not hook_url:
        print("[!] Error: RENDER_DEPLOY_HOOK is not set in the environment.")
        sys.exit(1)

    print(f">>> Triggering Render Deployment: {hook_url}")
    try:
        response = requests.get(hook_url, timeout=15)
        if response.status_code == 200:
            print("[+] Successfully triggered Render build!")
            print("    Response:", response.text)
        else:
            print(f"[!] Render hook returned status {response.status_code}")
            print("    Response:", response.text)
            sys.exit(1)
    except Exception as e:
        print(f"[!] Failed to trigger Render hook: {e}")
        sys.exit(1)

if __name__ == "__main__":
    trigger_render()

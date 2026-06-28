#!/usr/bin/env python3
import os
import sys
import time
import subprocess
from datetime import datetime

def run_phase(command, cwd):
    """Executes a pipeline phase as a subprocess, ensuring isolated namespace and proper error handling."""
    print(f"\n>> Executing: {' '.join(command)}")
    try:
        env = os.environ.copy()
        env["PYTHONPATH"] = os.path.join(cwd, "scripts")
        res = subprocess.run(command, cwd=cwd, env=env, check=True)
        return res.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"\n[CRITICAL FAILURE] Phase execution failed: {e}")
        return False
    except Exception as e:
        print(f"\n[CRITICAL FAILURE] Unexpected error launching phase: {e}")
        return False

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', default=os.environ.get('SCOUT_WORKSPACE', os.getcwd()), help='Path to scout workspace')
    parser.add_argument('--scope', default=os.environ.get('SCOUT_SCOPE', 'local'), help='Pipeline scope (local, national, global)')
    parser.add_argument('--limit', type=int, default=None, help='Max articles to produce')
    args = parser.parse_known_args()[0]
    
    workspace_dir = os.path.abspath(args.workspace)
    scope = args.scope.lower()
    os.environ['SCOUT_WORKSPACE'] = workspace_dir
    os.environ['SCOUT_SCOPE'] = scope

    print("========================================")
    print(f" NEWS AUTOMATION PIPELINE - STARTED")
    print(f" Workspace: {workspace_dir}")
    print(f" Scope:     {scope.upper()}")
    print(f" {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("========================================\n")
    
    start_time = time.time()
    local_dir = os.path.dirname(os.path.abspath(__file__))
    python_bin = os.path.join(workspace_dir, ".venv/bin/python3")
    if not os.path.exists(python_bin):
        python_bin = sys.executable # Fallback to current runner python
        
    # Write the pipeline start time so subsequent scripts synchronize their timeout triggers
    os.makedirs(os.path.join(workspace_dir, "tmp", scope), exist_ok=True)
    start_time_path = os.path.join(workspace_dir, "tmp", scope, "pipeline_start.txt")
    with open(start_time_path, 'w') as f:
        f.write(str(start_time))
        
    # Validate API key is set (load from workspace first, fallback to engine dir)
    from dotenv import load_dotenv
    env_path = os.path.join(workspace_dir, '.env')
    if not os.path.exists(env_path):
        env_path = os.path.join(local_dir, '.env')
    load_dotenv(env_path)
    
    # Check for any LLM_API_KEY or LLM_API_KEY_1 etc
    has_key = os.environ.get('LLM_API_KEY') or any(os.environ.get(f'LLM_API_KEY_{i}') for i in range(1, 10))
    if not has_key:
        print('[CRITICAL] No LLM_API_KEY or LLM_API_KEY_X set in env or .env file. Aborting.')
        sys.exit(1)
        
    # Build produce phase command dynamically based on limit config
    produce_cmd = [python_bin, os.path.join(local_dir, "scripts/phases/produce.py"), "--start-time", str(start_time)]
    if args.limit is not None:
        produce_cmd.extend(["--limit", str(args.limit)])

    # Define phase sequence with absolute paths to the scripts in the engine repo
    is_mock = os.environ.get("TEST_MODE_MOCK_DATA") == "true"
    if is_mock:
        print("\n[!] TEST_MODE_MOCK_DATA=true. Bypassing Phase 1 (RSS & Scraping) to use mock data.")
        phases = [
            [python_bin, os.path.join(local_dir, "scripts/phases/triage.py")],
            [python_bin, os.path.join(local_dir, "scripts/phases/deduplicate.py")],
            produce_cmd,
            [python_bin, os.path.join(local_dir, "scripts/phases/cleanup.py")]
        ]
    else:
        phases = [
            [python_bin, os.path.join(local_dir, "scripts/phases/get_rss.py")],
            [python_bin, os.path.join(local_dir, "scripts/utils/clean_html.py")],
            [python_bin, os.path.join(local_dir, "scripts/phases/triage.py")],
            [python_bin, os.path.join(local_dir, "scripts/phases/deduplicate.py")],
            produce_cmd,
            [python_bin, os.path.join(local_dir, "scripts/phases/cleanup.py")]
        ]
    
    for command in phases:
        if not run_phase(command, workspace_dir):
            print("\n========================================")
            print(" PIPELINE RUN FAILED")
            print("========================================")
            sys.exit(1)
            
    elapsed = (time.time() - start_time) / 60
    print("\n========================================")
    print(f" PIPELINE COMPLETE (Duration: {elapsed:.2f} mins)")
    print("========================================")

if __name__ == "__main__":
    main()

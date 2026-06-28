#!/bin/bash
# test_pipeline.sh
# Creates a true physical sandbox mirror of the GitHub Actions runner.

cd "$(dirname "$0")"

mkdir -p tmp
LOG_FILE="tmp/test_run_$(date +%s).log"
exec > >(tee -i "$LOG_FILE") 2>&1
export PYTHONUNBUFFERED=1

echo "========================================="
echo " CONSTRUCTING PHYSICAL SANDBOX ENVIRONMENT"
echo " (Logs are being saved to $LOG_FILE)"
echo "========================================="

# 1. Build Physical Sandbox Directory Structure
rm -rf tmp/mock_test 2>/dev/null || true
mkdir -p tmp/mock_test/{engine,content,frontend,workspace_state}

echo "[-] Syncing engine repository..."
rsync -a --exclude 'tmp' --exclude '.venv' --exclude '__pycache__' --exclude 'push' --exclude 'quarantine' --exclude '.git' ./ tmp/mock_test/engine/
ln -s ../../../.venv tmp/mock_test/engine/.venv

echo "[-] Syncing frontend repository..."
rsync -a --exclude 'node_modules' --exclude 'dist' --exclude '.git' ../frontend/ tmp/mock_test/frontend/
ln -s ../../../../frontend/node_modules tmp/mock_test/frontend/node_modules

echo "[-] Initializing Mock Content repository..."
cd tmp/mock_test/content
mkdir -p markdown/local markdown/national markdown/global
mkdir -p history/local/sources history/national/sources history/global/sources
mkdir -p quarantine/local quarantine/render
mkdir -p scripts
echo "print('[MOCK] update_indices.py ran successfully.')" > scripts/update_indices.py
git init -q
git config user.name "test-bot"
git config user.email "test-bot@localhost"
git commit -q --allow-empty -m "Initial mock commit"
cd ../../..

# 2. Setup Environment Variables
set -a
source .env 2>/dev/null || true
source test.env 2>/dev/null || true
set +a

# Default overrides if test.env is missing
export PIPELINE_SCOPE="${PIPELINE_SCOPE:-local}"
export ARTICLES_PER_SCOPE="${ARTICLES_PER_SCOPE:-1}"
export TEST_MODE_AGENTS="${TEST_MODE_AGENTS:-true}"
export TEST_MODE_MOCK_DATA="${TEST_MODE_MOCK_DATA:-true}"
export LLM_API_KEY="${LLM_API_KEY:-FAKE_KEY}"
export TEST_MODE_ENABLED="true"

# Define the precise sandbox paths just like the GH Runner
export SCOUT_WORKSPACE="$(pwd)/tmp/mock_test/engine"
export WEBSITE_REPO_PATH="$(pwd)/tmp/mock_test/content"
export FRONTEND_REPO_PATH="$(pwd)/tmp/mock_test/frontend"
export ENGINE_STATE_DIR="$(pwd)/tmp/mock_test/workspace_state"

# 3. Inject Mock Data
if [ "$TEST_MODE_MOCK_DATA" == "true" ] && [ "$TEST_MODE_AGENTS" == "true" ]; then
    echo "[*] Injecting fake 'covered.json'..."
    cp ../mock-data/covered.json "$WEBSITE_REPO_PATH/history/covered.json"
    
    echo "[*] Injecting perfectly crafted mock semantic duplicates into pipeline state..."
    scopes=()
    if [ "$PIPELINE_SCOPE" == "all" ]; then
        scopes=("local" "national" "global")
    else
        scopes=("$PIPELINE_SCOPE")
    fi
    
    for s in "${scopes[@]}"; do
        mkdir -p "$ENGINE_STATE_DIR/tmp/$s"
        
        # Inject the mock candidate JSON files
        cp ../mock-data/article1.json "$ENGINE_STATE_DIR/tmp/$s/"
        cp ../mock-data/article2.json "$ENGINE_STATE_DIR/tmp/$s/"
        cp ../mock-data/article3.json "$ENGINE_STATE_DIR/tmp/$s/"
        cp ../mock-data/article4.json "$ENGINE_STATE_DIR/tmp/$s/"
        
        # Generate the cleaned_candidates.json with dynamic paths pointing to the correct state directory
        cat <<EOF > "$ENGINE_STATE_DIR/tmp/$s/cleaned_candidates.json"
{
  "active_candidates": [
    {
      "url": "https://example.com/article1",
      "source_key": "mock_news",
      "clean_path": "$ENGINE_STATE_DIR/tmp/$s/article1.json"
    },
    {
      "url": "https://example.com/article2",
      "source_key": "mock_news",
      "clean_path": "$ENGINE_STATE_DIR/tmp/$s/article2.json"
    },
    {
      "url": "https://example.com/article3",
      "source_key": "mock_news",
      "clean_path": "$ENGINE_STATE_DIR/tmp/$s/article3.json"
    },
    {
      "url": "https://example.com/blocked-url",
      "source_key": "mock_news",
      "clean_path": "$ENGINE_STATE_DIR/tmp/$s/article4.json"
    }
  ],
  "archived_candidates_last_48h": []
}
EOF
    done
else
    echo "[]" > "$WEBSITE_REPO_PATH/history/covered.json"
fi


echo "========================================="
echo " EXECUTING ENGINE WITHIN PHYSICAL SANDBOX"
echo "========================================="
cd "$SCOUT_WORKSPACE"

# 4. Run Engine Pipeline
if [ "$TEST_MODE_AGENTS" == "true" ]; then
    if [ "$PIPELINE_SCOPE" == "all" ]; then
        .venv/bin/python3 main.py --scope local --limit $ARTICLES_PER_SCOPE
        .venv/bin/python3 main.py --scope national --limit $ARTICLES_PER_SCOPE
        .venv/bin/python3 main.py --scope global --limit $ARTICLES_PER_SCOPE
    else
        .venv/bin/python3 main.py --scope $PIPELINE_SCOPE --limit $ARTICLES_PER_SCOPE
    fi
else
    echo "[*] TEST_MODE_AGENTS=false. Injecting FAKE markdown articles..."
    scopes=()
    if [ "$PIPELINE_SCOPE" == "all" ]; then
        scopes=("local" "national" "global")
    else
        scopes=("$PIPELINE_SCOPE")
    fi
    for s in "${scopes[@]}"; do
        for ((i=1; i<=ARTICLES_PER_SCOPE; i++)); do
            slug="2026-01-01-mock-article-$s-$i"
            filepath="$ENGINE_STATE_DIR/push/$s/$slug.md"
            mkdir -p "$ENGINE_STATE_DIR/push/$s"
            cat <<EOF > "$filepath"
---
title: "Mock Article $i for $s Scope"
description: "Fake test."
image: "/images/fallback.webp"
date: "2026-01-01"
---
Fake body content.
EOF
        done
    done
fi

# 5. Inspection Phase
echo ""
echo "[*] ========================================="
echo "[*]        SANDBOX DATA INSPECTION           "
echo "[*] ========================================="
echo ""
echo ">>> HISTORY (covered.json):"
cat "$WEBSITE_REPO_PATH/history/covered.json" 2>/dev/null || echo "  (Empty or not found)"
echo ""
echo ">>> GENERATED MARKDOWN ARTICLES:"
shopt -s nullglob
for file in "$ENGINE_STATE_DIR"/push/*/*.md; do
    echo "---------------------------------------------------"
    echo " FILE: $file"
    echo "---------------------------------------------------"
    cat "$file"
    echo ""
done
shopt -u nullglob

# 6. Markdown Validation
echo ""
echo "[*] Validating generated markdown..."
cd "$FRONTEND_REPO_PATH"
npm ci > /dev/null 2>&1
cd "$SCOUT_WORKSPACE"
.venv/bin/python3 scripts/utils/validate_markdown.py

# 7. Sync to Content Repo
echo ""
echo "[*] Syncing verified articles to Mock Content Repo..."
cp -r "$ENGINE_STATE_DIR"/push/local/* "$WEBSITE_REPO_PATH"/markdown/local/ 2>/dev/null || true
cp -r "$ENGINE_STATE_DIR"/push/national/* "$WEBSITE_REPO_PATH"/markdown/national/ 2>/dev/null || true
cp -r "$ENGINE_STATE_DIR"/push/global/* "$WEBSITE_REPO_PATH"/markdown/global/ 2>/dev/null || true
cp -r "$ENGINE_STATE_DIR"/quarantine/local/* "$WEBSITE_REPO_PATH"/quarantine/local/ 2>/dev/null || true
rm "$WEBSITE_REPO_PATH"/markdown/*.md 2>/dev/null || true

# 8. Unified Publisher Simulation
echo ""
echo "[*] Running Publisher Orchestrator against Sandbox..."
.venv/bin/python3 scripts/social/publisher.py

echo ""
echo "========================================="
echo " SANDBOX TEST COMPLETE"
echo " Inspect 'engine/tmp/mock_test/content' to verify git quarantine commits."
echo "========================================="

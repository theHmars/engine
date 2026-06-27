# Phase 5: Markdown Assembly & Cleanup

Phase 5 translates the JSON payloads into finalized Markdown files, updates poison-pill history ledgers, and prepares the ephemeral workspace for the orchestration hand-off.

## Architectural Overview

```mermaid
graph TD
    A[cleanup.py] -->|1. Reads Produced| B[tmp/{scope}/produced_articles.json]
    A -->|2. Assembler| C[push/{scope}/*.md]
    A -->|3. Updates Backlog| D[history/{scope}/archive.json]
    A -->|4. Poison Pills| E[HistoryManager Log]
    A -->|5. Generates Summary| F[tmp/{scope}/sync_summary.json]
```

## Technical Specifications

### 5.1 Markdown Generation
- Iterates over `produced_articles.json`.
- Utilizes `assembler.py` to construct a clean YAML frontmatter block containing the generated metadata.
- Concatenates the frontmatter and the article body and writes the raw string to a `.md` file in `push/{scope}/`.
- *Note: Syntax validation is intentionally bypassed here. Validating the generated YAML is the responsibility of the Astro compiler in the Pre-Flight check (`validate_markdown.py`).*

### 5.2 Poison Pill Logging
- Cross-references the initial queue (`triaged_candidates.json`) against the successful outputs.
- Any candidate that failed to produce is permanently logged in the source ledger as `FAILED_OR_ABANDONED`. This prevents the pipeline from entering an infinite loop trying to process a corrupted source article day after day.

### 5.3 Workspace Prep
- Merges unselected clean candidates into `archive.json` to act as the backlog for the next cron run.
- Wipes the `tmp/{scope}/raw/` HTML cache to free up runner disk space.
- Generates `sync_summary.json` to formally signal the completion of the Python execution chain to the GitHub Action orchestrator.

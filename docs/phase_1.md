# Phase 1: Feed Discovery & Content Extraction

Phase 1 is responsible for scraping configured RSS feeds, checking against persistent history ledgers to prevent duplication, and downloading raw HTML content for downstream LLM processing.

## Architectural Overview

```mermaid
graph TD
    A[get_rss.py] -->|1. Reads Config| B[data/{scope}/sources.json]
    A -->|2. Reads Ledgers| C[history/{scope}/sources/*_processed.json]
    A -->|3. Fetches XML| D[External RSS Feeds]
    A -->|4. Writes Discovered| E[tmp/{scope}/discovered_urls.json]
    
    F[clean_html.py] -->|1. Reads Discovered| E
    F -->|2. Downloads HTML| G[External Article Pages]
    F -->|3. Applies Site Cleaners| H[cleaners/{scope}/extract_*.py]
    F -->|4. Reads Backlog| I[history/{scope}/archive.json]
    F -->|5. Writes Candidates| J[tmp/{scope}/cleaned_candidates.json]
```

## Technical Specifications

### 1.1 RSS Discovery (`get_rss.py`)
- Iterates through `sources.json` based on the active `--scope`.
- Applies a hardcoded `BLACKLIST` (e.g., "lottery", "satta") to filter out spam at the root level.
- **Deduplication Ledger:** Cross-references incoming URLs against the persistent `history/{scope}/sources/*_processed.json` files located in the `content` repository. URLs already in the ledger are immediately dropped.

### 1.2 Content Extraction (`clean_html.py`)
- Consumes `discovered_urls.json`.
- Dynamically loads extraction scripts from the `cleaners/{scope}/` directory based on the `cleaner_filename` property in `sources.json`.
- Uses BeautifulSoup to strip ads, navigation, and boilerplate, returning pure semantic article text.
- **Backlog Injection:** Loads articles published in the last 48 hours from `history/{scope}/archive.json` and appends them to the candidate pool to ensure the LLM has historical context for ongoing stories.

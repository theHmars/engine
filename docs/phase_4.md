# Phase 4: Article Production & Validation

Phase 4 is the core generative engine. It drafts the articles, strictly enforces factual accuracy via an LLM Critic loop, and generates all required SEO and tagging metadata.

## Architectural Overview

```mermaid
graph TD
    A[produce.py] -->|1. Reads Queue| B[tmp/{scope}/triaged_candidates.json]
    A -->|2. Writer Agent| C[Drafts Article]
    C -->|3. Corrector Agent| D{Passes Critic?}
    D -- No --> C
    D -- Yes --> E[Metadata Agent]
    E -->|4. Tagger Agent| F[Tag Whitelist Enforcement]
    F -->|5. Ledger Logging| G[HistoryManager Log]
    G -->|6. Writes Output| H[tmp/{scope}/produced_articles.json]
```

## Technical Specifications

### 4.1 Generative Loop
- **Writer Agent:** Synthesizes the raw HTML content (and any `secondary_sources` merged by Phase 2) into a cohesive news article.
- **Corrector Agent:** Evaluates the draft against the source material. If it detects hallucinations, style violations, or factual inaccuracies, it rejects the draft with specific feedback. The Writer is given up to 3 attempts to pass this validation.
- **Timeout Fallback:** If the global pipeline runtime exceeds 22 minutes, this switches to a "Fast-Fail" 1-shot mode to prevent GitHub Action timeouts.

### 4.2 Metadata & Tagging
- Generates SEO title, description, and region.
- Validates the primary tag against a hardcoded Python whitelist (e.g., `Politics`, `Sports`). If the agent hallucinates a tag, the `Tagger Agent` attempts to fix it. If it fails, it defaults to `Uncategorized`.
- Extracts embedded image URLs from the raw HTML text if no `featured_image` was provided by the RSS feed.

### 4.3 Transaction Logging
- Uses `HistoryManager` to immediately log successful articles as `SUCCESS` in `history/{scope}/sources/*_processed.json`.
- Articles that fail the 3-strike critic loop are logged as `RETRY_FAILED`.

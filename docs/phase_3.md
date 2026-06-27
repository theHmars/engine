# Phase 3: High-Fidelity Deduplication

Phase 3 is the final safety check before spending heavy LLM tokens on article production. It ensures the curated stories do not semantically overlap with articles published in recent cron runs.

## Architectural Overview

```mermaid
graph TD
    A[deduplicate.py] -->|1. Reads Curated| B[tmp/{scope}/chosen_articles.json]
    A -->|2. Reads Recent Pubs| C[history/{scope}/covered.json]
    A -->|3. Reads Shared Pubs| D[history/{scope}/shared.json]
    A -->|4. LLM Semantic Check| E[Compares Topics]
    A -->|5. Writes Final Queue| F[tmp/{scope}/triaged_candidates.json]
```

## Technical Specifications

### 3.1 Historical Overlap Check
- While Phase 1 prevents processing the *exact same URL*, Phase 3 prevents processing *different URLs about the exact same event*.
- The script loads `covered.json` (which contains articles successfully published in the last 48 hours) from the persistent `content` repository.
- An LLM agent compares the newly curated candidates against the `covered.json` metadata. If a candidate is deemed semantically identical to a recently published story, it is forcefully dropped from the queue.

### 3.2 Facebook Syndication Check
- It also cross-references against `shared.json` to ensure we don't accidentally regurgitate a topic that is currently queued for social media syndication.
- The remaining, completely unique stories are written to `tmp/{scope}/triaged_candidates.json` for Phase 4 production.

# Phase 2: Curation & Target Triage

Phase 2 acts as the editorial desk. It uses specialized LLM agents to filter out irrelevant PR fluff and select the absolute best news stories for the given scope, merging duplicate events into single comprehensive payloads.

## Architectural Overview

```mermaid
graph TD
    A[triage.py] -->|1. Reads Pool| B[tmp/{scope}/cleaned_candidates.json]
    A -->|2. Relevance Filter Agent| C[Strips PR/Fluff]
    A -->|3. Reads Semantic Ledgers| D[history/{scope}/topics.json & covered.json]
    A -->|4. Senior Curator Agent| E[Selects & Merges Top 10]
    A -->|5. Writes Output| F[tmp/{scope}/chosen_articles.json]
```

## Technical Specifications

### 2.1 Relevance Filtering
- Prompts the `relevance_filter` agent with a numbered list of candidate titles.
- The LLM returns a list of integer indices representing articles that are PR, opinion, or non-news.
- **Validation Loop:** A Python loop validates that the returned indices exist within the array bounds. If the LLM hallucinates indices, it triggers a 3-strike retry loop.

### 2.2 Senior Curation
- The surviving articles are passed to the `senior_curator` agent.
- The prompt is injected with historical context (`topics.json` and `covered.json`) from the persistent `content` repo to prevent covering stories that were already published earlier in the day.
- **Source Merging:** If multiple news outlets cover the exact same event, the LLM groups their indices together. The Python script parses these groupings, elevating the first to the primary article and appending the rest into a `secondary_sources` array for the Writer agent to synthesize.
- Limits output to a maximum of 10 curated story groups.

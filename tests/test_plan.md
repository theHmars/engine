# 📋 offline News Curation Pipeline - offline Test Plan

This document outlines the offline and local integration test cases required to ensure reliability, correctness, and fault tolerance of the news curation automation engine. 

Each test case contains a description, edge-case variations, and a justification explaining why it is critical.

---

## Test Categories

1. [Phase 1: Sourcing & Pre-Cleaning](#-phase-1-sourcing--pre-cleaning)
2. [Phase 2: Curation Triage](#-phase-2-curation-triage)
3. [Phase 3: Deduplication & Clustering](#-phase-3-deduplication--clustering)
4. [Phase 4: Content Rewrite & Critic Validation](#-phase-4-content-rewrite--critic-validation)
5. [Phase 5: Sync, History & Workspace Cleanup](#-phase-5-sync-history--workspace-cleanup)
6. [Phase 6: Publishing & Coordinated Releases](#-phase-6-publishing--coordinated-releases)

---

## 📥 Phase 1: Sourcing & Pre-Cleaning

### 1. Standard RSS Ingestion
* **Description**: Ingest a valid, well-formed RSS XML payload containing a mixture of standard tags (`<title>`, `<link>`, `<pubDate>`).
* **Justification**: Validates that core feed parsing libraries correctly read XML feeds and map items to internal extraction candidate dicts without dropping records.

### 2. Malformed RSS XML Resilience
* **Description**: Feed raw truncated XML, missing tags (e.g., missing `<channel>` or `<item>`), or syntax errors (unclosed brackets).
* **Justification**: External news feeds are unstable. A syntax error in one remote feed must be caught and logged gracefully rather than crashing the execution runner mid-cycle.

### 3. Empty Feed Graceful Exit
* **Description**: Parse an RSS feed containing 0 news items.
* **Justification**: Normal state for quiet news days or feeds with strict 24-hour expiration windows. The pipeline should log a notice and exit Phase 1 gracefully without raising index errors.

### 4. Cleaner Script Dynamic Registry Resolution
* **Description**: Map a domain name from `sources.json` to its custom cleaner file under `scripts/cleaners/extract_{source}.py`. Test fallback to a generic cleaner if the specific cleaner is missing.
* **Justification**: Verifies that the mapping registry is robust, preventing crashes if a new feed is added without its custom cleaner script being checked in.

### 5. Website Layout Mismatch Detection
* **Description**: Feed a cleaner script HTML content where the target selectors (e.g. `.article-body`) return empty (simulating a layout redesign of the source news site).
* **Justification**: Cleaners must report when they fail to extract text rather than returning empty files, allowing developers to be alerted of source layout updates.

### 6. Paywall & Ad-Widget Stripping Verification
* **Description**: Ingest HTML containing main text wrapped around ad banners, subscription overlay widgets, cookie notices, and newsletter subscribe sections.
* **Justification**: Keeps LLM context clean, saves API token costs, and ensures generated articles are based only on the core news story.

### 7. HTML Entity Decoding Accuracy
* **Description**: Ingest article headlines and bodies containing various HTML entities (e.g., `&amp;`, `&quot;`, `&#8217;`, `&nbsp;`).
* **Justification**: Prevents raw character entities from being written into markdown frontmatter/bodies, avoiding rendering artifacts on the frontend.

### 8. Lazy-Loaded Feature Image Extraction
* **Description**: Extract article images where the `<img>` tag lacks a standard `src` attribute but contains lazy-loaded pointers like `data-src` or `data-lazy-src`.
* **Justification**: Core website layout depends on feature images. Ensuring lazy-loaded fallbacks are captured prevents articles from defaulting to generic fallbacks.

---

## 🔍 Phase 2: Curation Triage

### 9. Regional/Scope Filter Precision (Positive Match)
* **Description**: Feed Guwahati-based regional news into the `Local` scope worker configuration. Verify that the relevance agent accepts the candidate.
* **Justification**: Ensures geographic classification accuracy for targeted local news scopes (Assam, Meghalaya, Mizoram, etc.).

### 10. Regional/Scope Filter Precision (Negative Match)
* **Description**: Feed a Delhi political updates article into the `Local` scope worker configuration. Verify that the relevance agent rejects the candidate.
* **Justification**: Prevents global or generic national news from polluting local scope news blocks.

### 11. Commercial/Advisory Pre-Filtering
* **Description**: Feed advertorials, corporate press releases, or utility schedules (e.g., "Power shutdown times in Shillong").
* **Justification**: Maintains the news portal's focus on public interest news and editorial reportage, filtering out low-value utility updates.

### 12. Non-English Content Filtering
* **Description**: Feed a candidate article written in non-English characters or severely corrupted text.
* **Justification**: Prevents the rewrite model from wasting API tokens attempting to translate or process garbage text.

### 13. Skeleton Content Thresholding
* **Description**: Filter out articles where the extracted body contains fewer than 50 words.
* **Justification**: Prevents thin-content publications that provide no actual informational value.

### 14. LLM API Rate Limit & Transient Failure Handling
* **Description**: Mock the LLM API to throw a 429 Rate Limit error or a 503 Service Unavailable error. Verify that the pipeline catches the exception, retries, and falls back to safe defaults if retries fail.
* **Justification**: Assures the pipeline remains operational even during third-party LLM service interruptions.

### 15. LLM JSON Output Validation
* **Description**: Mock the LLM to return malformed JSON (missing commas, trailing braces) during triage evaluations. Verify the parser catches it without crashing.
* **Justification**: LLMs cannot guarantee structured JSON output 100% of the time. The code must catch decode errors and handle them.

---

## 🔀 Phase 3: Deduplication & Clustering

### 16. Exact URL Duplicate Drop
* **Description**: Feed two candidates referencing the exact same URL.
* **Justification**: Basic safety check preventing redundant downloads.

### 17. Title Semantic Duplicate Merging
* **Description**: Feed "Heavy rains cause traffic gridlocks in Shillong" and "Monsoon downpour floods Shillong streets, chokes roads". Verify that semantic checking merges them into one event group.
* **Justification**: Prevents presenting multiple near-identical articles for the same news event.

### 18. Historical DB Deduplication (Same-Day)
* **Description**: Check a candidate against the list of URLs processed in the current run cycle.
* **Justification**: Prevents double-processing if a URL is registered across multiple feeds.

### 19. Historical DB Deduplication (Cross-Day)
* **Description**: Check a candidate against processed URLs in history logs spanning the past 48 hours.
* **Justification**: Prevents re-publishing a story that was already processed in the previous execution cycle.

### 20. Atomic History Write Verification
* **Description**: Verify that if a run crashes mid-phase, the history ledger files are NOT updated with half-processed items.
* **Justification**: Ensures that uncompleted articles are picked up again in the next scheduled execution run rather than being lost.

---

## ✍️ Phase 4: Content Rewrite & Critic Validation

### 21. Zod-Compliant Frontmatter Output
* **Description**: Validate that the generated Markdown frontmatter strictly matches the Zod schema defined in `content.config.ts`.
* **Justification**: Any deviation in frontmatter keys or types immediately breaks compile-time builds in Astro 5.

### 22. Critic Loop Rejection & Self-Correction
* **Description**: Mock the critic agent to reject the writer's initial draft (e.g. due to editorial opinion bias). Verify that the writer successfully edits the draft and submits a compliant version.
* **Justification**: Validates the autonomous correction loop that safeguards quality.

### 23. Strict Word-Count Enforcement
* **Description**: Verify that the final generated article body stays strictly within the 150-400 word threshold.
* **Justification**: Enforces layout consistency on grid columns.

### 24. No-Header Body Validation
* **Description**: Verify that the generated body text contains no markdown headers (`#`, `##`, etc.).
* **Justification**: The design system handles post headers dynamically. Inline markdown headers disrupt font styling.

### 25. National/Global N/A Region Mapping
* **Description**: Verify that articles categorized under Global or National scopes write `region: N/A` in the frontmatter.
* **Justification**: Prevents Astro build routing errors for scopes that don't have sub-regions.

---

## 🧹 Phase 5: Sync, History & Workspace Cleanup

### 26. Garbage Collection of Pre-Processed Data
* **Description**: Verify that at the end of `cleanup.py`, the `data/pre-processed` raw HTML and XML directories are cleared.
* **Justification**: Minimizes disk space usage and keeps git workspaces clean of transient data.

### 27. Concurrent File-Lock Handling
* **Description**: Simulate multiple worker pipelines attempting to write to the shared history ledger simultaneously.
* **Justification**: Prevents lock-contentions and data loss in local ledger updates.

### 28. Slug Collision Resolution Suffixing
* **Description**: Feed two articles that generate identical slugs (e.g., same title). Verify that the second article receives a numerical suffix (`-1`, `-2`).
* **Justification**: Prevents filesystem collisions when writing markdown files and compile errors during static site generation.

---

## Phase 6: Publishing & Coordinated Releases

### 29. Facebook Post Scheduling Intervals
* **Description**: Verify that the scheduling logic offsets consecutive posts by exactly 30 minutes in the Future.
* **Justification**: Prevents flooding the social page feed and triggering Facebook spam block filters.

### 30. Render Deploy Hook Polling States
* **Description**: Mock Render deploy status checks (`build_failed`, `build_in_progress`, `live`). Verify the publishing script sleeps during builds and aborts on failures.
* **Justification**: Publishing must wait for static assets to be live on Render to prevent broken links on shared posts.

### 31. Dirty Tree Prevention in upgrade.py
* **Description**: Run `upgrade.py` with uncommitted changes in one of the repositories. Verify it raises a warning but allows proceeding or aborting.
* **Justification**: Prevents accidental push of out-of-sync local configurations.

### 32. CLI Credentials Profile Lock
* **Description**: Verify that `upgrade.py` blocks execution if GitHub CLI is authenticated as a user other than `thingpuisenhang` or `thingpuisentlum`.
* **Justification**: Ensures correct git write permissions.

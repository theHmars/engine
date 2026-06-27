# theHmars News Pipeline Engine

The stateless execution engine powering the automated news pipeline for **theHmars**. Runs in a unified GitHub Actions workflow across three geographic scopes (local, national, global), complete with Astro Pre-Flight Validation and a 3-Strike Render Quarantine self-healing protocol.

- **Repository:** `https://github.com/theHmars/engine`
- **Architecture Overview:** [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)

---

## Architecture Quick-Glance

The `engine` acts as the computational brain. Published articles, histories, and quarantine logs are safely stored in the `content` repository.

| Repo | Role |
|---|---|
| `engine` | The runner. Contains `main.py`, LLM agents, and `pipeline.yml`. Completely ephemeral. |
| `content` | The persistent database. Stores published `markdown/`, JSON histories, and `quarantine/` logs. |
| `frontend` | Astro web portal (deployed to Render) |

---

## Pipeline Execution Flow

Orchestrated by `.github/workflows/pipeline.yml`, the pipeline runs 3 times a day (`23 0,8,16 * * *` UTC) with strict 30-minute processing limits per scope:

1. **`run LOC pipeline`** (Local Scope)
2. **`run NAT pipeline`** (National Scope)
3. **`run GLO pipeline`** (Global Scope)
4. **`Pre-Flight Markdown Validation`** (`validate_markdown.py` runs Astro checks on new files; corrupted files sent to `quarantine/local/`).
5. **`Sync & Handoff`** (Files synced to `content` repo, `update_indices.py` generates `articles.json`).
6. **`Commit & Push`** (Pushes to `content` remote).
7. **`Publisher & Render Trigger`** (`facebook_publisher.py` handles Render deployment. If Render fails 3x, it physically moves files to `quarantine/render/`, reverts index, and pushes self-healing Git revert).

---

## Phase Breakdown (Inside `main.py`)

| Phase | Script(s) | Purpose |
|---|---|---|
| **1** | `get_rss.py`, `clean_html.py` | Fetch RSS, deduct duplicates via history ledger, extract raw HTML |
| **2** | `triage.py` | LLM relevance filter + senior editor curation & source merging |
| **3** | `deduplicate.py` | Intra-batch clustering + historical dedup against `covered.json` |
| **4** | `produce.py` | 3-strike LLM rewrite → critic validation loop → metadata generation |
| **5** | `cleanup.py` | Format YAML frontmatter, write to `push/`, update backlog poison pills |

---

## Required Secrets (GitHub Actions)

| Secret | Purpose |
|---|---|
| `PAT_TOKEN` | Checkout `content` and `frontend` repos |
| `LLM_API_KEY` | NVIDIA NIM LLM authentication |
| `FB_PAGE_ID` | Facebook Graph API page identifier |
| `FB_PAGE_ACCESS_TOKEN` | Facebook Graph API auth token |
| `RENDER_API_KEY` | Render REST API authentication |
| `RENDER_SERVICE_ID` | Render service to poll for deploy status |
| `RENDER_DEPLOY_HOOK` | Webhook URL to trigger Render build |

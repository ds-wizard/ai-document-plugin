# AI Template Assistant

Generates a Data Management Plan (DMP) document from a DSW knowledge-model questionnaire export and a DMP template
definition, using LLM calls to match questions to sections and produce the final markdown.

## Quick start

```bash
uv sync --dev
```

Create `config.yaml` with your LLM credentials (see `config.template.yaml`). All input/output file paths, including the
prompts file, can be configured there.

Run the full pipeline:

```bash
uv run ai-document-pipeline \
  --questionnaire-uuid <QUESTIONNAIRE_UUID> \
  --token <TOKEN> \
  --template-uuid <TEMPLATE_UUID>
```

The CLI reads technical configuration such as DSW API base URL, database connection, model configuration, prompt paths,
and output file paths from `config.yaml`. The runtime inputs `questionnaire_uuid`, `token`, and `template_uuid` are
passed explicitly through CLI arguments.

This produces:

| File                       | Description                                      |
|----------------------------|--------------------------------------------------|
| `dmp_output_pre_polish.md` | Generated DMP with debug tables before polishing |
| `dmp_output.md`            | Final polished DMP with token-usage summary      |

Step 1 produces new record in the `assignments` table in the DB, when questions are assigned for the first time.

## Pipeline steps

`src/ai_document_plugin_service/run_pipeline.py` orchestrates three steps, each backed by a dedicated module:

### Step 1 — Question-to-section assignment (`templates/assignment`)

Assigns questions from the KM to leaf sections (sections with no children) from the DMP template

### Step 2 — DMP generation (`templates/generation`)

This step now uses user's replies. It matches them with assignments from the previous steps and generates sections of
the DMP. All sections are generated independently of each other.

### Step 3 — DMP polishing (`templates/polishing`)

A single LLM call that reorganizes content across sections — moving information to the most relevant chapter,
consolidating duplicates, and improving flow — without adding new content.

## Configuration

### `config.yaml`

LLM connection settings (API key, base URL, model name), DSW API base URL, database connection, and all pipeline file
paths. The API key supports environment variable expansion (e.g. `$OPENAI_API_KEY`).

### `prompts.yaml`

Prompt templates and LLM parameters for each step. Its location can be overridden via `files.prompts_path` in
`config.yaml`.

## Make commands

The project `Makefile` provides a few shortcuts for common development tasks:

- `make install` installs project dependencies from `pyproject.toml` using `uv sync`
- `make lint` runs Ruff checks over the source tree
- `make typecheck` runs static type checking with `ty`
- `make format` formats the codebase with Ruff
- `make requirements` regenerates `requirements.txt` from `pyproject.toml`
- `make dev` starts the FastAPI development server with auto-reload on port `8010`
- `make build` builds the Python package
- `make db` starts the local PostgreSQL container defined in `docker-compose.yml`
- `make db-init` starts the local PostgreSQL container, waits for it to become healthy, and applies all Alembic migrations
- `make db-migrate` applies all Alembic migrations to the configured database
- `make db-current` shows the current Alembic revision stored in the database
- `make db-history` shows available Alembic migration history

Run these commands from the [service](/Users/hana/DSW/AI-playground/ai-document-plugin/service:1) directory.

For a fresh local setup, the usual flow is:

```bash
make install
make db-init
```

`docker compose` creates the PostgreSQL database itself from the `POSTGRES_DB`, `POSTGRES_USER`, and
`POSTGRES_PASSWORD` values in [docker-compose.yml](/Users/hana/DSW/AI-playground/ai-document-plugin/service/docker-compose.yml:1). Alembic then creates or updates the schema inside that database; it does not create the PostgreSQL server or database on its own.

The application runtime does not create or alter database tables on its own. Run `make db-init` or
`make db-migrate` before starting the service against a fresh or changed database.

If the PostgreSQL container already exists with an older Docker volume, the database may be missing even though the server is running. In that case `make db-init` also checks that `ai_document_plugin` exists and creates it before running Alembic migrations.


## Tests

```bash
uv run pytest tests/ -v
```

Tests cover pure functions, reply matching, tree chunking, compatibility utilities, and end-to-end generation using a
stub LLM (no API calls needed).

# AI Template Assistant

Generates a Data Management Plan (DMP) document from a DSW knowledge-model questionnaire export and a DMP template
definition, using LLM calls to match questions to sections and produce the final markdown.

## Quick start

```bash
uv sync --dev
```

Create `config.yaml` with your LLM credentials (see `config.template.yaml`). All input/output file paths, including the
prompts file, can be configured there. The loader still accepts legacy `config.yaml` as a fallback.

Run the full pipeline:

```bash
uv run python src/ai_document_plugin_service/run_pipeline.py
```

This produces:

| File                                  | Description                                      |
|---------------------------------------|--------------------------------------------------|
| `question_section_assignments_*.json` | Question-to-section mapping (step 1 output)      |
| `dmp_output_pre_polish.md`            | Generated DMP with debug tables before polishing |
| `dmp_output.md`                       | Final polished DMP with token-usage summary      |

## Pipeline steps

`templates/run_pipeline.py` orchestrates three steps, each backed by a dedicated module:

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

LLM connection settings (API key, base URL, model name) plus all pipeline file paths. The API key supports environment
variable expansion (e.g. `$OPENAI_API_KEY`).

### `prompts.yaml`

Prompt templates and LLM parameters for each step. Its location can be overridden via `files.prompts_path` in
`config.yaml`.

## Tests

```bash
uv run pytest tests/ -v
```

Tests cover pure functions, reply matching, tree chunking, compatibility utilities, and end-to-end generation using a
stub LLM (no API calls needed).

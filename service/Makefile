.PHONY: install
install:
	uv sync

.PHONY: lint
lint:
	uv run ruff check

.PHONY: typecheck
typecheck:
	uv run ty check

.PHONY: test
test:
	uv run pytest

.PHONY: format
format:
	uv run ruff format

.PHONY: requirements
requirements:
	uv pip compile pyproject.toml > requirements.txt

.PHONY: dev
dev:
	uv run uvicorn ai_document_plugin_service:create_app --factory --reload --proxy-headers --host "0.0.0.0" --port 8010

.PHONY: build
build:
	uv build

.PHONY: db
db:
	docker compose up -d postgres

.PHONY: db-init
db-init:
	docker compose up -d postgres
	@echo "Waiting for postgres to become healthy..."
	@until [ "$$(docker inspect --format='{{.State.Health.Status}}' ai-document-plugin-postgres 2>/dev/null)" = "healthy" ]; do sleep 2; done
	@echo "Ensuring database ai_document_plugin exists..."
	@docker exec ai-document-plugin-postgres psql -U ai_document_plugin -d template1 -tAc "SELECT 1 FROM pg_database WHERE datname = 'ai_document_plugin'" | grep -q 1 || \
		docker exec ai-document-plugin-postgres psql -U ai_document_plugin -d template1 -c "CREATE DATABASE ai_document_plugin"
	uv run --active alembic upgrade head

.PHONY: db-migrate
db-migrate:
	uv run --active alembic upgrade head

.PHONY: db-current
db-current:
	uv run --active alembic current

.PHONY: db-history
db-history:
	uv run --active alembic history

# Both targets create versions/YYYYMMDD_NN_<message>.py with revision ID YYYYMMDD_NN (next free NN for today).
MIGRATIONS_VERSIONS_DIR := src/ai_document_plugin_service/migrations/versions
NEXT_REVISION_ID = $(shell day=$$(date +%Y%m%d); \
	count=$$(find $(MIGRATIONS_VERSIONS_DIR) -maxdepth 1 -name "$${day}_*.py" | wc -l); \
	printf '%s_%02d' "$$day" $$((count + 1)))

# Usage: make db-revision m="Add foo to bar"  (empty migration)
.PHONY: db-revision
db-revision:
	@test -n "$(m)" || { echo 'Usage: make db-revision m="Describe the change"'; exit 1; }
	uv run --active alembic revision --rev-id "$(NEXT_REVISION_ID)" -m "$(m)"

# Usage: make db-autogenerate m="Add foo to bar"  (diffs schema.py against the DB; DB must be at head)
.PHONY: db-autogenerate
db-autogenerate:
	@test -n "$(m)" || { echo 'Usage: make db-autogenerate m="Describe the change"'; exit 1; }
	uv run --active alembic revision --autogenerate --rev-id "$(NEXT_REVISION_ID)" -m "$(m)"

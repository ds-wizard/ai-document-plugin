.PHONY: install
install:
	uv sync

.PHONY: lint
lint:
	uv run ruff check

.PHONY: typecheck
typecheck:
	uv run ty check

.PHONY: format
format:
	uv run ruff format

.PHONY: requirements
requirements:
	uv pip compile pyproject.toml > requirements.txt

.PHONY: dev
dev:
	uv run uvicorn ai_document_plugin_service:create_app --reload --proxy-headers --host "0.0.0.0" --port 8010

.PHONY: build
build:
	uv build

.PHONY: db
db:
	docker compose up -d postgres

.PHONY: db-migrate
db-migrate:
	uv run alembic upgrade head

.PHONY: db-current
db-current:
	uv run alembic current

.PHONY: db-history
db-history:
	uv run alembic history

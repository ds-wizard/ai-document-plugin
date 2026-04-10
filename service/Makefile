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
	uv run uvicorn plugin_service:create_app --reload --proxy-headers --host "0.0.0.0" --port 8000

.PHONY: build
build:
	uv build

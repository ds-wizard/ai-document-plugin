FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY src/ ./src/

RUN uv sync --frozen --no-dev && uv pip install uvicorn

COPY prompts.yaml alembic.ini ./

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8010

CMD ["uvicorn", "ai_document_plugin_service:create_app", "--factory", "--proxy-headers", "--host", "0.0.0.0", "--port", "8010"]

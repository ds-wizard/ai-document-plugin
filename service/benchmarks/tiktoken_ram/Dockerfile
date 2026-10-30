# Build context is the service/ directory; run_benchmark.sh does this for you.
FROM python:3.13-slim

WORKDIR /app

# Install the versions from uv.lock, because requirements.txt has conflicting pins.
# uvicorn is a dev dependency of the service. matplotlib is only imported by plot_results.py.
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv \
    && uv export --frozen --no-dev --no-emit-project --no-hashes -o locked-requirements.txt \
    && pip install --no-cache-dir -r locked-requirements.txt uvicorn==0.54.0 matplotlib

COPY src ./src
COPY prompts.yaml cover-page.yaml ./
COPY benchmarks/tiktoken_ram/config.yaml ./benchmark-config.yaml
COPY benchmarks/tiktoken_ram /bench
COPY tests/resources/dsw_root_km.json.json /bench/km.json

ENV PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1 \
    AI_DOCUMENT_PLUGIN_CONFIG_PATH=/app/benchmark-config.yaml \
    HAYSTACK_TELEMETRY_ENABLED=False \
    HOME=/tmp \
    MPLCONFIGDIR=/tmp/matplotlib \
    TIKTOKEN_CACHE_DIR=/opt/tiktoken-cache

# Bake the encoding in, so loading it never depends on the network or on cache state.
RUN python -c "import tiktoken; tiktoken.get_encoding('cl100k_base')" \
    && chmod -R a+rX /opt/tiktoken-cache

CMD ["sh", "/bench/entrypoint.sh"]

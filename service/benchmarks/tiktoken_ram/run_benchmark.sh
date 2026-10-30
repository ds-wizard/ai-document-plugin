#!/usr/bin/env bash
# Measures the service's RAM with and without tiktoken, then plots it. Needs only Docker.
#
#   ./run_benchmark.sh [--runs 5] [--llm-delay 0.3] [--idle-before 20] [--idle-after 20] [--out DIR]
#
# Everything runs on a private Docker network with no internet access and no published ports, and is
# removed at the end. Each run gets a fresh service container and a fresh database, because stored
# assignments would otherwise skip the chunker, and tiktoken with it.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

RUNS=5
LLM_DELAY=0.3
IDLE_BEFORE=20
IDLE_AFTER=20
OUT_DIR="$SCRIPT_DIR/results/$(date +%Y%m%d-%H%M%S)"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --runs) RUNS="$2"; shift 2 ;;
        --llm-delay) LLM_DELAY="$2"; shift 2 ;;
        --idle-before) IDLE_BEFORE="$2"; shift 2 ;;
        --idle-after) IDLE_AFTER="$2"; shift 2 ;;
        --out) OUT_DIR="$2"; shift 2 ;;
        *) echo "Unknown option: $1" >&2; exit 2 ;;
    esac
done

IMAGE=tiktoken-ram-benchmark
NETWORK=tiktoken-bench-net
POSTGRES=bench-postgres
UPSTREAM=fake-upstream
SERVICE=bench-service
DB_USER=ai_document_plugin
DB_NAME=ai_document_plugin

mkdir -p "$OUT_DIR/raw" "$OUT_DIR/logs"
OUT_DIR="$(cd "$OUT_DIR" && pwd)"
USER_FLAG="$(id -u):$(id -g)"

cleanup() {
    docker rm -f "$SERVICE" "$UPSTREAM" "$POSTGRES" >/dev/null 2>&1 || true
    docker network rm "$NETWORK" >/dev/null 2>&1 || true
}
trap cleanup EXIT
cleanup

echo "==> Building image"
docker build -t "$IMAGE" -f "$SCRIPT_DIR/Dockerfile" "$SERVICE_DIR"

echo "==> Starting Postgres and the fake DSW/LLM server"
docker network create --internal "$NETWORK" >/dev/null
docker run -d --name "$POSTGRES" --network "$NETWORK" \
    -e POSTGRES_USER="$DB_USER" -e POSTGRES_PASSWORD="$DB_USER" -e POSTGRES_DB=postgres \
    postgres:17-alpine >/dev/null
docker run -d --name "$UPSTREAM" --network "$NETWORK" "$IMAGE" \
    python /bench/fake_upstream.py --llm-delay "$LLM_DELAY" >/dev/null

# The TCP check only passes once the real server is up, not during the image's init phase.
until docker exec "$POSTGRES" pg_isready -q -h 127.0.0.1 -U "$DB_USER" -d postgres; do sleep 1; done

reset_database() {
    docker exec "$POSTGRES" psql -q -h 127.0.0.1 -U "$DB_USER" -d postgres -v ON_ERROR_STOP=1 \
        -c "DROP DATABASE IF EXISTS $DB_NAME WITH (FORCE)" \
        -c "CREATE DATABASE $DB_NAME" >/dev/null
}

run_once() {
    local mode="$1" round="$2"
    local name="${mode}_${round}"

    reset_database
    docker run -d --name "$SERVICE" --network "$NETWORK" --user "$USER_FLAG" \
        -v "$OUT_DIR:/results" \
        -e TOKEN_COUNTER="$mode" \
        -e BENCH_SAMPLES_FILE="/results/raw/$name.csv" \
        "$IMAGE" >/dev/null

    local failed=0
    docker run --rm --network "$NETWORK" --user "$USER_FLAG" -v "$OUT_DIR:/results" "$IMAGE" \
        python /bench/drive_run.py --out "/results/raw/$name.json" --mode "$mode" --round "$round" \
        --idle-before "$IDLE_BEFORE" --idle-after "$IDLE_AFTER" || failed=1

    # Check the run really tested what it claims, before the container goes away.
    local loaded=""
    if [[ $failed -eq 0 ]]; then
        loaded="$(docker exec "$SERVICE" sh -c 'grep -c _tiktoken /proc/1/maps || true')"
    fi

    docker logs "$SERVICE" >"$OUT_DIR/logs/$name.log" 2>&1
    docker rm -f "$SERVICE" >/dev/null

    if [[ $failed -ne 0 ]]; then
        echo "Run $name failed. Last lines of the service log ($OUT_DIR/logs/$name.log):" >&2
        tail -n 30 "$OUT_DIR/logs/$name.log" >&2
        exit 1
    fi
    if [[ -z "$loaded" ]]; then
        echo "Could not read /proc/1/maps for $name, so the mode could not be verified." >&2
        exit 1
    fi
    if [[ "$mode" == tiktoken && "$loaded" -eq 0 ]]; then
        echo "Run $name is invalid: tiktoken mode did not load tiktoken." >&2
        exit 1
    fi
    if [[ "$mode" == approx && "$loaded" -ne 0 ]]; then
        echo "Run $name is invalid: approx mode still loaded tiktoken, so something else imports it." >&2
        exit 1
    fi
}

# Alternate which mode goes first, so any drift on the machine affects both equally.
for ((round = 1; round <= RUNS; round++)); do
    if ((round % 2)); then modes=(tiktoken approx); else modes=(approx tiktoken); fi
    for mode in "${modes[@]}"; do
        echo "==> Round $round/$RUNS: $mode"
        run_once "$mode" "$round"
    done
done

echo "==> Plotting"
docker run --rm --network none --user "$USER_FLAG" -v "$OUT_DIR:/results" "$IMAGE" \
    python /bench/plot_results.py /results

echo "==> Done. Results are in $OUT_DIR"

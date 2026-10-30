#!/bin/sh
# Starts a background memory sampler, then replaces this shell with uvicorn so the service is PID 1.
# The sampler reads the kernel's counters directly, and only adds a few MB of shell to the cgroup numbers.
set -eu

: "${BENCH_SAMPLES_FILE:?BENCH_SAMPLES_FILE must be set}"
interval="${BENCH_SAMPLE_INTERVAL:-0.25}"

echo 'epoch_ms,vmrss_kb,vmhwm_kb,rssanon_kb,cgroup_anon_kb' > "$BENCH_SAMPLES_FILE"

(
    while :; do
        proc=$(awk '/^VmRSS:/{r=$2} /^VmHWM:/{h=$2} /^RssAnon:/{a=$2} END{print r "," h "," a}' /proc/1/status)
        anon=$(awk '$1=="anon"{print int($2/1024)}' /sys/fs/cgroup/memory.stat 2>/dev/null || true)
        echo "$(date +%s%3N),$proc,$anon" >> "$BENCH_SAMPLES_FILE"
        sleep "$interval"
    done
) &

exec uvicorn ai_document_plugin_service:create_app --factory --host 0.0.0.0 --port 8010

#!/usr/bin/env bash
# Run from any directory. FINAL_RUN_WAVES=2 is for the local two-wave rehearsal.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

if [[ ! -f ../data/release-sunday/facts.json ]]; then
    echo "Sunday release is missing: expected ../data/release-sunday/facts.json" >&2
    exit 1
fi

if ! uv run arena me >/dev/null; then
    echo "arena me failed; check ARENA_URL, ARENA_API_KEY, and the connection" >&2
    exit 1
fi

log_file="final-$(date +%Y%m%d-%H%M%S).log"
waves=()
if [[ -n "${FINAL_RUN_WAVES:-}" ]]; then
    waves=(--waves "$FINAL_RUN_WAVES")
fi

trap 'exit 130' INT
trap 'exit 143' TERM

while true; do
    echo "$(date -Is) starting final runner; log: $log_file" | tee -a "$log_file"
    set +e
    systemd-inhibit --what=sleep:idle uv run arena run --set final "${waves[@]}" \
        --agent buyer --data ../data --parallel 10 -v 2>&1 | tee -a "$log_file"
    status=${PIPESTATUS[0]}
    set -e
    if [[ "$status" -eq 0 ]]; then
        echo "$(date -Is) final runner completed" | tee -a "$log_file"
        exit 0
    fi
    echo "$(date -Is) final runner exited $status; restarting in 5 seconds" | tee -a "$log_file"
    sleep 5
done

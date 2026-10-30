#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
test -d "$ROOT/workplace/probe"
test -f "$ROOT/tools/research_storage.py"
SCRIPT=research_storage.py
case "${1:-}" in
  dedup-plan|dedup-apply|dedup-verify|dedup-detach)
    ACTION="${1#dedup-}"
    shift
    set -- "$ACTION" "$@"
    SCRIPT=history_dedup.py
    test -f "$ROOT/tools/$SCRIPT"
    ;;
esac
timeout --kill-after=10s 1800s docker run --rm --pull never --network none \
  --user "$(id -u):$(id -g)" --memory 1g --cpus 2 --pids-limit 64 \
  --label project=dark-queen-of-krynn-cht -e PYTHONDONTWRITEBYTECODE=1 \
  -v "$ROOT:/project:ro" -v "$ROOT/workplace/probe:/project/workplace/probe" \
  --entrypoint python3 sha256:b050fc7c49003ea6eecbbe0fc93b465b6869daf550c3284d5039e5e87517e831 \
  "/project/tools/$SCRIPT" "$@"

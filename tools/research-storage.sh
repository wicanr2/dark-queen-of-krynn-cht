#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
test -d "$ROOT/workplace/probe"
test -f "$ROOT/tools/research_storage.py"
timeout --kill-after=10s 1800s docker run --rm --pull never --network none \
  --user "$(id -u):$(id -g)" --memory 1g --cpus 2 --pids-limit 64 \
  --label project=dark-queen-of-krynn-cht -e PYTHONDONTWRITEBYTECODE=1 \
  -v "$ROOT:/project:ro" -v "$ROOT/workplace/probe:/project/workplace/probe" \
  --entrypoint python3 sha256:44d0742ca1061bcd453440cdce925afa31c5324e115fca1334da0e364f0e2c48 \
  /project/tools/research_storage.py "$@"

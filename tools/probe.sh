#!/usr/bin/env bash
# 主機只做路徑檢查與 Docker 呼叫；遊戲與分析都在容器內執行。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ORIG="$ROOT/workplace/input/dos/drkqueen"
OUT="$ROOT/workplace/probe"
test -f "$ORIG/DQK.EXE"
test -f "$OUT/probe"
test -d "$OUT"
exec timeout "${DQK_TIMEOUT:-120s}" docker run --rm --init \
  --label project=dark-queen-of-krynn-cht --network none \
  --memory 1g --cpus 2 --pids-limit 128 \
  --log-opt max-size=10m --log-opt max-file=3 \
  --user "$(id -u):$(id -g)" \
  -v "$ORIG:/orig:ro" -v "$OUT:/out" -w /out \
  dosgolem-go-ebiten:1.24-r1 /out/probe "$@"

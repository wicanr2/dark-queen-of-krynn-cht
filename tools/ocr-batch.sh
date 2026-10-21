#!/usr/bin/env bash
# 主機只檢查路徑並呼叫 Docker；全文草稿只寫入被忽略的研究輸出。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CACHE="$ROOT/workplace/walkthrough/paddle-home"
case "${1:-}" in
  walkthrough) INPUT="$ROOT/walkthrough" ;;
  manual) INPUT="$ROOT/workplace/manual-ocr" ;;
  *) echo '用法：bash tools/ocr-batch.sh walkthrough|manual' >&2; exit 2 ;;
esac
test -d "$INPUT"
test -d "$CACHE/.paddlex/official_models/PP-OCRv5_mobile_det"
test -d "$CACHE/.paddlex/official_models/PP-OCRv5_mobile_rec"
OUT="$ROOT/workplace/paddle-$1"
mkdir -p "$OUT"
IMAGE_ID="$(docker image inspect dqk-ocr:ppocr5-r1 --format '{{.Id}}')"
timeout "${DQK_OCR_TIMEOUT:-1800s}" docker run --rm --init \
  --label project=dark-queen-of-krynn-cht --network none \
  --memory 2g --cpus 2 --pids-limit 128 --user "$(id -u):$(id -g)" \
  -v "$INPUT:/input:ro" -v "$CACHE:/cache:ro" -v "$ROOT/tools:/tools:ro" \
  -v "$OUT:/out" -e HOME=/cache -e OMP_NUM_THREADS=1 -e DQK_IMAGE_ID="$IMAGE_ID" \
  "$IMAGE_ID" /bin/sh -c '
    python3 /tools/ocr_batch.py /input /out
    result=$?
    cat /sys/fs/cgroup/memory.events > /out/memory-events.txt
    cat /sys/fs/cgroup/memory.peak > /out/memory-peak.txt
    exit "$result"'

#!/usr/bin/env bash
# 離線校讀資料檢查，沒有遊戲執行或正式 catalog 寫回。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NAME="${1:?需指定全新輸出名稱}"
[[ "$NAME" =~ ^[a-z0-9][a-z0-9.-]*$ && "$NAME" != *..* ]]
TEXT="$ROOT/workplace/translation"
OUT="$ROOT/workplace/probe/pane-render-20261022"
FONT=/home/anr2/cht/golden_box/death_knight_of_krynn/font
IMAGE=sha256:6d849051db2e108262fa689160011dc64045cc402f61985548a525559d3a1cf3
test -d "$TEXT"; test -d "$OUT"; test -f "$FONT/jf-openhuninn-2.1.ttf"
test "$(stat -c %u:%g "$OUT")" = "$(id -u):$(id -g)"
test ! -e "$OUT/$NAME.json"; test ! -e "$OUT/$NAME.zh-TW.tsv"
timeout 90s docker run --rm --init --network none --user "$(id -u):$(id -g)" \
  --memory 1g --cpus 1 --pids-limit 64 --label project=dark-queen-of-krynn-cht \
  -v "$ROOT:/project:ro" -v "$OUT:/out" -v "$FONT:/font:ro" \
  --entrypoint python3 "$IMAGE" /project/tools/journal_review_check.py \
  /project /project/workplace/translation /font/jf-openhuninn-2.1.ttf "/out/$NAME.zh-TW.tsv" "/out/$NAME.json"

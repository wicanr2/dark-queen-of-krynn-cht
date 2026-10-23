#!/usr/bin/env bash
# DRAFT：服務清單輸入。遊戲、畫格及對照沿 ui-list-live.sh，非正式啟動器。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROBE="$ROOT/workplace/probe"
BASE="$PROBE/pane-render-20261022/journal-illustrated-20261023/inputs-r2"
SOURCE="$PROBE/services-20261023"
FONT=/home/anr2/cht/golden_box/death_knight_of_krynn/font
NAME="${1:?全新輸入目錄名稱}"
[[ "$NAME" =~ ^[a-z0-9][a-z0-9-]*$ ]]
test -d "$BASE"; test -d "$SOURCE"; test -d "$ROOT/tools"; test -d "$ROOT/workplace/translation"
test -f "$SOURCE/observe-shop-full-r1/receipt.json"; test -f "$SOURCE/observe-temple-full-r1/receipt.json"
test -f "$FONT/jf-openhuninn-2.1.ttf"
test "$(stat -c %u:%g "$SOURCE")" = "$(id -u):$(id -g)"
test ! -e "$SOURCE/$NAME"
timeout 40s docker run --rm --pull never --network none --user "$(id -u):$(id -g)" --memory 1g --cpus 1 --pids-limit 64 \
  --label project=dark-queen-of-krynn-cht -v "$BASE:/base:ro" -v "$ROOT/tools:/tools:ro" -v "$ROOT/workplace/translation:/text:ro" \
  -v "$SOURCE:/source:ro" -v "$SOURCE:/out:rw" -v "$FONT:/font:ro" --entrypoint bash \
  sha256:44d0742ca1061bcd453440cdce925afa31c5324e115fca1334da0e364f0e2c48 -c \
  'set -e; python3 /tools/ui_service_inputs.py /base /text /source "/out/$1"; python3 /tools/menu_glyphs.py /font/jf-openhuninn-2.1.ttf "/out/$1/font-zh-TW.tsv" "/out/$1/glyphs-16.json" 16' -- "$NAME"

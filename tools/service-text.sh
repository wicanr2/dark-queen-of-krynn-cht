#!/usr/bin/env bash
# DRAFT：服務清單輸入。遊戲、畫格及對照沿 ui-list-live.sh，非正式啟動器。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROBE="$ROOT/workplace/probe"
BASE="$PROBE/pane-render-20261022/journal-illustrated-20261023/inputs-r2"
SOURCE="$PROBE/services-20261023"
FONT=/home/anr2/cht/golden_box/death_knight_of_krynn/font
NAME="${1:?全新輸入目錄名稱}"
KIND="${2:-services}"
PREPARER=ui_service_inputs.py
case "$KIND" in
  services) ;;
  trade)
    BASE="$SOURCE/inputs-r3"
    SOURCE="$PROBE/services-trade-20261023"
    PREPARER=ui_trade_inputs.py
    ;;
  *) printf '%s\n' '章節只能是 services 或 trade' >&2; exit 2 ;;
esac
[[ "$NAME" =~ ^[a-z0-9][a-z0-9-]*$ ]]
test -d "$BASE"; test -d "$SOURCE"; test -d "$ROOT/tools"; test -d "$ROOT/workplace/translation"
if [[ "$KIND" = services ]]; then
  test -f "$SOURCE/observe-shop-full-r1/receipt.json"; test -f "$SOURCE/observe-temple-full-r1/receipt.json"
else
  test -f "$SOURCE/observe-combined-r1/receipt.json"; test -f "$SOURCE/observe-combined-boundaries-r2/receipt.json"
fi
test -f "$FONT/jf-openhuninn-2.1.ttf"
test "$(stat -c %u:%g "$SOURCE")" = "$(id -u):$(id -g)"
test ! -e "$SOURCE/$NAME"
timeout 40s docker run --rm --pull never --network none --user "$(id -u):$(id -g)" --memory 1g --cpus 1 --pids-limit 64 \
  --label project=dark-queen-of-krynn-cht -v "$BASE:/base:ro" -v "$ROOT/tools:/tools:ro" -v "$ROOT/workplace/translation:/text:ro" \
  -v "$SOURCE:/source:ro" -v "$SOURCE:/out:rw" -v "$FONT:/font:ro" --entrypoint bash \
  sha256:44d0742ca1061bcd453440cdce925afa31c5324e115fca1334da0e364f0e2c48 -c \
  'set -e; python3 "/tools/$2" /base /text /source "/out/$1"; python3 /tools/menu_glyphs.py /font/jf-openhuninn-2.1.ttf "/out/$1/font-zh-TW.tsv" "/out/$1/glyphs-16.json" 16' -- "$NAME" "$PREPARER"

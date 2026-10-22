#!/usr/bin/env bash
# DRAFT：離線重繪入口；原始掃描不交給渲染器。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROBE="$ROOT/workplace/probe"
FONT=/home/anr2/cht/golden_box/death_knight_of_krynn/font
FORMAT="${1:?svg 或 png}"
GEOMETRY="${2:?幾何 JSON}"; LAYOUT="${3:?版面 JSON}"; CATALOG="${4:?文字 TSV}"; OUTPUT="${5:?全新輸出檔}"
relative() { [[ "$1" =~ ^[a-zA-Z0-9][a-zA-Z0-9/._-]*$ && "$1" != *..* ]]; }
for ARG in "$GEOMETRY" "$LAYOUT" "$CATALOG" "$OUTPUT"; do relative "$ARG"; done
test -d "$PROBE"
test -f "$PROBE/$GEOMETRY"; test -f "$PROBE/$LAYOUT"; test -f "$PROBE/$CATALOG"
test -f "$FONT/jf-openhuninn-2.1.ttf"
test ! -e "$PROBE/$OUTPUT"
PARENT="$(dirname "$PROBE/$OUTPUT")"
test -d "$PARENT"
test "$(stat -c %u:%g "$PARENT")" = "$(id -u):$(id -g)"
case "$FORMAT" in
  svg) IMAGE=sha256:6d849051db2e108262fa689160011dc64045cc402f61985548a525559d3a1cf3 ;;
  png) IMAGE=sha256:44d0742ca1061bcd453440cdce925afa31c5324e115fca1334da0e364f0e2c48 ;;
  *) printf '%s\n' '格式須為 svg 或 png' >&2; exit 2 ;;
esac
timeout 60s docker run --rm --pull never --network none --user "$(id -u):$(id -g)" --memory 512m --cpus 1 --pids-limit 64 \
  --label project=dark-queen-of-krynn-cht -v "$ROOT/tools:/tools:ro" -v "$PROBE:/probe:ro" -v "$PARENT:/out" -v "$FONT:/font:ro" \
  --entrypoint python3 "$IMAGE" /tools/journal_diagrams.py "/probe/$GEOMETRY" "/probe/$LAYOUT" "/probe/$CATALOG" \
  /font/jf-openhuninn-2.1.ttf "/out/$(basename "$OUTPUT")" --format "$FORMAT"

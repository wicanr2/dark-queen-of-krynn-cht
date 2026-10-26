#!/usr/bin/env bash
# 本機研究原型。主機只檢查路徑並呼叫 Docker，不是正式遊戲啟動器。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$ROOT/workplace"
FONT="${DQK_FONT_DIR:-/home/anr2/cht/golden_box/death_knight_of_krynn/font}"
PIL_IMAGE=sha256:44d0742ca1061bcd453440cdce925afa31c5324e115fca1334da0e364f0e2c48
BROWSER_IMAGE=sha256:f1e7e01021efd65dd1a2c56064be399f3e4de00fd021ac561325f2bfbb2b837a
test -d "$WORK"
test -d "$ROOT/tools"
case "${1:-}" in
  world-map)
    NAME="${2:-guide-world-map-20261027}"
    [[ "$NAME" =~ ^guide-[a-zA-Z0-9-]+$ ]] || { echo '輸出名稱必須以 guide- 開頭' >&2; exit 2; }
    MAP_SOURCE="$WORK/probe/guide-20261027"
    MAP_IMAGES="$WORK/probe/player-current/hd/originals"
    test -d "$WORK/probe"
    test ! -e "$WORK/probe/$NAME"
    test -f "$MAP_SOURCE/world-map-layout.json"
    test -f "$MAP_SOURCE/world-map.zh-TW.tsv"
    test -f "$MAP_IMAGES/BIGPIC.1.1.png"
    test -f "$MAP_IMAGES/BIGPIC.2.1.png"
    test -f "$FONT/jf-openhuninn-2.1.ttf"
    test -f "$FONT/LICENSE-open-huninn.txt"
    OCR_IMAGE=sha256:5625e878af8cce84fff9a7f63248fa38e6ed38dbf32d1be59a60e74519842ee2
    timeout 30s docker run --rm --init --label project=dark-queen-of-krynn-cht \
      --network none --memory 1g --cpus 1 --pids-limit 64 --user "$(id -u):$(id -g)" \
      -e PYTHONDONTWRITEBYTECODE=1 --entrypoint bash -v "$ROOT/tools:/tools:ro" \
      -v "$MAP_IMAGES:/input:ro" -v "$WORK/probe:/out" "$OCR_IMAGE" -c '
set -euo pipefail
test "$(stat -c %u:%g /out)" = "$(id -u):$(id -g)"
mkdir "/out/$1"
python3 /tools/manual_world_map.py geometry /input "/out/$1/terrain.json"
' -- "$NAME"
    timeout 30s docker run --rm --init --label project=dark-queen-of-krynn-cht \
      --network none --memory 1g --cpus 1 --pids-limit 64 --user "$(id -u):$(id -g)" \
      -e PYTHONDONTWRITEBYTECODE=1 --entrypoint bash -v "$ROOT/tools:/tools:ro" \
      -v "$MAP_SOURCE:/source:ro" -v "$FONT:/font:ro" -v "$WORK/probe/$NAME:/out" "$PIL_IMAGE" -c '
set -euo pipefail
python3 /tools/manual_world_map.py render /out/terrain.json /source/world-map-layout.json /source/world-map.zh-TW.tsv /font/jf-openhuninn-2.1.ttf /font/LICENSE-open-huninn.txt /out/rendered
find /out -user root -o -type d -name "*.md"
'
    ;;
  geometry)
    NAME="${2:-guide-geo-fields-20261027}"
    [[ "$NAME" =~ ^guide-[a-zA-Z0-9-]+$ ]] || { echo '輸出名稱必須以 guide- 開頭' >&2; exit 2; }
    test -d "$WORK/probe"
    test ! -e "$WORK/probe/$NAME"
    test -f "$WORK/input/dos/drkqueen/DISK3/GEO.GLB"
    timeout 30s docker run --rm --init --label project=dark-queen-of-krynn-cht \
      --network none --memory 512m --cpus 1 --pids-limit 64 --user "$(id -u):$(id -g)" \
      -e PYTHONDONTWRITEBYTECODE=1 --entrypoint bash \
      -v "$ROOT/tools:/tools:ro" -v "$WORK/input/dos/drkqueen/DISK3:/input:ro" \
      -v "$WORK/probe:/out" "$PIL_IMAGE" -c '
set -euo pipefail
test "$(stat -c %u:%g /out)" = "$(id -u):$(id -g)"
python3 /tools/guide_geo.py /input/GEO.GLB "/out/$1"
find "/out/$1" -user root -o -type d -name "*.md"
' -- "$NAME"
    ;;
  index)
    test -d "$ROOT/walkthrough"
    test -f "$WORK/guide-map-notes.json"
    timeout 30s docker run --rm --init --label project=dark-queen-of-krynn-cht \
      --network none --memory 256m --cpus 1 --pids-limit 64 --user "$(id -u):$(id -g)" \
      --entrypoint python3 -v "$ROOT/tools:/tools:ro" -v "$ROOT/walkthrough:/input:ro" \
      -v "$WORK:/research:ro" -v "$WORK:/out" "$PIL_IMAGE" \
      /tools/index_guide_maps.py /input /research/guide-map-notes.json /out/guide-map-index.json
    ;;
  redraw)
    test -f "$WORK/caergoth-redraw.json"
    test -f "$FONT/jf-openhuninn-2.1.ttf"
    test -f "$FONT/LICENSE-open-huninn.txt"
    timeout 30s docker run --rm --init --label project=dark-queen-of-krynn-cht \
      --network none --memory 512m --cpus 1 --pids-limit 64 --user "$(id -u):$(id -g)" \
      --entrypoint python3 -v "$ROOT/tools:/tools:ro" -v "$WORK:/research:ro" \
      -v "$WORK:/out" -v "$FONT:/font:ro" "$PIL_IMAGE" \
      /tools/redraw_guide_map.py /research/caergoth-redraw.json /font/jf-openhuninn-2.1.ttf \
      /out/caergoth-redraw --font-license /font/LICENSE-open-huninn.txt
    ;;
  check)
    test -f "$WORK/caergoth-redraw/reader.html"
    timeout 35s docker run --rm --init --label project=dark-queen-of-krynn-cht \
      --network none --memory 1g --cpus 2 --pids-limit 128 --user "$(id -u):$(id -g)" \
      --entrypoint node -v "$ROOT/tools:/tools:ro" -v "$WORK/caergoth-redraw:/out" \
      "$BROWSER_IMAGE" /tools/check_map_reader.mjs /out/reader.html /out
    ;;
  *) echo '用法：bash tools/guide-map.sh index|redraw|check|geometry|world-map [guide-新名稱]' >&2; exit 2 ;;
esac

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
  *) echo '用法：bash tools/guide-map.sh index|redraw|check' >&2; exit 2 ;;
esac

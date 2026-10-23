#!/usr/bin/env bash
# DRAFT：手冊文字校讀與離線量測，不接入遊戲。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REVIEW="$ROOT/workplace/probe/manual-gameplay-20261023/appendix-r1/core-review"
PRIOR=/home/anr2/cht/golden_box/death_knight_of_krynn
NAME="${1:?全新檢查目錄名稱}"
[[ "$NAME" =~ ^[a-z0-9][a-z0-9-]*$ ]]
test -d "$REVIEW"
test -f "$REVIEW/source-review.json"
test -f "$PRIOR/text/glossary.tsv"; test -f "$PRIOR/font/jf-openhuninn-2.1.ttf"
test "$(stat -c %u:%g "$REVIEW")" = "$(id -u):$(id -g)"
test ! -e "$REVIEW/$NAME"
timeout 60s docker run --rm --pull never --network none --user "$(id -u):$(id -g)" --memory 1g --cpus 1 --pids-limit 64 \
  --label project=dark-queen-of-krynn-cht -v "$ROOT:/project:ro" -v "$ROOT/tools:/tools:ro" -v "$REVIEW:/review:ro" -v "$REVIEW:/out" \
  -v "$PRIOR/text:/prior:ro" -v "$PRIOR/font:/font:ro" --entrypoint python3 \
  sha256:6d849051db2e108262fa689160011dc64045cc402f61985548a525559d3a1cf3 \
  /tools/manual_review_check.py validate /project /review /prior/glossary.tsv /font/jf-openhuninn-2.1.ttf "/out/$NAME"
timeout 60s docker run --rm --pull never --network none --user "$(id -u):$(id -g)" --memory 1g --cpus 1 --pids-limit 64 \
  --label project=dark-queen-of-krynn-cht -v "$ROOT/tools:/tools:ro" -v "$REVIEW:/review:ro" -v "$REVIEW/$NAME:/out" -v "$PRIOR/font:/font:ro" \
  --entrypoint sh sha256:44d0742ca1061bcd453440cdce925afa31c5324e115fca1334da0e364f0e2c48 -c \
  'python3 /tools/menu_glyphs.py /font/jf-openhuninn-2.1.ttf /out/font-source.tsv /out/glyphs-16.json 16 && python3 /tools/manual_review_check.py layout /review /out'

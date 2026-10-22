#!/usr/bin/env bash
# DRAFT：營地短標籤的原版位置原型，不是正式啟動器。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROBE="$ROOT/workplace/probe"
ORIG="$ROOT/workplace/input/dos/drkqueen"
TEXTS="$ROOT/workplace/translation"
FONT="${DQK_FONT_DIR:-/home/anr2/cht/golden_box/death_knight_of_krynn/font}"
INPUT_RUN="${DQK_CAMP_INPUT_RUN:-camp-live-inputs-20261022}"
[[ "$INPUT_RUN" =~ ^[a-z0-9][a-z0-9-]+$ ]]
INPUT="$PROBE/$INPUT_RUN"
GO_IMAGE=sha256:8ed6bdee2bce1f32f804e888f942b25bbf62f2165a43344bb4587f3371de0581
PIL_IMAGE=sha256:44d0742ca1061bcd453440cdce925afa31c5324e115fca1334da0e364f0e2c48
test -d "$PROBE"
test -f "$ORIG/DQK.EXE"
test -f "$PROBE/startup/adventure-start.state"
test "$(stat -c %u "$PROBE")" = "$(id -u)"
test "$(stat -c %g "$PROBE")" = "$(id -g)"
case "${1:-}" in
  prepare)
    test -f "$FONT/jf-openhuninn-2.1.ttf"
    test -f "$TEXTS/en.tsv"
    test -f "$TEXTS/zh-TW.tsv"
    test -f "$PROBE/camp-lifecycle-observe-20261022/trace.json"
    test ! -e "$INPUT"
    timeout 30s docker run --rm --network none --memory 512m --cpus 1 --pids-limit 64 \
      --user "$(id -u):$(id -g)" --label project=dark-queen-of-krynn-cht \
      -v "$ROOT/tools:/tools:ro" -v "$TEXTS:/catalogs:ro" -v "$PROBE:/out" -v "$FONT:/font:ro" \
      "$PIL_IMAGE" python3 /tools/camp_live_inputs.py /catalogs /out/camp-lifecycle-observe-20261022/trace.json \
      "/out/$INPUT_RUN" /font/jf-openhuninn-2.1.ttf
    ;;
  build)
    test -f "$INPUT/zh-TW.tsv"
    test -f "$FONT/jf-openhuninn-2.1.ttf"
    test "$(stat -c %u "$INPUT")" = "$(id -u)"
    test "$(stat -c %g "$INPUT")" = "$(id -g)"
    bash "$ROOT/tools/early-live.sh" build
    timeout 30s docker run --rm --network none --memory 512m --cpus 1 --pids-limit 64 \
      --user "$(id -u):$(id -g)" --label project=dark-queen-of-krynn-cht \
      -v "$ROOT/tools:/tools:ro" -v "$INPUT:/out" -v "$FONT:/font:ro" "$PIL_IMAGE" \
      python3 /tools/menu_glyphs.py /font/jf-openhuninn-2.1.ttf /out/zh-TW.tsv /out/glyphs-16.json 16
    ;;
  en|zh|fine-en|fine-zh)
    RUN="${2:-}"
    [[ "$RUN" =~ ^[a-z0-9][a-z0-9-]+$ ]]
    test ! -e "$PROBE/$RUN"
    test -f "$PROBE/early-live"
    test -f "$INPUT/inputs.json"
    test -f "$INPUT/glyphs-16.json"
    TRANSLATE=true; FINE=false
    case "$1" in en|fine-en) TRANSLATE=false ;; esac
    case "$1" in fine-*) FINE=true ;; esac
    timeout --kill-after=10s 180s docker run --rm --init --network none --memory 1g --cpus 2 --pids-limit 128 \
      --user "$(id -u):$(id -g)" --label project=dark-queen-of-krynn-cht \
      -v "$ORIG:/orig:ro" -v "$INPUT:/inputs:ro" -v "$PROBE:/out" -v "$PROBE/startup:/states:ro" \
      -e DQK_RUN="$RUN" -e DQK_TRANSLATE="$TRANSLATE" -e DQK_FINE="$FINE" -e GOMEMLIMIT=384MiB \
      "$GO_IMAGE" bash -c '
        set -e
        Xvfb :99 -screen 0 800x600x24 -nolisten tcp > "/out/${DQK_RUN}-xvfb.log" 2>&1 & xvfb_pid=$!
        trap "kill $xvfb_pid 2>/dev/null; wait $xvfb_pid 2>/dev/null" EXIT
        for attempt in {1..50}; do test -S /tmp/.X11-unix/X99 && break; sleep 0.1; done
        export DISPLAY=:99 LIBGL_ALWAYS_SOFTWARE=1
        set +e
        /out/early-live -state /states/adventure-start.state -out "/out/$DQK_RUN" \
          -camp -lifecycle -camp-inputs /inputs/inputs.json -catalog /inputs/zh-TW.tsv \
          -glyphs /inputs/glyphs-16.json -translate="$DQK_TRANSLATE" -fine="$DQK_FINE"
        status=$?
        cat /sys/fs/cgroup/memory.events > "/out/$DQK_RUN/memory-events.txt"
        exit "$status"'
    ;;
  verify)
    EN_RUN="${2:-}"; ZH_RUN="${3:-}"
    [[ "$EN_RUN" =~ ^[a-z0-9][a-z0-9-]+$ && "$ZH_RUN" =~ ^[a-z0-9][a-z0-9-]+$ ]]
    test -f "$PROBE/$EN_RUN/receipt.json"
    test -f "$PROBE/$ZH_RUN/receipt.json"
    test -f "$INPUT/inputs.json"
    test -d "$TEXTS"
    test "$(stat -c %u "$PROBE/$ZH_RUN")" = "$(id -u)"
    test "$(stat -c %g "$PROBE/$ZH_RUN")" = "$(id -g)"
    timeout 60s docker run --rm --network none --memory 384m --cpus 1 --pids-limit 64 \
      --user "$(id -u):$(id -g)" --label project=dark-queen-of-krynn-cht \
      -v "$ROOT/tools:/tools:ro" -v "$TEXTS:/catalogs:ro" -v "$PROBE:/out" \
      -e PYTHONDONTWRITEBYTECODE=1 "$PIL_IMAGE" python3 /tools/camp_live_check.py \
      /out "/out/$INPUT_RUN" /catalogs "$EN_RUN" "$ZH_RUN"
    ;;
  *) echo '用法：bash tools/camp-live.sh prepare|build|en 新名|zh 新名|fine-en 新名|fine-zh 新名|verify 英文名 中文名' >&2; exit 2 ;;
esac

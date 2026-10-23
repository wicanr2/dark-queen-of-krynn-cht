#!/usr/bin/env bash
# DRAFT：中文存檔的連續冷讀研究，非正式啟動器。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROBE="$ROOT/workplace/probe"
ORIG="$ROOT/workplace/input/dos/drkqueen"
GO_IMAGE=sha256:8ed6bdee2bce1f32f804e888f942b25bbf62f2165a43344bb4587f3371de0581
PIL_IMAGE=sha256:44d0742ca1061bcd453440cdce925afa31c5324e115fca1334da0e364f0e2c48
RUN="${2:?需指定研究目錄名稱}"
[[ "$RUN" =~ ^[a-z0-9][a-z0-9-]+$ ]]
test -d "$PROBE"; test -d "$ROOT/tools"; test -f "$ORIG/DQK.EXE"
test "$(stat -c %u:%g "$PROBE")" = "$(id -u):$(id -g)"
SAVE="$PROBE/camp-live-zh-fine-20261022/scratch/SAVE"
ROLES="$PROBE/interactive-menu-inputs-20261022"
test -f "$SAVE/SavGamJ.qsv"; test -f "$SAVE/VaultJ.DAT"
test -f "$ROLES/glyphs-20.json"
case "${1:-}" in
 prepare)
  test ! -e "$PROBE/$RUN"
  timeout 30s docker run --rm --pull never --network none --user "$(id -u):$(id -g)" --memory 512m --cpus 1 --pids-limit 64 \
   --label project=dark-queen-of-krynn-cht -v "$ROOT/tools:/tools:ro" -v "$PROBE:/probe" --entrypoint python3 "$PIL_IMAGE" \
   /tools/cold_load.py prepare /probe "/probe/$RUN"
  ;;
 build)
  bash "$ROOT/tools/ui-list-live.sh" build
  test -d "$ROOT/workplace/dosgolem"; test -d "$PROBE/gocache"
  test -d /home/anr2/cht/dosgolem/workplace/gomodcache
  timeout 120s docker run --rm --pull never --init --network none --user "$(id -u):$(id -g)" --memory 2g --cpus 2 --pids-limit 128 \
   --label project=dark-queen-of-krynn-cht -e HOME=/tmp -e GOCACHE=/gocache -e GOMODCACHE=/modules -e GOPROXY=off -e GOMAXPROCS=2 \
   -v "$ROOT/workplace/dosgolem:/src:ro" -v "$ROOT/tools:/tools:ro" -v /home/anr2/cht/dosgolem/workplace/gomodcache:/modules:ro \
   -v "$PROBE/gocache:/gocache" -v "$PROBE:/out" -w /src --entrypoint go "$GO_IMAGE" \
   build -o /out/cold-load-probe /tools/cold_load_probe.go
  ;;
 native)
  test -f "$PROBE/$RUN/boot.json"; test -f "$PROBE/cold-load-probe"
  test ! -e "$PROBE/$RUN/native-cold"
  timeout 120s docker run --rm --pull never --init --network none --user "$(id -u):$(id -g)" --memory 1g --cpus 1 --pids-limit 64 \
   --label project=dark-queen-of-krynn-cht -v "$PROBE:/probe:ro" -v "$PROBE/$RUN:/out" -v "$ORIG:/orig:ro" \
   --entrypoint /probe/cold-load-probe "$GO_IMAGE" "/probe/$RUN/boot.json" \
   /probe/camp-live-zh-fine-20261022/scratch/SAVE /out/native-cold
  timeout 30s docker run --rm --pull never --network none --user "$(id -u):$(id -g)" --memory 512m --cpus 1 --pids-limit 64 \
   --label project=dark-queen-of-krynn-cht -v "$ROOT/tools:/tools:ro" -v "$PROBE/$RUN:/out" --entrypoint python3 "$PIL_IMAGE" \
   /tools/cold_load.py gameplay /out
  ;;
 reuse)
  PREVIOUS="${3:?需指定已有原版收據的研究目錄}"
  [[ "$PREVIOUS" =~ ^[a-z0-9][a-z0-9-]+$ ]]
  test -f "$PROBE/$PREVIOUS/native-cold/receipt.json";test -f "$PROBE/$RUN/boot.json"
  timeout 60s docker run --rm --pull never --network none --user "$(id -u):$(id -g)" --memory 1g --cpus 1 --pids-limit 64 \
   --label project=dark-queen-of-krynn-cht -v "$ROOT/tools:/tools:ro" -v "$PROBE:/probe:ro" -v "$PROBE/$RUN:/out" --entrypoint python3 "$PIL_IMAGE" \
   /tools/cold_load.py reuse /probe /out "$PREVIOUS"
  ;;
 fine)
  test -f "$PROBE/$RUN/observe-r1/receipt.json"
  timeout 30s docker run --rm --pull never --network none --user "$(id -u):$(id -g)" --memory 512m --cpus 1 --pids-limit 64 \
   --label project=dark-queen-of-krynn-cht -v "$ROOT/tools:/tools:ro" -v "$PROBE/$RUN:/out" --entrypoint python3 "$PIL_IMAGE" \
   /tools/cold_load.py fine /out
  ;;
 en|zh|fine-en|fine-zh)
  RESULT="${3:?需指定全新子目錄}"; [[ "$RESULT" =~ ^[a-z0-9][a-z0-9-]+$ ]]
  INPUT="${4:-services-trade-20261023/inputs-r2}"
  [[ "$INPUT" =~ ^[a-z0-9][a-z0-9/.-]*$ && "$INPUT" != *..* ]]
  test -f "$PROBE/$INPUT/inputs.json"; test -f "$PROBE/$RUN/gameplay-request.json"
  test -f "$PROBE/ui-list-live"; test ! -e "$PROBE/$RUN/$RESULT"
  test "$(stat -c %u:%g "$PROBE/$RUN")" = "$(id -u):$(id -g)"
  TRANSLATE=true; FINE=false
  case "$1" in en|fine-en) TRANSLATE=false;; esac
  case "$1" in fine-*) FINE=true;; esac
  timeout --kill-after=10s 1800s docker run --rm --pull never --init --network none --user "$(id -u):$(id -g)" --memory 3g --cpus 2 --pids-limit 128 \
   --label project=dark-queen-of-krynn-cht -e GOMAXPROCS=2 -e GOMEMLIMIT=1GiB \
   -v "$PROBE:/probe:ro" -v "$PROBE/$RUN:/out" -v "$ORIG:/orig:ro" --entrypoint bash "$GO_IMAGE" -c '
    set -e
    Xvfb :99 -screen 0 800x600x24 -nolisten tcp >/tmp/xvfb.log 2>&1 & xvfb_pid=$!
    trap "kill $xvfb_pid 2>/dev/null || true; wait $xvfb_pid 2>/dev/null || true" EXIT
    for attempt in {1..50}; do test -S /tmp/.X11-unix/X99 && break; sleep 0.1; done
    export DISPLAY=:99 LIBGL_ALWAYS_SOFTWARE=1
    fine_args=()
    if test "$5" = true && test -f "/probe/$1/native-fine-windows.json"; then fine_args=(-cold-fine-windows "/probe/$1/native-fine-windows.json"); fi
    reader_args=()
    ui_args=()
    if test -f "/probe/$1/ui-inputs/bindings.json";then ui_args=(-cold-ui-inputs "/probe/$1/ui-inputs");fi
    if test -f "/probe/$3/reader.zh-TW.tsv"; then reader_args=(-reader-catalog "/probe/$3/reader.zh-TW.tsv"); fi
    if test -f "/probe/$3/illustrations.json"; then reader_args+=(-reader-illustrations "/probe/$3/illustrations.json"); fi
    status=0
    /probe/ui-list-live -list -cold-load "/probe/$1/boot.json" \
      -cold-save /probe/camp-live-zh-fine-20261022/scratch/SAVE -cold-role-inputs /probe/interactive-menu-inputs-20261022 \
      -out "/out/$2" -list-request "/probe/$1/gameplay-request.json" -list-inputs "/probe/$3/inputs.json" \
      -catalog "/probe/$3/zh-TW.tsv" -source-catalog "/probe/$3/en.tsv" -glyphs "/probe/$3/glyphs-16.json" \
      "${fine_args[@]}" \
      "${reader_args[@]}" \
      "${ui_args[@]}" \
      -translate="$4" -fine="$5" >"/out/$2.log" 2>&1 || status=$?
    cat /sys/fs/cgroup/memory.events >"/out/$2-memory-events.txt"
    exit "$status"' -- "$RUN" "$RESULT" "$INPUT" "$TRANSLATE" "$FINE"
  ;;
 guards)
  test -f "$PROBE/$RUN/boot.json"; test -f "$PROBE/ui-list-live"
  test ! -e "$PROBE/$RUN/runtime-guards"
  timeout 30s docker run --rm --pull never --network none --user "$(id -u):$(id -g)" --memory 512m --cpus 1 --pids-limit 64 \
   --label project=dark-queen-of-krynn-cht -v "$ROOT/tools:/tools:ro" -v "$PROBE:/probe:ro" -v "$PROBE/$RUN:/out" \
   --entrypoint python3 "$PIL_IMAGE" /tools/cold_load.py guards-prepare /probe /out
  timeout 60s docker run --rm --pull never --init --network none --user "$(id -u):$(id -g)" --memory 1g --cpus 1 --pids-limit 96 \
   --label project=dark-queen-of-krynn-cht -v "$PROBE:/probe:ro" -v "$PROBE/$RUN:/out" -v "$ORIG:/orig:ro" \
   --entrypoint bash "$GO_IMAGE" -c '
    set -e
    Xvfb :99 -screen 0 800x600x24 -nolisten tcp >/tmp/xvfb.log 2>&1 & xvfb_pid=$!
    trap "kill $xvfb_pid 2>/dev/null || true; wait $xvfb_pid 2>/dev/null || true" EXIT
    for attempt in {1..50}; do test -S /tmp/.X11-unix/X99 && break; sleep 0.1; done
    export DISPLAY=:99 LIBGL_ALWAYS_SOFTWARE=1
    for name in source quiz time role snapshot; do
      boot="/probe/$1/boot.json";roles=/probe/interactive-menu-inputs-20261022;extra=()
      case "$name" in
        source) boot=/out/runtime-guards/bad-source.json;expected="中文存檔來源不符";;
        quiz) boot=/out/runtime-guards/bad-quiz.json;expected="未知冷讀路徑";;
        time) boot=/out/runtime-guards/bad-time.json;expected="中文存檔時間來源不符";;
        role) roles=/out/runtime-guards/role16;expected="冷讀角色選單需沿用 20px 十二標籤";;
        snapshot) extra=(-state "/probe/$1/native-cold/handoff.state");expected="互動原型只支援冷啟動角色選單";;
      esac
      result=/out/runtime-guards/$name-run
      if /probe/ui-list-live -list -cold-load "$boot" -cold-save /probe/camp-live-zh-fine-20261022/scratch/SAVE \
        -cold-role-inputs "$roles" -out "$result" -list-request "/probe/$1/gameplay-request.json" \
        -list-inputs /probe/services-trade-20261023/inputs-r2/inputs.json \
        -catalog /probe/services-trade-20261023/inputs-r2/zh-TW.tsv -source-catalog /probe/services-trade-20261023/inputs-r2/en.tsv \
        -glyphs /probe/services-trade-20261023/inputs-r2/glyphs-16.json "${extra[@]}" >"/out/runtime-guards/$name.log" 2>&1;then
        echo "應拒絕卻成功：$name" >&2;exit 1
      fi
      grep -Fq "panic: $expected" "/out/runtime-guards/$name.log"
      test ! -e "$result/receipt.json"
      printf "%s\t%s\n" "$name" "$expected" >> /out/runtime-guards/results.tsv
    done
    cat /sys/fs/cgroup/memory.events > /out/runtime-guards/memory-events.txt
    cat /out/runtime-guards/results.tsv' -- "$RUN"
  ;;
 check-gameplay|check-legacy)
  EN="${3:?英文子目錄}"; ZH="${4:?中文子目錄}"
  [[ "$EN" =~ ^[a-z0-9][a-z0-9-]+$ && "$ZH" =~ ^[a-z0-9][a-z0-9-]+$ ]]
  PREFIX=""; REPORT=gameplay-check.json
  if test "$1" = check-legacy;then PREFIX=legacy-;REPORT=legacy-check.json;fi
  test -f "$PROBE/$RUN/$EN/receipt.json";test -f "$PROBE/$RUN/$ZH/receipt.json"
  test -f "$PROBE/$RUN/${PREFIX}control-r1/receipt.json";test -f "$PROBE/$RUN/${PREFIX}observe-r1/receipt.json"
  test ! -e "$PROBE/$RUN/$REPORT"
  timeout 600s docker run --rm --pull never --network none --user "$(id -u):$(id -g)" --memory 3g --cpus 1 --pids-limit 64 \
   --label project=dark-queen-of-krynn-cht -e PYTHONDONTWRITEBYTECODE=1 -v "$ROOT/tools:/tools:ro" -v "$PROBE:/probe:ro" -v "$PROBE/$RUN:/out" \
   --entrypoint python3 "$PIL_IMAGE" /tools/ui_list_live_check.py "/out/$EN" "/out/$ZH" /probe/services-trade-20261023/inputs-r2 \
   "/out/${PREFIX}control-r1" "/out/${PREFIX}observe-r1" "/out/$REPORT"
  ;;
 check|negative)
  EN="${3:?英文子目錄}"; ZH="${4:?中文子目錄}"
  [[ "$EN" =~ ^[a-z0-9][a-z0-9-]+$ && "$ZH" =~ ^[a-z0-9][a-z0-9-]+$ ]]
  test -f "$PROBE/$RUN/$EN/receipt.json"; test -f "$PROBE/$RUN/$ZH/receipt.json"
  if test "$1" = check;then test ! -e "$PROBE/$RUN/cold-check.json";fi
  timeout 600s docker run --rm --pull never --network none --user "$(id -u):$(id -g)" --memory 3g --cpus 1 --pids-limit 64 \
   --label project=dark-queen-of-krynn-cht -e PYTHONDONTWRITEBYTECODE=1 -v "$ROOT/tools:/tools:ro" \
   -v "$PROBE:/probe:ro" -v "$PROBE/$RUN:/out" -v "$ROOT/workplace/translation:/catalogs:ro" --entrypoint python3 "$PIL_IMAGE" \
   /tools/cold_load.py "$1" /probe /out "$EN" "$ZH"
  ;;
 evidence)
  test -f "$PROBE/$RUN/cold-check.json";test -f "$PROBE/$RUN/gameplay-check.json"
  test -f "$PROBE/$RUN/legacy-check.json";test -f "$PROBE/$RUN/checker-negatives/results.json"
  test ! -e "$PROBE/$RUN/evidence.json"
  test "$(stat -c %u:%g "$PROBE/$RUN")" = "$(id -u):$(id -g)"
  timeout 180s docker run --rm --pull never --network none --user "$(id -u):$(id -g)" --memory 3g --cpus 1 --pids-limit 64 \
   --label project=dark-queen-of-krynn-cht -e PYTHONDONTWRITEBYTECODE=1 -v "$ROOT:/project:ro" \
   -v "$PROBE/$RUN:/project/workplace/probe/$RUN" --entrypoint python3 "$PIL_IMAGE" \
   /project/tools/cold_load.py evidence /project "/project/workplace/probe/$RUN"
  ;;
 *) printf '%s\n' '用法：cold-load.sh prepare|build|native|reuse|fine|guards|en|zh|fine-en|fine-zh|check|check-gameplay|check-legacy|negative|evidence 研究目錄 [子目錄]' >&2; exit 2;;
esac

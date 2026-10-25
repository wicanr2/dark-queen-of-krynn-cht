#!/usr/bin/env bash
# 冷啟動與正常視窗輸入的有界抽樣，不載入研究快照或預填答案。
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
NAME="${1:?請指定新的玩家抽驗目錄名稱}"
[[ "$NAME" =~ ^player-sample-[a-zA-Z0-9-]+$ ]]
test ! -e "$ROOT/workplace/probe/$NAME"
test -d "$ROOT/workplace/probe/player-current"
test -f "$ROOT/workplace/probe/player-current/dqk-player"
test -d "$ROOT/workplace/input/dos/drkqueen"
test -d "$ROOT/workplace/probe"
GO=sha256:8ed6bdee2bce1f32f804e888f942b25bbf62f2165a43344bb4587f3371de0581
docker image inspect "$GO" >/dev/null
timeout 15s docker run --rm --pull never --network none --user "$(id -u):$(id -g)" \
 --memory 256m --cpus 1 --pids-limit 32 --label project=dark-queen-of-krynn-cht \
 -v "$ROOT/workplace/probe:/output" --entrypoint bash "$GO" -c '
set -euo pipefail
test "$(stat -c %u:%g /output)" = "$(id -u):$(id -g)"
mkdir "/output/$1"
mkdir "/output/$1/session"
' -- "$NAME"
timeout --kill-after=5s 75s docker run --rm --pull never --init --network none \
 --user "$(id -u):$(id -g)" --memory 2g --cpus 2 --pids-limit 128 \
 --label project=dark-queen-of-krynn-cht -e HOME=/tmp -e LIBGL_ALWAYS_SOFTWARE=1 -e GOMAXPROCS=2 -e GOMEMLIMIT=1GiB \
 -v "$ROOT/tools:/tools:ro" -v "$ROOT/workplace/probe/player-current:/player:ro" \
 -v "$ROOT/workplace/input/dos/drkqueen:/orig:ro" -v "$ROOT/workplace/probe/$NAME:/out" \
 --entrypoint bash "$GO" -c '
set -euo pipefail
test "$(stat -c %u:%g /out)" = "$(id -u):$(id -g)"
OUT=/out
cc -O2 -Wall /tools/player_gui_probe.c -lX11 -o "$OUT/gui-driver"
Xvfb :91 -screen 0 1280x900x24 -nolisten tcp >"$OUT/xvfb.log" 2>&1 &
XVFB_PID=$!
APP_PID=""
cleanup(){ if [[ -n "$APP_PID" ]]; then kill "$APP_PID" 2>/dev/null || true; fi; kill "$XVFB_PID" 2>/dev/null || true; }
trap cleanup EXIT
for i in {1..50}; do [[ -S /tmp/.X11-unix/X91 ]] && break; sleep .1; done
test -S /tmp/.X11-unix/X91
export DISPLAY=:91
/player/dqk-player -player /player/inputs -original /orig -saves "$OUT/session" >"$OUT/player.log" 2>&1 &
APP_PID=$!
"$OUT/gui-driver" "$OUT" >"$OUT/driver.log" 2>&1
wait "$APP_PID"
APP_PID=""
test -f "$OUT/session/render-counts.json"
find "$OUT" -user root -o -type d -name "*.md"
' -- "$NAME"

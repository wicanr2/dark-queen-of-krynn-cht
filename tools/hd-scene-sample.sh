#!/usr/bin/env bash
# 只協調離線Docker，固定選樣，不修改正式玩家或素材。
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
NAME="${1:?請指定新的scene-hd-研究目錄}"
[[ "$NAME" =~ ^scene-hd-[a-zA-Z0-9-]+$ ]]
BASE="$ROOT/workplace/probe/$NAME"
THEME="$ROOT/workplace/probe/player-current/hd"
SDK="$ROOT/workplace/dosgolem"
MODULES=/home/anr2/cht/dosgolem/workplace/gomodcache
GO=sha256:8ed6bdee2bce1f32f804e888f942b25bbf62f2165a43344bb4587f3371de0581
test ! -e "$BASE"
test -d "$ROOT/workplace/probe"
test -d "$ROOT/workplace/probe/gocache"
test -d "$SDK"
test -d "$MODULES"
test -f "$THEME/hd.json"
test "$(git -C "$SDK" rev-parse HEAD)" = f79eab6db8c64a524a06535e53e5d32b0bbcf7c8
git -C "$SDK" diff --quiet HEAD -- .
docker image inspect "$GO" >/dev/null
timeout 150s docker run --rm --pull never --init --network none \
 --user "$(id -u):$(id -g)" --memory 2g --cpus 2 --pids-limit 128 \
 --label project=dark-queen-of-krynn-cht -e HOME=/tmp -e GOPROXY=off -e GOMAXPROCS=2 \
 -e GOCACHE=/gocache -e GOMODCACHE=/modules \
 -v "$SDK:/src:ro" -v "$ROOT/tools:/tools:ro" -v "$MODULES:/modules:ro" \
 -v "$ROOT/workplace/probe/gocache:/gocache" -v "$THEME:/theme:ro" \
 -v "$ROOT/workplace/probe:/output" -w /src --entrypoint bash "$GO" -c '
set -euo pipefail
test "$(stat -c %u:%g /output)" = "$(id -u):$(id -g)"
test ! -e "/output/$1"
mkdir "/output/$1"
out="/output/$1"
go build -o "$out/hd-scene-probe" /tools/hd_scene_probe.go /tools/render_scene_state.go /tools/player_scene_backend.go
Xvfb :93 -screen 0 1280x900x24 -nolisten tcp >"$out/xvfb.log" 2>&1 &
xvfb_pid=$!
trap '\''kill "$xvfb_pid" 2>/dev/null || true'\'' EXIT
DISPLAY=:93 LIBGL_ALWAYS_SOFTWARE=1 "$out/hd-scene-probe" /theme "$out"
sha256sum /theme/hd.json /tools/hd_scene_probe.go /tools/render_scene_state.go /tools/player_scene_backend.go >"$out/inputs.sha256"
find "$out" -user root -o -type d -name "*.md"
' -- "$NAME"

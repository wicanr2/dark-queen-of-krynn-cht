#!/usr/bin/env bash
# 只協調 Docker，原版函式與候選各由獨立 dosgolem 執行。
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
NAME="${1:?請指定新的研究目錄名稱}"
[[ "$NAME" =~ ^render-abi-[a-zA-Z0-9-]+$ ]]
BASE="$ROOT/workplace/probe/$NAME"
SDK="$ROOT/workplace/dosgolem"
MODULES=/home/anr2/cht/dosgolem/workplace/gomodcache
GO=sha256:8ed6bdee2bce1f32f804e888f942b25bbf62f2165a43344bb4587f3371de0581
PIL=sha256:b050fc7c49003ea6eecbbe0fc93b465b6869daf550c3284d5039e5e87517e831
test ! -e "$BASE"
test -d "$SDK"
test -d "$MODULES"
test -d "$ROOT/workplace/probe/gocache"
test -f "$ROOT/workplace/probe/verify-base-20261031-r2/base/palanthas.state"
test -f "$ROOT/workplace/input/dos/drkqueen/DQK.EXE"
docker image inspect "$GO" >/dev/null
docker image inspect "$PIL" >/dev/null
timeout 30s docker run --rm --pull never --network none --user "$(id -u):$(id -g)" \
 --memory 512m --cpus 1 --pids-limit 64 --label project=dark-queen-of-krynn-cht \
 -v "$SDK:/src:ro" -v "$ROOT/tools:/tools:ro" -v "$ROOT/workplace/probe:/output" \
 --entrypoint bash "$PIL" -c '
set -euo pipefail
test "$(stat -c %u:%g /output)" = "$(id -u):$(id -g)"
mkdir "/output/$1"
python /tools/player_video_overlay.py /src "/output/$1/build-overlay"
python -c '\''from pathlib import Path;import json,sys;p=Path("/output",sys.argv[1],"build-overlay/overlay.json");j=json.loads(p.read_text());j["Replace"]["/src/oracle/dqk_render_probe.go"]="/tools/oracle_render_probe.go";j["Replace"]["/src/internal/machine/dqk_render_probe.go"]="/tools/machine_render_probe.go";p.write_text(json.dumps(j,indent=2)+"\n")'\'' "$1"
' -- "$NAME"
timeout --kill-after=5s 90s docker run --rm --pull never --init --network none \
 --user "$(id -u):$(id -g)" --memory 2g --cpus 2 --pids-limit 128 \
 --label project=dark-queen-of-krynn-cht -e HOME=/tmp -e GOPROXY=off -e GOMAXPROCS=2 \
 -e GOCACHE=/gocache -e GOMODCACHE=/modules -v "$SDK:/src:ro" -v "$ROOT:/project:ro" \
 -v "$ROOT/tools:/tools:ro" -v "$ROOT/workplace/input/dos/drkqueen:/orig:ro" -v "$MODULES:/modules:ro" -v "$ROOT/workplace/probe/gocache:/gocache" -v "$BASE:/out" \
 -w /src --entrypoint bash "$GO" -c '
set -euo pipefail
test "$(stat -c %u:%g /out)" = "$(id -u):$(id -g)"
if [[ "$1" == gpu ]]; then
go build -o /out/render-gpu /tools/render_gpu_probe.go /tools/render_scene_state.go /tools/player_scene_backend.go
Xvfb :91 -screen 0 1280x900x24 -nolisten tcp >/out/xvfb.log 2>&1 &
XVFB_PID=$!
trap '\''kill "$XVFB_PID" 2>/dev/null || true'\'' EXIT
for i in {1..50}; do [[ -S /tmp/.X11-unix/X91 ]] && break; sleep .1; done
DISPLAY=:91 LIBGL_ALWAYS_SOFTWARE=1 /out/render-gpu /project /out
else
go build -overlay /out/build-overlay/overlay.json -o /out/render-abi /tools/render_abi_probe.go /tools/player_owned_drivers.go /tools/render_scene_state.go
/out/render-abi /project /out
fi
find /out -user root -o -type d -name "*.md"
' -- "${2:-abi}"

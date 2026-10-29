#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
NAME="${1:?新批次名稱}";MODE="${2:?exploration或combat}";PLAYER="${3:-player-finish-20261029}"
[[ "$NAME" =~ ^finish-scene-[a-zA-Z0-9-]+$ && "$PLAYER" =~ ^player-[a-zA-Z0-9-]+$ ]]
case "$MODE" in
 exploration) STATE=voyage-text-20261025/ashore-control-r3/final.state;;
 combat) STATE=battle-continuation-20261025/control-r1/final.state;;
 *) exit 2;;
esac
BASE="$ROOT/workplace/probe/$NAME";SOURCE="$ROOT/workplace/probe/$PLAYER"
test ! -e "$BASE";test -f "$ROOT/workplace/probe/$STATE";test -f "$SOURCE/dqk-player"
test -d "$ROOT/workplace/probe";test -d "$ROOT/workplace/probe/player-current/hd"
test -d /home/anr2/cht/dosgolem/workplace/gomodcache;test -d "$ROOT/workplace/probe/music-go-deps"
GO=sha256:8ed6bdee2bce1f32f804e888f942b25bbf62f2165a43344bb4587f3371de0581
PIL=sha256:b050fc7c49003ea6eecbbe0fc93b465b6869daf550c3284d5039e5e87517e831
timeout 30s docker run --rm --network none --user "$(id -u):$(id -g)" --memory 512m --cpus 1 --pids-limit 64 \
 --label project=dark-queen-of-krynn-cht -v "$ROOT:/project:ro" -v "$ROOT/workplace/probe:/probe" --entrypoint python3 "$PIL" -c '
from pathlib import Path
import shutil,sys,json
p=Path("/probe")/sys.argv[1];p.mkdir();(p/"code").mkdir();(p/"session").mkdir()
for name in Path("/project/tools/player_sources.txt").read_text().splitlines()+["finish_scene_inject.go"]:shutil.copy2(Path("/project/tools")/name,p/"code"/("zz_"+name if name=="finish_scene_inject.go" else name))
s=Path("/probe")/sys.argv[2]
for name in ["audio-go.mod","audio-go.sum"]:shutil.copy2(s/name,p/name)
shutil.copytree(s/"build-overlay",p/"build-overlay")
(p/"session/preferences.json").write_text(json.dumps(dict(Scale=2,HD=True,Music=False)))
' "$NAME" "$PLAYER"
timeout --kill-after=5s 150s docker run --rm --init --network none --user "$(id -u):$(id -g)" --memory 2g --cpus 2 --pids-limit 128 \
 --label project=dark-queen-of-krynn-cht -e HOME=/tmp -e GOPROXY=off -e GOMODCACHE=/modules -e GOCACHE=/gocache -e GOMAXPROCS=2 -e LIBGL_ALWAYS_SOFTWARE=1 -e DQK_TRACE_PLAYER_UI=1 \
 -e DQK_SAMPLE_STATE="/project/workplace/probe/$STATE" -e DQK_SAMPLE_OUT=/out/session \
 -v "$ROOT:/project:ro" -v "$ROOT/tools:/tools:ro" -v "$ROOT/workplace/dosgolem:/src:ro" \
 -v /home/anr2/cht/dosgolem/workplace/gomodcache:/modules:ro -v "$ROOT/workplace/probe/music-go-deps:/music-deps:ro" \
 -v "$ROOT/workplace/probe/gocache:/gocache" -v "$BASE:/out" -v "$SOURCE:/player:ro" \
 -v "$SOURCE/hd:/player/hd:ro" -v "$ROOT/workplace/input/dos/drkqueen:/orig:ro" -w /src --entrypoint bash "$GO" -c '
set -euo pipefail
go build -modfile /out/audio-go.mod -overlay /out/build-overlay/overlay.json -o /out/scene-player /out/code/*.go
cc -O2 /tools/finish_scene_probe.c -lX11 -o /out/scene-driver
go build -o /out/xtest-key /tools/player_xtest_key.go
Xvfb :93 -screen 0 1280x900x24 -nolisten tcp >/out/xvfb.log 2>&1 & XVFB_PID=$!
APP_PID="";trap '\''[[ -z "$APP_PID" ]] || kill "$APP_PID" 2>/dev/null || true; kill "$XVFB_PID" 2>/dev/null || true'\'' EXIT
for i in {1..50};do [[ -S /tmp/.X11-unix/X93 ]] && break;sleep .1;done
export DISPLAY=:93
echo "pcm.!default { type null }" >/tmp/asound-null.conf;export ALSA_CONFIG_PATH=/tmp/asound-null.conf
/out/scene-player -player /player/inputs -original /orig -saves /out/session >/out/player.log 2>&1 & APP_PID=$!
/out/scene-driver /out "$1" >/out/driver.log 2>&1
wait "$APP_PID";APP_PID=""
find /out -user root -o -type d -name "*.md"
' -- "$MODE"
timeout 30s docker run --rm --network none --user "$(id -u):$(id -g)" --memory 512m --cpus 1 --pids-limit 64 \
 --label project=dark-queen-of-krynn-cht -v "$ROOT/tools:/tools:ro" -v "$BASE:/out" --entrypoint python3 "$PIL" /tools/finish_scene_check.py /out "$MODE"

#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
NAME="${1:?新錄影批次}";MODE="${2:?normal、exploration或combat}";PLAYER="${3:-player-finish-20261029}"
EDITION="${4:-short}"
[[ "$EDITION" = short || "$EDITION" = story ]]
[[ "$NAME" =~ ^promo-[a-zA-Z0-9-]+$ && "$PLAYER" =~ ^player-[a-zA-Z0-9-]+$ ]]
case "$MODE" in normal) STATE="";DURATION=75;;exploration) STATE=voyage-text-20261025/ashore-control-r3/final.state;DURATION=40;;combat) STATE=battle-continuation-20261025/control-r1/final.state;DURATION=55;;*)exit 2;;esac
if [[ "$EDITION" = story ]];then
 case "$MODE" in normal) DURATION=165;;exploration) DURATION=70;;combat) DURATION=65;;esac
fi
BASE="$ROOT/workplace/probe/$NAME";SOURCE="$ROOT/workplace/probe/$PLAYER"
GAME_CONTAINER="dqk-$NAME-game";VIDEO_CONTAINER="dqk-$NAME-video"
trap 'docker rm -f "$GAME_CONTAINER" "$VIDEO_CONTAINER" >/dev/null 2>&1 || true' EXIT
test ! -e "$BASE";test -f "$SOURCE/dqk-player";test -d "$SOURCE/hd";test -d "$ROOT/workplace/probe/player-current/hd"
[[ -z "$STATE" ]] || test -f "$ROOT/workplace/probe/$STATE"
GO=sha256:8ed6bdee2bce1f32f804e888f942b25bbf62f2165a43344bb4587f3371de0581
PIL=sha256:b050fc7c49003ea6eecbbe0fc93b465b6869daf550c3284d5039e5e87517e831
MEDIA=sha256:1c99728881f2cbcb54bfef0c1621968e59e32d6102e1b924db9d17a8a8713465
timeout 30s docker run --rm --network none --user "$(id -u):$(id -g)" --memory 512m --cpus 1 --pids-limit 64 --label project=dark-queen-of-krynn-cht \
 -v "$ROOT:/project:ro" -v "$ROOT/workplace/probe:/probe" --entrypoint python3 "$PIL" -c '
from pathlib import Path
import json,shutil,sys,hashlib
p=Path("/probe")/sys.argv[1];p.mkdir();(p/"x11").mkdir();(p/"x11").chmod(0o1777);(p/"session").mkdir()
(p/"session/preferences.json").write_text(json.dumps(dict(Scale=3,HD=True,Music=True)))
s=Path("/probe")/sys.argv[2]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
shutil.copy2(s/"build-info.json",p/"source-build-info.json")
metadata=dict(binary_sha256=sha(s/"dqk-player"),profile_sha256=sha(s/"inputs/player-profile.json"),hd_sha256=sha(s/"hd/hd.json"),edition=sys.argv[4],mode=sys.argv[3],capture_canvas=[1280,900],full_screen_capture=True)
(p/"capture-inputs.json").write_text(json.dumps(metadata,indent=2)+"\n")
(p/"capture-source").mkdir()
for name in ["promo-capture.sh","promo_session.c","player_gui_probe.c","player_xtest_key.go"]:
    shutil.copy2(Path("/project/tools")/name,p/"capture-source"/name)
if sys.argv[3]!="normal":
    (p/"code").mkdir()
    for n in Path("/project/tools/player_sources.txt").read_text().splitlines():shutil.copy2(Path("/project/tools")/n,p/"code"/n)
    shutil.copy2("/project/tools/finish_scene_inject.go",p/"code/zz_finish_scene_inject.go")
    shutil.copytree(s/"build-overlay",p/"build-overlay")
    for n in ["audio-go.mod","audio-go.sum"]:shutil.copy2(s/n,p/n)
' "$NAME" "$PLAYER" "$MODE" "$EDITION"
timeout --kill-after=5s 260s docker run --rm --name "$GAME_CONTAINER" --init --network none --user "$(id -u):$(id -g)" --memory 2g --cpus 2 --pids-limit 128 --label project=dark-queen-of-krynn-cht \
 -e HOME=/tmp -e GOPROXY=off -e GOCACHE=/gocache -e GOMODCACHE=/modules -e GOMAXPROCS=2 -e LIBGL_ALWAYS_SOFTWARE=1 -e DQK_TRACE_PLAYER_UI=1 -e DQK_PROMO_EDITION="$EDITION" \
 -e DQK_SAMPLE_STATE="/project/workplace/probe/$STATE" -e DQK_SAMPLE_OUT=/out/session \
 -v "$ROOT:/project:ro" -v "$ROOT/workplace/dosgolem:/src:ro" -v "$ROOT/tools:/tools:ro" \
 -v /home/anr2/cht/dosgolem/workplace/gomodcache:/modules:ro -v "$ROOT/workplace/probe/music-go-deps:/music-deps:ro" -v "$ROOT/workplace/probe/gocache:/gocache" \
 -v "$BASE:/out" -v "$BASE/x11:/tmp/.X11-unix" -v "$SOURCE:/player:ro" \
 -v "$ROOT/workplace/input/dos/drkqueen:/orig:ro" -w /src --entrypoint bash "$GO" -c '
set -euo pipefail
APP=/player/dqk-player
if [[ "$1" != normal ]];then go build -modfile /out/audio-go.mod -overlay /out/build-overlay/overlay.json -o /out/scene-player /out/code/*.go;APP=/out/scene-player;fi
cc -O2 /out/capture-source/promo_session.c -lX11 -o /out/promo-driver
go build -o /out/xtest-key /out/capture-source/player_xtest_key.go
Xvfb :94 -screen 0 1280x900x24 -nolisten tcp >/out/xvfb.log 2>&1 & XVFB_PID=$!
APP_PID="";trap '\''[[ -z "$APP_PID" ]] || kill "$APP_PID" 2>/dev/null || true;kill "$XVFB_PID" 2>/dev/null || true'\'' EXIT
for i in {1..50};do [[ -S /tmp/.X11-unix/X94 ]] && break;sleep .1;done
export DISPLAY=:94
echo "pcm.!default { type null }" >/tmp/asound-null.conf;export ALSA_CONFIG_PATH=/tmp/asound-null.conf
"$APP" -player /player/inputs -original /orig -saves /out/session >/out/player.log 2>&1 & APP_PID=$!
/out/promo-driver /out "$1" >/out/events.tsv 2>/out/driver.log
wait "$APP_PID";APP_PID=""
' -- "$MODE" &
GAME_JOB=$!
timeout --kill-after=5s 245s docker run --rm --name "$VIDEO_CONTAINER" --init --network none --user "$(id -u):$(id -g)" --memory 1g --cpus 2 --pids-limit 96 --label project=dark-queen-of-krynn-cht \
 -e HOME=/tmp -v "$BASE:/out" -v "$BASE/x11:/tmp/.X11-unix:ro" --entrypoint bash "$MEDIA" -c '
set -euo pipefail
for i in {1..600};do [[ -s /out/window-id ]] && break;sleep .1;done
read -r WINDOW_ID </out/window-id;[[ "$WINDOW_ID" =~ ^[0-9]+$ ]]
ffmpeg -nostdin -v warning -y -f x11grab -draw_mouse 0 -framerate 30 -video_size 1280x900 -i :94 -t "$1" -an -c:v libx264 -preset veryfast -crf 17 -pix_fmt yuv420p /out/raw.mp4 >/out/encoder.log 2>&1 & ENCODER=$!
touch /out/recording
wait "$ENCODER";touch /out/stop
' -- "$DURATION"
wait "$GAME_JOB"

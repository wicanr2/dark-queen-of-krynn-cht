#!/usr/bin/env bash
# 冷啟動與正常視窗輸入的有界抽樣，不載入研究快照或預填答案。
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
NAME="${1:?請指定新的玩家抽驗目錄名稱}"
PLAYER="${2:-player-current}"
READER_SAMPLE="${3:-}"
AUDIO_SAMPLE="${4:-null}"
[[ "$AUDIO_SAMPLE" = null || ( "$AUDIO_SAMPLE" = pulse && "$READER_SAMPLE" = music ) ]]
[[ -z "$READER_SAMPLE" || "$READER_SAMPLE" = manual-map || "$READER_SAMPLE" = demo || "$READER_SAMPLE" = guide || "$READER_SAMPLE" = music ]]
[[ "$NAME" =~ ^player-sample-[a-zA-Z0-9-]+$ ]]
[[ "$PLAYER" =~ ^player-[a-zA-Z0-9-]+$ ]]
test ! -e "$ROOT/workplace/probe/$NAME"
test -d "$ROOT/workplace/probe/$PLAYER"
test -f "$ROOT/workplace/probe/$PLAYER/dqk-player"
test -f "$ROOT/workplace/probe/$PLAYER/build-info.json"
test -d "$ROOT/workplace/input/dos/drkqueen"
test -d "$ROOT/workplace/probe"
test -f "$ROOT/workplace/probe/player-sample-20261026-r5/02-return.ppm"
test -f "$ROOT/workplace/probe/player-sample-20261026-r5/02a-player.ppm"
test -f "$ROOT/workplace/probe/player-current/hd/hd.json"
HD="$ROOT/workplace/probe/player-current/hd"
if [[ -f "$ROOT/workplace/probe/$PLAYER/hd/hd.json" ]]; then
  HD="$ROOT/workplace/probe/$PLAYER/hd"
fi
test -d "$ROOT/workplace/dosgolem"
test -d /home/anr2/cht/dosgolem/workplace/gomodcache
test -d "$ROOT/workplace/probe/gocache"
GO=sha256:8ed6bdee2bce1f32f804e888f942b25bbf62f2165a43344bb4587f3371de0581
PIL=sha256:b050fc7c49003ea6eecbbe0fc93b465b6869daf550c3284d5039e5e87517e831
docker image inspect "$GO" >/dev/null
docker image inspect "$PIL" >/dev/null
RUNTIME="$GO"
AUDIO_ARGS=()
if [[ "$AUDIO_SAMPLE" = pulse ]]; then
 PULSE_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/pulse"
 test -d "$PULSE_DIR"
 test -S "$PULSE_DIR/native"
 test "$(docker image inspect dqk-player-audio:1.24-r1 --format '{{index .Config.Labels "dqk.audio.contract"}}')" = pulse-alsa-1.2.7.1-1
 RUNTIME=dqk-player-audio:1.24-r1
 AUDIO_ARGS=(-v "$PULSE_DIR:/pulse:ro" -e PULSE_SERVER=unix:/pulse/native -e ALSA_CONFIG_PATH=/opt/dqk/asound-pulse.conf)
fi
timeout 15s docker run --rm --pull never --network none --user "$(id -u):$(id -g)" \
 --memory 256m --cpus 1 --pids-limit 32 --label project=dark-queen-of-krynn-cht \
 -v "$ROOT/workplace/probe:/output" --entrypoint bash "$GO" -c '
set -euo pipefail
test "$(stat -c %u:%g /output)" = "$(id -u):$(id -g)"
mkdir "/output/$1"
mkdir "/output/$1/session"
' -- "$NAME"
timeout --kill-after=5s 240s docker run --rm --pull never --init --network none \
 --user "$(id -u):$(id -g)" --memory 2g --cpus 2 --pids-limit 128 \
 --label project=dark-queen-of-krynn-cht -e HOME=/tmp -e LIBGL_ALWAYS_SOFTWARE=1 -e GOMAXPROCS=2 -e GOMEMLIMIT=1GiB \
 -e DQK_TRACE_PLAYER_UI=1 \
 -e GOPROXY=off -e GOCACHE=/gocache -e GOMODCACHE=/modules \
 -v "$ROOT/workplace/dosgolem:/src:ro" -v /home/anr2/cht/dosgolem/workplace/gomodcache:/modules:ro \
 -v "$ROOT/workplace/probe/gocache:/gocache" -w /src \
 -v "$ROOT/tools:/tools:ro" -v "$ROOT/workplace/probe/$PLAYER:/player:ro" \
 -v "$HD:/player/hd:ro" \
 -v "$ROOT/workplace/input/dos/drkqueen:/orig:ro" -v "$ROOT/workplace/probe/$NAME:/out" \
 -v "$ROOT/workplace/probe/player-sample-20261026-r5:/reference:ro" \
 "${AUDIO_ARGS[@]}" --entrypoint bash "$RUNTIME" -c '
set -euo pipefail
test "$(stat -c %u:%g /out)" = "$(id -u):$(id -g)"
OUT=/out
cc -O2 -Wall /tools/player_gui_probe.c -lX11 -o "$OUT/gui-driver"
go build -o "$OUT/xtest-key" /tools/player_xtest_key.go
Xvfb :91 -screen 0 1280x900x24 -nolisten tcp >"$OUT/xvfb.log" 2>&1 &
XVFB_PID=$!
APP_PID=""
cleanup(){ if [[ -n "$APP_PID" ]]; then kill "$APP_PID" 2>/dev/null || true; fi; kill "$XVFB_PID" 2>/dev/null || true; }
trap cleanup EXIT
for i in {1..50}; do [[ -S /tmp/.X11-unix/X91 ]] && break; sleep .1; done
test -S /tmp/.X11-unix/X91
export DISPLAY=:91
if [[ "$2" = music && "$3" = null ]]; then
  echo "pcm.!default { type null }" > /tmp/asound-null.conf
  export ALSA_CONFIG_PATH=/tmp/asound-null.conf
fi
echo "{\"audio_device\":\"$3\"}" > "$OUT/audio-device.json"
cp /player/build-info.json "$OUT/build-info-at-start.json"
/player/dqk-player -player /player/inputs -original /orig -saves "$OUT/session" >"$OUT/player.log" 2>&1 &
APP_PID=$!
if [[ -n "$2" ]]; then
  "$OUT/gui-driver" "$OUT" /reference "$2" >"$OUT/driver.log" 2>&1
else
  "$OUT/gui-driver" "$OUT" /reference >"$OUT/driver.log" 2>&1
fi
wait "$APP_PID"
APP_PID=""
test -f "$OUT/session/render-counts.json"
find "$OUT" -user root -o -type d -name "*.md"
' -- "$NAME" "$READER_SAMPLE" "$AUDIO_SAMPLE"
timeout 30s docker run --rm --pull never --network none --user "$(id -u):$(id -g)" \
 --memory 1g --cpus 1 --pids-limit 64 --label project=dark-queen-of-krynn-cht \
 -v "$ROOT:/project:ro" -v "$ROOT/workplace/probe/$NAME:/out" --entrypoint python3 "$PIL" \
 /project/tools/player_sample_check.py /project /out ${READER_SAMPLE:+--$READER_SAMPLE}

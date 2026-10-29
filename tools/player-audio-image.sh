#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
test "$(docker image inspect dosgolem-go-ebiten:1.24-r1 --format '{{.Id}}')" = sha256:8ed6bdee2bce1f32f804e888f942b25bbf62f2165a43344bb4587f3371de0581
if ! docker image inspect dqk-player-audio:1.24-r1 >/dev/null 2>&1; then
 timeout --kill-after=10s 180s docker build --network default --memory 1g \
  --cpu-period 100000 --cpu-quota 100000 -f "$ROOT/tools/Dockerfile.player-audio" \
  -t dqk-player-audio:1.24-r1 "$ROOT/tools"
fi
timeout 15s docker run --rm --network none --user "$(id -u):$(id -g)" \
  --memory 256m --cpus 1 --pids-limit 32 --label project=dark-queen-of-krynn-cht \
  -v "$ROOT/tools:/tools:ro" --entrypoint sh dqk-player-audio:1.24-r1 -c '
test -f /usr/lib/x86_64-linux-gnu/alsa-lib/libasound_module_pcm_pulse.so
test -f /opt/dqk/asound-pulse.conf
cmp /tools/asound-pulse.conf /opt/dqk/asound-pulse.conf
test "$(dpkg-query -W -f=\${Version} libasound2-plugins)" = 1.2.7.1-1
'
docker image inspect dqk-player-audio:1.24-r1 --format '{{.Id}}'

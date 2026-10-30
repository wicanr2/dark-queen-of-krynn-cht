#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="${1:?完整版號}";MODE="${2:?linux或windows}"
BATCH="${3:-$MODE}"
[[ "$BATCH" =~ ^[a-zA-Z0-9-]+$ ]]
[[ "$VERSION" =~ ^v\.[0-9]+\.[0-9]+\.[0-9]+-[0-9]{8}$ ]]
case "$MODE" in linux|appimage) IMAGE=dosgolem-go-ebiten:1.24-r1;;windows) IMAGE=cok-wine-verify:noble-r1;;*)exit 2;;esac
STAGE="$ROOT/workplace/probe/package-$VERSION";OUT="$ROOT/dist-all/$VERSION/smoke/$BATCH"
if [[ ! -d "$STAGE" ]];then
 echo "封包解壓暫存已清理；先執行 bash tools/restore-package-stage.sh $VERSION，再重跑驗收。" >&2
 exit 2
fi
test -d "$ROOT/dist-all/$VERSION/smoke";test ! -e "$OUT"
test -d "$ROOT/workplace/dosgolem";test -d /home/anr2/cht/dosgolem/workplace/gomodcache
timeout 60s docker run --rm --network none --user "$(id -u):$(id -g)" --memory 1g --cpus 2 --pids-limit 64 --label project=dark-queen-of-krynn-cht \
 -e HOME=/tmp -e GOPROXY=off -e GOCACHE=/tmp/gocache -e GOMODCACHE=/modules -e GOMAXPROCS=2 \
 -v "$ROOT/workplace/dosgolem:/src:ro" -v "$ROOT/tools:/tools:ro" -v /home/anr2/cht/dosgolem/workplace/gomodcache:/modules:ro \
 -v "$ROOT/dist-all/$VERSION/smoke:/out" -w /src --entrypoint bash dosgolem-go-ebiten:1.24-r1 -c '
set -euo pipefail
mkdir "/out/$1";mkdir "/out/$1/session"
cc -O2 /tools/package_smoke.c -lX11 -o "/out/$1/smoke-driver"
go build -o "/out/$1/xtest-key" /tools/player_xtest_key.go
if [[ "$2" = windows ]];then GOOS=windows GOARCH=amd64 CGO_ENABLED=0 go build -o "/out/$1/native-close.exe" /tools/windows_native_close_windows.go;fi
' -- "$BATCH" "$MODE"
timeout --kill-after=5s 150s docker run --rm --init --network none --user "$(id -u):$(id -g)" --memory 2g --cpus 2 --pids-limit 256 --label project=dark-queen-of-krynn-cht \
 -e HOME=/tmp -e LIBGL_ALWAYS_SOFTWARE=1 -e GOMAXPROCS=2 -e DQK_TRACE_PLAYER_UI=1 -e WINEPREFIX=/out/wine -e WINEDEBUG=-all -e WINEARCH=win64 -e LANG=C.UTF-8 -e LC_ALL=C.UTF-8 \
 -e DQK_VERIFY_MAP_WINDOW="${DQK_VERIFY_MAP_WINDOW:-0}" \
 -e DQK_MAP_CLOSE_WM="${DQK_MAP_CLOSE_WM:-0}" \
 -v "$STAGE:/packages:ro" -v "$ROOT/dist-all/$VERSION/full-local:/artifacts:ro" -v "$OUT:/out" --entrypoint bash "$IMAGE" -c '
set -euo pipefail
Xvfb :95 -screen 0 1280x900x24 -nolisten tcp >/out/xvfb.log 2>&1 & XVFB_PID=$!
APP_PID="";trap '\''[[ -z "$APP_PID" ]] || kill "$APP_PID" 2>/dev/null || true; command -v wineserver >/dev/null && wineserver -k || true;kill "$XVFB_PID" 2>/dev/null || true'\'' EXIT
for i in {1..50};do [[ -S /tmp/.X11-unix/X95 ]] && break;sleep .1;done
export DISPLAY=:95
echo "pcm.!default { type null }" >/tmp/asound-null.conf;export ALSA_CONFIG_PATH=/tmp/asound-null.conf
if [[ "$1" = appimage ]];then
  PACKAGES=(/artifacts/*linux-amd64-full-local.AppImage)
  XDG_DATA_HOME=/out/userdata "${PACKAGES[0]}" --appimage-extract-and-run >/out/player.log 2>&1 & APP_PID=$!
elif [[ "$1" = linux ]];then
  PACKAGES=(/packages/*linux-amd64-full-local)
  XDG_DATA_HOME=/out/userdata "${PACKAGES[0]}/啟動.sh" >/out/player.log 2>&1 & APP_PID=$!
else
  wineboot -u >/out/wineboot.log 2>&1
  wineserver -w
  PACKAGES=(/packages/*windows-amd64-full-local)
  PACKAGE="${PACKAGES[0]}"
  wine "$PACKAGE/DarkQueen.exe" -player "Z:$PACKAGE/data/inputs" -original "Z:$PACKAGE/original" -saves Z:/out/session >/out/player.log 2>&1 & APP_PID=$!
fi
/out/smoke-driver /out >/out/driver.log 2>&1
wait "$APP_PID";APP_PID=""
find /out -user root -o -type d -name "*.md"
' -- "$MODE"
timeout 30s docker run --rm --network none --user "$(id -u):$(id -g)" --memory 512m --cpus 1 --pids-limit 64 \
 -v "$ROOT/tools:/tools:ro" -v "$OUT:/out" --entrypoint python3 sc-cht-hdtools:pillow11.3.0-r2 /tools/package_smoke_check.py /out "${MODE/appimage/linux}"
timeout 30s docker run --rm --network none --user "$(id -u):$(id -g)" --memory 256m --cpus 1 --pids-limit 32 \
 -v "$OUT:/out" --entrypoint python3 sc-cht-hdtools:pillow11.3.0-r2 -c '
from pathlib import Path
import json,hashlib,shutil
p=Path("/out");c=json.loads((p/"checks.json").read_text());assert c["passed"]
assert all(hashlib.sha256((p/n).read_bytes()).hexdigest()==h for n,h in c["screenshots"].items())
if (p/"wine").is_dir():shutil.rmtree(p/"wine")
for n in ["smoke-driver","xtest-key"]:
    if (p/n).is_file():(p/n).unlink()
for f in p.glob("*.ppm"):f.unlink()
'

#!/usr/bin/env bash
# 原版樂譜、取樣輸出與收據只留本機。主機僅負責 Docker 調度。
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
NAME="${2:-music-hd-20261029}"
[[ "$NAME" =~ ^music-hd-[a-zA-Z0-9-]+$ ]] || exit 2
BASE="$ROOT/workplace/probe/$NAME"
MEDIA=sha256:1c99728881f2cbcb54bfef0c1621968e59e32d6102e1b924db9d17a8a8713465
PIL=sha256:b050fc7c49003ea6eecbbe0fc93b465b6869daf550c3284d5039e5e87517e831
GO=sha256:8ed6bdee2bce1f32f804e888f942b25bbf62f2165a43344bb4587f3371de0581
test -d "$ROOT/workplace/probe"
case "${1:-}" in
 deps)
  test ! -e "$ROOT/workplace/probe/music-go-deps"
  timeout --kill-after=5s 90s docker run --rm --pull never --network bridge \
    --user "$(id -u):$(id -g)" --memory 1g --cpus 1 --pids-limit 64 \
    --label project=dark-queen-of-krynn-cht -e HOME=/tmp -e GOPROXY=https://proxy.golang.org \
    -e GOMODCACHE=/output/music-go-deps -e GOCACHE=/tmp/cache \
    -v "$ROOT/workplace/probe:/output" -w /tmp --entrypoint bash "$GO" -c '
set -euo pipefail
test "$(stat -c %u:%g /output)" = "$(id -u):$(id -g)"
mkdir /output/music-go-deps
go mod download -json github.com/jfreymuth/oggvorbis@v1.0.5 github.com/jfreymuth/vorbis@v1.0.2 >/output/music-go-deps/download.json
'
  ;;
 prepare)
  test ! -e "$BASE"
  test -d "$ROOT/workplace/input/dos/drkqueen/DISK1"
  timeout 30s docker run --rm --pull never --network none --user "$(id -u):$(id -g)" \
    --memory 512m --cpus 1 --pids-limit 64 --label project=dark-queen-of-krynn-cht \
    -e PYTHONDONTWRITEBYTECODE=1 -v "$ROOT/tools:/tools:ro" \
    -v "$ROOT/workplace/input/dos/drkqueen/DISK1:/original:ro" \
    -v "$ROOT/workplace/probe:/output" --entrypoint sh "$PIL" -c '
set -eu
test "$(stat -c %u:%g /output)" = "$(id -u):$(id -g)"
mkdir "/output/$1"
python3 /tools/xmi_score.py /original "/output/$1"
' -- "$NAME"
  ;;
 render)
  REV="${3:-r1}"
  [[ "$REV" =~ ^[a-zA-Z0-9-]+$ ]] || exit 2
  test -f "$BASE/inventory.json"
  test ! -e "$BASE/render-$REV"
  timeout --kill-after=5s 180s docker run --rm --pull never --network none \
    --user "$(id -u):$(id -g)" --memory 1g --cpus 2 --pids-limit 96 \
    --label project=dark-queen-of-krynn-cht -e HOME=/tmp -e PYTHONDONTWRITEBYTECODE=1 \
    -e DQK_MEDIA_IMAGE="$MEDIA" -v "$ROOT/tools:/tools:ro" -v "$BASE:/output" \
    --entrypoint sh "$MEDIA" -c '
set -eu
test "$(stat -c %u:%g /output)" = "$(id -u):$(id -g)"
python3 /tools/music_score_render.py /output "/output/render-$1"
find /output -user root -o -type d -name "*.md"
' -- "$REV"
  ;;
 check)
  REV="${3:-final}"
  [[ "$REV" =~ ^[a-zA-Z0-9-]+$ ]] || exit 2
  test -f "$BASE/render-$REV/manifest.json"
  timeout 30s docker run --rm --pull never --network none --user "$(id -u):$(id -g)" \
    --memory 512m --cpus 1 --pids-limit 64 --label project=dark-queen-of-krynn-cht \
    -e PYTHONDONTWRITEBYTECODE=1 -v "$ROOT/tools:/tools:ro" -v "$BASE:/output" \
    --entrypoint python3 "$PIL" /tools/music_score_check.py /output "/output/render-$REV"
  ;;
 probe)
  REV="${3:-r1}"
  [[ "$REV" =~ ^[a-zA-Z0-9-]+$ ]] || exit 2
  test -d "$BASE"
  test ! -e "$BASE/cue-$REV"
  test -f "$ROOT/workplace/input/dos/drkqueen/DQK.EXE"
  test -d "$ROOT/workplace/dosgolem"
  test -d /home/anr2/cht/dosgolem/workplace/gomodcache
  test -d "$ROOT/workplace/probe/gocache"
  timeout --kill-after=5s 100s docker run --rm --pull never --network none \
    --user "$(id -u):$(id -g)" --memory 2g --cpus 2 --pids-limit 96 \
    --label project=dark-queen-of-krynn-cht -e HOME=/tmp -e GOPROXY=off \
    -e GOCACHE=/gocache -e GOMODCACHE=/modules -e GOMAXPROCS=2 \
    -v "$ROOT/workplace/dosgolem:/src:ro" -v "$ROOT/tools:/tools:ro" \
    -v /home/anr2/cht/dosgolem/workplace/gomodcache:/modules:ro \
    -v "$ROOT/workplace/probe/gocache:/gocache" -v "$BASE:/output" \
    -v "$ROOT/workplace/input/dos/drkqueen:/orig:ro" -w /src --entrypoint bash "$GO" -c '
set -euo pipefail
test "$(stat -c %u:%g /output)" = "$(id -u):$(id -g)"
mkdir "/output/cue-$1"
go build -o "/output/cue-$1/probe" /tools/music_cue_probe.go /tools/music_cues.go
"/output/cue-$1/probe" /orig "/output/cue-$1" --all-cues >"/output/cue-$1/stdout.json"
find "/output/cue-$1" -user root -o -type d -name "*.md"
' -- "$REV"
  ;;
 install)
  PLAYER="${3:?請指定player整合目錄}"
  REV="${4:-final}"
  [[ "$PLAYER" =~ ^player-[a-zA-Z0-9-]+$ && "$REV" =~ ^[a-zA-Z0-9-]+$ ]] || exit 2
  test -f "$BASE/render-$REV/manifest.json"
  test -d "$ROOT/workplace/probe/$PLAYER"
  test ! -e "$ROOT/workplace/probe/$PLAYER/music"
  timeout 30s docker run --rm --pull never --network none --user "$(id -u):$(id -g)" \
    --memory 512m --cpus 1 --pids-limit 64 --label project=dark-queen-of-krynn-cht \
    -v "$BASE/render-$REV:/source:ro" -v "$ROOT/workplace/probe/$PLAYER:/player" \
    --entrypoint python3 "$PIL" -c '
import hashlib,json,shutil
from pathlib import Path
p=Path("/player");assert p.stat().st_uid==1000
source=Path("/source");m=json.loads((source/"manifest.json").read_text());assert len(m["tracks"])==8
target=p/"music";target.mkdir()
for track in m["tracks"]:
    name=track["key"]+".ogg";assert "/" not in name and ".." not in name
    assert hashlib.sha256((source/name).read_bytes()).hexdigest()==track["ogg_sha256"]
    shutil.copyfile(source/name,target/name)
for name in ["manifest.json","index.html"]:shutil.copyfile(source/name,target/name)
print("已安裝8曲，未複製MIDI、WAV或原版檔案")
'
  ;;
 *) echo "用法：bash tools/music-hd.sh deps|prepare|render|check|probe|install music-hd-批次 [修訂或player目錄]" >&2; exit 2;;
esac
docker ps -a --filter label=project=dark-queen-of-krynn-cht --format '{{.Names}} {{.Status}}'

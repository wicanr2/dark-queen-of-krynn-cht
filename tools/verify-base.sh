#!/usr/bin/env bash
# 重生驗證基準快照：bash tools/verify-base.sh verify-base-新名稱
# 原版唯讀掛在/orig；快照內的檔案代碼指向/orig，使用者也須以同一路徑掛載。
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
NAME="${1:?請指定新的verify-base-目錄名稱}"
[[ "$NAME" =~ ^verify-base-[a-zA-Z0-9-]+$ ]]
BASE="$ROOT/workplace/probe/$NAME"
SDK="$ROOT/workplace/dosgolem"
MODULES=/home/anr2/cht/dosgolem/workplace/gomodcache
GO=sha256:8ed6bdee2bce1f32f804e888f942b25bbf62f2165a43344bb4587f3371de0581
test ! -e "$BASE"
test -d "$SDK"
test -d "$MODULES"
test -d "$ROOT/workplace/probe/gocache"
test -f "$ROOT/workplace/input/dos/drkqueen/DQK.EXE"
test "$(git -C "$SDK" rev-parse HEAD)" = f79eab6db8c64a524a06535e53e5d32b0bbcf7c8
docker image inspect "$GO" >/dev/null
mkdir "$BASE"
timeout --kill-after=5s 300s docker run --rm --pull never --init --network none \
 --user "$(id -u):$(id -g)" --memory 2g --cpus 2 --pids-limit 128 \
 --log-opt max-size=10m --log-opt max-file=3 \
 --label project=dark-queen-of-krynn-cht -e HOME=/tmp -e GOPROXY=off -e GOMAXPROCS=2 \
 -e GOCACHE=/gocache -e GOMODCACHE=/modules -v "$SDK:/src:ro" -v "$ROOT/tools:/tools:ro" \
 -v "$ROOT/workplace/input/dos/drkqueen:/orig:ro" -v "$MODULES:/modules:ro" \
 -v "$ROOT/workplace/probe/gocache:/gocache" -v "$BASE:/out" \
 -w /src --entrypoint bash "$GO" -c '
set -euo pipefail
test "$(stat -c %u:%g /out)" = "$(id -u):$(id -g)"
go build -o /tmp/verify-base /tools/verify_base_probe.go
/tmp/verify-base /orig /out/base
find /out -user root -o -type d -name "*.md"
'

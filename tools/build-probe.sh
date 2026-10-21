#!/usr/bin/env bash
# 先以 git clone --no-hardlinks 保存核對過的來源至 workplace/dosgolem。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE="$ROOT/workplace/dosgolem"
OUT="$ROOT/workplace/probe"
MODULES="${DQK_GOMODCACHE:-/home/anr2/cht/dosgolem/workplace/gomodcache}"
test -f "$SOURCE/go.mod"
test -d "$MODULES"
mkdir -p "$OUT"
git -C "$SOURCE" rev-parse HEAD > "$OUT/source-commit.txt"
git -C "$SOURCE" diff --exit-code HEAD -- .
docker image inspect dosgolem-go-ebiten:1.24-r1 --format '{{.Id}}' > "$OUT/image-id.txt"
exec timeout 240s docker run --rm --init \
  --label project=dark-queen-of-krynn-cht --network none \
  --memory 2g --cpus 2 --pids-limit 128 \
  --log-opt max-size=10m --log-opt max-file=3 \
  --user "$(id -u):$(id -g)" \
  -v "$SOURCE:/src:ro" -v "$OUT:/out" -v "$MODULES:/modules:ro" \
  -e HOME=/tmp -e GOCACHE=/out/gocache -e GOMODCACHE=/modules \
  -e GOPROXY=off -e GOMAXPROCS=2 -w /src dosgolem-go-ebiten:1.24-r1 \
  bash -c 'set -e; /usr/local/go/bin/go version; /usr/local/go/bin/go build -o /out/probe ./cmd/probe; /usr/local/go/bin/go version -m /out/probe > /out/build-info.txt; sha256sum /out/probe'

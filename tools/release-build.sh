#!/usr/bin/env bash
# 同一份已固定來源建置三平台；所有工作負載在容器內。
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="${1:?請指定完整版號}"
COMMIT="${2:?請指定固定來源commit}"
PLAYER="${3:-player-finish-20261029}"
[[ "$VERSION" =~ ^v\.[0-9]+\.[0-9]+\.[0-9]+-[0-9]{8}$ && "$COMMIT" =~ ^[0-9a-f]{40}$ && "$PLAYER" =~ ^player-[a-zA-Z0-9-]+$ ]]
BASE="$ROOT/workplace/probe/$PLAYER"
test -d "$BASE/inputs"
test -d "$ROOT/workplace/dosgolem"
test -d "$ROOT/workplace/probe/music-go-deps"
test -d /home/anr2/cht/dosgolem/workplace/gomodcache
test -d "$ROOT/workplace/probe/gocache"
DQK_VERSION="$VERSION" DQK_SOURCE_COMMIT="$COMMIT" bash "$ROOT/tools/player.sh" build "$PLAYER"
GO=sha256:8ed6bdee2bce1f32f804e888f942b25bbf62f2165a43344bb4587f3371de0581
MAC=sha256:a2dc911a8709192604ffe6e4936dd3fd74fecc5fbc63996fbe75058edfa00980
COMMON=(--rm --pull never --network none --user "$(id -u):$(id -g)" --memory 3g --cpus 2 --pids-limit 128
 --label project=dark-queen-of-krynn-cht -e HOME=/tmp -e GOPROXY=off -e GOTOOLCHAIN=local -e GOMAXPROCS=2
 -e GOCACHE=/gocache -e GOMODCACHE=/modules -e DQK_VERSION="$VERSION" -e DQK_SOURCE_COMMIT="$COMMIT"
 -v "$ROOT/workplace/dosgolem:/src:ro" -v "$ROOT/tools:/tools:ro" -v "$BASE:/out"
 -v "$ROOT/workplace/probe/music-go-deps:/music-deps:ro" -v /home/anr2/cht/dosgolem/workplace/gomodcache:/modules:ro
 -v "$ROOT/workplace/probe/gocache:/gocache" -w /src --entrypoint bash)
timeout --kill-after=5s 240s docker run "${COMMON[@]}" "$GO" -c '
set -euo pipefail
mkdir -p /out/bin
cp /usr/local/go/LICENSE /out/go-toolchain-license.txt
SOURCES=();while IFS= read -r source; do SOURCES+=("/tools/$source");done </tools/player_sources.txt
GOOS=windows GOARCH=amd64 CGO_ENABLED=0 go build -ldflags "-s -w -X main.playerVersion=$DQK_VERSION -X main.playerCommit=$DQK_SOURCE_COMMIT" -modfile /out/audio-go.mod -overlay /out/build-overlay/overlay.json -o /out/bin/dqk-windows-amd64.exe "${SOURCES[@]}"
'
timeout --kill-after=5s 300s docker run "${COMMON[@]}" "$MAC" -c '
set -euo pipefail
test -d /osxcross/SDK/MacOSX15.5.sdk
SOURCES=();while IFS= read -r source; do SOURCES+=("/tools/$source");done </tools/player_sources.txt
export GOOS=darwin CGO_ENABLED=1 MACOSX_DEPLOYMENT_TARGET=11.0
export CGO_CFLAGS=-mmacosx-version-min=11.0 CGO_LDFLAGS=-mmacosx-version-min=11.0
for arch in amd64 arm64;do
  export GOARCH="$arch"
  if [[ "$arch" = amd64 ]];then export CC=o64-clang CXX=o64-clang++;else export CC=oa64-clang CXX=oa64-clang++;fi
  go build -ldflags "-s -w -X main.playerVersion=$DQK_VERSION -X main.playerCommit=$DQK_SOURCE_COMMIT" -modfile /out/audio-go.mod -overlay /out/build-overlay/overlay.json -o "/out/bin/dqk-macos-$arch" "${SOURCES[@]}"
done
x86_64-apple-darwin24.5-lipo -create /out/bin/dqk-macos-amd64 /out/bin/dqk-macos-arm64 -output /out/bin/dqk-macos-universal
x86_64-apple-darwin24.5-lipo -info /out/bin/dqk-macos-universal
'

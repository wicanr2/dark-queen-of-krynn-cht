#!/usr/bin/env bash
# DRAFT 唯讀探針；正常按鍵 p、l、e，來源與初始快照唯讀。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$ROOT/workplace"
MODULES="${DQK_GOMODCACHE:-/home/anr2/cht/dosgolem/workplace/gomodcache}"
IMAGE=sha256:8ed6bdee2bce1f32f804e888f942b25bbf62f2165a43344bb4587f3371de0581
test -d "$WORK/probe"
test -d "$WORK/probe/gocache"
test -f "$WORK/input/dos/drkqueen/DQK.EXE"
test -f "$WORK/probe/startup/239m.state"
test "$(stat -c %u "$WORK/probe")" = "$(id -u)"
test "$(stat -c %g "$WORK/probe")" = "$(id -g)"
if test -e "$WORK/probe/menu-lifecycle-probe"; then
  test "$(stat -c %u "$WORK/probe/menu-lifecycle-probe")" = "$(id -u)"
  test "$(stat -c %g "$WORK/probe/menu-lifecycle-probe")" = "$(id -g)"
fi
case "${1:-}" in
  build)
    test -d "$MODULES"
    test -f "$WORK/dosgolem/go.mod"
    test "$(git -C "$WORK/dosgolem" rev-parse HEAD)" = f79eab6db8c64a524a06535e53e5d32b0bbcf7c8
    git -C "$WORK/dosgolem" diff --exit-code HEAD -- .
    timeout 120s docker run --rm --init --network none --memory 2g --cpus 2 --pids-limit 128 \
      --label project=dark-queen-of-krynn-cht --user "$(id -u):$(id -g)" \
      -v "$WORK/dosgolem:/src:ro" -v "$ROOT/tools:/tools:ro" -v "$WORK/probe:/out" \
      -v "$WORK/probe/gocache:/gocache" -v "$MODULES:/modules:ro" -w /src \
      -e GOCACHE=/gocache -e GOMODCACHE=/modules -e GOPROXY=off -e GOMAXPROCS=2 \
      --entrypoint /usr/local/go/bin/go "$IMAGE" build -o /out/menu-lifecycle-probe /tools/menu_lifecycle_probe.go
    ;;
  observe|control)
    RUN_NAME="${2:-}"
    [[ "$RUN_NAME" =~ ^[a-z0-9][a-z0-9-]+$ ]]
    test ! -e "$WORK/probe/$RUN_NAME"
    test -f "$WORK/probe/menu-lifecycle-probe"
    OBSERVE=true
    if test "$1" = control; then OBSERVE=false; fi
    timeout 90s docker run --rm --init --network none --memory 1g --cpus 1 --pids-limit 64 \
      --label project=dark-queen-of-krynn-cht --user "$(id -u):$(id -g)" \
      -v "$WORK/input/dos/drkqueen:/orig:ro" -v "$WORK/probe/startup:/states:ro" \
      -v "$WORK/probe:/out" -e GOMEMLIMIT=768MiB -e GOMAXPROCS=1 \
      --entrypoint /out/menu-lifecycle-probe "$IMAGE" -state /states/239m.state \
      -out "/out/$RUN_NAME" -observe="$OBSERVE"
    ;;
  *) echo '用法：bash tools/menu-lifecycle.sh build|observe 新輸出名|control 新輸出名' >&2; exit 2 ;;
esac

#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PLATFORM="${1:-linux-amd64}"
VERSION=v.1.0.3-20261029
REPO=wicanr2/dark-queen-of-krynn-cht
GH=/home/anr2/.local/bin/gh
case "$PLATFORM" in linux-amd64|windows-amd64|macos-universal) ;; *) exit 2 ;; esac
test -f "$ROOT/docs/private-release-assets.json"
test -f "$ROOT/tools/private_release_assets.py"
test -d "$ROOT"
"$GH" auth status
test "$("$GH" repo view "$REPO" --json isPrivate --jq .isPrivate)" = true
run_assets() {
  timeout --kill-after=10s 600s docker run --rm --pull never --network none \
    --user "$(id -u):$(id -g)" --memory 512m --cpus 1 --pids-limit 64 \
    --label project=dark-queen-of-krynn-cht -e PYTHONDONTWRITEBYTECODE=1 \
    --mount "type=bind,src=$ROOT,dst=/project" \
    --entrypoint python3 sha256:b050fc7c49003ea6eecbbe0fc93b465b6869daf550c3284d5039e5e87517e831 \
    /project/tools/private_release_assets.py "$@"
}
CACHE="$(run_assets prepare "$PLATFORM")"
if test -f "$ROOT/dist-all/$VERSION/full-local/黑暗之后-$VERSION-$PLATFORM-full-local.zip"; then
  run_assets join "$PLATFORM"
  exit 0
fi
if test "$PLATFORM" = linux-amd64; then
  PATTERN="dqk-$VERSION-$PLATFORM-full-local.zip.part*"
else
  bash "$ROOT/tools/private-release-download.sh" linux-amd64
  PATTERN="dqk-$VERSION-$PLATFORM-full-local.zip.delta.json.gz"
fi
timeout --kill-after=10s 1800s "$GH" release download "$VERSION" --repo "$REPO" \
  --pattern "$PATTERN" --dir "$ROOT/$CACHE" --skip-existing
run_assets join "$PLATFORM"

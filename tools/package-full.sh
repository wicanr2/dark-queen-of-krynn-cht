#!/usr/bin/env bash
# 三平台完整版，Linux使用含遊戲資料的type-2 AppImage。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="${1:?完整版號}";COMMIT="${2:?來源commit}";PLAYER="${3:?整合目錄}"
[[ "$VERSION" =~ ^v\.[0-9]+\.[0-9]+\.[0-9]+-[0-9]{8}$ ]]
IMAGE=sha256:0b933af1238ab5839ad7a64b6ae05f069f57cb85da5917dfbe59730f6d7ba53f
docker image inspect "$IMAGE" >/dev/null
bash "$ROOT/tools/package-local.sh" "$VERSION" "$COMMIT" "$PLAYER" full-appimage
STAGE="$ROOT/workplace/probe/package-$VERSION"
DELIVERY="$ROOT/dist-all/$VERSION"
test -d "$STAGE";test -d "$DELIVERY"
python_phase() {
 timeout --kill-after=10s 300s docker run --rm --network none --user "$(id -u):$(id -g)" \
  --memory 1g --cpus 2 --pids-limit 64 --label project=dark-queen-of-krynn-cht \
  -e PYTHONDONTWRITEBYTECODE=1 --mount "type=bind,src=$ROOT,dst=/project,readonly" \
  --mount "type=bind,src=$STAGE,dst=/stage" --mount "type=bind,src=$DELIVERY,dst=/delivery" \
  --entrypoint python3 sc-cht-hdtools:pillow11.3.0-r2 /project/tools/appimage_payload.py "$1" \
  --version "$VERSION" --image-id "$IMAGE"
}
python_phase prepare
timeout --kill-after=10s 900s docker run --rm --network none --user "$(id -u):$(id -g)" \
 --memory 2g --cpus 2 --pids-limit 64 --label project=dark-queen-of-krynn-cht \
 --mount "type=bind,src=$STAGE,dst=/stage" --mount "type=bind,src=$DELIVERY,dst=/delivery" \
 -e VERSION="$VERSION" --entrypoint bash "$IMAGE" -c '
set -euo pipefail
echo "1cc49bcf1e2ccd593c379adb17c9f85a36d619088296504de95b1d06215aebbf  /opt/runtime-x86_64" | sha256sum -c -
mksquashfs -version > /delivery/smoke/appimage-squashfs-version.txt
mksquashfs /stage/dqk.AppDir /stage/dqk.squashfs -noappend -all-root -no-xattrs -comp zstd -b 1M -mem 256M -processors 2 -mkfs-time 0 -all-time 0 > /delivery/smoke/appimage-build.log 2>&1
target="/delivery/full-local/黑暗之后-$VERSION-linux-amd64-full-local.AppImage"
test ! -e "$target"
cat /opt/runtime-x86_64 /stage/dqk.squashfs > "$target"
chmod 755 "$target"
test "$("$target" --appimage-offset)" = 944632
mkdir /stage/appimage-extracted
cd /stage/appimage-extracted
"$target" --appimage-extract > /delivery/smoke/appimage-extract.log 2>&1
'
python_phase finalize

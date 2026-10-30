#!/usr/bin/env bash
# 只在需要重跑封包啟動驗收時，從已驗證ZIP重建已清除的解壓暫存。
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="${1:?請指定完整版號}"
[[ "$VERSION" =~ ^v\.[0-9]+\.[0-9]+\.[0-9]+-[0-9]{8}$ ]]
test -d "$ROOT/dist-all/$VERSION"
test -d "$ROOT/workplace/probe"
test ! -e "$ROOT/workplace/probe/package-$VERSION"
if test "$VERSION" = v.1.0.3-20261029; then
 for PLATFORM in linux-amd64 windows-amd64 macos-universal; do
  if test ! -f "$ROOT/dist-all/$VERSION/full-local/黑暗之后-$VERSION-$PLATFORM-full-local.zip"; then
   bash "$ROOT/tools/private-release-download.sh" "$PLATFORM"
  fi
 done
fi
timeout --kill-after=5s 600s docker run --rm -i --pull never --network none \
 --user "$(id -u):$(id -g)" --memory 1g --cpus 2 --pids-limit 64 \
 --label project=dark-queen-of-krynn-cht \
 -v "$ROOT:/project:ro" -v "$ROOT/workplace/probe:/project/workplace/probe" \
 --entrypoint python3 sha256:b050fc7c49003ea6eecbbe0fc93b465b6869daf550c3284d5039e5e87517e831 - "$VERSION" <<'PY'
from pathlib import Path, PurePosixPath
import hashlib
import json
import os
import stat
import sys
import zipfile

root=Path('/project');version=sys.argv[1]
delivery=root/'dist-all'/version
stage=root/'workplace/probe'/('package-'+version)
assert stage.parent.stat().st_uid==os.getuid() and not stage.exists()
manifest=json.loads((delivery/'SHA256SUMS.json').read_text())
assert manifest['version']==version
stage.mkdir()
for row in manifest['packages']:
    archive=delivery/row['kind']/row['file']
    with archive.open('rb') as f:
        assert hashlib.file_digest(f,'sha256').hexdigest()==row['sha256'],archive
    with zipfile.ZipFile(archive) as z:
        for info in z.infolist():
            p=PurePosixPath(info.filename)
            assert not p.is_absolute() and '..' not in p.parts and p.parts[0]==archive.stem
            assert not stat.S_ISLNK(info.external_attr>>16)
        z.extractall(stage)
        for info in z.infolist():
            if not info.is_dir():
                (stage/info.filename).chmod(stat.S_IMODE(info.external_attr>>16) or 0o644)
    print('restored',row['platform'],row['kind'],flush=True)
print('封包暫存已還原；正式ZIP及使用者存檔未改動。')
PY

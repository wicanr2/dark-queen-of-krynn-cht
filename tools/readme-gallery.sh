#!/usr/bin/env bash
# 重建本機圖文首頁。原版及試繪來源唯讀，只寫入指定的新研究目錄。
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
name="${1:-}"
if [[ ! "$name" =~ ^readme-gallery-[a-zA-Z0-9-]+$ ]]; then
  echo '用法：bash tools/readme-gallery.sh readme-gallery-新的名稱' >&2
  exit 2
fi
test -d "$ROOT/workplace/input/dos/drkqueen"
test -d "$ROOT/workplace/probe"
test -f "$ROOT/workplace/probe/readme-gallery-20261024/hd-blue-dragon-r2.png"
test -f "$ROOT/workplace/probe/readme-gallery-20261024/hd-portrait-r1.png"
test -f "$ROOT/tools/tlb_gallery.py"
test -f "$ROOT/tools/readme_preview.py"
test ! -e "$ROOT/workplace/probe/$name"
image=sha256:44d0742ca1061bcd453440cdce925afa31c5324e115fca1334da0e364f0e2c48
docker image inspect "$image" >/dev/null
timeout --kill-after=5s 120s docker run --rm --pull never --network none \
  --user "$(id -u):$(id -g)" --memory 2g --cpus 1 --pids-limit 64 \
  --label project=dark-queen-of-krynn-cht -e PYTHONDONTWRITEBYTECODE=1 \
  -e PYTHONPATH=/project/tools -v "$ROOT:/project:ro" \
  -v "$ROOT/workplace/probe:/output" --entrypoint python3 "$image" \
  -c 'import os,sys; from pathlib import Path
from tlb_gallery import run
from readme_preview import build
base=Path("/output"); assert base.stat().st_uid==os.getuid()
out=base/sys.argv[1]; assert not out.exists(); out.mkdir()
run(Path("/project/workplace/input/dos/drkqueen"),out)
build(Path("/project"),out)
assert all(p.stat().st_uid==os.getuid() for p in out.rglob("*"))
bad=[str(p) for p in out.rglob("*") if p.stat().st_uid==0 or p.is_dir() and p.name.endswith(".md")]
assert not bad,bad
print("本機圖文首頁：workplace/probe/"+sys.argv[1]+"/README.html")' "$name"

#!/usr/bin/env bash
# DRAFT：只重播本作已核對的存檔 J 冷啟動路徑，不是正式啟動器。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROBE="$ROOT/workplace/probe"
ORIG="$ROOT/workplace/input/dos/drkqueen"
SOURCE_RUN="${1:-}"
RUN="${2:-}"
[[ "$SOURCE_RUN" =~ ^[a-z0-9][a-z0-9-]+$ && "$RUN" =~ ^[a-z0-9][a-z0-9-]+$ ]]
test -f "$PROBE/probe"
test -f "$ORIG/DQK.EXE"
test -f "$PROBE/$SOURCE_RUN/scratch/SAVE/SavGamJ.qsv"
test -f "$PROBE/$SOURCE_RUN/scratch/SAVE/VaultJ.DAT"
test ! -e "$PROBE/$RUN"
test "$(stat -c %u "$PROBE")" = "$(id -u)"
test "$(stat -c %g "$PROBE")" = "$(id -g)"
GO_IMAGE=sha256:8ed6bdee2bce1f32f804e888f942b25bbf62f2165a43344bb4587f3371de0581
PIL_IMAGE=sha256:44d0742ca1061bcd453440cdce925afa31c5324e115fca1334da0e364f0e2c48
timeout 30s docker run --rm --network none --memory 256m --cpus 1 --pids-limit 32 \
  --user "$(id -u):$(id -g)" --label project=dark-queen-of-krynn-cht \
  -v "$PROBE/$SOURCE_RUN/scratch:/saved:ro" -v "$PROBE:/out" -v "$ORIG:/orig:ro" \
  "$PIL_IMAGE" python3 -c '
from pathlib import Path
import hashlib,os,shutil,sys
p=Path("/out")/sys.argv[1]
assert not p.exists() and p.parent.stat().st_uid==os.getuid()
assert hashlib.sha256(Path("/orig/DQK.EXE").read_bytes()).hexdigest()=="3b41fb06a045568b0c35098a104499d489d8a5c0ef0dd48a039387ba2393ba58"
expected={"SavGamJ.qsv":"72a45079a189126c3a96d4681fac846086a6edaf26748d260d3a73fbc8905488","VaultJ.DAT":"2acc13fa21f319fac65ad823d7ca52f1ed02d13ce8708431f7ce5c116d9db7ba"}
for name,want in expected.items():
 assert hashlib.sha256((Path("/saved/SAVE")/name).read_bytes()).hexdigest()==want,name
(p/"scratch/SAVE").mkdir(parents=True)
for name in expected:
 shutil.copyfile(Path("/saved/SAVE")/name,p/"scratch/SAVE"/name)
' "$RUN"
run_probe() {
  local label="$1"; shift
  local state_name
  local -a state_mount=()
  if test "${1:-}" = -load-state; then
    state_name="${2#/out/}"
    [[ "$state_name" =~ ^[a-z0-9-]+\.state$ ]]
    test -f "$PROBE/$RUN/$state_name"
    state_mount=(-v "$PROBE/$RUN/$state_name:/input.state:ro")
    shift 2
    set -- -load-state /input.state "$@"
  fi
  timeout 120s docker run --rm --init --network none --memory 1g --cpus 2 --pids-limit 128 \
    --user "$(id -u):$(id -g)" --label project=dark-queen-of-krynn-cht \
    -v "$ORIG:/orig:ro" -v "$PROBE/probe:/probe:ro" -v "$PROBE/$RUN:/out" \
    "${state_mount[@]}" \
    --entrypoint /probe "$GO_IMAGE" -root /orig -scratch /out/scratch "$@" \
    > "$PROBE/$RUN/$label.log" 2>&1
}
run_probe load-j -exe /orig/DQK.EXE -args 'SB220 SI7 RB330' \
  -steps 326000001 -bios-keys '       pltj' -bios-key-from 101000000 -bios-key-every 20000000 \
  -dump-vram /out/load-j.bin -save-state 326000000:/out/load-j.state
test -f "$PROBE/$RUN/load-j.state"
run_probe begin-loaded-j -load-state /out/load-j.state -steps 355000001 \
  -bios-keys b -bios-key-from 327000000 -dump-vram /out/begin-loaded-j.bin \
  -save-state 355000000:/out/begin-loaded-j.state
test -f "$PROBE/$RUN/begin-loaded-j.state"
# 查驗頁完全相同才送已核對的手冊答案；不猜題、不重試。
timeout 30s docker run --rm --network none --memory 128m --cpus 1 --pids-limit 32 \
  --user "$(id -u):$(id -g)" --label project=dark-queen-of-krynn-cht \
  -v "$PROBE/$RUN:/out:ro" "$PIL_IMAGE" python3 -c '
import hashlib
from pathlib import Path
assert hashlib.sha256(Path("/out/begin-loaded-j.bin").read_bytes()).hexdigest()=="d7eec5b094e4265a627d2b61333d3bc7d339572431e281ac29b533e10c76ae67","查驗頁不同，停止，不送答案"
'
run_probe resume-j -load-state /out/begin-loaded-j.state -steps 400000001 \
  -bios-keys 'spells\n' -bios-key-from 356000000 -bios-key-every 500000 \
  -dump-vram /out/resume-j.bin -save-state 400000000:/out/resume-j.state
echo "已完成冷啟動讀取，畫面及原版 I/O 紀錄位於 workplace/probe/$RUN/"

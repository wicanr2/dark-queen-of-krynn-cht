#!/usr/bin/env bash
# 中文整合入口。所有工作負載在既有 Docker 中；不自動執行抽驗。
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
NAME="${2:-player-current}"
[[ "$NAME" =~ ^player-[a-zA-Z0-9-]+$ ]] || { echo '整合目錄名稱必須以 player- 開頭' >&2; exit 2; }
BASE="$ROOT/workplace/probe/$NAME"
GO=sha256:8ed6bdee2bce1f32f804e888f942b25bbf62f2165a43344bb4587f3371de0581
PIL=sha256:44d0742ca1061bcd453440cdce925afa31c5324e115fca1334da0e364f0e2c48
FONT=/home/anr2/cht/golden_box/death_knight_of_krynn/font
SDK="$ROOT/workplace/dosgolem"
MODULES=/home/anr2/cht/dosgolem/workplace/gomodcache
test -d "$ROOT/workplace/probe"
docker image inspect "$GO" >/dev/null
docker image inspect "$PIL" >/dev/null
case "${1:-}" in
 prepare)
  test ! -e "$BASE"
  test -d "$FONT"
  test -f "$FONT/jf-openhuninn-2.1.ttf"
  timeout 60s docker run --rm --pull never --network none --user "$(id -u):$(id -g)" \
    --memory 2g --cpus 1 --pids-limit 64 --label project=dark-queen-of-krynn-cht \
    -e PYTHONDONTWRITEBYTECODE=1 -v "$ROOT:/project:ro" -v "$ROOT/workplace/probe:/output" \
    -v "$FONT:/font:ro" --entrypoint bash "$PIL" -c '
set -euo pipefail
test "$(stat -c %u:%g /output)" = "$(id -u):$(id -g)"
mkdir "/output/$1"
python3 /project/tools/player_inputs.py prepare /project "/output/$1/inputs"
python3 /project/tools/menu_glyphs.py /font/jf-openhuninn-2.1.ttf "/output/$1/inputs/toolbar.zh-TW.tsv" "/output/$1/inputs/toolbar-glyphs-16.json" 16
python3 /project/tools/player_inputs.py display /project "/output/$1/inputs" --font /font/jf-openhuninn-2.1.ttf
python3 /project/tools/player_inputs.py finish /project "/output/$1/inputs"
mkdir "/output/$1/session"
find "/output/$1" -user root -o -type d -name "*.md"
' -- "$NAME"
  ;;
 refresh-ui)
  test -d "$BASE/inputs"
  test -d "$FONT"
  test -f "$FONT/jf-openhuninn-2.1.ttf"
  timeout 60s docker run --rm --pull never --network none --user "$(id -u):$(id -g)" \
    --memory 1g --cpus 1 --pids-limit 64 --label project=dark-queen-of-krynn-cht \
    -e PYTHONDONTWRITEBYTECODE=1 -v "$ROOT:/project:ro" -v "$BASE/inputs:/inputs" \
    -v "$FONT:/font:ro" --entrypoint python3 "$PIL" /project/tools/player_inputs.py \
    refresh /project /inputs --font /font/jf-openhuninn-2.1.ttf
  ;;
 build)
  test -d "$BASE/inputs"
  test -d "$SDK"
  test -d "$MODULES"
  test -d "$ROOT/workplace/probe/gocache"
  test "$(git -C "$SDK" rev-parse HEAD)" = f79eab6db8c64a524a06535e53e5d32b0bbcf7c8
  git -C "$SDK" diff --quiet HEAD -- .
  timeout --kill-after=5s 120s docker run --rm --pull never --init --network none \
    --user "$(id -u):$(id -g)" --memory 2g --cpus 2 --pids-limit 128 \
    --label project=dark-queen-of-krynn-cht -e HOME=/tmp -e GOPROXY=off -e GOMAXPROCS=2 \
    -e GOCACHE=/gocache -e GOMODCACHE=/modules -v "$SDK:/src:ro" -v "$ROOT/tools:/tools:ro" \
    -v "$MODULES:/modules:ro" -v "$ROOT/workplace/probe/gocache:/gocache" -v "$BASE:/out" \
    -w /src --entrypoint bash "$GO" -c '
set -euo pipefail
test "$(stat -c %u:%g /out)" = "$(id -u):$(id -g)"
printf "%s\n" "{\"Replace\":{\"/src/oracle/dqk_video_observer.go\":\"/tools/oracle_video_observer.go\",\"/src/oracle/dqk_input_modifier.go\":\"/tools/oracle_input_modifier.go\"}}" >/tmp/player-overlay.json
go build -overlay /tmp/player-overlay.json -o /out/dqk-player /tools/early_text_live.go /tools/player_hd.go /tools/player_render_owner.go /tools/player_text_owner.go /tools/ui_cold_prompts.go /tools/ui_list_live.go /tools/ui_list_paragraphs.go /tools/ui_journal_reader.go /tools/ui_manual_reader.go /tools/ui_journal_illustrations.go /tools/ui_menu_source.go /tools/ui_hud_integer.go /tools/ui_inventory_ammo.go /tools/ui_hud_weapon.go /tools/ui_passage_source.go /tools/ui_passage_live.go /tools/ui_original_prefix.go
sha256sum /out/dqk-player >/out/binary.sha256
find /out -user root -o -type d -name "*.md"
'
  ;;
 run)
  test -f "$BASE/dqk-player"
  test -f "$BASE/inputs/player-profile.json"
  test -d "$BASE/session"
  test -d "$ROOT/workplace/input/dos/drkqueen"
  test -d /tmp/.X11-unix
  : "${DISPLAY:?請先設定目前桌面的 DISPLAY；本入口不自行建立或放寬 X11 權限}"
  XAUTH_ARGS=()
  if [[ -n "${XAUTHORITY:-}" ]]; then
    test -f "$XAUTHORITY"
    XAUTH_ARGS=(-v "$XAUTHORITY:/tmp/player-xauthority:ro" -e XAUTHORITY=/tmp/player-xauthority)
  fi
  # 使用者啟動的互動程序有六小時上限；結束後容器移除，存檔目錄保留。
  timeout --kill-after=10s 21600s docker run --rm --pull never --init --network none \
    --user "$(id -u):$(id -g)" --memory 3g --cpus 2 --pids-limit 128 \
    --label project=dark-queen-of-krynn-cht -e DISPLAY -e LIBGL_ALWAYS_SOFTWARE=1 \
    -e GOMAXPROCS=2 -e GOMEMLIMIT=2GiB -v /tmp/.X11-unix:/tmp/.X11-unix:ro \
    "${XAUTH_ARGS[@]}" -v "$ROOT/workplace/input/dos/drkqueen:/orig:ro" \
    -v "$BASE:/player:ro" -v "$BASE/session:/session" --entrypoint /player/dqk-player "$GO" \
    -player /player/inputs -original /orig -saves /session
  ;;
 *) echo '用法：bash tools/player.sh prepare|refresh-ui|build|run [player-新名稱]' >&2; exit 2 ;;
esac

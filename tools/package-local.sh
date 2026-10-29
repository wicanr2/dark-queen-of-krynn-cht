#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="${1:?完整版號}";COMMIT="${2:?來源commit}";PLAYER="${3:-player-finish-20261029}"
[[ "$VERSION" =~ ^v\.[0-9]+\.[0-9]+\.[0-9]+-[0-9]{8}$ && "$COMMIT" =~ ^[0-9a-f]{40}$ && "$PLAYER" =~ ^player-[a-zA-Z0-9-]+$ ]]
test -d "$ROOT/workplace/probe/$PLAYER"
test -d /home/anr2/cht/dosgolem/workplace/gomodcache
test -d /home/anr2/cht/golden_box/death_knight_of_krynn/font
PIL=sha256:b050fc7c49003ea6eecbbe0fc93b465b6869daf550c3284d5039e5e87517e831
timeout 15s docker run --rm --network none --user "$(id -u):$(id -g)" --memory 256m --cpus 1 --pids-limit 32 -v "$ROOT:/project" --entrypoint python3 "$PIL" -c 'from pathlib import Path; p=Path("/project"); assert p.stat().st_uid==1000; (p/"dist-all").mkdir(exist_ok=True)'
test -d "$ROOT/dist-all"
timeout --kill-after=5s 600s docker run --rm --network none --user "$(id -u):$(id -g)" --memory 1g --cpus 2 --pids-limit 64 --label project=dark-queen-of-krynn-cht \
 -v "$ROOT:/project:ro" -v "$ROOT/workplace/probe:/probe" -v "$ROOT/dist-all:/delivery" \
 -v /home/anr2/cht/dosgolem/workplace/gomodcache:/modules:ro \
 -v /home/anr2/cht/golden_box/death_knight_of_krynn/font:/font:ro --entrypoint python3 "$PIL" \
 /project/tools/release_payload.py --root /project --player "/probe/$PLAYER" --stage "/probe/package-$VERSION" --output "/delivery/$VERSION" \
 --modules /modules --deps /project/workplace/probe/music-go-deps --font /font --version "$VERSION" --commit "$COMMIT"

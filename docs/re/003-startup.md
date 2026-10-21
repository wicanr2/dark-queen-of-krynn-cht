# 003：正常冷啟動基線

日期：2026-10-21。工作：[#3](https://github.com/wicanr2/dark-queen-of-krynn-cht/issues/3)。
輸入雜湊與版本見 [001](001-input-baseline.md)。執行器為 dosgolem
`f79eab6db8c64a524a06535e53e5d32b0bbcf7c8`，隔離 clone 在 `workplace/dosgolem/`。
Go 1.24.13；image `dosgolem-go-ebiten:1.24-r1`，ID
`sha256:8ed6bdee2bce1f32f804e888f942b25bbf62f2165a43344bb4587f3371de0581`。

## 正常玩家輸入

從原始 `DQK.EXE` 入口執行，沿用 `START.BAT` 的 `SB220 SI7 RB330` 參數。
沒有座標、角色、資源、暫存器注入，也沒有略過原版初始化。

| 虛擬指令步數 | 一般輸入／觀測 |
|---|---|
| 5M | MicroMagic 標誌 |
| 100M | SSI 標誌 |
| 101M 起，每隔 20M | 空白鍵，共 7 次，依序通過 AD&D、Dragonlance、標題、美術及製作名單 |
| 240M | PLAY／DEMO／QUIT 選單，版本 1.1 |
| 241M | `p` |
| 246M | 12 項角色管理選單，等待輸入 |

以一次不讀取快照的完整冷啟動再次驗證：

```sh
bash tools/build-probe.sh
bash tools/probe.sh -exe /orig/DQK.EXE -root /orig \
  -args 'SB220 SI7 RB330' -scratch-dir /out/startup/scratch \
  -steps 246000000 -bios-keys '       p' \
  -bios-key-from 101000000 -bios-key-every 20000000 \
  -dump-mem '0-100000:/out/startup/cold-menu-ram.bin' \
  -dump-vram /out/startup/cold-menu.bin
```

以上 wrapper 會在容器內執行，不在主機跑 probe。原始資料唯讀；寫入限於研究輸出。
收據：`workplace/probe/startup/cold-menu.log`、`cold-menu.png`、`cold-menu-ram.bin`。
PNG SHA-256：`543dc4f2e8b31b8bc3bd1c68d8872b33512a2c83daac2d82a51997f05a65267f`。

## 已證實與限制

- 已證實：遊戲切到 mode 13h，320×200、256 色；載入本作 TLB／GLB，能以一般按鍵到角色管理選單。
- 已證實：本段未回報未實作 DOS 服務。最終 `CS:IP=17AB:0EDD`、`DS=333E`。
- 已證實：程式查找 `monitor.dat` 及 `DISK1\INSTR.` 未取得檔案，仍能繼續至選單。
  不推斷這兩個檔案對後續功能是否必要。
- 已證實：原版存在 PC speaker／PIT 輸出；尚未驗證人耳聽感或音樂正確性。
- 工具限制：泛用 probe 的 `-dump-at` 採 planar 擷取，本作使用 `-dump-vram` 取得 mode 13h 畫面。
  擷取路徑失敗不算遊戲缺陷。
- 範圍限制：這次冷啟動基線涵蓋到角色管理選單，正常讀入附帶隊伍另見下節。
  建角、探索、戰鬥與存檔回讀尚未驗證，不能宣稱整部遊戲相容。
- 快照接續與完整冷啟動的最終色號畫面相同，但完整 RAM 不同，不能稱整機同狀態。
  文字觀測成對比較另見 [規格 001](../spec/001-early-text.md)。

本輪只用 dosgolem 形成上述收據，沒有把 DOSBox 圖片當作本作正式對拍。

## 接續正常讀檔與第一段劇情

角色管理選單之後以一般按鍵接續，沒有更改原版記憶體：

| 步數 | 一般輸入及結果 |
|---|---|
| 260M | `l`，出現 LOAD FROM WHERE? |
| 275M | `t`，選 TDQ，出現 LOAD WHICH GAME A |
| 290M | `a`，讀入原版附帶的六人隊伍 |
| 306M | `b`，正常開始冒險，出現英文手札查驗題 |
| 330M 起每 0.5M | 依本輪題目輸入英文手札所指單字，再按 Enter |
| 350M | 進入帕蘭薩斯街景與第一段劇情 |

查驗採 [001 的英文手札補充來源](001-input-baseline.md#英文手札補充來源)，未改動判定或跳過題目。
接續收據在 `workplace/probe/startup/load-menu.*`、`load-slots.*`、`loaded-party.*`、
`adventure-start.*`、`intro-start.*`。各檢查點都是從上述正常輸入形成的機器快照。
這補充證明「可讀入附帶隊伍並開始」，沒有驗證自建隊伍、正式存檔回讀、移動、戰鬥或通關。

文字掛勾的新限制：這段另見 `1212:03A0` 的 X／Y 參數大於畫面尺寸，
例如 `#306352929` 為 8008／8068；不能把初始角色選單的直接像素座標解釋外推至所有呼叫。
其編碼方式目前未知，保留原始值與來源，不猜補座標或啟用翻譯。

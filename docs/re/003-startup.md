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

## 2026-10-22：讀取來源與返回的選單生命週期

工具：[menu_lifecycle_probe.go](../../tools/menu_lifecycle_probe.go)、
[menu-lifecycle.sh](../../tools/menu-lifecycle.sh)。仍使用上述固定 dosgolem 與 Go image，
原版 EXE SHA-256 為 `3b41fb06a045568b0c35098a104499d489d8a5c0ef0dd48a039387ba2393ba58`。
從正常入口的 239M 快照，依序在 241M、260M、275M 送 `p`、`l`、`e`。
`e` 是畫面上 EXIT 的一般輸入，沒有跳轉或注入狀態。

| 檢查點 | 畫面 | 1 MiB RAM SHA-256 |
|---|---|---|
| 246M | 角色管理選單 | `e06582277263a7f79e77d061a44f20bd3edd0ab986ee75e29849f26af9be0a8b` |
| 275M | LOAD FROM WHERE? | `5016889571d7b13c153ab8b7475964fd10e56b6665895714199c4e6acf3a0e5f` |
| 290M | 取消並返回角色管理選單 | `de144afabb3f10ed4303871efd9e3cef06c28c9f5cda7a1102ebfea44c7ee34f` |

已證實：唯讀觀測與無觀測控制組在三處的暫存器、RAM、色號、色盤、消耗按鍵及檔案寫入
紀錄相同，未回報未實作服務。這條路徑沒有實際存檔寫入，不等於存讀檔回讀驗證。
本輪顯存 OnWrite 觀測沒有捕捉到實際 VGA 寫入；這是觀測限制，不能推論沒有繪圖。

收據都在 `workplace/probe/`：

| 目錄及收據 | SHA-256 |
|---|---|
| `menu-lifecycle-hooks-20261022/receipt.json` | `b0b1341196e4e873da265bb191688b2f0b148031bc2d4f2ae2e2a65afce90dcb` |
| `menu-lifecycle-hooks-control-20261022/receipt.json` | `d970c60dcae1ee24fb465ee6d177ff562be45e53956f67c90c1774cbe65f5571` |

原始 `.i64` SHA-256 仍為 `636ccf8c97165ea836e3b88bf44958f07a26da720ebe55051a183d7c3978e70f`。
IDA Pro 9.4 查詢只在 `workplace/ida/menu-lifecycle-20261022/dqk-query.i64` 副本進行。
`result.json` SHA-256 為 `047e5e0cad3ed8f0615c9c4eea9de694934e5a589910de5fad76400dadc9af34`。
未被 IDA 納入函式的按鈕處理區只保留原始定位，不造函式名。

| 原始定位 | IDA linear | 原始檔偏移 | 本路徑的語意與等級 |
|---|---|---|---|
| 執行期 `0CEB:008E` | `0x1BE3E` | `0x0E23E` | 已證實：按鈕處理入口；far 參數第三個 word 為 1 時重畫按鈕，背景與文字在返回前完成 |
| `sub_2BF7F`，`1BB6:151F` | `0x2BF7F` | `0x1E37F` | 已證實：遍歷選單表並呼叫各控制項處理器；`1BB6:1585` 為本函式 RETF |
| `sub_2C043`，`1BB6:15E3` | `0x2C043` | `0x1E443` | 已證實：本輪輸入處理及被選按鈕重畫；`1BB6:17B8` 的 AX 為 FFFF 或已選索引 |

原始 bytes 留在探針與 IDA 匯出。位址換算只沿用已核對的 resident 公式，見規格 001。
選單表由執行期 `DS:DAC0` 的數量及 `DS:DAC7`／`DAC9` 的 far pointer 取得，項目長 32 bytes。
角色管理表有 14 項，包括 12 個文字按鈕；讀取來源表有 4 項。這個形狀只在本路徑證實。

| 輸入處理返回 | 下一批繪製入口 | 下一批繪製返回 | 畫面變化 |
|---|---|---|---|
| 241026258 | 241162507 | 241805302 | PLAY 到角色管理 |
| 260062329 | 260191986 | 260241058 | 角色管理到讀取來源 |
| 275027020 | 275172166 | 275815194 | 讀取來源返回角色管理 |

已證實：輸入處理返回早於新畫面的清除與背景建立，可用於開始保留上一張完整呈現。
新批次入口清除舊中文事件，返回後才提交新背景與中文。平時批次可能跳過乾淨控制項，
不能每次進入都刪除中文。選中按鈕也會在批次函式以外重畫，因此另包住動作 1 的按鈕呼叫。
可丟棄視窗原型與驗證收據見 [規格 001](../spec/001-early-text.md#選單往返的呈現交易原型)。

重生入口：先 `bash tools/menu-lifecycle.sh build`，再以 `observe 新輸出名`、
`control 另一新輸出名` 執行。輸出名必須全新，缺少原版、固定 clone 或正常快照即停止。

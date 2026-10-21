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

## 2026-10-22：冷啟動的實際鍵盤操作入口

新增 [interactive-menu.sh](../../tools/interactive-menu.sh) 作為 DRAFT 研究入口。
它沿用前作的 Docker／X11 顯示方法，使用本作固定的 dosgolem、Go 1.24.13、Ebiten 2.9.9
與既有 Go image。原始 EXE、資料及前作唯讀，暫存存檔與研究畫格只寫入本次全新輸出。
本輪程式仍在 `tools/`，沒有把可丟棄原型轉成正式程式或發行包。

### 實際操作前發現的離開邊界

原版正常載入隊伍，在 306M 按 `b` 後，輸入函式於 `306065699` 返回索引 10。
直到 329M 手札查驗畫面都沒有再進入 `1BB6:151F`／`1585` 的整批選單繪製。
因此先前只等下一批繪製返回的原型，在這條新路徑會一直保留舊選單。
既有 `p／l／e` 收據仍有效，沒有用它外推這次開始冒險的行為。

已證實：下一個狀態區輸出於 `306352929` 進入已核對的 `1212:03A0`，
格式為 `%s`，原始 Y／X 參數為 `8008／8068`。互動原型只在角色選單選擇 10 後，
用這個已觀測入口清除舊中文及解除保留。這些數值是原始編碼參數，不當成螢幕像素。
另一條正常空隊伍 `b` 路徑沒有有效選擇返回，沒有新文字，原型不能把它當成已切換畫面。

| 原版唯讀觀測收據，均在 `workplace/probe/` | 範圍 | SHA-256 |
|---|---|---|
| `menu-adventure-boundaries-20261022/receipt.json` | 到手札查驗，五處狀態與無觀測組相同 | `52786e04aa880b76bae542c54f5f2abf88af8081907e81fd5bb397b8ed9713bc` |
| `menu-empty-boundaries-20261022/receipt.json` | 空隊伍開始冒險，兩處狀態相同 | `284c08707575748fcc359d1f0a1920eb178765a162c2881220d59c1c0f1c146c` |

控制組為同名目錄的 `menu-adventure-control-20261022/`、`menu-empty-control-20261022/`。
`menu-lifecycle.sh observe／control 新名 adventure／begin-empty` 可重生，未回報未實作服務。
新收據另存 `menu_header_hex`，保留原始全域資料，不猜測各旗標名稱。

### 真正視窗輸入與原版重播

[menu_live_inputs.py](../../tools/menu_live_inputs.py) 由目前 `en.tsv`、`zh-TW.tsv` 衍生十二項角色
選單及 20px 圓體字模，舊原型只提供已觀測 key 集合，不沿用舊樣張的譯文。
輸入在 `workplace/probe/interactive-menu-inputs-20261022/`，`inputs.json` 記錄兩份正式表、
舊 key 集合、衍生輸出雜湊及正式 key 對照。`source-en.tsv`、`source-zh-TW.tsv` 保存整表快照，
重驗時另核對目前十二項來源與譯文。其他批次新增不會使這十二項的歷史收據失效。
原始英文仍在 guest 裡，只有 Draw 合成中文。

`early_text_live.go -interactive -lifecycle` 從原始 MZ 入口冷啟動，不載入機器快照，
沿 `START.BAT` 的 `SB220 SI7 RB330` 參數執行。Ebiten 接收真正視窗事件，再送原版 BIOS
鍵盤佇列。沒有內建測試用按鍵腳本；一般預覽需由操作者使用原版字母快捷鍵。

[x11_menu_driver.c](../../tools/x11_menu_driver.c) 在容器自己的 Xvfb 伺服器操作指定 PID 的視窗。
它只送 X11 KeyPress／KeyRelease，等視窗回報已收到事件才放開，不直接呼叫 Oracle 或寫入
遊戲狀態。另以 XGetImage 擷取可見視窗，驗證範圍不只包含 Ebiten 內部 GPU 讀回。
最後送原生 `WM_DELETE_WINDOW` 關閉視窗；程式仍正常保存最終檢查點及收據。

[interactive_replay.go](../../tools/interactive_replay.go) 從另一份原版冷啟動，以 GUI 收據記錄的
實際虛擬步數重送每個按鍵，不安裝覆繪觀測。兩側使用相同固定 EXE、SDK 與參數。
時鐘沿用 `dos.New` 執行前的 `Time{}`，基準為 `00:00:00.00`，再依虛擬指令的 PIT tick 推進；
不是主機時間。遊戲 seed 位置未解，本次沒有改 seed 或驗證骰序。來源與條件保存在
冒險組的 `clock-conditions.json`，不擴張成戰鬥亂數或硬體時序結論。

| 實際 GUI 收據，均在 `workplace/probe/` | 一般操作 | 畫格／按鍵數 | 收據 SHA-256 |
|---|---|---|---|
| `interactive-menu-x11-roundtrip-r3-20261022/receipt.json` | 冷啟動、角色選單、讀取、取消返回、關閉視窗 | 235／10 | `228c0e9247e6f463e2e879daff6adecb0acb72e4917d7353e7a6b68cbd9eb3f9` |
| `interactive-menu-x11-adventure-r3-20261022/receipt.json` | 冷啟動、讀入隊伍、開始冒險、查驗欄輸入後退格、關閉視窗 | 256／14 | `a393e281987dadb3a7b99e6bc0294678eba3e8ba2eed72197d6580c2c53e5e20` |

兩組各自的無覆繪重播，暫存器、1 MiB RAM、原版色號、色盤、消耗按鍵與寫檔紀錄完全相同，
未寫檔、沒有未實作服務。兩組輸入時間不同，不拿彼此的整機記憶體比較。
取消返回組在 254M 的 RAM 為 `65775b5964b2cffbd7f03d9c14b942ca53afc172c8316576d25965a6bdb80c74`，
冒險組在 272M 為 `1af147607a8619f7438ef1144aae6b7973099cd325cac242c829bb0ff0df05f3`。

已證實：每幀 GPU 讀回等於合成輸入，保留畫格等於上一張完整畫面；沒有提交只建好部分標籤
的角色選單。真實 X11 640×400 視窗擷取逐點等於近期提交。冒險組於 `256348970` 清除舊標籤，
抽看前後畫格沒有露出原版角色按鈕文字，後續查驗畫面沒有中文殘字。兩組 OOM 計數皆為 0。
字母輸入與 Backspace 通過，沒有提交查驗答案或修改原版判定。

[check_interactive_menu.py](../../tools/check_interactive_menu.py) 驗證正式譯表依賴、全部畫格、
視窗擷取及重播收據。兩組控制結果在各自的 `-control/comparison.json`，總檢查在冒險組
`gui-verification.json`，邊界抽圖為 `begin-boundary-contact.png`；圖含原版素材，只留本機。

重生入口如下，所有工作負載均由 Docker 執行，輸出名必須全新。

```sh
bash tools/interactive-menu.sh prepare
bash tools/interactive-menu.sh build
bash tools/interactive-menu.sh smoke 全新取消返回名
bash tools/interactive-menu.sh smoke-adventure 全新冒險名
bash tools/interactive-menu.sh replay 全新取消返回名
bash tools/interactive-menu.sh replay 全新冒險名
bash tools/interactive-menu.sh verify 全新取消返回名 全新冒險名
```

字模與資料已存在時略過 `prepare`；要改用新的輸入版本，透過 `DQK_MENU_INPUT_RUN` 指定新目錄名。
一般鍵盤預覽使用 `bash tools/interactive-menu.sh preview 全新預覽名`，需主機 X11 DISPLAY
與可讀的 XAUTHORITY；這個分支沿用前作 X11 方法，本輪只實測容器自有 Xvfb 的 GUI 路徑。
預覽最長 10 分鐘、測試最長 3 分鐘，背景程序皆有 trap，沒有留下執行中容器。

限制：仍是 DRAFT，僅十二項角色選單中文。其他按鈕路徑、滑鼠、IME、音訊、正式存讀檔、
長段分頁與其餘遊戲中文尚未完成；劇情字級問題仍待選。沒有新增前作的作弊鍵或 HD 選項。

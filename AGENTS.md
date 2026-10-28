# 《黑暗之后》（The Dark Queen of Krynn）HD＋繁體中文化

本檔是 Claude 與 Codex 共用的專案入口。回覆、文件與提交訊息預設使用繁體中文。
新工作階段先讀本檔，再讀 `CONTEXT.md`、目前 GitHub Issue 與直接相關規格。
檔案尚未建立時明列缺項，不把前作狀態當成本作進度。

## 1. 使用者授權與工作順序

使用者於 2026-10-21 指定：

- 參考 `/home/anr2/cht/golden_box/death_knight_of_krynn/` 與
  `/home/anr2/cht/golden_box/champions_of_krynn/` 的經驗，進行《黑暗之后》HD＋中文化。
- 優先處理繁體中文，先撰寫本檔。
- 授權建立本專案的 GitHub 儲存庫。
- 明確授權使用主機 `/home/anr2/.local/bin/gh` 完成上述儲存庫操作。

建立儲存庫時採私人可見性，名稱預設 `dark-queen-of-krynn-cht`。owner 以主機登入身分
回讀為準，不由前作網址推定。先查同名庫；存在時核對用途，不接管、不覆寫既有專案。
建立授權不包含轉公開、公開 Release、上傳原版素材、改動前作或推送 dosgolem 上游。

| 項目 | 本作目前契約 |
|---|---|
| 中文題名 | 沿用使用者稱呼「黑暗之后」；來源盤點時核對封面，不自行改名 |
| 優先順序 | 使用者要求先完成中文化，再補齊 HD；目前中文資料已接到統一入口，HD接入依現況續行。攻略18章正文已重排，餘圖與閱讀器待接，現況見 `CONTEXT.md` |
| 驗證與 HD 審查上限 | 2026-10-26 使用者重新授權「可以抽驗」，可做必要函式對照與代表玩家操作；以最小充分證據收斂，不重跑全部父批，不把未跑範圍記成已驗。HD 同批最多審查兩輪，第二輪後接受結果。證據入口為 `CONTEXT.md`，來源與交付權利邊界維持。 |
| 工具列 | 2026-10-25 使用者明確要求納入；參照《幽靈騎士》頂端工具列，接上已授權的繁中／原版、縮放、手札、說明、手動攻略及 HD 控制。尚未接妥的控制明列停用原因，不移植前作作弊、答案、多語或未授權功能。 |
| 技術起點 | 參照前作的 dosgolem 執行原版與輸出覆繪方法；本作可執行性、掛勾與相容性逐項重驗 |
| 繪圖接管 | 使用者要求完全接管繪圖，必要時反組譯找掛勾。入口為[規格 005](docs/spec/005-render-owner.md)與[研究 007](docs/re/007-render-ownership.md)：玩家視窗只取新繪圖層的完整前緩衝；原版顯存留作背景相容資料。影像與短字串在原版繪製前辨識，不再用全畫面搜尋作 HD 來源。完整命令覆蓋及全量素材尚須補齊，不把部分接管稱為全部完成。 |
| 其他語言 | 本輪先處理繁中，不把前作五語擴充視為本作已授權交付範圍 |
| HD 與介面 | 使用者確認目前整合版：角色管理 20 像素圓體、其餘文字 16 像素、閱讀保留原框、頂端懸停工具列，見 [規格 003](docs/spec/003-player-toolbar.md)。HD 開關與視窗大小各自獨立，2 倍、3 倍與自由縮放都保留 HD 偏好；接續既有試繪方向，每批最多兩輪，見 [規格 004](docs/spec/004-hd-layer.md) |
| 手札與說明 | 使用者已選擇內建手札與繁中說明面板，引用時顯示對應手札；原版規則與存檔判定不變 |
| 攻略與答案 | 內建獨立、手動開啟的攻略閱讀頁；正文重新排版，攻略地圖重新繪製並作繁中標註，掃描只作校對來源，不以嵌入 PDF 或掃描頁交付；自動提示、查驗題答案及地圖疊層未定案 |
| 封包與發行 | 平台、完整版、推廣片及公開方式尚未定案 |

可逆的讀取、整理、文件修正與已授權測試自主進行。需要改變目標、架構、原版忠實度、
正式資料格式、玩家操作、授權或公開方式時，先按第 10 節共同決策。

## 2. 初始化順序與目前基線

初始化依序完成：本檔 → `.gitignore` → 私人儲存庫與 Git → 初始 Issue → 證據與規格 → 實作。
研究與實作以 GitHub Issue 追蹤；遠端 Issue 是可執行工作狀態的權威，本機不另建
`WORKLIST.md` 鏡像。未建立的 Issue 不填虛構編號或完成狀態。

以下是初始化時的本機觀察，後續現況集中移交 `CONTEXT.md`，不在本檔累積逐輪歷程。

| 項目 | 2026-10-21 初始觀察 |
|---|---|
| 原始輸入 | 根目錄已有第 3 節列出的 ZIP 與 RAR；內容與雜湊尚未盤點 |
| 程式與驗證 | 尚未建立本作程式、執行收據或中文化完成證據 |
| 本機 Git | 初次受 sandbox 阻擋；環境解除後已初始化 `main`，現況見 `CONTEXT.md` |
| GitHub | 已建立私人庫 `wicanr2/dark-queen-of-krynn-cht`，Issues 啟用；回讀見 `CONTEXT.md` |

初始工作範圍如下。只有實際建立並回讀後，才補 Issue 連結。

| 階段 | 依賴 | 完成條件 |
|---|---|---|
| G0 治理與環境 | 本檔 | 排除原始資料；儲存庫與 Issues 回讀；授權文件、現況與工作紀錄；Docker 可用 |
| G1 原始輸入 | G0 | 壓縮檔與成員 SHA-256、版本、啟動入口、中文來源及權利分類 |
| G2 執行基線 | G1 | 固定 dosgolem 來源；正常入口到首個可操作畫面；缺服務與重播收據 |
| G3 輸出路徑 | G2 | 本作印字、清除、捲動與選單掛勾；原始定位與證據等級 |
| G4 譯文與字型 | G1、G3 | 術語表、繁中試譯、TSV 與字型覆蓋驗證；試譯供使用者確認 |
| G5 繁中接入 | G3、G4 | READY 規格、正常玩家路徑、原文／繁中同狀態比較、存讀檔無殘字 |
| G6 HD 原型 | G5 | 本作圖像來源、遮擋與清除證據；並列原型確認倍率與風格 |
| G7 HD 接入 | G6 定案 | 批次來源與輸出索引、失配回退、切換不改遊戲狀態、正常路徑驗證 |
| G8 交付 | 平台與範圍定案 | 乾淨輸入重建、封包與雜湊、可啟動性、存檔位置、未驗平台與權利邊界 |

## 3. 原始輸入與資料保護

| 根目錄檔案 | 目前用途判斷 | 尚待確認 |
|---|---|---|
| `The Dark Queen of Krynn (1992).zip` | 原版遊戲候選輸入 | 平台、版本、EXE、資料格式與啟動方式 |
| `珍181-克萊恩黑暗之后.rar` | 中文參考資料候選輸入 | 是否含手冊、掃描、攻略或遊戲檔；頁序、缺頁與來源 |
| `walkthrough/` | 使用者新增的中文攻略掃描 | 《軟體世界》47、48 期共 25 張；目前頁序見 `docs/re/002-walkthrough-source.md`，文字及遊戲對照尚未完成 |

- 保留原始壓縮檔，不覆寫。容器內唯讀掛載，解壓、OCR、雜湊與探針產物寫入 `workplace/`。
- `.gitignore` 在 Git 初始化前排除上述檔名、`workplace/`、`dist-all/`、存檔、憑證及本機快取。
  成員盤點後再補精確規則；提交前逐項檢查，不使用 `git add .`。
- 原版 EXE、資料、美術、音樂、掃描、手冊與攻略全文及其大量轉錄預設只留本機。
  私人儲存庫不等於取得散布權；不沿用前作「全文先入 private、以後清歷史」的例外。
- 使用者於2026-10-26明確要求README截圖直接在GitHub顯示，授權將README選定的展示圖
  保存於`docs/images/`並提交私人儲存庫。來源及雜湊見[展示圖清單](docs/images/manifest.json)。
  此範圍只涵蓋首頁展示，不擴張為上傳原版遊戲檔、完整素材包或轉公開。
- 譯文與衍生素材逐批記錄來源及權利分類。未確認可提交的批次留在 `workplace/`。
- 需要原版的測試缺檔時明確略過，不用自製替代資料冒充原版驗證。
- 前作、dosgolem 與 `~/.claude/` 都是唯讀參考，不修改、不搬移、不清理其中的資料。

## 4. 參考來源與知識路由

每次開工、兩輪同類失敗、形成完成結論、建立文件或目錄前，核對
`/home/anr2/.codex/knowledge-base/knowledge-router.md`，說明命中項目與實際載入入口。
只讀本次任務入口及直接需要的 reference，不掃整個知識庫。

| 來源 | 可沿用的方法 | 必須在本作重驗 |
|---|---|---|
| `/home/anr2/cht/golden_box/death_knight_of_krynn/AGENTS.md`、`CONTEXT.md`，再依需求讀 `docs/spec/`、`docs/re/`、`tools/` | 輸出覆繪、語意隔離、字型管線、完整街景與戰鬥 HD 分層、收據與封包方法 | 位址、bytes、畫面模式、繪圖來源、地圖、遮擋、素材數量、完成狀態 |
| `/home/anr2/cht/golden_box/champions_of_krynn/AGENTS.md`、`CONTEXT.md`，再依需求讀規格與工具 | 同系列移植時逐項重驗、術語對齊、TSV、手札引用、正常玩家路徑抽樣 | 本作事件、查驗題、手札數量、資料形狀、字型與操作定案 |
| `/home/anr2/cht/dosgolem/README.md`、`CLAUDE.md`、`docs/spec/006-layering.md` | 能力矩陣、`cmd/probe`、分層與 Docker 入口 `tools/go.sh` | 本作 binary 是否可執行與實際缺服務 |

前作 `AGENTS.md` 與較新現況可能不同。以目前程式、較新決策與可重現收據核對，不從舊文件
推定遠端可見性或分支布局。本次已見幽靈騎士的公開說明與 `CONTEXT.md` 私人狀態不一致；
遠端狀態須在有權限的主機另行回讀。

| 觸發情境 | 必讀入口 |
|---|---|
| 直接繪圖替換、事件預算與矩形批次 | 使用者指定 `/home/anr2/cht/mm3/docs/re/direct-render-methodology.md`；本作實作與界線以[規格 005](docs/spec/005-render-owner.md)為準，不移植 MM3 的位址或驗收結論 |
| 中文化與逆向工作 | `/home/anr2/.codex/skills/reverse-engineer-retro-game-remake/SKILL.md`；只採適用方法，不擴張為重寫遊戲 |
| 翻譯顯示與語意隔離 | `/home/anr2/.codex/knowledge-base/local/localization-display-semantic-isolation.md` |
| IDA Pro 9.4、`.i64`、overlay 與交叉參照 | `/home/anr2/.codex/skills/use-ida-pro-9-4/SKILL.md`，再依其入口讀對應工具鏈規範 |
| 中文版面與 Gold Box 畫面比較 | `/home/anr2/.codex/skills/research-pc98-golden-box-ui/SKILL.md`；PC-98 是參考，不預設本作使用其布局 |
| 新文件或研究目錄 | `/home/anr2/.codex/knowledge-base/local/project-document-responsibilities.md` |
| README 圖文與圖庫重建 | `/home/anr2/.codex/knowledge-base/local/retro-remake-readme-standard.md`；本作入口 [研究 006](docs/re/006-readme-gallery.md)，使用 `bash tools/readme-gallery.sh readme-gallery-新的名稱`，需既有合法原版與本機試繪，輸出本機 HTML，不代表正式遊戲或全量 HD |
| 授權文件 | `/home/anr2/.codex/knowledge-base/local/rrsal-1.0.md`，使用 RRSAL-1.0；第三方元件保留各自授權 |
| 正式版號與交付目錄 | `/home/anr2/.codex/knowledge-base/local/retro-remake-release-versioning.md`、`retro-remake-dist-all-output.md` |
| HD 原型或其他共同決策 | `/home/anr2/.codex/skills/grill-me/SKILL.md`、`/home/anr2/.codex/skills/grilling/SKILL.md` |

## 5. 執行器與呈現層邊界

- 使用者明確要求消除原版與 HD 的重複繪製。已接管命令須在原版像素生成／搬移迴圈前轉交
  自有繪圖層，跳過對應原版繪圖；未接管命令只走原版一次。契約、目前缺口與入口見
  [規格 005](docs/spec/005-render-owner.md)，候選入口為 `tools/player_render_owner.go`、`tools/player_owned_drivers.go` 與 `tools/player_scene_backend.go`。
  直接迴圈替換須補齊機器效果與虛擬時間，未驗證研究建置不得走正式啟動。
  完整原版繪圖留在背景再合成中文／HD，只算過渡方案，不能宣稱已達成單次繪製。
- 跳過繪圖前須證實函式副作用、返回值、暫存器／旗標契約，以及遊戲是否讀回顯存。
  邏輯所需的相容資料由接管層維護；不以每幀完整原版光柵化當作長期相容方式。
- 以 dosgolem 執行原版、攔截已證實的顯示輸出作為前作經驗起點。正式技術規格須先通過本作
  啟動與掛勾驗證；不可因同屬 Gold Box 就宣稱相容。
- 原版 EXE、資料、規則、亂數、條件比較、檔名、腳本鍵值與存檔語意保持原樣。
  中文與 HD 僅作用於呈現層，不把譯文寫回遊戲記憶體作判定。
- 遊戲專屬位址、重播、圖像與文字掛勾屬 adapter；CPU、DOS、BIOS、VGA、輸入與音訊
  屬通用層。分層依 dosgolem `docs/spec/006-layering.md`。
- 開發使用本專案內的隔離副本，先核對前作現行來源與通用修正，再固定 commit、Go 版本與
  Docker image ID。遊戲短名、正式來源保存位置與分支布局尚未定案，不照搬歷史分支。
- Go 的 `internal/` 限制須由實際依賴核對；不要先建立無法編譯的外部 adapter module。
- dosgolem 是原版行為、畫面、輸入及虛擬時間的主要執行器，正式收據由它重生。
  DOSBox／DOSBox-X 僅補足與診斷缺口，標為輔助基準，不冒充 dosgolem 收據。

## 6. 繁中與 HD 契約

- 英文原文、來源識別與呼叫位置用於辨識輸出。譯文不得參與比較、資源查找、檔名或存檔。
  共用字串函式須盤點顯示與語意呼叫者，不在共用出口無條件翻譯。
- 使用者要求提早攔截，避免英文先出現再閃爍切成中文。追查文字繪製前的完整字串與清除事件，
  以連續畫格驗證頁面、捲動、反白與返回；靜態截圖不能單獨證明無閃爍。
- 玩家可見譯文採 UTF-8 TSV 為唯一正式來源。程式引用穩定 key；檢查唯一性、欄數、控制碼、
  placeholder、漏譯、孤兒 key、換行、顯示寬度與字型覆蓋。字型子集由正式 catalog 重建。
- `text/glossary.tsv` 建立時對照兩個前作同名檔。保留來源、異譯與選用理由；有衝突先核對
  本作語境，不無條件覆蓋。需輸入英文的謎題保留必要英文提示，不改原版答案判定。
- 使用者已確認首批 145 筆試譯的譯風，共通術語以前作優先；並明確指定武器、怪物及跨代人物
  須與《幽靈騎士》的現行譯文對齊。權威入口為該作 `text/glossary.tsv`、`text/name.zh-TW.tsv`
  與 `text/name-lexicon-five.tsv`，其次才用《克萊恩英豪》及本作手冊補缺。自動匹配僅產生待核對
  候選，歧義及異譯保留來源，不自動改動前作。使用者未要求重新訪談相同譯風。
- 繁中先試譯一批供使用者確認，再全量。字型先確認來源與授權，再以實際長句和 UI 驗證；
  不為塞入原英文單字格而把中文字縮到難以辨讀。
- 未辨識、歧義或失配的輸出保留原版並記錄缺口。前作的 Pascal 字串、文字視窗、水平選單
  與組句模板只是研究線索，尚非本作已證實路徑。
- HD 盤點涵蓋固定圖、戰鬥角色與地形、動畫、3D 牆面、室內外背景、天空與前後遮擋。
  有資產不代表已有執行畫面；未觀測來源與正常路徑分開計數。
- HD 批次保存來源檔、偏移、SHA-256、尺寸、色盤、透明色、構圖與規格編號；輸出保存
  對應 key、生成方式、版本及權利分類。沿[規格 004](docs/spec/004-hd-layer.md)接續既有試繪方向；三倍資產密度是內部貼圖尺寸，不限制視窗大小。實質更換畫風才另作共同決策，不重問視窗與 HD 是否綁定。
- HD 失配、素材撤除或遮擋未知時回退原版。呈現切換不得重啟遊戲、改亂數或重寫存檔。

## 7. 證據、規格與驗證

正式接入依序走：原版證據 → DRAFT → 證據審查 → READY → 實作 → 同狀態驗證 → CONFORMED。
未達 READY 的探針與原型不進正式路徑。實作發現缺口時退回研究或規格，不猜補。

- 每項研究記錄輸入檔名與 SHA-256、工具版本、位址空間、原始位址、bytes／交叉參照、
  可重播步驟與證據等級。等級使用「已證實、強推論、假說、未知」。
- 保留原始函式名、運算元與結構偏移，以註解或外部索引附加語意。前作定位只是假說，
  不把 IDA linear address、執行期 segment:offset 與檔案偏移混列成同一位址。
- 原文／繁中、原版／HD 比較固定資料、初始狀態、輸入與亂數條件。記錄種子及設定方式，
  不挑重擲結果；差異限於規格批准的呈現範圍，原版 CPU、記憶體、畫面緩衝與存檔另驗。
- 正常玩家路徑至少抽驗冷啟動、建角或載入、探索、對話、選單、戰鬥與存退讀。
  驗證捲動、反白、清除、返回、背景恢復及讀檔殘影；狀態注入不能取代正常路徑。
- 單元測試全綠只證明內部檢查通過。完成聲明限於本作收據覆蓋範圍，未驗項保留未知。
- 2026-10-26 使用者重新授權抽驗，取代前一日暫停抽驗的限制。沿用 `CONTEXT.md` 的有效證據，只補實際改動需要的函式對照與代表操作；既有英文閃爍、箭矢及存讀檔收據保留，不因解除限制就重跑全套。
- 證據足以接入玩家功能後停止深挖無關 helper。標準 DOS 硬體時序採公開規格與成熟模擬器
  契約，不為逐週期一致追查 driver、ISR 或 busy-wait。

## 8. Docker、GitHub 與主機衛生

- 分析、搜尋、解壓、OCR、轉檔、建置、測試、遊戲與 GUI 自動化均在 Docker 內執行。
  主機只做必要的 Docker、Git、工作樹檢查、檔案編輯及下述 GitHub 操作。
- 先沿用既有 image，核對 entrypoint 與工具版本。一次性容器使用 `--rm`、相稱的
  `--memory`、`--cpus`、`--pids-limit` 與外層逾時，預設 `--network none`。
- 掛載前確認來源存在且型態正確。原始資料唯讀，僅輸出與工作樹可寫；寫入容器指定
  `--user` 為目前 UID/GID，寫前檢查目標與輸出目錄擁有權，寫後抽查。
- 背景程序設 trap 與有界擁有程序。每批結束在容器內檢查
  `find <工作根> -user root -o -type d -name '*.md'`，並清理本次已無用途的容器。
  只修已確認的個別擁有權錯誤，不遞迴 chown 整個專案，不清其他專案資源。
- GitHub 儲存庫與 Issue 操作使用主機 `/home/anr2/.local/bin/gh`，第一次先做
  `gh auth status`。受 sandbox 或網路隔離影響時，須在允許的 host／unsandboxed 環境
  回讀；受限環境的失敗不等於主機憑證失效。不搬運憑證到容器，不用本機清單冒充遠端狀態。
- 平台拒絕 Docker、Git metadata 或主機權限時，記錄環境阻塞，繼續可安全完成的文件工作；
  不繞過唯讀目錄、不改用主機執行工作負載，也不把失敗歸成遊戲缺陷。
- 提交只列明確檔案，檢查 staged diff 與敏感資料。不得自行改寫歷史、刪遠端分支或轉公開。

## 9. 文件與目錄索引

本表同時是新文件的入口。以下除本檔外均按需建立，不代表目前已存在。
新增文件時同時更新此表或所屬子目錄索引，避免無入口文件。

| 路徑 | 唯一職責 |
|---|---|
| `AGENTS.md` | 協作規則與專案路由，即本檔 |
| `CONTEXT.md` | 有日期的唯一現況表、有效決策、工具鏈、限制與證據入口 |
| `WORKLOG.md` | 按時間追加操作、驗證、失敗分類、提交與 Docker 清理狀態 |
| `README.md` | 遊戲與專案介紹、穩定操作入口、現況摘要，不放逐輪歷程 |
| `docs/images/`、[展示圖清單](docs/images/manifest.json) | README在GitHub直接顯示的選定截圖及原版／HD總覽；清單記錄來源、雜湊與使用者授權範圍 |
| `docs/re/README.md`、`docs/re/` | 研究索引與可公開的最小證據；私人原始輸出留 `workplace/` |
| `docs/spec/README.md`、`docs/spec/` | 規格索引、狀態、依賴、驗收條件與 Issue 回鏈 |
| `text/`、`font/` | 經權利檢查的 TSV、術語、字型來源與重建規則；自有說明面板文案入口為 [manual-ui.zh-TW.tsv](text/manual-ui.zh-TW.tsv)，圖片內嵌文字由 [image-text.en.tsv](text/image-text.en.tsv) 與 [image-text.zh-TW.tsv](text/image-text.zh-TW.tsv) 成對保存。書籍正文仍留本機 |
| `tools/` | 可重現的 Docker、盤點、驗證與打包入口 |
| [圖片文字規格](docs/spec/005-render-owner.md#ready圖片文字的語言獨立替換)、[picture_text.go](tools/picture_text.go)、[picture_text_inputs.py](tools/picture_text_inputs.py) | 圖片文字的來源核對、繪製前底圖保存、Go文字安全框及獨立於HD的繁中替換；接入在[player_picture_text.go](tools/player_picture_text.go)，本機資料為正式入口的picture-text目錄 |
| [player.sh](tools/player.sh)、[規格 003](docs/spec/003-player-toolbar.md) | 中文整合與頂端工具列入口；`prepare`／`build`／`run`，來源只讀，字級、原框閱讀及工具列已定稿，HD與說明世界地圖已接入；目前數量與限制見CONTEXT |
| [規格 004](docs/spec/004-hd-layer.md)、[player_hd.go](tools/player_hd.go) | HD 素材契約、完整可見來源比對與獨立開關；主題放 `workplace/probe/player-current/hd/`，視窗大小不控制 HD |
| [規格 005](docs/spec/005-render-owner.md)、[研究 007](docs/re/007-render-ownership.md) | Go 命令畫布、交易及完整畫格提交；入口 `tools/player_render_owner.go`、`tools/player_owned_drivers.go`、`tools/render_scene_state.go`、`tools/player_scene_backend.go`。正式玩家不取原版整張 RGB；來源掛勾在規格目錄，不回寫原版。代表路徑零原版寫入與全場景覆蓋分開記錄 |
| [player_text_format.go](tools/player_text_format.go)、[規格005](docs/spec/005-render-owner.md#ready帶變數的完整顯示來源) | 正式TSV格式與原版實際輸出配對；保留數值、加值、未知姓名及檔名，不讀寫原版varargs或語意資料 |
| [player-sample.sh](tools/player-sample.sh)、[視窗驅動](tools/player_gui_probe.c)、[XTEST按鍵](tools/player_xtest_key.go)、[檢查器](tools/player_sample_check.py) | Docker內的正常介面代表抽驗；使用既有XGB／XTEST產生伺服器鍵盤事件，第二參數可選本機對照程式，來源與影像參考唯讀；結束後核畫格、控制與未完成交易，產生checks.json |
| [render-abi.sh](tools/render-abi.sh)、[player-sample.sh](tools/player-sample.sh) | 限定繪圖函式與正常玩家介面抽驗；前者可加 `gpu` 對照真實素材的 GPU／CPU 輸出，後者只送正常 X11 輸入。新目錄與收據皆留 `workplace/probe/`，範圍見規格 005 |
| `workplace/` | 唯一研究工作區，含隔離副本、解壓、掃描轉錄、快取與 HD 批次；不入 Git |
| `dist-all/` | 唯一正式交付根，建立前讀第 4 節交付契約；本機含原版產物不入 Git |
| [guide_atlas.py](tools/guide_atlas.py)、[攻略研究002](docs/re/002-walkthrough-source.md#2026-10-28諾里迪斯與陵墓五圖) | `bash tools/guide-map.sh atlas guide-新名稱 [註記JSON檔名]`依本機幾何重生圖稿，核來源與門線附著，不取掃描像素。註記限`guide-20261028/`內檔名；25圖依批次保存，正文及全部圖稿只留`workplace/`。這是紙本閱讀座標，未接正式攻略；紙色留白不表示可通行 |
| [guide_pdf_sources.py](tools/guide_pdf_sources.py)、[攻略研究002](docs/re/002-walkthrough-source.md#2026-10-28海岸四圖與來源交叉核對) | `bash tools/guide-map.sh source-images guide-新名稱`只接受固定SHA的本機SSI攻略PDF，無損取出32張JPEG供校圖。影像序號不是PDF頁碼，來源圖不得作為重繪成品或直接放入閱讀器 |
| GitHub Issues | 唯一可執行工作清單；現況必須由遠端回讀 |

不另建 `HANDOFF.md`、`REMAKE-PLAN.md` 或同義工作區。建立 `LICENSE` 前讀第 4 節授權入口，
自有部分使用 RRSAL-1.0；前作與 dosgolem 的程式碼保留其實際授權，不整包改掛本專案授權。

### 歷史重播紀錄的儲存

磁碟清理時可將大型歷史 `receipt.json` 無損封存為同目錄 `receipt.json.gz`。
原始資料、譯文、程式、字模、圖片、存檔、證據索引及目前工作批次保留。
封存前後逐檔核對原始內容 SHA-256，不改寫舊 evidence manifest 的歷史雜湊。

| 入口 | 職責 |
|---|---|
| [research-storage.sh](tools/research-storage.sh) | 離線 Docker 的 `list`、`verify`、`restore`、`pack` 與本專案 `cache` 入口 |
| [research_storage.py](tools/research_storage.py) | 串流壓縮、原始內容校驗、按邏輯路徑還原；不改遊戲或正式資料格式 |
| `workplace/probe/storage-index.json` | 唯一封存索引，保存原邏輯路徑、原始／壓縮雜湊、大小、權限及還原狀態 |

研究文件與舊程式中的原路徑保留為邏輯引用。取用缺少的歷史紀錄前，先執行：

```sh
bash tools/research-storage.sh list
bash tools/research-storage.sh restore workplace/probe/研究目錄/重播目錄/receipt.json
```

也可把 `restore` 的參數改成研究目錄，一次還原該目錄內的封存紀錄。
還原後原檔名、內容、權限及時間恢復，壓縮副本移除，才可執行既有稽核器或重播檢查。
`verify` 只證明封存的原始位元組完整，不等於重新執行 GUI 或遊戲驗收。
`pack` 依 [research_storage.py](tools/research_storage.py) 的 `KEEP` 名單保護目前批次及圖文來源，
僅選其他目錄至少 16 MiB 的 `receipt.json`；`cache` 只清本專案 `workplace/probe/gocache` 內容，保留目錄。

## 10. 共同決策與停止線

- 已確認的繁中優先與建立 GitHub 儲存庫授權不重複詢問。
- 普通「繼續」僅延續已展示並確認的範圍，不等於批准尚未展示的 HD 或發行選項。
- 先查檔案、bytes、工具與實驗可確認的事實。真正的產品取捨依第 4 節訪談技能，
  視覺與操作先展示可丟棄原型，每次只問最早阻塞的決定。
- 不把前作的作弊、多語、新配樂、全文攻略、素材公開或清歷史授權移植到本作。
- 收尾分開記錄「功能已完成」「原版證據未知」「可選美化」；只因歷史清單仍有舊項目，
  不重新開啟已完成工作。驗證與清理以最小充分證據收尾。

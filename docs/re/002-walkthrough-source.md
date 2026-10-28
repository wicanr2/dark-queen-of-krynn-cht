# 002：中文攻略來源

日期：2026-10-21。工作：[#6](https://github.com/wicanr2/dark-queen-of-krynn-cht/issues/6)。
使用者提供的目錄實際名稱是 `walkthrough/`。不更名；`walkthrought/` 是對話中的拼法。
兩個名稱均已加入 `.gitignore`，原始掃描及全文不入 Git。

現行正文見[十八章正文與首批十五圖](#2026-10-28十八章正文與首批十五圖)，新增圖稿見[海岸四圖](#2026-10-28海岸四圖與來源交叉核對)、[龍人洞穴](#2026-10-28龍人洞穴重繪)及[諾里迪斯與陵墓](#2026-10-28諾里迪斯與陵墓五圖)。較早樣張保留為研究歷史，不作目前完成數。

## 已證實的來源與頁序

| 來源 | 檔案 | 印刷頁碼 | 內容 |
|---|---|---|---|
| `軟體世界47期/` | `61.jpeg` 至 `68.jpeg`，8 張 | 60 至 67 | 《克萊恩黑暗之后》完全攻略上篇，署名 Steeler；含第 1 至 7 章 |
| `軟體世界48期/` | `59.jpeg` 至 `73.jpeg`，15 張 | 58 至 72 | 同名攻略下篇，同樣署名 Steeler；從第 7 章後續到第 18 章深淵 |
| `軟體世界48期/` | `43.jpeg`、`44.jpeg`，2 張 | 42、43 | 修改資料，含存檔欄位與數值表；與正常流程攻略分開分類 |

以上共 25 張 JPEG，9,797,077 bytes。兩段攻略的印刷頁碼各自連續，章節標題從 1 延續至 18。
這只證明已見掃描的頁序及章節覆蓋，不代表文字、地圖細節或原版流程已逐項核對。
檔名比印刷頁碼多 1，引用時同時保存兩者，不能把檔名直接當頁碼。
封面與冒險手冊的題名核對見 [001 輸入基線](001-input-baseline.md)。

## 重現與收據

以 [scan_inventory.py](../../tools/scan_inventory.py) 盤點唯讀來源，Pillow 11.3.0 產生接觸表。
容器：`sc-cht-hdtools:pillow11.3.0-r1`，非 root、停用網路。

- 逐檔路徑、bytes、SHA-256、尺寸與格式：`workplace/walkthrough/manifest.json`。
- manifest SHA-256：`d71f1911083b28de6e767dda614cdb48aa0736d16073cb3806054d1b9ef4a426`。
- 人工檢視：`workplace/walkthrough/sheet-1.jpg` 至 `sheet-3.jpg`，另檢視上篇首張原尺寸圖。
- 上篇首張 SHA-256：`e465c3f6482e31954e91fcc62e45624346ae409f40c987a1bd2135e2e7f5e3d8`。
- 下篇首張 SHA-256：`ed8ee5cafce155d80e7b9e4e25f9489f16556c0cbdfc766e921287b325b4a212`。
- 下篇末張 SHA-256：`3008466b1d2d5c44ca994c18af4605b956db5b9d8826363104a7a8778d41b348`。

## 使用界限

- 可用於核對本作地名、人物、章節與事件順序。選用譯名仍須對照原文及兩部前作術語表。
- 地圖上的位置、門與事件標記尚未與遊戲實際資料核對，暫不當作原版規則證據。
- 修改資料只列來源，不把修改值套入遊戲、測試狀態或存檔。
- 掃描含多欄細字與圖文混排。OCR 只能作草稿；必須保留頁碼、區塊位置及校對狀態。
- 使用者已確認內建手札、說明與獨立手動攻略閱讀頁。自動答案提示及地圖疊層尚未定案。
- 使用者另明確指定攻略地圖重新繪製。正文重新排版，地圖與繁中標註整合進閱讀頁；
  原始 PDF 與掃描只作校對來源，不以嵌入原頁交付。

## 攻略地圖重繪驗收

- 每張重繪圖保留來源期數、印刷頁碼、來源檔名與雜湊，方便逐項回查。
- 逐項校對通道連接、牆、門、樓梯、出入口、方向與事件標記；繁中圖例及標號須與正文一致。
- 原圖模糊或與實際遊戲不一致時，記錄待查處及證據，不猜補成已確認的路線。
- 圖文在閱讀頁的實際顯示尺寸須清楚可讀，長段正文與地圖須能對照。
- 閱讀頁必須使用重新排版的正文及重繪圖；放入 PDF、整頁掃描、裁切圖或單純放大原圖，
  都不算完成重繪。各張地圖仍待盤點、製作與驗證。

### 圖區初盤與首張重繪

已檢視 25 張掃描及接觸表，初盤 51 個圖區。計數單位為獨立分圖，同一區的不同樓層、
跨頁續圖及大陸圖分別計數，不能當作遊戲地圖數。圖名與各張幾何仍待校讀。
逐圖來源檔名、印刷頁碼及 SHA-256 保存於 `workplace/guide-map-index.json`，由
[index_guide_maps.py](../../tools/index_guide_maps.py) 合併人工圖區註記與原始掃描產生。
索引 SHA-256 為 `7b2b998ff08dd1bfc9862e0c16548d992acbb093cad0fe3d12b911a66785830f`。

| 期數 | 印刷頁碼 | 初盤圖區數 |
|---|---|---|
| 47 | 62、63、64、65、66、67 | 1、1、2、3、3、10 |
| 48 | 58、59、60、61、62、63 | 1、1、1、3、1、1 |
| 48 | 64、65、66、67、68、69 | 2、2、4、3、1、4 |
| 48 | 71、72 | 3、4 |

首張樣張為 Caergoth，來源 `軟體世界47期/63.jpeg`，印刷第 62 頁，SHA-256
`8012ada4d9fc9f763b28ea2e35f84de32f06a1681324445c14adab2aac8c293f`。
人工依原圖校讀可行走區、密林、樹牆、牆、瓦礫、不可通行區與 9 個門符號，再以獨立線段及
多邊形重繪。樣張座標採 14×17 的印刷格線近似，不是遊戲座標，也未證實遊戲地圖尺寸。

- 原圖 1 至 10 號共有 11 處標記，2 號標了兩處，原樣保留。
- 原頁只附 1、2、3、4、10 號說明。5 至 9 保留編號並顯示待查，不猜補用途。
- 原圖沒有方向箭頭，樣張不添加北箭頭。Caergoth 的正式繁中地名尚待術語對齊。
- 幾何與標記已對照來源初校，沒有獨立複核或遊戲逐格驗證，證據只到「依來源重繪」。
- 線條、色彩、字級與閱讀布局均未定版，沒有接入正式遊戲。

本機成果在 `workplace/caergoth-redraw/`：`map.svg` 是獨立向量，`map.png` 供檢視，
`reader.html` 是可縮放、拖曳及點選編號讀說明的可丟棄原型。SVG 沒有 `<image>` 元素，
不包含掃描像素。內嵌 OFL 字型供離線顯示，隨附 `FONT-LICENSE.txt`；原圖、衍生圖及正文
均只留本機，不入 Git。`receipt.json` 保存輸入、字型、工具及輸出雜湊。

### 重生與瀏覽器驗證

入口 [guide-map.sh](../../tools/guide-map.sh)，依序執行 `index`、`redraw`、`check`。
此入口只讀既有本機研究輸入，缺少掃描、人工註記或字型時停止，不下載或捏造替代輸入。
寫入 UID/GID 沿用目前使用者，網路關閉，容器有資源及時間限制，使用已存在且固定 ID 的工具。

```sh
bash tools/guide-map.sh index
bash tools/guide-map.sh redraw
bash tools/guide-map.sh check
```

[redraw_guide_map.py](../../tools/redraw_guide_map.py) 讀取 `workplace/caergoth-redraw.json`
的人工幾何與標記。這是研究輸入，尚非正式 schema。來源圖不掛入繪圖步驟。
Pillow 11.3.0 生成 PNG；字型沿用前作粉圓 2.1 與其 OFL，工具及來源雜湊同規格 001。

[check_map_reader.mjs](../../tools/check_map_reader.mjs) 在既有
`mcr.microsoft.com/playwright:v1.56.1-noble` 內以 Chromium DevTools pipe 驗證，沒有安裝新套件。
image ID 為 `sha256:f1e7e01021efd65dd1a2c56064be399f3e4de00fd021ac561325f2bfbb2b837a`，
Chromium `141.0.7390.37`。已通過中文字型、11 個標記、沒有點陣圖元素、鍵盤查閱、縮放、
真實指標拖曳及未知標記提示；截圖為 `browser.png`，收據為 `browser-receipt.json`。
操作檢查不證明原版地圖或事件正確，也不代表已完成遊戲內開啟與返回。

## OCR 工具與校對界限

`tools/docker/ocr.Dockerfile` 與同目錄 `ocr-runtime-versions.txt` 固定 111 個套件版本，
PaddleOCR 3.1.0、PaddleX 3.1.0、PaddlePaddle 3.1.1；`pip check` 通過。
乾淨重建的 image ID 為 `sha256:5625e878af8cce84fff9a7f63248fa38e6ed38dbf32d1be59a60e74519842ee2`。
實際使用 PP-OCRv5 mobile 偵測與辨識模型，單頁樣本無 OOM；較大的 server 模型曾觸及容器限制，
不能把失敗執行當作辨識結果。

入口是 [ocr-batch.sh](../../tools/ocr-batch.sh)，參數 `walkthrough` 處理本目錄，`manual` 處理
已拆頁的手冊。來源、模型快取皆唯讀、停用網路、每次 2 GiB／2 CPU，外層有逾時。
模型尚未下載時先以 [ocr_sample.py](../../tools/ocr_sample.py) 做一次明確允許網路的模型下載與
單頁品質探針；原始掃描只在容器內辨識，沒有送到遠端 OCR 服務。

批次輸出保存於 `workplace/paddle-walkthrough/`，包含：

- `provenance.json`：工具、image、套件版本及逐模型檔案 SHA-256。
- `manifest.json`：來源雜湊、進度、錯誤及輸出雜湊。
- 每張掃描的 JSON：原始辨識文字、信心分數及對應多邊形位置，全部標為未校對。

上篇首頁及手札第 1 則的單頁試驗已能辨識大部分文字，仍可見錯字、繁簡混用與多欄順序問題。
這些草稿不能直接進正式 TSV 或閱讀面板。實際批次完成數由 manifest 回讀，不以檔案存在推定完成。

本次攻略批次已完成：25／25 張、3,203 個辨識區塊、0 個執行錯誤。
逐頁輸出雜湊已逐一回驗；`oom`、`oom_kill` 皆為 0，峰值 1,010,225,152 bytes。
這是工具處理完成，沒有宣稱 3,203 個區塊內容皆正確。

- 完成 manifest SHA-256：`ccc16f8b16fe126fe542cb56262c9622b51f59d189ad0d77a97013996765e36c`。
- provenance SHA-256：`a43b72e71ee8922ec85e2ce94ba7a6116c757534c2a091586c98a1cfeffabb26`。

## 手動閱讀頁原型

使用者已選擇獨立、手動開啟的攻略閱讀頁。首次試排由
[reader_preview.py](../../tools/reader_preview.py) 讀取本機節錄及字型，輸出
`workplace/reader-preview.png`。試排將旅行手札、說明書與攻略並列，攻略保留章節目錄、
印刷頁碼、作者及地圖入口；這些按鈕目前只是圖面，尚未接入遊戲。
使用者澄清後，原型中的「查看原頁」已改為「查看地圖」，正式內容依上述重繪驗收。

原型尺寸為 960×600，正文暫用 20px 粉圓。這是閱讀頁試排，尚非正式版面或字級決定，
也不改變角色管理選單已確認的 20px 契約。只試排上篇首頁節錄，未驗證全文、長章節與地圖。
私有輸入 `workplace/reader-sample.json` 與生成圖皆不入 Git；正式資料須先校對。

重現時使用 `sc-cht-hdtools:pillow11.3.0-r1`，停用網路，以非 root 執行：

```text
python3 tools/reader_preview.py <本機節錄 JSON> <已授權字型 TTF> <輸出 PNG>
```

JSON 欄位為 `title`、`source` 及字串陣列 `paragraphs`。本輪唯讀使用前作的
`font/jf-openhuninn-2.1.ttf`，來源與授權沿用規格 001 的字型記錄，沒有複製進 Git。

## 2026-10-27：從GEO原始資料重繪的DRAFT

圖片中文與介面材質已接入20dae32後，攻略工作接續於本機`workplace/probe/guide-20261027/`。目前只做唯讀資料擷取及向量草稿，沒有啟用攻略按鈕，也沒有把掃描圖嵌入閱讀頁。

GEO.GLB SHA-256為`fd8435610b936bdbce997182ddef9ff0bc9e662a760bac2542d4cad8c697a2d1`。HLIB有一筆目錄及二十筆地圖資料，每筆均滿足八位元組標頭加四份高乘寬的byte平面；首byte為高、次byte為寬，尺寸10×10至39×20等，不能固定為16×16。來源偏移、完整區塊與平面起點保存`geo-inventory.json`。尺寸與位元組範圍已證實，牆方向及門／事件語意仍須來源對照，不因長度正確即稱原版引擎語意已驗。

外部入口為[Gold Box Companion作者的DQK格式說明](https://forums.goldbox.games/index.php?topic=981.105)及[Gold Box Explorer原始碼](https://github.com/bsimser/Gold-Box-Explorer/tree/eac30abaa6ee66aea6f5d65ebe6d676b10015a8f/src/Common/Plugins/GeoDax)。後者固定commit`eac30abaa6ee66aea6f5d65ebe6d676b10015a8f`，完整相關原始碼與MIT授權保存在本機upstream-format，逐檔雜湊見upstream-format-source.json。舊DAX解碼器固定16×16及兩byte標頭，不能直接當成本作GLB解碼器。只參考欄位格式，未把第三方實作或來源資料加入Git。

原生目錄標籤46／47與62／63分別指向不同區塊。首版草稿將標籤右移一bit後發生重名，被既有檔守衛阻擋；保留首版輸出，後版以完整raw tag作定位，不推定低bit或遊戲地圖ID語意。二十張SVG／PNG草稿與保留的逐方向資料在geo-decoded-draft.json，SVG由線段與矩形建立，無image元素；目前未加完整繁中名稱及事件標記。

紙本的五十一個圖區含樓層及分圖，與二十筆原生資料的對應仍在校讀。初版將所有非零門旗標畫成門符號，包含沒有可見壁面的邊界，不能當成已校對攻略圖。門／開口圖符與實際壁面、樓層、出入口及紙本標記對齊前維持DRAFT，不進正式閱讀頁；不修改原始地圖、存檔或遊戲通行判定。

可重現入口為[guide_geo.py](../../tools/guide_geo.py)及`bash tools/guide-map.sh geometry guide-新的名稱`。
輸出位於`workplace/probe/`，包含二十張SVG、原始四平面欄位及收據；SVG線段只表示非零美術欄位，
不把任何旗標直接畫成門。二十筆、47,768個方向欄位可無損重編回原位元組；零高度、尺寸不符、
重複raw tag及重複區塊四項變造皆拒絕。`guide-geo-fields-20261027/receipt.json` SHA-256
`8ada13f933c6870d06d55261e15157b0e04457bf7051c9a4044e540de892c1f7`。這是資料及研究圖驗證，沒有遊戲通行語意或原版逐格對拍聲明。

## 2026-10-27：冒險手冊世界地圖接入

手冊第2頁來源`workplace/manual-ocr/Image047-right.png`，SHA-256
`dd3c9c5a956a1850755b0631444db982a9ff3e7f7aa07555eaa662299fba3587`。
此頁與攻略泰勒達斯大陸圖同為地形及地名參照，與GEO逐格地圖分開。
已將原生`BIGPIC.1.1`及`BIGPIC.2.1`的兩張304×120地形接合，縮為24色輪廓後重新繪製，
加上13地名、8區域、引線及來源說明。地形與標籤都只作閱讀示意，不表示通行、任務或角色位置。
一般地名沿前作術語及本作正式譯表；新名稱的來源及採用理由留在`world-map-layout.json`，不改前作。

- 工具：[manual_world_map.py](../../tools/manual_world_map.py)的`geometry`／`render`，
  與`bash tools/guide-map.sh world-map guide-新的名稱`。來源、字型及人工標籤唯讀，輸出留本機。
  既有OCR image內的OpenCV 4.10.0／NumPy 1.26.4產生輪廓，Pillow 11.3.0容器排版；沒有新增image或套件。
- 現行私有資料：`guide-20261027/world-map-layout.json`、`world-map.zh-TW.tsv`、`world-terrain.json`及`world-map-r2/`。
  第一張結果出現輪廓中心取樣造成的紙色細縫，第二張補足邊界後接受，不做第三輪美化。
  SVG含獨立路徑與已授權字型，不含image元素；PNG為閱讀器取樣資源，沒有掃描或PDF像素。
- 接入：[manual_map_inputs.py](../../tools/manual_map_inputs.py)只換冒險手冊第2頁，189個其他項目、舊譯文及字模保持。
  [ui_manual_reader.go](../../tools/ui_manual_reader.go)核對檔名、雜湊、尺寸、內容框與不透明度，
  共用[圖文取樣元件](../../tools/ui_journal_illustrations.go)，圖稿與正文只留本機。
- 967e2445正常冷啟動後進入角色管理、F6換冊開圖，完成全圖、原尺寸、兩倍、平移、Home復位、Esc回目錄及遊戲。
  十一次閱讀事件保持同一原版步數；五張圖區由獨立座標抽驗，復位與初始全圖相同。
  五張既有介面基準差異0、guest寫入0。入口`player-sample.sh`新增可選第三參數`manual-map`，原抽驗模式保持。
  本輪沒有冒險、結局或逐一圖片引用驗收。
- `guide-world-map-rebuild-20261027/`由公開工具入口獨立重建，SVG與PNG皆逐位元組相同。
  正式1487項HD保持，新增兩份閱讀輸入，共38份profile資料；49個其他非HD檔案保持。
  正式程式與原資料備份在`player-prior-20261027-manual-map/`，安裝與總證據在`guide-20261027/`。

世界地圖PNG SHA-256為`d64ecbeff7ce6a94aac5dade5ea5e27cea4cf5fde90399bca119068074192d51`；
總證據`manual-map-final-evidence.json` SHA-256為`624a0d1ed152cb6b4b86989961d4fca224e3e5e15eef85e3988070ffc3de05e9`。
這完成說明書的世界地圖缺圖，攻略全文、GEO分圖與事件標記仍待校讀，攻略工具列保持停用。

## 2026-10-28：收尾正文校讀

現行工作在`workplace/probe/guide-20261028/`。已對照47期印刷62、63頁，重新排版
帕蘭薩斯、凱爾高斯與龍人洞穴三章，保存來源SHA-256及本作／前作術語表雜湊。
六個標題與正文鍵共1,144字元，連枷、解除法術、低語蜘蛛、飛彈項鍊等沿前作或本作現行術語；
原圖未附說明的5至9號不猜補。正文屬來源校讀，地圖未齊，沒有接入正式閱讀器。

來源與限制在`chapters-01-03-review.json`，SHA-256
`851d608487b136b8fb436f654875672e57964116ac61e675a743a7d9408ee3cf`。
`detected-map-boxes*.json`與接觸表只供尋找圖區，不能將自動框選或裁切掃描當作重繪。
原始GEO欄位語意未知不阻擋依紙本校讀，但正式通道、門、樓層與標記仍須逐項有來源，不能猜補。

## 2026-10-28：十八章正文與首批十五圖

本機入口為`workplace/probe/guide-20261028/`。`guide.zh-TW.tsv`已按18章重排，
另有攻略導讀與戰鬥法術提示，共40鍵、12573字元、292段圖號說明。正文逐頁對照
第47期8頁及第48期15頁，兩頁修改資料排除。這是重新敘寫的手動攻略，沒有將多欄OCR
直接送入閱讀器，也沒有把作者的戰鬥建議當成已對拍的遊戲規則。

| 證據 | 路徑與範圍 |
|---|---|
| 正文 | `guide.zh-TW.tsv`，SHA-256 `7c40d160151125201ff8e73fcfb211a3a456d794d9320f77ef9b30e665fe2be3` |
| 校讀紀錄 | `guide-text-review.json`，SHA-256 `f60df40facaf9e5c6a8998fe448f0b7a13d05a92a45cc1c09a6db0c8d198f2a6`；含章節對來源頁、23頁雜湊、術語出處及舊稿勘誤 |
| 人工幾何 | `atlas-annotations.json`；燈塔地下二層、地下一層與1至11層，加深淵兩圖，共15張及92標記 |
| 重繪輸出 | `workplace/probe/guide-atlas-20261028-final/`；每圖各有1100×1040 PNG與獨立SVG，附字型授權及來源／輸出收據 |
| 圖稿檢查 | `guide-20261028/atlas-review.json`，SHA-256 `366ccb6a53e475b09f9ec4ca811832fca2ba878f244f8fbf8fa03219477c4249` |

術語沿本作正式表及前作來源。物品中的20支箭+4保留數量與加值；李歐克斯、連枷、
解除法術等沿《幽靈騎士》。本作人物與通行證不另創異譯。原攻略的Malsi Hi、Cold-en Key
分別對齊原版Malgi Hi與Golden Key。古朗思卡依原版女性稱謂。

### 舊稿勘誤

首三章原檔及其收據保持，較新校讀在合併正文修正以下三處，不回寫舊證據。

- 洞穴5號只寫藏有兵器，沒有指明長弓，改成武器。
- 洞穴22號明寫解除陷阱後蜘蛛從東邊出現，不支持先前離洞重生的說法。
- 洞穴24號是藍龍與黑龍，先前將其中之一寫成龍人，已改正。

對照細節保存`source-detail-caves22*.png`，只作本機校讀，不嵌入成品。

### 圖稿重生與證據界線

[guide_atlas.py](../../tools/guide_atlas.py)只用人工多邊形、線段、門、坑洞、樓梯位置及標記
繪製。來源掃描只核對SHA-256與檔頭尺寸，不提供像素給繪圖函式；SVG無image元素。
門必須附著在相同方向的牆線或邊界，錯位便停止。所有文字均檢查畫布邊界。

```sh
bash tools/guide-map.sh atlas guide-atlas-新的名稱
```

入口沿既有Pillow 11.3.0 image、粉圓2.1與OFL。離線、非root、768 MiB、1 CPU、
64程序及60秒逾時；缺少本機人工註記、掃描或字型時停止。完整正文、圖稿及私人收據
依原權利分類只留本機，不入Git。

第一輪對照15圖接觸表，修正缺線、地下一層50號外輪廓、10層門位及牢籠外圍瓦礫。
第二輪抽看牢籠、地下一層、第4與10層，接受作紙本閱讀示意，不再開美化輪次。
全部15圖的PNG尺寸、輸出雜湊、92個標記、SVG無嵌圖及文字邊界通過；複雜的10層
獨立重建PNG／SVG逐位元組相同。

幾何屬「依紙本重繪的近似閱讀座標」，不能當成原生GEO或可行走性證據。樓梯保留
中性位置符號，沒有猜上／下方向；原圖未附說明的標記只留編號。這些圖沒有自動定位、
遊戲內疊層或任務判定。其餘圖集與正式閱讀器尚未接妥，攻略按鈕維持停用。
下一批從希茲登、海底通道及遺跡接續，不重做已接受的燈塔畫風，也不深挖無關GEO欄位。

## 2026-10-28：海岸四圖與來源交叉核對

新增希茲登漁村、諾里迪斯海底通道、瑟拉諾斯特水下及空氣室，共4張與27標記。
來源為第47期印刷64至66頁。遺跡掃描左側陰影以[SSI原版攻略](https://dlsaga.com/wp-content/uploads/2022/11/ks_darkqueen_cluebook_pdf.pdf)
第10頁交叉核對，補正通道、13／23號與6個窗戶，並分開一般門、堅固門及爪痕門。
SSI檔案SHA-256為`b866541812647947a34eed7a636d8d3c7ed50b5926f576258a3dc72bdb38170d`，
32個PDF頁面；PDF第6個零起算頁含印刷9／10頁。頁碼、印刷頁碼及圖片序號分開保存。

| 證據 | 本機位置與範圍 |
|---|---|
| 人工幾何 | `guide-20261028/atlas-coast-annotations.json`，SHA-256 `c23c3196bc2c81c7d7758030aa5625d83672dafea756bdedfafdd376633b5747`；保留中文主來源與SSI交叉來源 |
| 圖稿 | `guide-atlas-coast-20261028-final/`；每張1100×1040 PNG、獨立SVG與字型授權 |
| 校圖收據 | `guide-20261028/coast-review.json`，SHA-256 `f05a2303579507f8f732e3e6e76c20f286aa2525cfd73e0d3869a2fce22ffedf`；第二輪接受，不再美化 |
| 原始參考 | `guide-20261028/ssi-cluebook-source.pdf`及來源JSON；完整PDF、擷取JPEG及校圖裁切均只留本機 |

重生入口允許指定同一工作批次內的註記檔，缺少任何來源或SHA失配便停止：

```sh
bash tools/guide-map.sh atlas guide-atlas-新名稱 atlas-coast-annotations.json
bash tools/guide-map.sh source-images guide-ssi-source-images-新名稱
```

[guide_pdf_sources.py](../../tools/guide_pdf_sources.py)只接受上述固定SHA的PDF及已盤點的
直接JPEG串流。保存原始串流位元組、零起算檔案偏移、尺寸與SHA，不實作通用PDF解析器。
32張JPEG共7,373,374 bytes，已逐張對回PDF原始區間。影像串流名稱重複，
`image-00.jpg`等名稱只表示串流順序；沒有推定為PDF頁碼，manifest的PDF頁序欄保持空值。
輸出只供人工校圖，禁止把這些來源圖當作重繪成品或閱讀器圖片。

本輪發現舊Pillow r1已不存在，沿用主機既有r2，未新增image或OCR套件。
使用Python3.13.15、Pillow11.3.0，image ID為
`b050fc7c49003ea6eecbbe0fc93b465b6869daf550c3284d5039e5e87517e831`。
新工具下首批15張PNG／SVG逐位元組保持；新4張來源、27標記、門線附著、
文字邊界、PNG尺寸、SVG無image元素及輸出SHA均通過。空氣室6窗與13／23號另核對。

目前共19張、119標記，不包含較早的凱爾高斯原型。這是紙本閱讀示意圖，
沒有原生GEO通行或全場景聲明。攻略按鈕仍因其餘圖集及閱讀器未齊而停用；
播放器、38份正式資料、1487項HD與已接受正文保持，不重跑舊遊戲父批。

## 2026-10-28：龍人洞穴重繪

依第47期印刷63頁與SSI攻略印刷第6頁重繪龍人洞穴，保存1至25號，
其中9號四處、12號兩處，共29標記。6號為瓦礫，5號為密門，不混用圖例。
SSI來源為已校驗PDF中的`image-04.jpg`，印刷頁碼由圖面直接校讀；
沒有從串流序號推定PDF頁碼，註記的PDF頁序保持空值。

| 證據 | 本機位置與範圍 |
|---|---|
| 人工幾何 | `guide-20261028/atlas-caves-annotations.json`，SHA-256 `8ff8c013106145093f8c45e7b2d6dcee1756a96f80f6ae53b73cb2c66a3cbf4d`；保留兩份來源與擷取圖SHA |
| 圖稿 | `guide-atlas-caves-20261028-final/draconian-caves/`的PNG及SVG，附字型授權；第二輪接受 |
| 校圖收據 | `guide-20261028/caves-review.json`，SHA-256 `781133a95ed1c62016ed91d53598f36c1e5d1953ae1868659067b28aae883459` |
| 幾何重生 | 同批`caves_annotations.py`；人工矩形聯集只產生閱讀輪廓與空洞，不解讀遊戲GEO |

```sh
bash tools/guide-map.sh atlas guide-atlas-caves-新名稱 atlas-caves-annotations.json
```

初稿檢視後補正9號豎道與主洞的連接、19號房側通道、東北內牆及6號瓦礫。
製圖聯集在只碰角的邊界循線分開處理，不憑角點增加通道；輪廓內的空洞由獨立向量
留空，沒有用背景圖遮蓋。第二輪接受閱讀示意，不再追加美化。

25種圖號、29標記、來源、門線附著、PNG尺寸、文字邊界及SVG無image元素均通過。
完整洞穴PNG／SVG獨立重建相同；新增空洞支援後，燈塔與遺跡代表圖逐位元組保持。
紙圖座標仍為近似，沒有原生逐格通行、規則或正常玩家路徑聲明。
累計20圖、148標記，其餘圖集與正式攻略閱讀器待補，按鈕仍停用。

播放器、README圖庫及封存入口一併改沿已存在的Pillow r2固定ID，恢復必要工具依賴。
只核語法及現有封存清單讀取，不重新建置遊戲、重跑HD或重製已接受圖稿。

## 2026-10-28：諾里迪斯與陵墓五圖

諾里迪斯與宮殿新增44標記、152個門／拱門符號。陵墓四圖新增73標記，
涵蓋入口、列柱大廳、寶箱、傳送通道、表演場與地下墓穴。主來源為第47期印刷64頁、
第48期印刷60／61頁，交叉來源為SSI印刷8及22至25頁；每張保存來源與JPEG雜湊。

| 證據 | 本機位置 |
|---|---|
| 幾何 | `guide-20261028/atlas-city-final-annotations.json`、`atlas-tombs-annotations.json` |
| 諾里迪斯圖稿 | `guide-atlas-city-20261028-accepted/` |
| 陵墓四圖 | `guide-atlas-tombs-20261028-current/` |
| 校對與輸出 | `guide-20261028/city-tombs-review.json`，SHA-256 `8f52e98edb4287a9e5f285113922ec3696604840411fc980fae2096e00f63654` |

直線候選由來源中的長水平／垂直線取得，排除文字、圖例與圖號引線，另校讀門、
傳送點、樓梯與標記。封閉長方門框只作一般門候選，其他圖符人工指定；
未採用跨頁自動分類結果。繪圖步驟只讀幾何，不拿來源像素、字形描邊或PDF頁面作成品。
重生入口沿`guide-map.sh atlas`，指定上述註記檔名即可。

密集分圖採無外框的紙色底，牆線與符號仍各自繪製。留白不表示可通行，
圖號引線也不當作牆。51號損壞傳送點保留編號，沒有有效傳送符號。
城市第二輪修正南側門位與宮殿門；陵墓最多兩輪接受，再將標題對齊正文的「陵墓」。
標題修正後圖區保持，沒有新增美化輪次。

五圖PNG尺寸、來源、門線、117標記、SVG無image及輸出SHA通過；城市與一張陵墓
獨立重建相同，舊希茲登代表圖保持。完整幾何、圖稿、來源及重生用的私人腳本留本機，
收據記錄逐檔SHA。累計25圖、265標記，未接正式攻略入口，播放器及18章正文保持。

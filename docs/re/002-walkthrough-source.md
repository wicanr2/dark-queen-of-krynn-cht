# 002：中文攻略來源

日期：2026-10-21。工作：[#6](https://github.com/wicanr2/dark-queen-of-krynn-cht/issues/6)。
使用者提供的目錄實際名稱是 `walkthrough/`。不更名；`walkthrought/` 是對話中的拼法。
兩個名稱均已加入 `.gitignore`，原始掃描及全文不入 Git。

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

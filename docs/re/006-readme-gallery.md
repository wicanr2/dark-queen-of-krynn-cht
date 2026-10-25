# README 圖文與原版圖庫

對應使用者要求的故事背景、怪物／人物原版與 HD 對照、遊戲截圖及遊戲內地圖。
本頁只保存研究方法與限制；專案介紹仍以 [README](../../README.md) 為入口。
全部圖像、原版輸出及來源索引留在本機 `workplace/probe/readme-gallery-20261024/`。

## 原始輸入與格式

| 原版檔案 | SHA-256 |
|---|---|
| `DISK2/CPIC.TLB` | `47194884dfb1c0ce9c6b382bc551e0cd96ecbdea77b2ebdd3992f321b00ad4c1` |
| `DISK3/CBODY.TLB` | `8d825123a169e5d96cd3640b991f602086db4b1aaf95afd16d8177d1b44bbf40` |
| `DISK2/PICA.TLB` | `b3340ffd0475f1a736479095d842a88d4f387d30b3d304fa9642b3218694dc2c` |
| `DISK2/PICB.TLB` | `c1f6853c42e021761e289bb960dd7ffbd91252f9393cf910e92eccabfb05e4a0` |
| `DISK2/PICC.TLB` | `67e5c8cd549d1c108fa25d206ad0e182c701564f8fc4422a9a8b1a391fbcecf4` |
| `DISK2/WILDCOM.TLB` | `f57a90cabeb42d56a9a399f60a64ff76a79bcf4b76ef7ffdc8805e53116dfb49` |

[tlb_gallery.py](../../tools/tlb_gallery.py) 解析 HLIB 目錄與 TILE 圖像，位址均為檔案位移。
格式參考 [Gold Box Explorer 固定來源](https://github.com/bsimser/Gold-Box-Explorer/blob/eac30abaa6ee66aea6f5d65ebe6d676b10015a8f/src/Common/Plugins/Tbl/FruaTlbFile.cs)，
保留 [MIT 聲明](../../tools/LICENSE-Gold-Box-Explorer.txt)。外部來源副本及固定 commit 存於本機研究目錄。

- 已解碼方法 16、17、18、21；包含四平面資料、遮罩與壓縮列。
- 360 張輸出為 CPIC 190、CBODY 98、PICA 23、PICB 21、PICC 28。
- 另有 52 個區塊未解碼，方法 23 為 48 個，方法 25 為四個；不推定其完整動畫語意。
- 原版目錄的重複 ID、多個 ID 指向同一圖格均保留。190 格不是 190 種怪物。
- 色盤合併實際 WILDCOM、CBODY 與各圖庫的局部範圍，再換算原版六位元 DAC。
  未取得色號不補黑色。這個靜態色盤不能證明所有場景的循環、閃爍及動畫顏色。

`tlb-index.json` 保存每個原始區塊的檔案位移、雜湊、尺寸、繪圖方法、色盤與圖像雜湊。
方法 23、25 明列未知。人物候選只列 31 張第一圖格，身分尚未全量對回，不憑外觀命名。

## 已證實的圖格與未知範圍

藍龍 `CPIC..6`、目錄 ID 82、48×48，與首戰正常續行 `control-r1/wait-4.idx` 在原版座標
32,104 的 1,653 個非透明像素一致。輸出圖格的每個可見像素均用該原版畫面的實際色盤核對。
原版來源在 `workplace/probe/combat-rounds-20261024/`，由 dosgolem 產生；
執行器來源 `f79eab6db8c64a524a06535e53e5d32b0bbcf7c8`，Go 1.24.13。
此項只證實這一張圖格及其可見位置，不外推全圖庫對拍或完整怪物身分表。

兩張 HD 試繪使用內建 imagegen，以藍龍及 `PICA.7.1` 頭像為參考。
藍龍保留初版與留白調整版，首頁展示後者；人物圖仍保留來源編號。
生成器未提供模型版號，不填入推測名稱。原始生成 PNG 與專案副本分開保存，
`preview-index.json` 記錄輸出雜湊、原版來源、生成工具及「未接入」狀態。
本批沒有決定全量 HD 風格、倍率、動畫或正式資產規格。

## 展示來源與重建

[readme-gallery.sh](../../tools/readme-gallery.sh) 在既有離線 Docker image 中重新解碼，
再由 [readme_preview.py](../../tools/readme_preview.py) 產生 `README.md` 與 `README.html`。
image 固定為 `sha256:44d0742ca1061bcd453440cdce925afa31c5324e115fca1334da0e364f0e2c48`，
執行時的 Python、Pillow 版本與三個工具雜湊存入 `preview-index.json`。
來源唯讀，輸出使用目前 UID/GID。新目錄名稱以 `readme-gallery-` 開頭，既有目錄不覆寫。

| 展示 | 來源與限制 |
|---|---|
| 單支箭裝備 | `ammo-boundaries-20261024/single-en/zh-r1`，`single-ready-one`；使用該批完整畫格檢查收據 |
| 毒氣回報與敗北三行 | `combat-rounds-20261024/p3-en/zh-r2`、`p9-en/zh-r2`；只展示兩條已有完整畫格檢查的分段，不宣稱整場勝利或本批其他路徑通過 |
| 森林與區域圖 | `passage-chain-camp-20261024/area-observe-r1`；原版正常探索，未套用繁中或 HD |
| 凱爾高斯攻略圖 | `workplace/caergoth-redraw/map.png`；另行繪製的繁中攻略原型，尚未接入遊戲地圖 |

遊戲截圖從實際 GPU 畫格選取，不重新描字；預覽只複製 PNG，不修改來源。
原版及繁中使用相同截點，索引保存原收據雜湊、CPU 步數、記憶體與色號畫面雜湊。
頭像候選與完整已解圖庫分開，攻略圖與遊戲內區域圖分開。
首頁故事取自《冒險手冊》「故事開始」的將軍來信，譯名沿《幽靈騎士》現行詞表。
來源頁序見 [001](001-input-baseline.md)。

已在 Chromium 離線開啟預覽，49 張圖片可解碼，31 個頭像候選及五個導覽目標存在。
1280、720、390 像素寬度沒有水平溢出。瀏覽器版號、頁面雜湊與實際截圖存於預覽目錄
`browser-receipt.json`。這是文件展示驗證，不是正式遊戲、HD 接入或跨平台驗收。

## 2026-10-25：Markdown 圖文版與人物總覽圖

根目錄 README 分別介紹怪物、人物頭像、遊戲截圖與遊戲內地圖，故事仍取自既有手冊來源。
圖像不加入 Git；本機輸出新增可直接閱讀的 `README.md`，與 HTML 共用相同原圖及來源索引。
現行預覽為 `workplace/probe/readme-gallery-preview-20261025/`，舊版不覆寫。

新增 `portraits-original.png`，將既有三十一張人物候選依來源編號排成六欄，
尺寸 1,152 × 1,152，只作整數倍最近鄰縮放與排版，不補身分或改原圖。
索引記錄總覽雜湊、尺寸、三十一個來源鍵，以及 Markdown 與 HTML 的雜湊。
Markdown 十九個圖片連結全部可開啟，總覽每格逐像素核對原圖，
其餘既有展示 PNG 與前版逐位元組一致。檢查工具及結果見本機 `check-documents.py`、`document-check.json`。

Chromium 實際開啟新 HTML，五十張圖片均可解碼，三十一個獨立頭像與五個導覽目標保留。
1,280、720、390 像素寬度無水平溢出；來源、瀏覽器版本與截圖見同目錄 `browser-receipt.json`。
兩張 HD 仍為未接入試繪，未增加 HD 完成數或遊戲驗收範圍。

## 2026-10-25：完整故事背景、機制與首頁截圖

依使用者要求暫停中文化與 HD，先擴充 README。故事分為戰後安塞隆、凱爾高斯的災難、
跨海泰勒達斯三節，保留羅拉娜來信與戴諾船長的起點，介紹主線威脅及火焰塔。
機制分五節，涵蓋隊伍／職業、探索／手札、戰術戰鬥、法術／月相、裝備／城內服務；
另以兩張表整理職業工作與畫面數值。這些是原版設計介紹，不外推為本專案完成範圍。

| 介紹來源 | 定位與採用範圍 |
|---|---|
| 已校讀《冒險手冊》 | `manual-gameplay-20261023/adventurer-core-r1/operation-review.zh-TW.tsv`；第 1 頁將軍來信、第 3–37 頁人物、戰鬥與魔法，來源及校讀限制回查 [001](001-input-baseline.md) |
| SSI 原版攻略書 | [原文 PDF](https://dlsaga.com/wp-content/uploads/2022/11/ks_darkqueen_cluebook_pdf.pdf)，PDF index 2 導言、index 3 帕蘭薩斯／凱爾高斯、index 4 龍人洞穴；用於背景摘要，沒有轉載攻略全文 |
| 遊戲官方介紹 | [Steam](https://store.steampowered.com/app/1904622/The_Dark_Queen_of_Krynn/) 的遊戲內容介紹，核對三部曲、跨海泰勒達斯、海底與火焰塔；未採其重發日期當作原版年份 |
| 現行本作術語 | 本機 `workplace/translation/glossary.tsv`，確認塔克西絲、安塞隆、泰勒達斯、火焰塔、戴諾及克萊西亞；沒有改動正式詞表 |

根目錄 README 直接嵌入十六個本機圖片連結，包含圖庫、試繪、三組實測截圖與地圖。
圖文輸出為 `workplace/probe/readme-gallery-story-mechanics-20261025-r2/README.md`、同目錄 `README.html`。
[產生器](../../tools/readme_preview.py) 改為完整讀取故事與機制章節，保留小節、表格及來源，
兩份輸出共用同一章節內容；索引新增章節 SHA-256，專案文件連結改用圖庫所在層級的相對路徑。
重建仍使用原有 [Docker 入口](../../tools/readme-gallery.sh)，採新輸出名稱，不覆寫舊預覽。

文件檢查記錄於本機 `document-check.json`：根目錄三十八個及圖文版二十三個本機連結存在，
根目錄十六張與圖文版十九張圖片均可解碼，完整章節與索引雜湊相符。
既有圖庫、HD 試繪及遊戲截圖與前版逐位元組相同；沒有新遊戲執行或 HD 生成。
檢查器首次誤用容器 `/out` 別名解析相對連結，改以實際專案位置檢查後通過，屬驗證路徑問題。

Chromium 141.0.7390.37 離線載入五十張圖片，三個故事小節、五個機制小節、兩張機制表及
七個導覽目標存在，1,280 與 390 像素寬度均無水平溢出。
抽看的桌面故事、機制及手機機制截圖保存於同目錄；擷取器使用即時捲動並等待畫格提交，
避免平滑捲動尚未完成就抓到其他章節。工具與頁面雜湊記錄於 `browser-receipt.json`。
所有圖像仍只留本機；原版／繁中、遊戲內區域圖／攻略重繪及未接入 HD 的標示維持。

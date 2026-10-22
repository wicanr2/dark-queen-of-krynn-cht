# 001：遊戲與中文來源基線

日期：2026-10-21。工作：[G1／#2](https://github.com/wicanr2/dark-queen-of-krynn-cht/issues/2)。
輸入唯讀掛載，以 `dkk-inventory:bookworm-r1` 的 `lsar`、`unar` 與 Python 3 盤點。
工具為 [inventory.py](../../tools/inventory.py)，完整成員與逐檔 SHA-256 留在
`workplace/input/dos-inventory.json`、`manual-zh-inventory.json`。

## 壓縮檔

| 輸入 | SHA-256 | 成員與解壓結果 | 等級 |
|---|---|---|---|
| `The Dark Queen of Krynn (1992).zip` | `4daa1df265848b2c7b592fb49d6abf746ae6dfe8d86c6aa55b63d761499bb956` | 58 筆成員，53 個檔案，根為 `drkqueen/` | 已證實 |
| `珍181-克萊恩黑暗之后.rar` | `9f0d3f96d2356362187c95f23860f7e0ed79717dd92581397a559ad8c785ae31` | 120 筆成員，119 個檔案，含連續編號的 117 張 JPG、Thumbs.db 與來源說明 | 已證實 |

## 版本與檔案形狀

本節位址皆為原始檔案偏移，不是 IDA 或執行期位址。

| 項目 | 原始證據 | 等級 |
|---|---|---|
| 遊戲入口 | `START.BAT` 呼叫 `dqk SB220 SI7 RB330`；`DQK.EXE` 是 MZ | 已證實 |
| 版本 | `DQK.EXE` 偏移 `0x687AB` 的版本字串為 1.1，日期 1992-07-29 | 已證實 |
| EXE 雜湊 | 449,664 bytes；`3b41fb06a045568b0c35098a104499d489d8a5c0ef0dd48a039387ba2393ba58` | 已證實 |
| 容器 | `ALWAYS.TLB`、`ECL.GLB` 開頭均為 `HLIB`；TLB／GLB 分布在 DISK1–DISK3 | 已證實；內部格式待解 |
| 設定 | `DISK1/DQK.CFG` 是 144-byte 二進位，不是前作逐行文字設定 | 已證實；欄位語意未知 |
| 存檔 | 根目錄與 SAVE 下均有相同的 `SAVGAMA.QSV`、`VAULTA.DAT` | 已證實；正常讀入附帶隊伍見研究 003，存檔回寫尚未驗 |
| 連結期支援 | IDA 載入區可見 `.RTLink(R)/Plus` 的錯誤訊息 | 已證實；compiler family 與精確版本未知 |

前兩作的 FBOV／DAX 位址、設定改寫與解析器不能直接套用。本作沒有相同的 `GAME.OVR`。

## 中文來源

影像接觸表在 `workplace/manual-preview/sheet-1.jpg` 至 `sheet-4.jpg`，頁面映射與原始掃描
雜湊在 `page-map.json`。已逐張查看四份接觸表，並放大核對關鍵頁。

| 掃描 | 已確認內容 | 等級 |
|---|---|---|
| Image001–003 | 盒裝與書背，封面可見「克萊恩黑暗之后」 | 已證實 |
| Image004–043 | 操作手冊、目錄、操作說明及附錄 | 已證實分類；逐頁完整性尚待校對 |
| Image044–046 | 冒險手冊封面與目錄 | 已證實 |
| Image047 | 冒險手冊故事開頭與地圖，印刷第 1–2 頁 | 已證實 |
| Image087 右頁 | 印刷第 82 頁，旅行手札第 1 則開始 | 已證實 |
| Image111 | 印刷第 129–130 頁，旅行手札第 66–68 則 | 已證實 |
| Image112–117 | 版權頁、譯者說明、封面與磁片標籤 | 已證實分類 |

檔名 Image001–117 沒有缺號。這不證明每一印刷頁、每則手札內容都完整；OCR 也有誤識別，
必須校對後才可建立正式手札 catalog。

## OCR 草稿

[manual_ocr.py](../../tools/manual_ocr.py) 在既有
`sundog-manual-tools:bookworm-20261016-r2` 內使用 Tesseract 5.3.0、`chi_tra+eng`、PSM 3。
操作與冒險手冊共拆成 212 個左右頁，全部產出文字與 log，manifest 保存在
`workplace/manual-ocr/manifest.json`。此階段僅供定位、術語與頁序校對，不是已校訂正文。
掃描與 OCR 全文均未入 Git。

第一輪 Tesseract 草稿錯字過多，不能直接作正式文字。
後續 PP-OCRv5 mobile 工具與進度收據見 [002 的 OCR 入口](002-walkthrough-source.md#ocr-工具與校對界限)。

第二輪已處理 212／212 頁，7,783 個區塊，0 執行錯誤，逐頁輸出雜湊回驗通過。
兩個空白輸出 `Image005-left`、`Image045-left` 已對照影像，均為封面內側空白頁。
全文仍未校對，存在錯字、繁簡混用及圖中文字辨識問題。

- manifest：`workplace/paddle-manual/manifest.json`，SHA-256
  `91846ebac98a50f2939e6df1247d53a2974def983d4c9697e4cac3afe8448b54`。
- provenance：`workplace/paddle-manual/provenance.json`，SHA-256
  `a43b72e71ee8922ec85e2ce94ba7a6116c757534c2a091586c98a1cfeffabb26`。
- 成功續跑的容器 `oom`、`oom_kill` 均為 0，峰值 1,212,506,112 bytes。

## 英文手札補充來源

正常開始冒險會要求依英文手札的頁碼與字序回答，中文譯本不能提供相同的英文單字序號。
為核對這條正常路徑，另下載 Museum of Computer Adventure Game History 保存的
[SSI 英文 Adventurer’s Journal 掃描](https://mocagh.org/ssi/addcollectorsvol2-dqk-journal.pdf)。
檔案只留 `workplace/input/dqk-english-journal.pdf`，不入 Git。

| 項目 | 已證實的資料 |
|---|---|
| bytes | 15,626,086 |
| SHA-256 | `fb31889c508e81d3c32ef44b4d1245ee5aa418335e6f94a11a3361c7a30185aa` |
| PDF 形狀 | 33 頁，具有文字層；PDF 頁索引不是印刷頁碼 |
| 核對點 | PDF index 6 的印刷第 10 頁，Saving Throws 標題後第 6 個字，與原版本輪提問對應 |

以 Docker 內 Python 下載，pypdfium2 5.14.0 讀取文字層及擷取局部頁面。
本輪只為正常輸入查驗與英文定位補充來源，沒有新增遊戲內答案提示或略過原版判定。

## 手札編號跳號

本次 OCR 共找到 67 個明確手札標題，編號為 1 至 68，但沒有 13。
人工對照 `Image091-left` 的印刷第 89 頁及 `Image091-right` 的第 90 頁，確定第 12 則後
直接是第 14 則。英文補充來源的 PDF index 18、印刷第 33–34 頁也有相同跳號。
這不是本次解壓或 OCR 少處理一頁；遊戲是否引用第 13 則仍未知。

索引工具是 [index_journal.py](../../tools/index_journal.py)，只保留辨識出的原編號、來源區塊與座標，
不插入第 13 則，也不把第 14 則改排成第 13 則。輸出 `workplace/paddle-manual/journal-index.json`
只是研究索引，不能直接視為已校對的正式手札資料。圖文內容尚未逐則確認。

## 2026-10-23：手札正文校讀稿與字模量測

已依英文印刷第 31–48 頁的九張跨頁圖，重讀所有手札文字，配合原中文 OCR、現行術語及前作詞條，
新增 63 則正文校讀稿。加上原有第 54 則，目前有 67 個標題、64 則正文稿。
第 12 則是破損信件圖，第 25、64 則是地圖，分開保留七組可辨碎紙文字與 21 個地圖標籤。
它們尚未完成圖文重建，不能以已有標題宣稱全冊完成。第 13 則仍不補造。

本批資料只留本機，入口為 `workplace/probe/pane-render-20261022/journal-book-evidence.json`，
生成器 `journal_book_evidence.py`，回鏈上一份實際閱讀原型索引。
公開工具為 [journal-review.sh](../../tools/journal-review.sh) 與
[journal_review_check.py](../../tools/journal_review_check.py)。
執行 `bash tools/journal-review.sh 全新輸出名稱`，使用固定
`nectaris-font-subset:20260821`、目前 UID/GID、1 GiB、1 CPU、無網路的容器，
在既有 `workplace/probe/pane-render-20261022/` 產生合併稿與檢查收據。
檢查器不寫回主譯表，也不把校讀結果判為正式閱讀 catalog。

| 私有來源 | 用途 |
|---|---|
| `workplace/translation/journal-book-prose-additions.zh-TW.tsv` | 本批新增標題及正文；原有 54 由 `palace-journal54-review.tsv` 合併，不複製為另一份可編輯來源 |
| `journal-book-map-labels.zh-TW.tsv` | 兩張手札地圖的 21 個繁中標籤，尚無地圖幾何完成聲明 |
| `journal-book-fragments.zh-TW.tsv` | 第 12 則七組可辨文字；省略號表示破損處，缺字數量與紙片幾何尚未重建 |
| `journal-book-term-bindings.tsv` | 81 個既有詞根的 189 處明確綁定；其中 25 個前作詞根另回讀前作術語表核對 |
| `journal-book-name-candidates.tsv` | 25 個編輯候選，保留英文、來源與不確定處，未升入正式術語表 |

表內未重列根目錄的 TSV 均在 `workplace/translation/`。
合併稿為 `journal-book-review-r4.zh-TW.tsv`，131 筆，含 67 個標題與 64 則正文。
連同地圖標籤及碎紙文字，共 11,095 字元、1,534 種字元，圓體字型涵蓋完整。
五個禮儀用語的原文輸入字保留，待辦圖的一個已勾選、八個未勾選狀態也保留。
主譯表仍為 7,730 筆，971 筆術語、原文及 catalog 雜湊未改，不能與本批書籍資料加總。

校讀修正包含：第 6 則戰後覺得無聊被譯成出生，第 9 則警告語的反義，第 50 則未煮熟被譯成煮過熟、
夸脫被誤解為四分之一，第 53 則拔劍被譯成收劍，以及第 63 則書本被誤作陵墓。
武器、怪物與跨代人物沿現行前作優先詞條，例如寬刃劍、法杖、魔法杖、坎德人、塔克西絲、提卡與佛林特。
查凱斯在原劇本同時被稱為 Dragonman 及成年的 Bakali，第 2 則據此譯蜥蜴人，與 Draconian「龍人」分開。
這不授權對所有 Dragonmen 作全域替換，其他場景仍須各自核對。

英文文字層有漏標題、欄序混雜及錯字，第 12 則信件還是圖像，故不以自動切篇結果取代頁面。
九張圖已目視閱讀，文字層及圖以 `journal_book_sources.py` 在固定 pypdfium2 5.14.0 重生，逐位元組一致。
中文續頁範圍由既有標題索引與下個標題位置推導，僅供導覽，不冒充逐頁內容校對證據。
第 12 則可辨文字已形成片段稿；破損單字的補全仍屬強推論，缺文保持未知，不補成完整信件。

### 字格外伸的根因

本批從字型字碼表確認無缺字後，實際字模生成仍在「珊」被拒絕。
依 [中文版面技能](https://github.com/wicanr2/dark-queen-of-krynn-cht/blob/main/AGENTS.md#4-參考來源與知識路由)
的量測方法，分開測量字格、前進寬度與實際字墨，得到以下結果。
數值為 16px 字型、原繪製原點的相對像素框。

| 字 | 實際字墨框 | 前進寬度 | 放入 16px 字格的整數平移 |
|---|---|---|---|
| 取 | `[-1,0,15,13)` | 16px | x 加 1px |
| 珊 | `[1,0,17,14)` | 16px | x 減 1px |

兩字的實際字墨都只有 16px 寬。舊 [menu_glyphs.py](../../tools/menu_glyphs.py)
在字格內直接繪製，會裁掉「取」的左邊字墨，並因字型度量右界超出而拒絕「珊」。
新工具先在有餘白的畫布繪製，再依實際墨跡作最小整數平移；超過容量的真實字墨仍拒絕。
字級、字格、行高與 JSON 形狀不變。

全稿加介面詞條產生 1,538 個 16px 字模，逐點證明原始非零透明度完整保留，只有上述兩字平移，
下方四列皆無字墨。既有 20px 角色管理 32 字模逐位元組相同；既有 16px 閱讀 462 字模只改「取」。
64 則均產生排版量測圖，並目視抽看禮儀用語、珊西蘭及長篇料理稿；這些圖不是遊戲擷取。
字碼覆蓋使用 FontTools 4.53.1，繪製使用 Pillow 11.3.0；Pillow 映像為
`sc-cht-hdtools:pillow11.3.0-r1`，固定 SHA-256
`44d0742ca1061bcd453440cdce925afa31c5324e115fca1334da0e364f0e2c48`。

六種變造全部拒絕：補造 13、漏正文、錯人物譯名、改掉英文輸入字、把碎紙冒充完整正文、
以及改掉原圖勾選狀態。現行單頁原型容量另量出第 47、50 則各需 14、16 行，超出十三行，
其餘 62 則不超頁。長頁、手動查閱、三則圖文與全冊遊戲接入仍待完成，見
[規格 002](../spec/002-journal-reader.md)。本批未新增正常玩家路徑收據，第 54 則以外不宣稱已在遊戲中驗證。

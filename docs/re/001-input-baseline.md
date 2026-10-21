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
| 存檔 | 根目錄與 SAVE 下均有相同的 `SAVGAMA.QSV`、`VAULTA.DAT` | 已證實；讀檔內容未驗 |
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

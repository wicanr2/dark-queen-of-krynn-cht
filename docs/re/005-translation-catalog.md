# 005：文字候選與繁中譯表

日期：2026-10-21。工作：[#7](https://github.com/wicanr2/dark-queen-of-krynn-cht/issues/7)。
使用者已指定先完成中文化，再做全量 HD。地圖與 HD 批次延後，既有成果保留。

## 翻譯決定與權威來源

使用者確認首批 145 筆試譯的自然、簡潔譯風，共通術語以前作優先，並明確要求武器、怪物與
跨代人物對齊《幽靈騎士》。本作手冊的異譯保留來源，不無條件覆蓋前作。

| 優先 | 來源 | 用途 |
|---|---|---|
| 1 | 幽靈騎士 `text/glossary.tsv`、`name-lexicon-five.tsv`、`name.zh-TW.tsv` 及文字事件表 | 武器、怪物、跨代人物與既有譯文 |
| 2 | 克萊恩英豪的對應術語與譯表 | 補上前作未收錄的名稱 |
| 3 | 本作操作／冒險手冊及英文原文 | 本作新增名稱與語境核對 |

例如武器 Long Sword、Bastard Sword、Mace 沿用「長劍、手半劍、釘頭錘」，
怪物 Spectre、Wraith、Draconian 沿用「幽靈、縛靈、龍人」，人物 Lord Soth 沿用「索斯王」。
本作手冊的「龍怪」保留為 Draconian 異譯；使用者補充對齊要求後，已修正首批三句相關譯文。
本作新增的戴諾、克萊西亞已目視核對冒險手冊第 89 頁；凱爾高斯核對第 119 頁，
手札 65 的「卡爾高斯」留作異譯。飛刀陣核對冒險手冊第 62 頁。
另目視核對冒險手冊第 38、39、44、45、46、55 頁的 15 個新增怪物名稱，
例如多眼怪、黑布丁、大甲蟲、綠火怪與氣胞眼怪；相關掃描雜湊保存在本機術語來源。
第 63、78、80 頁補上還陽術、分解術、狂舞術及保護心智。
本作 Delayed Blast Fireball 的拼字變體沿用既有「延時爆發火球」，手冊異譯不覆蓋前作。

## 輸入與擷取界限

| 輸入 | SHA-256 | 本輪用途 |
|---|---|---|
| `DQK.EXE` | `3b41fb06a045568b0c35098a104499d489d8a5c0ef0dd48a039387ba2393ba58` | ASCII NUL 結尾介面候選 |
| `DISK3/ECL.GLB` | `40542071e42d3cd125eabcead11456a99942bf55a7736fdb79f66a3c27c3664d` | HLIB 索引及 6-bit 劇本候選 |
| `DISK2/MONCHA.GLB` | `43de18b224dde3786e223ae5d0af53afad2a8109981fd73c1e3e81bd87d6ac68` | HLIB 區塊中的 ASCII 名稱候選 |

[text_catalog.py](../../tools/text_catalog.py) 驗證 HLIB 的檔案長度、區塊數、單調索引與末端邊界。
ECL 的 48 個區塊含首個對照區塊，不能稱作 48 張地圖；MONCHA 有 99 個區塊。
本輪在 ECL 資料區塊掃描 `80 <長度> <6-bit bytes>`，以可讀字詞啟發式留下候選。
這不是完整腳本解譯器，仍可能留下內部訊息、偶然字節及嵌在長段裡的切片。

第一段完整 185 字元與 [研究 004](004-story-text.md) 的執行期觀測逐字相同；
正常選單另有 13 個完整字串，共 14 筆已觀測項目。6 次 `%c` 格式出口不當作玩家文字。
這組觀測在候選清單中沒有遺漏，不能因此宣稱全遊戲擷取完整。

| 分類 | 目前候選數 | 限制 |
|---|---|---|
| 劇本 | 6,937 | 包含開發訊息、雜訊與切片，尚未全數分類 |
| EXE 文字 | 1,346 | 包含資源名稱、系統錯誤及偶然機器碼，並非全是介面 |
| MONCHA 名稱 | 98 | 直接掃描原始 ASCII，含非名稱雜訊；記錄結構與壓縮尚未證實 |

MONCHA 的簡單 RLE 探針在多個區塊失敗，沒有把該假說寫成正式解析器。
名稱候選數不代表已還原 98 種怪物。武器名稱目前主要來自 EXE；沒有為翻譯改寫 ITEM 資料。

## 譯文、術語與檢查

所有大量原文、譯文、名稱對照、來源雜湊與批次只留 `workplace/translation/`，不入 Git。
主要檔案如下。

| 本機檔案 | 用途 |
|---|---|
| `en.tsv` | 唯一候選原文表，`key`、`text`，保留大小寫及頭尾空白 |
| `catalog.json`、`events.tsv`、`receipt.json` | 原始檔偏移、區塊、來源雜湊、觀測等級與工具／輸出雜湊 |
| `zh-TW.tsv` | 已通過批次檢查的目前譯文，`key`、`text`；尚未接入遊戲 |
| `trial.zh-TW.tsv`、`trial-review.md` | 使用者確認譯風的 145 筆首批與雙語稿 |
| `glossary.tsv`、`terminology-provenance.json` | 前作優先的 769 筆術語、原始來源及歧義 |
| `name-candidates.tsv`、`batch-names.tsv` | 單獨名稱對照與當批輸入，已合併批次及狀態由 `completed/` 與譯表回查 |
| `prior-candidates.tsv`、`prior-provenance.json` | 前作原文完全一致或僅大小寫不同的 886 筆待核對候選 |
| `prior-reviewed.tsv` | 從其餘前作候選逐筆審閱後保留的 375 筆；17 筆語境不明者未合併 |
| `story-caves.tsv`、`story-monsters.tsv` | 本作洞穴劇情、對話與怪物事件共 131 筆新譯 |
| `ui-effects-trade.tsv` | 204 筆狀態、交易、角色、存檔與戰鬥訊息新譯 |
| `current-validation.tsv`、`current-validation-check.json` | 現行譯表整體檢查的固定輸入及收據，不代表遊戲接入驗收 |
| `batches/index.json` | 其餘候選的分批入口，不是完成度分母 |
| `completed/` | 依批次名及輸入雜湊保存批次歷史與檢查收據；修訂前版本保留，現行值以 `zh-TW.tsv` 為準 |
| `term-reviews.tsv` | 句內多義詞的校讀理由，固定原文與譯文雜湊；內容改變後自動失效 |

[terminology_align.py](../../tools/terminology_align.py) 與
[translation_seed.py](../../tools/translation_seed.py) 固定前作來源優先序，保存逐檔雜湊及選用來源。
有格式參數的字串禁止以改大小寫方式匹配。Shield 同時有法術「魔法盾牌」及造形選項「盾牌」
兩種語境，保留歧義，不以全域替換硬套其中一種。

[translation_check.py](../../tools/translation_check.py) 檢查欄數、UTF-8、key 唯一與孤兒、NFC、
空白、控制字元、格式參數、數字及實際字型 cmap。武器、怪物、人物的單獨名稱另與術語表核對，
句內名稱及常見複數另列語境警示，不以無條件替換處理形容詞或其他歧義。
已核對的形容詞或複合名稱以逐句理由記錄；例如 giant shapes 的 giant 不指巨人族，
敘述「一頭龍」也不硬套類名「龍族」。此校讀不能豁免單獨怪物或武器名稱的錯誤。
前作「第一級」至「第九級」與英文序數做數值等價檢查，不為通過檢查改成另一套名稱。
帶參數的傷害片段仍需驗證完整組句，格式參數相同不代表實際句序已正確。

首輪已檢查並合併 504 筆譯文：首批 145、名稱 323、休息與戰鬥訊息 36。
後續另補 163 筆角色管理、商店、存讀檔、營地、戰鬥結果與神廟訊息，以及 2 個新增人物名稱鍵，
累計 669 筆。後續再補前作同文審閱 375、洞穴劇情 131、介面訊息 204、名稱與法術鍵 25，
目前共 1,404 筆。這是譯文進度，不能稱為 1,404 個功能、全遊戲覆蓋率或可玩中文化完成。
前作同文也可能依賴原場景；例如 TOWER 的前作譯文帶有特定塔名，不能直接帶入本作。
THE、SWORD、Shield 等片段或同文異義項目保留待查，不用前作的單一譯法補洞。
字型為 jf open 粉圓 2.1，SHA-256 沿用規格 001；fontTools 4.53.1 核對實際 cmap。

## Docker 入口

[translation.sh](../../tools/translation.sh) 提供以下入口，原版及前作唯讀，僅本作研究工作區可寫。
停用網路、非 root，使用已存在且固定 ID 的 Pillow 與字型工具 image。缺少來源時停止。

```sh
bash tools/translation.sh extract
bash tools/translation.sh terms
bash tools/translation.sh seed
bash tools/translation.sh batches
bash tools/translation.sh check trial
bash tools/translation.sh check names
bash tools/translation.sh check ui-rest-combat
bash tools/translation.sh check ui-management
bash tools/translation.sh check prior-reviewed
bash tools/translation.sh check story-caves
bash tools/translation.sh check story-monsters
bash tools/translation.sh check ui-effects-trade
bash tools/translation.sh test
```

[translation_batches.py](../../tools/translation_batches.py) 依目前譯表生成後續批次。
`check` 只有在使用者已確認本作譯風後使用；它逐批合併譯文，保留先前批次。
重新生成批次會隨已合併譯文改變內容；已合併批次及其檢查收據自動保存到 `completed/`。
新譯文不得進入原版記憶體、檔名、條件比較或存檔，顯示接入仍依規格 001 的證據閘門。

[test_translation_guards.py](../../tools/test_translation_guards.py) 以最小 fixture 驗證正常批次、
孤兒 key、遺失格式參數、錯誤怪物名稱、不同級數及重複 key。失敗時必須保留原有譯表，
不得把拒絕批次存成完成收據。這是工具防錯檢查，不是原版規則或遊戲接入驗證。

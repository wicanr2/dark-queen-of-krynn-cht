# 005：文字候選與繁中譯表

建立：2026-10-21；更新：2026-10-22。工作：[#7](https://github.com/wicanr2/dark-queen-of-krynn-cht/issues/7)。
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
海底與哈德弗克事件已核對諾里迪斯、西洛爾、鐵虎克、萊里恩、古朗思卡等本作名稱。
泰索何夫、麥坦尼、科南沿用前作；Tasselhoff／Tasslehoff 的原文字形都保留，顯示譯名一致。
特拉格與正式龍人族系分列，不因相近就一律加上龍人；本作手冊第 40 頁的族系異譯仍保留來源。
未找到手冊完整中英對照的少數名稱，以英文原名新譯並標記待全書校讀，
例如塞里亞斯、艾莉亞、瑟拉諾斯特及傳聲海螺，不冒充手冊中已有的中譯。

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

第一段完整 185 字元與 [研究 004](004-story-text.md) 的執行期觀測逐字相同。
最初清單有 14 筆已觀測項目；正常進城、訓練所及營地存檔來源補入後，清單目前登錄 51 個不重複
已觀測鍵，來源類別為 `ui` 41 個、`ecl` 10 個。已匯入的 89 次執行期 literal 觀測含重畫與槽位字母，
不當作 89 個功能。七段開場劇情是段落數，不與來源鍵數混列。
格式出口與編碼座標另行排除。上述已匯入的正常觀測在清單中沒有遺漏；本輪 Shield 的原始呼叫
另存於下節收據，尚未匯入 catalog，不加入此數量，也不能宣稱全遊戲擷取完整。

| 分類 | 目前候選數 | 限制 |
|---|---|---|
| 劇本 | 6,937 | 包含開發訊息、雜訊與切片，尚未全數分類 |
| 介面文字 | 1,372 | 1,346 個 EXE 掃描候選與 26 個執行期新鍵，含槽位字母；仍含資源名稱、錯誤與機器碼雜訊 |
| MONCHA 名稱 | 98 | 直接掃描原始 ASCII，含非名稱雜訊；記錄結構與壓縮尚未證實 |

MONCHA 的簡單 RLE 探針在多個區塊失敗，沒有把該假說寫成正式解析器。
名稱候選數不代表已還原 98 種怪物。武器名稱目前主要來自 EXE；沒有為翻譯改寫 ITEM 資料。
目前 98 筆 MONCHA 原始 ASCII 候選中有 96 筆譯文；其餘 AMT、HNZH 仍無法辨識為名稱。
這個數字只描述候選譯表，沒有證實記錄邊界、怪物種類或實際遇敵顯示。

## 譯文、術語與檢查

所有大量原文、譯文、名稱對照、來源雜湊與批次只留 `workplace/translation/`，不入 Git。
主要檔案如下。

| 本機檔案 | 用途 |
|---|---|
| `en.tsv` | 唯一候選原文表，`key`、`text`，保留大小寫及頭尾空白 |
| `catalog.json`、`events.tsv`、`receipt.json` | 原始檔偏移、區塊、來源雜湊、觀測等級與工具／輸出雜湊 |
| `zh-TW.tsv` | 已通過批次檢查的目前譯文，`key`、`text`；尚未正式接入遊戲 |
| `trial.zh-TW.tsv`、`trial-review.md` | 使用者確認譯風的 145 筆首批與雙語稿 |
| `glossary.tsv`、`terminology-provenance.json` | 前作優先的 971 筆術語、手冊對照、英文新譯來源及歧義 |
| `name-candidates.tsv`、`batch-names.tsv` | 單獨名稱對照與當批輸入，已合併批次及狀態由 `completed/` 與譯表回查 |
| `prior-candidates.tsv`、`prior-provenance.json` | 前作原文完全一致或僅大小寫不同的 886 筆待核對候選 |
| `prior-reviewed.tsv` | 從其餘前作候選逐筆審閱後保留的 375 筆；17 筆語境不明者未合併 |
| `story-caves.tsv`、`story-monsters.tsv` | 本作洞穴劇情、對話與怪物事件共 131 筆新譯 |
| `story-undersea.tsv`、`story-travel-rescue.tsv` | 海底救援 201 筆及旅行、洞穴與救援短句 270 筆 |
| `story-new-names.tsv`、`story-coast-hulder.tsv` | 新名稱相關事件 42 筆及海岸、哈德弗克事件 145 筆 |
| `story-forest-thenol.tsv`、`ui-quests-magic.tsv` | 森林、西洛爾事件 252 筆及介面、任務、魔法短句 48 筆 |
| `story-palace-kristophan.tsv` | 西洛爾王宮、克理斯多芬與陵墓劇情 178 筆 |
| `story-hawkbluff-blackwater.tsv`、`story-citadel-finale.tsv` | 鷹峽與黑水坡 120 筆，地侏堡壘及部分結局 76 筆 |
| `story-tower-abyss.tsv` | 地侏堡壘、火焰塔、深淵與結局敘述 165 筆 |
| `story-palace-tombs-short.tsv`、`story-tower-citadel-short.tsv` | 王宮至黑水坡短句 218 筆，黑水坡至深淵短句 245 筆 |
| `story-undersea-caves-short.tsv`、`story-hulder-caves-short.tsv` | 海底、希茲登與洞穴短句 184 筆，洞穴與哈德弗克森林短句 255 筆 |
| `story-aurim-palace-short.tsv` | 新奧利姆、神廟、監獄及王宮短對話與提示 303 筆 |
| `story-kristophan-hawkbluff-short.tsv`、`story-hawkbluff-blackwater-short.tsv` | 克理斯多芬、陵墓與鷹峽短句 328 筆，鷹峽與黑水坡短句 121 筆 |
| `story-blackwater-baior-short.tsv` | 黑水坡、特里摩爾與拜依歐爾短句 220 筆 |
| `story-citadel-tower-prompts.tsv`、`story-tower-abyss-prompts.tsv` | 地侏堡壘與火焰塔短句 248 筆，塔頂、深淵與結局短句 212 筆 |
| `story-aurim-palace-narrative.tsv`、`story-palace-kristophan-narrative.tsv` | 新奧利姆與王宮較長敘述 93 筆，王宮與克理斯多芬較長敘述 105 筆 |
| `story-tombs-hawkbluff-narrative.tsv`、`story-blackwater-citadel-narrative.tsv` | 陵墓與鷹峽較長敘述 119 筆，黑水坡與地侏堡壘較長敘述 130 筆 |
| `story-windship-tower-narrative.tsv`、`story-tower-abyss-narrative.tsv` | 風船與火焰塔較長敘述 129 筆，塔頂、深淵與結局較長敘述 126 筆 |
| `story-context-labels.tsv` | 蜥蜴人追逐場景的三個敘述／選單鍵，依來源位置校讀 |
| `manual-name-corrections.tsv` | 11 個既有鍵的精確修訂，含手冊新核名稱與同場地點用語；不增加譯文數 |
| `manual-deity-corrections.tsv` | 手冊第 124 頁核對後，校正一個既有喜得卡譯文鍵；不增加譯文數 |
| `*-review-input.json` | 逐批校讀時固定的來源字串與原文表 SHA-256；不是正式顯示來源 |
| `passage-candidates.json`、`passage-candidates.en.tsv` | 322 組靜態相鄰字串候選；獨立校讀輸入，未列入正式原文／譯文表 |
| `passage-review/zh-TW.review.tsv` | 284 組候選繁中校讀稿，含段落、引語前導及動態主詞片段；不合併目前譯表 |
| `passage-review/source-snapshot.json` | 校讀候選的完整來源快照、固定輸入雜湊與目前譯表的保護雜湊 |
| `passage-review/deferred.tsv` | 38 組未譯候選的疑問與推論等級；保留原始候選，不作刪除依據 |
| `passage-review/term-reviews.tsv` | 候選校讀稿的逐句歧義理由，18 則覆蓋 19 次匹配，與目前譯表的校讀紀錄分開保存 |
| `passage-review/passage-review-check.json`、`passage-review/passage-review-review.md` | 純校讀檢查收據與雙語稿；`review_only` 為真，未標記批次完成 |
| `term-corrections.tsv` | 已有譯文的精確鍵修訂，包括避難廳與不死怪物用語 |
| `ui-effects-trade.tsv` | 204 筆狀態、交易、角色、存檔與戰鬥訊息新譯 |
| `ui-palanthas-observed.tsv` | 正常城內去向選單的 7 個新介面鍵，保留實際大小寫及 Hall 語境 |
| `story-city-sea-choices.tsv` | 城鎮、海底短句及選項 91 筆；怪物與人名沿用既有術語，未全數驗證顯示呼叫 |
| `story-citadel-abyss-actions.tsv` | 堡壘、火焰塔與深淵操作、引語前導及動作片段 163 筆；不自動串接動態主詞 |
| `citadel-abyss-actions-review-input.json`、`story-citadel-abyss-actions-before.tsv` | 本批完整來源定位、來源雜湊與合併前 6,138 筆譯表快照；保留歷史，不作正式顯示來源 |
| `story-citadel-abyss-actions-comparison.json` | 合併差分收據，核對舊鍵、來源、原版輸入、目前譯表、全表檢查及前作術語 |
| `story-sea-lighthouse-clauses.tsv` | 海底、港口與燈塔文字 117 筆，含 116 個新鍵及 1 筆既有甲蟲敘述修正 |
| `sea-lighthouse-clauses-review-input.json`、`story-sea-lighthouse-clauses-before.tsv` | 每筆來源定位、原文與原版雜湊、允許修改的既有鍵及合併前 6,301 筆快照 |
| `story-sea-lighthouse-clauses-comparison.json`、`sea-lighthouse-clauses-context-review.json` | 本批差分收據、甲蟲敘述的推論等級、未知接續 bytes 及 OTHER 共享語境限制 |
| `ui-camp-save-observed.tsv` | 正常旅店營地與存檔確認頁新增的九個短標籤，保留實際大小寫；不含 A 至 J 槽位字母 |
| `../probe/catalog-runtime-save-20261022/` | 新舊來源比較，`before/` 保留 8,388 鍵與 6,417 筆譯表，`catalog-comparison.json` 核對九個短標籤及十個槽位字母 |
| `story-fastillion-lighthouse-clauses.tsv` | 菲斯特隆實驗室及燈塔陷阱 206 筆，含 204 個新鍵與 2 個既有敘述銜接修正 |
| `fastillion-lighthouse-clauses-review-input.json`、`story-fastillion-lighthouse-clauses-before.tsv` | 本批完整來源定位、原版及來源雜湊、允許修正的既有鍵與合併前 6,426 筆快照 |
| `story-fastillion-lighthouse-clauses-comparison.json` | 新增、修正與未改舊鍵的差分收據；前作人物、怪物及物品 266 筆對照結果 |
| `story-hulder-forest-clauses.tsv` | 森林、哈德弗克與眾樹之母片段 95 筆，含 93 個新鍵及 2 個舊譯修正 |
| `hulder-forest-clauses-review-input.json`、`story-hulder-forest-clauses-before.tsv` | 完整來源、JOIN 三處相鄰語境、七種保留謎題字形及三個未知候選，另存合併前 6,630 筆快照 |
| `story-hulder-forest-clauses-comparison.json` | 本批新增與修正差分、舊鍵保留、前作術語對照及謎題字形未合併檢查 |
| `story-city-luminari-clauses.tsv` | 城內、神廟、門鎖及魯明那里燈塔片段 168 筆，含 165 個新鍵及 3 處舊譯修正 |
| `city-luminari-clauses-review-input.json`、`story-city-luminari-clauses-before.tsv` | 本批全部來源定位、原版與譯表雜湊、允許修正鍵及合併前 6,723 筆快照；保留十八個未合併候選及理由 |
| `city-luminari-clauses-term-reviews-before.tsv`、`story-city-luminari-clauses-comparison.json` | 舊 265 則校讀快照、新舊差分、十八個候選未合併、既有校讀 bytes 保留及前作術語對照 |
| `story-palace-kristophan-clauses.tsv` | 王宮、克理斯多芬與陵墓片段 213 筆，含 205 個新鍵及 8 個舊鍵修正 |
| `palace-kristophan-clauses-review-input.json`、`story-palace-kristophan-clauses-before.tsv` | 全部來源、猴形動物及店家等語境、推論等級、三十二個未合併候選及合併前 6,888 筆快照 |
| `palace-kristophan-clauses-glossary-before.tsv`、`palace-kristophan-clauses-glossary-additions-before.tsv`、`palace-kristophan-clauses-term-reviews-before.tsv` | 舊 970 筆術語、原本 additions 及 267 則校讀的快照，不改歷史輸入 |
| `story-palace-kristophan-clauses-comparison.json` | 新舊譯文、八個修正鍵、URCHIN 六鍵一致性、舊術語保留、前作共通術語及未合併候選檢查 |
| `story-hawkbluff-blackwater-clauses.tsv` | 鷹峽、通行證與黑水坡片段 229 筆新譯 |
| `story-hawkbluff-blackwater-clauses-review-input.json`、`story-hawkbluff-blackwater-clauses-before.tsv` | 原始來源、同場語境、推論等級、44 個保留候選及合併前 7,093 筆快照 |
| `story-hawkbluff-blackwater-clauses-pure-check.json`、`story-hawkbluff-blackwater-clauses-term-reviews-before.tsv` | 純校讀通過收據及舊 271 則語境校讀快照 |
| `story-hawkbluff-blackwater-clauses-comparison.json` | 新增鍵、全數舊譯未變、原始輸入與術語雜湊、前作 266 筆共通術語檢查 |
| `story-baior-rebuilding-clauses.tsv` | 拜依歐爾、造船廠與焰息片段 314 筆，含 312 個新鍵及 2 個舊鍵修正 |
| `story-baior-rebuilding-clauses-review-input.json`、`story-baior-rebuilding-clauses-before.tsv` | 全部來源、相鄰語境、推論等級、四個未合併候選及合併前 7,322 筆快照 |
| `story-baior-rebuilding-clauses-pure-check.json`、`story-baior-rebuilding-clauses-term-reviews-before.tsv` | 純校讀通過收據及舊 279 則語境校讀快照 |
| `story-baior-rebuilding-clauses-comparison.json` | 新舊差分、兩個允許修改鍵、輸入與術語雜湊及前作 266 筆共通術語檢查 |
| `story-tower-abyss-clauses.tsv` | 要塞、火焰塔與深淵片段 96 筆，含 94 個新鍵及 2 個舊鍵修正 |
| `story-tower-abyss-clauses-review-input.json`、`story-tower-abyss-clauses-before.tsv` | 原始來源、同場證據、52 個未合併候選與逐項理由，以及合併前 7,634 筆快照 |
| `story-tower-abyss-clauses-pure-check.json`、`story-tower-abyss-clauses-term-reviews-before.tsv` | 純校讀通過收據與舊 289 則校讀快照 |
| `story-tower-abyss-clauses-comparison.json` | 新舊差分、兩個允許修改鍵、輸入與術語雜湊、前作共通術語檢查 |
| `issue7-tower-abyss-clauses-before.txt`、`issue7-tower-abyss-clauses-body.txt`、`issue7-tower-abyss-clauses-comment.txt` | 遠端 #7 更新前內文、更新稿及本批進度留言 |
| `issue7-baior-clauses-before.txt`、`issue7-baior-clauses-body.txt`、`issue7-baior-clauses-comment.txt` | 遠端 #7 本批更新前內文、更新稿與進度留言 |
| `issue7-hawkbluff-clauses-before.txt`、`issue7-hawkbluff-clauses-body.txt`、`issue7-hawkbluff-clauses-comment.txt` | 遠端 #7 本批更新前內文、更新稿與進度留言 |
| `current-validation.tsv`、`current-validation-check.json` | 現行譯表整體檢查的固定輸入及收據，不代表遊戲接入驗收 |
| `checker-equivalence.json` | 同一份 2,127 筆輸入的檢查器修正前後收據索引；除工具雜湊外結果相同 |
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

目前已檢查並合併 7,728 筆本機譯文，包含首批試譯、前作同文校讀、角色與介面、洞穴、海底、
森林、菲斯特隆實驗室、西洛爾、鷹峽、黑水坡、地侏堡壘、火焰塔、深淵及部分結局分支。
逐批數量見上表及 WORKLOG，現行譯文以 `zh-TW.tsv` 為準，歷史批次不重複計數。
這是譯文進度，不能稱為 7,728 個功能、全遊戲覆蓋率或可玩中文化完成。
前作同文也可能依賴原場景；例如 TOWER 的前作譯文帶有特定塔名，不能直接帶入本作。
THE、SWORD 等片段或同文異義項目保留待查。Shield 已補背包及法術書的分場景觀測，
正式呈現仍須依介面語境選譯，不在全域共用鍵填入單一譯法。
字型為 jf open 粉圓 2.1，SHA-256 沿用規格 001；fontTools 4.53.1 核對實際 cmap。
哈德弗克謎題仍保留 LIMENE、GEBENE 等原版英文字形，中文只解釋意思，未改輸入判定。
動態傷害、角色代詞、部分切片與跨段引號仍需完整組句驗證。

本輪另核對手冊第 65、66、81 頁的束縛動物、免受火焰傷害、流星火球術、召喚怪物及殺人之咒。
Skeletal Warrior 沿用前作 Skeleton Warrior 的「骷髏戰士」。Iron Dragon Scale 依森林事件中的
鐵製龍鱗形護符譯為「鐵製龍鱗」，不誤列為龍的種類。本作新增而缺完整中英手冊對照的名稱
仍標記待全書校讀，不宣稱已有前作或官方中譯。

另目視核對手冊第 83 頁的克理斯多芬、查凱斯，第 92 頁的特里摩爾、波追那斯、寇沙，
第 126 頁的黑水坡與阿默羅卡。Amrocar 及 Othlorx 原先是本作英文暫譯；找到手冊對照後，
將本作暫譯「阿姆羅卡、奧斯洛克斯」校正為「阿默羅卡、歐斯羅克斯」，歷史批次與來源保留。
安塞隆沿用《幽靈騎士》；岩漿海及火焰塔沿用先前核對的本作手冊第 110 頁。
本作手冊異譯不覆蓋前作已定名。
帕克蘭等未找到中英對照的新名稱，仍標記英文新譯、待全書校讀。

查凱斯的成年試煉同場明言 Bakali。ECL 區塊 34 的九個已譯鍵將 Dragonman／Dragonmen 譯為「蜥蜴人」。
不把它們全域換成 Draconian「龍人」，其他場景仍依原文與語境區分。
珠寶商線索保留須輸入的 PASS、RELEASE 並附中文解釋，不改原版答案判定。
地名另作人工抽查，修正本輪安塞隆、岩漿海的暫譯偏差；一般場所描述不套用前作房間專名。
另查多詞法術名稱，將一個既有 Mind Blank 狀態敘述修正為「受心靈防護術保護」，對齊前作。
人物、怪物及物品的程式檢查之外，地名與法術仍須人工校讀；射線描述、複合法術名及樓層
不能依較短的術語片段硬換。
完整譯表回驗為 7,728 筆，0 格式錯誤、0 未處理術語警示，292 則逐句校讀覆蓋 298 次匹配。
這些檢查不證明正式遊戲顯示、動態組句、跨頁或結局正常路徑已完成。

手冊第 110、115、116、124 頁補核地侏國王、伯基藍那摩、風船、火艦隊及兩類地侏。
Gnomoi、Minoi 分別作「聰明地侏、小地侏」，「地侏」詞根沿用前作；手冊原作「地精」。
國王完整姓名沿用第 110 頁，其他頁的簡稱留作來源異譯。Hiddukel 原先是本作英文暫譯，
第 124 頁確認「喜得卡」後修正一個既有鍵。雷斯林、蓋加斯與法術名稱維持前作。
赫倫比許諾格、普迪等未見完整手冊對照的本作名稱，仍標記待校讀。

黑水坡談判另有三句 Dragonman／Dragonmen。ECL 區塊 33 的談判位於檔案偏移 `303687`，
同場契約在 `304236` 明言雇用 Bakali 嚮導與戰士；按語境校正為蜥蜴人。
獨立 DRAGONMAN 選單鍵只有區塊 33、34 兩個來源，分別屬上述追逐與成年試煉，亦採蜥蜴人。
這是來源位置與文字語境的校讀，未宣稱已解出敵人結構或正常遭遇。

後續補上海底救援、菲斯特隆、哈德弗克語教學、數樹葉、新奧利姆通行證與囚犯事件的短句。
長矛、踢開術、牛精、鐵魔像、骷髏戰士及欺瞞戒指沿用既有術語。
LIMENE、BILBARA、GEBENE、TOKTOKCHAKERI、WANTIL LIBENE 保留原詞形；只翻原有說明，
不增加答案提示或自動回答。金額與手札編號按原文核對，不改付費、計數與任務判定。
Mislaxia 拼字變體依同場 Mislaxa Talisman 翻譯，原文與物品識別值保留。
VHLARR MAGNAR 暫留原字形並註明未解，不補造意思。缺少主詞、跨段引號與其他片段仍須完整組句。

使用者再次要求對齊《幽靈騎士》後，回查其 `text/glossary.tsv` 中 266 筆人物、怪物及物品術語，
本作同名同類別的選用譯名全部一致，前作兩份術語來源的 SHA-256 與來源紀錄相符。
這是術語表對照，句內譯名另由完整譯表檢查與語境校讀把關，不代表所有場景已驗證。
新批次將 Huge Bat 的敘述統一為「大蝙蝠」；普通複數 ruffians 採「惡徒」，
不誤套前作手札 Ruffian「魯飛」。Iron Scale 依同場護符採「鐵製龍鱗」，不套防具「鱗甲」。
新增 Mimic「擬態怪」、店招 Shariskis「夏里斯基」兩個英文新譯，均標記待全書校讀。
前作全文表與本作手冊 OCR 未命中，不證明手冊沒有對照，也不據此推定遭遇結構或人物身分。

後續補入黑水坡、拜依歐爾、地侏堡壘、火焰塔、深淵與結局的短句，並補王宮與克理斯多芬
較長敘述。牛精、棘刺怪、火怪、牛頭人、各龍人族系、長劍、短劍與匕首按既有術語核對；
法術選項採解除法術、踢開術、閱讀魔法與火球。另依完整場所名稱修正一個「盜賊公會」句內用詞。
鯊魚人裝束依原文保留，不套用海底魚精的名稱。青銅龍蛋、銀龍蛋不當作貨幣，鎖鍊不當作鎖甲。
達米亞、瑟拉、卡斯頓、亞里沙諾利斯、安比烏汀未見前作或手冊 OCR 對照，記錄為英文新譯
待全書校讀；世次與原始識別值保留。VIGNNAK HURG 未解，保留原字形，不補造語意。
跨段引號、動態代詞與其他片段仍需整句校讀及正式顯示驗證。

陵墓、鷹峽、黑水坡、風船與深淵後段的較長敘述另補 504 筆。雷斯林完整姓名採
「雷斯林．馬傑里」，由既有詞根組合；前作 Majere 詞條屬神名，本作此處是姓氏，來源分開記錄，
不據此推定人物與神祇身分相同。完整姓名與達米亞的新增姓名部分仍待全書校讀。
斬首劍、詛咒時代、瑪爾弗與亞梅特那查魯標記為本作英文新譯，不冒充前作或手冊既有定名。
斬首劍名稱參照同場挑戰敘述，不代表已證實武器記錄、命中或斬首規則。
SARAKI 保留字形並翻出原文已有解釋；TRAKVALHISS DRAACKISS 未解，保留原形，
不推定是真名或咒語。呼語疑似誤用數字 0 的原文鍵 `ecl.87600d86b65255df4aec` 保留待核，
沒有在譯文塞入多餘數字，也未放寬數字檢查。其餘片段與開發訊息仍待分類，不從待譯數推算覆蓋率。

## 正常城內選單的七個新增原文鍵

正常進城收據另有七個直接像素座標的 `1212:03A0` 呼叫，內容是 Palace、Temple、Hall、Shop、
Inn、Bar、Leave。它們不是目前大寫劇本鍵的位元組同文，不能只用不分大小寫的替換冒充來源。
本輪將這七個實際字串加入介面原文表，保留英文大小寫與獨立 key，總候選由 8,381 增至 8,388。
原先 8,381 個鍵的原文與原始來源定位全部保留，原版資料雜湊不變。

來源是 `workplace/probe/story-return-sequence-20261022/trace.json` 及新補的訓練所路徑。
後者從同一正常入口到城內選單，在 575M 按一般 `h`，625M 回到可訓練角色的管理選單，
沒有選角色或實際支付訓練費用。觀測與無觀測控制組在十處的暫存器、RAM、色號、色盤、
按鍵及寫檔紀錄相同；未寫檔、沒有未實作服務。因此本場景 Hall 譯「訓練所」，
不套用大廳的場所描述，也不把進入選單當作已驗證訓練規則。

| 正常訓練所收據 | SHA-256 |
|---|---|
| `workplace/probe/story-hall-20261022/trace.json` | `6460ac64359118846bc75c11f29fd42424c0ec9291bcc990d8e001aa63f8624e` |
| `workplace/probe/story-hall-control-20261022/trace.json` | `7dd602b5c3ae9bf004072c69289783b0667cdaf1410a2a3258961b06fe6d00e0` |

625M RAM SHA-256 為 `8b401afcd09716205e10c447a29f51752a4aadafa914f63352e5d2dcb56b939e`。
[story-live.sh](../../tools/story-live.sh) 先 `probe-build`，再以 `hall-probe 新名`、
`hall-probe-control 另一新名` 重生這條原版路徑。

候選 JSON 仍屬研究資料。本輪為它加上執行期來源位置，正式 TSV 的 `key`、`text` 兩欄不變。
執行期來源使用 `file: runtime RAM`、明示位址空間、segment、offset 與螢幕位置；沒有
`file_offset`，不把 RAM 位址偽裝成 EXE 偏移。原始檔來源與 RAM 來源分別排序。
觀測另保留 trace SHA-256、虛擬步數及指標。實際 RAM 字串已證實，回到原始檔的生成來源仍未知。

[text_catalog.py](../../tools/text_catalog.py) 的新入口只接收符合 EXE 身分、已核對呼叫入口、
完整 ASCII literal、直接座標及傳統記憶體範圍的觀測。格式出口、編碼座標與未結束字串不收。
[test_runtime_label_catalog.py](../../tools/test_runtime_label_catalog.py) 以真實遊戲及正常觀測衍生
八項檢查，涵蓋正例、編碼座標、格式、結尾、錯誤入口、指標失配、顯存及 EXE 失配。
所有舊候選在邊界案例中保持不變；拒絕的批次沒有產出原文表。缺少真實輸入時明確略過。

新增來源先在 `workplace/probe/catalog-runtime-ui-20261022/` 比較後才更新目前表。
`before/` 保留四份舊來源產物與 6,040 筆舊譯表，`after-hall/` 保存新產物，
`catalog-comparison.json` 記錄新增鍵、原始定位保護與 trace 雜湊。正式擷取 wrapper 已納入
正常進城及訓練所觀測，重跑四份來源產物逐 byte 相同，譯表不變。

本輪譯文新增七個介面鍵及 91 筆城鎮／海底短句與選項。牛精、多頭龍、雙頭怪、龍族、
鯊魚人、大蝙蝠、大鱷魚及山怪沿用既有術語；沒有改寫怪物記錄或原版比較字串。
STAND 兩處與後退或逃離相對，採「留在原地」；POUND 依上閂木門場景採「用力敲門」。
店家稱呼 fine people 是客氣話，譯為「貴客」，不套用品質「精良」，以固定雜湊記錄一則校讀。

該批合併後的 6,138 筆譯表 SHA-256 為 `2f58ac656fd8cb04edd782ef9583c03af01c68d26c34ada9c17b3dc870e01914`。
本輪 98 個新鍵不重複，舊 6,040 筆譯文逐筆未變，七段已擷取中文畫面的文字依賴也未變。
新譯文尚未接入視窗；不把舊畫面收據當作新 98 筆的顯示證據。當時未合併有 2,250 個原始候選，
含 2,249 個一般候選與 1 個名稱候選，仍不是漏譯數或完成比例。

## 2026-10-22：堡壘至深淵的操作與引語

新增 `story-citadel-abyss-actions.tsv` 的 163 筆，來源為 ECL 區塊 38 至 47 的已擷取候選。
`citadel-abyss-actions-review-input.json` 保存所選每筆完整來源、偏移、原始字串雜湊及 ECL
輸入雜湊，另保存合併前譯表。這是靜態文字語境校讀，不把相鄰字串當作已證實的執行分支。

行動選項涵蓋地侏機器、爆炸罐、升降梯目的地、陷阱、火焰塔與傳送門。
CHARM、BOLT、DISPEL、MISSILE 的同場完整詢問列明四個法術，因此分別採前作
「迷惑術、閃電術、解除法術、魔法飛彈」，不把 BOLT 當成普通弩箭。
PICK HIM UP 的相鄰來源是架上的灰貓，後句有眨眼與喵叫，譯為「抱起牠」。
LET THEM 的前後是奉命陪同、離開或跟隨的地侏隊伍，譯「要讓他們同行嗎？」。

Tas 暱稱沿用「泰斯」，完整 Tasslehoff 沿用「泰索何夫」。波橘克、特里摩爾、伯基藍那摩、
聰明地侏及雷斯林均用既有術語。新增三則固定雜湊校讀：蜘蛛提問中的 RUFFIANS 是因犯罪
受罰的選項，譯「罪犯」，不套用人物「魯飛」；砍斷及一擊斬斷的 chains 是抑制魔法的鎖鍊，
不套用「鎖甲」。原版字串、答案、比較與物品識別值均未修改。

本批先用純校讀模式檢查，再於零錯誤、零未處理術語警示後合併。
舊 6,138 筆逐筆未改，該批合併後共 6,301 筆，SHA-256 為
`3f31e935c7992ca72a650399c179f562d4071aecffba9b52c1479d2b697dac9e`。
全表回驗 0 格式錯誤、0 未處理術語警示，258 則逐句校讀覆蓋 264 次匹配，字型覆蓋通過。
原文表與術語表沒有變動；該批十二項角色選單依賴及既有 GUI／原版重播收據另回驗通過，
沒有重寫歷史畫格。當時候選重新分批後為 2,086 個一般候選及 1 個名稱候選，仍含雜訊及切片。

引語前導與動態主詞後的片段保留各自 key，尚未建立全遊戲組句、分頁與正式呈現。
本批沒有把獨立段落校讀稿合併或重複計數，也沒有把 163 筆當作已驗證的玩家功能。

## 2026-10-22：海底、港口與燈塔的敘述片段

`story-sea-lighthouse-clauses.tsv` 補上 116 個新鍵，並修正一個既有鍵，共 117 筆。
來源為 ECL 區塊 9 至 12 的候選，保留所有來源位置及合併前快照。
新譯包含萊里恩反應、運蛋結果、精靈救援、港口引語、蛛網、落穴、怪機械與幽魂守衛。
原始字串與遊戲判定保持原樣，未將這些片段自動串接或作正式呈現。

`MOVE IN FOR THE KILL!` 原譯含原文沒有的受詞「牠們」，像在命令玩家攻擊。
相鄰原文的主詞為大甲蟲，支持第三人稱敘述的強推論；改為「逼近，準備痛下殺手！」，
移除錯添的受詞。三段來源位於 ECL 檔案偏移 `91718`、`91745`、`91775`。
最後一段前的 `18 33 18 11` 位於 `91771`，其中 `33` 的執行語意未知；沒有因此擴張相鄰
段落合併器，也沒有將靜態語法判斷宣稱為正常玩家路徑收據。原獨立段落稿仍保留待驗。

CARRY 的三個來源均為精靈孩童或傷者救援，採「抱走」，不套一般物品搬運。
雙輪交通增強器、多頭龍、大蜘蛛、大蝙蝠、萊里恩、克萊西亞、鐵虎克與魚精沿用既有名稱。
新增三則固定原文與譯文雜湊的校讀：darts 是精靈迅速游走，不是飛鏢；呼喊中的 dragons
採龍群，類名龍族不變；giant 形容雙頭獸人的身形，不據此推定巨人族或雙頭怪記錄。

另回查取蛋提示：`AN`、`OTHER`、`EGG?` 在區塊 9 分開，`OTHER` 同鍵在區塊 35 又用於
項鍊選單。不能全域改成「另一顆」，依呼叫來源選譯與完整組句仍待驗。本批沒有修改這些
舊鍵或補譯該尾段，也沒有把未知控制碼改成自動接續。

本批先純校讀，再於零錯誤、零未處理術語警示後合併。除上述一個修正外，舊 6,300 筆逐筆
相同。該批譯表為 6,417 筆，SHA-256 為
`e9ebb4a62ae7756a1466fcc916bf6f7b866eaa02768a1db4bb856864cac86f03`。
全表字型、格式及術語檢查通過，261 則校讀覆蓋 267 次匹配，前作 266 筆共通術語仍為零差異。
原文表與原版 ECL 雜湊未變。剩餘為 1,970 個一般候選及 1 個名稱候選，仍含雜訊及切片，
不作漏譯數或完成度分母。正式組句、分頁、其他選單、手札、戰鬥與存讀檔仍未完成。

## 2026-10-22：正常營地與存檔的短標籤

[研究 003](003-startup.md#2026-10-22原版旅店存檔與冷啟動讀回) 的正常旅店與存檔 J 路徑，
新增 View、Magic、Rest、Alt、Fix、Load、Save、Yes、No 九個實際大小寫來源，
另記錄 A 至 J 十個槽位字母。來源均為已核對 `1212:03A0` 的直接 ASCII literal，
保留當時 RAM 指標與原始座標，不用大小寫折疊冒充原文，也不偽造原始檔偏移。

九個新鍵採「檢視人物、魔法、休息、設定、治療、讀取進度、儲存遊戲、是、否」。
View、Magic、Rest、Alter、Fix、Save 沿用《幽靈騎士》術語；本作按 Alt 後顯示 Order、
Drop、Speed、Icon、Level 等選項，支持使用既有「設定」。本輪沒有操作 Fix 或改治療規則。
槽位字母保持原字形，不列入九筆中文譯文數，也不改按鍵與原版存檔識別值。

擷取前四份來源產物與 6,417 筆譯表保存在 `workplace/probe/catalog-runtime-save-20261022/before/`。
比較確認舊 8,388 鍵的字串、類別、雜湊及原始定位全部保留，新增十九個來源鍵，共 8,407 個。
其中九個短標籤已補譯，十個字母留原版。正式原文／譯文兩欄格式不變。
擷取入口已納入 `save-load-observe-r2-20261022/trace.json`，乾淨重跑四份產物逐位元組相同。
新原文表 SHA-256 為 `c998b6f2232d41ddbae8bdfd9c3ae59ad4c873c2be09d32a2589fa3c6a01a479`。

該批合併後譯表為 6,426 筆，SHA-256 為
`485bc3898fa6920e4531357632e80b44b507043edd9ef7d67329bd03045be2a3`。
舊 6,417 筆逐筆未改，格式、實際字型覆蓋與術語檢查通過，261 則校讀覆蓋 267 次匹配。
剩餘為 1,980 個一般候選及 1 個名稱候選，含十個槽位字母、雜訊與切片，不當作漏譯數。
本輪只觀測原版與補譯短標籤，未接入營地中文、格式模板、完整組句或 GUI 存讀檔。

## 2026-10-22：菲斯特隆實驗室與燈塔敘述片段

`story-fastillion-lighthouse-clauses.tsv` 共 206 筆，新增 204 個鍵，另修正兩個既有鍵。
來源為 ECL 區塊 13 的靜態文字，部分同鍵另出現在區塊 12；每個來源位置均保留於
`fastillion-lighthouse-clauses-review-input.json`，不以相鄰字串推定已驗證的執行組句。
合併前 6,426 筆快照及允許修改的兩鍵另存，原始 ECL、catalog 與原文表雜湊未變。

新譯涵蓋精靈女子的求助、菲斯特隆工作與交付鑰匙、贊托斯對話、能量漩渦、鋼顎陷阱、
落穴、石像、拉桿、樓層提示及怪物遭遇。菲斯特隆沿用已核對手冊的譯名，贊托斯仍為
既有英文新譯待全書校讀。鐵魔像及地侏詞根沿用《幽靈騎士》；牛精、多眼怪、野豬怪、
火元素沿用目前已核對的本作術語，不因字面或外形描述改造怪物種類。

兩處舊譯修正均有同場完整來源：讀清單片段移除重複代詞，接續菲斯特隆皺眉後的動作；
鐵魔像的後段改為站在「門前」，補回上一片段 before 的位置關係。
其他舊 6,424 筆逐筆相同。金屬公牛、牛精石像與怪物記錄分開描述，沒有推定新規則。

新增四則固定原文與譯文雜湊的語境校讀。鋼顎及尖刺的 steel 指鋼鐵材質，並非鋼幣；
墜落時 armor 的撞擊聲用敘事詞「盔甲」，裝備類名「護甲」不變。沒有放寬術語檢查器。
先純校讀達零錯誤、零未處理警示，確認譯表仍未變，再依已確認譯風合併。

合併後共 6,630 筆，SHA-256：
`eb722060e1df0cbae4469b2c4beb8ba3c651a22c096c62b9e35fe3d59335102e`。
全表格式、實際字型及術語檢查通過，265 則逐句校讀覆蓋 271 次匹配；
《幽靈騎士》266 筆共通人物、怪物與物品術語對照零差異。
差分結果位於 `story-fastillion-lighthouse-clauses-comparison.json`。
剩餘為 1,776 個一般候選與 1 個名稱候選，仍含雜訊、識別字及切片，不換算漏譯數。

既有營地十項依賴及其畫格／存檔收據回驗通過，未改歷史畫格或重跑未變的 runtime。
本批沒有接入新畫面，分段、動態角色名稱及原始 key 均保留。
完整組句、正式分頁、其他選單、手札、戰鬥及中文讀檔仍未完成，未進行 HD。

## 2026-10-22：森林、哈德弗克與眾樹之母的片段

`story-hulder-forest-clauses.tsv` 補上 93 個新鍵，另修正 2 個舊鍵，共 95 筆。
來源主要為 ECL 區塊 14 至 16，包含艾莉亞低語、狩獵與食物、宴席、國王覲見、數葉任務、
戒指、龍之護符及離別敘述。防禦選項亦出現於區塊 42、45，採通用「防禦」。
完整來源、所有定位、原文與原版雜湊均保存在 `hulder-forest-clauses-review-input.json`。
這是靜態語境校讀，沒有推定新的分支、執行組句或規則。

泰索何夫沿用前作名稱，姓氏「柏伏特」沿用現有全名詞條，仍保留先前英文新譯的校讀限制。
坎德人沿用《幽靈騎士》，艾莉亞及魯明那里沿用既有術語。狩獵的 GAME 譯「獵物」，
不套用一般「遊戲」。樹葉、砍樹與放火選項依同場來源翻譯，不改答案或樹葉數量判定。

本次發現劇情 JOIN 由前作同文沿用成「集合物品」。回查該 key 的全部三個來源：
區塊 15 檔案偏移 `128373`、`129474` 是宴席邀請，區塊 17 偏移 `151527` 是加入喜斯侍奉。
依三處相鄰對話的強推論，改採通用「加入」，不改介面另一個同字 key。
此為文字語境證據，尚非三處選單的動態顯示收據。
另一個舊鍵補回 WORDS 的「話」，保留泰索何夫不耐煩時脫口而出的受詞。
合併前 6,630 筆另存快照，其他 6,628 筆逐筆相同。

七種獨立謎題字形保留原版：LIMENE、GEBENE、BILBARA、SHUWARA、HOLBANI，
以及帶引號的 MAHENE 提問與 GEBENE 呼喊。含 GEBENE 的問候句只翻周圍敘述。
這七個候選不加入中文筆數，不移除來源，也不宣稱它們是漏譯。
另有 `SP`、`SH` 及夾雜 `A4BRB#D` 的長切片，保留為未知，不猜方向或補造原句。
原始 entries、分類理由及未合併檢查保存在本批輸入與差分收據。

先純校讀至零錯誤、零術語警示，再依已確認譯風合併；本輪沒有新增或放寬術語豁免。
該批合併後共 6,723 筆，SHA-256：
`1ac0096b2a9af0cde2d2bfb24ab6093565d53c731e19dd33b8491bb004c5eb5d`。
全表格式、字型及術語檢查通過，265 則校讀仍覆蓋 271 次匹配，前作 266 筆共通人物、怪物
與物品對照零差異。差分收據為 `story-hulder-forest-clauses-comparison.json`。
候選重分批後為 1,683 個一般候選與 1 個名稱候選，仍含已知保留字形、雜訊及切片，
不換算漏譯數。既有營地十項的目前文字依賴與畫格／存檔收據回驗通過，未改歷史畫格。

新譯尚未接入新畫面。完整組句、正式分頁、其他選單、手札、戰鬥及中文讀檔仍未完成，
劇情與營地最終字級未定案，未開始 HD。

## 2026-10-22：城內、神廟、門鎖與魯明那里燈塔片段

`story-city-luminari-clauses.tsv` 共 168 筆，新增 165 個鍵，另修正三個既有鍵。
來源主要為 ECL 區塊 12、17 至 19；TRAIN 與魯明那里獨立名稱另有區塊 1 來源，
共用門鎖文字亦出現在區塊 39，REBELS 選項另見區塊 21。完整原文、所有位置、ECL 及
catalog 雜湊保存於 `city-luminari-clauses-review-input.json`，原始資料未改。
區塊 1 的除錯樣式鄰近字串不當成正常玩家顯示收據；本批只補譯文。

內容涵蓋路人反應、抓丁隊、店家、神廟祝福、讀取命令、訓練、門鎖、守衛及囚犯，
燈塔部分補上蜘蛛、蝙蝠、甲蟲、地侏、屏障、拱門與幽魂守衛。
魯明那里沿用已核對的手冊詞根；本次將區塊 1 的獨立名稱納入譯表，未新增術語或改名。
喜斯、米絲拉克莎、西洛爾、雙頭怪、觸手怪、紫蠕蟲等沿用現有表。
法術 Knock 為前作「踢開術」，實際敲門動作依原文譯「敲門」；不改兩者的原版判定。

三處舊譯依相鄰來源修正：寶石堆改回名詞片段，銜接「那裡有」；
通行敘述移除重複的「似乎」，接續前段「看來」；同一位低階祭司的稱呼統一為祭司。
合併前 6,723 筆另存快照，除此三鍵，舊 6,720 筆逐筆相同。
字串仍各有原始 key，沒有把靜態相鄰當作已證實的完整訊息或分頁邊界。

新增兩則固定原文與譯文雜湊的語境校讀：地侏口袋裡的小錘屬工具敘述，
不套裝備名「鐵錘」；中文語序把小錘放到下一個口袋片段，必須連讀，執行組句仍待驗。
審判官交付的 chain 是拴著囚犯的鐵鍊，不是鎖甲。舊 265 則校讀的原始 bytes 完整保留，
快照另存，檢查器未放寬。

十八個候選保留未合併，理由與原始 entries 均存於本批輸入。
Pash 與 Ildamar 未找到已核對中譯；本輪查前作文字與本作 OCR 未命中，不證明手冊沒有。
紫蠕蟲屍體下的 STEEL 可能指鋼幣或鋼鐵物件，保留兩個相鄰鍵待獎勵／顯示證據，
不因出現在寶藏附近就定成鋼幣。THE 冠詞、短識別值及夾雜指令樣式的破碎切片也未猜譯。

先純校讀至零錯誤、零未處理術語警示，且目前譯表雜湊未變，再依已確認譯風合併。
該批合併後共 6,888 筆，SHA-256：
`164e28fbe20f322a7ddb0e690f7f983ff1fd1a7e648e1cb0bce59af48ad57248`。
全表格式、實際字型及術語檢查通過，267 則校讀覆蓋 273 次匹配；前作 266 筆共通人物、
怪物與物品術語對照零差異。差分收據為 `story-city-luminari-clauses-comparison.json`。
重分批後剩 1,519 個一般候選，已無可直接沿用的單獨名稱批次；這不代表新專名全數已校讀，
也不將候選數當成漏譯分母。MONCHA 的兩個未辨識名稱候選仍保留。

既有營地十項目前文字依賴與畫格／存檔收據回驗通過，歷史畫格沒有修改。
本批未接入新畫面，正式組句、分頁、其他選單、手札、戰鬥與中文讀檔仍未完成。
劇情與營地最終字級未定案，沒有開始 HD。

## 2026-10-22：王宮、克理斯多芬與陵墓片段及 URCHIN 語境修正

`story-palace-kristophan-clauses.tsv` 共 213 筆，新增 205 個鍵，另修正 8 個舊鍵。
主要來源為 ECL 區塊 20 至 27，涵蓋王宮守衛、制服、通行、門鎖、銅鑼、商販、競技場、
艾夏拉、圖書館、占卜、鑰匙、幽靈及擬態怪。共用片段的其他來源也完整保留，
不將它們當成已驗證的執行分支或正常玩家輸出。

### URCHIN 的描述譯名

舊四句把 URCHIN 譯成「小乞兒」，與同場文字不合。`ecl.553a46062973ce716c38`，
ECL 檔案偏移 `192761`，描述商販身上爬滿猴子般的小動物；選項 URCHIN 在 `192822`。
其他來源寫牠爬上肩頭、搶走蘋果、擠進鐵欄。六個鍵共同支持「猴形小獸」這個描述譯名，
推論等級為強推論。沒有宣稱已驗證動態圖像、物種、NPC 或 MONCHA 記錄對應，
也不冒充手冊既有中譯。前作文字查詢未找到同詞對照。

本次加入 `other` 類別，術語由 970 增至 971 筆；舊 970 筆的每個欄位保持不變。
兩個新鍵與四個舊鍵都用「猴形小獸」，差分收據逐一核對；目前段落候選原文沒有 URCHIN，
獨立段落校讀稿也沒有殘留「小乞兒」。歷史快照保留，未全域替換其他語境或重寫舊批次。

### 其他文字與語境

牛頭人、幽靈及擬態怪沿用現有術語。衣著講究的 bull 依同場牛頭人店主與牛頭人婦女文字，
作雄性牛頭人描述，保留強推論，不推定新的遭遇種類。
金色、生鏽與心形鑰匙對照同場敘述；法術仍用前作「踢開術」。
競技場的今日休館與暴動關閉兩種告示分開翻譯，沒有合併分支。

另外四個舊鍵修正動態銜接：DOES 與後段提問配合；艾夏拉摟住角色後接續動作，移除重複
代詞；UP／DOWN 改採「上／下」，可接樓梯命令及兩處火焰平台方向。所有原始判定不變。
八個舊鍵之外的 6,880 筆譯文逐筆相同，合併前 6,888 筆另存快照。

新增四則固定原文與譯文雜湊的語境校讀：銅鑼吊鍊不是鎖甲；飲料的 belt 是喝一口，
不是腰帶；鋼製門的 steel 是材質；咒罵龍的話採一般「龍」，正式龍種譯名不變。
舊 267 則校讀 bytes 完整保留並另存快照，沒有放寬檢查器。

三十二個候選保留未合併，完整 entries 及理由見本批輸入。GLADE 是否指特定地點短名、
HER 的賓格／所有格語境、開發者除錯訊息及破碎切片未猜補。原文表、catalog 與 ECL
雜湊保持不變。相鄰語序校讀不代替完整訊息、清除或分頁的動態驗證。

本批先純校讀至零錯誤、零未處理術語警示，再依已確認譯風合併。
目前共 7,093 筆，SHA-256：
`be9ca7389f75705dc18b554359c8a5a6e848284d2b9d4c254d927727795e567c`。
全表格式、實際字型及術語檢查通過，271 則校讀覆蓋 277 次匹配；前作 266 筆人物、怪物與
物品術語對照零差異。差分收據為 `story-palace-kristophan-clauses-comparison.json`。
剩餘 1,314 個一般候選仍含雜訊、保留字形及切片，不作漏譯分母。

營地十項目前文字依賴與畫格／存檔收據回驗通過，歷史畫格未改。
新譯尚未接入新畫面，正式組句、分頁、其他選單、手札、戰鬥與中文讀檔仍未完成。
劇情與營地最終字級待定，未開始 HD。

## 2026-10-22：鷹峽、通行證與黑水坡片段補譯

`story-hawkbluff-blackwater-clauses.tsv` 新增 229 個鍵，主要來自 ECL 區塊 28 至 35，
包含陵墓收尾、鷹峽守衛、暗門、監牢、喜斯神殿、珠寶商、蜥蜴人議會與巨龍衝突。
每鍵保留全部來源及原始定位；同鍵出現多次不增加翻譯筆數。
合併前 7,093 筆快照逐筆比較一致，沒有修改任何舊譯。

巫妖與既有怪物、武器及人物仍沿用《幽靈騎士》術語，查凱斯、波橘克、特里摩爾、
波追那斯及阿默羅卡依現有核對來源。查凱斯同場新增一個 DRAGONMAN 片段作「蜥蜴人」，
同場成年試煉明言 Bakali，屬靜態語境的強推論；不全域更動 Draconian「龍人」。
包含 NAAMIL 部族的新長句仍保留待查，不補造手冊譯名。

通行證八種帶空白的詞根，以及六個獨立名稱保留英文提示，例如鑰匙孔、燈籠及羽毛筆。
PASS、RELEASE 附中文意思與英文，保留原版輸入所需線索。沒有改動答案比較或原版資料，
也未宣稱已動態驗證珠寶商的所有輸入分支。另一個跨場景的 SWORD 鍵仍待查，
不把通行證或特定武器名稱全域套用。

新增八則固定原文與譯文雜湊的語境校讀：龍穴、個體或群龍的敘事，以及龍鱗道具。
後者不是裝備鱗甲。旅店老闆直接對齊既有術語，沒有建立豁免。
舊 271 則校讀的原始位元組完整保留；術語表 971 筆及檢查器未變。

四十四個候選保留未合併，每項來源與理由在本批輸入。交易數量、價格與受詞須重排，
不能只把 FOR 等片段定成一個中文詞；短識別字、開發者除錯訊息及破碎切片也未猜補。
手札第 2 則的動態主詞片段另做語序校讀，但完整執行組句與分頁仍待驗。

本批先純校讀，確認原譯表雜湊未變，且零錯誤、零未處理術語警示後才合併。
合併後共 7,322 筆，SHA-256：
`0d2fb6cbd7c2355059fa4029d9c2c09b94a61e8adb2fefe1f060b1e2e23196d8`。
全表格式、實際字型及術語檢查通過，279 則校讀覆蓋 285 次匹配；前作 266 筆人物、怪物與
物品術語對照零差異。原始 ECL、catalog 及原文表未變，差分收據見本節同名 comparison。
重分批後剩 1,085 個一般候選，仍含雜訊、保留字形及切片，不作漏譯分母。

營地十項現行文字依賴與既有畫格、狀態及存檔收據回驗通過，歷史畫格未改。
新譯尚未接入新畫面，正式組句、分頁、其他選單、手札、戰鬥與中文讀檔仍未完成。
劇情與營地最終字級待定，沒有開始 HD。

## 2026-10-22：拜依歐爾、造船廠與焰息片段補譯

`story-baior-rebuilding-clauses.tsv` 共 314 筆，新增 312 個鍵，修正 2 個舊鍵。
來源為 ECL 區塊 36、37，包含鯊魚人巡邏、村民、造船廠、安希拉、圖書館、反抗、
重建與焰息的對話。保留原始頭尾空白、來源定位及全部相鄰鍵，中文按敘事語序校讀。
四個短識別值或混入疑似指令的破碎切片未猜補，完整條目及理由見本批輸入。

珍妮佛沿用《幽靈騎士》已校讀字形，不據此認定為同一角色。安希拉、拜依歐爾及
阿迪那那出沿用現有手冊對照；歐雷格、漢姆漢德、艾瑞克．史壯邦德與焰息仍為英文新譯，
待全書校讀。鯊魚人的裝束與扮裝情節不被當成新物種證據；武器與怪物術語表未改。

兩個舊鍵依唯一來源的前後文修正：長老代表團由安希拉帶領，補回領隊關係；
HOW 後的 DO YOU RESPOND 改為「回應？」，與前段共同構成「你們會如何回應？」。
不再誤作是否題。其他舊 7,320 筆逐筆未變，合併前 7,322 筆另存快照。
原文 THE IS STUCK 缺少名詞，依同場鎖住的暗門、強行開門、撬鎖及踢開術選項，
中文補作「門卡住了」，明列強推論。沒有改原始英文或原版程式。

新增十則固定原文與譯文雜湊的語境校讀：九處個體或群體的龍不套角色類名「龍族」；
旅店主人稱讚來客的 fine folk 採「貴客」，不套物品品質「精良」。
拆行的姓氏、護手與安希拉姓名已連讀核對，沒有新增名稱豁免。
舊 279 則校讀的原始位元組完整保留，術語表仍為 971 筆，檢查器未改。

先純校讀至零錯誤、零未處理術語警示，確認現行譯表雜湊不變後才合併。
目前共 7,634 筆，SHA-256：
`aaa78153b7e3665103051ff6e89a0d45562fedfbdb7c6dfcfb1924c5a23b7941`。
全表格式、實際字型及術語檢查通過，289 則校讀覆蓋 295 次匹配；前作 266 筆人物、怪物與
物品術語對照零差異。原始 ECL、catalog、原文表及術語表未變，差分收據見本批 comparison。
重分批後剩 773 個一般候選，仍含雜訊、識別字及切片，不作漏譯分母。

本批是靜態組句校讀，未增加正常玩家畫面或分頁證據。營地現行十項依賴與既有畫格、
狀態及存檔收據另回驗；正式組句、分頁、其他選單、手札、戰鬥與中文讀檔仍待完成。
劇情與營地最終字級待定，沒有開始 HD。

## 2026-10-22：要塞、火焰塔與深淵片段補譯

`story-tower-abyss-clauses.tsv` 共 96 筆，新增 94 個鍵，修正 2 個舊鍵。
主要來源為 ECL 區塊 38 至 47，涵蓋要塞、升降臺、毒針、地侏戰士、救火、風船、
克萊西亞、火焰平台、戴諾、雷斯林與傳送門。每鍵保留全部原始來源及定位。
治療與藥劑兩段連讀作「治療藥劑」，對齊《幽靈騎士》。葛雷沙尼奇、赫倫比許諾格、
奧拉克龍人及其他人物沿用既有術語與來源等級，沒有新增名詞或改動 971 筆術語表。

兩個舊鍵配合前段修正：地侏主詞之後接「同伴」，移除重複主詞；
怪聲之後接回聲音來自身後的方位。其他舊 7,632 筆逐筆未變，合併前 7,634 筆另存快照。
樓層前導採「目前樓層：」，人數片段按「同行的有 N 名地侏戰士。」校讀，沒有改原數值。
角色姓名、代詞與數值的正式組句、英文複數字尾及清除邊界仍待執行驗證。

新增三則固定原文與譯文雜湊的語境校讀：兩處龍採敘事個體或群體用字；
解除法術作用的發光球體按形狀描述，不推定為物品索引中的 Orb 寶珠。
舊 289 則校讀的原始位元組完整保留，檢查器未放寬。

五十二個候選保留未合併，逐項理由及來源見本批輸入。範圍包含短識別字、破碎切片、
共用代詞、單複數及最高級片段，以及須確認分支和重排的穿牆、通風井升降與聲音方位。
特殊詞與呼告保留原字形，未補造中譯或輸入角色；一處呼告含 0／O 字形疑問，
沒有為通過數字檢查而硬添字元。這些項目不被當作可直接合併的漏譯。

本批先純校讀至零錯誤、零未處理術語警示，確認舊譯表雜湊未變後才合併。
目前共 7,728 筆，SHA-256：
`f7178725213d314f68634292f3255eaaf48707ebb7b3dcbe6566d3bf38b2ef75`。
全表格式、實際字型及術語檢查通過，292 則校讀覆蓋 298 次匹配；前作 266 筆人物、怪物與
物品術語對照零差異。原始 ECL、catalog、原文表及術語表未變，差分見本批 comparison。
重分批後剩 679 個一般候選，仍含雜訊、識別字及切片，不作漏譯分母。

營地十項現行依賴與既有畫格、狀態及存檔收據回驗通過，歷史畫格未改。
本批是靜態組句校讀，未新增正常玩家畫面；正式組句、分頁、其他選單、手札、戰鬥與
中文讀檔仍待完成。劇情與營地最終字級待定，沒有開始 HD。

## 2026-10-22：Shield 的背包與法術書語境

本輪沒有增加譯文筆數。現有 7,728 筆與 971 筆術語雜湊未變，
《幽靈騎士》既有 Shield 的「盾牌」及「魔法盾牌」兩種用法均保留。
剩餘 302 個介面候選包含識別字、錯誤訊息及同文歧義；先沿實際玩家路徑追查 Shield，
沒有把全部候選硬譯或改稱已完成。

### 原版路徑與觀測隔離

[ui_context_probe.go](../../tools/ui_context_probe.go) 是 DRAFT 只讀觀測器，
由已正常形成的旅店快照 `save-load-city-20261022/inn-menu.state` 接續。
快照步數為 665M，SHA-256 為 `4bcda89c43b66693e1d63c24104d003de5347df70149a5db035af549972677b6`。
只送一般 View、Items、Exit、方向鍵，以及 Magic、Memorize 閱覽與退出。
沒有改人物、發物品、提交記憶選取、施法、休息或寫遊戲存檔。
快照接續不被當成新的冷啟動 GUI 證據。

| 路徑 | 觀測結果 | 與無觀測控制組比較 |
|---|---|---|
| 六名隊員逐一 View／Items／退出 | 四次已裝備的 Shield +2／+3 | 29 個檢查點相同 |
| 第三名隊員 Magic／Memorize／方向鍵／退出 | Shield 在法術書中兩次重畫 | 21 個檢查點相同 |

每個檢查點均比較暫存器、1 MiB RAM、色號、色盤、消耗按鍵、寫檔紀錄及實際 320×200 PNG。
上表兩條流程的印字呼叫均已配對返回，沒有未實作服務或遊戲寫檔。
重畫次數不被當成不同法術數；沒有驗未裝備的盾牌或其他加值。

### 印字前已有完整緩衝區，但返回位址不足以分義

在已驗的 `1212:03A0` 入口，六次印字都有完整 NUL 結尾緩衝區，
至首個 `13C7:0C96` 字元呼叫皆相差 565 道指令。兩者的格式都為 `%s`，
呼叫端返回位址都為 `0B72:027C`，不是兩個可直接分義的呼叫端。
背包文字為帶 Yes、Tab 及加值的整列，法術書文字為 Tab 後的 Shield。
暫存緩衝區只作本次定位，不把堆疊位址或文字前綴升格為全遊戲的語意識別值。

正式接入必須保留介面／欄位語境，再選取前作的「盾牌」或「魔法盾牌」。
共用原文鍵 `ui.480d4be7d61fe52bc317` 仍未填入單一譯文；本輪沒有改 catalog 或資料格式。
列表欄位組句、未知介面回退、清除與提早提交仍待規格及實作，不以觀測成功宣稱已中文化。

### 原始檔與 RAM 的內容對照

| 原始 DQK.EXE 檔案偏移 | 靜態相鄰語境 | 兩條路徑的 RAM 實模式線性位址 |
|---|---|---|
| `421649` | Read Magic、Shield、Shocking Grasp | `0x368D1` |
| `429507` | Plate、Shield、Scroll | `0x38783` |

Shield 前後共 55 bytes 的視窗在兩份最終 RAM 各只有一個完全相同的匹配。
位元組相同已證實；由相同內容推回來源屬強推論，未追寫入資料流或宣稱 IDA 直接 xref 已補齊。
英文原文、法術判定、物品、存檔及前作資料都未修改。

### 工具、收據與界限

Docker 入口為 [ui-context.sh](../../tools/ui-context.sh)，比較器為
[ui_context_check.py](../../tools/ui_context_check.py)。`build` 固定 dosgolem commit 與 image，
`run` 將輸入及原版唯讀掛載，只寫指定的全新輸出；`check` 核對原始畫面及狀態，
並拒絕尚未封閉的呼叫。先前七點探索收據雖狀態相同，仍有一個未封閉呼叫，已由檢查器拒絕，
沒有列入上述 50 點證據。公開 wrapper 另重跑背包控制組，29 點及四次來源匹配仍相同。

所有私有產物在 `workplace/probe/shield-context-20261022/`：

| 產物 | 職責 |
|---|---|
| `shield-context-evidence.json` | 工具、輸入及譯表雜湊，前作兩種譯名、已證實／強推論／未知與限制 |
| `all-party-items-request.json`、`third-grimoire-request.json` | 兩條一般按鍵腳本及原始快照身分 |
| `observe-all-party-items/`、`control-all-party-items/` | 背包原始呼叫、PNG、最終 RAM、快照及 29 個檢查點 |
| `observe-third-grimoire/`、`control-third-grimoire/` | 法術書原始呼叫、PNG、最終 RAM、快照及 21 個檢查點 |
| `items-comparison.json`、`grimoire-comparison.json` | 兩種語境的成對驗證、來源緩衝區與首字元之前的指令差 |
| `shield-source-windows.json` | 原始檔偏移、來源視窗雜湊及各 RAM 內容匹配 |
| `wrapper-control-all-party-items/`、`wrapper-comparison.json` | 正式工具入口的控制組重跑及比較 |
| `guard-check.json` | 真實未封閉呼叫收據被拒絕，沒有產生成功比較檔 |
| `ui-context-probe`、`build-info.txt` | 本輪探針及 Go 建置資訊；wrapper 重建的共用 binary 另在 `workplace/probe/ui-context-probe` |
| `input.json`、`view*`、`items*`、`*mage*`、`*magic*`、`*memorize*` | 保留的探索輸入、輸出與失敗分類；不冒充封閉呼叫驗證 |
| `issue7-before.txt`、`issue7-body.txt`、`issue7-comment.txt` | 本輪遠端 Issue 更新前內文、更新稿及進度留言 |

## 2026-10-22：列表繪製、捲動與 Shield 字形對照

接續上述原版路徑，擴充 [ui_context_probe.go](../../tools/ui_context_probe.go) 的只讀掛勾。
兩份請求及初始旅店快照不變，重新跑觀測／控制組；50 個檢查點的暫存器、RAM、色號、
色盤、按鍵、寫檔紀錄與實際 PNG 仍相同。這是同一路徑的補充驗證，不增加正常路徑覆蓋數。
兩組都沒有未封閉的印字、列表或捲動呼叫，沒有未實作服務或遊戲寫檔。

### 原始定位與已證實範圍

IDA Pro 9.4 匯出保留原始名稱與運算元；輸入、工具與一次性資料庫身分保存在下表的私有索引。
本表的執行期定位經本次 bytes 核對，其他 overlay 不套用 resident 位址換算。

| 原始定位 | IDA linear | 原始檔偏移 | 本次觀測與等級 |
|---|---|---|---|
| `sub_1A666`，`0B72:0046` | `0x1A666` | `0xCA66` | 已證實：較早的格式化入口已有完整列文字、欄列及顏色參數；六次 Shield 均早於原版首字元 |
| `sub_1B0A5`，`0C15:0055` | `0x1B0A5` | `0xD4A5` | 已證實：本路徑背包 6 批、法術書 9 批列表繪製；入口與 `0C15:0508` 的 `retf` 成對，覆蓋完整列印字及其中的捲動 |
| `sub_1DC47`，`0CEB:1E97` | `0x1DC47` | `0x10047` | 已證實：兩種列表共用回呼。原始 `ds:0A70Dh`、`ds:0A65Bh` 指向串列；從節點 `+4` 讀狀態並回傳 `+5` 文字。這個回呼不是裝備／法術分類器 |
| `sub_25A76`，`13C7:2F06` | `0x25A76` | `0x17E76` | 已證實：本次法術書 8 次呼叫搬移原版色號，前後整個複製區逐位元組相同；可見內容每次上移 8 個原生像素 |

列表結構 `+0Ah／+0Ch`、堆疊參數與呼叫前後 bytes 原樣保存。
本次可見它們隨捲動及選取更新；未將未驗欄位命名成正式資料格式。
印字返回 `0C15:042C／0460／01CE` 分別出現在一般列、反白或取消反白分支，
不能拿來區分裝備與法術。原有 BP 鏈記錄仍是候選，沒有宣稱完整堆疊回溯。

### 捲動必須納入中文位置

第二次法術 Shield 先在原生 `(16,112)` 取消反白，接著整列上移至 `(16,104)`。
捲動參數指定來源位移，可見像素朝反方向移動；此結論由原版呼叫前後色號核對，
沒有只憑參數名稱推定。八次複製區皆由原生 `(8,48,288,72)` 搬至 `(8,40,288,72)`。
只記印字座標會讓中文留在下一列，正式呈現必須處理同一批內後續的捲動。

原版第二個顏色參數 `8` 也不能直接當成背景色盤索引。六個字框實際背景皆為
RGB `(105,73,65)`，此次僅以字框內唯一的非前景色核對背景，不推定通用透明色規則。

### 離線字形對照與限制

[ui_context_preview.py](../../tools/ui_context_preview.py) 只讀已通過比較的原版畫面與
`workplace/translation/glossary.tsv`，從《幽靈騎士》的兩個既有詞條產生六張對照圖：
背包四張「盾牌」、法術書兩張「魔法盾牌」。語境由已知測試流程指定，沒有自動分類器。
工具核對比較收據、原始 PNG、字型及術語來源；只允許六字母原文的 96×16 像素框內改動。
加值、其他欄位及畫面逐像素保持相同，並納入取消反白後的捲動位置。

試排沿用粉圓 2.1，640×400、16 像素。兩種文字字墨分別為 32×15、64×15，
限於本次離線對照，不是字級定案。角色管理選單既有 20 像素決定不變。
這些圖片沒有遊戲接入、連續畫格、無閃爍、退出殘字或完整列表中文的驗收聲明。
譯文仍是 7,728 筆，971 筆術語及共用 Shield 原文鍵未改，規格 001 維持 DRAFT。

私有產物入口：

| 路徑 | 用途 |
|---|---|
| `workplace/probe/list-pane-context-20261022/list-pane-evidence.json` | 本輪來源、工具、輸入與有效收據雜湊，已證實範圍及限制 |
| 同目錄 `observe-items-scroll/`、`control-items-scroll/` | 六名隊員的一般背包流程，29 點原版狀態及畫面 |
| 同目錄 `observe-grimoire-scroll/`、`control-grimoire-scroll/` | 法術書閱覽及退出，21 點；8 次捲動前後的原始色號 `.idx` |
| 同目錄 `items-scroll-comparison-v3.json`、`grimoire-scroll-comparison-v3.json` | 目前檢查器的有效比較；含捲動區與 Shield 搬移核對 |
| 同目錄 `preview-items-v4/`、`preview-grimoire-v4/` | 目前離線對照圖與收據，左原文、右中文 |
| 同目錄 `guard-check.json` | 真實收據的五種變造都被拒絕，沒有產生成功收據 |
| `workplace/ida/list-pane-20261022/` | 一次性 IDA 查詢、原始 bytes、xref 及失敗紀錄；以證據索引區分有效輸出 |

Docker 重播及比較仍走 `bash tools/ui-context.sh run …`、`check …`。
離線預覽入口為 `bash tools/ui-context.sh preview OBS COMPARISON NEW_RESULT`，
三個路徑皆相對於 `workplace/probe/`，輸出必須全新。先 `check`，再以該次比較收據預覽。
不把舊版成功收據、失敗試排或不同檢查器的雜湊混用。
尚待辨識上層選單語境與離開邊界，再做真正視窗的連續畫格驗證；不再把共用回呼當作候選分類器。

## 2026-10-22：標題語境與列表視窗原型

接續列表與捲動證據，原版較早的格式化入口還提供可區分的標題來源：
背包是 `333E:4689`，法術書是 `333E:A7C4`。兩者都是標題列的直接格式字串，
與玩家名稱的 `%s` 參數分開。比對原始來源指標、NUL 字串雜湊及低位元組列號，
才設定物品或法術語境；其他標題輸出撤銷舊語境，不以玩家名字或共用列表回呼選譯。

本次新增工具均為 DRAFT：

- [ui_list_inputs.py](../../tools/ui_list_inputs.py)：由正式原文 TSV 或已驗 RAM 格式來源、既有術語 TSV 產生私有輸入。
  `Spells in Grimoire` 尚未登錄主 catalog，保留此來源差異；`%s` 是格式語法，不計為漏譯文案。
- [ui_list_live.go](../../tools/ui_list_live.go)：與既有 [early_text_live.go](../../tools/early_text_live.go) 共用前端。
  原版標題決定語境，原版列表、捲動與顯存寫入決定呈現交易；中文不回寫原版。
- [ui-list-live.sh](../../tools/ui-list-live.sh)：Docker 內準備、建置與一般按鍵重播入口。
  `prepare INPUT`、`build`、`en|zh STATE REQUEST INPUT NEW_RESULT [true|false]` 的路徑相對 `workplace/probe/`。
  最後一個參數只控制測試用的細分畫格，不決定物品或法術語境。
- [ui_list_live_check.py](../../tools/ui_list_live_check.py)：比較無觀測原版狀態、來源事件與真正 GPU 提交畫格。
- [oracle_video_observer.go](../../tools/oracle_video_observer.go)：僅由 Go build 的覆疊來源表掛入 `oracle`，
  導出固定 dosgolem 已有的 `Machine.ObserveVideoWrites`，不修改隔離 clone 或上游。
  此原型用它觀測 mode 13h 的原始視訊寫入，包含一般記憶體變值監看漏掉的路徑。

私有來源與輸出位於 `workplace/probe/pane-render-20261022/`，IDA 查詢在
`workplace/ida/pane-render-20261022/`，有效驗證結果在本節後續記錄。
標題來源辨識、文字框背景與填色要求的返回不能互相替代；原版尚未真正重寫舊字框前，
不得將填色返回直接當作中文清除完成。16px 仍是可丟棄原型，規格 001 維持 DRAFT。

實際觀測進一步確認本路徑使用 mode 13h 的非鏈結 256 色平面，先繪製另一頁，再改變可見頁。
例如法術書退出：原生填色起點 `(8,8)` 的首筆寫入位移為 `17026`，
依固定執行器的 `VGA.Unchained256` 公式，該頁基底為 `0x4000`，當時可見頁仍是 `0`。
因此直接把位移當成線性螢幕像素、或只監看一般 RAM 變值，都會漏掉這次清除。
這是執行器視訊寫入契約與原版呼叫的證據，不追查硬體逐週期時序。

原型現依原版整頁繪製請求失效舊語境，保留上一張完整畫面。
視訊 observer 對應四個平面及繪製頁，舊字框的全部 384 個位元組都有寫入，
且該頁已成為原版可見頁，才撤銷保留。上述退出在步數 `744367878` 滿足兩項條件，
早於新狀態欄首字。此方法不靠延遲幾幀、玩家姓名、按鍵次數或螢幕英文辨識。
未知頁基底、列距或分割線仍拒絕為有效原型，不推廣成任意 VGA 版面的契約。

| 流程 | 成對 GPU 畫格 | 保留完整畫格 | 原版狀態檢查點 | 列表退出清除 |
|---|---:|---:|---:|---:|
| 法術書 | 3,654 | 357 | 21 | 1 |
| 六人背包 | 3,804 | 407 | 29 | 4 |

兩組實際 GPU 讀回比較通過；保留畫格等於上一張完整畫面，其他畫格逐像素符合原版背景與
當前中文框。兩次法術 Shield 及四次裝備 Shield 都在原版首字元前選譯，裝備加值保持原樣。
原版狀態與無觀測組相同，列表退出後中文字框為空。
兩案合計 7,458 組成對畫格、50 個原版檢查點、5 次舊中文字框清除。
這仍是原有兩條正常路徑，沒有把重跑累加成新的覆蓋數。

有效法術書入口：`workplace/probe/pane-render-20261022/live-grimoire-en-r6/`、
`live-grimoire-zh-r6/`、`grimoire-live-check.json`。私有 `inputs/` 保存 UTF-8 原文及兩個譯文鍵、
標題來源、背景色號、字型及來源紀錄。`verify EN ZH INPUT CONTROL OBS NEW_RESULT` 可重跑比較。
其餘 UI 仍可能是英文；這只驗兩種 Shield 詞義及指定路徑，不是完整列表中文化、
冷啟動或實際 X11 按鍵驗收，也不是字級定案。

最終證據索引為 `workplace/probe/pane-render-20261022/pane-render-evidence.json`。
背包有效目錄為 `live-items-en-r7/`、`live-items-zh-r7/` 及 `items-live-check.json`；
`live-guard-check.json` 記錄錯誤語境、延後攔截、錯誤可見頁及英文漏出四種變造均被拒絕。
既有 20px 角色選單由原 Docker 入口重建，兩種語言模式都可執行，十二項事件及原版狀態相同；
只作本次共用前端的回歸抽樣，不重複宣稱原有冷啟動與 X11 驗證。

早期 `live-grimoire-*-r2/r3/r4` 退出清除未封閉，沒有列為成功收據。
背包 r6 的程式畫格比較雖通過，執行中編輯 shell 導致 wrapper 結尾讀取失敗；
固定腳本後兩組乾淨重跑 r7 成功，最終索引採 r7。這是驗證流程問題，沒有歸成遊戲缺陷。
本輪不再深挖共用列表 helper；下一步沿已證實入口擴充已觀測的完整物品與法術列。

## 相鄰劇情字串候選

[passage_candidates.py](../../tools/passage_candidates.py) 先核對 ECL 與 catalog 的來源雜湊，
再檢查 literal 的原始長度、6-bit 解碼及 HLIB 區塊邊界。只整理同一區塊內由 `11` 或
`18 11` 相鄰接續、且首段前為 `11` 或 `12` 的字串；遇其他位元組即停止，不跨過未知控制碼。
輸出保留每段來源鍵、檔案與區塊偏移、長度、前後位元組及工具雜湊。

目前有 322 組不重複候選，來自 344 個來源位置，共 875 次片段出現。
分組屬強推論，完整控制及分頁邊界尚未證實；每組都標記未經動態驗證。
兩種接續在受控副本中的繪製行為已另驗，見 [研究 004](004-story-text.md#2026-10-22相鄰字串的受控接續實驗)。
這個工具不修改 `en.tsv`、`zh-TW.tsv` 或原版資料，不把候選組數加入翻譯完成數。

已逐組檢視 322 組候選，其中 284 組補上獨立繁中校讀稿，包含可讀段落、引語前導與帶動態主詞的
片段。38 組的分支或上下文不足，理由與推論等級保存在 `passage-review/deferred.tsv`。
例如相鄰代詞或升降選項可能屬不同分支，不能因位元組相鄰就當作同一敘述；未證實的分支假說
保留待查，不丟棄原始字串，也不補造缺文。這批與既有字串內容有重疊，不與目前譯表筆數加總。

`translation_check.py --review-only` 只產生候選檢查及雙語稿，即使譯風已確認，也不讀寫既有
`zh-TW.tsv`、不建立 `completed/`。`translation.sh check-passages` 將目前譯表掛為唯讀，
只有 `passage-review/` 可寫。實際執行確認目前譯表雜湊不變，候選原文、來源快照、284 組校讀稿
及 38 組待查項目完整對應；格式、字型與術語檢查通過。靜態組句邊界仍為強推論，
尚未逐組動態驗證或接入正式顯示。

本批目視核對手冊第 121 頁、旅行手札 56 的 Luminari「魯明那里」。手冊稱其為月亮，
燈塔名稱沿用此詞根，來源與掃描雜湊保存在術語表。Jennifer「珍妮佛」沿用《幽靈騎士》
`text/translit-names.tsv` 的已校讀譯字，不據此判定是同一角色。
雙輪交通增強器、贊托斯、歐雷格、漢姆漢德與艾瑞克．史壯邦德仍為英文新譯，待全書校讀。

Shield 的同一原文鍵有兩個 `DQK.EXE` 來源，檔案偏移分別為 `421649` 與 `429507`。
前者介於 Read Magic、Shocking Grasp，後者介於 Plate、Scroll。這是字串表相鄰資料的
靜態證據，支持法術與裝備兩種語境的強推論；當時只有靜態證據。後續背包及法術書的動態觀測見
[Shield 語境](#2026-10-22shield-的背包與法術書語境)；兩者共用返回位址，依語境選譯仍未接入。

## Docker 入口

[translation.sh](../../tools/translation.sh) 提供以下入口，原版及前作唯讀，僅本作研究工作區可寫。
停用網路、非 root，使用已存在且固定 ID 的 Pillow 與字型工具 image。缺少來源時停止。

```sh
bash tools/translation.sh extract
bash tools/translation.sh terms
bash tools/translation.sh seed
bash tools/translation.sh batches
bash tools/translation.sh passages
bash tools/translation.sh check-passages
bash tools/translation.sh check trial
bash tools/translation.sh check names
bash tools/translation.sh check ui-rest-combat
bash tools/translation.sh check ui-management
bash tools/translation.sh check prior-reviewed
bash tools/translation.sh check story-caves
bash tools/translation.sh check story-monsters
bash tools/translation.sh check ui-effects-trade
bash tools/translation.sh check ui-palanthas-observed
bash tools/translation.sh check ui-camp-save-observed
bash tools/translation.sh check story-city-sea-choices
bash tools/translation.sh check story-citadel-abyss-actions
bash tools/translation.sh check story-sea-lighthouse-clauses
bash tools/translation.sh check story-fastillion-lighthouse-clauses
bash tools/translation.sh check story-hulder-forest-clauses
bash tools/translation.sh check story-city-luminari-clauses
bash tools/translation.sh check story-palace-kristophan-clauses
bash tools/translation.sh check story-hawkbluff-blackwater-clauses
bash tools/translation.sh check story-baior-rebuilding-clauses
bash tools/translation.sh check story-tower-abyss-clauses
bash tools/translation.sh check story-undersea
bash tools/translation.sh check story-travel-rescue
bash tools/translation.sh check story-new-names
bash tools/translation.sh check story-coast-hulder
bash tools/translation.sh check story-forest-thenol
bash tools/translation.sh check ui-quests-magic
bash tools/translation.sh check story-palace-kristophan
bash tools/translation.sh check story-hawkbluff-blackwater
bash tools/translation.sh check story-citadel-finale
bash tools/translation.sh check story-tower-abyss
bash tools/translation.sh check story-palace-tombs-short
bash tools/translation.sh check story-tower-citadel-short
bash tools/translation.sh check story-context-labels
bash tools/translation.sh check story-undersea-caves-short
bash tools/translation.sh check story-hulder-caves-short
bash tools/translation.sh check story-aurim-palace-short
bash tools/translation.sh check story-kristophan-hawkbluff-short
bash tools/translation.sh check story-hawkbluff-blackwater-short
bash tools/translation.sh check story-blackwater-baior-short
bash tools/translation.sh check story-citadel-tower-prompts
bash tools/translation.sh check story-tower-abyss-prompts
bash tools/translation.sh check story-aurim-palace-narrative
bash tools/translation.sh check story-palace-kristophan-narrative
bash tools/translation.sh check story-tombs-hawkbluff-narrative
bash tools/translation.sh check story-blackwater-citadel-narrative
bash tools/translation.sh check story-windship-tower-narrative
bash tools/translation.sh check story-tower-abyss-narrative
bash tools/translation.sh check manual-name-corrections
bash tools/translation.sh check manual-deity-corrections
bash tools/translation.sh check term-corrections
bash tools/translation.sh check current-validation
bash tools/translation.sh test
bash tools/translation.sh test-runtime-labels
```

[translation_batches.py](../../tools/translation_batches.py) 依目前譯表生成後續批次。
`check` 只有在使用者已確認本作譯風後使用；它逐批合併譯文，保留先前批次。
重新生成批次會隨已合併譯文改變內容；已合併批次及其檢查收據自動保存到 `completed/`。
新譯文不得進入原版記憶體、檔名、條件比較或存檔，顯示接入仍依規格 001 的證據閘門。

[test_translation_guards.py](../../tools/test_translation_guards.py) 以最小 fixture 驗證正常批次、
孤兒 key、遺失格式參數、錯誤怪物名稱、不同級數及重複 key。失敗時必須保留原有譯表，
不得把拒絕批次存成完成收據。同句不同詞的校讀以 key 與 term 組合辨識；相同組合重複時拒絕。
術語規則改為每輪預先編譯，避免大量術語超出正規表示式快取容量後逐句重新編譯。
同一份 2,127 筆輸入的修正前後收據除工具雜湊外完全相同，8 項防錯測試通過。
這是工具防錯檢查，不是原版規則或遊戲接入驗證。

新增純校讀模式後，原有 8 項防錯測試及新增 1 項隔離測試均通過。
新增測試使用不同來源的既有譯表，確認已開譯風確認旗標的純校讀仍不改寫譯表或建立完成批次。
新增純校讀模式時的 6,040 筆已由預設模式回驗；目前 7,728 筆全表另已回驗通過。
新模式沒有放寬名稱、數字或格式檢查。

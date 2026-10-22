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
最初清單有 14 筆已觀測項目；正常進城、訓練所及營地存檔來源補入後，現為 51 個不重複
已觀測鍵，來源類別為 `ui` 41 個、`ecl` 10 個。89 次執行期 literal 觀測含重畫與槽位字母，
不當作 89 個功能。七段開場劇情是段落數，不與來源鍵數混列。
格式出口與編碼座標另行排除。這些正常觀測在清單中沒有遺漏，不能宣稱全遊戲擷取完整。

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
| `glossary.tsv`、`terminology-provenance.json` | 前作優先的 970 筆術語、手冊對照、英文新譯來源及歧義 |
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

目前已檢查並合併 6,630 筆本機譯文，包含首批試譯、前作同文校讀、角色與介面、洞穴、海底、
森林、菲斯特隆實驗室、西洛爾、鷹峽、黑水坡、地侏堡壘、火焰塔、深淵及部分結局分支。
逐批數量見上表及 WORKLOG，現行譯文以 `zh-TW.tsv` 為準，歷史批次不重複計數。
這是譯文進度，不能稱為 6,630 個功能、全遊戲覆蓋率或可玩中文化完成。
前作同文也可能依賴原場景；例如 TOWER 的前作譯文帶有特定塔名，不能直接帶入本作。
THE、SWORD、Shield 等片段或同文異義項目保留待查，不用前作的單一譯法補洞。
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

查凱斯的成年試煉同場明言 Bakali，因此該場景五個鍵的 Dragonman／Dragonmen 譯為「蜥蜴人」。
不把它們全域換成 Draconian「龍人」，其他場景仍依原文與語境區分。
珠寶商線索保留須輸入的 PASS、RELEASE 並附中文解釋，不改原版答案判定。
地名另作人工抽查，修正本輪安塞隆、岩漿海的暫譯偏差；一般場所描述不套用前作房間專名。
另查多詞法術名稱，將一個既有 Mind Blank 狀態敘述修正為「受心靈防護術保護」，對齊前作。
人物、怪物及物品的程式檢查之外，地名與法術仍須人工校讀；射線描述、複合法術名及樓層
不能依較短的術語片段硬換。
完整譯表回驗為 6,630 筆，0 格式錯誤、0 未處理術語警示，265 則逐句校讀覆蓋 271 次匹配。
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
靜態證據，支持法術與裝備兩種語境的強推論；實際顯示呼叫者仍待驗證，保留歧義不全域定譯。

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
新增純校讀模式時的 6,040 筆已由預設模式回驗；目前 6,630 筆全表另已回驗通過。
新模式沒有放寬名稱、數字或格式檢查。

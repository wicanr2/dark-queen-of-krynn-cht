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
目前 98 筆 MONCHA 原始 ASCII 候選中有 96 筆譯文；其餘 AMT、HNZH 仍無法辨識為名稱。
這個數字只描述候選譯表，沒有證實記錄邊界、怪物種類或實際遇敵顯示。

## 譯文、術語與檢查

所有大量原文、譯文、名稱對照、來源雜湊與批次只留 `workplace/translation/`，不入 Git。
主要檔案如下。

| 本機檔案 | 用途 |
|---|---|
| `en.tsv` | 唯一候選原文表，`key`、`text`，保留大小寫及頭尾空白 |
| `catalog.json`、`events.tsv`、`receipt.json` | 原始檔偏移、區塊、來源雜湊、觀測等級與工具／輸出雜湊 |
| `zh-TW.tsv` | 已通過批次檢查的目前譯文，`key`、`text`；尚未接入遊戲 |
| `trial.zh-TW.tsv`、`trial-review.md` | 使用者確認譯風的 145 筆首批與雙語稿 |
| `glossary.tsv`、`terminology-provenance.json` | 前作優先的 950 筆術語、手冊對照、英文新譯來源及歧義 |
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
| `story-context-labels.tsv` | 蜥蜴人追逐場景的三個敘述／選單鍵，依來源位置校讀 |
| `manual-name-corrections.tsv` | 11 個既有鍵的精確修訂，含手冊新核名稱與同場地點用語；不增加譯文數 |
| `manual-deity-corrections.tsv` | 手冊第 124 頁核對後，校正一個既有喜得卡譯文鍵；不增加譯文數 |
| `*-review-input.json` | 逐批校讀時固定的來源字串與原文表 SHA-256；不是正式顯示來源 |
| `passage-candidates.json`、`passage-candidates.en.tsv` | 322 組靜態相鄰字串候選；獨立校讀輸入，未列入正式原文／譯文表 |
| `term-corrections.tsv` | 已有譯文的精確鍵修訂，包括避難廳與不死怪物用語 |
| `ui-effects-trade.tsv` | 204 筆狀態、交易、角色、存檔與戰鬥訊息新譯 |
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

目前已檢查並合併 4,209 筆本機譯文，包含首批試譯、前作同文校讀、角色與介面、洞穴、海底、
森林、西洛爾、鷹峽、黑水坡、地侏堡壘、火焰塔、深淵及部分結局分支。
逐批數量見上表及 WORKLOG，現行譯文以 `zh-TW.tsv` 為準，歷史批次不重複計數。
這是譯文進度，不能稱為 4,209 個功能、全遊戲覆蓋率或可玩中文化完成。
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
完整譯表回驗為 4,209 筆，0 格式錯誤、0 未處理術語警示，170 則逐句校讀覆蓋 174 次匹配。
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

## 相鄰劇情字串候選

[passage_candidates.py](../../tools/passage_candidates.py) 先核對 ECL 與 catalog 的來源雜湊，
再檢查 literal 的原始長度、6-bit 解碼及 HLIB 區塊邊界。只整理同一區塊內由 `11` 或
`18 11` 相鄰接續、且首段前為 `11` 或 `12` 的字串；遇其他位元組即停止，不跨過未知控制碼。
輸出保留每段來源鍵、檔案與區塊偏移、長度、前後位元組及工具雜湊。

目前有 322 組不重複候選，來自 344 個來源位置，共 875 次片段出現。
分組屬強推論，完整控制及分頁邊界尚未證實；每組都標記未經動態驗證。
兩種接續在受控副本中的繪製行為已另驗，見 [研究 004](004-story-text.md#2026-10-22相鄰字串的受控接續實驗)。
這個工具不修改 `en.tsv`、`zh-TW.tsv` 或原版資料，不把候選組數加入翻譯完成數。

## Docker 入口

[translation.sh](../../tools/translation.sh) 提供以下入口，原版及前作唯讀，僅本作研究工作區可寫。
停用網路、非 root，使用已存在且固定 ID 的 Pillow 與字型工具 image。缺少來源時停止。

```sh
bash tools/translation.sh extract
bash tools/translation.sh terms
bash tools/translation.sh seed
bash tools/translation.sh batches
bash tools/translation.sh passages
bash tools/translation.sh check trial
bash tools/translation.sh check names
bash tools/translation.sh check ui-rest-combat
bash tools/translation.sh check ui-management
bash tools/translation.sh check prior-reviewed
bash tools/translation.sh check story-caves
bash tools/translation.sh check story-monsters
bash tools/translation.sh check ui-effects-trade
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
bash tools/translation.sh check manual-name-corrections
bash tools/translation.sh check manual-deity-corrections
bash tools/translation.sh check term-corrections
bash tools/translation.sh check current-validation
bash tools/translation.sh test
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

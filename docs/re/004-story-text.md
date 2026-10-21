# 004：劇情段落在逐字繪製前的入口

日期：2026-10-21。工作：[#4](https://github.com/wicanr2/dark-queen-of-krynn-cht/issues/4)。
輸入 `DQK.EXE` 1.1，SHA-256
`3b41fb06a045568b0c35098a104499d489d8a5c0ef0dd48a039387ba2393ba58`，版本來源見 [001](001-input-baseline.md)。
正常玩家路徑見 [003](003-startup.md)，本輪以原版附帶隊伍進入第一段劇情，不注入狀態或跳過查驗。

## 工具與位址基準

- IDA Pro 9.4，MZ 載入基底 `0x10000`；資料庫及查詢副本見規格 001。
- dosgolem `f79eab6db8c64a524a06535e53e5d32b0bbcf7c8`，Go 1.24.13。
- 原始檔偏移、IDA linear、執行期 segment:offset 各自標示。
  已核對的 resident 映射沿用 [規格 001](../spec/001-early-text.md#證據身分) 的三個 anchors。
- [story_text_probe.go](../../tools/story_text_probe.go) 只讀取參數及原始位元組，保留未證實候選。
  `vararg_1_candidate` 只是原始讀取，不代表每個格式字串的第一個參數都是指標。

## 已證實的繪製鏈

| 原始定位 | IDA linear | 原始檔偏移 | 執行期 | 本輪語意 |
|---|---|---|---|---|
| `sub_1A931` | `0x1A931` | `0x0CD31` | `0B72:0311` | 取得完整 NUL 結尾段落及文字框；沿字詞換行，再逐字輸出 |
| `sub_1A8A3` | `0x1A8A3` | `0x0CCA3` | `0B72:0283` | 由欄／列與字元建立低層輸出參數；原始公式含 `4×欄或列 + 0x1F40` |
| `sub_213C0` | `0x213C0` | `0x137C0` | `1212:03A0` | 本段落每個字元經 `%c` 呼叫；到此才辨識只能拿到單字元 |
| `sub_23806` | `0x23806` | `0x15C06` | `13C7:0C96` | 單字元繪製分派 |

前三個入口保留 IDA 原名，沒有用語意名稱覆蓋函式或全域。
`sub_1A931` 的 guard bytes 是 `55 8B EC 83 EC 02 56 57`，由原始檔、IDA 與執行期核對。

## 段落入口參數

在 `0B72:0311` 第一條指令前：

| 堆疊位置 | 本輪已證實的用途 |
|---|---|
| `SS:SP+4/+6/+8/+10` 的低位元組 | 左欄、上列、右欄、下列；忽略未初始化的高位元組 |
| `SS:SP+12/+14` 的低位元組 | 前景、背景參數；本函式把背景 0 轉成 8 |
| `SS:SP+16` 的低位元組 | 本輪清除旗標為 1；靜態分支呼叫區域清除程序 |
| `SS:SP+18/+20` | 完整段落的 offset／segment |

本輪段落入口在 `#334646730`，來源指標 `333E:B487`。
文字框欄／列為 `1,17,38,22`，前景 7，背景原始值 0。
第一次字元分派在 `#334649938`，字元 `Y`、原版像素 `(8,136)`、顏色 `0x87`。
兩者相差 3,208 道虛擬指令，沒有換算成實機毫秒。

首段完整來源可在第一個字元出現前讀取。低層觀察到的 185 個單字元輸出與段落內容相符；
這項結論限於本次首段，不外推全遊戲腳本。

## 收據與未完成項

- 動態收據：`workplace/probe/story-text/trace.json`。
- SHA-256：`7d61a8737b9c97603d694c64f53bdbc6a5b7ae6b4edaa10793f55dd761af990d`。
- 原始 IDA bytes、函式邊界與 xref：`workplace/ida-query/story-functions.json`。
- 探針執行到 375M，記錄 260 個定位輸出呼叫、601 個字元分派及 1 個完整段落入口。
- 靜態程式顯示換行後可能觸發頁面等待及清除；尚未抽驗跨頁長段、控制碼、接續文字或中斷。
- 未建立正式段落 parser、中文分頁或 UI。新發現回填 [DRAFT 規格 001](../spec/001-early-text.md)，
  達成分頁及清除驗證後才可縮定 READY 範圍。

成對重跑的觀測與控制組使用相同正常快照、字母輸入及 Return，皆到 375M。
暫存器、1 MiB RAM、原版色號及色盤相同。RAM SHA-256：
`5c0087c30fcdc08ccd1467b7c87705aba712da09599a4f0f8d63532df4c94189`。
讀取字串限制在傳統記憶體，未知 vararg 不到顯示記憶體讀取，避免觀測觸及 VGA 的讀取副作用。

| 成對收據 | SHA-256 |
|---|---|
| `workplace/probe/story-observe/trace.json` | `147213072661e0ffcc5027fa9c3804dc685200c0f455461c67399ffd78b41f35` |
| `workplace/probe/story-control/trace.json` | `809b13e7ef62200dda2e7df89bea2063516a2b713051b097ba5f62667dc8e01e` |

成對測試證明這次觀測沒有改變比較的原版狀態，沒有證明尚未接入的中文分頁或正式前端已完成。

## 字級原型量測

[story_preview.py](../../tools/story_preview.py) 以本輪完整段落及私有試譯產生離線比較。
使用前作依法使用的 jf open 粉圓 2.1，SHA-256 與角色管理原型相同。
地名 Palanthas 採《克萊恩英豪》`text/glossary.tsv` 的「帕蘭薩斯」。
這是試譯與字級樣本，尚未供使用者定版，也未接入實際逐字繪製。

| 項目 | 本作原版量測／原型 |
|---|---|
| 原版畫面 | 320×200，原型整數放大到 640×400 |
| 本段欄／列 | 1 至 38 欄、17 至 22 列 |
| 原版文字框 | `[8,136,312,184)`，304×48 px |
| 放大後文字安全框 | `[16,272,624,368)`，608×96 px |
| 16px 原型 | 行距 20px，本次試譯 2 行，字墨及行數均在安全框內 |
| 20px 原型 | 行距 24px，本次試譯 2 行，字墨及行數均在安全框內 |

輸出在 `workplace/probe/story-text/preview-{16,20}px.png`、`preview-report.json`。
角色管理選單的 20px 定案只適用選單；這兩張圖不代表劇情字級定案。
目前只是短段落，尚未用最長實際段落、中文禁則、混合英文與跨頁狀態驗證。

## 2026-10-22：相鄰字串的受控接續實驗

目的為確認腳本把一句話拆成多段後，是否仍能在第一個字元前取得全部內容。
工具 [make_text_chain_fixture.py](../../tools/make_text_chain_fixture.py) 建立兩份獨立資料副本，
只置換 `DISK3/ECL.GLB` 檔案偏移 `0x321A` 的首段 literal，保留封包長度及 HLIB 索引。
53 個檔案逐一回驗，只有 ECL 改變；`DQK.EXE` 與原始資料目錄不變。
這是受控資料實驗，不能當作原版正常玩家路徑或中文化完成收據。

- 原始 ECL SHA-256：`40542071e42d3cd125eabcead11456a99942bf55a7736fdb79f66a3c27c3664d`。
- 快照來自正常入口 329M：`workplace/probe/startup/adventure-start.state`，SHA-256
  `7c5ce572b8cd979f03ffd423e80c2c3048ed404b44f49a9f42d834b6f6fbacc5`。
- 執行器與 Go 版本沿用上文；從現行 `story_text_probe.go` 重建後，二進位 SHA-256 為
  `c015cd7b7b3f74d33585316dd2f111208c0956f0a5cec7d158c8db4e2eed5238`。
- fixture 工具 SHA-256：`e4f533dfedd0442d3be8f9c363352d451e906f2ce63b69421cf8a45220d12c1a`。
- 兩種副本分別以 `11` 及 `18 11` 連接兩個 literal；第一個 literal 之前保留原 `12`。
  這裡的十六進位數是資料位元組，不是函式位址。

| 接續位元組 | 第一段入口／首字元步數 | 第二段入口／首字元步數 | 清除旗標 |
|---|---|---|---|
| `11` | 334599045／334601829 | 339785948／339787956 | 1、0 |
| `18 11` | 334598682／334601463 | 339785963／339787971 | 1、0 |

已證實：在這兩個受控案例中，段落函式 `0B72:0311` 被呼叫兩次，文字框皆為
`1,17,38,22`，第一段已開始繪製後才進入第二段。等待第二段到達才組成中文會太晚。
尚未證實：`18` 的完整語意、其他控制碼、全遊戲分頁、輸入等待與所有靜態候選的執行情形。

重跑入口為 `bash tools/translation.sh chain-fixture 新輸出名`，輸出名只能使用小寫字母、數字及
連字號，而且必須尚未存在。需要既有正常入口快照、固定 dosgolem 副本及模組快取；缺件即停止。
本次乾淨重建收據為 `workplace/probe/text-chain-rebuild-20261022/receipt.json`。

| 該目錄下的追蹤檔 | SHA-256 |
|---|---|
| `direct-11/trace/trace.json` | `4522997ae2ad2a87e22c1fecfa8b8d9a72f8c41af26b1fd8bcfa8558330fb55e` |
| `prefix-18-11/trace/trace.json` | `ff4d953c3b3898d1898edbe2d1b89b8eac4e71059156d8498332e8334c70ff8f` |

因此先建立供校讀的整句候選，見 [研究 005](005-translation-catalog.md)。
正式顯示前的整句辨識、中文分頁與清除生命週期仍依 DRAFT 規格 001 處理。

## 2026-10-22：正常進城七段與實際中文視窗

本輪沿同一正常 329M 快照完成英文手札查驗。375M 起每隔 25M 按一次畫面要求的 Return，
共八次，至 575M 停在城內去向選單。先前另測八次空白鍵，按鍵被消耗但沒有推進劇情，
收據保留在 `workplace/probe/story-sequence-20261022/`，不把空白鍵當繼續操作。
來源仍是本節上方固定雜湊的原始 EXE、ECL 及 dosgolem，沒有改腳本、跳轉或注入狀態。

[story_text_probe.go](../../tools/story_text_probe.go) 加入 `enter-sequence` 與
`enter-sequence-control` 模式。段落的 far 返回位址以入口 SS:SP 成對追蹤，只附加返回步數，
未改原始函式名。七次返回都在首字元之後，第一段於 360416760 返回，接著才顯示 Return 提示。
這是本流程的觀測，不代表所有段落函式返回都等於玩家完成閱讀。

| 本輪內容定位 | 段落入口步數 | 清除旗標 | 現行 catalog key |
|---|---:|---:|---|
| 抵達帕蘭薩斯 | 334646730 | 1 | `ecl.6eddbe9ac1fb277bfaab` |
| 城門衛兵查驗 | 375066416 | 1 | `ecl.bc2406fb36732bff9eb9` |
| 出示羅拉娜的信 | 400054641 | 1 | `ecl.34bcf7a8a3daac1c7f98` |
| 衛兵轉達邀請 | 408782023 | 0 | `ecl.b759967b4a8e86a56a3a` |
| 繼續入城 | 419290091 | 0 | `ecl.95d76cd76998c349a93f` |
| 城市標題 | 425141745 | 1 | `ecl.ea364d1749909fbc2006` |
| 去向提問 | 428553765 | 0 | `ecl.5f82368960d8b00baea1` |

已證實：七段都是完整 NUL 結尾 ASCII，與現行原文 TSV 逐字相同，譯表已有對應。
本輪七次文字框都是 `1,17,38,22`，背景 0 轉成色盤索引 8。信件與衛兵轉述的三次呼叫
依 1、0、0 清除／接續，城市標題與去向提問依 1、0 接續。沒有用受控副本冒充這次正常流程。

本輪原版觀測與無觀測組在 375M 至 575M 的九處檢查點，暫存器、1 MiB RAM、色號、色盤、
按鍵與寫檔紀錄均相同，未回報未實作服務。575M RAM SHA-256 為
`5c6511f43b078b4d17ee05953600bd730d52a5958bd3a18bade0624de7a34688`。

| 私人收據 | SHA-256 |
|---|---|
| `workplace/probe/story-return-sequence-20261022/trace.json` | `3155d4251b7fc4f37399d7aa81dc1c0018cee36c080639e8d5a7addc806ee9bb` |
| `workplace/probe/story-return-control-20261022/trace.json` | `6ae1bd271edd389b99bb0dc3eaae4357e2705a30ce9558da267e7a2a2fedb39c` |

### 正式譯文衍生的 DRAFT 視窗

[story_preview.py](../../tools/story_preview.py) 的 `--runtime-inputs` 模式從上表七段及本批當時的 TSV
建立研究子集，逐字比對原文，沒有沿用最初首段試譯，也不在程式碼內嵌譯文。
子集與字模位於觀測目錄，`runtime-inputs.json` 記錄原始觀測、原文、譯文及輸出的雜湊。
本批對拍所用譯表為 6,040 筆，SHA-256
`1c28045904ecca685519a2204ab91c554f6cd18bc271a44b04c6a676d7ed4602`，未增加或改寫譯文。
字模沿用已核對的 jf open 粉圓 2.1，字型雜湊見前節及規格 001。

[early_text_live.go](../../tools/early_text_live.go) 加入劇情原型。原文 key 與完整來源都相符才處理。
清除旗標 1 取代中文事件；0 接續前段並重新斷行。同一文字框、前景及背景與中文字一次合成，
原版記憶體照常保留英文。原型遇到七段子集以外的段落即停止，不充當泛用失配回退實作。
角色選單仍保留原本模式，劇情未套用選單的像素參數解釋。

| 實際視窗收據目錄，均在 `workplace/probe/` | 畫格數 | 段落事件 | 收據 SHA-256 |
|---|---:|---:|---|
| `live-story-sequence-en` | 1,400 | 7 | `99dff6c85ea5fb2b100063ceaf97a2194116ba5e0f10c0c0ca298b2b5f76f529` |
| `live-story-sequence-16` | 1,431 | 7 | `f1551c2317c51e9250ed7d245d16869391de67b950b1cbcac98158d2d3049809` |
| `live-story-sequence-20` | 1,412 | 7 | `8dbf627a29517e4a8f2c36903dfc867eed00abe9b67ce4d94ae78ea857244748` |
| `live-story-fine-en` | 950 | 1 | `d0672028e06f6cc4dbe4f58e40dfa63f4b75c33fe0e0857467ca68837e8fdd8a` |
| `live-story-fine-20` | 950 | 1 | `d3e49a6e4a04be9ac61f008b95722749bcbcdfe0c45491c8003efce3b68f06a7` |

已證實：三個連續視窗組的九處原版狀態都與無觀測組相同。每幀實際 GPU 讀回等於合成輸入，
中文字框在同段的所有提交中保持相同，不露出原版逐字輸出的中間態。16／20 像素組分別有
832／765 個共同步數，框外畫面逐點等於原文組；首段細分組的 950 個共同步數也相同。
首段每 2,000 道指令提交一次，`#334648000` 已提交中文，比第一個原版字元早 1,938 道指令。
全部五組 OOM 計數為 0。正常流程抽看四張檢查圖，信件、轉述及入城文字均保留，清除後無舊段。

重生入口是 [story-live.sh](../../tools/story-live.sh)：先有上述正常觀測，執行 `prepare` 衍生子集，
再 `build` 重建共用原型與 16／20 字模。`en`、`16`、`20`、`fine-en`、`fine-20` 到首段末；
`sequence-en`、`sequence-16`、`sequence-20` 接續至城內去向選單。執行可附全新輸出名。
來源、字型與目前 TSV 唯讀；擷取與 manifest 留在既有研究輸出，不入 Git。
正常觀測可由 `probe-build` 重建探針，再用 `probe 新輸出名`、`probe-control 另一新輸出名`
重生；實際對應 `enter-sequence`、`enter-sequence-control`。要從新觀測衍生字模時，以
`DQK_STORY_SEQUENCE` 指定該既有觀測目錄，再執行 `prepare`、`build`。wrapper 的來源、
資源上限與掛載契約沿用角色選單原型，沒有新建 image。

[story_live_check.py](../../tools/story_live_check.py) 在 Pillow 11.3.0 image 內重驗：

```sh
python3 /tools/story_live_check.py /out \
  story-return-sequence-20261022 story-return-control-20261022 \
  live-story-sequence-en live-story-sequence-16 live-story-sequence-20 \
  live-story-fine-en live-story-fine-20
```

`/tools` 掛本專案工具唯讀，`/catalogs` 掛這批收據當時的原文／譯文快照唯讀，`/out` 掛既有研究輸出。
本輪原始快照已保存於 `workplace/probe/catalog-runtime-ui-20261022/before/`，見研究 005。
目前譯表後續新增不回寫舊收據；若用新譯表重跑，須建立新的衍生輸入及收據。
比較結果寫入連續 20px 組的 `comparison.json`，存在即停止。
字級比較圖在 `live-story-20-r2/font-comparison.png`，左 16、右 20；四畫面抽樣在
`live-story-sequence-20/route-contact.png`。圖含原版美術，只留本機。

限制：字級問題已呈交使用者，尚未定案。這個原型在段落入口一次顯示本段中文，原版內部逐字
繪製照常執行；正式顯示節奏尚未決定。未驗證長段溢位分頁、捲動、其他框、手札、戰鬥、
選單與提示全文中文及正式存讀檔。保留 DRAFT，不宣稱已完成可玩中文版本。

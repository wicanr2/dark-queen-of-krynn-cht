# 原譜音樂與播放時機

對應[#8](https://github.com/wicanr2/dark-queen-of-krynn-cht/issues/8)，規格入口為[006](../spec/006-hd-music.md)。原曲、樂譜轉出與衍生音樂留本機。

## 已證實的輸入

固定原版DQK.EXE SHA-256為`3b41fb06a045568b0c35098a104499d489d8a5c0ef0dd48a039387ba2393ba58`。DISK1的AD、RO、TY、PC四組XMI各為1＋6＋1，共8序列。四組是硬體音源版本，不能計成32首不同曲。

[擷取器](../../tools/xmi_score.py)檢查IFF區塊、INFO序列數、TIMB音色及EVNT事件邊界；音符、力度、長度、控制器及來源位移保留。輸出在本機`workplace/probe/music-hd-20261029/`。Roland八段未見XMI內嵌迴圈控制，外部播放命令的觀測範圍見下節。

安裝程式的原始字串明列MT-32，EXE使用MT32MPU.ADV。RO版本使用MT-32編號，不能直接套GM同號樂器。取樣音色先沿既有容器的FluidR3_GM，版本、雜湊及授權全文保存在該批次；不下載新音色或新增容器映像。

## 平台格式契約

- XMI等待量為加總的7位元組，音符長度採一般VLQ。固定每秒120個tick；tempo meta不改這個時基。對照[ScummVM的XMIDI格式實作](https://github.com/scummvm/scummvm/blob/master/audio/midiparser_xmidi.cpp)，本機另保存固定commit的完整參考與雜湊。
- MT-32至GM採音色角色近似，記錄每個用到的對應，不宣稱原硬體逐波形一致。參考[Roland音色表](https://cdn.roland.com/assets/media/pdf/RA-50_OM.pdf)及[成熟音源對應實作](https://github.com/scummvm/scummvm/blob/master/audio/mididrv.cpp)；不複製其程式碼。
- 正式播放資產採Ogg Vorbis；MIDI與WAV只作來源與中間檔。音量、尾音、循環及實際聽驗分開記錄，格式可解碼不等於聽感通過。

## 播放入口與證據等級

以下resident定位由IDA Pro 9.4資料庫邊界、原始機器碼及執行期堆疊核對。原版EXE雜湊見上文。IDA線性位址減`0xEF00`對應此固定載入配置的執行期線性位址；原檔位移為IDA線性位址減`0xDC00`。此公式不套用overlay。

| 原始IDA函式 | 原檔位移 | 執行期入口 | 已證實語意 |
|---|---|---|---|
| sub_1FEA6 | 0x122A6 | 10E3:0176 | 音效與音樂共用派發器；音樂命令32至39 |
| sub_1E7C5 | 0x10BC5 | 0F66:0265 | 來源C字串遠指標、序列、音量；開始播放 |
| sub_1EA2B | 0x10E2B | 0F66:04CB | 同來源與序列的音量調整 |
| sub_1ED0B | 0x1110B | 0F66:07AB | 同來源與序列的停止 |

三個低層入口與遠返回的機器碼在[只讀觀察器](../../tools/music_cues.go)逐一核對。使用SS:SP配對，參數從SP＋4起讀取，只在AX為0時提交。IRQ或不同堆疊返回不能提前提交。此處只觀察，不跳過原版呼叫或改動回傳值。

原版DS:1F21的8個檔案索引為`1,2,2,2,2,2,2,3`，DS:1F31的序列為`0,0,1,2,3,4,5,0`。命令32至39依此順序對應。四組XMI來源的序列布局經解析驗證，正式音樂內容固定取RO版本，AD／PC／TY的同一來源識別映至這8段。

正常冷啟動、Return、D及Esc的550M指令觀察，取得標題曲RODQ1-0、停止及展示曲RODQ2-3三個命令。新觀察器取得的步數與先前原版原始入口收據相同，分別為2025037、350324136、350336553。其後用原版派發函式注入全部8段，另呼叫音量0／90／100；無效序列99回傳FFFB且未提交音樂事件。注入只驗函式，不稱為正常走訪8個劇情場景。

本機收據為`music-hd-20261029/cue-controls/cues.json`。未觀測到原版B0循環API呼叫；RO樂譜亦沒有116／117內嵌循環。接入採單次播放，若原版重新發出開始命令就重新播放。不把此範圍推廣為所有原版場景的硬體時序證明。硬體ISR與逐週期時序沿AGENTS停止線。

IDA原始匯出、版本與地址基準保存在該批次`ida-cues/`。沿用`ida-pro-9.4-idapython:py312-v1`，新UID組合的最小匯出已核606個函式、9.4與EXE雜湊；正式資料庫唯讀，所有查詢用一次性副本。

## 取樣音樂與技術驗證

[製作器](../../tools/music_score_render.py)將8段共4191個音符轉出標準MIDI，再以FluidSynth 2.3.1及FluidR3_GM 3.1製作48kHz立體聲Ogg。音符、起點、時長與力度經獨立MIDI讀回核對；控制事件另由[核對器](../../tools/music_score_check.py)逐一核對。只移除原版專用的零號音色庫命令，樂器按公開角色表對應。音量及聲像控制保留，鐘聲與低音小鼓採明列近似，兩種豎琴使用同一取樣樂器。

音色檔SHA-256為`74594e8f4250680adf590507a306655a299935343583256f3b722c48a1bc1cb0`，採MIT授權，全文與取樣程式版本保存在本機。每段保留三秒釋音，8段合計216.341667秒。WAV與Ogg讀回均非靜音、削波0；Go解碼另驗全部8段的取樣率、聲道與完整畫格數。技術檢查及已連通的音訊服務不等於聽驗。

使用現有媒體映像`1c99728881f2cbcb54bfef0c1621968e59e32d6102e1b924db9d17a8a8713465`。Go解碼新增固定的oggvorbis v1.0.5、vorbis v1.0.2，下載zip與解壓內容逐項相同，兩者為BSD-3-Clause。SDK、共用模組快取與前作不修改。桌面播放映像僅延伸固定Go映像，補libasound2-plugins 1.2.7.1-1，連接同UID的PulseAudio socket，不搬運主機憑證。

| 收據 | 範圍 |
|---|---|
| `music-hd-20261029/render-final/manifest.json`、`checks.json` | 8曲、4191音符、553個非音符控制事件；來源、輸出雜湊、音量、尾音及權利 |
| `player-music-20261029/ui-tests.json`、`ui-contract.json` | 24個既有介面子案例與2項音樂測試；音樂測試內含32個來源別名與8曲Go解碼 |
| `player-sample-music-20261029-r2/checks.json` | 正常冷啟動、F8、音樂工具列、偏好與縮放／語言獨立；ALSA null技術輸出 |
| `player-sample-music-pulse-20261029-r1/checks.json` | 同一正式程式、相同正常介面操作，改接桌面PulseAudio服務；未作聽驗 |
| `player-sample-music-fallback-20261029-r1/checks.json` | 無音訊裝置仍可正常操作；D示範、Esc中斷及P角色管理 |

目前未驗：人耳聽感、實體喇叭輸出及逐劇情走訪全部8種cue。後者的函式選取已透過上述注入證實，不另為硬體內部開逆向工作。

## 重建入口

需既有合法原版、固定SDK及本機工具映像。各批使用新名稱，避免覆寫收據。

```sh
bash tools/music-hd.sh prepare music-hd-my-batch
bash tools/music-hd.sh render music-hd-my-batch final
bash tools/music-hd.sh check music-hd-my-batch final
bash tools/music-hd.sh probe music-hd-my-batch sample
bash tools/music-hd.sh install music-hd-my-batch player-my-build final
```

安裝目標須先由`player.sh prepare player-my-build`建立，音樂安裝後再以`player.sh build player-my-build`建置。第一次補Go音訊解碼依賴使用`bash tools/music-hd.sh deps`。桌面音訊映像使用`bash tools/player-audio-image.sh`；建置來源為[Dockerfile](../../tools/Dockerfile.player-audio)，只補PulseAudio橋接，不更換Go版本。已存在的依賴與映像先核對，不重複建立。

離線音樂可在本機`render-final/index.html`逐曲播放。原版樂譜、完整轉出、中間音訊及衍生音樂均不加入Git。

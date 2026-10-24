# 《黑暗之后》HD＋繁體中文化

《The Dark Queen of Krynn》是克萊恩三部曲的第三部，接續《克萊恩英豪》與《幽靈騎士》。
本專案使用 dosgolem 執行原版，在呈現層加入繁體中文，之後再製作全量 HD 圖像。
武器、怪物與跨代人物譯名沿用《幽靈騎士》，原版規則與存檔保持原樣。

玩家須自備合法原版。原版遊戲、美術、手冊與掃描留在本機，不隨儲存庫提供。

## 故事背景

在前兩次冒險之後，英雄們的事蹟傳到了帕蘭薩斯。羅拉娜將軍來信，感謝隊伍挫敗
索斯王與姬蒂拉的陰謀，並邀請英雄前往城中。但效忠黑暗之后的勢力仍未消失，
這封看似慶功的邀請，也帶著另一項重要任務。

這段介紹依《冒險手冊》「故事開始」的一封將軍來信整理，譯名以前作現行詞表為準。
來源與頁序見[手冊基線](docs/re/001-input-baseline.md#中文來源)。

## 遊戲方式

玩家帶領冒險隊伍探索城鎮與地下區域，與人物交談、管理裝備、準備法術，並在格狀戰場上
進行回合制戰鬥。旅行手札補充線索與故事；本專案也將加入繁中說明與手動查閱的攻略頁。
攻略正文重新排版，地圖重新繪製，不以掃描頁或 PDF 代替遊戲內閱讀頁。

## 畫面、圖鑑與地圖

| 圖文 | 原版來源與展示方式 | HD 對照 |
|---|---|---|
| 怪物總覽 | CPIC 已解出 190 個戰鬥圖格，含角色、動作格與重複編號；怪物名稱尚待逐項對照 | 藍龍一張試繪，與原版並排；全量尚未製作 |
| 人物頭像總覽 | 先列 31 張人物候選圖，保留來源編號；另附人物、怪物與場景的圖庫 | 頭像一張試繪，身分與正式風格未定 |
| 遊戲截圖 | 裝備清單、首戰回報與敗北結語的原版／繁中實際畫面 | 尚未接入 HD，試繪圖另列 |
| 遊戲內地圖 | 原版森林探索、區域圖，以及另行重繪的凱爾高斯攻略圖 | 攻略重繪原型尚未作為遊戲內地圖接入 |

圖文首頁在本機產生，包含可點開的總覽圖、原版／HD 試繪對照及遊戲截圖。
五份圖庫目前解出 360 格，另有 52 個繪圖區塊尚未解碼；圖格數不等於怪物或人物種類數。
原版及衍生圖像不加入 Git，GitHub 上的 README 因此只保存介紹與重建入口。

在本專案既有 Docker 工具鏈、合法原版及本機研究素材齊備後，執行：

```sh
bash tools/readme-gallery.sh readme-gallery-preview-r1
```

用瀏覽器開啟 `workplace/probe/readme-gallery-preview-r1/README.html`。
輸出目錄須為新名稱，保留既有預覽及來源索引。入口為 [readme-gallery.sh](tools/readme-gallery.sh)，
頁面由 [readme_preview.py](tools/readme_preview.py) 產生。這是研究圖文入口，尚非遊戲啟動器。
本機素材與驗證範圍見 [CONTEXT.md](CONTEXT.md)；攻略重繪的來源見
[攻略地圖研究](docs/re/002-walkthrough-source.md)。

圖庫盤點工具為 [tlb_gallery.py](tools/tlb_gallery.py)。HLIB／TILE 格式參照
[Gold Box Explorer](https://github.com/bsimser/Gold-Box-Explorer)，保留其
[MIT 授權聲明](tools/LICENSE-Gold-Box-Explorer.txt)。
解碼方法、圖格見證及展示限制見[圖文研究紀錄](docs/re/006-readme-gallery.md)。

## 目前狀態

已建立正常載入、建角、城內服務、裝備、法術清單、手札引用及首戰部分回報的繁中顯示原型。
文字在原版繪製前辨識，並以連續畫格檢查過渡；這些仍是研究原型，尚無正式完整中文入口。
手札正文與圖文元件已有校讀及驗證，說明面板、其餘敘事與玩家路徑仍待接入。
詳細範圍與目前有效程式集中在 [CONTEXT.md](CONTEXT.md)，全量 HD 尚未開始。

## 操作與文件入口

開發、研究與原型驗證使用 Docker。現有入口的用途與限制見規格，請勿把單一場景原型當作完整遊戲啟動器。

- [協作規則](AGENTS.md)
- [目前狀態](CONTEXT.md)
- [工作紀錄](WORKLOG.md)
- [研究索引](docs/re/README.md)
- [規格索引](docs/spec/README.md)
- [歷史重播紀錄的封存與還原](AGENTS.md#歷史重播紀錄的儲存)
- [GitHub Issues](https://github.com/wicanr2/dark-queen-of-krynn-cht/issues)

自有程式與文件採 [RRSAL-1.0](LICENSE)，屬 source-available。授權不涵蓋原版遊戲、
手冊、美術、音樂及第三方元件。原始遊戲與掃描只留本機，使用者須自備合法原版。

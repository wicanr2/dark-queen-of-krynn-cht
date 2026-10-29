# 研究索引

> 儲存說明：大型歷史 `receipt.json` 可能已無損封存。依原邏輯路徑取用前，先按[封存與還原入口](../../AGENTS.md#歷史重播紀錄的儲存)還原紀錄，再執行既有檢查；歷史雜湊不改寫。

原始掃描、全文轉錄、解壓資料與執行收據保留於 `workplace/`，不加入 Git。
本目錄只保存輸入雜湊、工具版本、原始定位、推論等級及可重現步驟。

跨規格回填保存在 [resolutions.tsv](resolutions.tsv)，以
[check_evidence_links.py](../../tools/check_evidence_links.py) 在 Docker 內驗證舊規格與新證據回鏈。

| 研究 | 對應工作 |
|---|---|
| [001：遊戲與中文來源基線](001-input-baseline.md) | [#2](https://github.com/wicanr2/dark-queen-of-krynn-cht/issues/2) |
| [002：中文攻略來源、52張重繪圖與閱讀接入](002-walkthrough-source.md) | [#6](https://github.com/wicanr2/dark-queen-of-krynn-cht/issues/6) |
| [003：dosgolem 正常冷啟動基線](003-startup.md) | [#3](https://github.com/wicanr2/dark-queen-of-krynn-cht/issues/3) |
| [004：劇情段落的繪製前入口](004-story-text.md) | [#4](https://github.com/wicanr2/dark-queen-of-krynn-cht/issues/4) |
| [005：文字候選與繁中譯表](005-translation-catalog.md) | [#7](https://github.com/wicanr2/dark-queen-of-krynn-cht/issues/7) |
| [006：README 圖文與原版圖庫](006-readme-gallery.md) | 使用者指定的故事、圖鑑、原版／HD 試繪、截圖及地圖 |
| [007：繪圖層接管與提交邊界](007-render-ownership.md) | 使用者授權接管原版繪圖，沿 #7 |
| [008：原譜音樂與播放時機](008-original-music.md) | [#8](https://github.com/wicanr2/dark-queen-of-krynn-cht/issues/8) |

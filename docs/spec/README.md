# 規格索引

> 儲存說明：大型歷史 `receipt.json` 可能已無損封存。依原邏輯路徑取用前，先按[封存與還原入口](../../AGENTS.md#歷史重播紀錄的儲存)還原紀錄，再執行既有檢查；歷史雜湊不改寫。

規則見 [AGENTS.md](../../AGENTS.md)。DRAFT 只允許研究與可丟棄原型，READY 才能正式接入。

| 規格 | 狀態 | 工作 |
|---|---|---|
| [001：提早辨識文字與同幀呈現](001-early-text.md) | READY，限已列來源契約 | [#4](https://github.com/wicanr2/dark-queen-of-krynn-cht/issues/4) |
| [002：手札閱讀與分頁](002-journal-reader.md) | READY，原框閱讀已定稿 | [#5](https://github.com/wicanr2/dark-queen-of-krynn-cht/issues/5) |
| [003：中文整合入口與頂端工具列](003-player-toolbar.md) | READY；攻略及獨立全螢幕地圖呈現CONFORMED，正常操作與Linux／Wine封包已有代表抽驗 | [#6](https://github.com/wicanr2/dark-queen-of-krynn-cht/issues/6)、[#7](https://github.com/wicanr2/dark-queen-of-krynn-cht/issues/7)、[#13](https://github.com/wicanr2/dark-queen-of-krynn-cht/issues/13) |
| [004：HD素材與獨立呈現開關](004-hd-layer.md) | CONFORMED，依使用者接受的類型抽驗收尾；HD與視窗尺寸獨立 | 1488項素材、17家族49個固定樣本，正常／注入範圍見CONTEXT |
| [005：繪圖接管與完整畫格提交](005-render-owner.md) | 限定內層搬移、機器效果與事件預算為 READY；已接管命令及追加兩輪繪圖抽驗完成並結案，未走訪來源只列證據界線 | 使用者要求完全接管，沿 #7 |
| [006：原譜高品質樂器音樂](006-hd-music.md) | CONFORMED，8段原譜與技術接入；正常開關、桌面音訊與無裝置回退已驗，聽驗待完成 | [#8](https://github.com/wicanr2/dark-queen-of-krynn-cht/issues/8) |
| [007：全量串接、兩輪抽驗與正式交付](007-completion-delivery.md) | CONFORMED；既有兩輪代表抽驗結案；現行v.1.0.1三平台六包、封面開場86秒本機影片及地圖修正完成 | [#13](https://github.com/wicanr2/dark-queen-of-krynn-cht/issues/13) |

package main

import "testing"

func TestAutoMapDismissKeepsOriginalReference(t *testing.T) {
	page := &readerPage{Entry: 25, Image: &readerImageView{}, SourceKey: "original-reference"}
	r := &journalReader{Page: page, Auto: page, Index: 2, Seen: map[int]string{25: page.SourceKey}, Last: 25}
	g := &liveGame{reader: r} // 無Oracle；關閉地圖不能依賴或改寫遊戲狀態。
	g.dismissReaderMap("map-window")
	if readerSeparateMap(r.currentPage()) || r.Index != 0 {
		t.Fatal("關閉後仍會重開同一地圖")
	}
	if r.Auto != page || r.Last != 25 || r.Seen[25] != "original-reference" {
		t.Fatal("原版引用或已讀狀態被改寫")
	}
}

func TestFragmentRemainsInReader(t *testing.T) {
	if readerSeparateMap(&readerPage{Entry: 12, Image: &readerImageView{}}) {
		t.Fatal("碎紙誤當地圖")
	}
	for _, mode := range []string{"manual-map", "guide-map"} {
		if !readerSeparateMap(&readerPage{Mode: mode, Image: &readerImageView{}}) {
			t.Fatal("地圖未使用獨立視窗")
		}
	}
}

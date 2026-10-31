package main

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestKnownPartyNamesStayInDisplayLayer(t *testing.T) {
	root := os.Getenv("DQK_SOURCE_ROOT")
	en := readLiveCatalog(filepath.Join(root, "text/party-names.en.tsv"))
	zh := readLiveCatalog(filepath.Join(root, "text/party-names.zh-TW.tsv"))
	p := &playerTextOwner{Sources: map[string]string{}, NameKeys: map[string]string{}, Catalog: zh, FoldedSources: map[string]string{}}
	if len(en) != 6 || len(zh) != len(en) {
		t.Fatal("預設隊員姓名不完整")
	}
	for key, source := range en {
		p.Sources[source], p.NameKeys[strings.ToLower(source)] = key, key
		p.FoldedSources[strings.ToLower(source)] = zh[key]
	}
	for _, source := range []string{"SIR DRYDEN", "Joris the Wise", "LENDUIRA", "neacail", "ALARIC THE BOLD", "MAIGUREIGNE"} {
		key := p.sourceKey(source)
		if key == "" || zh[key] == "" || p.translateValue(source) != zh[key] {
			t.Fatalf("姓名或稱號未完整翻譯：%q", source)
		}
		format, err := compileDisplayFormat("fixture", "%s loses %d hit points", "%s損失%d點生命力")
		if err != nil {
			t.Fatal(err)
		}
		text, ok := format.Render(source+" loses 12 hit points", p.translateValue)
		if !ok || text != zh[key]+"損失12點生命力" {
			t.Fatalf("戰鬥訊息姓名或數值改變：%q", text)
		}
	}
	for _, source := range []string{"MY HERO", "SIR DRYDEN II", "neacail.dat"} {
		if p.sourceKey(source) != "" || p.translateValue(source) != source {
			t.Fatalf("未知姓名或檔名遭套譯：%q", source)
		}
	}
}

func TestOriginalModeSkipsOwnedTranslation(t *testing.T) {
	// 原版模式連Text與Oracle都不應讀取，更不能留下中文。
	p := &playerRenderOwner{}
	p.ComposeText(nil, &liveGame{translate: false}, nil)
}

func TestNativeDisplayTextRemainsASCII(t *testing.T) {
	for _, source := range []string{"SIR DRYDEN", "JORIS THE WISE", "-6", "30", "%2d", "Arrow +1"} {
		if !nativeDisplaySource(source) {
			t.Fatalf("原版顯示來源被拒：%q", source)
		}
	}
	for _, source := range []string{"", "角色", "name\nnext", "\x01hidden", string(make([]byte, 129))} {
		if nativeDisplaySource(source) {
			t.Fatalf("控制碼／不完整來源被接管：%q", source)
		}
	}
}

func TestCoveredACDoesNotReserveUnpaintedSpace(t *testing.T) {
	// 完整來源AC的「防護力」佔24格，既有HUD的「防護」佔16格。
	// 被HUD接手後，完整來源的額外8格不能留下黑色遮罩。
	protected := [][4]int{{184, 40, 200, 48}}
	if !ownedTextCovered(listWord{X: 184, Y: 40, Width: 24}, protected) {
		t.Fatal("部分重疊的完整來源未交出所有權")
	}
	if ownedTextCovered(listWord{X: 208, Y: 40, Width: 16}, protected) {
		t.Fatal("原版防護數值被相鄰標籤遮住")
	}
	if ownedTextCovered(listWord{X: 184, Y: 48, Width: 24}, protected) {
		t.Fatal("相鄰下一行被遮住")
	}
}

func TestCopiedDisplayWordsRequireCompleteSource(t *testing.T) {
	w := listWord{X: 8, Y: 8, Width: 112, Key: "name.fixture"}
	if got, ok := copiedDisplayWord(w, 0, 0, 16000); !ok || got != w {
		t.Fatal("完整換頁沒有保留姓名位置")
	}
	if got, ok := copiedDisplayWord(w, 0, 80, 15920); !ok || got.X != 8 || got.Y != 9 || got.Key != w.Key {
		t.Fatal("文字搬移位移不符")
	}
	for _, args := range [][3]int{{0, 0, 641}, {643, 0, 1000}, {0, 15999, 16000}, {0, 70, 16000}} {
		if _, ok := copiedDisplayWord(w, args[0], args[1], args[2]); ok {
			t.Fatalf("部分字框或越界搬移取得所有權：%v", args)
		}
	}
}

func TestMouseUsesOriginalDriverUnits(t *testing.T) {
	// DQK把範圍設為0..2559×0..1599並把AX=3讀值除以8；驅動回報CX＝X×2、DX＝Y。
	for _, p := range [][2]int{{0, 0}, {40, 40}, {160, 100}, {300, 190}, {319, 199}} {
		x, y := dqkMouseDriverPosition(p[0], p[1])
		if cx, dy := x*2, y; cx/8 != p[0] || dy/8 != p[1] || cx > 2559 || dy > 1599 {
			t.Fatalf("遊戲讀回%d,%d，應為%v", cx/8, dy/8, p)
		}
		if gx, gy := dqkMouseGamePixel(x, y); gx != p[0] || gy != p[1] {
			t.Fatalf("呈現層游標位置%d,%d，應為%v", gx, gy, p)
		}
	}
}

func TestCursorRunsOnlyTemporaryPixelsInText(t *testing.T) {
	// 只補回游標附近、中文框內、底層素材仍在但暫時不可見的像素。
	asset := &sceneAsset{W: 1, H: 1, Index: []byte{7}}
	model := new(scenePage)
	hidden := sceneCell{Asset: asset, Visible: false}
	model.Cells[100*320+100] = hidden                                 // 框內游標像素
	model.Cells[100*320+101] = hidden                                 // 同列相鄰
	model.Cells[100*320+102] = sceneCell{Asset: asset, Visible: true} // 可見素材
	model.Cells[100*320+103] = sceneCell{}                            // 非自有像素
	model.Cells[95*320+100] = hidden                                  // 框外
	model.Cells[100*320+120] = hidden                                 // 離游標太遠
	runs := temporaryCursorRuns(model, 104, 102, [][4]int{{96, 98, 140, 106}})
	if len(runs) != 1 || runs[0] != [3]int{100, 100, 102} {
		t.Fatalf("游標補回範圍錯誤：%v", runs)
	}
	if len(temporaryCursorRuns(model, 0, 0, [][4]int{{96, 98, 140, 106}})) != 0 {
		t.Fatal("游標不在附近時不應補回")
	}
}

func TestTemporaryCursorKeepsKnownText(t *testing.T) {
	// 游標改變當下色號，底下仍保留原字形；普通清除及新字形則會撤除它。
	asset := &sceneAsset{W: 1, H: 1, Index: []byte{7}}
	if !retainedTextPixel(0, 7, sceneCell{Asset: asset, Source: 0, Visible: false}) {
		t.Fatal("暫時游標遮住後遺失中文")
	}
	if retainedTextPixel(0, 7, sceneCell{}) || retainedTextPixel(0, 7, sceneCell{Asset: asset, Visible: true}) {
		t.Fatal("普通清除或覆寫留下過期中文")
	}
	if retainedTextPixel(0, 11, sceneCell{Asset: asset}) {
		t.Fatal("不同底層字形被錯認為原字形")
	}
}

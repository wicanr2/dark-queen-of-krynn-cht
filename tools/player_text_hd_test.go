package main

import "testing"

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

package main

import (
	"bytes"
	"image"
	"image/color"
	"testing"
)

func clothTextFixture(thin bool) (*image.NRGBA, *image.NRGBA, imageTextFont) {
	src := image.NewNRGBA(image.Rect(0, 0, 304, 55))
	hi := 22
	if thin {
		hi = 19
	}
	for y := 16; y < hi; y++ {
		for x := 90; x < 210; x++ {
			src.SetNRGBA(x, y, color.NRGBA{240, 210, 30, 255})
		}
	}
	src.SetNRGBA(150, 17, color.NRGBA{60, 100, 0, 255})
	out := image.NewNRGBA(image.Rect(0, 0, 912, 165))
	for y := 0; y < 165; y++ {
		for x := 0; x < 912; x++ {
			c := src.NRGBAAt(x/3, y/3)
			if c.A != 0 {
				out.SetNRGBA(x, y, color.NRGBA{230, 180, 20, 255})
			}
		}
	}
	for y := 51; y < 54; y++ {
		for x := 450; x < 453; x++ {
			out.SetNRGBA(x, y, color.NRGBA{0, 80, 0, 255})
		}
	}
	g := make([]byte, 320)
	for y := 1; y < 15; y++ {
		for x := 1; x < 15; x++ {
			g[y*16+x] = 255
		}
	}
	return src, out, imageTextFont{16, 20, map[string][]byte{"測": g, "試": g}}
}

func TestClothTextContainedAndAlphaPreserved(t *testing.T) {
	src, art, font := clothTextFixture(false)
	before := append([]byte(nil), art.Pix...)
	out, r, err := compileClothText(src, art, "測試", font)
	if err != nil || r.State != "localized" || r.ClearedPixels == 0 || r.GlyphInkPixels != 392 {
		t.Fatalf("編譯結果：%+v %v", r, err)
	}
	if !bytes.Equal(before, art.Pix) {
		t.Fatal("不應修改輸入圖")
	}
	for y := 0; y < 165; y++ {
		for x := 0; x < 912; x++ {
			if out.NRGBAAt(x, y).A != art.NRGBAAt(x, y).A {
				t.Fatal("原生透明範圍改變")
			}
			if src.NRGBAAt(x/3, y/3).A == 0 && out.NRGBAAt(x, y) != art.NRGBAAt(x, y) {
				t.Fatal("字墨寫入透明區域")
			}
		}
	}
}

func TestClothTextRejectsThinClothAndMissingGlyph(t *testing.T) {
	src, art, font := clothTextFixture(true)
	out, r, err := compileClothText(src, art, "測試", font)
	if err != nil || r.State != "partially-unfurled-no-full-text-box" || !bytes.Equal(out.Pix, art.Pix) {
		t.Fatalf("窄布料應保持：%+v %v", r, err)
	}
	if _, _, err = compileClothText(src, art, "缺", font); err == nil {
		t.Fatal("缺字必須拒絕")
	}
}

func TestImageTextCatalogRejectsDuplicateAndMissing(t *testing.T) {
	for _, raw := range []string{"key\ttext\na\t一\na\t二\n", "key\ttext\nb\t二\n"} {
		if _, err := imageTextCatalog([]byte(raw), "a"); err == nil {
			t.Fatal("不可接受重複鍵或缺鍵")
		}
	}
	if text, err := imageTextCatalog([]byte("key\ttext\na\t我們的英雄\n"), "a"); err != nil || text != "我們的英雄" {
		t.Fatalf("正確TSV未保留：%q %v", text, err)
	}
}

func TestClothTextFollowsLoweredCloth(t *testing.T) {
	src, art, font := clothTextFixture(false)
	lower := image.NewNRGBA(src.Bounds())
	lowerArt := image.NewNRGBA(art.Bounds())
	for y := 0; y < 35; y++ {
		for x := 0; x < 304; x++ {
			lower.SetNRGBA(x, y+20, src.NRGBAAt(x, y))
		}
	}
	for y := 0; y < 105; y++ {
		for x := 0; x < 912; x++ {
			lowerArt.SetNRGBA(x, y+60, art.NRGBAAt(x, y))
		}
	}
	_, r, err := compileClothText(lower, lowerArt, "測試", font)
	if err != nil || r.State != "localized" || r.Box[1] < 108 || r.ClearedPixels == 0 {
		t.Fatalf("安全框未隨布料下垂：%+v %v", r, err)
	}
}

func TestClothTextRemovesGoldenLetterOutline(t *testing.T) {
	src, art, font := clothTextFixture(false)
	// 舊字的金色外框也符合布料金色條件，不能當作乾淨材質保留。
	art.SetNRGBA(450, 65, color.NRGBA{255, 230, 30, 255})
	out, r, err := compileClothText(src, art, "測試", font)
	if err != nil || r.State != "localized" || r.RecompiledPixels != r.ClothPixels {
		t.Fatalf("布料未完整重編：%+v %v", r, err)
	}
	if out.NRGBAAt(450, 65) != (color.NRGBA{230, 180, 20, 255}) {
		t.Fatal("金色舊字外框未清除")
	}
}

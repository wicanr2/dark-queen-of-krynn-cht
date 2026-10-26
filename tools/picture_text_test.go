package main

import (
	"bytes"
	"encoding/json"
	"image"
	"image/png"
	"os"
	"path/filepath"
	"testing"
)

func pictureFixture() (*pictureTextLayer, *scenePage, *sceneAsset, *pictureTextBinding, [256][3]byte) {
	var pal [256][3]byte
	pal[1] = [3]byte{40, 50, 60}
	pal[2] = [3]byte{150, 20, 10}
	pal[3] = [3]byte{10, 200, 30}
	s := new(renderScene)
	p := s.page(0, func(int, uint32) byte { return 1 })
	bg := &sceneAsset{W: 320, H: 200, Index: bytes.Repeat([]byte{1}, 64000), Reference: bytes.Repeat([]byte{40, 50, 60}, 64000), HD: bytes.Repeat([]byte{70, 80, 90, 255}, 64000*9)}
	s.record(p, bg, 0, 0)
	a := &sceneAsset{W: 16, H: 8, Index: bytes.Repeat([]byte{2}, 128), Alpha: make([]byte, 128)}
	for i := 0; i < 128; i += 3 {
		a.Alpha[i] = 255
	}
	g := make([]byte, 320)
	g[5*16+5] = 255
	b := pictureTextBinding{Key: "fixture", W: 16, H: 8, IndexSHA256: pictureDigest(a.Index), AlphaSHA256: pictureDigest(a.Alpha), Captions: []pictureCaption{{Key: "direction", ClearBox: [4]int{0, 0, 48, 24}, TextBox: [4]int{0, 0, 48, 24}, Scale: 1, Mode: "background", Foreground: 3}}}
	l := &pictureTextLayer{Catalog: map[string]string{"direction": "北"}, Font: pictureTextFont{16, 20, map[string][]byte{"北": g}}}
	return l, p, a, &b, pal
}
func TestPictureTextBackgroundAndPalette(t *testing.T) {
	l, p, a, b, pal := pictureFixture()
	s := new(renderScene)
	if !l.capture(b, a, p, 8, 8, 0) {
		t.Fatal("來源未綁定")
	}
	s.record(p, a, 8, 8)
	native := p.Index
	for _, hd := range []bool{false, true} {
		r, boxes := l.prepare(p, 0, pal, hd, nil)
		if len(r) != 1 || len(boxes) != 1 {
			t.Fatal("圖片未一次替換")
		}
		out := r[0].Asset.HD
		want := []byte{40, 50, 60, 255}
		if hd {
			want = []byte{70, 80, 90, 255}
		}
		if !bytes.Equal(out[:4], want) {
			t.Fatalf("舊字區域沒有取繪製前底圖：%v", out[:4])
		}
		at := ((4+5)*48 + 16 + 5) * 4
		if !bytes.Equal(out[at:at+4], []byte{10, 200, 30, 255}) {
			t.Fatal("正式字模未繪製")
		}
		coverage := [64000]bool{}
		for _, v := range append(p.rectangles(hd, pal, boxes), r...) {
			for y := v.Y; y < v.Y+v.H; y++ {
				for x := v.X; x < v.X+v.W; x++ {
					if coverage[y*320+x] {
						t.Fatal("原圖與中文矩形重疊")
					}
					coverage[y*320+x] = true
				}
			}
		}
	}
	pal[1] = [3]byte{4, 5, 6}
	pal[3] = [3]byte{1, 20, 3}
	r, _ := l.prepare(p, 0, pal, true, nil)
	if !bytes.Equal(r[0].Asset.HD[:4], []byte{4, 5, 6, 255}) {
		t.Fatal("淡入色盤沒有沿原色號")
	}
	if p.Index != native {
		t.Fatal("翻譯不得改原生索引")
	}
}
func TestPictureTextOcclusionAndRepeatedCapture(t *testing.T) {
	l, p, a, b, pal := pictureFixture()
	s := new(renderScene)
	l.capture(b, a, p, 8, 8, 0)
	s.record(p, a, 8, 8)
	l.capture(b, a, p, 8, 8, 0)
	if l.Occurrences[0].BackgroundIndex[0] != 1 {
		t.Fatal("重複命令把自己的舊字當成背景")
	}
	if r, _ := l.prepare(p, 0, pal, false, [][4]int{{9, 9, 10, 10}}); len(r) != 0 {
		t.Fatal("圖片不可覆蓋新的文字框")
	}
	old := p.Cells[8*320+8]
	p.Cells[8*320+8] = sceneCell{}
	if r, _ := l.prepare(p, 0, pal, false, nil); len(r) != 0 {
		t.Fatal("前景被覆寫後仍顯示舊中文")
	}
	p.Cells[8*320+8] = old
	p.Index[8*320+9] = 7
	if r, _ := l.prepare(p, 0, pal, false, nil); len(r) != 0 {
		t.Fatal("透明背景改變後仍顯示舊底圖")
	}
	if r, _ := l.prepare(p, 0x4000, pal, false, nil); len(r) != 0 {
		t.Fatal("隱藏頁不可提前顯示")
	}
}
func TestPictureTextRejectsDifferentNativeData(t *testing.T) {
	l, p, a, b, _ := pictureFixture()
	b.IndexSHA256 = pictureDigest([]byte{1})
	if l.capture(b, a, p, 8, 8, 0) {
		t.Fatal("不同來源色號被接受")
	}
	if _, err := pictureCatalog([]byte("key\ttext\na\t北\na\t南\n")); err == nil {
		t.Fatal("重複鍵被接受")
	}
}

func TestPictureTextTemporaryCursorKeepsChinese(t *testing.T) {
	l, p, a, b, pal := pictureFixture()
	s := new(renderScene)
	l.capture(b, a, p, 8, 8, 0)
	s.record(p, a, 8, 8)
	for _, n := range []int{0, 1} {
		i := 8*320 + 8 + n
		c := p.Cells[i]
		c.Visible = false
		p.Cells[i] = c
		p.Index[i] = 3
	}
	r, _ := l.prepare(p, 0, pal, false, nil)
	if len(r) != 1 {
		t.Fatal("暫時游標使圖片回退英文")
	}
	if !bytes.Equal(r[0].Asset.HD[:4], []byte{10, 200, 30, 255}) {
		t.Fatal("游標沒有併入同一紋理")
	}
	if !bytes.Equal(r[0].Asset.HD[6*4:6*4+4], []byte{40, 50, 60, 255}) {
		t.Fatal("游標以外的舊字重新出現")
	}
}

func TestPictureTextOtherImageRegionDoesNotRemoveCaption(t *testing.T) {
	l, p, a, b, pal := pictureFixture()
	b.Captions[0].ClearBox = [4]int{0, 0, 24, 24}
	b.Captions[0].TextBox = [4]int{0, 0, 24, 24}
	s := new(renderScene)
	l.capture(b, a, p, 8, 8, 0)
	s.record(p, a, 8, 8)
	p.Cells[8*320+23] = sceneCell{}
	r, _ := l.prepare(p, 0, pal, false, nil)
	if len(r) != 1 || r[0].W != 8 {
		t.Fatal("圖片其他區域的覆寫不應撤掉仍可見的文字區域")
	}
}

// 實際本機來源只檢查圖片資料與Go排版，不執行原版或冒充正常玩家路徑。
func TestPictureTextSourceCorpus(t *testing.T) {
	root := os.Getenv("DQK_PICTURE_TEXT_ROOT")
	if root == "" {
		t.Skip("未提供本機唯讀來源")
	}
	base := filepath.Join(root, "workplace/probe/player-pictures-20261027/picture-text")
	l, err := loadPictureText(base)
	if err != nil {
		t.Fatal(err)
	}
	if l == nil || len(l.Bindings) != 24 {
		t.Fatal("來源清單數量不符")
	}
	inv := filepath.Join(root, "workplace/probe/hd-assets-20261026-r3")
	raw, err := os.ReadFile(filepath.Join(inv, "inventory.json"))
	if err != nil {
		t.Fatal(err)
	}
	var inventory struct {
		Records []struct {
			Key     string
			Palette [][3]byte
		}
	}
	if err = json.Unmarshal(raw, &inventory); err != nil {
		t.Fatal(err)
	}
	pals := map[string][256][3]byte{}
	for _, r := range inventory.Records {
		var pal [256][3]byte
		copy(pal[:], r.Palette)
		pals[r.Key] = pal
	}
	for n := range l.Bindings {
		b := &l.Bindings[n]
		t.Run(b.Key, func(t *testing.T) {
			idx, e := os.ReadFile(filepath.Join(inv, b.Key+".idx"))
			if e != nil {
				t.Fatal(e)
			}
			f, e := os.Open(filepath.Join(inv, b.Key+".png"))
			if e != nil {
				t.Fatal(e)
			}
			im, e := png.Decode(f)
			f.Close()
			if e != nil {
				t.Fatal(e)
			}
			a := &sceneAsset{W: b.W, H: b.H, Index: idx, Alpha: make([]byte, b.W*b.H)}
			for y := 0; y < b.H; y++ {
				for x := 0; x < b.W; x++ {
					_, _, _, alpha := im.At(x, y).RGBA()
					a.Alpha[y*b.W+x] = byte(alpha >> 8)
				}
			}
			l.Occurrences = nil
			s := new(renderScene)
			p := s.page(0, func(int, uint32) byte { return 0 })
			if !l.capture(b, a, p, 0, 0, 0) {
				t.Fatal("原生來源失配")
			}
			s.record(p, a, 0, 0)
			before := p.Index
			r, _ := l.prepare(p, 0, pals[b.Key], false, nil)
			if len(r) != len(b.Captions) || p.Index != before {
				t.Fatal("實際圖片替換或索引保存失敗")
			}
			composed := image.NewNRGBA(image.Rect(0, 0, b.W*3, b.H*3))
			for y := 0; y < b.H*3; y++ {
				for x := 0; x < b.W*3; x++ {
					n := y/3*b.W + x/3
					at := (y*b.W*3 + x) * 4
					var col [3]byte
					if a.Alpha[n] > 0 {
						col = pals[b.Key][a.Index[n]]
					}
					copy(composed.Pix[at:at+3], col[:])
					composed.Pix[at+3] = 255
				}
			}
			for _, v := range r {
				for y := v.Y * 3; y < (v.Y+v.H)*3; y++ {
					for x := v.X * 3; x < (v.X+v.W)*3; x++ {
						at := (y*b.W*3 + x) * 4
						copy(composed.Pix[at:at+4], v.Asset.HD[at:at+4])
					}
				}
			}
			if b.Key[:5] == "FRAME" {
				// 中央指針與方位字分開；翻譯不得擦掉指針。
				for y := 16; y < 28; y++ {
					for x := 28; x < 36; x++ {
						red, green, blue, alpha := im.At(x, y).RGBA()
						if alpha == 0 {
							continue
						}
						for yy := 0; yy < 3; yy++ {
							for xx := 0; xx < 3; xx++ {
								at := ((y*3+yy)*b.W*3 + x*3 + xx) * 4
								if !bytes.Equal(composed.Pix[at:at+3], []byte{byte(red >> 8), byte(green >> 8), byte(blue >> 8)}) {
									t.Fatal("羅盤中央指針改變")
								}
							}
						}
					}
				}
			}
			if out := os.Getenv("DQK_PICTURE_TEXT_OUTPUT"); out != "" {
				im := composed
				f, e := os.Create(filepath.Join(out, b.Key+"-zh.png"))
				if e != nil {
					t.Fatal(e)
				}
				e = png.Encode(f, im)
				f.Close()
				if e != nil {
					t.Fatal(e)
				}
			}
		})
	}
}

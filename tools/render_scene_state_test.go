package main

import (
	"bytes"
	"encoding/hex"
	"encoding/json"
	"image/png"
	"os"
	"path/filepath"
	"testing"
)

// 不執行原版 CPU。讀回、遮擋、隱藏頁及選定美術各自有可觀察結果。
func TestSceneReadbackAndRestore(t *testing.T) {
	var planes [4][65536]byte
	raw := func(p int, o uint32) byte { return planes[p][o] }
	put := func(p int, o uint32, v byte) { planes[p][o] = v }
	s := new(renderScene)
	page := s.page(0x4000, raw)
	a := &sceneAsset{W: 4, H: 1, Index: []byte{2, 3, 4, 5}}
	s.record(page, a, 8, 1)
	if planes[0][0x4052] != 0 {
		t.Fatal("接管時不應產生原版像素")
	}
	if s.materialize(0x4052, put) != 4 {
		t.Fatal("讀回應只補四個色號")
	}
	if planes[2][0x4052] != 4 {
		t.Fatal("平面定址錯誤")
	}
	planes[2][0x4052] = 99
	s.nativeWrite(0x4052, 4, true, false, raw)
	if page.Cells[330].Visible || page.Index[330] != 99 {
		t.Fatal("暫時遮擋應顯示原版讀寫結果")
	}
	planes[2][0x4052] = 4
	s.nativeWrite(0x4052, 4, true, false, raw)
	if !page.Cells[330].Visible {
		t.Fatal("原版恢復讀回背景時應重新顯示同一命令")
	}
	s.nativeWrite(0x4052, 4, false, false, raw)
	if page.Cells[330].Asset != nil {
		t.Fatal("永久覆寫即使同色也不能保留舊 HD")
	}
	if s.page(0, raw).Cells[328].Asset != nil {
		t.Fatal("隱藏頁不得提前污染可見頁")
	}
}

func TestSceneVariantAndProtectedText(t *testing.T) {
	s := new(renderScene)
	p := s.page(0, func(int, uint32) byte { return 0 })
	var pal [256][3]byte
	pal[7] = [3]byte{10, 20, 30}
	a := &sceneAsset{W: 4, H: 1, Index: []byte{7, 7, 7, 7}, Alpha: []byte{255, 0, 255, 255}, Reference: bytes.Repeat([]byte{10, 20, 30}, 4), HD: bytes.Repeat([]byte{90, 80, 70, 255}, 36)}
	s.record(p, a, 0, 0)
	out := p.rgba(true, pal, [][4]int{{2, 0, 3, 1}})
	if !bytes.Equal(out[:4], []byte{90, 80, 70, 255}) {
		t.Fatal("HD 應直接選定，不包含原版 RGB")
	}
	if out[3*4+3] != 0 || out[6*4+3] != 0 {
		t.Fatal("透明像素與中文保護區應保持透明")
	}
	if !bytes.Equal(out[9*4:9*4+4], []byte{90, 80, 70, 255}) {
		t.Fatal("保護部分不得撤掉整張圖片")
	}
	out = p.rgba(false, pal, nil)
	if !bytes.Equal(out[:4], []byte{10, 20, 30, 255}) {
		t.Fatal("關閉 HD 應以同一命令選擇原版")
	}
	pal[7] = [3]byte{1, 2, 3}
	out = p.rgba(true, pal, nil)
	if !bytes.Equal(out[:4], []byte{1, 2, 3, 255}) {
		t.Fatal("色盤變動時應採原版色號")
	}
}

func TestSceneUnownedGlyphAndClear(t *testing.T) {
	s := new(renderScene)
	p := s.page(0, func(int, uint32) byte { return 1 })
	s.nativeWrite(0, 15, false, true, func(int, uint32) byte { return 9 })
	if p.safe([4]int{0, 0, 4, 1}) {
		t.Fatal("未接管字形不可再覆中文字")
	}
	s.record(p, &sceneAsset{W: 4, H: 1, Index: []byte{0, 0, 0, 0}}, 0, 0)
	if !p.safe([4]int{0, 0, 4, 1}) {
		t.Fatal("清框後應允許下一筆命令")
	}
}

func TestImageDecoderLimits(t *testing.T) {
	header := [8]byte{1, 0, 0, 0, 0, 0, 2, 18}
	for _, body := range [][]byte{{}, {7, 1, 2}, {128, 1}, {255}} {
		if _, _, err := decodeSceneImage(header, body); err == nil {
			t.Fatalf("損壞壓縮不可接管：%x", body)
		}
	}
	a, used, err := decodeSceneImage(header, []byte{249, 6})
	if err != nil || used != 2 || !bytes.Equal(a.Index, bytes.Repeat([]byte{6}, 8)) {
		t.Fatal(a, used, err)
	}
	header[7] = 23
	if _, _, err := decodeSceneImage(header, make([]byte, 8)); err == nil {
		t.Fatal("未知格式不可猜解")
	}
}

// 使用現有素材及原始 TLB，逐項核解碼，不啟動遊戲或 GUI。
func TestNativeAssetCorpus(t *testing.T) {
	root := os.Getenv("DQK_ASSET_CORPUS")
	if root == "" {
		t.Skip("未提供本機唯讀原版資料")
	}
	raw, err := os.ReadFile(filepath.Join(root, "workplace/probe/player-current/hd/hd.json"))
	if err != nil {
		t.Fatal(err)
	}
	var corpus struct {
		Assets []struct {
			Key, Indexed, SourceFile, Header string
			Offset                           int
		}
	}
	var manifest struct{ Assets []json.RawMessage }
	if err := json.Unmarshal(raw, &manifest); err != nil {
		t.Fatal(err)
	}
	for _, entry := range manifest.Assets {
		var r struct {
			Key, Indexed string
			File         string `json:"source_file"`
			Header       string `json:"source_header_hex"`
			Offset       int    `json:"source_offset"`
		}
		if err := json.Unmarshal(entry, &r); err != nil {
			t.Fatal(err)
		}
		corpus.Assets = append(corpus.Assets, struct {
			Key, Indexed, SourceFile, Header string
			Offset                           int
		}{r.Key, r.Indexed, r.File, r.Header, r.Offset})
	}
	if len(corpus.Assets) != 48 {
		t.Fatalf("目前素材數量改變：%d", len(corpus.Assets))
	}
	for _, r := range corpus.Assets {
		t.Run(r.Key, func(t *testing.T) {
			data, err := os.ReadFile(filepath.Join(root, "workplace/input/dos/drkqueen", r.SourceFile))
			if err != nil {
				t.Fatal(err)
			}
			hexHeader, err := hex.DecodeString(r.Header)
			if err != nil || len(hexHeader) != 8 {
				t.Fatal("標頭失配")
			}
			var header [8]byte
			copy(header[:], hexHeader)
			if r.Offset < 0 || r.Offset+8 > len(data) || !bytes.Equal(data[r.Offset:r.Offset+8], header[:]) {
				t.Fatal("原始 TLB 定位失配")
			}
			a, _, err := decodeSceneImage(header, data[r.Offset+8:])
			if err != nil {
				t.Fatal(err)
			}
			want, err := os.ReadFile(filepath.Join(root, "workplace/probe/player-current/hd", r.Indexed))
			if err != nil {
				t.Fatal(err)
			}
			if !bytes.Equal(a.Index, want) {
				t.Fatal("來源色號與既有盤點不同")
			}
			pngPath := filepath.Join(root, "workplace/probe/player-current/hd", r.Indexed[:len(r.Indexed)-4]+".png")
			file, err := os.Open(pngPath)
			if err != nil {
				t.Fatal(err)
			}
			pic, err := png.Decode(file)
			file.Close()
			if err != nil {
				t.Fatal(err)
			}
			for y := 0; y < a.H; y++ {
				for x := 0; x < a.W; x++ {
					_, _, _, alpha := pic.At(x, y).RGBA()
					opaque := len(a.Alpha) == 0 || a.Alpha[y*a.W+x] != 0
					if opaque != (alpha != 0) {
						t.Fatal("原始透明範圍不符")
					}
				}
			}
		})
	}
}

func TestSceneRectangleBatch(t *testing.T) {
	s := new(renderScene)
	p := s.page(0, func(int, uint32) byte { return 0 })
	var pal [256][3]byte
	for i := range pal {
		pal[i] = [3]byte{byte(i), byte(i + 1), byte(i + 2)}
	}
	bg := &sceneAsset{W: 16, H: 8, Index: make([]byte, 128)}
	s.record(p, bg, 0, 0)
	if rects := p.rectangles(false, pal, nil); len(rects) != 1 || rects[0].W != 16 || rects[0].H != 8 {
		t.Fatalf("完整矩形未合併：%v", rects)
	}
	a := &sceneAsset{W: 12, H: 6, Index: make([]byte, 72), Alpha: make([]byte, 72), Reference: make([]byte, 216), HD: make([]byte, 72*36)}
	for i := range a.Index {
		a.Index[i] = byte(i + 1)
		a.Alpha[i] = 255
		if i%7 == 0 {
			a.Alpha[i] = 0
		}
		col := pal[a.Index[i]]
		copy(a.Reference[i*3:i*3+3], col[:])
		for yy := 0; yy < 3; yy++ {
			for xx := 0; xx < 3; xx++ {
				at := ((i/12*3+yy)*36 + i%12*3 + xx) * 4
				copy(a.HD[at:at+4], []byte{byte(i), byte(xx), byte(yy), 255})
			}
		}
	}
	s.record(p, a, 2, 1)
	protected := [][4]int{{4, 3, 6, 4}}
	for _, hd := range []bool{false, true} {
		out := make([]byte, 960*600*4)
		coverage := [64000]bool{}
		for _, r := range p.rectangles(hd, pal, protected) {
			for y := 0; y < r.H; y++ {
				for x := 0; x < r.W; x++ {
					cell := (r.Y+y)*320 + r.X + x
					if coverage[cell] {
						t.Fatal("同一像素被矩形重複繪製")
					}
					coverage[cell] = true
					for yy := 0; yy < 3; yy++ {
						for xx := 0; xx < 3; xx++ {
							dst := (((r.Y+y)*3+yy)*960 + (r.X+x)*3 + xx) * 4
							if r.HD {
								src := (((r.SY+y)*3+yy)*r.Asset.W*3 + (r.SX+x)*3 + xx) * 4
								copy(out[dst:dst+4], r.Asset.HD[src:src+4])
							} else {
								col := pal[r.Asset.Index[(r.SY+y)*r.Asset.W+r.SX+x]]
								copy(out[dst:dst+3], col[:])
								out[dst+3] = 255
							}
						}
					}
				}
			}
		}
		if !bytes.Equal(out, p.rgba(hd, pal, protected)) {
			t.Fatal("矩形批次與獨立逐格參考畫面不同")
		}
	}
}

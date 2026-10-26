package main

import (
	"bytes"
	"encoding/hex"
	"encoding/json"
	"image"
	"image/color"
	"image/png"
	"os"
	"path/filepath"
	"testing"

	"github.com/wicanr2/dosgolem/oracle"
)

func TestHDLookupPaletteVariants(t *testing.T) {
	// 自製COM只建立Oracle記憶體與色盤；不執行或冒充原版遊戲。
	dir := t.TempDir()
	path := filepath.Join(dir, "palette.com")
	if err := os.WriteFile(path, []byte{0x90}, 0600); err != nil {
		t.Fatal(err)
	}
	o, err := oracle.LoadProgram(path, dir, "")
	if err != nil {
		t.Fatal(err)
	}
	defer o.Close()
	command := sourceTileCommand{Source: oracle.Addr{Seg: 0x7000, Off: 0x100}}
	command.Header = [8]byte{8, 0, 0, 0, 0, 0, 2, 16}
	body := []byte{19, 23, 29}
	o.WriteBytes(command.Source, body)
	pal, steps := o.Palette(), o.Steps()
	c := pal[7]
	good := uint32(c[0])<<16 | uint32(c[1])<<8 | uint32(c[2])
	first, second := &playerImageAsset{W: 8}, &playerImageAsset{W: 8}
	hash := digest(append(append([]byte(nil), command.Header[:]...), body...))
	a := &hdAsset{W: 8, H: 8, SourceBytes: 11, SourceSHA256: hash, Image: first, Colors: map[byte]uint32{7: good ^ 0x010000}}
	b := &hdAsset{W: 8, H: 8, SourceBytes: 11, SourceSHA256: hash, Image: second, Colors: map[byte]uint32{7: good}}
	layer := &hdLayer{BySourceHeader: map[string][]*hdAsset{hex.EncodeToString(command.Header[:]): {a, b}}}
	if got := layer.Lookup(o, command); got != second {
		t.Fatal("相同來源應選當前色盤版本，不能固定取第一項")
	}
	a.Colors[7] = good
	if got := layer.Lookup(o, command); got != first {
		t.Fatal("完全相同來源與色盤的別名維持穩定順序")
	}
	a.Colors[7], b.Colors[7] = good^0x010000, good^0x000100
	if got := layer.Lookup(o, command); got != first {
		t.Fatal("未知色盤須保留來源，交場景色盤檢查回退原版")
	}
	a.SourceSHA256, b.SourceSHA256 = "失配", "失配"
	if layer.Lookup(o, command) != nil {
		t.Fatal("色盤不得取代完整來源雜湊")
	}
	a.SourceSHA256, b.SourceSHA256 = hash, hash
	command.X = 313
	if layer.Lookup(o, command) != nil {
		t.Fatal("色盤版本不得放寬畫布邊界")
	}
	if o.Palette() != pal || o.Steps() != steps || !bytes.Equal(o.Bytes(command.Source, len(body)), body) {
		t.Fatal("HD選擇不得改動Oracle")
	}
}

func TestHDPaletteIgnoresTransparentPixels(t *testing.T) {
	dir := t.TempDir()
	original := image.NewNRGBA(image.Rect(0, 0, 16, 8))
	painted := image.NewNRGBA(image.Rect(0, 0, 48, 24))
	indexed := make([]byte, 128)
	for y := 0; y < 8; y++ {
		for x := 0; x < 16; x++ {
			c := color.NRGBA{R: 90, G: byte(x), B: 17}
			indexed[y*16+x] = 123
			if x < 8 {
				c = color.NRGBA{R: byte(x%2) * 255, A: 255}
				indexed[y*16+x] = byte(x%2) + 1
			}
			original.SetNRGBA(x, y, c)
			for yy := 0; yy < 3; yy++ {
				for xx := 0; xx < 3; xx++ {
					painted.SetNRGBA(x*3+xx, y*3+yy, c)
				}
			}
		}
	}
	writePNG := func(name string, im image.Image) string {
		var buf bytes.Buffer
		if err := png.Encode(&buf, im); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(filepath.Join(dir, name), buf.Bytes(), 0600); err != nil {
			t.Fatal(err)
		}
		return digest(buf.Bytes())
	}
	originalSHA, paintedSHA := writePNG("original.png", original), writePNG("painted.png", painted)
	if err := os.WriteFile(filepath.Join(dir, "original.idx"), indexed, 0600); err != nil {
		t.Fatal(err)
	}
	record := hdAssetRecord{Key: "synthetic-alpha", Original: "original.png", Image: "painted.png", Indexed: "original.idx", OriginalSHA256: originalSHA, SHA256: paintedSHA, IndexedSHA256: digest(indexed), SourceHeader: "0800000000000410", SourceBytes: 136, SourceSHA256: digest(indexed)}
	data, err := json.Marshal(map[string]any{"Version": 1, "Scale": 3, "Ready": true, "Assets": []hdAssetRecord{record}})
	if err != nil {
		t.Fatal(err)
	}
	if err = os.WriteFile(filepath.Join(dir, "hd.json"), data, 0600); err != nil {
		t.Fatal(err)
	}
	renderer := loadHDLayer(dir)
	layer, ok := renderer.(*hdLayer)
	if !ok || len(layer.Assets) != 1 {
		t.Fatal("合法透明素材應完整載入")
	}
	colors := layer.Assets[0].Colors
	if len(colors) != 2 || colors[1] != 0 || colors[2] != 0xff0000 {
		t.Fatalf("只索引可見色號：%v", colors)
	}
	if _, exists := colors[123]; exists {
		t.Fatal("透明像素不得限制當前色盤")
	}
}

func TestHDCompleteProjectileScope(t *testing.T) {
	for _, tc := range []struct {
		key              string
		w, h, foreground int
		want             bool
	}{
		{"COMSPR..2", 24, 24, 48, true},
		{"COMSPR..47", 24, 24, 12, true},
		{"COMSPR..2", 24, 24, 11, false},
		{"COMSPR..1", 24, 24, 48, false},
		{"COMSPR..48", 24, 24, 48, false},
		{"PICA.6.2", 24, 24, 48, false},
		{"COMSPR..2", 16, 24, 48, false},
		{"COMSPR..2", 24, 16, 48, false},
		{"COMSPR..bad", 24, 24, 48, false},
	} {
		if got := hdCompleteProjectile(tc.key, tc.w, tc.h, tc.foreground); got != tc.want {
			t.Fatalf("完整投射物邊界 %v：得到%t", tc, got)
		}
	}
}

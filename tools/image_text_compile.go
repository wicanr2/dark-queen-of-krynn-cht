// 將正式圖片文案編譯進已生成布料。僅處理FINAL.2的已知布條，不改遊戲資料。
package main

import (
	"bytes"
	"crypto/sha256"
	"encoding/csv"
	"encoding/hex"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"image"
	"image/color"
	"image/draw"
	"image/png"
	"os"
	"strconv"
	"strings"
)

type imageTextFont struct {
	Size   int               `json:"size"`
	Height int               `json:"height"`
	Glyphs map[string][]byte `json:"glyphs"`
}

type imageTextResult struct {
	State            string `json:"state"`
	Text             string `json:"text"`
	Box              [4]int `json:"text_safe_box"`
	ClothPixels      int    `json:"cloth_pixels"`
	ClearedPixels    int    `json:"cleared_generated_text_pixels"`
	RecompiledPixels int    `json:"recompiled_cloth_pixels"`
	GlyphInkPixels   int    `json:"glyph_ink_pixels"`
	AlphaUnchanged   bool   `json:"alpha_unchanged"`
	OutsideUnchanged bool   `json:"outside_cloth_rgb_unchanged"`
}

func imageTextSHA(raw []byte) string {
	h := sha256.Sum256(raw)
	return hex.EncodeToString(h[:])
}

func imageTextCatalog(raw []byte, key string) (string, error) {
	r := csv.NewReader(bytes.NewReader(raw))
	r.Comma = '\t'
	rows, err := r.ReadAll()
	if err != nil || len(rows) < 2 || len(rows[0]) != 2 || rows[0][0] != "key" || rows[0][1] != "text" {
		return "", errors.New("圖片TSV欄位不符")
	}
	seen := map[string]bool{}
	text := ""
	for _, row := range rows[1:] {
		if len(row) != 2 || row[0] == "" || row[1] == "" || seen[row[0]] {
			return "", errors.New("圖片TSV空值或重複鍵")
		}
		seen[row[0]] = true
		if row[0] == key {
			text = row[1]
		}
	}
	if text == "" || strings.ContainsAny(text, "\r\n\t") {
		return "", errors.New("圖片文案缺鍵或含控制字元")
	}
	return text, nil
}

func imageTextNRGBA(src image.Image) *image.NRGBA {
	r := image.NewNRGBA(image.Rect(0, 0, src.Bounds().Dx(), src.Bounds().Dy()))
	draw.Draw(r, r.Bounds(), src, src.Bounds().Min, draw.Src)
	return r
}

func imageTextGreen(c color.NRGBA) bool {
	return c.A == 255 && int(c.G) > int(c.R)*6/5 && int(c.G) > int(c.B)*6/5 && c.R < 150
}

func imageTextGold(c color.NRGBA) bool {
	return c.A == 255 && c.R >= 120 && c.G >= 90 && int(c.R)*10 >= int(c.G)*9 && int(c.G) > int(c.B)*6/5
}

func compileClothText(original, painted image.Image, text string, font imageTextFont) (*image.NRGBA, imageTextResult, error) {
	src, out := imageTextNRGBA(original), imageTextNRGBA(painted)
	result := imageTextResult{Text: text}
	if src.Bounds().Dx() != 304 || (src.Bounds().Dy() != 55 && src.Bounds().Dy() != 120) || out.Bounds().Dx() != 912 || out.Bounds().Dy() != src.Bounds().Dy()*3 {
		return nil, result, errors.New("布條原圖或三倍貼圖尺寸不符")
	}
	if font.Size != 16 || font.Height != 20 || len([]rune(text)) == 0 {
		return nil, result, errors.New("布條文字需使用已定稿16像素字模")
	}
	for _, ch := range text {
		g := font.Glyphs[string(ch)]
		if len(g) != 320 || !bytes.Equal(g[256:], make([]byte, 64)) {
			return nil, result, errors.New("布條字模缺字或超出16像素字墨")
		}
	}
	before := append([]byte(nil), out.Pix...)
	w, h := out.Bounds().Dx(), out.Bounds().Dy()
	mask := make([]bool, w*h)
	greenX, greenY, greenCount := 0, 0, 0
	// 來源圖可見布條位於兩根金色柱之間；不納入下方人群與柱外部件。
	for x := 84; x < 222; x++ {
		limit := min(src.Bounds().Dy(), 55)
		lo, hi := limit, -1
		for y := 0; y < limit; y++ {
			if imageTextGold(src.NRGBAAt(x, y)) {
				lo = y
				break
			}
		}
		// 布料會下垂；沿第一段連續不透明來源，不用固定的35列假設。
		for y := lo; y < limit && src.NRGBAAt(x, y).A == 255; y++ {
			hi = y
		}
		for y := lo; y <= hi; y++ {
			c := src.NRGBAAt(x, y)
			if c.A != 255 {
				continue
			}
			if c.G >= c.R && int(c.G) > int(c.B)*2 && c.R < 150 {
				greenX += x*3 + 1
				greenY += y*3 + 1
				greenCount++
			}
			for yy := y * 3; yy < y*3+3; yy++ {
				for xx := x * 3; xx < x*3+3; xx++ {
					mask[yy*w+xx] = true
					result.ClothPixels++
				}
			}
		}
	}
	if greenCount == 0 {
		result.State = "no-visible-source-lettering"
		result.AlphaUnchanged, result.OutsideUnchanged = true, true
		return out, result, nil
	}
	cx, cy := greenX/greenCount, greenY/greenCount
	tw, th := len([]rune(text))*16, 16
	// 積分遮罩保證全文安全框內每個像素都是原版可見布料。
	integral := make([]int, (w+1)*(h+1))
	for y := 0; y < h; y++ {
		row := 0
		for x := 0; x < w; x++ {
			if mask[y*w+x] {
				row++
			}
			integral[(y+1)*(w+1)+x+1] = integral[y*(w+1)+x+1] + row
		}
	}
	best, found := int(^uint(0)>>1), false
	for y := 0; y+th <= min(h, 165); y++ {
		for x := 252; x+tw <= 666; x++ {
			x1, y1 := x+tw, y+th
			n := integral[y1*(w+1)+x1] - integral[y*(w+1)+x1] - integral[y1*(w+1)+x] + integral[y*(w+1)+x]
			if n != tw*th {
				continue
			}
			dx, dy := x+tw/2-cx, y+th/2-cy
			score := dx*dx + dy*dy
			if score < best {
				best, found, result.Box = score, true, [4]int{x, y, x1, y1}
			}
		}
	}
	if !found {
		result.State = "partially-unfurled-no-full-text-box"
		result.AlphaUnchanged, result.OutsideUnchanged = true, true
		return out, result, nil
	}
	// 生成字有金色外框，不能用綠色辨識完整字形。從每欄無字的上緣
	// 三列取材，延展整段布料，再畫唯一一份正式字模。
	near := make([]int, w*h)
	for i := range near {
		near[i] = -1
	}
	queue := make([]int, 0, result.ClothPixels)
	for x := 0; x < w; x++ {
		top := 0
		for top < h && !mask[top*w+x] {
			top++
		}
		for y := top; y < min(top+3, h); y++ {
			i := y*w + x
			if mask[i] && imageTextGold(out.NRGBAAt(x, y)) {
				near[i] = i
				queue = append(queue, i)
			}
		}
	}
	if len(queue) == 0 {
		return nil, result, errors.New("生成布料沒有可用金色材質")
	}
	for head := 0; head < len(queue); head++ {
		i := queue[head]
		for _, d := range []image.Point{{1, 0}, {-1, 0}, {0, 1}, {0, -1}} {
			x, y := i%w+d.X, i/w+d.Y
			if x < 0 || x >= w || y < 0 || y >= h {
				continue
			}
			n := y*w + x
			if mask[n] && near[n] < 0 {
				near[n] = near[i]
				queue = append(queue, n)
			}
		}
	}
	for i, on := range mask {
		if on {
			if near[i] < 0 {
				return nil, result, errors.New("布料區域無法連到無字材質")
			}
			if imageTextGreen(out.NRGBAAt(i%w, i/w)) {
				result.ClearedPixels++
			}
			d, s := i*4, near[i]*4
			copy(out.Pix[d:d+3], before[s:s+3])
			result.RecompiledPixels++
		}
	}
	ink := [3]byte{0, 64, 16}
	for n, ch := range []rune(text) {
		g := font.Glyphs[string(ch)]
		for y := 0; y < 16; y++ {
			for x := 0; x < 16; x++ {
				a := uint32(g[y*16+x])
				if a == 0 {
					continue
				}
				at := (result.Box[1]+y)*w + result.Box[0] + n*16 + x
				if !mask[at] {
					return nil, result, errors.New("中文字墨超出原版布料")
				}
				for c := 0; c < 3; c++ {
					out.Pix[at*4+c] = byte((uint32(ink[c])*a + uint32(out.Pix[at*4+c])*(255-a) + 127) / 255)
				}
				result.GlyphInkPixels++
			}
		}
	}
	for i, on := range mask {
		if out.Pix[i*4+3] != before[i*4+3] || (!on && !bytes.Equal(out.Pix[i*4:i*4+3], before[i*4:i*4+3])) {
			return nil, result, errors.New("布條編譯改變遮罩外資料")
		}
		if on && imageTextGreen(out.NRGBAAt(i%w, i/w)) && (i%w < result.Box[0] || i%w >= result.Box[2] || i/w < result.Box[1] || i/w >= result.Box[3]) {
			return nil, result, errors.New("中文安全框外仍有舊綠色字墨")
		}
	}
	result.State, result.AlphaUnchanged, result.OutsideUnchanged = "localized", true, true
	return out, result, nil
}

func main() {
	original := flag.String("original", "", "原版來源PNG")
	painted := flag.String("painted", "", "已編譯HD貼圖PNG")
	glyphs := flag.String("glyphs", "", "現行16像素字模JSON")
	catalog := flag.String("catalog", "", "正式圖片文案TSV")
	key := flag.String("key", "image.ending.our-heroes", "文案穩定鍵")
	nativeKey := flag.String("native-key", "", "FINAL.2.5至FINAL.2.14")
	outPath := flag.String("out", "", "全新輸出PNG")
	receiptPath := flag.String("receipt", "", "全新編譯收據JSON")
	flag.Parse()
	fail := func(err error) {
		if err != nil {
			panic(err)
		}
	}
	index, err := strconv.Atoi(strings.TrimPrefix(*nativeKey, "FINAL.2."))
	fail(err)
	if !strings.HasPrefix(*nativeKey, "FINAL.2.") || index < 5 || index > 14 {
		panic("不是已證實的布條來源")
	}
	for _, path := range []string{*outPath, *receiptPath} {
		if path == "" {
			panic("需全新輸出路徑")
		}
		if _, err := os.Stat(path); !os.IsNotExist(err) {
			panic("不覆寫既有輸出")
		}
	}
	paths := []string{*original, *painted, *glyphs, *catalog}
	inputs := map[string]string{}
	raw := make([][]byte, len(paths))
	for i, path := range paths {
		raw[i], err = os.ReadFile(path)
		fail(err)
		inputs[path] = imageTextSHA(raw[i])
	}
	src, err := png.Decode(bytes.NewReader(raw[0]))
	fail(err)
	art, err := png.Decode(bytes.NewReader(raw[1]))
	fail(err)
	var font imageTextFont
	fail(json.Unmarshal(raw[2], &font))
	text, err := imageTextCatalog(raw[3], *key)
	fail(err)
	result, detail, err := compileClothText(src, art, text, font)
	fail(err)
	if index >= 8 && detail.State != "localized" {
		panic("已展開的布條沒有完整中文安全框")
	}
	var pngBytes bytes.Buffer
	fail(png.Encode(&pngBytes, result))
	data, err := json.MarshalIndent(map[string]any{"passed": true, "native_key": *nativeKey, "text_key": *key, "inputs": inputs, "output_sha256": imageTextSHA(pngBytes.Bytes()), "result": detail, "new_gameplay_verification": false}, "", "  ")
	fail(err)
	fail(os.WriteFile(*outPath, pngBytes.Bytes(), 0644))
	fail(os.WriteFile(*receiptPath, append(data, '\n'), 0644))
	fmt.Println(*nativeKey, detail.State)
}

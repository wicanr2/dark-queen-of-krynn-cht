// 圖片文字的純Go編排。輸入為已解碼圖片、命令底圖與字模，不存取原版記憶體。
package main

import (
	"bytes"
	"crypto/sha256"
	"encoding/csv"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"unicode/utf8"
)

type pictureCaption struct {
	Key                   string
	ClearBox, TextBox     [4]int // 三倍畫布座標。
	Scale                 int
	GlyphSize             int
	Foreground, FillIndex byte
	Mode                  string
	MaskSource            bool
	Mask, Fill            []byte
}
type pictureTextBinding struct {
	Key, Header, SourceSHA256, IndexSHA256, AlphaSHA256 string
	SourceBytes, W, H                                   int
	HDAlreadyLocalized                                  bool
	Captions                                            []pictureCaption
}
type pictureTextFont struct {
	Size, Height int
	Glyphs       map[string][]byte
}
type pictureTextOccurrence struct {
	Binding         *pictureTextBinding
	Asset           *sceneAsset
	X, Y            int
	Page            uint32
	Background      []sceneCell
	BackgroundIndex []byte
}
type pictureTextLayer struct {
	Bindings    []pictureTextBinding
	Catalog     map[string]string
	Font        pictureTextFont
	Occurrences []*pictureTextOccurrence
}

func pictureDigest(raw []byte) string { h := sha256.Sum256(raw); return hex.EncodeToString(h[:]) }
func pictureCatalog(raw []byte) (map[string]string, error) {
	if !utf8.Valid(raw) {
		return nil, fmt.Errorf("圖片文案不是UTF-8")
	}
	r := csv.NewReader(bytes.NewReader(raw))
	r.Comma = '\t'
	rows, err := r.ReadAll()
	if err != nil || len(rows) < 2 || len(rows[0]) != 2 || rows[0][0] != "key" || rows[0][1] != "text" {
		return nil, fmt.Errorf("圖片文案欄位失配")
	}
	out := map[string]string{}
	for _, r := range rows[1:] {
		if len(r) != 2 || r[0] == "" || r[1] == "" || out[r[0]] != "" || strings.ContainsAny(r[1], "\r\n\t") {
			return nil, fmt.Errorf("圖片文案空值、重複鍵或控制碼")
		}
		out[r[0]] = r[1]
	}
	return out, nil
}
func loadPictureText(root string) (*pictureTextLayer, error) {
	raw, err := os.ReadFile(filepath.Join(root, "manifest.json"))
	if os.IsNotExist(err) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	var m struct {
		Version  int
		Files    map[string]string
		Bindings []pictureTextBinding
	}
	if err = json.Unmarshal(raw, &m); err != nil {
		return nil, err
	}
	if m.Version != 1 || len(m.Bindings) < 1 || len(m.Bindings) > 64 || len(m.Files) != 3 {
		return nil, fmt.Errorf("圖片文案清單不符")
	}
	files := map[string][]byte{}
	for _, name := range []string{"en.tsv", "zh-TW.tsv", "glyphs.json"} {
		want := m.Files[name]
		data, e := os.ReadFile(filepath.Join(root, name))
		if e != nil || len(data) > 8<<20 || len(want) != 64 || pictureDigest(data) != want {
			return nil, fmt.Errorf("圖片文字來源失配：%s", name)
		}
		files[name] = data
	}
	en, err := pictureCatalog(files["en.tsv"])
	if err != nil {
		return nil, err
	}
	zh, err := pictureCatalog(files["zh-TW.tsv"])
	if err != nil {
		return nil, err
	}
	if len(en) != len(zh) {
		return nil, fmt.Errorf("圖片雙語鍵數不同")
	}
	for key := range en {
		if zh[key] == "" {
			return nil, fmt.Errorf("圖片文案缺鍵")
		}
	}
	l := &pictureTextLayer{Bindings: m.Bindings, Catalog: zh}
	if err = json.Unmarshal(files["glyphs.json"], &l.Font); err != nil {
		return nil, err
	}
	if l.Font.Size != 16 || l.Font.Height != 20 {
		return nil, fmt.Errorf("圖片字模尺寸不符")
	}
	seen := map[string]bool{}
	for n := range l.Bindings {
		b := &l.Bindings[n]
		header, e := hex.DecodeString(b.Header)
		if b.Key == "" || seen[b.Key] || e != nil || len(header) != 8 || b.W < 1 || b.H < 1 || b.W > 320 || b.H > 200 || int(header[6])*4 != b.W || int(header[0])|int(header[1])<<8 != b.H || len(b.SourceSHA256) != 64 || b.SourceBytes < 8 || b.SourceBytes > 1<<20 || len(b.IndexSHA256) != 64 || len(b.AlphaSHA256) != 64 || len(b.Captions) == 0 {
			return nil, fmt.Errorf("圖片文字來源資料不符：%s", b.Key)
		}
		seen[b.Key] = true
		for _, c := range b.Captions {
			text := zh[c.Key]
			if text == "" || c.Scale < 1 || c.Scale > 8 || c.GlyphSize < 0 || c.GlyphSize > 128 {
				return nil, fmt.Errorf("圖片文案鍵或字級不符")
			}
			for _, box := range [][4]int{c.ClearBox, c.TextBox} {
				if box[0] < 0 || box[1] < 0 || box[2] > b.W*3 || box[3] > b.H*3 || box[0] >= box[2] || box[1] >= box[3] {
					return nil, fmt.Errorf("圖片文字安全框越界")
				}
			}
			if len([]rune(text))*pictureGlyphSize(c) > c.TextBox[2]-c.TextBox[0] || pictureGlyphSize(c) > c.TextBox[3]-c.TextBox[1] {
				return nil, fmt.Errorf("圖片文字溢出：%s", c.Key)
			}
			if c.Mode != "background" && c.Mode != "color" && c.Mode != "indexed" {
				return nil, fmt.Errorf("未知圖片清字模式")
			}
			if c.Mode == "indexed" && (len(c.Mask) != b.W*b.H || len(c.Fill) != b.W*b.H) {
				return nil, fmt.Errorf("圖片布料遮罩失配")
			}
			for _, ch := range text {
				g := l.Font.Glyphs[string(ch)]
				if len(g) != 320 || !bytes.Equal(g[256:], make([]byte, 64)) {
					return nil, fmt.Errorf("圖片字模缺字：%U", ch)
				}
			}
		}
	}
	return l, nil
}
func pictureGlyphSize(c pictureCaption) int {
	if c.GlyphSize > 0 {
		return c.GlyphSize
	}
	return 16 * c.Scale
}
func pictureAlpha(a *sceneAsset) []byte {
	if len(a.Alpha) > 0 {
		return a.Alpha
	}
	return bytes.Repeat([]byte{255}, a.W*a.H)
}
func (l *pictureTextLayer) capture(b *pictureTextBinding, a *sceneAsset, p *scenePage, x, y int, page uint32) bool {
	if a.W != b.W || a.H != b.H || x < 0 || y < 0 || x+a.W > 320 || y+a.H > 200 || pictureDigest(a.Index) != b.IndexSHA256 || pictureDigest(pictureAlpha(a)) != b.AlphaSHA256 {
		return false
	}
	alpha := pictureAlpha(a)
	for _, c := range b.Captions {
		text := []rune(l.Catalog[c.Key])
		left := (c.TextBox[0] + c.TextBox[2] - len(text)*pictureGlyphSize(c)) / 2
		top := (c.TextBox[1] + c.TextBox[3] - pictureGlyphSize(c)) / 2
		for k, ch := range text {
			g := l.Font.Glyphs[string(ch)]
			for yy := 0; yy < pictureGlyphSize(c); yy++ {
				for xx := 0; xx < pictureGlyphSize(c); xx++ {
					if g[yy*16/pictureGlyphSize(c)*16+xx*16/pictureGlyphSize(c)] == 0 {
						continue
					}
					at := (top+yy)/3*a.W + (left+k*pictureGlyphSize(c)+xx)/3
					if c.MaskSource && alpha[at] == 0 || c.Mode == "indexed" && c.Mask[at] == 0 {
						return false
					}
				}
			}
		}
	}
	o := &pictureTextOccurrence{Binding: b, Asset: a, X: x, Y: y, Page: page, Background: make([]sceneCell, a.W*a.H), BackgroundIndex: make([]byte, a.W*a.H)}
	var prior *pictureTextOccurrence
	for _, v := range l.Occurrences {
		if v.Page == page && v.X == x && v.Y == y && v.Binding == b {
			prior = v
			break
		}
	}
	for yy := 0; yy < a.H; yy++ {
		for xx := 0; xx < a.W; xx++ {
			n := yy*a.W + xx
			i := (y+yy)*320 + x + xx
			o.Background[n] = p.Cells[i]
			o.BackgroundIndex[n] = p.Index[i]
			if cell := o.Background[n]; cell.Asset != nil && !cell.Visible && !cell.Unsafe {
				o.Background[n].Visible = true
				o.BackgroundIndex[n] = cell.Asset.Index[cell.Source]
			}
			if prior != nil && p.Cells[i].Asset == prior.Asset && p.Cells[i].Source == n {
				o.Background[n] = prior.Background[n]
				o.BackgroundIndex[n] = prior.BackgroundIndex[n]
			}
		}
	}
	for i, v := range l.Occurrences {
		if v == prior {
			l.Occurrences[i] = o
			return true
		}
	}
	if len(l.Occurrences) >= 64 {
		l.Occurrences = l.Occurrences[1:]
	}
	l.Occurrences = append(l.Occurrences, o)
	return true
}
func pictureHD(a *sceneAsset, pal [256][3]byte) bool {
	if len(a.HD) != a.W*a.H*36 || len(a.Reference) != a.W*a.H*3 {
		return false
	}
	for n, index := range a.Index {
		if len(a.Alpha) > 0 && a.Alpha[n] == 0 {
			continue
		}
		c := pal[index]
		if !bytes.Equal(a.Reference[n*3:n*3+3], c[:]) {
			return false
		}
	}
	return true
}
func pictureContains(b [4]int, x, y int) bool { return x >= b[0] && y >= b[1] && x < b[2] && y < b[3] }
func pictureIntersects(a, b [4]int) bool {
	return a[0] < b[2] && b[0] < a[2] && a[1] < b[3] && b[1] < a[3]
}
func (l *pictureTextLayer) prepare(p *scenePage, page uint32, pal [256][3]byte, hd bool, protected [][4]int) ([]sceneRect, [][4]int) {
	var rects []sceneRect
	var boxes [][4]int
	choices := map[*sceneAsset]bool{}
	choose := func(a *sceneAsset) bool {
		if a == nil {
			return false
		}
		if v, ok := choices[a]; ok {
			return v
		}
		v := hd && pictureHD(a, pal)
		choices[a] = v
		return v
	}
	pixel := func(a *sceneAsset, n, xx, yy int, fallback byte) [3]byte {
		if a == nil {
			return pal[fallback]
		}
		if choose(a) {
			at := ((n/a.W*3+yy)*a.W*3 + n%a.W*3 + xx) * 4
			return [3]byte{a.HD[at], a.HD[at+1], a.HD[at+2]}
		}
		return pal[a.Index[n]]
	}
	occurrences := []*pictureTextOccurrence{}
	for _, o := range l.Occurrences {
		for _, c := range o.Binding.Captions {
			copyOccurrence := *o
			copyBinding := *o.Binding
			copyBinding.Captions = []pictureCaption{c}
			copyOccurrence.Binding = &copyBinding
			occurrences = append(occurrences, &copyOccurrence)
		}
	}
	for _, o := range occurrences {
		if o.Page != page {
			continue
		}
		a, b := o.Asset, o.Binding
		if b.HDAlreadyLocalized && choose(a) {
			continue
		}
		caption := b.Captions[0]
		local := [4]int{caption.ClearBox[0] / 3, caption.ClearBox[1] / 3, (caption.ClearBox[2] + 2) / 3, (caption.ClearBox[3] + 2) / 3}
		if caption.Mode == "indexed" {
			local = [4]int{a.W, a.H, 0, 0}
			for n, on := range caption.Mask {
				if on != 0 {
					local[0] = min(local[0], n%a.W)
					local[1] = min(local[1], n/a.W)
					local[2] = max(local[2], n%a.W+1)
					local[3] = max(local[3], n/a.W+1)
				}
			}
		}
		local[0] = min(local[0], caption.TextBox[0]/3)
		local[1] = min(local[1], caption.TextBox[1]/3)
		local[2] = max(local[2], (caption.TextBox[2]+2)/3)
		local[3] = max(local[3], (caption.TextBox[3]+2)/3)
		box := [4]int{o.X + local[0], o.Y + local[1], o.X + local[2], o.Y + local[3]}
		blocked := false
		for _, r := range append(append([][4]int(nil), protected...), boxes...) {
			if pictureIntersects(box, r) {
				blocked = true
				break
			}
		}
		if blocked {
			continue
		}
		alpha := pictureAlpha(a)
		valid := true
		temporary := make([]bool, a.W*a.H)
		for n, on := range alpha {
			if n%a.W < local[0] || n%a.W >= local[2] || n/a.W < local[1] || n/a.W >= local[3] {
				continue
			}
			i := (o.Y+n/a.W)*320 + o.X + n%a.W
			c := p.Cells[i]
			if on != 0 {
				if c.Asset != a || c.Source != n || c.Unsafe {
					valid = false
					break
				}
				temporary[n] = !c.Visible
			} else if c != o.Background[n] || p.Index[i] != o.BackgroundIndex[n] {
				bg := o.Background[n]
				if bg.Asset != nil && bg.Visible && !c.Visible && c.Asset == bg.Asset && c.Source == bg.Source && !c.Unsafe {
					temporary[n] = true
				} else {
					valid = false
					break
				}
			}
		}
		if !valid {
			continue
		}
		out := &sceneAsset{W: a.W, H: a.H, HD: make([]byte, a.W*a.H*36)}
		for y := local[1] * 3; y < local[3]*3; y++ {
			for x := local[0] * 3; x < local[2]*3; x++ {
				n := y/3*a.W + x/3
				bg := o.Background[n]
				var col [3]byte
				if alpha[n] != 0 {
					col = pixel(a, n, x%3, y%3, a.Index[n])
				} else {
					var ba *sceneAsset
					if bg.Visible {
						ba = bg.Asset
					}
					col = pixel(ba, bg.Source, x%3, y%3, o.BackgroundIndex[n])
				}
				for _, c := range b.Captions {
					if c.Mode == "indexed" {
						if c.Mask[n] != 0 {
							col = pal[c.Fill[n]]
						}
						continue
					}
					if !pictureContains(c.ClearBox, x, y) {
						continue
					}
					if c.Mode == "color" {
						if alpha[n] != 0 {
							col = pal[c.FillIndex]
						}
					} else {
						var ba *sceneAsset
						if bg.Visible {
							ba = bg.Asset
						}
						col = pixel(ba, bg.Source, x%3, y%3, o.BackgroundIndex[n])
					}
				}
				at := (y*a.W*3 + x) * 4
				copy(out.HD[at:at+3], col[:])
				out.HD[at+3] = 255
			}
		}
		for _, c := range b.Captions {
			text := []rune(l.Catalog[c.Key])
			left := (c.TextBox[0] + c.TextBox[2] - len(text)*pictureGlyphSize(c)) / 2
			top := (c.TextBox[1] + c.TextBox[3] - pictureGlyphSize(c)) / 2
			col := pal[c.Foreground]
			for k, ch := range text {
				g := l.Font.Glyphs[string(ch)]
				for y := 0; y < pictureGlyphSize(c); y++ {
					for x := 0; x < pictureGlyphSize(c); x++ {
						coverage := uint32(g[y*16/pictureGlyphSize(c)*16+x*16/pictureGlyphSize(c)])
						if coverage == 0 {
							continue
						}
						xx, yy := left+k*pictureGlyphSize(c)+x, top+y
						n := yy/3*a.W + xx/3
						if c.MaskSource && alpha[n] == 0 {
							continue
						}
						at := (yy*a.W*3 + xx) * 4
						for channel := 0; channel < 3; channel++ {
							out.HD[at+channel] = byte((uint32(col[channel])*coverage + uint32(out.HD[at+channel])*(255-coverage) + 127) / 255)
						}
					}
				}
			}
		}
		// 暫時游標沿原色號合成進同一紋理，不能撤除整張中文或蓋住游標。
		for n, on := range temporary {
			if !on {
				continue
			}
			col := pal[p.Index[(o.Y+n/a.W)*320+o.X+n%a.W]]
			for yy := 0; yy < 3; yy++ {
				for xx := 0; xx < 3; xx++ {
					at := ((n/a.W*3+yy)*a.W*3 + n%a.W*3 + xx) * 4
					copy(out.HD[at:at+3], col[:])
				}
			}
		}
		rects = append(rects, sceneRect{Asset: out, HD: true, SX: local[0], SY: local[1], X: box[0], Y: box[1], W: local[2] - local[0], H: local[3] - local[1]})
		boxes = append(boxes, box)
	}
	return rects, boxes
}

// 命令所有權與最小顯存相容資料。這裡不執行原版，也不依賴 GUI。
package main

import "fmt"

type sceneAsset struct {
	W, H          int
	Index, Alpha  []byte
	HD, Reference []byte // 3x RGBA 與原尺寸 RGB；均可省略。
}
type sceneCell struct {
	Asset           *sceneAsset
	Source          int
	Visible, Unsafe bool
}
type scenePage struct {
	Cells [64000]sceneCell
	Index [64000]byte
}
type renderScene struct {
	Pages    [4]*scenePage
	Revision uint64
}

// 紋理與幾何後端的輸入；不包含 DOS RAM、CPU 或執行器。
type sceneRect struct {
	Asset              *sceneAsset
	HD                 bool
	SX, SY, X, Y, W, H int
}

func (p *scenePage) rectangles(hd bool, pal [256][3]byte, protected [][4]int) []sceneRect {
	blocked := [64000]bool{}
	for _, r := range protected {
		if r[0] < 0 || r[1] < 0 || r[2] > 320 || r[3] > 200 {
			panic("呈現保護框越界")
		}
		for y := r[1]; y < r[3]; y++ {
			for x := r[0]; x < r[2]; x++ {
				blocked[y*320+x] = true
			}
		}
	}
	choices := map[*sceneAsset]bool{}
	choose := func(a *sceneAsset) bool {
		if v, ok := choices[a]; ok {
			return v
		}
		v := hd && len(a.HD) == a.W*a.H*36 && len(a.Reference) == a.W*a.H*3
		if v {
			for n, index := range a.Index {
				if len(a.Alpha) > 0 && a.Alpha[n] == 0 {
					continue
				}
				col := pal[index]
				if a.Reference[n*3] != col[0] || a.Reference[n*3+1] != col[1] || a.Reference[n*3+2] != col[2] {
					v = false
					break
				}
			}
		}
		choices[a] = v
		return v
	}
	type mergeKey struct {
		A        *sceneAsset
		SX, X, W int
		HD       bool
	}
	previous := map[mergeKey]int{}
	rects := []sceneRect{}
	for y := 0; y < 200; y++ {
		for x := 0; x < 320; {
			i := y*320 + x
			c := p.Cells[i]
			if c.Asset == nil || !c.Visible || blocked[i] {
				x++
				continue
			}
			a := c.Asset
			run := 1
			for x+run < 320 {
				next := p.Cells[i+run]
				if blocked[i+run] || !next.Visible || next.Asset != a || next.Source != c.Source+run || next.Source/a.W != c.Source/a.W {
					break
				}
				run++
			}
			r := sceneRect{Asset: a, HD: choose(a), SX: c.Source % a.W, SY: c.Source / a.W, X: x, Y: y, W: run, H: 1}
			key := mergeKey{a, r.SX, x, run, r.HD}
			merged := false
			if prev, ok := previous[key]; ok {
				old := &rects[prev]
				if old.Y+old.H == y && old.SY+old.H == r.SY {
					old.H++
					merged = true
				}
			}
			if !merged {
				previous[key] = len(rects)
				rects = append(rects, r)
			}
			x += run
		}
	}
	return rects
}

func (s *renderScene) page(page uint32, raw func(int, uint32) byte) *scenePage {
	if page > 0xc000 || page%0x4000 != 0 {
		panic("場景頁面越界")
	}
	i := page / 0x4000
	if s.Pages[i] == nil {
		p := new(scenePage)
		for n := range p.Index {
			p.Index[n] = raw(n&3, page+uint32(n/320*80+(n%320)/4))
		}
		s.Pages[i] = p
	}
	return s.Pages[i]
}

func (s *renderScene) record(p *scenePage, a *sceneAsset, x, y int) {
	if a.W < 1 || a.H < 1 || x < 0 || y < 0 || x+a.W > 320 || y+a.H > 200 || len(a.Index) != a.W*a.H || (len(a.Alpha) != 0 && len(a.Alpha) != len(a.Index)) {
		panic("場景命令越界")
	}
	for yy := 0; yy < a.H; yy++ {
		for xx := 0; xx < a.W; xx++ {
			n := yy*a.W + xx
			if len(a.Alpha) > 0 && a.Alpha[n] == 0 {
				continue
			}
			i := (y+yy)*320 + x + xx
			p.Cells[i] = sceneCell{Asset: a, Source: n, Visible: true}
			p.Index[i] = a.Index[n]
		}
	}
	s.Revision++
}

// 原版讀回或混色前，僅補該位址的四個平面。真正 VGA.Read 仍負責載入 latch。
func (s *renderScene) materialize(off uint32, put func(int, uint32, byte)) int {
	if off >= 0x10000 {
		return 0
	}
	page, local := off&0xc000, off&0x3fff
	if local >= 16000 || s.Pages[page/0x4000] == nil {
		return 0
	}
	p := s.Pages[page/0x4000]
	i := int(local/80)*320 + int(local%80)*4
	count := 0
	for plane := 0; plane < 4; plane++ {
		c := p.Cells[i+plane]
		if c.Asset != nil && c.Visible {
			put(plane, off, c.Asset.Index[c.Source])
			count++
		}
	}
	return count
}

func (s *renderScene) nativeWrite(off uint32, mask byte, temporary, glyph bool, raw func(int, uint32) byte) {
	if off >= 0x10000 {
		return
	}
	page, local := off&0xc000, off&0x3fff
	if local >= 16000 || s.Pages[page/0x4000] == nil {
		return
	}
	p := s.Pages[page/0x4000]
	i := int(local/80)*320 + int(local%80)*4
	for plane := 0; plane < 4; plane++ {
		if mask&(1<<plane) == 0 {
			continue
		}
		c := &p.Cells[i+plane]
		v := raw(plane, off)
		if temporary && c.Asset != nil {
			c.Visible = v == c.Asset.Index[c.Source]
		} else {
			*c = sceneCell{Unsafe: glyph}
		}
		p.Index[i+plane] = v
	}
	s.Revision++
}

func (p *scenePage) safe(r [4]int) bool {
	if r[0] < 0 || r[1] < 0 || r[2] > 320 || r[3] > 200 {
		return false
	}
	for y := r[1]; y < r[3]; y++ {
		for x := r[0]; x < r[2]; x++ {
			if p.Cells[y*320+x].Unsafe {
				return false
			}
		}
	}
	return true
}

// 每個可見像素只選一種來源。HD 開關及色盤不同時仍使用相同命令與所有權。
func (p *scenePage) rgba(hd bool, pal [256][3]byte, protected [][4]int) []byte {
	out := make([]byte, 960*600*4)
	blocked := make([]bool, 64000)
	for _, r := range protected {
		if r[0] < 0 || r[1] < 0 || r[2] > 320 || r[3] > 200 {
			panic("呈現保護框越界")
		}
		for y := r[1]; y < r[3]; y++ {
			for x := r[0]; x < r[2]; x++ {
				blocked[y*320+x] = true
			}
		}
	}
	choices := map[*sceneAsset]bool{}
	for i, c := range p.Cells {
		if c.Asset == nil || !c.Visible || blocked[i] {
			continue
		}
		a := c.Asset
		use, known := choices[a]
		if !known {
			use = hd && len(a.HD) == a.W*a.H*36 && len(a.Reference) == a.W*a.H*3
			if use {
				for n, index := range a.Index {
					if len(a.Alpha) > 0 && a.Alpha[n] == 0 {
						continue
					}
					col := pal[index]
					if a.Reference[n*3] != col[0] || a.Reference[n*3+1] != col[1] || a.Reference[n*3+2] != col[2] {
						use = false
						break
					}
				}
			}
			choices[a] = use
		}
		x, y := i%320, i/320
		col := pal[a.Index[c.Source]]
		for yy := 0; yy < 3; yy++ {
			for xx := 0; xx < 3; xx++ {
				d := ((y*3+yy)*960 + x*3 + xx) * 4
				if use {
					src := (((c.Source/a.W)*3+yy)*(a.W*3) + (c.Source%a.W)*3 + xx) * 4
					copy(out[d:d+4], a.HD[src:src+4])
				} else {
					copy(out[d:d+3], col[:])
					out[d+3] = 255
				}
			}
		}
	}
	return out
}

// 格式見 tlb_gallery.py 與 Gold Box Explorer 授權。限制長度的 PackBits 解碼。
func decodeSceneImage(header [8]byte, body []byte) (*sceneAsset, int, error) {
	w, h := int(header[6])*4, int(header[0])|int(header[1])<<8
	n := w * h
	if w < 1 || w > 320 || h < 1 || h > 200 {
		return nil, 0, fmt.Errorf("圖像尺寸越界")
	}
	method := header[7]
	used := 0
	data := body
	switch method {
	case 16, 21:
		if len(body) < n {
			return nil, 0, fmt.Errorf("圖像資料不足")
		}
		data = body[:n]
		used = n
	case 18:
		data = make([]byte, 0, n)
		for len(data) < n {
			if used >= len(body) {
				return nil, 0, fmt.Errorf("壓縮資料不足")
			}
			op := int(body[used])
			used++
			if op < 128 {
				k := op + 1
				if used+k > len(body) || len(data)+k > n {
					return nil, 0, fmt.Errorf("壓縮常值越界")
				}
				data = append(data, body[used:used+k]...)
				used += k
			} else {
				k := 257 - op
				if used >= len(body) || len(data)+k > n {
					return nil, 0, fmt.Errorf("壓縮重複越界")
				}
				v := body[used]
				used++
				for j := 0; j < k; j++ {
					data = append(data, v)
				}
			}
		}
	default:
		return nil, 0, fmt.Errorf("未接管圖像格式")
	}
	a := &sceneAsset{W: w, H: h, Index: make([]byte, n)}
	if method == 21 {
		a.Alpha = make([]byte, n)
	}
	for y := 0; y < h; y++ {
		for x := 0; x < w; x++ {
			src := (x%4)*(n/4) + y*(w/4) + x/4
			if method == 18 {
				src = y*w + (x%4)*(w/4) + x/4
			}
			i := y*w + x
			a.Index[i] = data[src]
			if method == 21 && data[src] != 255 {
				a.Alpha[i] = 255
			}
		}
	}
	return a, used, nil
}

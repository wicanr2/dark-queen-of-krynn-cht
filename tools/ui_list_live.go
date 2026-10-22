// DRAFT：依原版標題辨識列表，文字只進呈現層。與 early_text_live.go 一起建置。
package main

import (
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"

	"github.com/wicanr2/dosgolem/oracle"
)

type listAction struct {
	At, End          uint64
	Kind, Key, Label string
}
type listRequest struct {
	StateSHA string `json:"state_sha256"`
	Start    uint64 `json:"start_steps"`
	Actions  []listAction
}
type listHeader struct {
	Pane, Key       string
	Segment, Offset uint16
	SHA256          string
}
type listConfig struct {
	Headers     []listHeader
	Rows        []listRow
	Fields      []listField
	Background  byte
	FineWindows [][2]uint64 `json:"fine_windows"`
}
type listField struct {
	Pane, Group, Key, SHA256, FormatSHA256 string
	RawX, RawY                             uint16
	Caller                                 oracle.Addr
}
type listSpan struct {
	Start, Length int
	Key           string
}
type listRow struct {
	Pane, SHA256 string
	Spans        []listSpan
}
type listWord struct {
	X, Y, Width            int
	Key                    string
	Group                  string
	Foreground, Background byte
}
type listTextEvent struct {
	Step       uint64
	Kind, Pane string
	Words      []listWord
	FirstGlyph uint64 `json:"first_glyph,omitempty"`
	Detail     any    `json:"detail,omitempty"`
}
type listState struct {
	request                listRequest
	config                 listConfig
	sources                map[string]string
	pane                   string
	words                  map[[2]int]listWord
	events                 []listTextEvent
	frames                 []map[string]any
	paints, fills, scrolls []paintReturn
	clearTargets           []listWord
	clearCovered           map[int]bool
	clearPending           bool
	awaitGlyph             int
	videoSample            []map[string]any
	awaitPageFlip          bool
	renderPageKnown        bool
	renderPage             uint32
	renderOrigin           [2]int
	action                 int
	sent                   bool
	menuDepth              int
	buttons                []paintReturn
	pendingHeader          *listWord
	headerTransition       bool
	headerReturn           *paintReturn
	footerTransition       bool
}

func (l *listState) snapshot() []listWord {
	var words []listWord
	for _, w := range l.words {
		words = append(words, w)
	}
	sort.Slice(words, func(i, j int) bool {
		if words[i].Y != words[j].Y {
			return words[i].Y < words[j].Y
		}
		return words[i].X < words[j].X
	})
	return words
}
func (g *liveGame) listLog(kind string, detail any) int {
	l := g.list
	l.events = append(l.events, listTextEvent{Step: g.o.Steps(), Kind: kind, Pane: l.pane, Words: l.snapshot(), Detail: detail})
	return len(l.events) - 1
}
func (l *listState) erase(x, y, w, h int) {
	for p, v := range l.words {
		if v.X < x+w && v.X+v.Width > x && v.Y < y+h && v.Y+8 > y {
			delete(l.words, p)
		}
	}
}
func listString(o *oracle.Oracle, seg, off uint16) (string, bool) {
	var b []byte
	for i := 0; i < 256; i++ {
		if uint32(off)+uint32(i) > 65535 || uint32(seg)*16+uint32(off)+uint32(i) >= 0xa0000 {
			return "", false
		}
		v := o.Byte(oracle.Addr{Seg: seg, Off: off + uint16(i)})
		if v == 0 {
			return string(b), true
		}
		if v < 32 && v != 9 || v > 126 {
			return "", false
		}
		b = append(b, v)
	}
	return "", false
}
func (g *liveGame) installList(inputs, requestPath, sourcePath string) {
	l := g.list
	o := g.o
	l.words = map[[2]int]listWord{}
	l.awaitGlyph = -1
	l.sources = readLiveCatalog(sourcePath)
	b, e := os.ReadFile(inputs)
	must(e)
	must(json.Unmarshal(b, &l.config))
	b, e = os.ReadFile(requestPath)
	must(e)
	must(json.Unmarshal(b, &l.request))
	if len(l.config.Headers) != 2 || len(l.config.Rows) == 0 || len(l.config.Fields) == 0 || len(l.request.Actions) == 0 || o.Steps() != l.request.Start {
		panic("列表輸入不符")
	}
	for _, key := range []string{"answer.yes", "answer.no", "format.string"} {
		if l.sources[key] == "" {
			panic("列表原文缺鍵")
		}
	}
	seenRows := map[string]bool{}
	for _, row := range l.config.Rows {
		id := row.Pane + ":" + row.SHA256
		if seenRows[id] || len(row.SHA256) != 64 || len(row.Spans) == 0 || (row.Pane != "inventory" && row.Pane != "grimoire") {
			panic("列表列綁定重複或無效")
		}
		seenRows[id] = true
		end := 0
		for _, span := range row.Spans {
			if span.Start < end || span.Length <= 0 || len(l.sources[span.Key]) != span.Length || g.catalog[span.Key] == "" || len([]rune(g.catalog[span.Key]))*16 > span.Length*16 {
				panic("列表譯文缺鍵、重疊或超寬")
			}
			end = span.Start + span.Length
		}
	}
	last := l.request.Start
	for _, a := range l.request.Actions {
		if a.At < last || a.End <= a.At || (a.Kind != "named" && a.Kind != "text") {
			panic("列表動作不符")
		}
		last = a.End
	}
	for _, h := range l.config.Headers {
		if digest([]byte(l.sources[h.Key])) != h.SHA256 {
			panic("標題來源不符")
		}
	}
	for _, f := range l.config.Fields {
		if digest([]byte(l.sources[f.Key])) != f.SHA256 || g.catalog[f.Key] == "" || len([]rune(g.catalog[f.Key])) > len(l.sources[f.Key]) ||
			(f.Group != "header" && f.Group != "body" && f.Group != "footer") ||
			(f.Pane != "inventory" && f.Pane != "grimoire" && f.Pane != "suffix") {
			panic("列表欄位綁定無效")
		}
	}
	for _, p := range []struct {
		a oracle.Addr
		b string
	}{
		{oracle.Addr{Seg: 0xb72, Off: 0x46}, "558bec83ec60168d461250"},
		{oracle.Addr{Seg: 0xc15, Off: 0x55}, "558bec83ec245657"},
		{oracle.Addr{Seg: 0x13c7, Off: 0x78}, "558bec83ec2e5657"},
		{oracle.Addr{Seg: 0x13c7, Off: 0xf7}, "8b4606"},
		{oracle.Addr{Seg: 0x13c7, Off: 0x2f06}, "558bec83ec0c5657168d46"},
	} {
		if hex.EncodeToString(o.Bytes(p.a, len(p.b)/2)) != p.b {
			panic("列表掛勾 bytes 不符")
		}
	}
	entry := func(stack *[]paintReturn, addr oracle.Addr) {
		r := o.Regs()
		*stack = append(*stack, paintReturn{addr, r.SS, r.SP})
	}
	ret := func(stack *[]paintReturn) {
		if len(*stack) == 0 {
			panic("列表繪製返回未配對")
		}
		p := (*stack)[len(*stack)-1]
		r := o.Regs()
		if p.SS != r.SS || p.SP != r.SP {
			panic("列表返回堆疊不符")
		}
		*stack = (*stack)[:len(*stack)-1]
	}
	o.OnCall(oracle.Addr{Seg: 0xc15, Off: 0x55}, func(_ *oracle.Oracle) { entry(&l.paints, oracle.Addr{}); g.listLog("list-entry", nil) })
	o.OnCall(oracle.Addr{Seg: 0xc15, Off: 0x508}, func(_ *oracle.Oracle) { ret(&l.paints); g.listLog("list-return", nil) })
	o.OnCall(oracle.Addr{Seg: 0x13c7, Off: 0x78}, func(_ *oracle.Oracle) { entry(&l.fills, oracle.Addr{}) })
	o.OnCall(oracle.Addr{Seg: 0x13c7, Off: 0x6db}, func(_ *oracle.Oracle) { ret(&l.fills) })
	o.OnCall(oracle.Addr{Seg: 0x13c7, Off: 0xf7}, func(_ *oracle.Oracle) {
		r := o.Regs()
		v := [4]int{}
		for i := range v {
			v[i] = int(int16(o.Word(oracle.Addr{Seg: r.SS, Off: r.BP + 6 + uint16(i*2)})))
		}
		x, y, w, h := v[1], v[0], v[3]-v[1], v[2]-v[0]
		if len(l.paints) == 0 && x <= 8 && y <= 8 && x+w >= 312 && y+h >= 184 {
			l.awaitPageFlip = true
			l.renderPageKnown = false
			l.renderOrigin = [2]int{x, y}
			l.clearTargets = nil
			for p, word := range l.words {
				if word.Group != "footer" {
					l.clearTargets = append(l.clearTargets, word)
					delete(l.words, p)
				}
			}
			// 固定順序才能與控制組逐事件比較。
			sort.Slice(l.clearTargets, func(i, j int) bool {
				if l.clearTargets[i].Y != l.clearTargets[j].Y {
					return l.clearTargets[i].Y < l.clearTargets[j].Y
				}
				return l.clearTargets[i].X < l.clearTargets[j].X
			})
			if len(l.clearTargets) > 0 {
				l.clearCovered = map[int]bool{}
				l.clearPending = true
				g.listLog("clear-write-baseline", map[string]any{"targets": l.clearTargets})
			}
			l.pendingHeader = nil
			l.headerTransition = false
			l.headerReturn = nil
			l.pane = ""
			g.listLog("pane-invalidate", [4]int{x, y, w, h})
		} else {
			l.erase(x, y, w, h)
			g.listLog("native-fill", [4]int{x, y, w, h})
		}
	})
	// 使用 Machine 已有的視訊寫入 observer，包括 planar 路徑及同值寫入。
	// 此固定 mode 13h 路徑須覆蓋每個舊字框的全部原生像素後才解除保留。
	o.OnVideoWriteEvent(func(hit oracle.VideoWriteEvent) {
		if !l.clearPending && !l.awaitPageFlip {
			return
		}
		if len(l.videoSample) < 16 {
			l.videoSample = append(l.videoSample, map[string]any{"step": hit.Step, "offset": hit.Offset, "mode": hit.Mode, "unchained": hit.Unchained, "map_mask": hit.MapMask, "display_start": hit.DisplayStart, "pitch": hit.Pitch, "line_compare": hit.LineCompare})
		}
		var locations []int
		if hit.Unchained {
			if hit.Mode != 0x13 || hit.Pitch != 80 || hit.LineCompare < 400 {
				panic("未驗證的非鏈結視訊版面")
			}
			if !l.renderPageKnown {
				if hit.MapMask != 15 || l.renderOrigin[0]%4 != 0 {
					panic("未驗證的整頁繪製起點")
				}
				l.renderPage = (hit.Offset - uint32(l.renderOrigin[1]*hit.Pitch+l.renderOrigin[0]/4)) & 0xffff
				if l.renderPage != 0 && l.renderPage != 0x4000 {
					panic("未驗證的顯存頁")
				}
				l.renderPageKnown = true
				g.listLog("render-page", map[string]any{"target_page": l.renderPage, "visible_page": hit.DisplayStart, "first_write_offset": hit.Offset, "origin": l.renderOrigin})
			}
			p := int((hit.Offset - l.renderPage) & 0xffff)
			y, x := p/hit.Pitch, (p%hit.Pitch)*4
			for plane := 0; plane < 4; plane++ {
				if hit.MapMask&(1<<plane) != 0 {
					locations = append(locations, y*320+x+plane)
				}
			}
		} else {
			locations = []int{int(hit.Offset)}
		}
		for _, p := range locations {
			x, y := p%320, p/320
			for _, w := range l.clearTargets {
				if x >= w.X && x < w.X+w.Width && y >= w.Y && y < w.Y+8 {
					l.clearCovered[p] = true
				}
			}
		}
	})
	o.SetStepGuard(func(_ *oracle.Oracle) error {
		if !l.awaitPageFlip && !l.clearPending {
			return nil
		}
		if !l.renderPageKnown {
			return nil
		}
		layout := o.VideoLayoutState()
		if layout.DisplayStart != l.renderPage {
			return nil
		}
		pixels := 0
		for _, w := range l.clearTargets {
			pixels += w.Width * 8
		}
		if l.clearPending && len(l.clearCovered) != pixels {
			return nil
		}
		if l.clearPending {
			l.clearPending = false
			g.listLog("pane-cleared", map[string]any{"pixels": len(l.clearCovered), "targets": l.clearTargets, "target_page": l.renderPage, "visible_page": layout.DisplayStart})
			l.clearTargets = nil
		}
		if l.awaitPageFlip {
			l.awaitPageFlip = false
			g.listLog("page-visible", map[string]any{"target_page": l.renderPage, "visible_page": layout.DisplayStart})
		}
		return nil
	})
	registered := map[oracle.Addr]bool{}
	o.OnCall(oracle.Addr{Seg: 0x13c7, Off: 0x2f06}, func(_ *oracle.Oracle) {
		r := o.Regs()
		at := o.Caller()
		l.scrolls = append(l.scrolls, paintReturn{at, r.SS, r.SP + 4})
		s := [6]int{}
		for i := range s {
			s[i] = (int(o.StackWord(2+i)) - 8000) * 2
		}
		y0, x0, y1, x1, dy, dx := s[0], s[1], s[2], s[3], -s[4], -s[5]
		// 參數是裁切區。來源及目的都必須留在此區，不能把整個區域搬到區外。
		next := map[[2]int]listWord{}
		for _, w := range l.words {
			if w.X < x1 && w.X+w.Width > x0 && w.Y < y1 && w.Y+8 > y0 {
				if w.X < x0 || w.X+w.Width > x1 || w.Y < y0 || w.Y+8 > y1 {
					continue
				}
				w.X += dx
				w.Y += dy
				if w.X < x0 || w.X+w.Width > x1 || w.Y < y0 || w.Y+8 > y1 {
					continue
				}
			}
			next[[2]int{w.X, w.Y}] = w
		}
		l.words = next
		g.listLog("native-scroll", map[string]any{"delta": [2]int{dx, dy}, "rect": [4]int{x0, y0, x1 - x0, y1 - y0}})
		if !registered[at] {
			registered[at] = true
			o.OnCall(at, func(_ *oracle.Oracle) {
				if len(l.scrolls) == 0 {
					return
				}
				p := l.scrolls[len(l.scrolls)-1]
				r := o.Regs()
				if p.Addr == at && p.SS == r.SS && p.SP == r.SP {
					l.scrolls = l.scrolls[:len(l.scrolls)-1]
				}
			})
		}
	})
	headerRegistered := map[oracle.Addr]bool{}
	o.OnCall(oracle.Addr{Seg: 0xb72, Off: 0x46}, func(_ *oracle.Oracle) {
		s := [10]uint16{}
		for i := range s {
			s[i] = o.StackWord(i)
		}
		format, ok := listString(o, s[7], s[6])
		if !ok {
			return
		}
		col, row := int(byte(s[2])), int(byte(s[3]))
		if row == 1 {
			hadSuffix := l.pendingHeader != nil
			l.pane = ""
			for _, h := range l.config.Headers {
				if s[7] == h.Segment && s[6] == h.Offset && digest([]byte(format)) == h.SHA256 {
					l.pane = h.Pane
				}
			}
			if l.pane != "" && l.pendingHeader != nil {
				w := *l.pendingHeader
				l.words[[2]int{w.X, w.Y}] = w
				g.listLog("title-suffix-attached", map[string]any{"key": w.Key})
			}
			l.pendingHeader = nil
			if hadSuffix {
				r, at := o.Regs(), o.Caller()
				l.headerReturn = &paintReturn{at, r.SS, r.SP + 4}
				if !headerRegistered[at] {
					headerRegistered[at] = true
					o.OnCall(at, func(_ *oracle.Oracle) {
						r, p := o.Regs(), l.headerReturn
						if p != nil && p.Addr == at && p.SS == r.SS && p.SP == r.SP {
							l.headerTransition, l.headerReturn = false, nil
							g.listLog("title-render-return", nil)
						}
					})
				}
			}
			g.listLog("title-field", map[string]any{"source_sha256": digest([]byte(format)), "pointer": [2]uint16{s[7], s[6]}})
		}
		if len(l.paints) == 0 || l.pane == "" || format != l.sources["format.string"] {
			return
		}
		text, ok := listString(o, s[9], s[8])
		if !ok {
			return
		}
		l.erase(col*8, row*8, len(text)*8, 8)
		sha := digest([]byte(text))
		for _, binding := range l.config.Rows {
			if binding.Pane != l.pane || binding.SHA256 != sha {
				continue
			}
			for _, span := range binding.Spans {
				if span.Start+span.Length > len(text) || text[span.Start:span.Start+span.Length] != l.sources[span.Key] {
					panic("列表詞框來源不符")
				}
				w := listWord{X: (col + span.Start) * 8, Y: row * 8, Width: span.Length * 8, Key: span.Key, Group: "body", Foreground: byte(s[4]), Background: l.config.Background}
				if w.X < 0 || w.X+w.Width > 320 || w.Y < 0 || w.Y+8 > 200 {
					panic("列表中文字框越界")
				}
				l.words[[2]int{w.X, w.Y}] = w
			}
			l.awaitGlyph = g.listLog("row-before-glyph", map[string]any{"source_sha256": sha, "spans": binding.Spans})
			return
		}
		g.listLog("unknown-row-original", map[string]any{"source_sha256": sha})
	})
	g.installListFields()
	o.OnCall(oracle.Addr{Seg: 0x13c7, Off: 0xc96}, func(_ *oracle.Oracle) {
		if l.awaitGlyph >= 0 {
			l.events[l.awaitGlyph].FirstGlyph = o.Steps()
			l.awaitGlyph = -1
		}
	})
}
func (g *liveGame) installListFields() {
	l, o := g.list, g.o
	for _, point := range []struct {
		a     oracle.Addr
		bytes string
	}{
		{oracle.Addr{Seg: 0x0ceb, Off: 0x008e}, "558bec83ec085657c45e0626f6471c20"},
		{oracle.Addr{Seg: 0x1bb6, Off: 0x151f}, "558bec83ec0456803ec2da00751833c0"},
		{oracle.Addr{Seg: 0x1bb6, Off: 0x1585}, "cb558bec56803ecfda00750e1eb811a2"},
		{oracle.Addr{Seg: 0x1bb6, Off: 0x17b8}, "cb558bec83ec085657168d46fe50168d"},
	} {
		if hex.EncodeToString(o.Bytes(point.a, len(point.bytes)/2)) != point.bytes {
			panic("列表底列入口 bytes 不符")
		}
	}
	o.OnCall(oracle.Addr{Seg: 0x1bb6, Off: 0x151f}, func(_ *oracle.Oracle) {
		l.menuDepth++
		if l.footerTransition {
			for p, w := range l.words {
				if w.Group == "footer" {
					delete(l.words, p)
				}
			}
			g.listLog("footer-render-entry", nil)
		}
	})
	o.OnCall(oracle.Addr{Seg: 0x1bb6, Off: 0x1585}, func(_ *oracle.Oracle) {
		l.menuDepth--
		if l.menuDepth < 0 {
			panic("列表底列返回不成對")
		}
		if l.footerTransition {
			l.footerTransition = false
			g.listLog("footer-render-return", nil)
		}
	})
	o.OnCall(oracle.Addr{Seg: 0x1bb6, Off: 0x17b8}, func(_ *oracle.Oracle) {
		if o.Regs().AX != 0xffff {
			for _, w := range l.words {
				if w.Group == "footer" {
					l.footerTransition = true
					g.listLog("footer-selection-return", nil)
					break
				}
			}
		}
	})
	registered := map[oracle.Addr]bool{}
	o.OnCall(oracle.Addr{Seg: 0x0ceb, Off: 0x008e}, func(_ *oracle.Oracle) {
		if o.StackWord(4) != 1 {
			return
		}
		r, at := o.Regs(), o.Caller()
		l.buttons = append(l.buttons, paintReturn{at, r.SS, r.SP + 4})
		if registered[at] {
			return
		}
		registered[at] = true
		o.OnCall(at, func(_ *oracle.Oracle) {
			if len(l.buttons) == 0 {
				return
			}
			p, r := l.buttons[len(l.buttons)-1], o.Regs()
			if p.Addr == at && p.SS == r.SS && p.SP == r.SP {
				l.buttons = l.buttons[:len(l.buttons)-1]
			}
		})
	})
	o.OnCall(oracle.Addr{Seg: 0x1212, Off: 0x03a0}, func(_ *oracle.Oracle) {
		var s [9]uint16
		for i := range s {
			s[i] = o.StackWord(i)
		}
		format, ok := listString(o, s[6], s[5])
		if !ok {
			return
		}
		source := format
		if format == l.sources["format.string"] {
			source, ok = listString(o, s[8], s[7])
			if !ok {
				return
			}
		}
		for _, f := range l.config.Fields {
			if f.RawX != s[3] || f.RawY != s[2] || f.Caller != o.Caller() ||
				f.FormatSHA256 != digest([]byte(format)) || f.SHA256 != digest([]byte(source)) {
				continue
			}
			if f.Pane == "suffix" {
				if len(l.fills) > 0 {
					return
				}
			} else if f.Pane != l.pane {
				continue
			}
			native := func(v uint16) int {
				if v < 400 {
					return int(v)
				}
				return (int(v) - 8000) * 2
			}
			w := listWord{X: native(s[3]), Y: native(s[2]), Width: len(source) * 8, Key: f.Key,
				Group: f.Group, Foreground: byte(s[4]) & 15, Background: l.config.Background}
			if w.X < 0 || w.Y < 0 || w.X+w.Width > 320 || w.Y+8 > 200 {
				panic("列表欄位越界")
			}
			if f.Pane == "suffix" {
				l.pendingHeader = &w
				l.headerTransition = true
			} else {
				l.erase(w.X, w.Y, w.Width, 8)
				l.words[[2]int{w.X, w.Y}] = w
			}
			l.awaitGlyph = g.listLog("field-before-glyph", map[string]any{"key": f.Key, "source_sha256": f.SHA256,
				"format_sha256": f.FormatSHA256, "raw_xy": [2]uint16{s[3], s[2]}, "caller": o.Caller(), "word": w, "deferred": f.Pane == "suffix"})
			return
		}
	})
}
func (g *liveGame) updateList() error {
	l := g.list
	step := g.o.Steps()
	if l.action >= len(l.request.Actions) {
		return nil
	}
	a := l.request.Actions[l.action]
	if !l.sent && step == a.At {
		if a.Kind == "text" {
			must(g.o.TypeKeys(a.Key))
		} else {
			must(g.o.SendKeys(a.Key))
		}
		l.sent = true
	}
	next := a.At
	if l.sent {
		next = a.End
	}
	batch := uint64(500000)
	if g.fine {
		for _, w := range l.config.FineWindows {
			if step >= w[0] && step < w[1] {
				batch = 2000
				if w[1]-step < batch {
					batch = w[1] - step
				}
			} else if step < w[0] && w[0]-step < batch {
				batch = w[0] - step
			}
		}
	}
	if next-step < batch {
		batch = next - step
	}
	if batch == 0 {
		panic("列表步數未前進")
	}
	must(g.o.Run(batch))
	if g.o.Steps() == a.End {
		g.capture()
		g.checkpoints[len(g.checkpoints)-1]["label"] = a.Label
		l.action++
		l.sent = false
	}
	return nil
}
func (g *liveGame) composeList(px []byte) {
	l := g.list
	pal := g.o.Palette()
	for _, w := range l.snapshot() {
		x, y := w.X*2, w.Y*2
		bg, fg := pal[w.Background], pal[w.Foreground]
		for yy := 0; yy < 16; yy++ {
			for xx := 0; xx < w.Width*2; xx++ {
				copy(px[((y+yy)*640+x+xx)*4:][:3], bg[:])
			}
		}
		for i, ch := range []rune(g.catalog[w.Key]) {
			alpha, ok := g.glyphs.Glyphs[string(ch)]
			if !ok || len(alpha) != 320 {
				panic("列表字型缺字")
			}
			for yy := 0; yy < 20; yy++ {
				for xx := 0; xx < 16; xx++ {
					a := uint32(alpha[yy*16+xx])
					if a == 0 {
						continue
					}
					if yy >= 16 {
						panic("列表字墨超出列高")
					}
					d := ((y+yy)*640 + x + i*16 + xx) * 4
					for c := 0; c < 3; c++ {
						px[d+c] = byte((uint32(fg[c])*a + uint32(px[d+c])*(255-a) + 127) / 255)
					}
				}
			}
		}
	}
}
func (g *liveGame) listReceipt(result map[string]any) {
	l := g.list
	if len(l.paints) > 0 || len(l.fills) > 0 || len(l.scrolls) > 0 || l.clearPending || l.awaitPageFlip || l.menuDepth != 0 || len(l.buttons) > 0 || l.footerTransition || l.headerTransition || l.headerReturn != nil {
		b, err := json.MarshalIndent(map[string]any{"failed": true, "events": l.events, "covered": len(l.clearCovered), "targets": l.clearTargets, "words": l.snapshot(), "clear_pending": l.clearPending, "video_sample": l.videoSample}, "", "  ")
		must(err)
		must(os.WriteFile(filepath.Join(g.out, "list-failure.json"), b, 0644))
		panic(fmt.Sprintf("列表呈現未完成：paint=%d fill=%d scroll=%d clear=%t", len(l.paints), len(l.fills), len(l.scrolls), l.clearPending))
	}
	result["scope"] = "DRAFT automatic title-field context and observed complete row bindings, normal snapshot/key routes; no all-game/production/cold-boot claim"
	result["list_events"] = l.events
	result["list_frames"] = l.frames
	result["checkpoints"] = g.checkpoints
	result["unimplemented"] = g.o.Unimplemented()
	result["final_words"] = l.snapshot()
	result["video_write_layout_samples"] = l.videoSample
}

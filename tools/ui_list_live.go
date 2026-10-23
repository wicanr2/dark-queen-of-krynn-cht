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
	Paragraphs  []listParagraph
	Menus       map[string]string
	PaneLists   []listPaneSource
	RowCallers  []oracle.Addr
	Background  byte
	FineWindows [][2]uint64 `json:"fine_windows"`
}
type listPaneSource struct {
	RowFillPage                           bool
	Pane, DescriptorSHA256, MenuSignature string
	Caller                                oracle.Addr
}
type listField struct {
	Pane, Group, Key, SHA256, FormatSHA256 string
	MenuSignature                          string
	SourcePattern                          string
	UpperFormatSHA256                      string
	Start, Length                          int
	Width                                  int
	RawX, RawY                             uint16
	Caller, UpperCaller                    oracle.Addr
	UpperNative                            *[2]int
	BackgroundOverride, Color              *byte
}
type listFieldWrapper struct {
	Return paintReturn
	Caller oracle.Addr
	Source string
	X, Y   int
}
type listSpan struct {
	Start, Length int
	Key           string
}
type listRow struct {
	Pane, SHA256 string
	Spans        []listSpan
	Foregrounds  []byte
}
type listWord struct {
	X, Y, Width            int
	Key                    string
	Group                  string
	Foreground, Background byte
	Button                 bool `json:"Button,omitempty"`
}
type listTextEvent struct {
	Step       uint64
	Kind, Pane string
	Words      []listWord
	FirstGlyph uint64 `json:"first_glyph,omitempty"`
	Detail     any    `json:"detail,omitempty"`
}
type listFeedback struct {
	Upper                     paintReturn
	Entry                     uint64
	SourceSHA                 string
	ReturnPane                string
	Rect                      [4]int
	Pixels                    []byte
	Saved                     []listWord
	Started, Ready, Restoring bool
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
	awaitGlyphs            []int
	videoSample            []map[string]any
	awaitPageFlip          bool
	renderPageKnown        bool
	renderPage             uint32
	renderOrigin           [2]int
	action                 int
	sent                   bool
	menus                  []paintReturn
	buttons                []paintReturn
	pendingHeader          *listWord
	headerTransition       bool
	headerReturn           *paintReturn
	footerTransition       bool
	fieldWrapper           *listFieldWrapper
	clockReturn            *paintReturn
	clockKeys              map[string]bool
	paragraphPaints        []paintReturn
	trackListPage          bool
	descriptorContext      bool
	rowPagePending         bool
	rowPagePrelude         int
	feedback               *listFeedback
	serviceNotice          *serviceNotice
}

func listRectPixels(pixels []byte, rect [4]int) []byte {
	result := make([]byte, 0, rect[2]*rect[3])
	for y := rect[1]; y < rect[1]+rect[3]; y++ {
		result = append(result, pixels[y*320+rect[0]:y*320+rect[0]+rect[2]]...)
	}
	return result
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
func (l *listState) fieldStart(f listField, source string) (int, bool) {
	if f.SourcePattern == "" {
		return f.Start, f.SHA256 == digest([]byte(source))
	}
	if f.SourcePattern != "clock-period" || len(source) < 7 || len(source) > 8 {
		return 0, false
	}
	colon := len(source) - 6
	if source[colon] != ':' || source[colon+3] != ' ' {
		return 0, false
	}
	for _, i := range []int{0, colon + 1, colon + 2} {
		if source[i] < '0' || source[i] > '9' {
			return 0, false
		}
	}
	if colon == 2 && (source[1] < '0' || source[1] > '9') {
		return 0, false
	}
	start := len(source) - 2
	return start, source[start:] == l.sources[f.Key] && digest([]byte(source[start:])) == f.SHA256
}
func (l *listState) footerCompatible(signature string) bool {
	if l.config.Menus[signature] == "" {
		return false
	}
	expected, actual := 0, 0
	for _, word := range l.words {
		if word.Group == "footer" && word.Button {
			actual++
		}
	}
	for _, field := range l.config.Fields {
		if field.Pane != "menu" || field.MenuSignature != signature {
			continue
		}
		expected++
		width := field.Width
		if width == 0 {
			width = field.Length * 8
		}
		word, ok := l.words[[2]int{int(field.RawX) + field.Start*8, int(field.RawY)}]
		if !ok || word.Group != "footer" || !word.Button || word.Key != field.Key || word.Width != width || word.Background != l.config.Background {
			return false
		}
	}
	return expected > 0 && actual == expected
}
func (g *liveGame) installList(inputs, requestPath, sourcePath string) {
	l := g.list
	o := g.o
	l.words = map[[2]int]listWord{}
	l.clockKeys = map[string]bool{}
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
		if seenRows[id] || len(row.SHA256) != 64 || len(row.Spans) == 0 || len(row.Foregrounds) == 0 || (row.Pane != "inventory" && row.Pane != "grimoire" && row.Pane != "effects" && row.Pane != "shop-stock" && row.Pane != "temple-spells") {
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
		if f.UpperFormatSHA256 != "" && (f.Pane != "callsite" || len(f.UpperFormatSHA256) != 64 ||
			(f.UpperFormatSHA256 != digest([]byte("%s")) && f.UpperFormatSHA256 != digest([]byte("%s%s")))) {
			panic("未驗證的上層組句格式")
		}
		if f.UpperNative != nil || f.BackgroundOverride != nil || f.Color != nil {
			prompt := f.UpperNative != nil && *f.UpperNative == ([2]int{56, 192}) && f.BackgroundOverride != nil && *f.BackgroundOverride == 7 &&
				f.Color != nil && *f.Color == 0x70 && f.UpperCaller == (oracle.Addr{Seg: 0xCEB, Off: 0x4BD}) && f.Pane == "callsite" && f.Group == "footer" &&
				f.RawX == 8032 && f.RawY == 189 && f.Width == 0 && ((f.Start == 0 && f.Length == 5) || (f.Start == 13 && f.Length == 12))
			purchase := f.UpperNative != nil && *f.UpperNative == ([2]int{0, 192}) && f.BackgroundOverride == nil && f.Color != nil && *f.Color == 0x8f &&
				f.UpperCaller == (oracle.Addr{Seg: 0x088e, Off: 0x1560}) && f.Pane == "callsite" && f.Group == "footer" && f.RawX == 8004 && f.RawY == 189 &&
				f.Width == 0 && f.UpperFormatSHA256 == digest([]byte("%s"))
			itemsLabel := f.UpperNative != nil && *f.UpperNative == ([2]int{0, 192}) && f.BackgroundOverride != nil && *f.BackgroundOverride == 7 && f.Color != nil && *f.Color == 0x70 &&
				f.UpperCaller == (oracle.Addr{Seg: 0xCEB, Off: 0x995}) && f.Pane == "callsite" && f.Group == "footer" && f.RawX == 8004 && f.RawY == 189 &&
				f.Width == 0 && f.Start == 0 && f.UpperFormatSHA256 == digest([]byte("%s")) &&
				((f.Length == 5 && l.sources[f.Key] == "items") ||
					(f.Length == len(l.sources[f.Key]) && (l.sources[f.Key] == "Is It a Deal?" || l.sources[f.Key] == "Will you sell it?")))
			if !prompt && !purchase && !itemsLabel {
				panic("未驗證的提示欄位幾何或顏色")
			}
		}
		if f.SourcePattern != "" {
			if f.SourcePattern != "clock-period" || f.Pane != "callsite" || f.Group != "body" || f.UpperCaller != (oracle.Addr{Seg: 0x205e, Off: 0x53c}) || f.RawX != 8104 || f.RawY != 8060 || f.Start != 0 || f.Length != 2 || f.Width != 0 {
				panic("未知時間欄位契約")
			}
			l.clockKeys[f.Key] = true
		}
		width := f.Width
		if width == 0 {
			width = f.Length * 8
		}
		if f.Start < 0 || f.Length <= 0 || len(l.sources[f.Key]) != f.Length || g.catalog[f.Key] == "" || len([]rune(g.catalog[f.Key]))*8 > width || width < f.Length*8 || width > 320 || width%8 != 0 ||
			(f.Group != "header" && f.Group != "body" && f.Group != "footer") ||
			(f.Pane != "inventory" && f.Pane != "grimoire" && f.Pane != "suffix" && f.Pane != "callsite" && f.Pane != "menu") ||
			(f.Pane == "menu" && (len(f.MenuSignature) != 64 || l.config.Menus[f.MenuSignature] == "")) ||
			(f.Pane == "callsite" && f.UpperCaller == (oracle.Addr{})) {
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
	o.OnCall(oracle.Addr{Seg: 0xc15, Off: 0x55}, func(_ *oracle.Oracle) {
		if l.descriptorContext {
			l.pane = ""
		}
		l.descriptorContext, l.trackListPage = false, false
		ptr := oracle.Addr{Seg: o.StackWord(6), Off: o.StackWord(5)}
		if uint32(ptr.Off)+24 > 0x10000 || uint32(ptr.Seg)*16+uint32(ptr.Off)+24 > 0xa0000 {
			panic("列表來源指標越界")
		}
		descriptor := digest(o.Bytes(ptr, 24))
		for _, source := range l.config.PaneLists {
			if source.Caller != o.Caller() || source.DescriptorSHA256 != descriptor {
				continue
			}
			menu, ok := readMenuSource(o)
			if ok && menu.Signature == source.MenuSignature {
				l.pane = source.Pane
				l.descriptorContext = true
				l.trackListPage = source.RowFillPage
				g.listLog("list-context", map[string]any{"descriptor_sha256": descriptor, "menu_signature": menu.Signature, "caller": o.Caller()})
			}
		}
		entry(&l.paints, oracle.Addr{})
		g.listLog("list-entry", nil)
	})
	o.OnCall(oracle.Addr{Seg: 0xc15, Off: 0x508}, func(_ *oracle.Oracle) {
		ret(&l.paints)
		if len(l.paints) == 0 {
			if l.trackListPage && !l.renderPageKnown {
				panic("列表重用頁尚未定位")
			}
			l.trackListPage = false
		}
		g.listLog("list-return", nil)
	})
	o.OnCall(oracle.Addr{Seg: 0x13c7, Off: 0x78}, func(_ *oracle.Oracle) { entry(&l.fills, oracle.Addr{}) })
	o.OnCall(oracle.Addr{Seg: 0x13c7, Off: 0x6db}, func(_ *oracle.Oracle) { ret(&l.fills) })
	o.OnCall(oracle.Addr{Seg: 0x13c7, Off: 0xf7}, func(_ *oracle.Oracle) {
		r := o.Regs()
		v := [4]int{}
		for i := range v {
			v[i] = int(int16(o.Word(oracle.Addr{Seg: r.SS, Off: r.BP + 6 + uint16(i*2)})))
		}
		x, y, w, h := v[1], v[0], v[3]-v[1], v[2]-v[0]
		g.invalidateListParagraph(x, y, w, h, "native fill")
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
			l.descriptorContext = false
			l.trackListPage, l.rowPagePending = false, false
			g.listLog("pane-invalidate", [4]int{x, y, w, h})
		} else {
			if l.trackListPage && len(l.paints) > 0 && w > 0 && h > 0 {
				if l.clearPending || l.awaitPageFlip {
					panic("列表繪製頁尚未脫離整頁清除")
				}
				l.renderOrigin = [2]int{x, y}
				l.rowPagePending, l.trackListPage = true, false
				l.rowPagePrelude = 0
				g.listLog("list-page-baseline", [4]int{x, y, w, h})
			}
			l.erase(x, y, w, h)
			g.listLog("native-fill", [4]int{x, y, w, h})
		}
	})
	// 使用 Machine 已有的視訊寫入 observer，包括 planar 路徑及同值寫入。
	// 此固定 mode 13h 路徑須覆蓋每個舊字框的全部原生像素後才解除保留。
	o.OnVideoWriteEvent(func(hit oracle.VideoWriteEvent) {
		if f := l.feedback; f != nil && f.Ready && hit.Unchained && hit.Mode == 0x13 && hit.Pitch == 80 {
			p := int((hit.Offset - hit.DisplayStart) & 0xffff)
			y, x := p/80, (p%80)*4
			for plane := 0; plane < 4; plane++ {
				if hit.MapMask&(1<<plane) != 0 && x+plane >= f.Rect[0] && x+plane < f.Rect[0]+f.Rect[2] && y >= f.Rect[1] && y < f.Rect[1]+f.Rect[3] {
					if !f.Restoring {
						f.Restoring = true
						g.listLog("footer-feedback-restore-begin", map[string]any{"entry_step": f.Entry, "native_rect": f.Rect, "offset": hit.Offset, "map_mask": hit.MapMask})
					}
				}
			}
		}
		if l.rowPagePending {
			if !hit.Unchained || hit.Mode != 0x13 || hit.Pitch != 80 || hit.LineCompare < 400 || l.renderOrigin[0]%4 != 0 {
				panic("未驗證的列表填色頁寫入")
			}
			originOffset := uint32(l.renderOrigin[1]*hit.Pitch + l.renderOrigin[0]/4)
			// 原版可先還原其他區域。只以真正的全平面填色起點辨識頁面。
			if hit.MapMask != 15 || (hit.Offset != originOffset && hit.Offset != 0x4000+originOffset) {
				l.rowPagePrelude++
				return
			}
			l.renderPage = (hit.Offset - uint32(l.renderOrigin[1]*hit.Pitch+l.renderOrigin[0]/4)) & 0xffff
			if l.renderPage != 0 && l.renderPage != 0x4000 {
				panic("未驗證的列表顯存頁")
			}
			l.renderPageKnown, l.rowPagePending = true, false
			g.listLog("list-render-page", map[string]any{"target_page": l.renderPage, "visible_page": hit.DisplayStart, "first_write_offset": hit.Offset, "origin": l.renderOrigin, "pre_origin_writes": l.rowPagePrelude})
		}
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
	fieldRegistered := map[oracle.Addr]bool{}
	o.OnCall(oracle.Addr{Seg: 0xb72, Off: 0x46}, func(_ *oracle.Oracle) {
		s := [10]uint16{}
		for i := range s {
			s[i] = o.StackWord(i)
		}
		col, row := int(byte(s[2])), int(byte(s[3]))
		l.fieldWrapper = nil
		if len(l.clockKeys) > 0 && o.Caller() == (oracle.Addr{Seg: 0x205e, Off: 0x53c}) && col*8 == 208 && row*8 == 120 {
			for pos, word := range l.words {
				if l.clockKeys[word.Key] {
					delete(l.words, pos)
				}
			}
			g.listLog("clock-source-reset", map[string]any{"caller": o.Caller(), "native_xy": [2]int{col * 8, row * 8}})
		}
		format, ok := listString(o, s[7], s[6])
		if !ok {
			return
		}
		for _, f := range l.config.Fields {
			_, matches := l.fieldStart(f, format)
			if f.UpperFormatSHA256 != "" {
				matches = digest([]byte(format)) == f.UpperFormatSHA256
			}
			if f.Pane != "callsite" || f.UpperCaller != o.Caller() || !matches {
				continue
			}
			r, at := o.Regs(), o.Caller()
			if at == (oracle.Addr{Seg: 0x088e, Off: 0x1560}) && f.UpperFormatSHA256 == digest([]byte("%s")) {
				text, ok := listString(o, s[9], s[8])
				if !ok || digest([]byte(text)) != f.SHA256 {
					continue
				}
				if l.pane != "shop-stock" && l.pane != "inventory" {
					l.erase(8, 189, 304, 8)
					l.footerTransition = false
					g.listLog("unknown-feedback-original", map[string]any{"caller": at, "source_sha256": f.SHA256, "native_rect": [4]int{8, 189, 304, 8}, "reason": "unrecognized return context"})
					return
				}
			}
			l.fieldWrapper = &listFieldWrapper{Return: paintReturn{at, r.SS, r.SP + 4}, Caller: at, Source: format, X: col * 8, Y: row * 8}
			if at == (oracle.Addr{Seg: 0x088e, Off: 0x1560}) && f.UpperFormatSHA256 == digest([]byte("%s")) {
				text, ok := listString(o, s[9], s[8])
				if ok && digest([]byte(text)) == f.SHA256 && l.feedback == nil {
					rect := [4]int{8, 189, len(text) * 8, 8}
					if l.pane == "inventory" {
						// 原版先撤掉整個背包底列；短回報也必須撤除右側舊按鈕。
						rect[2] = 304
					}
					if rect[0]+rect[2] > 320 {
						panic("購買回報越界")
					}
					feedback := &listFeedback{Upper: l.fieldWrapper.Return, Entry: o.Steps(), SourceSHA: f.SHA256, ReturnPane: l.pane, Rect: rect, Pixels: listRectPixels(o.Indexed(), rect)}
					for _, word := range l.snapshot() {
						if word.X < rect[0]+rect[2] && word.X+word.Width > rect[0] && word.Y < rect[1]+rect[3] && word.Y+8 > rect[1] {
							feedback.Saved = append(feedback.Saved, word)
						}
					}
					l.feedback = feedback
					g.listLog("footer-feedback-capture", map[string]any{"caller": at, "source_sha256": f.SHA256, "return_pane": feedback.ReturnPane, "native_rect": rect, "before_sha256": digest(feedback.Pixels), "saved_words": feedback.Saved})
				}
			}
			if f.SourcePattern == "clock-period" {
				p := l.fieldWrapper.Return
				l.clockReturn = &p
			}
			if !fieldRegistered[at] {
				fieldRegistered[at] = true
				o.OnCall(at, func(_ *oracle.Oracle) {
					p, r := l.fieldWrapper, o.Regs()
					if p != nil && p.Return.Addr == at && p.Return.SS == r.SS && p.Return.SP == r.SP {
						if feedback := l.feedback; feedback != nil && feedback.Upper == p.Return {
							feedback.Ready = true
							l.footerTransition = false
							g.listLog("footer-feedback-ready", map[string]any{"entry_step": feedback.Entry, "caller": at, "ss": r.SS, "sp": r.SP})
						}
						l.fieldWrapper = nil
					}
					if c := l.clockReturn; c != nil && c.Addr == at && c.SS == r.SS && c.SP == r.SP {
						l.clockReturn = nil
						g.listLog("clock-render-return", map[string]any{"caller": at, "ss": r.SS, "sp": r.SP})
					}
				})
			}
			break
		}
		rowCaller := false
		for _, caller := range l.config.RowCallers {
			rowCaller = rowCaller || caller == o.Caller()
		}
		if row == 1 && !(rowCaller && l.descriptorContext) {
			hadSuffix := l.pendingHeader != nil
			l.pane = ""
			l.descriptorContext = false
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
		if !rowCaller || l.pane == "" || format != l.sources["format.string"] {
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
			allowed := false
			for _, foreground := range binding.Foregrounds {
				allowed = allowed || foreground == byte(s[4])
			}
			if !allowed {
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
			l.awaitGlyphs = append(l.awaitGlyphs, g.listLog("row-before-glyph", map[string]any{"source_sha256": sha, "spans": binding.Spans,
				"caller": o.Caller(), "foreground": byte(s[4]), "within_list": len(l.paints) > 0}))
			return
		}
		g.listLog("unknown-row-original", map[string]any{"source_sha256": sha})
	})
	g.installListFields()
	g.installListParagraphs()
	o.OnCall(oracle.Addr{Seg: 0x13c7, Off: 0xc96}, func(_ *oracle.Oracle) {
		for _, index := range l.awaitGlyphs {
			l.events[index].FirstGlyph = o.Steps()
		}
		l.awaitGlyphs = nil
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
	menuReturns := map[oracle.Addr]bool{}
	o.OnCall(oracle.Addr{Seg: 0x1bb6, Off: 0x151f}, func(_ *oracle.Oracle) {
		r, at := o.Regs(), o.Caller()
		p := paintReturn{at, r.SS, r.SP + 4}
		// 執行前的中斷可使同一入口再次被觀測，仍屬同一次呼叫。
		if len(l.menus) > 0 && l.menus[len(l.menus)-1] == p {
			return
		}
		l.menus = append(l.menus, p)
		if notice := l.serviceNotice; notice != nil && notice.Ready && notice.Restoring {
			menu, ok := readMenuSource(o)
			if ok && at == (oracle.Addr{Seg: 0x0ceb, Off: 0x0e18}) && l.config.Menus[menu.Signature] == "inventory" {
				l.erase(8, 189, 304, 8)
				l.serviceNotice = nil
				l.footerTransition = true
				g.listLog("service-notice-closed", map[string]any{"entry_step": notice.Entry, "caller": at, "menu_signature": menu.Signature})
			}
		}
		if f := l.feedback; f != nil && f.Ready && f.Restoring {
			menu, ok := readMenuSource(o)
			// 回報結束後由原版重新畫選單，並不還原成進入印字函式前的像素。
			// 只接已觀測的商店 caller 及完整選單，未知返回邊界仍保留未完成狀態。
			if ok && at == (oracle.Addr{Seg: 0x0ceb, Off: 0x0e18}) && l.config.Menus[menu.Signature] == f.ReturnPane {
				l.erase(f.Rect[0], f.Rect[1], f.Rect[2], f.Rect[3])
				l.feedback = nil
				l.footerTransition = true
				g.listLog("footer-feedback-closed", map[string]any{"entry_step": f.Entry, "caller": at, "native_rect": f.Rect, "menu_signature": menu.Signature, "native_sha256": digest(listRectPixels(o.Indexed(), f.Rect))})
			}
		}
		if l.footerTransition {
			menu, ok := readMenuSource(o)
			signature := ""
			if ok {
				signature = menu.Signature
			}
			preserved := l.footerCompatible(signature)
			if !preserved {
				for p, w := range l.words {
					if w.Group == "footer" && w.Button {
						delete(l.words, p)
					}
				}
			}
			g.listLog("footer-render-entry", map[string]any{"menu_signature": signature, "preserved": preserved})
		}
		if !menuReturns[at] {
			menuReturns[at] = true
			o.OnCall(at, func(_ *oracle.Oracle) {
				if len(l.menus) == 0 {
					return
				}
				p, r := l.menus[len(l.menus)-1], o.Regs()
				if p.Addr == at && p.SS == r.SS && p.SP == r.SP {
					l.menus = l.menus[:len(l.menus)-1]
					if len(l.menus) == 0 && l.footerTransition {
						l.footerTransition = false
						g.listLog("footer-render-return", map[string]any{"caller": at, "ss": r.SS, "sp": r.SP})
					}
				}
			})
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
			start, matches := l.fieldStart(f, source)
			if f.RawX != s[3] || f.RawY != s[2] || f.Caller != o.Caller() ||
				f.FormatSHA256 != digest([]byte(format)) || !matches {
				continue
			}
			if f.Color != nil && byte(s[4]) != *f.Color {
				continue
			}
			if f.Pane == "suffix" {
				if len(l.fills) > 0 {
					return
				}
			} else if f.Pane == "callsite" {
				p := l.fieldWrapper
				if p == nil || p.Caller != f.UpperCaller || (f.UpperFormatSHA256 == "" && p.Source != source) ||
					(f.UpperFormatSHA256 != "" && digest([]byte(p.Source)) != f.UpperFormatSHA256) {
					continue
				}
				if feedback := l.feedback; feedback != nil && !feedback.Started && f.UpperCaller == (oracle.Addr{Seg: 0x088e, Off: 0x1560}) {
					feedback.Started = true
					l.erase(feedback.Rect[0], feedback.Rect[1], feedback.Rect[2], feedback.Rect[3])
					g.listLog("footer-feedback-entry", map[string]any{"entry_step": feedback.Entry, "native_rect": feedback.Rect, "source_sha256": feedback.SourceSHA})
				}
			} else if f.Pane == "menu" {
				menu, ok := readMenuSource(o)
				if !ok || menu.Signature != f.MenuSignature {
					continue
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
			if start+f.Length > len(source) || source[start:start+f.Length] != l.sources[f.Key] {
				panic("欄位詞框來源不符")
			}
			if f.Pane == "callsite" {
				expected := [2]int{native(s[3]), native(s[2])}
				if f.UpperNative != nil {
					expected = *f.UpperNative
				}
				if l.fieldWrapper.X != expected[0] || l.fieldWrapper.Y != expected[1] {
					panic("欄位上下層座標不符")
				}
			}
			width := f.Width
			if width == 0 {
				width = f.Length * 8
			}
			w := listWord{X: native(s[3]) + start*8, Y: native(s[2]), Width: width, Key: f.Key,
				Group: f.Group, Foreground: byte(s[4]) & 15, Background: l.config.Background, Button: f.Pane == "menu"}
			if f.BackgroundOverride != nil {
				w.Background = *f.BackgroundOverride
			}
			if w.X < 0 || w.Y < 0 || w.X+w.Width > 320 || w.Y+8 > 200 {
				panic("列表欄位越界")
			}
			g.invalidateListParagraph(w.X, w.Y, w.Width, 8, "field overwrite")
			if f.Pane == "suffix" {
				l.pendingHeader = &w
				l.headerTransition = true
			} else {
				l.erase(w.X, w.Y, w.Width, 8)
				l.words[[2]int{w.X, w.Y}] = w
			}
			l.awaitGlyphs = append(l.awaitGlyphs, g.listLog("field-before-glyph", map[string]any{"key": f.Key, "source_sha256": digest([]byte(source)), "source_start": start,
				"format_sha256": f.FormatSHA256, "raw_xy": [2]uint16{s[3], s[2]}, "caller": o.Caller(), "word": w, "deferred": f.Pane == "suffix", "menu_signature": f.MenuSignature}))
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
	if g.reader != nil && g.reader.ControlIndex < len(g.reader.Controls) {
		at := g.reader.Controls[g.reader.ControlIndex].At
		if at > step && at-step < batch {
			batch = at - step
		}
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
	if len(l.paints) > 0 || len(l.fills) > 0 || len(l.scrolls) > 0 || l.clearPending || l.awaitPageFlip || len(l.menus) > 0 || len(l.buttons) > 0 || l.footerTransition || l.headerTransition || l.headerReturn != nil || l.rowPagePending || l.trackListPage || len(l.awaitGlyphs) > 0 || l.clockReturn != nil || len(l.paragraphPaints) > 0 || l.feedback != nil || l.serviceNotice != nil {
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
	result["button_ownership"] = true
	result["paragraphs"] = g.pages
	result["final_paragraph"] = g.page
	result["video_write_layout_samples"] = l.videoSample
}

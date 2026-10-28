// DRAFT：MZ 冷讀期間的原版底列提示。只改呈現，字模與角色管理分開保存。
package main

import (
	"encoding/hex"
	"encoding/json"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"github.com/wicanr2/dosgolem/oracle"
)

type coldPromptBinding struct {
	Key, Group, SourceSHA256, FormatSHA256, UpperFormatSHA256, MenuSignature string
	Caller, UpperCaller                                                      oracle.Addr
	RawX, RawY                                                               uint16
	X, Y, Width                                                              int
	Color                                                                    *uint16
	Background                                                               byte
	Button                                                                   bool
}
type coldPromptConfig struct {
	Bindings    []coldPromptBinding
	Menus       map[string]string
	FineWindows [][2]uint64 `json:",omitempty"`
}
type coldPromptFill struct {
	Return    paintReturn
	Entry     uint64
	Affected  bool
	Page      uint32
	PageKnown bool
}
type coldPromptPrint struct {
	Return                           paintReturn
	Entry                            uint64
	Key                              string
	Page                             uint32
	PageKnown, Complete, Seen, Stale bool
}
type coldPromptUI struct {
	Path             string
	Config           coldPromptConfig
	Catalog, Sources map[string]string
	Glyphs           glyphSet
	Words            map[[2]int]listWord
	Events           []map[string]any
	Wrapper          *listFieldWrapper
	Fills            []coldPromptFill
	Await            []int
	Owner            *liveGame
	Prints           map[string]*coldPromptPrint
	Pending          []*coldPromptPrint
	ClearPages       []uint32
	VisiblePage      uint32
	VisibleKnown     bool
}

func (u *coldPromptUI) snapshot() []listWord {
	var words []listWord
	for _, w := range u.Words {
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
func (g *liveGame) coldPromptLog(kind string, detail any) int {
	u := g.cold.ui
	u.Events = append(u.Events, map[string]any{"step": g.o.Steps(), "kind": kind, "detail": detail, "words": u.snapshot()})
	return len(u.Events) - 1
}
func (u *coldPromptUI) erase(x, y, w, h int) bool {
	removed := false
	for p, v := range u.Words {
		if v.X < x+w && v.X+v.Width > x && v.Y < y+h && v.Y+8 > y {
			delete(u.Words, p)
			removed = true
		}
	}
	return removed
}
func (u *coldPromptUI) held() bool {
	if len(u.Config.Bindings) == 15 {
		u.syncPages()
	}
	if len(u.ClearPages) > 0 {
		return true
	}
	for _, w := range u.Words {
		if len(u.Config.Bindings) != 15 {
			break
		}
		p := u.Prints[w.Key]
		if p == nil || !p.Complete || !p.Seen || p.Stale {
			return true
		}
	}
	for _, f := range u.Fills {
		if f.Affected {
			return true
		}
	}
	return false
}

// 同一個實體頁再度顯示，不代表舊文字仍有效。離開後須等待原版覆寫。
func (u *coldPromptUI) syncPages() {
	if len(u.Config.Bindings) != 15 {
		return
	}
	if len(u.Words) == 0 && len(u.ClearPages) == 0 {
		return
	}
	page := u.Owner.o.VideoLayoutState().DisplayStart
	if u.VisibleKnown && u.VisiblePage == page {
		return
	}
	u.VisiblePage = page
	u.VisibleKnown = true
	for _, p := range u.Prints {
		if !p.Complete {
			continue
		}
		if p.Page == page {
			p.Seen = true
		} else if p.Seen {
			p.Stale = true
		}
	}
	remaining := u.ClearPages[:0]
	for _, p := range u.ClearPages {
		if p != page {
			remaining = append(remaining, p)
		}
	}
	u.ClearPages = remaining
}
func coldWritePage(known *bool, page *uint32, hit oracle.VideoWriteEvent) {
	if !hit.Unchained || hit.Mode != 0x13 || hit.Pitch != 80 || hit.LineCompare < 400 {
		panic("未驗證的冷讀文字顯存版面")
	}
	next := hit.Offset & 0xc000
	if (next != 0 && next != 0x4000) || (*known && next != *page) {
		panic("未驗證的冷讀文字顯存頁")
	}
	*known = true
	*page = next
}
func (u *coldPromptUI) videoWrite(hit oracle.VideoWriteEvent) {
	if len(u.Config.Bindings) != 15 {
		return
	}
	for _, p := range u.Pending {
		coldWritePage(&p.PageKnown, &p.Page, hit)
	}
	for i := range u.Fills {
		f := &u.Fills[i]
		coldWritePage(&f.PageKnown, &f.Page, hit)
	}
}
func (g *liveGame) installColdPrompts(path string) {
	u := &coldPromptUI{Owner: g, Prints: map[string]*coldPromptPrint{}, Path: path, Words: map[[2]int]listWord{}, Catalog: readLiveCatalog(filepath.Join(path, "zh-TW.tsv")), Sources: readLiveCatalog(filepath.Join(path, "en.tsv"))}
	raw, e := os.ReadFile(filepath.Join(path, "bindings.json"))
	must(e)
	must(json.Unmarshal(raw, &u.Config))
	raw, e = os.ReadFile(filepath.Join(path, "glyphs-16.json"))
	must(e)
	must(json.Unmarshal(raw, &u.Glyphs))
	count := len(u.Config.Bindings)
	if u.Glyphs.Size != 16 || u.Glyphs.Height != 20 || (count != 6 && count != 15 && count != 17) || len(u.Catalog) != count || len(u.Sources) != count {
		panic("冷讀提示輸入不符")
	}
	last := uint64(220000000)
	for _, w := range u.Config.FineWindows {
		if w[0] < last || w[1] <= w[0] || w[1] > g.cold.Handoff {
			panic("開頭提示細驗區間不符")
		}
		last = w[1]
	}
	for _, b := range u.Config.Bindings {
		source, ok := u.Sources[b.Key]
		width := len(source) * 8
		if !b.Button && b.SourceSHA256 == loadSourcePromptSHA256 && b.Group == "source" {
			width -= 8
		}
		if !b.Button && b.SourceSHA256 == loadSlotPromptSHA256 && b.Group == "slots" {
			width -= 4
		}
		startup := validStartupCaption(b, source)
		if !ok || digest([]byte(source)) != b.SourceSHA256 || u.Catalog[b.Key] == "" || (width != b.Width && !startup) || len([]rune(u.Catalog[b.Key]))*8 > b.Width ||
			b.X < 0 || (b.Y != 189 && !startup) || b.X+b.Width > 312 || (b.Background > 15 && !startup) ||
			(b.Button && (b.Caller != (oracle.Addr{Seg: 0xceb, Off: 0x1be}) || u.Config.Menus[b.MenuSignature] == "")) ||
			(!b.Button && !startup && (b.Caller != (oracle.Addr{Seg: 0xb72, Off: 0x27c}) || b.UpperCaller == (oracle.Addr{}))) ||
			(len(b.Key) >= 8 && b.Key[:8] == "startup." && !startup) {
			panic("冷讀提示綁定不符")
		}
	}
	for _, p := range []struct {
		a oracle.Addr
		s string
	}{
		{oracle.Addr{Seg: 0xb72, Off: 0x46}, "558bec83ec60168d461250"},
		{oracle.Addr{Seg: 0x13c7, Off: 0x78}, "558bec83ec2e5657"},
		{oracle.Addr{Seg: 0x13c7, Off: 0xf7}, "8b4606"},
	} {
		if hex.EncodeToString(g.o.Bytes(p.a, len(p.s)/2)) != p.s {
			panic("冷讀提示掛勾不符")
		}
	}
	g.cold.ui = u
	active := func() bool {
		return !g.cold.ready || len(u.Words) > 0 || len(u.Fills) > 0 || len(u.ClearPages) > 0 || len(u.Pending) > 0
	}
	o := g.o
	o.OnVideoWriteEvent(u.videoWrite)
	o.SetStepGuard(func(_ *oracle.Oracle) error { u.syncPages(); return nil })
	returns := map[oracle.Addr]bool{}
	printReturns := map[oracle.Addr]bool{}
	o.OnCall(oracle.Addr{Seg: 0xb72, Off: 0x46}, func(_ *oracle.Oracle) {
		if !active() || g.cold.ready {
			return
		}
		u.Wrapper = nil
		source, ok := listString(o, o.StackWord(7), o.StackWord(6))
		if !ok {
			return
		}
		r, at := o.Regs(), o.Caller()
		mark := paintReturn{at, r.SS, r.SP + 4}
		u.Wrapper = &listFieldWrapper{Return: mark, Caller: at, Source: source}
		if returns[at] {
			return
		}
		returns[at] = true
		o.OnCall(at, func(_ *oracle.Oracle) {
			if !active() || u.Wrapper == nil {
				return
			}
			r := o.Regs()
			p := u.Wrapper.Return
			if p.Addr == at && p.SS == r.SS && p.SP == r.SP {
				u.Wrapper = nil
			}
		})
	})
	o.OnCall(oracle.Addr{Seg: 0x1bb6, Off: 0x151f}, func(_ *oracle.Oracle) {
		if !active() {
			return
		}
		menu, ok := readMenuSource(o)
		pane := ""
		footer := ok
		if ok {
			pane = u.Config.Menus[menu.Signature]
			for _, b := range menu.Buttons {
				if b.RawY != 8094 {
					footer = false
				}
			}
		}
		for p, w := range u.Words {
			if startupBody(w.Group) {
				continue
			}
			if !footer || (w.Button && pane == "") || w.Group == "loading" || (pane != "" && w.Group != pane) {
				delete(u.Words, p)
			}
		}
		g.coldPromptLog("menu-entry", map[string]any{"menu": menu, "valid": ok, "pane": pane})
	})
	o.OnCall(oracle.Addr{Seg: 0x1212, Off: 0x3a0}, func(_ *oracle.Oracle) {
		if !active() {
			return
		}
		format, ok := listString(o, o.StackWord(6), o.StackWord(5))
		if !ok {
			return
		}
		source := format
		if format == "%s" {
			source, ok = listString(o, o.StackWord(8), o.StackWord(7))
			if !ok {
				return
			}
		}
		if g.cold.ready {
			width := len(source) * 8
			if format == "%c" {
				width = 8
			} else if format != "%s" && strings.Contains(format, "%") {
				return
			}
			native := func(v uint16) int {
				if v < 400 {
					return int(v)
				}
				return (int(v) - 8000) * 2
			}
			rect := [4]int{native(o.StackWord(3)), native(o.StackWord(2)), width, 8}
			if u.erase(rect[0], rect[1], rect[2], rect[3]) {
				g.coldPromptLog("native-text-overwrite", map[string]any{"caller": o.Caller(), "source_sha256": digest([]byte(source)), "rect": rect})
			}
			return
		}
		for _, b := range u.Config.Bindings {
			if b.Caller != o.Caller() || b.RawX != o.StackWord(3) || b.RawY != o.StackWord(2) || b.SourceSHA256 != digest([]byte(source)) || b.FormatSHA256 != digest([]byte(format)) {
				continue
			}
			if b.Color != nil && *b.Color != o.StackWord(4) {
				continue
			}
			if b.Button {
				menu, valid := readMenuSource(o)
				if !valid || menu.Signature != b.MenuSignature {
					continue
				}
			}
			if !b.Button && b.UpperCaller != (oracle.Addr{}) {
				if u.Wrapper == nil || u.Wrapper.Caller != b.UpperCaller || digest([]byte(u.Wrapper.Source)) != b.UpperFormatSHA256 {
					continue
				}
			}
			word := listWord{X: b.X, Y: b.Y, Width: b.Width, Key: b.Key, Group: b.Group, Foreground: byte(o.StackWord(4)) & 15, Background: b.Background, Button: b.Button}
			mark := paintReturn{o.Caller(), o.Regs().SS, o.Regs().SP + 4}
			if len(u.Pending) > 0 {
				last := u.Pending[len(u.Pending)-1]
				if last.Key == b.Key && last.Return == mark {
					continue
				}
			}
			u.erase(word.X, word.Y, word.Width, 8)
			u.Words[[2]int{word.X, word.Y}] = word
			index := g.coldPromptLog("word-before-glyph", map[string]any{"key": b.Key, "source_sha256": b.SourceSHA256, "format_sha256": b.FormatSHA256, "caller": o.Caller(), "word": word})
			u.Await = append(u.Await, index)
			if len(u.Config.Bindings) != 15 && b.Group != "quiz" {
				continue
			}
			r, at := o.Regs(), o.Caller()
			p := &coldPromptPrint{Return: paintReturn{at, r.SS, r.SP + 4}, Entry: o.Steps(), Key: b.Key}
			u.Prints[b.Key] = p
			u.Pending = append(u.Pending, p)
			if !printReturns[at] {
				printReturns[at] = true
				o.OnCall(at, func(_ *oracle.Oracle) {
					if len(u.Pending) == 0 {
						return
					}
					p := u.Pending[len(u.Pending)-1]
					r := o.Regs()
					if p.Return.Addr != at || p.Return.SS != r.SS || p.Return.SP != r.SP {
						return
					}
					if !p.PageKnown && len(u.Config.Bindings) == 15 {
						panic("冷讀文字沒有顯存寫入")
					}
					p.Complete = true
					p.Seen = p.Page == o.VideoLayoutState().DisplayStart
					u.Pending = u.Pending[:len(u.Pending)-1]
					u.syncPages()
					g.coldPromptLog("print-complete", map[string]any{"call_step": p.Entry, "key": p.Key, "target_page": p.Page})
					g.completeStartupQuiz()
				})
			}
		}
	})
	o.OnCall(oracle.Addr{Seg: 0x13c7, Off: 0xc96}, func(_ *oracle.Oracle) {
		if !active() {
			return
		}
		for _, i := range u.Await {
			u.Events[i]["first_glyph"] = o.Steps()
		}
		u.Await = nil
	})
	g.installColdFillObserver(active)
}

func (g *liveGame) completeStartupQuiz() bool {
	u, l := g.cold.ui, g.list
	if l == nil || !l.footerTransition {
		return false
	}
	for _, key := range []string{"startup.quiz-page", "startup.quiz-word", "startup.quiz-heading", "startup.quiz-enter"} {
		p := u.Prints[key]
		if p == nil || !p.Complete {
			return false
		}
		found := false
		for _, word := range u.Words {
			found = found || word.Key == key && word.Group == "quiz"
		}
		if !found {
			return false
		}
	}
	for _, word := range l.words {
		if word.Group == "footer" && !strings.HasPrefix(word.Key, "role.") {
			return false
		}
	}
	removed := 0
	for pos, word := range l.words {
		if word.Group == "footer" && strings.HasPrefix(word.Key, "role.") {
			delete(l.words, pos)
			removed++
		}
	}
	l.footerTransition = false
	g.coldPromptLog("quiz-presentation-ready", map[string]any{"retired_role_words": removed})
	return true
}

func (g *liveGame) installColdFillObserver(active func() bool) {
	u, o := g.cold.ui, g.o
	returns := map[oracle.Addr]bool{}
	o.OnCall(oracle.Addr{Seg: 0x13c7, Off: 0x78}, func(_ *oracle.Oracle) {
		if !active() {
			return
		}
		r := o.Regs()
		mark := paintReturn{Addr: o.Caller(), SS: r.SS, SP: r.SP + 4}
		// OnCall先於IRQ派送。ISR返回入口時，原版prologue可能尚未執行。
		if len(u.Fills) > 0 && u.Fills[len(u.Fills)-1].Return == mark {
			return
		}
		u.Fills = append(u.Fills, coldPromptFill{Return: mark, Entry: o.Steps()})
		if !returns[mark.Addr] {
			returns[mark.Addr] = true
			o.OnCall(mark.Addr, func(_ *oracle.Oracle) {
				if len(u.Fills) == 0 {
					return
				}
				f, r := u.Fills[len(u.Fills)-1], o.Regs()
				if f.Return.Addr != mark.Addr || f.Return.SS != r.SS || f.Return.SP != r.SP {
					return
				}
				// 已回到呼叫者，原版retf已完成；此後的IRQ重訪不再結束同筆交易。
				u.Fills = u.Fills[:len(u.Fills)-1]
				if f.Affected {
					if len(u.Config.Bindings) != 15 {
						g.coldPromptLog("native-clear-return", map[string]any{"entry_step": f.Entry})
						return
					}
					if !f.PageKnown {
						panic("冷讀填色沒有顯存寫入")
					}
					if f.Page != o.VideoLayoutState().DisplayStart {
						u.ClearPages = append(u.ClearPages, f.Page)
					}
					u.syncPages()
					g.coldPromptLog("native-clear-return", map[string]any{"entry_step": f.Entry, "target_page": f.Page})
				}
			})
		}
	})
	o.OnCall(oracle.Addr{Seg: 0x13c7, Off: 0xf7}, func(_ *oracle.Oracle) {
		if !active() {
			return
		}
		if len(u.Fills) == 0 {
			panic("冷讀填色未配對")
		}
		r := o.Regs()
		v := [4]int{}
		for i := range v {
			v[i] = int(int16(o.Word(oracle.Addr{Seg: r.SS, Off: r.BP + 6 + uint16(i*2)})))
		}
		rect := [4]int{v[1], v[0], v[3] - v[1], v[2] - v[0]}
		if u.erase(rect[0], rect[1], rect[2], rect[3]) {
			f := &u.Fills[len(u.Fills)-1]
			f.Affected = true
			g.coldPromptLog("native-clear", map[string]any{"entry_step": f.Entry, "rect": rect})
		}
	})
}

func startupBody(group string) bool {
	return group == "role-name" || group == "party-name" || group == "quiz" || group == "opening-title"
}

func validStartupCaption(b coldPromptBinding, source string) bool {
	if len(b.Key) < 8 || b.Key[:8] != "startup." {
		return false
	}
	type spec struct {
		source, group string
		x, y          uint16
		upper         oracle.Addr
		color         uint16
		button        bool
	}
	specs := map[string]spec{
		"startup.title":        {"The Dark Queen of Krynn", "opening-title", 8032, 8020, oracle.Addr{Seg: 0x20f9, Off: 0xcf}, 0x87, false},
		"startup.version":      {"Version 1.1        July 29,1992", "opening-title", 8016, 8024, oracle.Addr{Seg: 0x20f9, Off: 0xeb}, 0x87, false},
		"startup.play":         {"Play", "opening", 8, 189, oracle.Addr{}, 0, true},
		"startup.demo":         {"Demo", "opening", 48, 189, oracle.Addr{}, 0, true},
		"startup.quit":         {"Quit", "opening", 88, 189, oracle.Addr{}, 0, true},
		"startup.role-name":    {"Name", "role-name", 8004, 8008, oracle.Addr{Seg: 0x205e, Off: 0x2a0}, 0x8c, false},
		"startup.party-name":   {"Name", "party-name", 8068, 8008, oracle.Addr{Seg: 0x205e, Off: 0x2a0}, 0x8c, false},
		"startup.quiz-page":    {" journal, page ", "quiz", 8012, 8008, oracle.Addr{Seg: 0x2808, Off: 0x148}, 0x8a, false},
		"startup.quiz-word":    {" what is word # ", "quiz", 8012, 8016, oracle.Addr{Seg: 0x2808, Off: 0x1ad}, 0x8a, false},
		"startup.quiz-heading": {" after the heading ", "quiz", 8012, 8024, oracle.Addr{Seg: 0x2808, Off: 0x214}, 0x8a, false},
		"startup.quiz-enter":   {"Enter ", "quiz", 8004, 189, oracle.Addr{}, 0x8b, false},
	}
	s, ok := specs[b.Key]
	if !ok || source != s.source || b.Group != s.group || b.RawX != s.x || b.RawY != s.y || b.Button != s.button || b.Background != 23 || b.UpperCaller != s.upper {
		return false
	}
	native := func(v uint16) int {
		if v < 400 {
			return int(v)
		}
		return (int(v) - 8000) * 2
	}
	if b.X != native(s.x) || b.Y != native(s.y) || b.Width != len(strings.TrimRight(source, " "))*8 {
		return false
	}
	caller := oracle.Addr{Seg: 0xb72, Off: 0x27c}
	format := "%s"
	if s.button {
		caller = oracle.Addr{Seg: 0xceb, Off: 0x1be}
		format = source
		if b.MenuSignature != "768ef24d00a8efba2ad49db6dcc90c41e83823be7ee6a3d310b387b6af1b58b4" || b.Color != nil {
			return false
		}
	} else if b.Color == nil || *b.Color != s.color {
		return false
	}
	if b.Key == "startup.quiz-enter" {
		caller = oracle.Addr{Seg: 0x266d, Off: 0x11f}
	}
	if b.Caller != caller || b.FormatSHA256 != digest([]byte(format)) {
		return false
	}
	if s.upper != (oracle.Addr{}) {
		return b.UpperFormatSHA256 == digest([]byte(source))
	}
	return b.UpperFormatSHA256 == ""
}
func (g *liveGame) coldPromptsReceipt(result map[string]any) {
	u := g.cold.ui
	if u == nil {
		return
	}
	if len(u.Fills) > 0 || len(u.Await) > 0 || u.Wrapper != nil || len(u.Words) > 0 || len(u.Pending) > 0 || len(u.ClearPages) > 0 {
		panic("冷讀提示呈現未完成")
	}
	files := map[string]string{}
	for _, name := range []string{"bindings.json", "en.tsv", "zh-TW.tsv", "glyphs-16.json", "provenance.json"} {
		raw, e := os.ReadFile(filepath.Join(u.Path, name))
		must(e)
		files[name] = digest(raw)
	}
	result["cold_ui"] = map[string]any{"input_root": u.Path, "files": files, "events": u.Events}
}

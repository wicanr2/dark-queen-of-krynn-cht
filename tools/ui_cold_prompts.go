// DRAFT：MZ 冷讀期間的原版底列提示。只改呈現，字模與角色管理分開保存。
package main

import (
	"encoding/hex"
	"encoding/json"
	"os"
	"path/filepath"
	"sort"

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
	Bindings []coldPromptBinding
	Menus    map[string]string
}
type coldPromptFill struct {
	Return   paintReturn
	Entry    uint64
	Affected bool
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
	for _, f := range u.Fills {
		if f.Affected {
			return true
		}
	}
	return false
}
func (g *liveGame) installColdPrompts(path string) {
	u := &coldPromptUI{Path: path, Words: map[[2]int]listWord{}, Catalog: readLiveCatalog(filepath.Join(path, "zh-TW.tsv")), Sources: readLiveCatalog(filepath.Join(path, "en.tsv"))}
	raw, e := os.ReadFile(filepath.Join(path, "bindings.json"))
	must(e)
	must(json.Unmarshal(raw, &u.Config))
	raw, e = os.ReadFile(filepath.Join(path, "glyphs-16.json"))
	must(e)
	must(json.Unmarshal(raw, &u.Glyphs))
	if u.Glyphs.Size != 16 || u.Glyphs.Height != 20 || len(u.Config.Bindings) != 6 || len(u.Catalog) != 6 || len(u.Sources) != 6 {
		panic("冷讀提示輸入不符")
	}
	for _, b := range u.Config.Bindings {
		source, ok := u.Sources[b.Key]
		if !ok || digest([]byte(source)) != b.SourceSHA256 || u.Catalog[b.Key] == "" || len(source)*8 != b.Width || len([]rune(u.Catalog[b.Key]))*8 > b.Width ||
			b.X < 0 || b.Y != 189 || b.X+b.Width > 312 || b.Background > 15 ||
			(b.Button && (b.Caller != (oracle.Addr{Seg: 0xceb, Off: 0x1be}) || u.Config.Menus[b.MenuSignature] == "")) ||
			(!b.Button && (b.Caller != (oracle.Addr{Seg: 0xb72, Off: 0x27c}) || b.UpperCaller == (oracle.Addr{}))) {
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
	active := func() bool { return !g.cold.ready }
	o := g.o
	returns := map[oracle.Addr]bool{}
	o.OnCall(oracle.Addr{Seg: 0xb72, Off: 0x46}, func(_ *oracle.Oracle) {
		if !active() {
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
			if !b.Button {
				if u.Wrapper == nil || u.Wrapper.Caller != b.UpperCaller || digest([]byte(u.Wrapper.Source)) != b.UpperFormatSHA256 {
					continue
				}
			}
			word := listWord{X: b.X, Y: b.Y, Width: b.Width, Key: b.Key, Group: b.Group, Foreground: byte(o.StackWord(4)) & 15, Background: b.Background, Button: b.Button}
			u.erase(word.X, word.Y, word.Width, 8)
			u.Words[[2]int{word.X, word.Y}] = word
			index := g.coldPromptLog("word-before-glyph", map[string]any{"key": b.Key, "source_sha256": b.SourceSHA256, "format_sha256": b.FormatSHA256, "caller": o.Caller(), "word": word})
			u.Await = append(u.Await, index)
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
	o.OnCall(oracle.Addr{Seg: 0x13c7, Off: 0x78}, func(_ *oracle.Oracle) {
		if !active() {
			return
		}
		r := o.Regs()
		u.Fills = append(u.Fills, coldPromptFill{Return: paintReturn{SS: r.SS, SP: r.SP}, Entry: o.Steps()})
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
	o.OnCall(oracle.Addr{Seg: 0x13c7, Off: 0x6db}, func(_ *oracle.Oracle) {
		if !active() {
			return
		}
		if len(u.Fills) == 0 {
			panic("冷讀填色返回未配對")
		}
		f := u.Fills[len(u.Fills)-1]
		r := o.Regs()
		if f.Return.SS != r.SS || f.Return.SP != r.SP {
			panic("冷讀填色堆疊不符")
		}
		u.Fills = u.Fills[:len(u.Fills)-1]
		if f.Affected {
			g.coldPromptLog("native-clear-return", map[string]any{"entry_step": f.Entry})
		}
	})
}
func (g *liveGame) coldPromptsReceipt(result map[string]any) {
	u := g.cold.ui
	if u == nil {
		return
	}
	if len(u.Fills) > 0 || len(u.Await) > 0 || u.Wrapper != nil || len(u.Words) > 0 {
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

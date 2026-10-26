// 完整短字串的來源命令。只處理正式譯文、已量測字模與原生八像素高的單行。
package main

import (
	"bytes"
	"path/filepath"
	"sort"
	"strings"

	"github.com/wicanr2/dosgolem/oracle"
)

type ownedPrint struct {
	Return       paintReturn
	Source       string
	Word         listWord
	Color        uint16
	Next         int
	Valid        bool
	Reference    []byte
	Page         uint32
	Format       *displayFormat
	Printed      []byte
	Text         string
	Layout       displayTextLayout
	LastX, LastY int
}

type playerTextOwner struct {
	Oracle        *oracle.Oracle
	Sources       map[string]string
	Catalog       map[string]string
	Glyphs        glyphSet
	Runs          []*ownedPrint
	Words         []*ownedPrint
	FormatText    string
	Formats       map[string]*displayFormat
	FormatOrder   []*displayFormat
	FoldedSources map[string]string
	Counters      map[string]uint64
}

func loadPlayerTextOwner(o *oracle.Oracle, profile string, glyphPoint oracle.Addr) *playerTextOwner {
	p := &playerTextOwner{Oracle: o, Sources: map[string]string{}, Catalog: readLiveCatalog(filepath.Join(profile, "display.zh-TW.tsv"))}
	p.Formats = map[string]*displayFormat{}
	p.Counters = map[string]uint64{}
	formatTargets := readLiveCatalog(filepath.Join(profile, "display-format.zh-TW.tsv"))
	for key, source := range readLiveCatalog(filepath.Join(profile, "display-format.en.tsv")) {
		compiled, err := compileDisplayFormat(key, source, formatTargets[key])
		must(err)
		if p.Formats[source] != nil {
			panic("重複格式來源")
		}
		p.Formats[source] = &compiled
		p.FormatOrder = append(p.FormatOrder, &compiled)
		p.Catalog[key] = formatTargets[key]
	}
	sort.Slice(p.FormatOrder, func(i, j int) bool {
		a, b := p.FormatOrder[i], p.FormatOrder[j]
		if a.LiteralBytes != b.LiteralBytes {
			return a.LiteralBytes > b.LiteralBytes
		}
		return a.Key < b.Key
	})
	for key, source := range readLiveCatalog(filepath.Join(profile, "display-source.en.tsv")) {
		if p.Sources[source] != "" || p.Catalog[key] == "" || len(source) < 2 || len(source) > 128 || strings.Contains(source, "%") {
			panic("短字串來源不符")
		}
		p.Sources[source] = key
	}
	p.FoldedSources = map[string]string{}
	for source, key := range p.Sources {
		fold, text := strings.ToLower(source), p.Catalog[key]
		if previous, exists := p.FoldedSources[fold]; exists && previous != text {
			p.FoldedSources[fold] = ""
		} else if !exists {
			p.FoldedSources[fold] = text
		}
	}
	loadPlayerJSON(filepath.Join(profile, "display-glyphs-16.json"), &p.Glyphs)
	if p.Glyphs.Size != 16 || p.Glyphs.Height != 20 {
		panic("短字串字型尺寸不符")
	}
	for _, text := range p.Catalog {
		for _, ch := range text {
			glyph := p.Glyphs.Glyphs[string(ch)]
			if len(glyph) != 320 {
				panic("短字串缺字")
			}
			for _, alpha := range glyph[256:] {
				if alpha != 0 {
					panic("短字串字墨超出八列原生像素")
				}
			}
		}
	}
	p.FormatText = readLiveCatalog(filepath.Join(profile, "en.tsv"))["format.string"]
	returns := map[oracle.Addr]bool{}
	o.OnCall(oracle.Addr{Seg: 0x1212, Off: 0x03a0}, func(_ *oracle.Oracle) {
		if len(p.Runs) >= 256 {
			panic("短字串交易超過有界容量")
		}
		r := o.Regs()
		target := o.Caller()
		run := &ownedPrint{Return: paintReturn{target, r.SS, r.SP + 4}, Color: o.StackWord(4)}
		source, ok := listString(o, o.StackWord(6), o.StackWord(5))
		if ok && source == p.FormatText {
			source, ok = listString(o, o.StackWord(8), o.StackWord(7))
		}
		if ok && p.Sources[source] != "" {
			run.Source, run.Valid = source, true
			run.Word.Key = p.Sources[source]
		} else if ok && p.Formats[source] != nil {
			run.Source, run.Valid, run.Format = source, true, p.Formats[source]
			run.Word.Key = run.Format.Key
		} else if ok && len(source) <= 80 {
			for _, format := range p.FormatOrder {
				if text, matched := format.Render(source, p.translateValue); matched && len([]rune(text)) <= len(source) {
					run.Source, run.Valid, run.Text = source, true, text
					run.Word.Key = format.Key
					break
				}
			}
		}
		p.Runs = append(p.Runs, run)
		if returns[target] {
			return
		}
		returns[target] = true
		o.OnCall(target, func(_ *oracle.Oracle) {
			r := o.Regs()
			for i := len(p.Runs) - 1; i >= 0; i-- {
				run := p.Runs[i]
				if run.Return.Addr == target && run.Return.SS == r.SS && run.Return.SP == r.SP {
					p.finish(run)
					p.Runs = append(p.Runs[:i], p.Runs[i+1:]...)
					return
				}
			}
		})
	})
	o.OnCall(glyphPoint, func(_ *oracle.Oracle) { p.glyph() })
	return p
}

func (p *playerTextOwner) glyph() {
	if len(p.Runs) == 0 {
		return
	}
	run := p.Runs[len(p.Runs)-1]
	if !run.Valid {
		return
	}
	o, r := p.Oracle, p.Oracle.Regs()
	word := func(off uint16) uint16 { return o.Word(oracle.Addr{Seg: r.SS, Off: r.BP + off}) }
	x, y, ch := int(int16(word(8))), int(int16(word(6))), byte(word(10))
	page, known := nativeRenderPage(o)
	if !known || run.Next >= 128 || ch < 32 || ch > 126 || word(12) != run.Color ||
		(run.Format == nil && (run.Next >= len(run.Source) || ch != run.Source[run.Next])) ||
		(run.Next > 0 && page != run.Page) {
		run.Valid = false
		return
	}
	// 原印字器仍產生被右邊界裁掉的字元呼叫。只收完整來源，不為它建立畫布。
	if run.Next > 0 && x == 320 && y == run.LastY && (run.LastX == 312 || run.LastX == 320) {
		if run.Format != nil {
			run.Printed = append(run.Printed, ch)
		}
		run.LastX, run.LastY = x, y
		run.Next++
		return
	}
	initial := 8
	if run.Next == 0 {
		text := run.Text
		if text == "" {
			text = p.Catalog[run.Word.Key]
		}
		if run.Format == nil {
			initial = max(len(run.Source)*8, len([]rune(text))*8)
			if initial > 320-x {
				initial = 8
			}
		}
		if x < 0 || y < 0 || x+initial > 320 || y+8 > 200 {
			run.Valid = false
			return
		}
		run.Word.X, run.Word.Y, run.Word.Width = x, y, initial
		run.Page = page
		before := nativeTextRegion(o, page, run.Word)
		if len(before) == 0 {
			run.Valid = false
			return
		}
		for _, v := range before {
			if v != before[0] {
				run.Valid = false
				return
			}
		}
		run.Word.Background = before[0]
		run.Word.Foreground = byte(run.Color & 15)
	}
	if !run.Layout.Add(x, y, initial) {
		run.Valid = false
		return
	}
	before := nativeTextRegion(o, page, listWord{X: x, Y: y, Width: 8})
	for _, v := range before {
		if v != run.Word.Background {
			run.Valid = false
			return
		}
	}
	if run.Format != nil {
		run.Printed = append(run.Printed, ch)
	}
	run.Next++
	run.LastX, run.LastY = x, y
}

func (p *playerTextOwner) finish(run *ownedPrint) {
	if !run.Valid || run.Next == 0 || (run.Format == nil && run.Next != len(run.Source)) {
		return
	}
	if run.Text == "" {
		run.Text = p.Catalog[run.Word.Key]
	}
	if run.Format != nil {
		text, ok := run.Format.Render(string(run.Printed), p.translateValue)
		if !ok {
			return
		}
		run.Text = text
	}
	for _, ch := range run.Text {
		if len(p.Glyphs.Glyphs[string(ch)]) != 320 {
			return
		}
	}
	texts, ok := run.Layout.Pack(run.Text)
	if !ok {
		return
	}
	pending := []*ownedPrint{}
	ink := false
	for i, row := range run.Layout.Rows {
		child := &ownedPrint{Word: run.Word, Page: run.Page, Source: run.Source, Text: texts[i]}
		child.Word.X, child.Word.Y, child.Word.Width = row.X, row.Y, row.Width
		child.Reference = nativeTextRegion(p.Oracle, run.Page, child.Word)
		if len(child.Reference) == 0 {
			return
		}
		for _, v := range child.Reference {
			if v == child.Word.Background {
				continue
			}
			if v != child.Word.Foreground {
				return
			}
			ink = true
		}
		pending = append(pending, child)
	}
	if !ink {
		return
	}
	p.Counters["complete_runs"]++
	p.Counters["key:"+run.Word.Key]++
	if run.Format != nil {
		p.Counters["native_format_runs"]++
	}
	if len(run.Layout.Rows) > 1 {
		p.Counters["multiline_runs"]++
	}
	p.prune()
	for _, child := range pending {
		replaced := false
		for i, previous := range p.Words {
			if previous.Page == child.Page && previous.Word.X == child.Word.X && previous.Word.Y == child.Word.Y {
				p.Words[i] = child
				replaced = true
				break
			}
		}
		if !replaced {
			if len(p.Words) >= 512 {
				p.Words = p.Words[1:]
			}
			p.Words = append(p.Words, child)
		}
	}
}

func (p *playerTextOwner) translateValue(value string) string {
	return translateDisplayValue(value, func(source string) string {
		if key := p.Sources[source]; key != "" {
			return p.Catalog[key]
		}
		return p.FoldedSources[strings.ToLower(source)]
	})
}

func (p *playerTextOwner) prune() {
	kept := p.Words[:0]
	for _, run := range p.Words {
		if bytes.Equal(run.Reference, nativeTextRegion(p.Oracle, run.Page, run.Word)) {
			kept = append(kept, run)
		}
	}
	p.Words = kept
}

func (p *playerTextOwner) Compose(px []byte, g *liveGame, rgb []byte) {
	// 完整畫格的 Source 已按相同色號視圖整理一次，合成期間沒有客體執行。
	page, ok := nativeVisiblePage(p.Oracle)
	if !ok {
		return
	}
	protected := g.playerProtectedRectangles()
	for _, run := range p.Words {
		if run.Page != page {
			continue
		}
		w, covered := run.Word, false
		for _, r := range protected {
			if w.X < r[2] && w.X+w.Width > r[0] && w.Y < r[3] && w.Y+8 > r[1] {
				covered = true
				break
			}
		}
		if !covered {
			g.composeWords(px, []listWord{w}, map[string]string{w.Key: run.Text}, p.Glyphs)
		}
	}
}

func (p *playerTextOwner) Rectangles() [][4]int {
	result := make([][4]int, 0, len(p.Words))
	page, ok := nativeVisiblePage(p.Oracle)
	if !ok {
		return result
	}
	for _, run := range p.Words {
		if run.Page != page {
			continue
		}
		w := run.Word
		r := [4]int{w.X, w.Y, w.X + w.Width, w.Y + 8}
		if owner := renderOwners[p.Oracle]; owner != nil && owner.CanTranslate(r) {
			result = append(result, r)
		}
	}
	return result
}

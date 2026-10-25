// 完整短字串的來源命令。只處理正式譯文、已量測字模與原生八像素高的單行。
package main

import (
	"bytes"
	"path/filepath"
	"strings"

	"github.com/wicanr2/dosgolem/oracle"
)

type ownedPrint struct {
	Return    paintReturn
	Source    string
	Word      listWord
	Color     uint16
	Next      int
	Valid     bool
	Reference []byte
	Page      uint32
}

type playerTextOwner struct {
	Oracle     *oracle.Oracle
	Sources    map[string]string
	Catalog    map[string]string
	Glyphs     glyphSet
	Runs       []*ownedPrint
	Words      []*ownedPrint
	FormatText string
}

func loadPlayerTextOwner(o *oracle.Oracle, profile string, glyphPoint oracle.Addr) *playerTextOwner {
	p := &playerTextOwner{Oracle: o, Sources: map[string]string{}, Catalog: readLiveCatalog(filepath.Join(profile, "display.zh-TW.tsv"))}
	for key, source := range readLiveCatalog(filepath.Join(profile, "display-source.en.tsv")) {
		if p.Sources[source] != "" || p.Catalog[key] == "" || len(source) < 2 || len(source) > 80 || strings.Contains(source, "%") {
			panic("短字串來源不符")
		}
		p.Sources[source] = key
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
	word := func(offset uint16) uint16 { return o.Word(oracle.Addr{Seg: r.SS, Off: r.BP + offset}) }
	x, y, ch := int(int16(word(8))), int(int16(word(6))), byte(word(10))
	page, pageKnown := nativeRenderPage(o)
	if !pageKnown || run.Next >= len(run.Source) || ch != run.Source[run.Next] || word(12) != run.Color || (run.Next > 0 && page != run.Page) {
		run.Valid = false
		return
	}
	if run.Next == 0 {
		run.Word.X, run.Word.Y, run.Word.Width = x, y, len(run.Source)*8
		if translated := len([]rune(p.Catalog[run.Word.Key])) * 8; translated > run.Word.Width {
			run.Word.Width = translated
		}
		if x < 0 || y < 0 || x+run.Word.Width > 320 || y+8 > 200 {
			run.Valid = false
			return
		}
		run.Page = page
		before := nativeTextRegion(o, page, run.Word)
		if len(before) == 0 {
			run.Valid = false
			return
		}
		for _, index := range before {
			if index != before[0] {
				run.Valid = false
				return
			}
		}
		run.Word.Background = before[0]
		run.Word.Foreground = byte(run.Color & 15)
	}
	if y != run.Word.Y || x != run.Word.X+run.Next*8 {
		run.Valid = false
		return
	}
	run.Next++
}

func (p *playerTextOwner) finish(run *ownedPrint) {
	if !run.Valid || run.Next != len(run.Source) {
		return
	}
	reference := nativeTextRegion(p.Oracle, run.Page, run.Word)
	if len(reference) == 0 {
		return
	}
	bg, fg := run.Word.Background, run.Word.Foreground
	ink := false
	for _, index := range reference {
		if index == bg {
			continue
		}
		if index != fg {
			return
		}
		ink = true
	}
	// 隱藏頁也保存來源，但只在該頁成為可見頁後合成。
	if !ink {
		return
	}
	run.Reference = reference
	p.prune()
	for i, previous := range p.Words {
		if previous.Page == run.Page && previous.Word.X == run.Word.X && previous.Word.Y == run.Word.Y {
			p.Words[i] = run
			return
		}
	}
	if len(p.Words) >= 512 {
		p.Words = p.Words[1:]
	}
	p.Words = append(p.Words, run)
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
	p.prune()
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
			g.composeWords(px, []listWord{w}, p.Catalog, p.Glyphs)
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

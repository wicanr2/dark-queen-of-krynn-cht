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
		if p.Sources[source] != "" || p.Catalog[key] == "" || len(source) < 2 || len(source) > 80 || strings.Contains(source, "%") ||
			len([]rune(p.Catalog[key])) > len(source) {
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

func textRegion(rgb []byte, w listWord) []byte {
	region := make([]byte, 0, w.Width*8*3)
	for y := w.Y; y < w.Y+8; y++ {
		i := (y*320 + w.X) * 3
		region = append(region, rgb[i:i+w.Width*3]...)
	}
	return region
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
	if run.Next >= len(run.Source) || ch != run.Source[run.Next] || word(12) != run.Color {
		run.Valid = false
		return
	}
	if run.Next == 0 {
		run.Word.X, run.Word.Y, run.Word.Width = x, y, len(run.Source)*8
		if x < 0 || y < 0 || x+run.Word.Width > 320 || y+8 > 200 {
			run.Valid = false
			return
		}
		_, _, rgb := o.ScreenRGB()
		before := textRegion(rgb, run.Word)
		for i := 3; i < len(before); i += 3 {
			if !bytes.Equal(before[:3], before[i:i+3]) {
				run.Valid = false
				return
			}
		}
		found := false
		for index, color := range o.Palette() {
			if bytes.Equal(before[:3], color[:]) {
				run.Word.Background, found = byte(index), true
				break
			}
		}
		if !found {
			run.Valid = false
			return
		}
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
	_, _, rgb := p.Oracle.ScreenRGB()
	reference := textRegion(rgb, run.Word)
	palette := p.Oracle.Palette()
	bg, fg := palette[run.Word.Background], palette[run.Word.Foreground]
	ink := false
	for i := 0; i < len(reference); i += 3 {
		if bytes.Equal(reference[i:i+3], bg[:]) {
			continue
		}
		if !bytes.Equal(reference[i:i+3], fg[:]) {
			return
		}
		ink = true
	}
	// 未顯示的後頁仍是空白底色，不提前把該頁的中文放進目前畫面。
	if !ink {
		return
	}
	run.Reference = reference
	p.prune(rgb)
	for i, previous := range p.Words {
		if previous.Word.X == run.Word.X && previous.Word.Y == run.Word.Y {
			p.Words[i] = run
			return
		}
	}
	if len(p.Words) >= 512 {
		p.Words = p.Words[1:]
	}
	p.Words = append(p.Words, run)
}

func (p *playerTextOwner) prune(rgb []byte) {
	kept := p.Words[:0]
	for _, run := range p.Words {
		if bytes.Equal(run.Reference, textRegion(rgb, run.Word)) {
			kept = append(kept, run)
		}
	}
	p.Words = kept
}

func (p *playerTextOwner) Compose(px []byte, g *liveGame, rgb []byte) {
	p.prune(rgb)
	protected := g.playerProtectedRectangles()
	for _, run := range p.Words {
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
	for _, run := range p.Words {
		w := run.Word
		result = append(result, [4]int{w.X, w.Y, w.X + w.Width, w.Y + 8})
	}
	return result
}

// DRAFT：完整來源先辨識，實際片段依序返回後才提交整句。
package main

import "github.com/wicanr2/dosgolem/oracle"

type livePassage struct {
	Binding                *passageSourceBinding
	Part                   int
	Printing               bool
	Paint                  paintReturn
	Box                    [4]int
	Foreground, Background byte
	ScriptSegment, Base    uint16
}

func (g *liveGame) cancelPassage(reason string) {
	if p := g.list.passage; p != nil {
		g.list.passage = nil
		g.page = nil
		g.listLog("passage-original", map[string]any{"key": p.Binding.Key, "part": p.Part, "reason": reason})
	}
}

func (g *liveGame) installPassages() {
	if len(g.list.config.PassageGroups) == 0 {
		return
	}
	for _, b := range g.list.config.PassageGroups {
		source, text := g.list.sources[b.Key], g.catalog[b.Key]
		limit := 144
		if b.LeadingContinuation {
			limit = 128
		}
		if b.Key != "passage."+digest([]byte(source))[:20] || source == "" || text == "" ||
			len([]rune(text)) > limit || len(b.Fragments) < 2 || len(b.Fragments) > 32 {
			panic("整句目錄或字數不符")
		}
	}
	for _, off := range []uint16{0x1d81, 0x1d53} {
		at := oracle.Addr{Seg: 0x26b4, Off: off}
		g.o.OnCall(at, func(_ *oracle.Oracle) {
			p, r := g.list.passage, g.o.Regs()
			if p == nil || !p.Printing || p.Paint.Addr != at || p.Paint.SS != r.SS || p.Paint.SP != r.SP {
				return
			}
			p.Printing = false
			g.listLog("passage-part-return", map[string]any{"key": p.Binding.Key, "part": p.Part})
			if p.Part == len(p.Binding.Fragments)-1 {
				g.listLog("passage-complete", map[string]any{"key": p.Binding.Key, "parts": len(p.Binding.Fragments)})
				g.list.passage = nil
			}
		})
	}
}

func (g *liveGame) passageProgress() {
	p := g.list.passage
	if p == nil || p.Printing {
		return
	}
	o := g.o
	seg := o.Word(oracle.Addr{Seg: 0x333e, Off: 0xae5e})
	base := o.Word(oracle.Addr{Seg: 0x333e, Off: 0xae5c})
	position := int(uint16(uint32(base) + uint32(o.Word(oracle.Addr{Seg: 0x333e, Off: 0xb7f9}))))
	if seg != p.ScriptSegment || base != p.Base || position < p.Binding.Fragments[p.Part].End || position > p.Binding.EndChunkOffset {
		g.cancelPassage("script left source group")
	}
}

func (g *liveGame) passageFill(x, y, w, h int, scroll bool) {
	p := g.list.passage
	if p == nil || x >= p.Box[2] || x+w <= p.Box[0] || y >= p.Box[3] || y+h <= p.Box[1] {
		return
	}
	if scroll || !p.Printing {
		g.cancelPassage("native clear or scroll")
	}
}

// handled=true 且 binding=nil 表示接續片段已辨識，不能再當成孤立句子顯示。
func (g *liveGame) passageParagraph(ptr, caller oracle.Addr, box [4]int, fg, bg, clear byte, source string) (*listParagraph, string, bool) {
	l, o := g.list, g.o
	if len(l.config.PassageGroups) == 0 {
		return nil, source, false
	}
	context := box == ([4]int{8, 136, 312, 184}) && fg <= 15 && bg == 0 && clear <= 1
	if !context {
		g.cancelPassage("paragraph context changed")
		return nil, source, false
	}
	if _, literal := shortECLLiteralSource(o, ptr, caller); !literal {
		g.cancelPassage("nonliteral source")
		return nil, source, false
	}
	base := oracle.Addr{Seg: o.Word(oracle.Addr{Seg: 0x333e, Off: 0xae5e}), Off: o.Word(oracle.Addr{Seg: 0x333e, Off: 0xae5c})}
	r := o.Regs()
	view := passageSourceObservation{DS: r.DS, PointerSeg: ptr.Seg, PointerOff: ptr.Off, CallerSeg: caller.Seg, CallerOff: caller.Off,
		RawBaseOffset: base.Off, RawCursorAfter: o.Word(oracle.Addr{Seg: 0x333e, Off: 0xb7f9}),
		Kind: o.Byte(oracle.Addr{Seg: 0x333e, Off: 0xb216}), Opcode: o.Byte(oracle.Addr{Seg: 0x333e, Off: 0xb1c7}), Clear: clear, Source: source}
	match := func(b *passageSourceBinding, part int) (passageSourceCandidate, bool) {
		if part >= len(b.Fragments) || b.ChunkBytes <= 0 || b.ChunkBytes > 0x8000 ||
			uint32(base.Seg)*16+uint32(b.ChunkBytes) > 0xa0000 ||
			int(uint16(uint32(base.Off)+uint32(view.RawCursorAfter))) != b.Fragments[part].End {
			return passageSourceCandidate{}, false
		}
		view.Script = o.Bytes(oracle.Addr{Seg: base.Seg}, b.ChunkBytes)
		return matchPassageSource(*b, l.sources, part, view)
	}
	logPart := func(p *livePassage) {
		l.awaitGlyphs = append(l.awaitGlyphs, g.listLog("passage-part-before-glyph", map[string]any{
			"key": p.Binding.Key, "part": p.Part, "source_sha256": digest([]byte(source)),
			"packet_sha256": p.Binding.PacketSHA256, "caller": caller}))
	}
	if p := l.passage; p != nil {
		if !p.Printing && p.Foreground == fg && p.Background == bg && p.Box == box && p.ScriptSegment == base.Seg && p.Base == base.Off {
			if _, ok := match(p.Binding, p.Part+1); ok {
				p.Part++
				p.Printing, p.Paint = true, paintReturn{caller, r.SS, r.SP + 4}
				logPart(p)
				return nil, source, true
			}
		}
		g.cancelPassage("unexpected source part")
	}
	for i := range l.config.PassageGroups {
		b := &l.config.PassageGroups[i]
		if b.LeadingContinuation && (g.page == nil || g.page.Box != ([4]int{16, 272, 624, 368}) || g.page.Background != 8) {
			continue
		}
		candidate, ok := match(b, 0)
		if !ok {
			continue
		}
		p := &livePassage{Binding: b, Printing: true, Paint: paintReturn{caller, r.SS, r.SP + 4}, Box: box,
			Foreground: fg, Background: bg, ScriptSegment: base.Seg, Base: base.Off}
		l.passage = p
		logPart(p)
		g.listLog("passage-start", map[string]any{"key": b.Key, "parts": len(b.Fragments), "continuation": b.LeadingContinuation})
		return &listParagraph{Key: b.Key, SHA256: digest([]byte(candidate.Source)), Caller: caller, NativeBox: box,
			Foreground: fg, Background: bg, Clear: clear}, candidate.Source, true
	}
	return nil, source, false
}

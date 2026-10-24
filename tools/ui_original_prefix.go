// DRAFT：保留已見證的原版動態前綴，讓後續譯文沿既有段落接續。
package main

import "github.com/wicanr2/dosgolem/oracle"

type originalPrefixBinding struct {
	ChunkSHA256, PacketSHA256 string
	ChunkBytes, Offset, End   int
}

type originalPrefix struct {
	Key, Text string
	paint     paintReturn
	rgb       []byte
}

func matchOriginalPrefix(b originalPrefixBinding, v passageSourceObservation) bool {
	if v.DS != 0x333e || v.PointerSeg != 0x333e || v.PointerOff != 0xb487 ||
		v.CallerSeg != 0x26b4 || v.CallerOff != 0x1d81 || v.Kind != 0x81 || v.Opcode != 0x12 || v.Clear != 1 ||
		len(v.Source) < 1 || len(v.Source) > 15 || b.ChunkBytes <= 0 || b.ChunkBytes > 0x8000 ||
		len(v.Script) < b.ChunkBytes || b.Offset < 0 || b.End <= b.Offset+2 || b.End > b.ChunkBytes ||
		int(uint16(uint32(v.RawBaseOffset)+uint32(v.RawCursorAfter))) != b.End {
		return false
	}
	for _, c := range []byte(v.Source) {
		if c < 32 || c > 126 {
			return false
		}
	}
	block := v.Script[:b.ChunkBytes]
	return block[b.Offset] == 0x12 && block[b.Offset+1] == 0x81 &&
		passageSourceHash(block) == b.ChunkSHA256 && passageSourceHash(block[b.Offset:b.End]) == b.PacketSHA256
}

func (g *liveGame) originalPrefixParagraph(ptr, caller oracle.Addr, box [4]int, fg, bg, clear byte, source string) *listParagraph {
	if len(g.list.config.OriginalPrefixes) == 0 || box != ([4]int{8, 136, 312, 184}) || fg != 7 || bg != 0 || clear != 1 {
		return nil
	}
	o := g.o
	if digest(o.Bytes(oracle.Addr{Seg: 0x26b4, Off: 0x1cd3}, 0xba)) != "c61ccaba966f4c04eea49304ea633c61c02566cd8ca8e93105412d50e7f239c9" ||
		digest(o.Bytes(oracle.Addr{Seg: 0x2143, Off: 0x13}, 0xff)) != "c6f1c1c8cb204e32aa000a8ca180da3a23431f5d2a0e799cf4e65792269ef6ff" {
		return nil
	}
	r := o.Regs()
	base := oracle.Addr{Seg: o.Word(oracle.Addr{Seg: 0x333e, Off: 0xae5e}), Off: o.Word(oracle.Addr{Seg: 0x333e, Off: 0xae5c})}
	for _, b := range g.list.config.OriginalPrefixes {
		if b.ChunkBytes <= 0 || b.ChunkBytes > 0x8000 || uint32(base.Seg)*16+uint32(b.ChunkBytes) > 0xa0000 {
			continue
		}
		v := passageSourceObservation{DS: r.DS, PointerSeg: ptr.Seg, PointerOff: ptr.Off, CallerSeg: caller.Seg, CallerOff: caller.Off,
			RawBaseOffset: base.Off, RawCursorAfter: o.Word(oracle.Addr{Seg: 0x333e, Off: 0xb7f9}),
			Kind: o.Byte(oracle.Addr{Seg: 0x333e, Off: 0xb216}), Opcode: o.Byte(oracle.Addr{Seg: 0x333e, Off: 0xb1c7}),
			Clear: clear, Script: o.Bytes(oracle.Addr{Seg: base.Seg}, b.ChunkBytes), Source: source}
		if matchOriginalPrefix(b, v) {
			key := "original-prefix." + b.PacketSHA256[:20]
			return &listParagraph{Key: key, SHA256: digest([]byte(source)), Caller: caller, NativeBox: box,
				Foreground: fg, Background: bg, Clear: clear,
				prefix: &originalPrefix{Key: key, Text: source, paint: paintReturn{caller, r.SS, r.SP + 4}}}
		}
	}
	return nil
}

func (g *liveGame) captureOriginalPrefix(p paintReturn) {
	if g.page == nil || g.page.Prefix == nil || g.page.Prefix.paint != p || len(g.page.Prefix.rgb) != 0 {
		return
	}
	prefix := g.page.Prefix
	w, h, rgb := g.o.ScreenRGB()
	if w != 320 || h != 200 {
		panic("原版前綴畫面尺寸不符")
	}
	width := len(prefix.Text) * 8
	for y := 136; y < 144; y++ {
		at := (y*320 + 8) * 3
		prefix.rgb = append(prefix.rgb, rgb[at:at+width*3]...)
	}
	g.listLog("original-prefix-return", map[string]any{"key": prefix.Key, "source_sha256": digest([]byte(prefix.Text)), "rgb_sha256": digest(prefix.rgb), "native_rect": [4]int{8, 136, width, 8}})
}

func drawOriginalPrefix(px []byte, p *storyPage) {
	if p.Prefix == nil || len(p.Prefix.rgb) == 0 {
		return
	}
	width := len(p.Prefix.Text) * 8
	for y := 0; y < 16; y++ {
		for x := 0; x < width*2; x++ {
			s := ((y/2)*width + x/2) * 3
			d := ((p.Box[1]+y)*640 + p.Box[0] + x) * 4
			copy(px[d:d+3], p.Prefix.rgb[s:s+3])
		}
	}
}

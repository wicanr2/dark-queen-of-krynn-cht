// DRAFT：完整段落與列表共用呈現層；來源、規則與原版逐字輸出保持原樣。
package main

import (
	"encoding/hex"
	"strings"

	"github.com/wicanr2/dosgolem/oracle"
)

type listParagraph struct {
	Key, SHA256                   string
	Caller                        oracle.Addr
	NativeBox                     [4]int
	Foreground, Background, Clear byte
}

func (g *liveGame) invalidateListParagraph(x, y, width, height int, reason string) {
	if g.page == nil || len(g.list.paragraphPaints) > 0 {
		return
	}
	b := g.page.Box
	if x*2 < b[2] && (x+width)*2 > b[0] && y*2 < b[3] && (y+height)*2 > b[1] {
		g.page = nil
		g.listLog("paragraph-invalidated", map[string]any{"native_rect": [4]int{x, y, width, height}, "reason": reason})
	}
}

func (g *liveGame) installListParagraphs() {
	l, o := g.list, g.o
	if len(l.config.Paragraphs) == 0 {
		return
	}
	for _, p := range l.config.Paragraphs {
		source := l.sources[p.Key]
		suffix := digest([]byte(source))[:20]
		literal := p.Key == "ecl."+suffix
		message := p.Key == "message."+suffix && p.Caller == (oracle.Addr{Seg: 0x26b4, Off: 0x3320}) && p.Foreground == 7 && p.Clear == 1
		if source == "" || !(literal || message) || p.SHA256 != digest([]byte(source)) ||
			g.catalog[p.Key] == "" || p.NativeBox != ([4]int{8, 136, 312, 184}) || p.Foreground > 15 || p.Background != 0 || p.Clear > 1 {
			panic("段落來源或安全框不符")
		}
	}
	anchor := oracle.Addr{Seg: 0xb72, Off: 0x311}
	if hex.EncodeToString(o.Bytes(anchor, 8)) != "558bec83ec025657" {
		panic("段落入口 bytes 不符")
	}
	registered := map[oracle.Addr]bool{}
	o.OnCall(anchor, func(_ *oracle.Oracle) {
		caller := o.Caller()
		box := [4]int{int(byte(o.StackWord(2))) * 8, int(byte(o.StackWord(3))) * 8, (int(byte(o.StackWord(4))) + 1) * 8, (int(byte(o.StackWord(5))) + 1) * 8}
		fg, bg, clear := byte(o.StackWord(6)), byte(o.StackWord(7)), byte(o.StackWord(8))
		ptr := oracle.Addr{Seg: o.StackWord(10), Off: o.StackWord(9)}
		source, ok := listString(o, ptr.Seg, ptr.Off)
		var binding *listParagraph
		if ok {
			for i := range l.config.Paragraphs {
				p := &l.config.Paragraphs[i]
				if p.Caller == caller && p.NativeBox == box && p.Foreground == fg && p.Background == bg && p.Clear == clear &&
					p.SHA256 == digest([]byte(source)) && l.sources[p.Key] == source {
					binding = p
					break
				}
			}
		}
		fallback := func(reason string) {
			g.page = nil
			g.listLog("unknown-paragraph-original", map[string]any{"caller": caller, "reason": reason})
		}
		if binding == nil {
			fallback("source or context mismatch")
			return
		}
		if bg == 0 {
			bg = 8
		}
		text := g.catalog[binding.Key]
		components := []string{binding.Key}
		componentColors := []int{int(fg)}
		outputBox := [4]int{box[0] * 2, box[1] * 2, box[2] * 2, box[3] * 2}
		if clear == 0 {
			if g.page == nil || g.page.Box != outputBox || g.page.Background != bg {
				fallback("missing compatible predecessor")
				return
			}
			text = g.page.Text + text
			components = append(append([]string{}, g.page.Components...), binding.Key)
			previousColors := append([]int{}, g.page.ComponentColors...)
			if len(previousColors) == 0 {
				for range g.page.Components {
					previousColors = append(previousColors, int(g.page.Foreground))
				}
			}
			componentColors = append(previousColors, int(fg))
		}
		cells := (outputBox[2] - outputBox[0]) / g.glyphs.Size
		chars := []rune(text)
		var lines []string
		for len(chars) > 0 {
			n := cells
			if n > len(chars) {
				n = len(chars)
			}
			if n < len(chars) && strings.ContainsRune("，。！？、；：」』）》】", chars[n]) {
				n--
			}
			if n < len(chars) && strings.ContainsRune("「『（《【", chars[n-1]) {
				n--
			}
			if n <= 0 {
				fallback("no safe line break")
				return
			}
			lines = append(lines, string(chars[:n]))
			chars = chars[n:]
		}
		if len(lines)*g.glyphs.Height > outputBox[3]-outputBox[1] {
			fallback("text overflow")
			return
		}
		page := storyPage{Step: o.Steps(), Key: binding.Key, Source: source, Text: text, Box: outputBox, Foreground: fg, Background: bg, Lines: lines, Clear: clear, Components: components}
		for _, color := range componentColors {
			if color != int(fg) {
				page.ComponentColors = componentColors
				break
			}
		}
		g.page = &page
		g.pages = append(g.pages, page)
		l.erase(box[0], box[1], box[2]-box[0], box[3]-box[1])
		r := o.Regs()
		l.paragraphPaints = append(l.paragraphPaints, paintReturn{caller, r.SS, r.SP + 4})
		l.awaitGlyphs = append(l.awaitGlyphs, g.listLog("paragraph-before-glyph", map[string]any{"page": page, "caller": caller, "source_pointer": ptr}))
		if !registered[caller] {
			registered[caller] = true
			o.OnCall(caller, func(_ *oracle.Oracle) {
				if len(l.paragraphPaints) == 0 {
					return
				}
				p, r := l.paragraphPaints[len(l.paragraphPaints)-1], o.Regs()
				if p.Addr == caller && p.SS == r.SS && p.SP == r.SP {
					l.paragraphPaints = l.paragraphPaints[:len(l.paragraphPaints)-1]
					g.listLog("paragraph-return", map[string]any{"caller": caller, "ss": r.SS, "sp": r.SP})
				}
			})
		}
	})
}

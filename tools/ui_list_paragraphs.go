// DRAFT：完整段落與列表共用呈現層；來源、規則與原版逐字輸出保持原樣。
package main

import (
	"encoding/hex"
	"strconv"
	"strings"

	"github.com/wicanr2/dosgolem/oracle"
)

type listParagraph struct {
	Key, SHA256                   string
	Caller                        oracle.Addr
	NativeBox                     [4]int
	Foreground, Background, Clear byte
	JournalEntry                  int `json:",omitempty"`
}

type serviceNotice struct {
	Entry            uint64
	Ready, Restoring bool
}

// 右側各框獨立保留；來源由同一原版段落入口取得，不從已畫出的字元猜字。
type listHUDSpan struct {
	Start, Length int
	Key           string
	Rect          [4]int
}
type listHUDParagraph struct {
	SHA256                        string
	Caller                        oracle.Addr
	NativeBox                     [4]int
	Foreground, Background, Clear byte
	Spans                         []listHUDSpan
	HideFooter                    bool `json:",omitempty"`
}
type listHUDPending struct {
	Paint      paintReturn
	Entry      uint64
	Words      []listWord
	HideFooter bool
}

func (g *liveGame) validateHUDParagraphs() {
	for _, p := range g.list.config.HUDParagraphs {
		weapon := p.Caller == (oracle.Addr{Seg: 0x088e, Off: 0x097e}) && p.NativeBox == ([4]int{184, 56, 312, 80})
		status := p.Caller == (oracle.Addr{Seg: 0x088e, Off: 0x15e1}) && p.NativeBox == ([4]int{184, 88, 312, 176})
		miss := p.Caller == (oracle.Addr{Seg: 0x22f4, Off: 0x048f}) && p.NativeBox == ([4]int{184, 104, 312, 136})
		if !(weapon || status || miss) || (p.HideFooter && !status) || len(p.SHA256) != 64 || p.Foreground != 7 || p.Background != 0 || p.Clear != 1 || len(p.Spans) == 0 {
			panic("右側段落來源不符")
		}
		for _, span := range p.Spans {
			x, y, w, h := span.Rect[0], span.Rect[1], span.Rect[2], span.Rect[3]
			if span.Start != 0 || span.Length <= 0 || g.list.sources[span.Key] == "" || len(g.list.sources[span.Key]) != span.Length ||
				g.catalog[span.Key] == "" || x != p.NativeBox[0] || y != p.NativeBox[1] || w <= 0 || h < 8 || x+w > p.NativeBox[2] || y+h > p.NativeBox[3] ||
				len([]rune(g.catalog[span.Key]))*g.glyphs.Size > w*2 {
				panic("右側段落切片或字框不符")
			}
		}
	}
}

func (g *liveGame) beginHUDParagraph(caller oracle.Addr, box [4]int, fg, bg, clear byte, ptr oracle.Addr, source string) bool {
	l, o := g.list, g.o
	for _, p := range l.config.HUDParagraphs {
		if p.Caller != caller || p.NativeBox != box || p.Foreground != fg || p.Background != bg || p.Clear != clear || p.SHA256 != digest([]byte(source)) {
			continue
		}
		var words []listWord
		for _, span := range p.Spans {
			if span.Start+span.Length > len(source) || source[span.Start:span.Start+span.Length] != l.sources[span.Key] {
				return false
			}
			x, y, w, h := span.Rect[0], span.Rect[1], span.Rect[2], span.Rect[3]
			word := listWord{X: x, Y: y, Width: w, Key: span.Key, Group: "body", Foreground: fg, Background: l.config.Background}
			if h != 8 {
				word.Height = h
			}
			words = append(words, word)
		}
		g.page = nil
		l.erase(box[0], box[1], box[2]-box[0], box[3]-box[1])
		r := o.Regs()
		paint := paintReturn{caller, r.SS, r.SP + 4}
		l.paragraphPaints = append(l.paragraphPaints, paint)
		l.hudActive = true
		l.hudPending = append(l.hudPending, listHUDPending{paint, o.Steps(), words, p.HideFooter})
		l.awaitGlyphs = append(l.awaitGlyphs, g.listLog("hud-before-glyph", map[string]any{"caller": caller, "native_box": box, "source_sha256": p.SHA256, "source_pointer": ptr, "spans": p.Spans, "words": words}))
		if l.hudReturns == nil {
			l.hudReturns = map[oracle.Addr]bool{}
		}
		if !l.hudReturns[caller] {
			l.hudReturns[caller] = true
			o.OnCall(caller, func(_ *oracle.Oracle) {
				if len(l.hudPending) == 0 {
					return
				}
				pending := l.hudPending[len(l.hudPending)-1]
				now := o.Regs()
				if pending.Paint.Addr != caller || pending.Paint.SS != now.SS || pending.Paint.SP != now.SP {
					return
				}
				if len(l.paragraphPaints) == 0 || l.paragraphPaints[len(l.paragraphPaints)-1] != pending.Paint {
					panic("右側段落返回未配對")
				}
				l.paragraphPaints = l.paragraphPaints[:len(l.paragraphPaints)-1]
				l.hudPending = l.hudPending[:len(l.hudPending)-1]
				for _, word := range pending.Words {
					l.erase(word.X, word.Y, word.Width, word.height())
					l.words[[2]int{word.X, word.Y}] = word
				}
				if pending.HideFooter {
					for at, word := range l.words {
						if word.Group == "footer" {
							delete(l.words, at)
						}
					}
					l.footerTransition = false
				}
				g.listLog("hud-return", map[string]any{"entry_step": pending.Entry, "caller": caller, "ss": now.SS, "sp": now.SP, "words": pending.Words, "footer_hidden": pending.HideFooter})
			})
		}
		return true
	}
	return false
}

// 已證實的 26B4 敘事路徑先解碼一個 ECL 運算元，再建立 B487 文字。
// 只接 80h 原位元串；1／2／3 與 81h 的查表或間接來源不套短句譯文。
// 原始定位與 IDA／正常重播證據見規格 001「短敘事來源的 DRAFT 研究」。
func shortECLLiteralSource(o *oracle.Oracle, ptr, caller oracle.Addr) (map[string]any, bool) {
	if o.Regs().DS != 0x333e || ptr != (oracle.Addr{Seg: 0x333e, Off: 0xb487}) ||
		caller.Seg != 0x26b4 || (caller.Off != 0x1d53 && caller.Off != 0x1d81) {
		return nil, false
	}
	kind := o.Byte(oracle.Addr{Seg: 0x333e, Off: 0xb216})
	opcode := o.Byte(oracle.Addr{Seg: 0x333e, Off: 0xb1c7})
	if kind != 0x80 || (caller.Off == 0x1d53 && opcode != 0x11) || (caller.Off == 0x1d81 && opcode != 0x12) {
		return nil, false
	}
	handler := digest(o.Bytes(oracle.Addr{Seg: 0x26b4, Off: 0x1cd3}, 0xba))
	operand := digest(o.Bytes(oracle.Addr{Seg: 0x2143, Off: 0x13}, 0xff))
	if handler != "c61ccaba966f4c04eea49304ea633c61c02566cd8ca8e93105412d50e7f239c9" ||
		operand != "c6f1c1c8cb204e32aa000a8ca180da3a23431f5d2a0e799cf4e65792269ef6ff" {
		return nil, false
	}
	return map[string]any{"raw_b216": kind, "raw_b1c7": opcode, "handler_sha256": handler, "operand_sha256": operand}, true
}

func (g *liveGame) invalidateListParagraph(x, y, width, height int, reason string) {
	if g.page == nil || len(g.list.paragraphPaints) > 0 {
		return
	}
	b := g.page.Box
	if x*2 < b[2] && (x+width)*2 > b[0] && y*2 < b[3] && (y+height)*2 > b[1] {
		if notice := g.list.serviceNotice; notice != nil && notice.Ready && !notice.Restoring && reason == "native fill" {
			notice.Restoring = true
			g.listLog("service-notice-restore-begin", map[string]any{"entry_step": notice.Entry, "native_rect": [4]int{x, y, width, height}})
		}
		g.page = nil
		g.listLog("paragraph-invalidated", map[string]any{"native_rect": [4]int{x, y, width, height}, "reason": reason})
	}
}

func (g *liveGame) installListParagraphs() {
	l, o := g.list, g.o
	g.validateHUDParagraphs()
	if len(l.config.Paragraphs) == 0 {
		return
	}
	for _, p := range l.config.Paragraphs {
		source := l.sources[p.Key]
		suffix := digest([]byte(source))[:20]
		literal := p.Key == "ecl."+suffix
		message := p.Key == "message."+suffix && p.Caller == (oracle.Addr{Seg: 0x26b4, Off: 0x3320}) && p.Foreground == 7 && p.Clear == 1
		service := p.Key == "service-message."+suffix && p.Caller.Seg == 0x291a &&
			(p.Caller.Off == 0x0eee || p.Caller.Off == 0x0fd0 || p.Caller.Off == 0x0c7f) &&
			p.NativeBox == ([4]int{8, 168, 312, 184}) && p.Foreground == 11 && p.Background == 0 && p.Clear == 1 && l.config.Background == 23
		formattedJournal := message &&
			digest([]byte(l.sources[journalTemplateKey]))[:20] == strings.TrimPrefix(journalTemplateKey, "ui.") &&
			strings.Count(l.sources[journalTemplateKey], "%s") == 1 &&
			strings.Replace(l.sources[journalTemplateKey], "%s", strconv.Itoa(p.JournalEntry), 1) == source
		literalJournal := literal && p.Caller == (oracle.Addr{Seg: 0x26b4, Off: 0x1d81}) && p.Foreground == 7 && p.Clear == 1 &&
			strings.HasSuffix(source, " AS JOURNAL ENTRY "+strconv.Itoa(p.JournalEntry)+".")
		if p.JournalEntry != 0 && (p.JournalEntry < 1 || p.JournalEntry > 99 || (!formattedJournal && !literalJournal)) {
			panic("手札編號與完整原文不符")
		}
		if source == "" || !(literal || message || service) || p.SHA256 != digest([]byte(source)) ||
			g.catalog[p.Key] == "" || (!service && p.NativeBox != ([4]int{8, 136, 312, 184})) || p.Foreground > 15 || p.Background != 0 || p.Clear > 1 {
			panic("段落來源或安全框不符")
		}
	}
	anchor := oracle.Addr{Seg: 0xb72, Off: 0x311}
	if hex.EncodeToString(o.Bytes(anchor, 8)) != "558bec83ec025657" {
		panic("段落入口 bytes 不符")
	}
	registered := map[oracle.Addr]bool{}
	o.OnCall(anchor, func(_ *oracle.Oracle) {
		g.closeReader()
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
			if ok && g.beginHUDParagraph(caller, box, fg, bg, clear, ptr, source) {
				return
			}
			fallback("source or context mismatch")
			return
		}
		var shortSource map[string]any
		if strings.HasPrefix(binding.Key, "ecl.") && len(source) <= 15 {
			var literal bool
			shortSource, literal = shortECLLiteralSource(o, ptr, caller)
			if !literal {
				fallback("nonliteral short ECL source")
				return
			}
		}
		if strings.HasPrefix(binding.Key, "service-message.") {
			bg = byte(l.config.Background)
		} else if bg == 0 {
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
		detail := map[string]any{"page": page, "caller": caller, "source_pointer": ptr}
		if shortSource != nil {
			detail["short_ecl_source"] = shortSource
		}
		l.awaitGlyphs = append(l.awaitGlyphs, g.listLog("paragraph-before-glyph", detail))
		if strings.HasPrefix(binding.Key, "service-message.") && caller == (oracle.Addr{Seg: 0x291a, Off: 0x0fd0}) {
			if l.serviceNotice != nil {
				panic("服務段落回報尚未返回")
			}
			l.serviceNotice = &serviceNotice{Entry: o.Steps()}
			g.listLog("service-notice-entry", map[string]any{"key": binding.Key, "caller": caller})
		}
		g.openReader(binding)
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
					if notice := l.serviceNotice; notice != nil && !notice.Ready && caller == (oracle.Addr{Seg: 0x291a, Off: 0x0fd0}) {
						menu, ok := readMenuSource(o)
						if !ok || l.config.Menus[menu.Signature] != "confirm" || !l.footerCompatible(menu.Signature) {
							panic("服務回報的原版確認底列不符")
						}
						notice.Ready = true
						l.footerTransition = false
						g.listLog("service-notice-ready", map[string]any{"entry_step": notice.Entry, "caller": caller, "ss": r.SS, "sp": r.SP, "menu_signature": menu.Signature})
					}
				}
			})
		}
	})
}

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
	JournalEntry                  int    `json:",omitempty"`
	PredecessorKey                string `json:",omitempty"`
	prefix                        *originalPrefix
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
	HideFooter                    bool   `json:",omitempty"`
	IntegerTemplateKey            string `json:",omitempty"`
	KeepFooterSignature           string `json:",omitempty"`
	OrdinaryDamage                bool   `json:",omitempty"`
}
type listHUDPending struct {
	Paint               paintReturn
	Entry               uint64
	Words               []listWord
	HideFooter          bool
	KeepFooterSignature string
	AutomaticDamage     bool
}

// 原版 Quick 期間的九鈕戰鬥描述。只辨識顯示語境，不改施法或傷害判定。
const automaticSpellMenuSignature = "c5b214e0c009d9bf9bb1be3435f8b0c72be521577ac3912c57dfa55d39b0a5c2"

func automaticDamageMenu(signature string) bool {
	return signature == automaticSpellMenuSignature || signature == "b891f7b3c26270165eaf8756b7b4d59704d7cf11b45fccb5cdae13dd2468ae6b" ||
		signature == "326aacadb1a01c55f2e08f88cd3fc3ce209f7cfb0826f53439bd66558839a4dc"
}

type listHUDPanelPending struct {
	Paint     paintReturn
	Entry     uint64
	Signature string
}

// 只在已知瞄準底列完整且原版右框確實重畫時等待 sub_1803F 返回。
func (g *liveGame) installHUDPanelUpdates() {
	l, o := g.list, g.o
	signatures := map[string]bool{}
	for _, p := range l.config.HUDParagraphs {
		if p.KeepFooterSignature != "" {
			signatures[p.KeepFooterSignature] = true
		}
	}
	if len(signatures) == 0 {
		return
	}
	entry := oracle.Addr{Seg: 0x088e, Off: 0x085f}
	if hex.EncodeToString(o.Bytes(entry, 11)) != "558bec83ec02803eb7c600" || o.Byte(oracle.Addr{Seg: 0x088e, Off: 0x0a18}) != 0xcb {
		panic("右框更新邊界不符")
	}
	registered := map[oracle.Addr]bool{}
	o.OnCall(entry, func(_ *oracle.Oracle) {
		r := o.Regs()
		raw := o.Byte(oracle.Addr{Seg: r.DS, Off: 0xc6b7})
		menu, ok := readMenuSource(o)
		if r.DS != 0x333e || raw == 0 || !ok || !signatures[menu.Signature] || !l.footerCompatible(menu.Signature) {
			return
		}
		at := o.Caller()
		paint := paintReturn{at, r.SS, r.SP + 4}
		l.hudPanelPaints = append(l.hudPanelPaints, listHUDPanelPending{paint, o.Steps(), menu.Signature})
		g.listLog("hud-update-entry", map[string]any{"caller": at, "ss": r.SS, "sp": r.SP, "menu_signature": menu.Signature, "raw_c6b7": raw})
		if !registered[at] {
			registered[at] = true
			o.OnCall(at, func(_ *oracle.Oracle) {
				if len(l.hudPanelPaints) == 0 {
					return
				}
				p := l.hudPanelPaints[len(l.hudPanelPaints)-1]
				now := o.Regs()
				if p.Paint.Addr != at || p.Paint.SS != now.SS || p.Paint.SP != now.SP {
					return
				}
				menu, ok := readMenuSource(o)
				if !ok || menu.Signature != p.Signature || !l.footerCompatible(menu.Signature) {
					panic("右框重畫改變瞄準底列")
				}
				l.hudPanelPaints = l.hudPanelPaints[:len(l.hudPanelPaints)-1]
				// Next 的右框完成後，原版還會在可見頁恢復按鈕顏色。
				if at == (oracle.Addr{Seg: 0x22f4, Off: 0x2d1c}) {
					l.hudFooterRestore = true
				} else if at != (oracle.Addr{Seg: 0x205e, Off: 0x084b}) {
					l.footerTransition = false
				}
				g.listLog("hud-update-return", map[string]any{"entry_step": p.Entry, "caller": at, "ss": now.SS, "sp": now.SP, "menu_signature": p.Signature})
			})
		}
	})
	o.OnCall(oracle.Addr{Seg: 0x0ceb, Off: 0x01be}, func(_ *oracle.Oracle) {
		p, r := l.hudFooterReturn, o.Regs()
		if p == nil || p.SS != r.SS || p.SP != r.SP {
			return
		}
		l.hudFooterReturn = nil
		l.hudFooterRestore = false
		l.footerTransition = false
		g.listLog("hud-footer-restored", map[string]any{"caller": p.Addr, "ss": r.SS, "sp": r.SP})
	})
}

func (l *listState) aimDamageKey(key string) bool {
	for _, p := range l.config.HUDParagraphs {
		if p.IntegerTemplateKey == key && p.KeepFooterSignature != "" {
			return true
		}
	}
	return false
}

func (g *liveGame) validateHUDParagraphs() {
	if !hudWeaponVocabulary(g.list.config.HUDWeaponNames, g.list.sources, g.catalog) {
		panic("武器名稱詞表不符")
	}
	for _, p := range g.list.config.HUDParagraphs {
		weapon := p.Caller == (oracle.Addr{Seg: 0x088e, Off: 0x097e}) && p.NativeBox == ([4]int{184, 56, 312, 80})
		status := p.Caller == (oracle.Addr{Seg: 0x088e, Off: 0x15e1}) && p.NativeBox == ([4]int{184, 88, 312, 176})
		miss := p.Caller == (oracle.Addr{Seg: 0x22f4, Off: 0x048f}) && p.NativeBox == ([4]int{184, 104, 312, 136})
		death := p.Caller == (oracle.Addr{Seg: 0x088e, Off: 0x15e1}) &&
			(p.NativeBox == ([4]int{184, 112, 312, 176}) || (p.NativeBox == ([4]int{184, 120, 312, 176}) &&
				p.SHA256 == "3639be1dab675907c6bf2d573639a1a3c2c15f7bfd8169f2b4e64e5c43291d64"))
		tailSources := map[int]string{
			104: "e6f16936a01e776202d7148017f7c770f31925d4f97f5312106a685880a34152",
			136: "bcf47e35fc5fe9b78d1ce32a9b98b05adeb3e2aae129207ef29f5fdaeb290f93",
			152: "a95140d02db9873ba8a6300365dbbaf0f6cd0d25d7fda0141df8ff30ee7b07ee",
		}
		tail := p.Caller == (oracle.Addr{Seg: 0x088e, Off: 0x15e1}) && p.NativeBox == ([4]int{184, p.NativeBox[1], 312, 176}) &&
			tailSources[p.NativeBox[1]] == p.SHA256 && p.IntegerTemplateKey == "" && len(p.Spans) == 1 &&
			p.SHA256 == digest([]byte(g.list.sources[p.Spans[0].Key]))
		defeatRows := map[oracle.Addr]struct {
			y   int
			key string
		}{
			{Seg: 0x27c7, Off: 0x148e}: {40, "round.7dac946f666da2007a13"},
			{Seg: 0x27c7, Off: 0x14b0}: {48, "round.cb9c29877d1d0994294e"},
			{Seg: 0x27c7, Off: 0x14d2}: {56, "round.fc2486907daf61f75699"},
		}
		row, knownDefeat := defeatRows[p.Caller]
		explorationEffect := p.Caller == (oracle.Addr{Seg: 0x088e, Off: 0x164e}) && p.NativeBox == ([4]int{8, 152, 312, 184}) &&
			(p.SHA256 == "d95ff49dc50236cb9df4a434fe0a654e5bd08a3d6f33b400207ead1768ef8d51" ||
				p.SHA256 == "ba24b7992d5d9077dba9a98bc15047ddea1c340dd068683687736ca0f0c072eb") &&
			p.IntegerTemplateKey == "" && !p.HideFooter && p.KeepFooterSignature == "" && len(p.Spans) == 1 &&
			p.Spans[0].Start == 0 && p.Spans[0].Rect == ([4]int{8, 152, p.Spans[0].Length * 8, 8}) &&
			p.SHA256 == digest([]byte(g.list.sources[p.Spans[0].Key]))
		defeat := knownDefeat && p.NativeBox == ([4]int{16, row.y, 304, 184}) && p.IntegerTemplateKey == "" &&
			len(p.Spans) == 1 && p.Spans[0].Key == row.key && p.Spans[0].Rect == ([4]int{16, row.y, 288, 8}) &&
			p.SHA256 == digest([]byte(g.list.sources[row.key]))
		if !(weapon || status || miss || death || tail || defeat || explorationEffect) || (p.HideFooter && !status) || len(p.SHA256) != 64 || p.Foreground != 7 || p.Background != 0 || p.Clear != 1 || len(p.Spans) == 0 {
			panic("右側段落來源不符")
		}
		if p.IntegerTemplateKey != "" {
			ordinary := p.OrdinaryDamage && (status || miss) && p.KeepFooterSignature == "" && (!p.HideFooter || status)
			aimed := !p.OrdinaryDamage && status && !p.HideFooter && len(p.KeepFooterSignature) == 64 && g.list.config.Menus[p.KeepFooterSignature] == "aim"
			if !(ordinary || aimed) || len(p.Spans) != 1 || p.Spans[0].Key != p.IntegerTemplateKey ||
				p.SHA256 != digest([]byte(g.list.sources[p.IntegerTemplateKey])) || !hudIntegerTemplate(g.list.sources[p.IntegerTemplateKey]) || !hudIntegerTemplate(g.catalog[p.IntegerTemplateKey]) {
				panic("右側數值模板或底列來源不符")
			}
		} else if p.KeepFooterSignature != "" || p.OrdinaryDamage {
			panic("未辨識的右側底列保留契約")
		}
		for _, span := range p.Spans {
			x, y, w, h := span.Rect[0], span.Rect[1], span.Rect[2], span.Rect[3]
			quantityName := weapon && span.Start == 2 && h == 8 && (g.list.sources[span.Key] == "Javelin" || g.list.sources[span.Key] == "Javelins")
			wrappedBow := weapon && span.Start == 15 && span.Length == 3 && g.list.sources[span.Key] == "Bow" && span.Rect == ([4]int{184, 64, 24, 8})
			aligned := x == p.NativeBox[0]+span.Start*8 && y == p.NativeBox[1]
			if (span.Start != 0 && !quantityName && !wrappedBow) || span.Length <= 0 || g.list.sources[span.Key] == "" || len(g.list.sources[span.Key]) != span.Length ||
				g.catalog[span.Key] == "" || (!aligned && !wrappedBow) || w <= 0 || h < 8 || x+w > p.NativeBox[2] || y+h > p.NativeBox[3] ||
				len([]rune(g.catalog[span.Key]))*g.glyphs.Size > w*2 {
				panic("右側段落切片或字框不符")
			}
		}
	}
}

func (g *liveGame) beginHUDParagraph(caller oracle.Addr, box [4]int, fg, bg, clear byte, ptr oracle.Addr, source string) bool {
	l, o := g.list, g.o
	bindings := l.config.HUDParagraphs
	if caller == (oracle.Addr{Seg: 0x088e, Off: 0x097e}) && box == ([4]int{184, 56, 312, 80}) && fg == 7 && bg == 0 && clear == 1 {
		if part, ok := hudWeaponName(l.config.HUDWeaponNames, l.sources, source); ok {
			bindings = append(append([]listHUDParagraph{}, bindings...), listHUDParagraph{
				SHA256: digest([]byte(source)), Caller: caller, NativeBox: box, Foreground: fg, Background: bg, Clear: clear,
				Spans: []listHUDSpan{{Start: 0, Length: len(part.Name), Key: part.Key, Rect: [4]int{184, 56, len(part.Name) * 8, 8}}},
			})
		}
	}
	for _, p := range bindings {
		if p.Caller != caller || p.NativeBox != box || p.Foreground != fg || p.Background != bg || p.Clear != clear {
			continue
		}
		var number *int32
		if p.IntegerTemplateKey != "" {
			value, ok := hudInteger(source, l.sources[p.IntegerTemplateKey])
			if !ok {
				continue
			}
			number = &value
			if !p.OrdinaryDamage {
				menu, ok := readMenuSource(o)
				if !ok || menu.Signature != p.KeepFooterSignature || !l.footerCompatible(menu.Signature) {
					continue
				}
			} else if l.aimDamageKey(p.IntegerTemplateKey) {
				menu, ok := readMenuSource(o)
				if !ok || !automaticDamageMenu(menu.Signature) {
					continue
				}
			}
		} else if p.SHA256 != digest([]byte(source)) {
			continue
		}
		var words []listWord
		for _, span := range p.Spans {
			if number == nil && (span.Start+span.Length > len(source) || source[span.Start:span.Start+span.Length] != l.sources[span.Key]) {
				return false
			}
			x, y, w, h := span.Rect[0], span.Rect[1], span.Rect[2], span.Rect[3]
			word := listWord{X: x, Y: y, Width: w, Key: span.Key, Group: "body", Foreground: fg, Background: l.config.Background}
			if h != 8 {
				word.Height = h
			}
			word.Number = number
			if number != nil {
				text, ok := hudIntegerText(g.catalog[span.Key], *number)
				if !ok || len([]rune(text))*g.glyphs.Size > w*2 {
					return false
				}
			}
			words = append(words, word)
		}
		g.page = nil
		l.erase(box[0], box[1], box[2]-box[0], box[3]-box[1])
		r := o.Regs()
		paint := paintReturn{caller, r.SS, r.SP + 4}
		l.paragraphPaints = append(l.paragraphPaints, paint)
		l.hudActive = true
		if caller == (oracle.Addr{Seg: 0x088e, Off: 0x164e}) && box == ([4]int{8, 152, 312, 184}) {
			l.explorationEffects = true
		}
		l.hudPending = append(l.hudPending, listHUDPending{paint, o.Steps(), words, p.HideFooter, p.KeepFooterSignature,
			p.OrdinaryDamage && l.aimDamageKey(p.IntegerTemplateKey)})
		l.awaitGlyphs = append(l.awaitGlyphs, g.listLog("hud-before-glyph", map[string]any{"caller": caller, "native_box": box, "source_sha256": digest([]byte(source)), "source_pointer": ptr, "spans": p.Spans, "words": words}))
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
				if pending.AutomaticDamage {
					// 自動施法沒有瞄準選單待復色；完整傷害回報返回後即可提交。
					l.footerTransition = false
				}
				for _, word := range pending.Words {
					l.erase(word.X, word.Y, word.Width, word.height())
					l.words[[2]int{word.X, word.Y}] = word
				}
				if pending.HideFooter {
					for at, word := range l.words {
						if word.Group == "footer" {
							// 自動施法的原生底列跨越右側回報；由原版填色或覆寫撤除。
							if c := l.spellCaption; c != nil && c.Reference != nil && word == c.Word {
								continue
							}
							if c := l.movementCaption; c != nil && c.Reference != nil && word.Key == c.Word.Key {
								continue
							}
							delete(l.words, at)
						}
					}
					l.footerTransition = false
				}
				if pending.KeepFooterSignature != "" {
					menu, ok := readMenuSource(o)
					if !ok || menu.Signature != pending.KeepFooterSignature || !l.footerCompatible(menu.Signature) {
						panic("右側數值回報的瞄準底列改變")
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
	if g.list.passage != nil {
		g.passageFill(x, y, width, height, false)
		if g.list.passage != nil {
			return
		}
	}
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
	g.installHUDPanelUpdates()
	g.installPassages()
	if len(l.config.Paragraphs) == 0 {
		return
	}
	for _, p := range l.config.Paragraphs {
		source := l.sources[p.Key]
		suffix := digest([]byte(source))[:20]
		literal := p.Key == "ecl."+suffix
		if literal && len(source) == 1 && p.PredecessorKey == "" {
			panic("單字元敘事缺少前文限制")
		}
		if p.PredecessorKey != "" {
			valid := false
			for _, previous := range l.config.Paragraphs {
				if previous.Key == p.PredecessorKey && previous.Clear == 1 && previous.NativeBox == p.NativeBox &&
					previous.Background == p.Background && previous.Caller == (oracle.Addr{Seg: 0x26b4, Off: 0x1d81}) {
					valid = true
				}
			}
			if !valid || !literal || len(source) != 1 || p.Clear != 0 || p.Foreground != 3 ||
				p.Caller != (oracle.Addr{Seg: 0x26b4, Off: 0x1d53}) || p.JournalEntry != 0 {
				panic("敘事前文限制不符")
			}
		}
		message := p.Key == "message."+suffix && p.Caller == (oracle.Addr{Seg: 0x26b4, Off: 0x3320}) && p.Foreground == 7 && p.Clear == 1
		choicePrompt := p.Key == "ui.ab9e574dc207b6412ef1" && p.Key == "ui."+suffix &&
			p.Caller == (oracle.Addr{Seg: 0x26b4, Off: 0x2022}) && p.Foreground == 7 && p.Clear == 0 &&
			p.JournalEntry == 0 && p.PredecessorKey == ""
		service := p.Key == "service-message."+suffix && p.Caller.Seg == 0x291a &&
			(p.Caller.Off == 0x0eee || p.Caller.Off == 0x0fd0 || p.Caller.Off == 0x0c7f) &&
			p.NativeBox == ([4]int{8, 168, 312, 184}) && p.Foreground == 11 && p.Background == 0 && p.Clear == 1 && l.config.Background == 23
		formattedJournal := message &&
			digest([]byte(l.sources[journalTemplateKey]))[:20] == strings.TrimPrefix(journalTemplateKey, "ui.") &&
			strings.Count(l.sources[journalTemplateKey], "%s") == 1 &&
			strings.Replace(l.sources[journalTemplateKey], "%s", strconv.Itoa(p.JournalEntry), 1) == source
		number, knownNumber := journalLiteralNumber(source)
		literalJournal := literal && p.Caller.Seg == 0x26b4 && (p.Foreground == 7 || p.Foreground == 3) &&
			((p.Caller.Off == 0x1d81 && p.Clear == 1) || (p.Caller.Off == 0x1d53 && p.Clear == 0)) &&
			knownNumber && number == p.JournalEntry
		if p.JournalEntry != 0 && (p.JournalEntry < 1 || p.JournalEntry > 99 || (!formattedJournal && !literalJournal)) {
			panic("手札編號與完整原文不符")
		}
		if source == "" || !(literal || message || service || choicePrompt) || p.SHA256 != digest([]byte(source)) ||
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
			g.cancelPassage(reason)
			g.page = nil
			g.listLog("unknown-paragraph-original", map[string]any{"caller": caller, "reason": reason})
		}
		if ok && (binding == nil || binding.JournalEntry == 0) {
			if grouped, wholeSource, handled := g.passageParagraph(ptr, caller, box, fg, bg, clear, source); handled {
				if grouped == nil {
					return
				}
				binding, source = grouped, wholeSource
			}
		}
		if binding == nil {
			if ok {
				binding = g.originalPrefixParagraph(ptr, caller, box, fg, bg, clear, source)
			}
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
		if !paragraphPredecessor(binding, g.page) {
			fallback("paragraph predecessor mismatch")
			return
		}
		if strings.HasPrefix(binding.Key, "service-message.") {
			bg = byte(l.config.Background)
		} else if bg == 0 {
			bg = 8
		}
		text := g.catalog[binding.Key]
		prefix := binding.prefix
		if prefix != nil {
			text = source
		}
		components := []string{binding.Key}
		componentColors := []int{int(fg)}
		outputBox := [4]int{box[0] * 2, box[1] * 2, box[2] * 2, box[3] * 2}
		if clear == 0 {
			if g.page == nil || g.page.Box != outputBox || g.page.Background != bg {
				fallback("missing compatible predecessor")
				return
			}
			text = g.page.Text + text
			prefix = g.page.Prefix
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
		page.Prefix = prefix
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
					g.captureOriginalPrefix(p)
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

// 限定最近一個完整片段；不把同頁較早出現的文字當成目前的語境。
func paragraphPredecessor(binding *listParagraph, page *storyPage) bool {
	if binding.PredecessorKey == "" {
		return true
	}
	return page != nil && len(page.Components) > 0 && page.Key == binding.PredecessorKey &&
		page.Components[len(page.Components)-1] == binding.PredecessorKey
}

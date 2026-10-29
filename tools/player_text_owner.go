// 完整短字串的來源命令。只處理正式譯文、已量測字模與原生八像素高的單行。
package main

import (
	"image"
	"path/filepath"
	"sort"
	"strings"

	"github.com/wicanr2/dosgolem/oracle"
)

type ownedPrint struct {
	Return         paintReturn
	Source         string
	Word           listWord
	Color          uint16
	Next           int
	Valid          bool
	Reference      []byte
	Page           uint32
	Format         *displayFormat
	Printed        []byte
	Text           string
	Layout         displayTextLayout
	LastX, LastY   int
	PreserveNative bool
}

type playerTextOwner struct {
	Oracle        *oracle.Oracle
	Sources       map[string]string
	NameKeys      map[string]string
	Catalog       map[string]string
	Glyphs        glyphSet
	Runs          []*ownedPrint
	Words         []*ownedPrint
	FormatText    string
	Formats       map[string]*displayFormat
	FormatOrder   []*displayFormat
	FoldedSources map[string]string
	Counters      map[string]uint64
	Unmatched     []map[string]any
	UnmatchedSeen map[string]bool
}

func loadPlayerTextOwner(o *oracle.Oracle, profile string, glyphPoint oracle.Addr) *playerTextOwner {
	p := &playerTextOwner{Oracle: o, Sources: map[string]string{}, NameKeys: map[string]string{}, Catalog: readLiveCatalog(filepath.Join(profile, "display.zh-TW.tsv"))}
	p.Formats = map[string]*displayFormat{}
	p.Counters = map[string]uint64{}
	p.UnmatchedSeen = map[string]bool{}
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
		if strings.HasPrefix(key, "name.") {
			fold := strings.ToLower(source)
			if previous := p.NameKeys[fold]; previous != "" && p.Catalog[previous] != p.Catalog[key] {
				panic("姓名大小寫對應歧義")
			}
			p.NameKeys[fold] = key
		}
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
		mark := paintReturn{target, r.SS, r.SP + 4}
		for _, active := range p.Runs {
			if active.Return == mark {
				p.Counters["entry_revisit"]++
				return
			}
		}
		run := &ownedPrint{Return: paintReturn{target, r.SS, r.SP + 4}, Color: o.StackWord(4)}
		source, ok := listString(o, o.StackWord(6), o.StackWord(5))
		if ok && source == p.FormatText {
			source, ok = listString(o, o.StackWord(8), o.StackWord(7))
		}
		if ok {
			run.Source = source
		}
		if ok && p.sourceKey(source) != "" {
			run.Source, run.Valid = source, true
			run.Word.Key = p.sourceKey(source)
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
		// 已知顯示出口的未知姓名／數字僅保留原版實際印出的字元，
		// 不解析varargs，不翻譯或改寫原版字串。完整返回後才提交高清字。
		if ok && !run.Valid && nativeDisplaySource(source) {
			run.Valid, run.PreserveNative = true, true
			run.Word.Key = "native-display." + digest([]byte(source))[:20]
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
		(run.Format == nil && !run.PreserveNative && (run.Next >= len(run.Source) || ch != run.Source[run.Next])) ||
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
		if run.Format == nil && !run.PreserveNative {
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
	if run.Format != nil || run.PreserveNative {
		run.Printed = append(run.Printed, ch)
	}
	run.Next++
	run.LastX, run.LastY = x, y
}

func (p *playerTextOwner) finish(run *ownedPrint) {
	if !run.Valid || run.Next == 0 || (run.Format == nil && !run.PreserveNative && run.Next != len(run.Source)) {
		// 未取得本層所有權不等同漏譯；列表、段落及冷啟動可由其他層承接。
		// 只保存有界來源，供抽驗核對，不改原版執行或強行套譯。
		if source := strings.TrimSpace(run.Source); len(source) > 1 && strings.Trim(source, " 0123456789+-.,()%:") != "" {
			key := digest([]byte(source))
			if p.UnmatchedSeen == nil {
				p.UnmatchedSeen = map[string]bool{}
			}
			if !p.UnmatchedSeen[key] && len(p.Unmatched) < 128 {
				p.UnmatchedSeen[key] = true
				p.Unmatched = append(p.Unmatched, map[string]any{"source": source, "sha256": key, "return": run.Return, "step": p.Oracle.Steps(), "local_layer_valid": run.Valid, "glyphs": run.Next, "classification": "unclaimed-by-complete-string-layer; check other text owners"})
			}
		}
		return
	}
	if run.Text == "" {
		run.Text = p.Catalog[run.Word.Key]
	}
	if run.PreserveNative {
		run.Text = string(run.Printed)
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

func nativeDisplaySource(source string) bool {
	if len(source) < 1 || len(source) > 128 {
		return false
	}
	for _, ch := range []byte(source) {
		if ch < 32 || ch > 126 {
			return false
		}
	}
	return true
}

// 只在已證實的顯示出口辨識已知姓名的大小寫；不改客體字串。
func (p *playerTextOwner) sourceKey(source string) string {
	if key := p.Sources[source]; key != "" {
		return key
	}
	return p.NameKeys[strings.ToLower(source)]
}

func (g *liveGame) drawKnownNamePrefix(px []byte, page *storyPage) bool {
	if g.player == nil || page.Prefix == nil {
		return false
	}
	owner := renderOwners[g.o]
	if owner == nil || owner.Text == nil {
		return false
	}
	p := owner.Text
	source := page.Prefix.Text
	key := p.sourceKey(strings.TrimSpace(source))
	if !strings.HasPrefix(key, "name.") {
		return false
	}
	w := listWord{X: page.Box[0] / 2, Y: page.Box[1] / 2, Width: len(source) * 8,
		Key: key, Foreground: page.Foreground, Background: page.Background}
	g.composeWords(px, []listWord{w}, map[string]string{key: p.translateValue(source)}, p.Glyphs)
	return true
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
		if p.referenceMatches(run) {
			kept = append(kept, run)
		}
	}
	p.Words = kept
}

// 游標暫存繪圖保留底層資產，只暫時遮住它；不能因此丟失中文命令。
func (p *playerTextOwner) referenceMatches(run *ownedPrint) bool {
	now := nativeTextRegion(p.Oracle, run.Page, run.Word)
	if len(now) != len(run.Reference) || len(now) == 0 {
		return false
	}
	owner := renderOwners[p.Oracle]
	for i, value := range now {
		if value == run.Reference[i] {
			continue
		}
		if owner == nil {
			return false
		}
		w := run.Word
		cell := owner.Scene.page(run.Page, p.Oracle.PresentationPlane).Cells[(w.Y+i/w.Width)*320+w.X+i%w.Width]
		if !retainedTextPixel(value, run.Reference[i], cell) {
			return false
		}
	}
	return true
}

func retainedTextPixel(value, reference byte, cell sceneCell) bool {
	return value == reference || cell.Asset != nil && !cell.Visible && cell.Asset.Index[cell.Source] == reference
}

func (p *playerTextOwner) restoreOcclusion(px []byte, g *liveGame, run *ownedPrint) {
	now := nativeTextRegion(p.Oracle, run.Page, run.Word)
	w, pal := run.Word, p.Oracle.Palette()
	for y := 0; y < 8; y++ {
		for x := 0; x < w.Width; {
			if now[y*w.Width+x] == run.Reference[y*w.Width+x] {
				x++
				continue
			}
			start := x
			for x < w.Width && now[y*w.Width+x] != run.Reference[y*w.Width+x] {
				color := pal[now[y*w.Width+x]]
				for yy := 0; yy < 2; yy++ {
					for xx := 0; xx < 2; xx++ {
						at := (((w.Y+y)*2+yy)*640 + (w.X+x)*2 + xx) * 4
						copy(px[at:at+3], color[:])
					}
				}
				x++
			}
			g.sharpClear(image.Rect((w.X+start)*2, (w.Y+y)*2, (w.X+x)*2, (w.Y+y+1)*2))
		}
	}
}

// 畫面搬移也搬移完整文字命令。只接受來源及目的都完整、未折行的字框。
func copiedDisplayWord(w listWord, source, destination, count int) (listWord, bool) {
	first := w.Y*80 + w.X/4
	last := (w.Y+7)*80 + (w.X+w.Width)/4
	if w.X%4 != 0 || w.Width <= 0 || w.Width%4 != 0 || first < source || last > source+count {
		return listWord{}, false
	}
	at := w.Y*320 + w.X + (destination-source)*4
	if at < 0 || at >= 64000 {
		return listWord{}, false
	}
	w.X, w.Y = at%320, at/320
	return w, w.X+w.Width <= 320 && w.Y+8 <= 200
}

func (p *playerTextOwner) copyTransaction(origin uint32) []*ownedPrint {
	if origin != 0x11632 && origin != 0x11688 {
		return nil
	}
	o := p.Oracle
	if !nativePageLayout(o) {
		return nil
	}
	srcSeg, dstSeg := o.Arg(1), o.Arg(3)
	source, destination, count := int(o.Arg(0)), int(o.Arg(2)), int(o.Arg(4))
	if srcSeg < 0xa000 || srcSeg > 0xac00 || (srcSeg-0xa000)%0x400 != 0 ||
		dstSeg < 0xa000 || dstSeg > 0xac00 || (dstSeg-0xa000)%0x400 != 0 ||
		count == 0 || source+count > 16000 || destination+count > 16000 {
		return nil
	}
	return p.copyCandidates(uint32(srcSeg-0xa000)*16, uint32(dstSeg-0xa000)*16, source, destination, count)
}

func (p *playerTextOwner) copyCandidates(from, to uint32, source, destination, count int) []*ownedPrint {
	var result []*ownedPrint
	for _, run := range p.Words {
		if run.Page != from || !p.referenceMatches(run) {
			continue
		}
		word, ok := copiedDisplayWord(run.Word, source, destination, count)
		if !ok {
			continue
		}
		copyOfRun := *run
		copyOfRun.Word, copyOfRun.Page = word, to
		result = append(result, &copyOfRun)
	}
	return result
}

func (p *playerTextOwner) finishCopies(copies []*ownedPrint) {
	if len(copies) == 0 {
		return
	}
	p.prune()
	for _, run := range copies {
		// Mode X可能分平面搬移；目的所有色號完整相同後才取得文字所有權。
		if !p.referenceMatches(run) {
			continue
		}
		replaced := false
		for i, previous := range p.Words {
			if previous.Page == run.Page && previous.Word.X == run.Word.X && previous.Word.Y == run.Word.Y {
				p.Words[i], replaced = run, true
				break
			}
		}
		if !replaced {
			if len(p.Words) >= 512 {
				p.Words = p.Words[1:]
			}
			p.Words = append(p.Words, run)
		}
		p.Counters["copied_complete_words"]++
	}
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
		covered = ownedTextCovered(w, protected)
		if !covered {
			g.composeWords(px, []listWord{w}, map[string]string{w.Key: run.Text}, p.Glyphs)
			p.restoreOcclusion(px, g, run)
		}
	}
}

func ownedTextCovered(w listWord, protected [][4]int) bool {
	for _, r := range protected {
		if w.X < r[2] && w.X+w.Width > r[0] && w.Y < r[3] && w.Y+8 > r[1] {
			return true
		}
	}
	return false
}

func (p *playerTextOwner) Rectangles(protected [][4]int) [][4]int {
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
		if ownedTextCovered(w, protected) {
			continue
		}
		r := [4]int{w.X, w.Y, w.X + w.Width, w.Y + 8}
		if owner := renderOwners[p.Oracle]; owner != nil && owner.CanTranslate(r) {
			result = append(result, r)
		}
	}
	return result
}

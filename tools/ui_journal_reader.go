// DRAFT：手札自動顯示、長頁與已讀查閱；前端按鍵不送入原版。
package main

import (
	"encoding/json"
	"fmt"
	"os"
	"sort"
	"strconv"
	"strings"
	"time"

	"github.com/hajimehoshi/ebiten/v2"
	"github.com/hajimehoshi/ebiten/v2/inpututil"
)

const journalTemplateKey = "ui.aa93370ee0689e9a462e"

type readerPage struct {
	Entry     int
	Heading   string
	Lines     []string
	Box       [4]int
	Step      uint64 `json:"step"`
	SourceKey string
	Number    int              `json:",omitempty"`
	Count     int              `json:",omitempty"`
	Footer    string           `json:",omitempty"`
	Mode      string           `json:",omitempty"`
	Image     *readerImageView `json:",omitempty"`
}

type readerControl struct {
	At    uint64 `json:"at"`
	Key   string `json:"key"`
	Entry int    `json:"entry,omitempty"`
}

type journalReader struct {
	SHA256        string
	Entries       map[int]readerPage
	Page          *readerPage
	Events        []map[string]any
	Auto          *readerPage
	UI            map[string]string
	Seen          map[int]string
	Last          int
	Index         int
	Mode          string
	Ready         bool
	Live          bool
	Probe         bool
	Controls      []readerControl
	ControlIndex  int
	ControlSHA    string
	UIEvents      []map[string]any
	Gallery       []readerPage
	GalleryIndex  int
	GalleryFrames []map[string]any
	Saved         *readerPage
	SavedIndex    int
	WaitDraw      bool
	Images        map[int]readerIllustration
	ImageSHA      string
}

func readerLines(body string) []string {
	var lines []string
	for _, paragraph := range strings.Split(body, "\\n") {
		if paragraph == "" {
			lines = append(lines, "")
			continue
		}
		chars := []rune(paragraph)
		for len(chars) > 0 {
			n := min(38, len(chars))
			for n < len(chars) && n > 0 && (strings.ContainsRune("，。！？、；：」』）》】", chars[n]) || strings.ContainsRune("「『（《【", chars[n-1])) {
				n--
			}
			if n == 0 {
				panic("手札無安全斷行")
			}
			lines = append(lines, string(chars[:n]))
			chars = chars[n:]
		}
	}
	if len(lines) == 0 || len(lines) > 39 {
		panic("手札超出三頁原型容量")
	}
	return lines
}

func (g *liveGame) installReader(path, illustrations string) {
	if g.list == nil || len(g.list.config.Paragraphs) == 0 {
		panic("手札原型需要完整段落辨識")
	}
	data, err := os.ReadFile(path)
	must(err)
	catalog := readLiveCatalog(path)
	heading := catalog["reader.heading"]
	if strings.Count(heading, "%s") != 2 || strings.Contains(strings.ReplaceAll(heading, "%s", ""), "%") {
		panic("手札標題模板不符")
	}
	r := &journalReader{SHA256: digest(data), Entries: map[int]readerPage{}, UI: catalog, Seen: map[int]string{}}
	uiCount := 1
	if catalog["reader.page"] != "" || catalog["reader.empty"] != "" || catalog["reader.browse_hint"] != "" {
		if strings.Count(catalog["reader.page"], "%s") != 2 || strings.Contains(strings.ReplaceAll(catalog["reader.page"], "%s", ""), "%") ||
			catalog["reader.empty"] == "" || catalog["reader.browse_hint"] == "" {
			panic("手札查閱介面詞條不完整")
		}
		uiCount, r.Ready = 4, true
	}
	if illustrations != "" {
		g.loadReaderIllustrations(r, illustrations)
		g.validateReaderText(catalog["reader.image_hint"], 38)
		uiCount++
	}
	for key, body := range catalog {
		if key == "reader.heading" || (illustrations != "" && key == "reader.image_hint") || (r.Ready && (key == "reader.page" || key == "reader.empty" || key == "reader.browse_hint")) || strings.HasSuffix(key, ".title") {
			continue
		}
		idText := strings.TrimSuffix(strings.TrimPrefix(key, "journal."), ".body")
		id, err := strconv.Atoi(idText)
		if err != nil || id < 1 || id > 99 || key != fmt.Sprintf("journal.%d.body", id) || catalog[fmt.Sprintf("journal.%d.title", id)] == "" {
			panic("手札鍵或標題不符")
		}
		p := readerPage{Entry: id, Heading: fmt.Sprintf(heading, idText, catalog[fmt.Sprintf("journal.%d.title", id)]), Lines: readerLines(body), Box: [4]int{16, 16, 624, 256}}
		if len(p.Lines) > 13 && !r.Ready {
			panic("手札超出單頁原型容量")
		}
		if len([]rune(p.Heading)) > 37 {
			panic("手札標題超出安全框")
		}
		for _, text := range append([]string{p.Heading}, p.Lines...) {
			for _, ch := range text {
				alpha := g.glyphs.Glyphs[string(ch)]
				if ch < 32 || ch == '\\' || len(alpha) != 320 {
					panic("手札字型或控制字元不符")
				}
				for _, a := range alpha[256:] {
					if a != 0 {
						panic("手札字墨超出列高")
					}
				}
			}
		}
		if r.Entries[id].Entry != 0 {
			panic("圖文與正文編號重複")
		}
		r.Entries[id] = p
	}
	if len(r.Entries) == 0 || len(catalog) != uiCount+len(r.Entries)*2-len(r.Images) {
		panic("手札缺頁或含未知鍵")
	}
	if r.Ready {
		for _, text := range []string{catalog["reader.empty"], catalog["reader.browse_hint"], fmt.Sprintf(catalog["reader.page"], "3", "3")} {
			if len([]rune(text)) > 37 {
				panic("手札操作提示超出安全框")
			}
			for _, ch := range text {
				alpha := g.glyphs.Glyphs[string(ch)]
				if ch < 32 || ch == '\\' || len(alpha) != 320 {
					panic("手札操作提示缺字")
				}
				for _, a := range alpha[256:] {
					if a != 0 {
						panic("手札操作提示字墨超出列高")
					}
				}
			}
		}
	}
	g.reader = r
}

func (r *journalReader) page(id, index int, mode, key string, step uint64) *readerPage {
	p, ok := r.Entries[id]
	if !ok {
		panic("未知手札頁")
	}
	count := r.pageCount(id)
	if index < 0 || index >= count {
		panic("手札頁碼越界")
	}
	p.Lines = p.Lines[index*13 : min((index+1)*13, len(p.Lines))]
	if p.Image != nil {
		p.Image = &readerImageView{}
	}
	p.Step, p.SourceKey, p.Mode = step, key, mode
	if count > 1 {
		p.Number, p.Count = index+1, count
		p.Footer = fmt.Sprintf(r.UI["reader.page"], strconv.Itoa(index+1), strconv.Itoa(count))
	}
	if mode == "browse" || mode == "probe" {
		if p.Footer != "" {
			p.Footer += " "
		}
		p.Footer += r.UI["reader.browse_hint"]
	}
	if p.Image != nil {
		p.Footer = r.UI["reader.image_hint"]
	}
	if len([]rune(p.Footer)) > 38 {
		panic("手札頁尾超出安全框")
	}
	return &p
}

func (r *journalReader) seenIDs() []int {
	ids := make([]int, 0, len(r.Seen))
	for id := range r.Seen {
		ids = append(ids, id)
	}
	sort.Ints(ids)
	return ids
}

func (g *liveGame) closeReader() {
	if g.reader != nil && g.reader.Auto != nil {
		g.reader.Events = append(g.reader.Events, map[string]any{"step": g.o.Steps(), "action": "close", "entry": g.reader.Auto.Entry, "reason": "next paragraph"})
		g.reader.Auto = nil
		if g.reader.Mode == "" {
			g.reader.Page = nil
			g.reader.Index = 0
		}
	}
}

func (g *liveGame) openReader(p *listParagraph) {
	if g.reader == nil || p.JournalEntry == 0 {
		return
	}
	_, ok := g.reader.Entries[p.JournalEntry]
	if !ok {
		g.reader.Events = append(g.reader.Events, map[string]any{"step": g.o.Steps(), "action": "unavailable", "entry": p.JournalEntry, "source_key": p.Key})
		return
	}
	page := g.reader.page(p.JournalEntry, 0, "", p.Key, g.o.Steps())
	g.reader.Auto, g.reader.Page, g.reader.Index = page, page, 0
	g.reader.Seen[p.JournalEntry], g.reader.Last = p.Key, p.JournalEntry
	g.reader.Events = append(g.reader.Events, map[string]any{"step": page.Step, "action": "open", "page": *page})
}

func (g *liveGame) composeReader(px []byte) {
	if g.reader == nil || g.reader.Page == nil {
		return
	}
	p, pal := g.reader.Page, g.o.Palette()
	for y := p.Box[1]; y < p.Box[3]; y++ {
		for x := p.Box[0]; x < p.Box[2]; x++ {
			if x < 32 && y < 32 {
				continue // 保留原版左上徽章的右下角。
			}
			copy(px[(y*640+x)*4:][:3], pal[0][:])
		}
	}
	rows := append([]string{p.Heading}, p.Lines...)
	if p.Image != nil {
		g.composeReaderImage(px, p)
	}
	if p.Footer != "" {
		for len(rows) < 14 {
			rows = append(rows, "")
		}
		rows = append(rows, p.Footer)
	}
	for row, text := range rows {
		color := 15
		left := p.Box[0]
		if row == 0 {
			color = 14
			left += 16
		}
		fg := pal[color]
		for col, ch := range []rune(text) {
			for off, a := range g.glyphs.Glyphs[string(ch)][:256] {
				if a == 0 {
					continue
				}
				d := ((p.Box[1]+row*16+off/16)*640 + left + col*16 + off%16) * 4
				for c := 0; c < 3; c++ {
					px[d+c] = byte((uint32(fg[c])*uint32(a) + uint32(px[d+c])*(255-uint32(a)) + 127) / 255)
				}
			}
		}
	}
}

func (g *liveGame) readerStable() bool {
	l := g.list
	if l != nil && (l.hudFooterRestore || l.hudFooterReturn != nil) {
		return false
	}
	return l != nil && len(l.paints) == 0 && len(l.fills) == 0 && len(l.scrolls) == 0 && !l.clearPending && !l.awaitPageFlip &&
		len(l.menus) == 0 && len(l.buttons) == 0 && !l.headerTransition && !l.footerTransition && l.clockReturn == nil && len(l.paragraphPaints) == 0 && len(l.hudPanelPaints) == 0
}

func (g *liveGame) installReaderControls(path, nativeRequest string, live, probe bool) {
	r := g.reader
	if r == nil || !r.Ready {
		panic("查閱控制需要完整介面詞條")
	}
	r.Live, r.Probe = live, probe
	if path == "" {
		return
	}
	data, err := os.ReadFile(path)
	must(err)
	var input struct {
		NativeSHA string          `json:"native_request_sha256"`
		Controls  []readerControl `json:"controls"`
	}
	must(json.Unmarshal(data, &input))
	native, err := os.ReadFile(nativeRequest)
	must(err)
	if input.NativeSHA != digest(native) {
		panic("查閱控制與原版請求不符")
	}
	var last uint64
	manual := false
	for _, c := range input.Controls {
		if c.Key != "Preview" && c.Entry != 0 {
			panic("查閱控制含多餘編號")
		}
		if c.At < g.o.Steps() || c.At >= g.limit() || c.At < last || (manual && c.At != last) {
			panic("查閱控制時點不符")
		}
		switch c.Key {
		case "F5":
			manual = !manual
		case "Esc":
			manual = false
		case "PgUp", "PgDn", "Left", "Right":
		case "ZoomIn", "ZoomOut", "PanLeft", "PanRight", "PanUp", "PanDown", "Home":
			if len(r.Images) == 0 {
				panic("圖文控制未載入圖文")
			}
		case "Gallery", "Preview":
			if !probe || manual || (c.Key == "Preview" && r.Entries[c.Entry].Entry == 0) {
				panic("手札元件預覽未啟用或編號不符")
			}
			if c.Key == "Preview" {
				manual = true
			}
		default:
			panic("未知查閱控制鍵")
		}
		last = c.At
	}
	if manual && !live {
		panic("查閱控制沒有同時點關閉鍵")
	}
	r.Controls, r.ControlSHA = input.Controls, digest(data)
}

func (g *liveGame) readerKey(key, source string, entry int) {
	r, step := g.reader, g.o.Steps()
	if !g.readerStable() {
		if source != "keyboard" {
			panic("查閱控制點不在完整畫面")
		}
		r.UIEvents = append(r.UIEvents, map[string]any{"step": step, "frame": len(g.frames), "key": key, "source": source, "ignored": "unstable"})
		return
	}
	switch key {
	case "ZoomIn", "ZoomOut", "PanLeft", "PanRight", "PanUp", "PanDown", "Home":
		g.readerImageKey(key)
	case "Gallery":
		if !r.Probe || r.Mode != "" {
			panic("元件畫廊不可巢狀開啟")
		}
		r.Saved, r.SavedIndex = r.Page, r.Index
		ids := make([]int, 0, len(r.Entries))
		for id := range r.Entries {
			ids = append(ids, id)
		}
		sort.Ints(ids)
		for _, id := range ids {
			for page := 0; page < r.pageCount(id); page++ {
				r.Gallery = append(r.Gallery, *r.page(id, page, "gallery", "", step))
			}
		}
		r.GalleryIndex = 0
	case "Preview":
		if !r.Probe || r.Mode != "" {
			panic("元件預覽不可巢狀開啟")
		}
		r.Saved, r.SavedIndex = r.Page, r.Index
		r.Mode, r.Index = "probe", 0
		r.Page = r.page(entry, 0, "probe", "", step)
	case "F5", "Esc":
		if r.Mode == "probe" {
			r.Page, r.Index, r.Mode = r.Saved, r.SavedIndex, ""
			r.Saved = nil
		} else if r.Mode == "browse" {
			r.Page, r.Index, r.Mode = nil, 0, ""
		} else if key == "F5" {
			r.Mode, r.Index = "browse", 0
			if r.Last == 0 {
				r.Page = &readerPage{Heading: r.UI["reader.empty"], Lines: []string{}, Box: [4]int{16, 16, 624, 256}, Step: step, Mode: "browse", Footer: r.UI["reader.browse_hint"]}
			} else {
				r.Page = r.page(r.Last, 0, "browse", r.Seen[r.Last], step)
			}
		}
	case "PgUp", "PgDn":
		if r.Page != nil && r.Page.Entry != 0 {
			next := r.Index + 1
			if key == "PgUp" {
				next = r.Index - 1
			}
			count := r.pageCount(r.Page.Entry)
			if next >= 0 && next < count {
				r.Index = next
				r.Page = r.page(r.Page.Entry, next, r.Mode, r.Page.SourceKey, step)
			}
		}
	case "Left", "Right":
		if r.Mode == "browse" && len(r.Seen) > 0 {
			ids := r.seenIDs()
			at := sort.SearchInts(ids, r.Page.Entry)
			if key == "Right" {
				at++
			} else {
				at--
			}
			at = (at + len(ids)) % len(ids)
			r.Index = 0
			r.Page = r.page(ids[at], 0, "browse", r.Seen[ids[at]], step)
		}
	}
	r.UIEvents = append(r.UIEvents, map[string]any{"step": step, "frame": len(g.frames), "key": key, "source": source, "entry": entry, "page": r.Page})
}

func (g *liveGame) tickReader() bool {
	r := g.reader
	if r == nil {
		return false
	}
	// Ebiten 可在同一 Draw 前補跑多次 Update；閱讀操作須先提交一張完整畫格。
	if r.WaitDraw {
		return true
	}
	if !r.Ready {
		return false
	}
	if r.Gallery != nil {
		if r.GalleryIndex < len(r.Gallery) {
			page := r.Gallery[r.GalleryIndex]
			r.Page = &page
			r.GalleryFrames = append(r.GalleryFrames, map[string]any{"step": g.o.Steps(), "frame": len(g.frames), "entry": page.Entry, "page": max(1, page.Number)})
			r.GalleryIndex++
		} else {
			r.Gallery = nil
			r.Page, r.Index = r.Saved, r.SavedIndex
			r.Saved = nil
		}
		r.WaitDraw = true
		return true
	}
	if r.ControlIndex < len(r.Controls) {
		c := r.Controls[r.ControlIndex]
		if c.At < g.o.Steps() {
			panic("查閱控制時點已越過")
		}
		if c.At == g.o.Steps() {
			r.ControlIndex++
			source := "script"
			if c.Key == "Gallery" || c.Key == "Preview" {
				source = "probe"
			}
			g.readerKey(c.Key, source, c.Entry)
			r.WaitDraw = true
			return true
		}
	}
	if r.Live {
		if r.Page != nil && r.Page.Image != nil {
			for _, k := range []struct {
				code ebiten.Key
				name string
			}{
				{ebiten.KeyEqual, "ZoomIn"}, {ebiten.KeyMinus, "ZoomOut"}, {ebiten.KeyA, "PanLeft"}, {ebiten.KeyD, "PanRight"},
				{ebiten.KeyW, "PanUp"}, {ebiten.KeyS, "PanDown"}, {ebiten.KeyHome, "Home"},
			} {
				if inpututil.IsKeyJustPressed(k.code) {
					g.readerKey(k.name, "keyboard", 0)
					r.WaitDraw = true
					return true
				}
			}
		}
		for _, k := range []struct {
			code ebiten.Key
			name string
		}{{ebiten.KeyF5, "F5"}, {ebiten.KeyPageUp, "PgUp"}, {ebiten.KeyPageDown, "PgDn"}, {ebiten.KeyArrowLeft, "Left"}, {ebiten.KeyArrowRight, "Right"}, {ebiten.KeyEscape, "Esc"}} {
			if inpututil.IsKeyJustPressed(k.code) && (k.name == "F5" || (r.Page != nil && (k.name == "PgUp" || k.name == "PgDn")) || r.Mode != "") {
				g.readerKey(k.name, "keyboard", 0)
				r.WaitDraw = true
				return true
			}
		}
	}
	if r.Mode != "" {
		if r.Live {
			time.Sleep(15 * time.Millisecond)
		}
		return true
	}
	return false
}

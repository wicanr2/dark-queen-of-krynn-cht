// DRAFT：已校讀手札的單頁自動顯示；不改原版按鍵、記憶體或時序。
package main

import (
	"fmt"
	"os"
	"strconv"
	"strings"
)

const journalTemplateKey = "ui.aa93370ee0689e9a462e"

type readerPage struct {
	Entry     int
	Heading   string
	Lines     []string
	Box       [4]int
	Step      uint64 `json:"step"`
	SourceKey string
}

type journalReader struct {
	SHA256  string
	Entries map[int]readerPage
	Page    *readerPage
	Events  []map[string]any
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
	if len(lines) == 0 || len(lines) > 13 {
		panic("手札超出單頁原型容量")
	}
	return lines
}

func (g *liveGame) installReader(path string) {
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
	r := &journalReader{SHA256: digest(data), Entries: map[int]readerPage{}}
	for key, body := range catalog {
		if key == "reader.heading" || strings.HasSuffix(key, ".title") {
			continue
		}
		idText := strings.TrimSuffix(strings.TrimPrefix(key, "journal."), ".body")
		id, err := strconv.Atoi(idText)
		if err != nil || id < 1 || id > 99 || key != fmt.Sprintf("journal.%d.body", id) || catalog[fmt.Sprintf("journal.%d.title", id)] == "" {
			panic("手札鍵或標題不符")
		}
		p := readerPage{Entry: id, Heading: fmt.Sprintf(heading, idText, catalog[fmt.Sprintf("journal.%d.title", id)]), Lines: readerLines(body), Box: [4]int{16, 16, 624, 256}}
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
		r.Entries[id] = p
	}
	if len(r.Entries) == 0 || len(catalog) != 1+len(r.Entries)*2 {
		panic("手札缺頁或含未知鍵")
	}
	g.reader = r
}

func (g *liveGame) closeReader() {
	if g.reader != nil && g.reader.Page != nil {
		g.reader.Events = append(g.reader.Events, map[string]any{"step": g.o.Steps(), "action": "close", "entry": g.reader.Page.Entry, "reason": "next paragraph"})
		g.reader.Page = nil
	}
}

func (g *liveGame) openReader(p *listParagraph) {
	if g.reader == nil || p.JournalEntry == 0 {
		return
	}
	page, ok := g.reader.Entries[p.JournalEntry]
	if !ok {
		g.reader.Events = append(g.reader.Events, map[string]any{"step": g.o.Steps(), "action": "unavailable", "entry": p.JournalEntry, "source_key": p.Key})
		return
	}
	page.Step, page.SourceKey = g.o.Steps(), p.Key
	g.reader.Page = &page
	g.reader.Events = append(g.reader.Events, map[string]any{"step": page.Step, "action": "open", "page": page})
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
	for row, text := range append([]string{p.Heading}, p.Lines...) {
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

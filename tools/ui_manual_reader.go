// DRAFT：獨立手冊目錄與正文；只讀私有 TSV，不加入手札已讀或原版輸入。
package main

import (
	"encoding/json"
	"fmt"
	"os"
	"regexp"
	"strconv"
	"strings"
	"unicode/utf8"
)

type manualDocument struct {
	ID         string   `json:"id"`
	SourcePage int      `json:"source_page"`
	TitleKey   string   `json:"title_key"`
	BodyKey    string   `json:"body_key"`
	Kind       string   `json:"kind"`
	Lines      []string `json:"-"`
}

type manualBook struct {
	ID        string           `json:"id"`
	TitleKey  string           `json:"title_key"`
	Documents []manualDocument `json:"documents"`
}

type manualReader struct {
	Version            int               `json:"version"`
	Books              []manualBook      `json:"books"`
	UI                 map[string]string `json:"-"`
	SHA, IndexSHA      string
	Book, Cursor, Part int
	Reading            bool
	Page               *readerPage
	Saved              *readerPage
	SavedIndex         int
	Events             []map[string]any
}

var manualTokens = regexp.MustCompile(`-?\d+|[A-Za-z]+(?:[-'][A-Za-z]+)*|.`)

func manualLines(body string) []string {
	var lines []string
	for _, paragraph := range strings.Split(body, `\n`) {
		if paragraph == "" {
			lines = append(lines, "")
			continue
		}
		boundaries := map[int]bool{}
		for _, match := range manualTokens.FindAllStringIndex(paragraph, -1) {
			boundaries[utf8.RuneCountInString(paragraph[:match[1]])] = true
		}
		chars := []rune(paragraph)
		for at := 0; at < len(chars); {
			end := min(at+38, len(chars))
			for end > at && (!boundaries[end] || (end < len(chars) &&
				(strings.ContainsRune("，。！？、；：」』）》】", chars[end]) || strings.ContainsRune("「『（《【", chars[end-1])))) {
				end--
			}
			if end == at {
				panic("手冊無安全斷行")
			}
			lines = append(lines, string(chars[at:end]))
			at = end
		}
	}
	if len(lines) == 0 || len(lines) > 8192 {
		panic("手冊容量不符")
	}
	return lines
}

func (g *liveGame) validateManualText(text string, width int) {
	if len([]rune(text)) > width {
		panic("手冊文字超出安全框")
	}
	for _, ch := range text {
		alpha := g.glyphs.Glyphs[string(ch)]
		if ch < 32 || len(alpha) != 320 {
			panic("手冊缺字或含控制字元")
		}
		for _, a := range alpha[256:] {
			if a != 0 {
				panic("手冊字墨超出列高")
			}
		}
	}
}

func (g *liveGame) installManual(path, index string) {
	if g.reader == nil || !g.reader.Ready || path == "" || index == "" {
		panic("手冊需要完整手札閱讀元件及獨立資料")
	}
	data, err := os.ReadFile(index)
	must(err)
	m := &manualReader{UI: readLiveCatalog(path), IndexSHA: digest(data)}
	must(json.Unmarshal(data, m))
	data, err = os.ReadFile(path)
	must(err)
	m.SHA = digest(data)
	if m.Version != 1 || len(m.Books) != 3 {
		panic("手冊索引版本或冊數不符")
	}
	expected := map[string]bool{}
	for key, placeholders := range map[string]int{
		"manual.index_heading": 1, "manual.document_heading": 3, "manual.index_item": 3,
		"manual.index_hint": 0, "manual.document_hint": 2, "manual.image_pending": 0,
		"manual.selected": 0, "manual.cell": 2,
	} {
		text := m.UI[key]
		if text == "" || strings.Count(text, "%s") != placeholders || strings.Contains(strings.ReplaceAll(text, "%s", ""), "%") {
			panic("手冊介面詞條不符")
		}
		expected[key] = true
	}
	ids := map[string]bool{}
	for i := range m.Books {
		book := &m.Books[i]
		if book.ID != []string{"operation", "adventurer", "appendix"}[i] || book.TitleKey != "manual.book."+book.ID ||
			len(book.Documents) == 0 || len(book.Documents) > 1024 || m.UI[book.TitleKey] == "" {
			panic("手冊分冊不符")
		}
		expected[book.TitleKey] = true
		g.validateManualText(fmt.Sprintf(m.UI["manual.index_heading"], m.UI[book.TitleKey]), 37)
		for j := range book.Documents {
			doc := &book.Documents[j]
			if doc.ID == "" || ids[doc.ID] || doc.SourcePage < 1 || doc.SourcePage > 999 ||
				m.UI[doc.TitleKey] == "" || m.UI[doc.BodyKey] == "" ||
				(doc.Kind != "body" && doc.Kind != "table" && doc.Kind != "illustration-pending") {
				panic("手冊文章或來源頁不符")
			}
			ids[doc.ID], expected[doc.TitleKey], expected[doc.BodyKey] = true, true, true
			if (doc.Kind == "illustration-pending") != (doc.BodyKey == "manual.image_pending") {
				panic("手冊圖稿狀態不符")
			}
			doc.Lines = manualLines(m.UI[doc.BodyKey])
			for _, line := range doc.Lines {
				g.validateManualText(line, 38)
			}
			g.validateManualText(m.heading(book, doc), 37)
			g.validateManualText(fmt.Sprintf(m.UI["manual.index_item"], m.UI["manual.selected"], strconv.Itoa(doc.SourcePage), m.UI[doc.TitleKey]), 38)
			count := (len(doc.Lines) + 12) / 13
			g.validateManualText(fmt.Sprintf(m.UI["manual.document_hint"], strconv.Itoa(count), strconv.Itoa(count)), 38)
		}
	}
	if len(expected) != len(m.UI) {
		panic("手冊含孤兒詞條")
	}
	g.validateManualText(m.UI["manual.index_hint"], 38)
	g.reader.Manual = m
}

func (m *manualReader) heading(book *manualBook, doc *manualDocument) string {
	return fmt.Sprintf(m.UI["manual.document_heading"], m.UI[book.TitleKey], strconv.Itoa(doc.SourcePage), m.UI[doc.TitleKey])
}

func (m *manualReader) refresh(step uint64) {
	book := &m.Books[m.Book]
	p := &readerPage{Box: [4]int{16, 16, 624, 256}, Step: step}
	if m.Reading {
		doc := &book.Documents[m.Cursor]
		count := (len(doc.Lines) + 12) / 13
		p.Heading, p.SourceKey, p.Mode = m.heading(book, doc), doc.BodyKey, "manual-body"
		p.Lines = doc.Lines[m.Part*13 : min((m.Part+1)*13, len(doc.Lines))]
		p.Number, p.Count = m.Part+1, count
		p.Footer = fmt.Sprintf(m.UI["manual.document_hint"], strconv.Itoa(m.Part+1), strconv.Itoa(count))
	} else {
		p.Heading, p.Mode, p.Footer = fmt.Sprintf(m.UI["manual.index_heading"], m.UI[book.TitleKey]), "manual-index", m.UI["manual.index_hint"]
		first := m.Cursor / 13 * 13
		for j := first; j < min(first+13, len(book.Documents)); j++ {
			doc := book.Documents[j]
			marker := " "
			if j == m.Cursor {
				marker = m.UI["manual.selected"]
			}
			p.Lines = append(p.Lines, fmt.Sprintf(m.UI["manual.index_item"], marker, strconv.Itoa(doc.SourcePage), m.UI[doc.TitleKey]))
		}
	}
	m.Page = p
}

func (g *liveGame) manualKey(key, source string) {
	r, step := g.reader, g.o.Steps()
	m := r.Manual
	if m == nil {
		panic("未載入手冊")
	}
	if key == "F6" {
		if r.Mode == "manual" {
			r.Page, r.Index, r.Mode = m.Saved, m.SavedIndex, ""
			m.Page, m.Saved = nil, nil
		} else if r.Mode == "" {
			m.Saved, m.SavedIndex = r.Page, r.Index
			r.Mode, m.Reading, m.Part = "manual", false, 0
			m.refresh(step)
		}
	} else if r.Mode == "manual" {
		book := &m.Books[m.Book]
		if m.Reading {
			count := (len(book.Documents[m.Cursor].Lines) + 12) / 13
			switch key {
			case "PgUp":
				m.Part = max(0, m.Part-1)
			case "PgDn":
				m.Part = min(count-1, m.Part+1)
			case "Esc":
				m.Reading, m.Part = false, 0
			}
		} else {
			switch key {
			case "Left":
				m.Book, m.Cursor = (m.Book+len(m.Books)-1)%len(m.Books), 0
			case "Right":
				m.Book, m.Cursor = (m.Book+1)%len(m.Books), 0
			case "Up":
				m.Cursor = max(0, m.Cursor-1)
			case "Down":
				m.Cursor = min(len(book.Documents)-1, m.Cursor+1)
			case "PgUp":
				m.Cursor = max(0, m.Cursor-13)
			case "PgDn":
				m.Cursor = min(len(book.Documents)-1, m.Cursor+13)
			case "Return":
				m.Reading, m.Part = true, 0
			case "Esc":
				r.Page, r.Index, r.Mode = m.Saved, m.SavedIndex, ""
				m.Page, m.Saved = nil, nil
			}
		}
		if r.Mode == "manual" {
			m.refresh(step)
		}
	}
	m.Events = append(m.Events, map[string]any{"step": step, "frame": len(g.frames), "key": key, "source": source,
		"book": m.Books[m.Book].ID, "cursor": m.Cursor, "part": m.Part, "reading": m.Reading, "page": m.Page})
}

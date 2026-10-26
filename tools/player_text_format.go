package main

import (
	"fmt"
	"regexp"
	"strings"
)

type displayFormatPart struct {
	Literal string
	Kind    byte
}

type displayTextRow struct{ X, Y, Width, Count int }
type displayTextLayout struct{ Rows []displayTextRow }

func (p *displayTextLayout) Add(x, y, firstWidth int) bool {
	if x < 0 || y < 0 || x+8 > 320 || y+8 > 200 {
		return false
	}
	if len(p.Rows) == 0 {
		p.Rows = append(p.Rows, displayTextRow{X: x, Y: y, Width: max(8, firstWidth)})
	}
	i := len(p.Rows) - 1
	row := &p.Rows[i]
	if y != row.Y || x != row.X+row.Count*8 {
		if y < row.Y+8 || len(p.Rows) >= 25 {
			return false
		}
		p.Rows = append(p.Rows, displayTextRow{X: x, Y: y, Width: 8})
		row = &p.Rows[len(p.Rows)-1]
	}
	row.Count++
	row.Width = max(row.Width, row.Count*8)
	return row.X+row.Width <= 320
}

func (p displayTextLayout) Pack(text string) ([]string, bool) {
	runes := []rune(text)
	result := make([]string, len(p.Rows))
	at := 0
	for i, row := range p.Rows {
		end := min(len(runes), at+row.Width/8)
		result[i] = string(runes[at:end])
		at = end
	}
	return result, at == len(runes)
}

type displayFormat struct {
	Key          string
	Pattern      *regexp.Regexp
	Target       []displayFormatPart
	Kinds        []byte
	LiteralBytes int
}

// 只辨識原目錄的欄位標記；不讀原版varargs、不模擬原版格式化器。
func splitDisplayFormat(text string) ([]displayFormatPart, []byte, error) {
	parts, kinds := []displayFormatPart{}, []byte{}
	var literal strings.Builder
	for i := 0; i < len(text); i++ {
		if text[i] != '%' {
			literal.WriteByte(text[i])
			continue
		}
		if i+1 >= len(text) {
			return nil, nil, fmt.Errorf("不完整欄位")
		}
		i++
		if text[i] == '%' {
			literal.WriteByte('%')
			continue
		}
		if !strings.ContainsRune("sducr", rune(text[i])) {
			return nil, nil, fmt.Errorf("未知欄位 %%%c", text[i])
		}
		parts = append(parts, displayFormatPart{Literal: literal.String()}, displayFormatPart{Kind: text[i]})
		literal.Reset()
		kinds = append(kinds, text[i])
	}
	parts = append(parts, displayFormatPart{Literal: literal.String()})
	return parts, kinds, nil
}

func compileDisplayFormat(key, source, translated string) (displayFormat, error) {
	input, kinds, err := splitDisplayFormat(source)
	if err != nil {
		return displayFormat{}, err
	}
	output, targetKinds, err := splitDisplayFormat(translated)
	if err != nil || len(kinds) == 0 || string(kinds) != string(targetKinds) {
		return displayFormat{}, fmt.Errorf("來源／譯文欄位不一致：%s", key)
	}
	var expression strings.Builder
	literalBytes := 0
	expression.WriteString("^")
	for _, part := range input {
		switch part.Kind {
		case 0:
			expression.WriteString(regexp.QuoteMeta(part.Literal))
			literalBytes += len(part.Literal)
		case 'd':
			expression.WriteString(`( *[+-]?[0-9]+)`)
		case 'u':
			expression.WriteString(`( *[0-9]+)`)
		case 'c':
			expression.WriteString(`(.)`)
		default:
			expression.WriteString(`(.*?)`)
		}
	}
	expression.WriteString("$")
	pattern, err := regexp.Compile(expression.String())
	return displayFormat{Key: key, Pattern: pattern, Target: output, Kinds: kinds, LiteralBytes: literalBytes}, err
}

var displayItemValue = regexp.MustCompile(`^([0-9]+ +)?(.+?)( *[+-][0-9]+)?$`)

// 僅翻完整正式名稱，數量與加值依原輸出逐字保留。
func translateDisplayValue(value string, lookup func(string) string) string {
	core := strings.TrimSpace(value)
	if core == "" {
		return value
	}
	if text := lookup(core); text != "" {
		return strings.Replace(value, core, text, 1)
	}
	match := displayItemValue.FindStringSubmatch(core)
	if len(match) == 4 && (match[1] != "" || match[3] != "") {
		if text := lookup(match[2]); text != "" {
			return strings.Replace(value, core, match[1]+text+match[3], 1)
		}
	}
	return value
}

func (f displayFormat) Render(printed string, translate func(string) string) (string, bool) {
	match := f.Pattern.FindStringSubmatch(printed)
	if len(match) != len(f.Kinds)+1 {
		return "", false
	}
	var result strings.Builder
	at := 1
	for _, part := range f.Target {
		if part.Kind == 0 {
			result.WriteString(part.Literal)
			continue
		}
		value := match[at]
		at++
		if part.Kind == 's' && translate != nil {
			value = translate(value)
		}
		result.WriteString(value)
	}
	return result.String(), true
}

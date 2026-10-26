package main

import (
	"encoding/csv"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestDisplayValueKeepsAmmunitionCountAndBonus(t *testing.T) {
	lookup := func(s string) string {
		if strings.EqualFold(s, "Arrows") {
			return "箭矢"
		}
		if strings.EqualFold(s, "Long Sword") {
			return "長劍"
		}
		return ""
	}
	for _, pair := range [][2]string{{"30 ARROWS +1", "30 箭矢 +1"}, {"1 Arrows +2", "1 箭矢 +2"}, {"Long Sword -1", "長劍 -1"}, {"Hero-One +7", "Hero-One +7"}} {
		if actual := translateDisplayValue(pair[0], lookup); actual != pair[1] {
			t.Fatalf("%q => %q", pair[0], actual)
		}
	}
}

func TestFormalDisplayFormats(t *testing.T) {
	root := os.Getenv("DQK_FORMAT_CORPUS")
	if root == "" {
		t.Skip("needs local player catalog")
	}
	read := func(name string) map[string]string {
		file, err := os.Open(filepath.Join(root, name))
		if err != nil {
			t.Fatal(err)
		}
		defer file.Close()
		r := csv.NewReader(file)
		r.Comma = '\t'
		r.LazyQuotes = true
		rows, err := r.ReadAll()
		if err != nil {
			t.Fatal(err)
		}
		result := map[string]string{}
		for _, row := range rows[1:] {
			if len(row) != 2 {
				t.Fatal("invalid TSV")
			}
			result[row[0]] = row[1]
		}
		return result
	}
	en, zh := read("display-format.en.tsv"), read("display-format.zh-TW.tsv")
	if len(en) != 67 || len(zh) != len(en) {
		t.Fatalf("format catalogs: %d/%d", len(en), len(zh))
	}
	for key, source := range en {
		if _, err := compileDisplayFormat(key, source, zh[key]); err != nil {
			t.Fatal(err)
		}
	}
}

func TestDisplayFormatPreservesVariables(t *testing.T) {
	for _, test := range []struct{ source, target, printed, want string }{
		{"takes %d%s", "受到%d%s", "takes 27 damage", "受到27 damage"},
		{"%d:%s PM", "下午 %d:%s", "7:04 PM", "下午 7:04"},
		{"I'll give you %u steel pieces for your %s", "我願出 %u 枚鋼幣收購你的 %s", "I'll give you 1250 steel pieces for your Long Sword +2", "我願出 1250 枚鋼幣收購你的 長劍 +2"},
		{"Save %s?", "要儲存 %s 嗎？", "Save Hero-One?", "要儲存 Hero-One 嗎？"},
		{"Disk %c", "磁片 %c", "Disk C", "磁片 C"},
		{"Error: %r", "錯誤：%r", "Error: 0x27", "錯誤：0x27"},
	} {
		f, err := compileDisplayFormat("fixture", test.source, test.target)
		if err != nil {
			t.Fatal(err)
		}
		actual, ok := f.Render(test.printed, func(s string) string {
			if s == "Long Sword +2" {
				return "長劍 +2"
			}
			return s
		})
		if !ok || actual != test.want {
			t.Fatalf("%q => %q, want %q", test.printed, actual, test.want)
		}
	}
}

func TestDisplayFormatRejectsChangedContract(t *testing.T) {
	for _, pair := range [][2]string{{"Save %s?", "儲存%d？"}, {"%d years", "%s年"}, {"%q", "%q"}, {"Hello%", "你好%"}} {
		if _, err := compileDisplayFormat("fixture", pair[0], pair[1]); err == nil {
			t.Fatalf("accepted changed contract %v", pair)
		}
	}
	f, err := compileDisplayFormat("clock", "%d:%s PM", "下午%d:%s")
	if err != nil {
		t.Fatal(err)
	}
	for _, invalid := range []string{"x:04 PM", "7:04 AM", "prefix 7:04 PM"} {
		if _, ok := f.Render(invalid, nil); ok {
			t.Fatalf("accepted %q", invalid)
		}
	}
}

func TestDisplayLayoutUsesOnlyOriginalRows(t *testing.T) {
	var layout displayTextLayout
	for row, count := range []int{38, 37, 7} {
		for x := 0; x < count; x++ {
			if !layout.Add(8+x*8, 136+row*12, 8) {
				t.Fatal("valid original row rejected")
			}
		}
	}
	text := "你們離開時，店主說：「打擾了，各位還有錢留在這裡。」"
	packed, ok := layout.Pack(text)
	if !ok || packed[0] != text || packed[1] != "" || packed[2] != "" {
		t.Fatal(packed, ok)
	}
	if _, ok = layout.Pack(strings.Repeat("字", 83)); ok {
		t.Fatal("accepted overflowing translation")
	}
	if layout.Add(312, 200, 8) || layout.Add(8, 136, 8) {
		t.Fatal("accepted outside or overlapping row")
	}
}

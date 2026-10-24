package main

import (
	"bufio"
	"encoding/json"
	"os"
	"strings"
	"testing"
)

func hudTestCatalog(t *testing.T, variable string) map[string]string {
	t.Helper()
	path := os.Getenv(variable)
	if path == "" {
		t.Skip("缺少原版校讀資料：" + variable)
	}
	f, err := os.Open(path)
	if err != nil {
		t.Fatal(err)
	}
	defer f.Close()
	r := bufio.NewScanner(f)
	if !r.Scan() || r.Text() != "key\ttext" {
		t.Fatal("TSV 欄位不符")
	}
	result := map[string]string{}
	for r.Scan() {
		row := strings.Split(r.Text(), "\t")
		if len(row) != 2 {
			t.Fatal("TSV 欄數不符")
		}
		result[row[0]] = row[1]
	}
	if err := r.Err(); err != nil {
		t.Fatal(err)
	}
	return result
}

func TestHUDIntegerOriginalMagicText(t *testing.T) {
	en, zh := hudTestCatalog(t, "DQK_UI_EN"), hudTestCatalog(t, "DQK_UI_ZH")
	pattern := func(values map[string]string) string {
		base := strings.Replace(values["ui.0047c0cbccc6f94c1ac8"], "%s", values["ui.f5e1d63728c2e2d27737"], 1)
		return strings.Replace(values["ui.d4d4cdcd08b7f8cdfb44"], "%s", base, 1)
	}
	path := os.Getenv("DQK_MAGIC_SOURCE")
	if path == "" {
		t.Skip("缺少正常法術來源")
	}
	raw, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	var trace struct {
		Paragraphs []struct {
			Source    struct{ Text string }
			NativeBox [4]int `json:"native_box"`
		}
	}
	if err = json.Unmarshal(raw, &trace); err != nil {
		t.Fatal(err)
	}
	count := 0
	for _, p := range trace.Paragraphs {
		value, ok := hudInteger(p.Source.Text, pattern(en))
		if !ok {
			continue
		}
		count++
		if value != 16 || p.NativeBox != ([4]int{184, 88, 312, 176}) {
			t.Fatal("原版來源或數值改變")
		}
		original, ok := hudIntegerText(pattern(en), value)
		if !ok || original != p.Source.Text {
			t.Fatal("原文參數未往返")
		}
		translated, ok := hudIntegerText(pattern(zh), value)
		if !ok || strings.Count(translated, "16") != 1 || strings.Contains(translated, "%") {
			t.Fatal("譯文數值或格式不符")
		}
	}
	if count != 7 {
		t.Fatalf("正常來源數不符：%d", count)
	}
}

func TestHUDIntegerRejectsDifferentText(t *testing.T) {
	pattern := "takes %d points of damage from Magic"
	for _, source := range []string{"takes 016 points of damage from Magic", "takes +16 points of damage from Magic", "takes 16 points of damage from Fire", "takes 16 points of damage from Magic extra", "takes 2147483648 points of damage from Magic"} {
		if _, ok := hudInteger(source, pattern); ok {
			t.Fatal("接受了不同來源：", source)
		}
	}
	for _, bad := range []string{"%d", "takes %d %d points", "takes %d%s points"} {
		if _, ok := hudInteger("takes 16 points", bad); ok {
			t.Fatal("接受未支援格式")
		}
	}
}

func TestHUDIntegerDisplayRoundTrip(t *testing.T) {
	pattern := "takes %d points of damage from Magic"
	for _, value := range []int32{0, -1, 1, 16, 32767, 2147483647, -2147483648} {
		text, ok := hudIntegerText(pattern, value)
		if !ok {
			t.Fatal("格式拒絕")
		}
		actual, ok := hudInteger(text, pattern)
		if !ok || actual != value {
			t.Fatal("顯示參數改變")
		}
	}
}

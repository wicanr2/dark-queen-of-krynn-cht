package main

import (
	"encoding/csv"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestVictoryCounterFromOriginal(t *testing.T) {
	root := "/probe/victory-text-20261025"
	b, err := os.ReadFile(filepath.Join(root, "observe-r2/receipt.json"))
	if os.IsNotExist(err) {
		t.Skip("缺少原版勝利收據")
	}
	if err != nil {
		t.Fatal(err)
	}
	var trace struct {
		EXE   string `json:"exe_sha256"`
		Calls []struct {
			Format struct{ Text string } `json:"format"`
			Source struct{ Text string } `json:"vararg_1_candidate"`
		} `json:"calls"`
	}
	if err := json.Unmarshal(b, &trace); err != nil {
		t.Fatal(err)
	}
	if trace.EXE != "3b41fb06a045568b0c35098a104499d489d8a5c0ef0dd48a039387ba2393ba58" {
		t.Fatal("原版版本不符")
	}
	b, err = os.ReadFile(filepath.Join(root, "inputs-r3/en.tsv"))
	if err != nil {
		t.Fatal(err)
	}
	r := csv.NewReader(strings.NewReader(string(b)))
	r.Comma = '\t'
	rows, err := r.ReadAll()
	if err != nil {
		t.Fatal(err)
	}
	prefix := ""
	for _, row := range rows {
		if row[0] == "victory.aa90baed1dda012893d9" {
			prefix = row[1]
		}
	}
	if prefix == "" {
		t.Fatal("缺少正式前綴")
	}
	matched := 0
	for _, c := range trace.Calls {
		if c.Format.Text == "%s" && strings.HasPrefix(c.Source.Text, prefix) {
			value, ok := prefixedDisplayCount(c.Source.Text, prefix)
			if !ok || value != 3157 {
				t.Fatalf("原版數字解析失敗：%q %d %t", c.Source.Text, value, ok)
			}
			matched++
		}
	}
	if matched != 1 {
		t.Fatal("原版經驗來源數量不符", matched)
	}
	for _, raw := range []string{"0", "1", "3157", "4294967295"} {
		if _, ok := prefixedDisplayCount(prefix+raw, prefix); !ok {
			t.Fatal("拒絕標準數字", raw)
		}
	}
	for _, raw := range []string{"", "00", "03157", "-1", "+1", "3157 ", " 3157", "3157x", "4294967296", "３１５７"} {
		if _, ok := prefixedDisplayCount(prefix+raw, prefix); ok {
			t.Fatal("接受未知格式", raw)
		}
	}
	if _, ok := prefixedDisplayCount(prefix+"3157", ""); ok {
		t.Fatal("接受空前綴")
	}
	if _, ok := prefixedDisplayCount("每位角色獲得3157", prefix); ok {
		t.Fatal("把譯文當成原版識別來源")
	}
}

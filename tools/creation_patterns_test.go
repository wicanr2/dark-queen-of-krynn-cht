package main

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// 正向資料取原版十五條正常輸入收據；未提供原版資料時明確略過。
func TestCreatedNameOriginalCases(t *testing.T) {
	root := os.Getenv("DQK_NAME_CASE_ROOT")
	if root == "" {
		t.Skip("需提供原版姓名長度收據 DQK_NAME_CASE_ROOT")
	}
	l := &listState{sources: map[string]string{"verb": "Save"}}
	f := listField{Key: "verb", SourcePattern: "created-name", SHA256: digest([]byte("Save"))}
	for length := 1; length <= 15; length++ {
		raw, err := os.ReadFile(filepath.Join(root, fmt.Sprintf("length-%02d", length), "observe", "receipt.json"))
		if err != nil {
			t.Fatal(err)
		}
		var receipt struct {
			Calls []struct {
				Candidate struct {
					Text string `json:"text"`
				} `json:"vararg_1_candidate"`
			} `json:"calls"`
		}
		if err := json.Unmarshal(raw, &receipt); err != nil {
			t.Fatal(err)
		}
		want := "Save " + strings.Repeat("A", length) + "? "
		found := false
		for _, c := range receipt.Calls {
			if c.Candidate.Text != want {
				continue
			}
			found = true
			if start, ok := l.fieldStart(f, c.Candidate.Text); !ok || start != 0 {
				t.Fatalf("原版長度 %d 未辨識", length)
			}
		}
		if !found {
			t.Fatalf("原版長度 %d 缺少實際提問", length)
		}
	}
	for _, source := range []string{"Save ? ", "Save " + strings.Repeat("A", 16) + "? ", "Save A?", "SAVE A? ", "Save A\n? "} {
		if _, ok := l.fieldStart(f, source); ok {
			t.Fatalf("不符來源契約仍通過：%q", source)
		}
	}
	// 顯示譯文不能作為原文比較值，即使同時改變呼叫端提供的來源字串。
	l.sources["verb"] = "Changed"
	if _, ok := l.fieldStart(f, "Changed A? "); ok {
		t.Fatal("來源雜湊失配仍通過")
	}
}

func TestAgeUnitKeepsNumericPrefix(t *testing.T) {
	l := &listState{sources: map[string]string{"unit": "years"}}
	f := listField{Key: "unit", SourcePattern: "age-unit", SHA256: digest([]byte("years"))}
	for _, digits := range []string{"0", "7", "28", "123", "60000"} {
		source := digits + " years"
		start, ok := l.fieldStart(f, source)
		if !ok || source[:start] != digits+" " || source[start:] != "years" {
			t.Fatalf("數字前段被納入翻譯：%q", source)
		}
	}
	for _, source := range []string{" years", "-1 years", "A years", "28years", "28 Years", "28 years!"} {
		if _, ok := l.fieldStart(f, source); ok {
			t.Fatalf("不符年齡顯示形狀仍通過：%q", source)
		}
	}
}

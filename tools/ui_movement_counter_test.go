package main

import (
	"encoding/json"
	"os"
	"strings"
	"testing"
)

func TestMovementCounterOriginalText(t *testing.T) {
	prefix := hudTestCatalog(t, "DQK_UI_EN")["ui.5af65b05298fbefb97ac"]
	if prefix == "" {
		t.Fatal("缺少正式移動力前綴")
	}
	seen := map[int32]bool{}
	count := 0
	for _, variable := range []string{"DQK_QUICK_SOURCE", "DQK_MOVEMENT_SOURCE"} {
		path := os.Getenv(variable)
		if path == "" {
			t.Skip("缺少正常移動來源：" + variable)
		}
		raw, err := os.ReadFile(path)
		if err != nil {
			t.Fatal(err)
		}
		var trace struct {
			Calls []struct {
				Format    struct{ Text string }
				Candidate struct{ Text string } `json:"vararg_1_candidate"`
			}
		}
		if err = json.Unmarshal(raw, &trace); err != nil {
			t.Fatal(err)
		}
		for _, call := range trace.Calls {
			if call.Format.Text != "%s" || !strings.HasPrefix(call.Candidate.Text, prefix) {
				continue
			}
			value, ok := movementCounter(call.Candidate.Text, prefix)
			if !ok {
				t.Fatal("拒絕正常原版來源", call.Candidate.Text)
			}
			seen[value] = true
			count++
		}
	}
	if count != 4 || len(seen) != 4 || !seen[9] || !seen[10] || !seen[11] || !seen[12] {
		t.Fatal("正常移動力來源或數值不符", seen, count)
	}
}

func TestMovementCounterRejectsDifferentFormat(t *testing.T) {
	prefix := hudTestCatalog(t, "DQK_UI_EN")["ui.5af65b05298fbefb97ac"]
	for _, suffix := range []string{"", "-1", "+9", "09", "9 ", " 09 ", "  9 ", " 9  ", "12  ", "2147483648", "9 extra"} {
		if _, ok := movementCounter(prefix+suffix, prefix); ok {
			t.Fatal("接受未觀測或非標準格式", suffix)
		}
	}
	if _, ok := movementCounter("9", ""); ok {
		t.Fatal("接受沒有原文前綴的數字")
	}
	if _, ok := movementCounter("other text 9", prefix); ok {
		t.Fatal("接受不同來源")
	}
}

package main

import (
	"encoding/json"
	"os"
	"strings"
	"testing"
)

func TestAmmoRowsFromNormalSplitAndJoin(t *testing.T) {
	en := hudTestCatalog(t, "DQK_AMMO_EN")
	root, yes, no := en["inventory.423c677c12e0b601c34c"], en["answer.yes"], en["answer.no"]
	path := os.Getenv("DQK_AMMO_SOURCE")
	if path == "" {
		t.Skip("缺少本作正常箭堆重播")
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
	seen := map[int32]bool{}
	ready := map[string]bool{}
	count := 0
	for _, call := range trace.Calls {
		text := call.Candidate.Text
		if call.Format.Text != "%s" || !strings.Contains(text, root) {
			continue
		}
		parts, ok := matchAmmoRow(text, root, yes, no)
		if !ok || text[parts.ReadyStart:parts.ReadyStart+len(parts.Ready)] != parts.Ready || text[parts.NameStart:parts.NameStart+len(root)] != root || parts.Bonus != "+2" {
			t.Fatal("正常原版列或文字切片不符", text, parts)
		}
		seen[parts.Quantity], ready[parts.Ready] = true, true
		count++
	}
	for _, n := range []int32{2, 3, 5, 10, 20, 40} {
		if !seen[n] {
			t.Fatal("缺少正常分半／集合數量", n)
		}
	}
	if len(seen) != 6 || !ready[yes] || !ready[no] || count != 28 {
		t.Fatal("正常來源覆蓋不符", seen, ready, count)
	}
}

// 跨作截圖的 +1 只測格式，不宣稱本作已正常取得 +1 箭。
func TestAmmoScreenshotQuantityAndBonusFormat(t *testing.T) {
	en := hudTestCatalog(t, "DQK_AMMO_EN")
	root, yes, no := en["inventory.423c677c12e0b601c34c"], en["answer.yes"], en["answer.no"]
	text := " " + no + "\t 30 " + root + " +1 "
	parts, ok := matchAmmoRow(text, root, yes, no)
	if !ok || parts.Quantity != 30 || parts.Bonus != "+1" || parts.Ready != no || parts.NameStart != 8 {
		t.Fatal("跨作回歸格式未辨識", parts)
	}
}

func TestAmmoRejectsUnprovenText(t *testing.T) {
	en := hudTestCatalog(t, "DQK_AMMO_EN")
	root, yes, no := en["inventory.423c677c12e0b601c34c"], en["answer.yes"], en["answer.no"]
	for _, tail := range []string{" 0 " + root, " -1 " + root, " 02 " + root, " 2147483648 " + root,
		" 20 " + root + " extra", " 20 " + root + " +0", " 20 " + root + " +-1", " 20 " + root + " +01",
		" 20 " + root + " +2147483648", "  20 " + root, "20 " + root, " " + root, " 20 Other"} {
		if _, ok := matchAmmoRow(" "+no+"\t"+tail+" ", root, yes, no); ok {
			t.Fatal("接受未證實格式或名稱", tail)
		}
	}
}

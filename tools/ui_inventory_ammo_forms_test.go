package main

import (
	"encoding/json"
	"os"
	"strings"
	"testing"
)

func TestAmmoBoundaryOriginalForms(t *testing.T) {
	en := hudTestCatalog(t, "DQK_AMMO_FORMS_EN")
	keys := []string{"inventory.05800e70aa10c86f5ab8", "inventory.423c677c12e0b601c34c", "inventory.ea0151c4cf78b351118d", "inventory.d3e53a2e348022ba16a6"}
	seen := map[string]map[string]bool{}
	for _, variable := range []string{"DQK_AMMO_SINGLE_SOURCE", "DQK_AMMO_BOLTS_SOURCE"} {
		path := os.Getenv(variable)
		if path == "" {
			t.Skip("缺少正常單支／弩箭來源：" + variable)
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
			text := call.Candidate.Text
			if call.Format.Text != "%s" || !strings.Contains(text, "\t") {
				continue
			}
			for _, key := range keys {
				parts, ok := matchAmmoRow(text, en[key], en["answer.yes"], en["answer.no"])
				if !ok {
					continue
				}
				if !ammoQuantityMatches(key, parts.Quantity) || text[parts.NameStart:parts.NameStart+len(en[key])] != en[key] {
					t.Fatal("原版詞形、數量或切片不符", text, parts)
				}
				if seen[key] == nil {
					seen[key] = map[string]bool{}
				}
				seen[key][parts.Ready] = true
			}
		}
	}
	for _, key := range keys {
		if !seen[key][en["answer.yes"]] || !seen[key][en["answer.no"]] {
			t.Fatal("缺少原版備妥及卸下詞形", key, seen[key])
		}
	}
}

func TestAmmoBoundaryRejectsNumberMismatch(t *testing.T) {
	for _, key := range []string{"inventory.05800e70aa10c86f5ab8", "inventory.ea0151c4cf78b351118d"} {
		if ammoQuantityMatches(key, 2) || ammoQuantityMatches(key, 0) {
			t.Fatal("接受非單支的單數名稱", key)
		}
	}
	for _, key := range []string{"inventory.423c677c12e0b601c34c", "inventory.d3e53a2e348022ba16a6"} {
		if ammoQuantityMatches(key, 1) || ammoQuantityMatches(key, -1) {
			t.Fatal("接受非多支的複數名稱", key)
		}
	}
	if ammoQuantityMatches("inventory.cab923a670e4baa826aa", 2) {
		t.Fatal("把既有長劍詞條當成彈藥")
	}
}

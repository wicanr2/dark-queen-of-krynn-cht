package main

import (
	"bufio"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func weaponTestInputs(t *testing.T) ([]string, map[string]string, map[string]string) {
	t.Helper()
	dir := os.Getenv("DQK_WEAPON_INPUTS")
	if dir == "" {
		t.Skip("需要本機武器詞表")
	}
	raw, err := os.ReadFile(filepath.Join(dir, "inputs.json"))
	if err != nil {
		t.Fatal(err)
	}
	var cfg struct{ HUDWeaponNames []string }
	if err := json.Unmarshal(raw, &cfg); err != nil {
		t.Fatal(err)
	}
	read := func(name string) map[string]string {
		f, err := os.Open(filepath.Join(dir, name))
		if err != nil {
			t.Fatal(err)
		}
		defer f.Close()
		values := map[string]string{}
		s := bufio.NewScanner(f)
		s.Buffer(make([]byte, 4096), 1<<20)
		if !s.Scan() || s.Text() != "key\ttext" {
			t.Fatal("TSV 標頭不符")
		}
		for s.Scan() {
			row := strings.Split(s.Text(), "\t")
			if len(row) != 2 {
				t.Fatal("TSV 欄數不符")
			}
			if _, exists := values[row[0]]; exists {
				t.Fatal("重複 key")
			}
			values[row[0]] = row[1]
		}
		if err := s.Err(); err != nil {
			t.Fatal(err)
		}
		return values
	}
	return cfg.HUDWeaponNames, read("en.tsv"), read("zh-TW.tsv")
}

func TestHUDWeaponRealSources(t *testing.T) {
	keys, en, zh := weaponTestInputs(t)
	if len(keys) < 20 || !hudWeaponVocabulary(keys, en, zh) {
		t.Fatal("既有術語的批次詞表不符")
	}
	checked, wrapped := 0, 0
	for _, env := range []string{"DQK_WEAPON_NATIVE", "DQK_WEAPON_LEGACY"} {
		path := os.Getenv(env)
		if path == "" {
			t.Fatalf("需要 %s", env)
		}
		raw, err := os.ReadFile(path)
		if err != nil {
			t.Fatal(err)
		}
		var native struct {
			Paragraphs []struct {
				Caller struct{ Seg, Off uint16 }
				Source struct {
					Text string
					NUL  bool `json:"nul_terminated"`
				}
			}
		}
		if err := json.Unmarshal(raw, &native); err != nil {
			t.Fatal(err)
		}
		for _, p := range native.Paragraphs {
			if p.Caller.Seg != 0x088e || p.Caller.Off != 0x097e {
				continue
			}
			if !p.Source.NUL {
				t.Fatal("原版來源未完整結束")
			}
			part, ok := hudWeaponName(keys, en, p.Source.Text)
			switch p.Source.Text {
			case "Staff Sling +2 ", "Long Sword +2 ":
				name := strings.TrimSuffix(p.Source.Text, " +2 ")
				if !ok || part.Name != name || part.Suffix != " +2 " || en[part.Key] != name || zh[part.Key] == "" {
					t.Fatal("真實單行武器來源未辨識")
				}
				checked++
			case "Mace of Disruption ":
				if ok {
					t.Fatal("多行武器不應進單行契約")
				}
				wrapped++
			}
		}
	}
	if checked < 3 || wrapped == 0 {
		t.Fatal("缺少實際短／長武器來源")
	}
	t.Logf("%d 個既有物品詞、%d 次真實單行來源、%d 次多行保留；不是全部名稱已走訪", len(keys), checked, wrapped)
}

func TestHUDWeaponRejectsMismatch(t *testing.T) {
	keys, en, _ := weaponTestInputs(t)
	for _, source := range []string{"Staff Sling", "Staff Sling+2 ", "Staff Sling +0 ", "Staff Sling +02 ",
		"Staff Sling -1 ", "Staff Sling +2\t", "Staff Sling +2  ", "Staff Sling +2a ",
		"2 Staff Sling ", "STAFF SLING +2 ", "Unknown weapon ", "Staff Sling +200 ", ""} {
		if _, ok := hudWeaponName(keys, en, source); ok {
			t.Errorf("錯誤接受 %q", source)
		}
	}
}

func TestHUDWeaponVocabularyGuards(t *testing.T) {
	keys, en, zh := weaponTestInputs(t)
	key := keys[0]
	copyMap := func(old map[string]string) map[string]string {
		result := map[string]string{}
		for k, v := range old {
			result[k] = v
		}
		return result
	}
	for _, name := range []string{"", " leading", "trailing ", "%s", "x+y", "x\\y", "中文", "line\nbreak", "1234567890123456"} {
		bad := copyMap(en)
		bad[key] = name
		if hudWeaponVocabulary(keys, bad, zh) {
			t.Errorf("接受錯誤名稱 %q", name)
		}
	}
	if hudWeaponVocabulary(append(append([]string{}, keys...), key), en, zh) {
		t.Fatal("接受重複名稱")
	}
	bad := copyMap(zh)
	bad[key] = strings.Repeat("字", len(en[key])+1)
	if hudWeaponVocabulary(keys, en, bad) {
		t.Fatal("接受越界譯名")
	}
}

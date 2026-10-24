package main

import (
	"encoding/json"
	"os"
	"testing"
)

func TestOriginalPrefixRealSources(t *testing.T) {
	path := os.Getenv("DQK_PREFIX_FIXTURE")
	if path == "" {
		t.Skip("需要本機正常來源，不能以替代資料冒充")
	}
	raw, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	var fixture struct {
		Cases []struct {
			Binding     originalPrefixBinding
			Observation passageSourceObservation
			ScriptFile  string
		}
	}
	if err := json.Unmarshal(raw, &fixture); err != nil || len(fixture.Cases) != 2 {
		t.Fatalf("來源不符：%v", err)
	}
	for _, c := range fixture.Cases {
		v := c.Observation
		v.Script, err = os.ReadFile(c.ScriptFile)
		if err != nil || !matchOriginalPrefix(c.Binding, v) {
			t.Fatalf("真實來源失配：%v", err)
		}
		for _, name := range []string{"A", "PLAYER NAME", "ABCDEFGHIJKLMNO"} {
			changed := v
			changed.Source = name
			if !matchOriginalPrefix(c.Binding, changed) {
				t.Fatal("原版識別字不得要求相同姓名")
			}
		}
		for name, mutate := range map[string]func(*passageSourceObservation){
			"ds":        func(v *passageSourceObservation) { v.DS++ },
			"pointer":   func(v *passageSourceObservation) { v.PointerOff++ },
			"caller":    func(v *passageSourceObservation) { v.CallerOff++ },
			"kind":      func(v *passageSourceObservation) { v.Kind = 0x80 },
			"opcode":    func(v *passageSourceObservation) { v.Opcode = 0x11 },
			"clear":     func(v *passageSourceObservation) { v.Clear = 0 },
			"cursor":    func(v *passageSourceObservation) { v.RawCursorAfter++ },
			"base":      func(v *passageSourceObservation) { v.RawBaseOffset++ },
			"empty":     func(v *passageSourceObservation) { v.Source = "" },
			"long":      func(v *passageSourceObservation) { v.Source = "ABCDEFGHIJKLMNOP" },
			"control":   func(v *passageSourceObservation) { v.Source = "NAME\n" },
			"non-ascii": func(v *passageSourceObservation) { v.Source = "名字" },
			"truncated": func(v *passageSourceObservation) { v.Script = v.Script[:c.Binding.ChunkBytes-1] },
			"changed-block": func(v *passageSourceObservation) {
				v.Script = append([]byte(nil), v.Script...)
				v.Script[c.Binding.Offset] ^= 1
			},
		} {
			t.Run(name, func(t *testing.T) {
				changed := v
				mutate(&changed)
				if matchOriginalPrefix(c.Binding, changed) {
					t.Fatal("失配來源被接受")
				}
			})
		}
	}
}

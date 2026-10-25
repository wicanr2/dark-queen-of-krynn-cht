package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

func TestPassageRuntimeArchive(t *testing.T) {
	_, _, formal, blocks := passageTestFixtures(t)
	dir := os.Getenv("DQK_RUNTIME_INPUTS")
	if dir == "" {
		t.Skip("需要本機新整句子集")
	}
	var book struct{ Occurrences []passageSourceFixture }
	if err := json.Unmarshal(passageTestFile(t, filepath.Join(dir, "registry.json")), &book); err != nil {
		t.Fatal(err)
	}
	sources := passageTestCatalog(t, filepath.Join(dir, "en.tsv"))
	if len(book.Occurrences) != 219 || len(sources) != 205 {
		t.Fatal("原版批次大小不同")
	}
	checks, continuations := 0, 0
	for _, row := range book.Occurrences {
		b := row.passageSourceBinding
		if b.LeadingContinuation {
			continuations++
		}
		for part, fragment := range b.Fragments {
			v := passageTestView(b, part, blocks[row.Chunk], formal)
			if b.LeadingContinuation && part == 0 {
				v.CallerOff, v.Opcode, v.Clear = 0x1d53, 0x11, 0
			}
			for _, base := range []uint16{0, 0x8000, 0xfff0} {
				v.RawBaseOffset = base
				v.RawCursorAfter = uint16(fragment.End - int(base))
				got, ok := matchPassageSource(b, sources, part, v)
				if !ok || got.Key != b.Key || got.Source != sources[b.Key] || got.Fragments[part] != formal[fragment.Key] {
					t.Fatalf("來源 %d/%d/%d 不符", row.Chunk, b.ChunkOffset, part)
				}
				checks++
			}
			if b.LeadingContinuation && part == 0 {
				bad := v
				bad.Clear = 1
				if _, ok := matchPassageSource(b, sources, part, bad); ok {
					t.Fatal("接續型接受清除旗標")
				}
				bad = v
				bad.Opcode, bad.CallerOff = 0x12, 0x1d81
				if _, ok := matchPassageSource(b, sources, part, bad); ok {
					t.Fatal("接續型接受清除呼叫端")
				}
				old := b
				old.LeadingContinuation = false
				if _, ok := matchPassageSource(old, sources, part, v); ok {
					t.Fatal("未標示接續型仍被接受")
				}
			}
		}
	}
	if continuations != 64 {
		t.Fatal("接續來源數不同")
	}
	t.Logf("205 組／219 處來源，64 處接續型，%d 次含位址環回核對；不代表逐處正常執行", checks)
}

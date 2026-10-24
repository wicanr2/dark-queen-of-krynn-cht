package main

import (
	"bufio"
	"bytes"
	"encoding/binary"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

type passageSourceFixture struct {
	passageSourceBinding
	Chunk int `json:"chunk"`
}

func passageTestFile(t *testing.T, path string) []byte {
	t.Helper()
	if path == "" {
		t.Skip("缺少原始資料路徑，略過實際來源測試")
	}
	raw, err := os.ReadFile(path)
	if os.IsNotExist(err) {
		t.Skipf("缺少原始資料 %s", path)
	}
	if err != nil {
		t.Fatal(err)
	}
	return raw
}

func passageTestCatalog(t *testing.T, path string) map[string]string {
	t.Helper()
	values := map[string]string{}
	s := bufio.NewScanner(bytes.NewReader(passageTestFile(t, path)))
	s.Buffer(make([]byte, 4096), 1<<20)
	if !s.Scan() || s.Text() != "key\ttext" {
		t.Fatal("來源 TSV 標頭不符")
	}
	for s.Scan() {
		row := strings.Split(s.Text(), "\t")
		if len(row) != 2 {
			t.Fatal("來源 TSV 欄數不符")
		}
		if _, ok := values[row[0]]; ok {
			t.Fatal("重複來源 key")
		}
		values[row[0]] = row[1]
	}
	if err := s.Err(); err != nil {
		t.Fatal(err)
	}
	return values
}

func passageTestFixtures(t *testing.T) ([]passageSourceFixture, map[string]string, map[string]string, [][]byte) {
	t.Helper()
	dir := os.Getenv("DQK_PASSAGE_INPUTS")
	if dir == "" {
		t.Skip("未提供既有整句子集")
	}
	var registry struct {
		SourceSHA   string                 `json:"source_sha256"`
		Occurrences []passageSourceFixture `json:"occurrences"`
	}
	if err := json.Unmarshal(passageTestFile(t, filepath.Join(dir, "registry.json")), &registry); err != nil {
		t.Fatal(err)
	}
	raw := passageTestFile(t, os.Getenv("DQK_PASSAGE_LIBRARY"))
	if passageSourceHash(raw) != "40542071e42d3cd125eabcead11456a99942bf55a7736fdb79f66a3c27c3664d" || passageSourceHash(raw) != registry.SourceSHA {
		t.Fatal("原版 ECL.GLB 雜湊不符")
	}
	if len(raw) < 20 || string(raw[:4]) != "HLIB" || int(binary.LittleEndian.Uint32(raw[4:8])) != len(raw) {
		t.Fatal("HLIB 標頭不符")
	}
	count := int(binary.LittleEndian.Uint16(raw[8:10]))
	header := 16 + 4*(count+1)
	if count != 48 || header > len(raw) {
		t.Fatal("HLIB 索引範圍不符")
	}
	blocks := make([][]byte, count)
	for i := 0; i < count; i++ {
		begin := int(binary.LittleEndian.Uint32(raw[16+i*4:]))
		end := int(binary.LittleEndian.Uint32(raw[20+i*4:]))
		if begin < header || end < begin || end > len(raw) {
			t.Fatal("HLIB 區塊越界")
		}
		blocks[i] = raw[begin:end]
	}
	sources := passageTestCatalog(t, filepath.Join(dir, "en.tsv"))
	formal := passageTestCatalog(t, os.Getenv("DQK_PASSAGE_FORMAL_EN"))
	if len(registry.Occurrences) != 155 || len(sources) != 144 {
		t.Fatal("既有子集數量不符")
	}
	return registry.Occurrences, sources, formal, blocks
}

func passageTestView(b passageSourceBinding, part int, block []byte, formal map[string]string) passageSourceObservation {
	opcode, clear, caller := byte(0x12), byte(1), uint16(0x1d81)
	if part != 0 {
		opcode, clear, caller = 0x11, 0, 0x1d53
	}
	return passageSourceObservation{DS: 0x333e, PointerSeg: 0x333e, PointerOff: 0xb487, CallerSeg: 0x26b4, CallerOff: caller,
		RawBaseOffset: 0x8000, RawCursorAfter: uint16(b.Fragments[part].End - 0x8000), Kind: 0x80, Opcode: opcode, Clear: clear,
		Script: block, Source: formal[b.Fragments[part].Key]}
}

func TestPassageSourceRealArchive(t *testing.T) {
	fixtures, sources, formal, blocks := passageTestFixtures(t)
	observations := 0
	fragments := map[string]bool{}
	for _, fixture := range fixtures {
		b := fixture.passageSourceBinding
		for i, part := range b.Fragments {
			view := passageTestView(b, i, blocks[fixture.Chunk], formal)
			for _, base := range []uint16{0, 0x8000, 0xfff0} {
				view.RawBaseOffset = base
				view.RawCursorAfter = uint16(part.End - int(base))
				got, ok := matchPassageSource(b, sources, i, view)
				if !ok || got.Key != b.Key || got.Source != sources[b.Key] || got.Part != i || got.Fragments[i] != formal[part.Key] {
					t.Fatalf("原始區塊 %d／%x／片段 %d 不符", fixture.Chunk, b.ChunkOffset, i)
				}
				observations++
			}
			fragments[part.Key] = true
		}
	}
	if len(fragments) != 306 {
		t.Fatal("片段鍵數不符")
	}
	t.Logf("155 處來源、144 則整句、306 個片段鍵、%d 次含位址環回的辨識核對；不是原版執行順序驗收", observations)
}

func TestPassageSourceRejectsMismatch(t *testing.T) {
	fixtures, sources, formal, blocks := passageTestFixtures(t)
	original := fixtures[0]
	for _, name := range []string{"kind", "opcode", "caller", "pointer", "ds", "clear", "cursor", "source", "chunk-hash", "packet-hash", "negative-start", "truncated", "fragment-key", "gap", "unknown-opcode", "indirect", "zero-length", "catalog"} {
		t.Run(name, func(t *testing.T) {
			b := original.passageSourceBinding
			b.Fragments = append([]passageSourceFragment{}, b.Fragments...)
			view := passageTestView(b, 0, append([]byte{}, blocks[original.Chunk]...), formal)
			catalog := sources
			rehash := false
			switch name {
			case "kind":
				view.Kind = 0x81
			case "opcode":
				view.Opcode = 0x11
			case "caller":
				view.CallerOff++
			case "pointer":
				view.PointerOff++
			case "ds":
				view.DS++
			case "clear":
				view.Clear = 0
			case "cursor":
				view.RawCursorAfter++
			case "source":
				view.Source += " "
			case "chunk-hash":
				b.ChunkSHA256 = strings.Repeat("0", 64)
			case "packet-hash":
				b.PacketSHA256 = strings.Repeat("0", 64)
			case "negative-start":
				b.ChunkOffset = -1
			case "truncated":
				view.Script = view.Script[:len(view.Script)-1]
			case "fragment-key":
				b.Fragments[1].Key = "ecl." + strings.Repeat("0", 20)
			case "gap":
				b.Fragments[1].Offset++
			case "unknown-opcode":
				view.Script[b.Fragments[1].Offset] = 0x18
				rehash = true
			case "indirect":
				view.Script[b.Fragments[1].Offset+1] = 0x81
				rehash = true
			case "zero-length":
				view.Script[b.ChunkOffset+2] = 0
				b.Fragments[0].PackedLength = 0
				rehash = true
			case "catalog":
				catalog = map[string]string{b.Key: sources[b.Key] + " "}
			}
			if rehash {
				b.ChunkSHA256 = passageSourceHash(view.Script)
				b.PacketSHA256 = passageSourceHash(view.Script[b.ChunkOffset:b.EndChunkOffset])
			}
			if _, ok := matchPassageSource(b, catalog, 0, view); ok {
				t.Fatal("接受失配來源")
			}
		})
	}
	view := passageTestView(original.passageSourceBinding, 0, append(append([]byte{}, blocks[original.Chunk]...), 0xa5), formal)
	if _, ok := matchPassageSource(original.passageSourceBinding, sources, 0, view); !ok {
		t.Fatal("誤將區塊外記憶體當作區塊身分")
	}
}

func TestPassageSourceRealBarFallback(t *testing.T) {
	fixtures, sources, _, _ := passageTestFixtures(t)
	path := os.Getenv("DQK_PASSAGE_NATIVE")
	var native struct {
		Paragraphs []struct {
			Caller    struct{ Seg, Off uint16 }
			Regs      struct{ DS uint16 }
			Source    string
			Pointer   struct{ Seg, Off uint16 } `json:"source_pointer"`
			Base      struct{ Seg, Off uint16 } `json:"raw_ae5c"`
			Cursor    uint16                    `json:"raw_b7f9"`
			Kind      byte                      `json:"raw_b216"`
			Opcode    byte                      `json:"raw_b1c7"`
			Clear     byte
			ScriptSHA string `json:"script_sha256"`
		}
		Files map[string]struct{ File string } `json:"script_files"`
	}
	if err := json.Unmarshal(passageTestFile(t, path), &native); err != nil {
		t.Fatal(err)
	}
	if len(native.Paragraphs) != 4 {
		t.Fatal("正常酒館來源數不符")
	}
	for _, p := range native.Paragraphs {
		raw := passageTestFile(t, filepath.Join(filepath.Dir(path), native.Files[p.ScriptSHA].File))
		if passageSourceHash(raw) != p.ScriptSHA {
			t.Fatal("原版 segment 雜湊不符")
		}
		view := passageSourceObservation{DS: p.Regs.DS, PointerSeg: p.Pointer.Seg, PointerOff: p.Pointer.Off, CallerSeg: p.Caller.Seg, CallerOff: p.Caller.Off, RawBaseOffset: p.Base.Off, RawCursorAfter: p.Cursor, Kind: p.Kind, Opcode: p.Opcode, Clear: p.Clear, Script: raw, Source: p.Source}
		for _, fixture := range fixtures {
			for i := range fixture.Fragments {
				if _, ok := matchPassageSource(fixture.passageSourceBinding, sources, i, view); ok {
					t.Fatal("將正常酒館單段誤認為整句")
				}
			}
		}
	}
}
